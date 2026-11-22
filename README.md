# fomcdata-site

[中文说明](README.zh-CN.md)

An index of public data sources for research on the Federal Open Market Committee, with a market snapshot drawn from public series.

Live: <https://fomcdata.dpdns.org>

## What the site has

The index lists 21 sources in five groups: Federal Reserve, international organizations, fiscal and cross-border capital, markets and regulation, literature. Each entry gives the publisher, the domain, and one line on what the source covers.

The snapshot tracks 35 series in five groups. Rates cover the target range, EFFR, SOFR, 2/10/30-year Treasury yields, spreads, the real yield, breakevens and the Fed balance sheet. Inflation covers CPI, core CPI, PCE, core PCE and the Michigan expectation, all year over year except the survey. Employment covers unemployment, U-6, payrolls, participation, wages, JOLTS and claims. Markets cover the S&P 500, gold, WTI, VIX, the broad dollar index, NFCI and high-yield and investment-grade spreads.

| Group | Series | Source | Starts |
|---|---|---|---|
| Rates | target range, SOFR, Treasury yields, spreads, real yield, breakeven, balance sheet, RRP, IORB | FRED | 1996–2021, depending on the series |
| Inflation | CPI, core CPI, PCE, core PCE, Michigan expectations | FRED | 1996 |
| Employment | unemployment, U-6, payrolls, participation, wages, JOLTS, claims | FRED | 1996 |
| Markets | S&P 500, gold, WTI, VIX | Yahoo Finance | 1996–2000 |
| Markets | broad dollar index, NFCI, HY and IG spreads | FRED | 1996–2023 |

Six pages share one stylesheet and three scripts: the index, a chart dashboard, macro cards, an FOMC calendar, research, and about. The dashboard compares up to four series, switches range and scale, prints window statistics, and exports CSV, PNG or SVG. Its state lives in the query string, so a view can be linked.

Pages open in English. The `中文` button switches all text, the page title and the chart labels, and stores the choice in `localStorage`.

## How the data updates

`scripts/fetch_data.py` runs in GitHub Actions every day at 23:17 UTC. FRED requests run in a pool of six; Yahoo runs serially with two attempts. Daily and weekly series pull the last 400 days. Monthly series pull full history, which keeps year-over-year bases and benchmark revisions current. Points older than 90 days are thinned to one per week, and anything older than five years to one per month.

Output is `public/data/meta.json` plus one file per group: `rates.json`, `macro.json`, `markets.json`. Meta carries labels and the latest values; a page fetches a group file only when one of its series is opened. The job commits `public/data` and deploys the Worker, and skips the commit when no point changed.

A push to `main` deploys the current files without fetching. To refresh data by hand, run the `deploy` workflow from the Actions tab.

## When a source fails

The script keeps the stored points for that series, sets `stale: true`, records the error in `warnings`, and continues with the other series. The page marks the affected tile with a small dot and prints the data cutoff under the chart.

FRED and Yahoo want different `User-Agent` headers: a plain one for FRED, a browser string for Yahoo. The script sets both per host, and each host gets retries with growing waits.

## Layout

```
public/                index, dashboard, macro, calendar,
                       research, about, 404
public/style.css       design tokens and components
public/site.js         language switch and page metadata
public/data.js         loading, windows, statistics, URL state
public/chart.js        SVG renderer, crosshair, exports
public/data/           meta, rates, macro, markets, calendar
scripts/fetch_data.py  fetch, merge, thin, and flag stale series
scripts/fetch_calendar.py  parse the Fed calendar, add new meetings, resolve links
.github/workflows/     daily refresh and deploy
wrangler.toml          Worker name and assets directory
```

The Worker serves static assets.

`fetch_calendar.py` reads the Federal Reserve meeting calendar once a day and merges new dates into `calendar.json`. Each meeting carries the statement page for its decision; older links resolve to the boarddocs archive or the historical page for that year. Links are resolved once and stored, so a normal run costs one request.

The calendar page folds years before the current one. Rows open the Federal Reserve statement for that meeting; a chart link beside each row opens the policy rate around that day.

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

A scheduled run set for 23:17 UTC usually starts within half an hour.

The index links to third-party sites. Those publishers own their data.
