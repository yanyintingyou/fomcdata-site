#!/usr/bin/env python3
"""Fetch public macro and market series into public/data.

meta.json holds labels and the latest values; one file per group holds the
points. Each run pulls a recent window for daily series and full history for
monthly ones, merges it into the stored points, and leaves untouched series
alone.
"""

import csv
import io
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "public", "data")
META = os.path.join(DATA, "meta.json")
FULL_START = date(1996, 1, 1)
WINDOW_DAYS = 400
DAILY_TAIL_DAYS = 90
WEEKLY_YEARS = 5
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
    meta = result.get("meta") or {}
    end = (meta.get("currentTradingPeriod") or {}).get("regular", {}).get("end")
    market_time = meta.get("regularMarketTime")
    # drop today's bar while the regular session is still open
    if (
        rows
        and end
        and market_time
        and rows[-1][0] == datetime.fromtimestamp(end, timezone.utc).date()
        and market_time < end - 60
    ):
        rows.pop()
    return rows


def fetch_yahoo(symbol, start):
    last = None
    time.sleep(1.5)
    for attempt in range(2):
        try:
            return fetch_yahoo_once(symbol, start, YAHOO_HOSTS[attempt % 2])
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(4)
    raise last


def yoy(rows):
    by_month = {(d.year, d.month): v for d, v in rows}
    out = []
    for day, value in rows:
        base = by_month.get((day.year - 1, day.month))
        if base:
            out.append((day, round((value / base - 1) * 100, 2)))
    return out


def monthly_change(rows):
    out = []
    for i in range(1, len(rows)):
        out.append((rows[i][0], rows[i][1] - rows[i - 1][1]))
    return out


def scaled(factor):
    return lambda rows: [(d, v * factor) for d, v in rows]


def fr(series_id, transform=None, full=False):
    def fetch(start):
        rows = fetch_fred(series_id, FULL_START if (full or transform) else start)
        if transform:
            rows = transform(rows)
        return rows
    return fetch


def yh(symbol):
    return lambda start: fetch_yahoo(symbol, start)


