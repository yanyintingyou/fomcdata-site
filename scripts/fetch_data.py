#!/usr/bin/env python3
"""Fetch public macro and market series and write public/data/market.json.

History already in market.json is kept; each run only pulls a recent window
and merges it in, so the download stays small while the series keeps 30 years.
"""

import csv
import io
import json
import os
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "public", "data", "market.json")
FULL_START = date(1996, 1, 1)
WINDOW_DAYS = 400
DAILY_TAIL_DAYS = 90
UA_SITE = {
    "User-Agent": "fomcdata-site/1.0 (+https://fomcdata.dpdns.org)",
    "Accept": "*/*",
}
# Yahoo answers 403 to non-browser agents; FRED drops the connection for them.
UA_BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
}


def get(url, timeout=45, headers=UA_SITE):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def parse_fred(text, start):
    if isinstance(text, bytes):
        text = text.decode("utf-8", "replace")
    rows = []
    reader = csv.reader(io.StringIO(text))
    next(reader, None)
    for row in reader:
        if len(row) < 2 or not row[1] or row[1] == ".":
            continue
        try:
            day = datetime.strptime(row[0][:10], "%Y-%m-%d").date()
            value = float(row[1])
        except ValueError:
            continue
        if day >= start:
            rows.append((day, value))
    rows.sort()
    return rows


def with_retry(fn, attempts=3, wait=2):
    last = None
    for attempt in range(attempts):
        try:
            rows = fn()
            if not rows:
                raise ValueError("empty series")
            return rows
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(wait + attempt * 3)
    raise last


def fred_rows(series_id, start):
    url = (
        f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        f"&cosd={start.isoformat()}"
    )
    return parse_fred(get(url), start)


def fetch_fred(series_id, start):
    return with_retry(lambda: fred_rows(series_id, start))


YAHOO_HOSTS = ("query1.finance.yahoo.com", "query2.finance.yahoo.com")


def fetch_yahoo_once(symbol, start, host=YAHOO_HOSTS[0]):
    p1 = int(datetime(start.year, start.month, start.day, tzinfo=timezone.utc).timestamp())
    p2 = int(datetime.now(timezone.utc).timestamp())
    url = (
        f"https://{host}/v8/finance/chart/{quote(symbol, safe='')}"
        f"?period1={p1}&period2={p2}&interval=1d"
    )
    payload = json.loads(get(url, headers=UA_BROWSER))
    result = payload["chart"]["result"][0]
    stamps = result.get("timestamp") or []
    closes = result["indicators"]["quote"][0]["close"]
    rows = []
    for stamp, close in zip(stamps, closes):
        if close is None:
            continue
        day = datetime.fromtimestamp(stamp, timezone.utc).date()
        if day >= start:
            rows.append((day, float(close)))
    if not rows:
        raise ValueError("empty yahoo series")
    rows.sort()
    return rows


def fetch_yahoo(symbol, start):
    last = None
    time.sleep(2)
    for attempt in range(4):
        try:
            return fetch_yahoo_once(symbol, start, YAHOO_HOSTS[attempt % 2])
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(5 * (attempt + 1))
    raise last


def fetch_effr(start):
    return fetch_fred("DFF", start)


def fetch_unrate(start):
    return fetch_fred("UNRATE", start)


def fetch_cpi(start):
    rows = with_retry(lambda: fred_rows("CPIAUCSL", FULL_START))
    by_month = {(d.year, d.month): v for d, v in rows}
    out = []
    for day, value in rows:
        base = by_month.get((day.year - 1, day.month))
        if base and day >= start:
            out.append((day, round((value / base - 1) * 100, 2)))
    return out


def fetch_spx(start):
    return fetch_yahoo("^GSPC", start)


def fetch_gold(start):
    return fetch_yahoo("GC=F", start)


def fetch_oil(start):
    return fetch_yahoo("CL=F", start)


def fetch_vix(start):
    return fetch_yahoo("^VIX", start)


def thin(rows):
    if not rows:
        return rows
    cutoff = date.today() - timedelta(days=DAILY_TAIL_DAYS)
    weekly = {}
    recent = []
    for day, value in rows:
        if day >= cutoff:
            recent.append((day, value))
        else:
            iso = day.isocalendar()
            weekly[(iso[0], iso[1])] = (day, value)
    return [weekly[key] for key in sorted(weekly)] + recent


def merge(old_points, new_rows):
    if not old_points:
        return new_rows
    if not new_rows:
        return old_points
    cutoff = new_rows[0][0]
    tail = [p for p in old_points if p[0] > new_rows[-1][0]]
    return [p for p in old_points if p[0] < cutoff] + new_rows + tail


