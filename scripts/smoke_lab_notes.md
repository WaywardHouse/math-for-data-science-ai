# Fire and Smoke lab notes

## API keys

The Quarto chapter `12-fire-and-smoke-lab.qmd` can use OpenAQ (requires an API key).

Set:

`OPENAQ_API_KEY=...`

## If you prefer not to use OpenAQ

Swap in a provincial/federal source and export:

- a `locations.csv` with `location_id,name,locality,latitude,longitude`
- a `pm25_daily.csv` with `date,pm25`

Then adjust the chapter to read local files first and only fall back to a remote
API.