_SPECS = [
    # rates
    ("effr", fr("DFF"), "Effective fed funds rate", "联邦基金有效利率", "EFFR", "联邦基金利率",
     "%", 2, "rates", "rates", "daily", "FRED DFF", False, True, True),
    ("target_upper", fr("DFEDTARU"), "Fed target range, upper bound", "联邦基金目标区间上限", "Target high", "目标上限",
     "%", 2, "rates", "rates", "daily", "FRED DFEDTARU", False, False, True),
    ("target_lower", fr("DFEDTARL"), "Fed target range, lower bound", "联邦基金目标区间下限", "Target low", "目标下限",
     "%", 2, "rates", "rates", "daily", "FRED DFEDTARL", False, False, True),
    ("sofr", fr("SOFR"), "SOFR", "担保隔夜融资利率", "SOFR", "SOFR",
     "%", 2, "rates", "rates", "daily", "FRED SOFR", False, False, True),
    ("dgs2", fr("DGS2"), "2-year Treasury yield", "2 年期美债收益率", "2Y", "2 年",
     "%", 2, "rates", "rates", "daily", "FRED DGS2", False, False, True),
    ("dgs10", fr("DGS10"), "10-year Treasury yield", "10 年期美债收益率", "10Y", "10 年",
     "%", 2, "rates", "rates", "daily", "FRED DGS10", False, True, True),
    ("dgs30", fr("DGS30"), "30-year Treasury yield", "30 年期美债收益率", "30Y", "30 年",
     "%", 2, "rates", "rates", "daily", "FRED DGS30", False, False, True),
    ("spread_10y2y", fr("T10Y2Y"), "10-year minus 2-year spread", "10 年减 2 年利差", "10Y-2Y", "10Y-2Y",
     "%", 2, "rates", "rates", "daily", "FRED T10Y2Y", False, False, True),
    ("spread_10y3m", fr("T10Y3M"), "10-year minus 3-month spread", "10 年减 3 个月利差", "10Y-3M", "10Y-3M",
     "%", 2, "rates", "rates", "daily", "FRED T10Y3M", False, False, True),
    ("real10", fr("DFII10"), "10-year real yield", "10 年期实际利率", "Real 10Y", "实际 10Y",
     "%", 2, "rates", "rates", "daily", "FRED DFII10", False, False, True),
    ("breakeven10", fr("T10YIE"), "10-year breakeven inflation", "10 年期通胀预期", "Breakeven 10Y", "盈亏平衡 10Y",
     "%", 2, "rates", "rates", "daily", "FRED T10YIE", False, False, True),
    ("walcl", fr("WALCL", scaled(1 / 1e6)), "Fed total assets", "美联储总资产", "Fed assets", "总资产",
     "T", 2, "rates", "rates", "weekly", "FRED WALCL", False, False, True),
    ("reserves", fr("WRESBAL", scaled(1 / 1e6)), "Reserve balances", "准备金余额", "Reserves", "准备金",
     "T", 2, "rates", "rates", "weekly", "FRED WRESBAL", False, False, True),
    ("rrp", fr("RRPONTSYD"), "Overnight reverse repo", "隔夜逆回购", "RRP", "逆回购",
     "B", 1, "rates", "rates", "daily", "FRED RRPONTSYD", False, False, True),
    ("iorb", fr("IORB"), "Interest on reserve balances", "准备金余额利率", "IORB", "IORB",
     "%", 2, "rates", "rates", "daily", "FRED IORB", False, False, True),
    # inflation
    ("cpi", fr("CPIAUCSL", yoy), "CPI inflation, year over year", "CPI 同比", "CPI YoY", "CPI 同比",
     "%", 2, "inflation", "inflation", "monthly", "FRED CPIAUCSL", False, True, False),
    ("core_cpi", fr("CPILFESL", yoy), "Core CPI, year over year", "核心 CPI 同比", "Core CPI", "核心 CPI",
     "%", 2, "inflation", "inflation", "monthly", "FRED CPILFESL", False, False, False),
    ("pce", fr("PCEPI", yoy), "PCE inflation, year over year", "PCE 同比", "PCE YoY", "PCE 同比",
     "%", 2, "inflation", "inflation", "monthly", "FRED PCEPI", False, False, False),
    ("core_pce", fr("PCEPILFE", yoy), "Core PCE, year over year", "核心 PCE 同比", "Core PCE", "核心 PCE",
     "%", 2, "inflation", "inflation", "monthly", "FRED PCEPILFE", False, False, False),
    ("mich", fr("MICH"), "Michigan 1-year inflation expectation", "密歇根 1 年通胀预期", "Expectations", "通胀预期",
     "%", 2, "inflation", "inflation", "monthly", "FRED MICH", False, False, False),
    # labor
    ("unrate", fr("UNRATE"), "Unemployment rate", "失业率", "UNRATE", "失业率",
     "%", 2, "labor", "labor", "monthly", "FRED UNRATE", False, True, False),
    ("u6", fr("U6RATE"), "U-6 unemployment", "U6 失业率", "U-6", "U6",
     "%", 2, "labor", "labor", "monthly", "FRED U6RATE", False, False, False),
    ("payrolls", fr("PAYEMS", monthly_change), "Nonfarm payroll change", "非农新增就业", "Payrolls", "非农",
     "K", 0, "labor", "labor", "monthly", "FRED PAYEMS", False, False, False),
    ("civpart", fr("CIVPART"), "Labor force participation", "劳动参与率", "Participation", "参与率",
     "%", 2, "labor", "labor", "monthly", "FRED CIVPART", False, False, False),
    ("ahetpi", fr("AHETPI", yoy), "Average hourly earnings, year over year", "平均时薪同比", "Wages", "时薪",
     "%", 2, "labor", "labor", "monthly", "FRED AHETPI", False, False, False),
    ("jolts", fr("JTSJOL", scaled(1 / 1e3)), "Job openings", "职位空缺", "JOLTS", "职位空缺",
     "M", 2, "labor", "labor", "monthly", "FRED JTSJOL", False, False, False),
    ("claims", fr("ICSA", scaled(1 / 1e3)), "Initial jobless claims", "初请失业金", "Claims", "初请",
     "K", 0, "labor", "labor", "weekly", "FRED ICSA", False, False, True),
    # markets
    ("spx", yh("^GSPC"), "S&P 500 index", "标普 500 指数", "S&P 500", "标普 500",
     "", 0, "markets", "markets", "daily", "Yahoo Finance ^GSPC", False, True, True),
    ("gold", yh("GC=F"), "Gold futures, USD per ounce", "黄金期货，美元/盎司", "Gold", "黄金",
     "", 0, "commodities", "markets", "daily", "Yahoo Finance GC=F", False, True, True),
    ("oil", yh("CL=F"), "WTI crude futures, USD per barrel", "WTI 原油期货，美元/桶", "WTI", "WTI 原油",
     "", 2, "commodities", "markets", "daily", "Yahoo Finance CL=F", False, True, True),
    ("vix", yh("^VIX"), "VIX index", "VIX 指数", "VIX", "VIX",
     "", 2, "markets", "markets", "daily", "Yahoo Finance ^VIX", False, True, True),
    ("dollar", fr("DTWEXBGS"), "Broad dollar index", "广义美元指数", "Dollar", "美元指数",
     "", 2, "markets", "markets", "daily", "FRED DTWEXBGS", False, False, True),
    ("nfci", fr("NFCI"), "Chicago Fed financial conditions", "芝加哥联储金融条件指数", "NFCI", "NFCI",
     "", 2, "markets", "markets", "weekly", "FRED NFCI", False, False, True),
    ("hy_oas", fr("BAMLH0A0HYM2"), "High-yield credit spread", "高收益债利差", "HY OAS", "高收益利差",
     "%", 2, "markets", "markets", "daily", "FRED BAMLH0A0HYM2", False, False, True),
    ("ig_oas", fr("BAMLC0A0CM"), "Investment-grade credit spread", "投资级债利差", "IG OAS", "投资级利差",
     "%", 2, "markets", "markets", "daily", "FRED BAMLC0A0CM", False, False, True),
]