SPECS = [
    {
        "key": "effr",
        "fetch": fetch_effr,
        "label_en": "Effective fed funds rate",
        "label_zh": "联邦基金有效利率",
        "tile_en": "EFFR",
        "tile_zh": "联邦基金利率",
        "unit": "%",
        "decimals": 2,
        "thin": True,
    },
    {
        "key": "cpi",
        "fetch": fetch_cpi,
        "label_en": "CPI inflation, year over year",
        "label_zh": "CPI 同比",
        "tile_en": "CPI YoY",
        "tile_zh": "CPI 同比",
        "unit": "%",
        "decimals": 2,
        "thin": False,
    },
    {
        "key": "unrate",
        "fetch": fetch_unrate,
        "label_en": "Unemployment rate",
        "label_zh": "失业率",
        "tile_en": "UNRATE",
        "tile_zh": "失业率",
        "unit": "%",
        "decimals": 2,
        "thin": False,
    },
    {
        "key": "spx",
        "fetch": fetch_spx,
        "label_en": "S&P 500 index",
        "label_zh": "标普 500 指数",
        "tile_en": "S&P 500",
        "tile_zh": "标普 500",
        "unit": "",
        "decimals": 0,
        "thin": True,
    },
    {
        "key": "gold",
        "fetch": fetch_gold,
        "label_en": "Gold futures, USD per ounce",
        "label_zh": "黄金期货，美元/盎司",
        "tile_en": "Gold",
        "tile_zh": "黄金",
        "unit": "",
        "decimals": 0,
        "thin": True,
    },
    {
        "key": "oil",
        "fetch": fetch_oil,
        "label_en": "WTI crude futures, USD per barrel",
        "label_zh": "WTI 原油期货，美元/桶",
        "tile_en": "WTI",
        "tile_zh": "WTI 原油",
        "unit": "",
        "decimals": 2,
        "thin": True,
    },
    {
        "key": "vix",
        "fetch": fetch_vix,
        "label_en": "VIX index",
        "label_zh": "VIX 指数",
        "tile_en": "VIX",
        "tile_zh": "VIX",
        "unit": "",
        "decimals": 2,
        "thin": True,
    },
]


def build_series(spec, rows):
    if not rows:
        return None
    last_day, last_value = rows[-1]
    prev_value = rows[-2][1] if len(rows) > 1 else last_value
    return {
        "label_en": spec["label_en"],
        "label_zh": spec["label_zh"],
        "tile_en": spec["tile_en"],
        "tile_zh": spec["tile_zh"],
        "short": spec["tile_en"],
        "unit": spec["unit"],
        "decimals": spec["decimals"],
        "asof": last_day.isoformat(),
        "last": round(last_value, spec["decimals"]),
        "prev": round(prev_value, spec["decimals"]),
        "points": [[d.isoformat(), round(v, spec["decimals"])] for d, v in rows],
    }


def load_existing():
    try:
        with open(OUT, encoding="utf-8") as fh:
            return json.load(fh).get("series", {})
    except (OSError, ValueError):
        return {}


def parse_points(raw):
    return [(datetime.strptime(p[0], "%Y-%m-%d").date(), float(p[1])) for p in raw]


def main():
    existing = load_existing()
    start = date.today() - timedelta(days=WINDOW_DAYS) if existing else FULL_START
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    series = {}
    failed = []
    for spec in SPECS:
        key = spec["key"]
        prev = existing.get(key) or {}
        try:
            rows = spec["fetch"](start)
            error = None
        except Exception as exc:  # noqa: BLE001
            rows = []
            error = str(exc)
        old = prev.get("points")
        if old:
            rows = merge(parse_points(old), rows)
        if spec["thin"]:
            rows = thin(rows)
        item = build_series(spec, rows)
        if not item:
            if key in existing:
                series[key] = existing[key]
            failed.append(f"{key}: no data")
            continue
        item["stale"] = bool(error)
        item["fetched"] = prev.get("fetched") if error else now
        series[key] = item
        if error:
            failed.append(f"{key}: {error}")

    if not series:
        print("no series available", file=sys.stderr)
        return 1

    payload = {
        "updated": now,
        "warnings": failed,
        "series": series,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, separators=(",", ":"), ensure_ascii=False)

    for key, item in series.items():
        flag = " STALE" if item.get("stale") else ""
        print(f"{key}: {item['last']}{item['unit']} as of {item['asof']} ({len(item['points'])} points){flag}")
    if failed:
        print("warnings: " + "; ".join(failed), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
