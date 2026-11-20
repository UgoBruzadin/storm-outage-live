"""County alerts from the newest forecast: an RSS feed per county, and a push notification (ntfy) per county.

Run by the hourly job right after the forecast (.github/workflows/hourly.yml). Standard library only.

An alert is sent when a county's chance reaches a level in config.json and either
  - the county had no alert running (its last hour at a level was more than `quiet_hours` ago; ml/alert_counts.py
    in storm-outage-risk counts alerts the same way), or
  - it reached a higher level than the alert running.
While a county stays at or above a level, it is not alerted again: one alert per storm, not one per hour.

The levels are chances, and a chance belongs to one model: config.json keeps the levels per model (the `model_trained`
stamp in latest.json), each chosen to give the same number of alerts a year per county (docs in alerts/README.md).
A forecast from a model with no levels in config.json sends nothing.

Usage: python alerts/send.py [--latest latest.json] [--dry-run]
Reads alerts/config.json, alerts/counties.json, alerts/state.json; writes alerts/state.json and feeds/<region>.xml.
Push needs config ntfy.enabled; the token, if the server needs one, comes from the NTFY_TOKEN environment variable.
"""
import argparse
import json
import os
import sys
import urllib.request
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def hour(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%MZ").replace(tzinfo=UTC)


def iso(t):
    return f"{t:%Y-%m-%dT%H:%MZ}"


def slug(region):
    """A region id safe for topic and file names: 29189+29510 -> 29189-29510."""
    return region.replace("+", "-")


def level_of(chance, levels):
    """Index of the highest level reached (levels sorted low to high), or -1."""
    reached = [i for i, lv in enumerate(levels) if chance >= lv["chance"]]
    return reached[-1] if reached else -1


def decide(forecast, levels, state, quiet_hours):
    """The alerts to send for one forecast, and the new state. state: region -> {level, since, last_above}."""
    now = hour(forecast["decision_hour"])
    new_state, sends = {}, []
    for region, chance, low, high, *_ in forecast["counties"]:
        lv = level_of(chance, levels)
        prev = state.get(region)
        running = prev is not None and now - hour(prev["last_above"]) <= timedelta(hours=quiet_hours)
        if lv < 0:
            if running:
                new_state[region] = prev                    # keep it until it has been quiet long enough
            continue
        if not running or lv > prev["level"]:
            sends.append({"region": region, "level": lv, "chance": chance, "low": low, "high": high})
            new_state[region] = {"level": lv, "since": iso(now), "last_above": iso(now)}
        else:
            new_state[region] = {**prev, "last_above": iso(now)}
    return sends, new_state


def window_text(forecast, tz):
    a, b = (hour(t).astimezone(ZoneInfo(tz)) for t in forecast["window"])
    day = "today" if a.date() == hour(forecast["decision_hour"]).astimezone(ZoneInfo(tz)).date() else f"{a:%a}"
    fmt = lambda t: f"{t:%I %p}".lstrip("0").lower()
    return f"{fmt(a)} to {fmt(b)} {b:%Z} {day}"


def message(send, forecast, county, levels, cfg):
    name, state, tz = county
    lv = levels[send["level"]]
    title = f"{lv['label']} outage risk: {name}, {state}"
    body = (f"{send['chance']:.0%} chance of a new outage affecting 5% or more of customers, "
            f"{window_text(forecast, tz)} (range {send['low']:.0%}-{send['high']:.0%}). "
            f"{lv['meaning']} {cfg['disclaimer']}")
    return title, body


def push(cfg, topic, title, body, priority, link):
    req = urllib.request.Request(f"{cfg['ntfy']['server'].rstrip('/')}/{topic}", data=body.encode(), method="POST")
    req.add_header("Title", title)
    req.add_header("Priority", str(priority))
    req.add_header("Tags", "zap")
    req.add_header("Click", link)
    if token := os.environ.get("NTFY_TOKEN"):
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=20) as r:
        r.read()


def write_feed(path, county, items, cfg):
    name, state, _ = county
    entries = "".join(
        f"<item><title>{escape(i['title'])}</title><description>{escape(i['body'])}</description>"
        f"<link>{escape(i['link'])}</link><guid isPermaLink=\"false\">{escape(i['guid'])}</guid>"
        f"<pubDate>{i['date']}</pubDate></item>" for i in items)
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel>'
        f"<title>Storm outage alerts: {escape(name)}, {state}</title><link>{escape(cfg['link'])}</link>"
        f"<description>{escape(cfg['disclaimer'])}</description>{entries}</channel></rss>\n")


def read_feed_items(path):
    """The items already in a feed (newest first), kept as dicts so the feed can be rewritten."""
    if not path.exists():
        return []
    import xml.etree.ElementTree as ET
    items = []
    for it in ET.parse(path).getroot().iter("item"):
        items.append({k: it.findtext(t) for k, t in
                      (("title", "title"), ("body", "description"), ("link", "link"), ("guid", "guid"),
                       ("date", "pubDate"))})
    return items


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", default=ROOT / "latest.json", type=Path)
    ap.add_argument("--dry-run", action="store_true", help="print the alerts; write and send nothing")
    a = ap.parse_args(argv)

    cfg = json.loads((HERE / "config.json").read_text())
    counties = json.loads((HERE / "counties.json").read_text())
    forecast = json.loads(a.latest.read_text())
    model = forecast.get("model_trained")
    levels = cfg["levels"].get(model)
    if not levels:
        print(f"No alert levels for the model trained {model}: nothing sent.")
        return 0
    levels = sorted(levels, key=lambda lv: lv["chance"])

    state_path = HERE / "state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    if state.get("_hour") and hour(state["_hour"]) >= hour(forecast["decision_hour"]):
        print(f"Alerts for {forecast['decision_hour']} already done.")
        return 0
    sends, new_state = decide(forecast, levels, state.get("counties", {}), cfg["quiet_hours"])

    feeds = ROOT / "feeds"
    feeds.mkdir(exist_ok=True)
    made = forecast.get("generated_at")
    made = datetime.strptime(made, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC) if made else datetime.now(UTC)
    failed = 0
    for s in sends:
        county = counties.get(s["region"], [s["region"], "", "UTC"])
        title, body = message(s, forecast, county, levels, cfg)
        link = f"{cfg['link']}?county={s['region']}"
        print(f"{s['region']:12} {title} | {body}")
        if a.dry_run:
            continue
        path = feeds / f"{slug(s['region'])}.xml"
        items = [{"title": title, "body": body, "link": link, "date": format_datetime(made),
                  "guid": f"{s['region']}-{forecast['decision_hour']}-{s['level']}"}] + read_feed_items(path)
        write_feed(path, county, items[:cfg["feed_items"]], cfg)
        if cfg["ntfy"]["enabled"]:
            try:
                push(cfg, cfg["ntfy"]["topic"].format(region=slug(s["region"])), title, body,
                     levels[s["level"]]["priority"], link)
            except OSError as e:                             # one failed push must not stop the others
                failed += 1
                print(f"  push failed: {e}", file=sys.stderr)
    print(f"{len(sends)} alerts for {forecast['decision_hour']} ({len(new_state)} counties with an alert running)"
          + (f", {failed} pushes failed" if failed else ""))
    if not a.dry_run:
        state_path.write_text(json.dumps({"_hour": forecast["decision_hour"], "model": model,
                                          "counties": new_state}, indent=1, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
