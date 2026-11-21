# fomcdata-site

Public data source index for FOMC-related research, with a daily market snapshot.

- `public/` — static site served by Cloudflare Workers
- `scripts/fetch_data.py` — pulls EFFR, CPI, unemployment, S&P 500 and VIX into `public/data/market.json`
- `.github/workflows/deploy.yml` — refreshes the data daily at 06:00 UTC and deploys with wrangler

Local preview: `python -m http.server -d public 8123`

Deploy: `npx wrangler deploy`