FIELDS = ("key", "fetch", "label_en", "label_zh", "tile_en", "tile_zh", "unit", "decimals",
          "category", "group", "frequency", "source", "hidden", "featured", "thin")
GROUP_FILE = {
    "rates": "rates",
    "inflation": "macro",
    "labor": "macro",
    "markets": "markets",
    "commodities": "markets",
}
SPECS = []
for row in _SPECS:
    spec = dict(zip(FIELDS, row))
    spec["group"] = GROUP_FILE[spec["category"]]
    SPECS.append(spec)


def thin(rows):
    if not rows:
        return rows
    today = date.today()
    recent_cut = today - timedelta(days=DAILY_TAIL_DAYS)
    weekly_cut = date(today.year - WEEKLY_YEARS, today.month, today.day)
    recent = []
    weekly = {}
    monthly = {}
    for day, value in rows:
        if day >= recent_cut:
            recent.append((day, value))
        elif day >= weekly_cut:
            iso = day.isocalendar()
            weekly[(iso[0], iso[1])] = (day, value)
        else:
            monthly[(day.year, day.month)] = (day, value)
    return (
        [monthly[k] for k in sorted(monthly)]
        + [weekly[k] for k in sorted(weekly)]
        + recent
    )


def merge(old_points, new_rows):
    if not old_points:
        return new_rows
    if not new_rows:
        return old_points
    cutoff = new_rows[0][0]
    tail = [p for p in old_points if p[0] > new_rows[-1][0]]
    return [p for p in old_points if p[0] < cutoff] + new_rows + tail


def load_existing():
    meta = {}
    groups = {}
    try:
        with open(META, encoding="utf-8") as fh:
            meta = json.load(fh)
    except (OSError, ValueError):
        meta = {}
    for group in ("rates", "macro", "markets"):
        path = os.path.join(DATA, group + ".json")
        try:
            with open(path, encoding="utf-8") as fh:
                groups[group] = json.load(fh).get("series", {})
        except (OSError, ValueError):
            groups[group] = {}
    return meta, groups


def parse_points(raw):
    return [(datetime.strptime(p[0], "%Y-%m-%d").date(), float(p[1])) for p in raw]


def fetch_recessions():
    rows = fetch_fred("USREC", FULL_START)
    spans = []
    start = None
    for day, value in rows:
        if value >= 1 and start is None:
            start = day
        elif value < 1 and start is not None:
            spans.append([start.isoformat(), day.isoformat()])
            start = None
    if start is not None:
        spans.append([start.isoformat(), date.today().isoformat()])
    return spans


