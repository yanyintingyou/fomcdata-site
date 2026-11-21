#!/usr/bin/env python3
"""Fetch public macro and market series and write public/data/market.json."""

import csv
import io
import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "public", "data", "market.json")
START = date(2006, 1, 1)
DAILY_TAIL_DAYS = 90
UA = {"User-Agent": "fomcdata-site/1.0 (+https://fomcdata.dpdns.org)"}


def get(url, timeout=45):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def parse_fred(text):
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
        if day >= START:
            rows.append((day, value))
    rows.sort()
    return rows


def fetch_effr():
    end = date.today().isoformat()
    url = (
        "https://markets.newyorkfed.org/api/rates/unsecured/effr/search.json"
        f"?startDate={START.isoformat()}&endDate={end}"
    )
    payload = json.loads(get(url))
    rows = []
    for item in payload.get("refRates", []):
        try:
            day = datetime.strptime(item["effectiveDate"][:10], "%Y-%m-%d").date()
            rows.append((day, float(item["percentRate"])))
        except (KeyError, ValueError):
            continue
    rows.sort()
    return rows


def fetch_cpi():
    rows = parse_fred(get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL"))
    by_month = {(d.year, d.month): v for d, v in rows}
    out = []
    for day, value in rows:
        base = by_month.get((day.year - 1, day.month))
        if base:
            out.append((day, round((value / base - 1) * 100, 2)))
    return out


def fetch_unrate():
    return parse_fred(get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=UNRATE"))


def fetch_spx_yahoo():
    start = int(datetime(2006, 1, 1, tzinfo=timezone.utc).timestamp())
    end = int(datetime.now(timezone.utc).timestamp())
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC"
        f"?period1={start}&period2={end}&interval=1d"
    )
    payload = json.loads(get(url))
    result = payload["chart"]["result"][0]
    stamps = result["timestamp"]
    closes = result["indicators"]["quote"][0]["close"]
    rows = []
    for stamp, close in zip(stamps, closes):
        if close is None:
            continue
        day = datetime.fromtimestamp(stamp, timezone.utc).date()
        if day >= START:
            rows.append((day, float(close)))
    if not rows:
        raise ValueError("empty yahoo series")
    rows.sort()
    return rows


def fetch_spx_stooq():
    text = get("https://stooq.com/q/d/l/?s=%5Espx&i=d").decode("utf-8", "replace")
    reader = csv.reader(io.StringIO(text))
    next(reader, None)
    rows = []
    for row in reader:
        if len(row) < 5 or not row[4]:
            continue
        try:
            day = datetime.strptime(row[0][:10], "%Y-%m-%d").date()
            value = float(row[4])
        except ValueError:
            continue
        if day >= START:
            rows.append((day, value))
    rows.sort()
    return rows


def fetch_spx():
    try:
        return fetch_spx_yahoo()
    except Exception:  # noqa: BLE001
        return fetch_spx_stooq()


def fetch_vix():
    text = get(
        "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
    ).decode("utf-8", "replace")
    rows = []
    reader = csv.reader(io.StringIO(text))
    next(reader, None)
    for row in reader:
        if len(row) < 5 or not row[4]:
            continue
        try:
            day = datetime.strptime(row[0].strip(), "%m/%d/%Y").date()
            value = float(row[4])
        except ValueError:
            continue
        if day >= START:
            rows.append((day, value))
    rows.sort()
    return rows


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


def build_series(spec):
    rows = spec["fetch"]()
    if spec["thin"]:
        rows = thin(rows)
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


def main():
    existing = load_existing()
    series = {}
    failed = []
    for spec in SPECS:
        key = spec["key"]
        try:
            item = build_series(spec)
        except Exception as exc:  # noqa: BLE001
            failed.append(f"{key}: {exc}")
            item = None
        if item:
            series[key] = item
        elif key in existing:
            series[key] = existing[key]
            failed.append(f"{key}: kept previous data")

    if not series:
        print("no series available", file=sys.stderr)
        return 1

    payload = {
        "updated": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "series": series,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, separators=(",", ":"), ensure_ascii=False)

    for key, item in series.items():
        print(f"{key}: {item['last']}{item['unit']} as of {item['asof']} ({len(item['points'])} points)")
    if failed:
        print("warnings: " + "; ".join(failed), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
