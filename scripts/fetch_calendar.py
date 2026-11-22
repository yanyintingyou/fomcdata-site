#!/usr/bin/env python3
"""Refresh the FOMC calendar from the Federal Reserve meeting calendar.

The live page carries the current year, the two years before it and the next
year, each meeting row holding the statement link. Meetings parsed from the
page are merged into public/data/calendar.json; entries already stored are
kept, so the 1996–2020 history stays put.

Events without a link get one resolved on the first run: the modern press
release path, the boarddocs path used before 2006, or the year page as a
fallback. Resolved links are stored, so later runs only touch new dates.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAL = os.path.join(ROOT, "public", "data", "calendar.json")
BASE = "https://www.federalreserve.gov"
CAL_URL = BASE + "/monetarypolicy/fomccalendars.htm"
UA = {
    "User-Agent": "fomcdata-site/1.0 (+https://fomcdata.dpdns.org)",
    "Accept": "*/*",
}
MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
HISTORICAL_LAST_YEAR = 2020

ROW = re.compile(r'<div class="[^"]*\bfomc-meeting\b[^"]*"')
MONTH = re.compile(r'fomc-meeting__month[^>]*>\s*<strong>([^<]+)</strong>')
DAY = re.compile(r'fomc-meeting__date[^>]*>([^<]+)<')
STATEMENT = re.compile(r'href="(/newsevents/pressreleases/monetary\d{8}a\.htm)"')


def get(url, timeout=45):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def exists(url):
    try:
        req = urllib.request.Request(url, headers=UA, method="HEAD")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status < 400
    except urllib.error.HTTPError:
        return False
    except Exception:  # noqa: BLE001
        return False


def month_num(token):
    key = token.strip()[:3].lower()
    if key not in MONTHS:
        raise ValueError("unknown month " + token)
    return MONTHS[key]


def end_date(year, month_text, day_text):
    sep = "*" in day_text
    parts = day_text.replace("*", "").split("-")
    day = int(parts[-1].strip())
    months = [m for m in month_text.split("/") if m.strip()]
    month = month_num(months[-1])
    return date(year, month, day), sep


def parse_page(html):
    events = []
    for chunk in html.split('<div class="panel panel-default">')[1:]:
        head = re.search(r">(\d{4}) FOMC Meetings<", chunk)
        if not head:
            continue
        year = int(head.group(1))
        for block in ROW.split(chunk)[1:]:
            mon = MONTH.search(block)
            day = DAY.search(block)
            if not mon or not day:
                continue
            try:
                when, sep = end_date(year, mon.group(1), day.group(1))
            except ValueError:
                continue
            link = STATEMENT.search(block)
            events.append({
                "date": when.isoformat(),
                "type": "fomc",
                "sep": sep,
                "url": BASE + link.group(1) if link else None,
            })
    return events


def candidates(day):
    ymd = day.strftime("%Y%m%d")
    y = day.strftime("%Y")
    return [
        f"{BASE}/newsevents/pressreleases/monetary{ymd}a.htm",
        f"{BASE}/boarddocs/press/general/{y}/{ymd}/",
        f"{BASE}/boarddocs/press/monetary/{y}/{ymd}/default.htm",
    ]


def resolve(date_text):
    when = datetime.strptime(date_text, "%Y-%m-%d").date()
    for url in candidates(when):
        if exists(url):
            return url
    if when.year <= HISTORICAL_LAST_YEAR:
        return f"{BASE}/monetarypolicy/fomchistorical{when.year}.htm"
    return None


def backfill(events):
    todo = [e for e in events if not e.get("url")]
    if not todo:
        return 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        links = list(pool.map(lambda e: resolve(e["date"]), todo))
    filled = 0
    for ev, link in zip(todo, links):
        if link:
            ev["url"] = link
            filled += 1
    return filled


def main():
    with open(CAL, encoding="utf-8") as fh:
        old = json.load(fh)
    before = json.dumps(old.get("events", []), sort_keys=True)
    stored = {e["date"]: e for e in old.get("events", [])}

    try:
        page = parse_page(get(CAL_URL))
    except Exception as exc:  # noqa: BLE001
        print(f"calendar page unavailable: {exc}", file=sys.stderr)
        page = []
    if not page:
        print("no meetings parsed", file=sys.stderr)
        return 1

    added = 0
    for ev in page:
        cur = stored.get(ev["date"])
        if not cur:
            stored[ev["date"]] = ev
            added += 1
            continue
        cur["sep"] = ev["sep"]
        if ev["url"]:
            cur["url"] = ev["url"]

    events = [stored[k] for k in sorted(stored)]
    filled = backfill(events)

    if json.dumps(events, sort_keys=True) == before:
        print(f"{len(events)} meetings, no change")
        return 0

    with open(CAL, "w", encoding="utf-8") as fh:
        json.dump({"updated": date.today().isoformat(), "events": events}, fh,
                  ensure_ascii=False, indent=0)

    years = {}
    for ev in events:
        years[ev["date"][:4]] = years.get(ev["date"][:4], 0) + 1
    print(f"{len(events)} meetings, {added} added, {filled} linked")
    print(", ".join(f"{y}:{n}" for y, n in sorted(years.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