def build_meta(spec, rows, prev, error, now):
    last_day, last_value = rows[-1]
    prev_value = rows[-2][1] if len(rows) > 1 else last_value
    item = {
        "label_en": spec["label_en"],
        "label_zh": spec["label_zh"],
        "tile_en": spec["tile_en"],
        "tile_zh": spec["tile_zh"],
        "unit": spec["unit"],
        "decimals": spec["decimals"],
        "category": spec["category"],
        "group": spec["group"],
        "frequency": spec["frequency"],
        "source": spec["source"],
        "hidden": spec["hidden"],
        "featured": spec["featured"],
        "asof": last_day.isoformat(),
        "last": round(last_value, spec["decimals"]),
        "prev": round(prev_value, spec["decimals"]),
        "n": len(rows),
        "full": bool(prev.get("full") or prev.get("asof") is None),
        "stale": bool(error),
        "fetched": prev.get("fetched") if error else now,
    }
    return item


def main():
    old_meta, old_groups = load_existing()
    have_history = bool(old_meta.get("series"))
    start = date.today() - timedelta(days=WINDOW_DAYS) if have_history else FULL_START
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    results = {}
    errors = {}
    starts = {}
    for spec in SPECS:
        old = old_groups.get(spec["group"], {}).get(spec["key"])
        prev = old_meta.get("series", {}).get(spec["key"], {})
        starts[spec["key"]] = start if (old and prev.get("full")) else FULL_START

    fred_specs = [s for s in SPECS if s["source"].startswith("FRED")]
    yahoo_specs = [s for s in SPECS if s["source"].startswith("Yahoo")]

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(spec["fetch"], starts[spec["key"]]): spec for spec in fred_specs}
        for future, spec in futures.items():
            try:
                results[spec["key"]] = future.result()
            except Exception as exc:  # noqa: BLE001
                errors[spec["key"]] = str(exc)
    for spec in yahoo_specs:
        try:
            results[spec["key"]] = spec["fetch"](starts[spec["key"]])
        except Exception as exc:  # noqa: BLE001
            errors[spec["key"]] = str(exc)

    meta_series = {}
    group_series = {"rates": {}, "macro": {}, "markets": {}}
    changed = False
    for spec in SPECS:
        key = spec["key"]
        rows = results.get(key) or []
        error = errors.get(key)
        prev = old_meta.get("series", {}).get(key, {})
        old_points = old_groups.get(spec["group"], {}).get(key) or []
        if old_points:
            rows = merge(parse_points(old_points), rows)
        if spec["thin"]:
            rows = thin(rows)
        if not rows:
            if key in old_meta.get("series", {}):
                meta_series[key] = prev
                group_series[spec["group"]][key] = old_points
            continue
        item = build_meta(spec, rows, prev, error, now)
        item["full"] = bool(prev.get("full")) or starts[key] == FULL_START
        points = [[d.isoformat(), round(v, spec["decimals"])] for d, v in rows]
        meta_series[key] = item
        group_series[spec["group"]][key] = points
        if points != old_points or prev.get("stale") != item["stale"]:
            changed = True

    if not meta_series:
        print("no series available", file=sys.stderr)
        return 1

    try:
        recessions = fetch_recessions()
    except Exception:  # noqa: BLE001
        recessions = old_meta.get("recessions", [])

    warnings = [f"{k}: {v}" for k, v in errors.items()]
    if not changed and not warnings and have_history:
        print("market data unchanged")
        return 0

    meta = {
        "updated": now,
        "warnings": warnings,
        "recessions": recessions,
        "series": meta_series,
    }
    os.makedirs(DATA, exist_ok=True)
    with open(META, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, separators=(",", ":"), ensure_ascii=False)
    for group, series in group_series.items():
        path = os.path.join(DATA, group + ".json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"series": series}, fh, separators=(",", ":"), ensure_ascii=False)

    for key, item in meta_series.items():
        flag = " STALE" if item.get("stale") else ""
        print(f"{key}: {item['last']}{item['unit']} as of {item['asof']} ({item['n']} points){flag}")
    if warnings:
        print("warnings: " + "; ".join(warnings), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
