# County alert feeds

One RSS feed per county, `feeds/<county FIPS>.xml` (merged regions join their codes with `-`, e.g.
`29189-29510.xml` for St. Louis City + County). A county's feed appears with its first alert and keeps the last 20.
Written every hour by `alerts/send.py`; see `alerts/README.md`.
