# fomcdata-site

[中文说明](README.zh-CN.md)

An index of public data sources for research on the Federal Open Market Committee, with a market snapshot drawn from public series.

Live: <https://fomcdata.dpdns.org>

## What the site has

The index lists 21 sources in five groups: Federal Reserve, international organizations, fiscal and cross-border capital, markets and regulation, literature. Each entry gives the publisher, the domain, and one line on what the source covers.

The snapshot tracks seven series and draws them on one chart with 1Y, 3Y, 5Y, 10Y, 20Y and 30Y ranges. Hovering the chart shows a crosshair and the value at that date.

| Series | Source | Frequency | Starts |
|---|---|---|---|
| Effective fed funds rate | FRED `DFF` | daily | 1996 |
| CPI, year over year | FRED `CPIAUCSL`, computed here | monthly | 1997 |
| Unemployment rate | FRED `UNRATE` | monthly | 1996 |
| S&P 500 | Yahoo Finance `^GSPC` | daily | 1996 |
| Gold futures, front month | Yahoo Finance `GC=F` | daily | 2000 |
| WTI crude futures, front month | Yahoo Finance `CL=F` | daily | 2000 |
| VIX | Yahoo Finance `^VIX` | daily | 1996 |

Seven pages share one stylesheet and three scripts: the index, a chart dashboard, macro cards, an FOMC calendar, methodology, research, and about. The dashboard compares up to three series, switches range and scale, prints window statistics, and exports CSV, PNG or SVG. Its state lives in the query string, so a view can be linked.

Pages open in English. The `中文` button switches all text, the page title and the chart labels, and stores the choice in `localStorage`.

## How the data updates

`scripts/fetch_data.py` runs in GitHub Actions every day at 23:00 UTC, after the US close. Each run pulls the last 400 days for every series and merges that window into the stored history. Points older than 90 days get thinned to one per week, which keeps 30 years of history in a 180 KB file. The script commits the new `public/data/market.json` and deploys the Worker.

A push to `main` deploys the current files without fetching. To refresh data by hand, run the `deploy` workflow from the Actions tab.

## When a source fails

The script keeps the stored points for that series, sets `stale: true`, records the error in `warnings`, and continues with the other series. The page marks the affected tile with a small dot and prints the data cutoff under the chart.

FRED and Yahoo want different `User-Agent` headers: a plain one for FRED, a browser string for Yahoo. The script sets both per host, and each host gets retries with growing waits.

## Layout

```
public/                index, dashboard, macro, calendar, methodology,
                       research, about, 404
public/style.css       design tokens and components
public/site.js         language switch and page metadata
public/data.js         loading, windows, statistics, URL state
public/chart.js        SVG renderer, crosshair, exports
public/data/           market.json, calendar.json
scripts/fetch_data.py  fetch, merge, thin, and flag stale series
.github/workflows/     daily refresh and deploy
wrangler.toml          Worker name and assets directory
```

The Worker serves static assets.

## Local preview

```
python -m http.server -d public 8123
```

## Deploy

GitHub Actions deploys with `cloudflare/wrangler-action`. The workflow reads two repository secrets:

- `CLOUDFLARE_API_TOKEN`, scoped to `Account › Workers Scripts › Edit`
- `CLOUDFLARE_ACCOUNT_ID`

To deploy from your machine, put a token in the environment and run `npx wrangler deploy`.

## Licensing

Site code is MIT, see `LICENSE`. Data in `public/data/` follows its sources, listed in `LICENSE-DATA.md`. Research datasets are released as separate repositories with their own license and DOI.

## Notes

A scheduled run set for 23:00 UTC usually starts within half an hour.

The index links to third-party sites. Those publishers own their data. The repository has no license file.
