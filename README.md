# Storm Outage Risk: live forecast (beta)

Every hour, the chance that each Missouri and Illinois county has a **new power outage** (5% or more of its
customers, after a day with none) in the 6 hours starting 2 hours later.

> **Experimental research forecast.** Not from any utility or the National Weather Service. Don't use it for
> safety decisions.

This repo holds the forecasts and the job that makes them. The model, its tests and the write-up are in
[storm-outage-risk](https://github.com/UgoBruzadin/storm-outage-risk); the story page shows the latest map:
https://ugobruzadin.github.io/storm-outage-risk/

## What's here

| Path | What |
|---|---|
| `latest.json` | The newest hour: decision time, the 6-hour window, the forecast runs used, and per county `[fips, chance, low, high, alert]` |
| `predictions/YYYY/MM/DD/HH.parquet` | Every hour's forecast, one row per county |
| `inputs/YYYY/MM/DD/HH.csv.gz` | The inputs behind it (shakedown period only; rebuildable from the public archives) |

Each forecast is committed when it is made, so the commit history shows it existed before the weather it
forecasts. The job runs the code at tag
[`live-v1.1`](https://github.com/UgoBruzadin/storm-outage-risk/tree/live-v1.1/live) of storm-outage-risk: the model
can't change while it is being tested.

## The blind test

The forecasts will be graded against DOE's EAGLE-I outage records for 2026, once they are published, against NWS
warnings + SPC outlooks alone. On 2025, a year it never trained on, this model ranked new outages 2.2× better than
those official forecasts.
