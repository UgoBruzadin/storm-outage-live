# County alerts

Every hour, after the forecast, `send.py` checks each county's chance against the alert levels and, for each county
that reaches one, adds an item to its RSS feed (`feeds/<county>.xml`) and, when push is turned on, sends a
notification to its ntfy topic (`storm-outage-<county>`).

> **Experimental research forecast.** Not from any utility or the National Weather Service. Don't use it for
> safety decisions.

## When a county is alerted

- **Once per storm.** A county is alerted when its chance reaches a level and it had no alert running; while it
  stays at or above a level it is not alerted again. An alert ends after 6 hours below every level.
- **Again if it gets worse.** Reaching a higher level than the alert running sends a new alert.

| Level | Alerts a year, typical county | Followed by an outage (2025) | Outages that had one |
|---|---|---|---|
| Elevated | about 9 | about 1 in 5 | 27% |
| High | about 4 to 5 | about 2 in 7 | 19% |

An outage here is a new outage of 5% or more of the county's customers, after a day with none. The numbers are for
Missouri and Illinois in 2025, a year the model it was tested with didn't train on (`ml/alert_counts.py` in
storm-outage-risk, `docs/alerts.md`). The median alert came 7 hours before the outage began.

## Levels belong to a model

A chance from one model doesn't mean the same as the same chance from another, so `config.json` keeps the levels per
model, under the `model_trained` stamp in `latest.json`. Each model's levels are set to give the same number of
alerts a year per county, read off a year it didn't train on. A forecast from a model with no levels sends nothing,
so a new model can't send alerts on the old model's cut-offs by accident.

## Files

| Path | What |
|---|---|
| `config.json` | Levels per model, the quiet hours, the push server and topic names, the disclaimer |
| `counties.json` | Every study county in the 48 states: name, state, time zone (for the alert's local times) |
| `state.json` | The alert running in each county (written every hour) |
| `send.py` | The alerts; `--dry-run` prints them without writing or sending |
| `test_send.py` | `python -m unittest alerts/test_send.py` |

## Push notifications

Off until turned on (`ntfy.enabled`). On the public ntfy.sh server anyone can post to any topic, so a county's
topic could carry messages that aren't ours; for wide use, run our own ntfy server where only this job can post (set
`ntfy.server`, and the `NTFY_TOKEN` repository secret).
