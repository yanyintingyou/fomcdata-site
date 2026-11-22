#!/usr/bin/env python3
"""Refresh the FOMC calendar from Federal Reserve pages.

fomccalendars.htm carries the current year, the two years before it and the
next year. Each meeting row holds the statement, press conference, projection
and minutes links plus the minutes release date, so one request fills the
whole decision record. Beige Book editions come from the publication page for
the running year and from the archive year pages for earlier ones; a year is
fetched once, then skipped.

Meetings and editions already stored stay put, so the 1996–2020 history
survives every run. Links resolved for old meetings are written back, which
keeps later runs down to two requests.
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
BEIGE_URL = BASE + "/monetarypolicy/publications/beige-book-default.htm"
BEIGE_ARCHIVE = BASE + "/monetarypolicy/beige-book-archive.htm"
UA = {
    "User-Agent": "fomcdata-site/1.0 (+https://fomcdata.dpdns.org)",
    "Accept": "*/*",
}
MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
HISTORICAL_LAST_YEAR = 2020

ROW = re.compile(r'<div class="(?:fomc-meeting--shaded )?row fomc-meeting"')
MONTH = re.compile(r'fomc-meeting__month[^>]*>\s*<strong>([^<]+)</strong>')
DAY = re.compile(r'fomc-meeting__date[^>]*>([^<]+)<')
HOST = r"(?:https://www\.federalreserve\.gov)?"
LINK = {
    "statement": re.compile(r'href="' + HOST + r'(/newsevents/pressreleases/monetary\d{8}a\.htm)"'),
    "press": re.compile(r'href="' + HOST + r'(/monetarypolicy/fomcpresconf\d{8}\.htm)"'),
    "projections": re.compile(r'href="' + HOST + r'(/monetarypolicy/fomcprojtabl?e?\d{8}\.htm)"'),
    "minutes": re.compile(r'href="' + HOST + r'(/monetarypolicy/fomcminutes\d{8}\.htm)"'),
}
RELEASED = re.compile(r"Released ([A-Z][a-z]+ \d{1,2}, \d{4})")
BEIGE_DATE = re.compile(r"BeigeBook_(\d{8})")
BEIGE_OLD = re.compile(r"/beigebook/\d{4}/(\d{8})/")


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


def day_range(year, month_text, day_text):
    sep = "*" in day_text
    parts = [int(p) for p in day_text.replace("*", "").split("-") if p.strip()]
    months = [m for m in month_text.split("/") if m.strip()]
    start = date(year, month_num(months[0]), parts[0])
    end = date(year, month_num(months[-1]), parts[-1])
    return start, end, sep


def parse_fomc(html):
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
                start, end, sep = day_range(year, mon.group(1), day.group(1))
            except ValueError:
                continue
            links = {}
            for key, pattern in LINK.items():
                hit = pattern.search(block)
                if hit:
                    links[key] = BASE + hit.group(1)
            released = RELEASED.search(block)
            minutes_date = None
            if released:
                try:
                    minutes_date = datetime.strptime(
                        released.group(1), "%B %d, %Y").date().isoformat()
                except ValueError:
                    minutes_date = None
            events.append({
                "date": end.isoformat(),
                "type": "fomc",
                "start": start.isoformat(),
                "sep": sep,
                "links": links,
                "minutes_date": minutes_date,
            })
    return events


def parse_beige(html):
    found = {}
    for href in re.findall(r'href="([^"]+)"', html):
        hit = BEIGE_DATE.search(href) or BEIGE_OLD.search(href)
        if not hit:
            continue
        try:
            day = datetime.strptime(hit.group(1), "%Y%m%d").date().isoformat()
        except ValueError:
            continue
        link = href if href.startswith("http") else BASE + href
        if day not in found or (".htm" in link and ".htm" not in found[day]):
            found[day] = link
    return found


def beige_years():
    try:
        html = get(BEIGE_ARCHIVE)
    except Exception as exc:  # noqa: BLE001
        print(f"beige archive unavailable: {exc}", file=sys.stderr)
        return []
    return sorted({int(y) for y in re.findall(r"/monetarypolicy/beigebook(\d{4})\.htm", html)})


def collect_beige(stored_years):
    found = {}
    try:
        found.update(parse_beige(get(BEIGE_URL)))
    except Exception as exc:  # noqa: BLE001
        print(f"beige page unavailable: {exc}", file=sys.stderr)
    years = [y for y in beige_years() if y not in stored_years]
    if years:
        with ThreadPoolExecutor(max_workers=6) as pool:
            for _, html in pool.map(
                    lambda y: (y, get(f"{BASE}/monetarypolicy/beigebook{y}.htm")), years):
                found.update(parse_beige(html))
    return found


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


def normalize(events):
    """Move the old single `url` field into links."""
    for ev in events:
        if ev["type"] != "fomc":
            continue
        links = ev.setdefault("links", {})
        old = ev.pop("url", None)
        if old and not links.get("statement"):
            links["statement"] = old
    return events


def backfill(meetings):
    todo = [e for e in meetings if not e["links"].get("statement")]
    if not todo:
        return 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        links = list(pool.map(lambda e: resolve(e["date"]), todo))
    filled = 0
    for ev, link in zip(todo, links):
        if link:
            ev["links"]["statement"] = link
            filled += 1
    return filled


def main():
    with open(CAL, encoding="utf-8") as fh:
        old = json.load(fh)
    before = json.dumps(old.get("events", []), sort_keys=True)
    events = normalize(list(old.get("events", [])))
    stored = {(e["type"], e["date"]): e for e in events}
    meetings = [e for e in events if e["type"] == "fomc"]

    try:
        parsed = parse_fomc(get(CAL_URL))
    except Exception as exc:  # noqa: BLE001
        print(f"calendar page unavailable: {exc}", file=sys.stderr)
        parsed = []
    if not parsed:
        print("no meetings parsed", file=sys.stderr)
        return 1

    added = 0
    for ev in parsed:
        cur = stored.get(("fomc", ev["date"]))
        if not cur:
            events.append(ev)
            stored[("fomc", ev["date"])] = ev
            meetings.append(ev)
            added += 1
            continue
        cur["sep"] = ev["sep"]
        cur["start"] = ev["start"]
        if ev.get("minutes_date"):
            cur["minutes_date"] = ev["minutes_date"]
        merged = cur.setdefault("links", {})
        for key, value in ev["links"].items():
            if value:
                merged[key] = value

    for ev in meetings:
        minutes = ev.get("minutes_date")
        link = ev["links"].get("minutes")
        if not minutes or not link:
            continue
        cur = stored.get(("minutes", minutes))
        if cur:
            cur["meeting"] = ev["date"]
            cur["url"] = link
            continue
        item = {"date": minutes, "type": "minutes", "meeting": ev["date"], "url": link}
        events.append(item)
        stored[("minutes", minutes)] = item
        added += 1

    stored_beige_years = {int(e["date"][:4]) for e in events if e["type"] == "beige"}
    for day, link in collect_beige(stored_beige_years).items():
        cur = stored.get(("beige", day))
        if cur:
            cur["url"] = link
            continue
        item = {"date": day, "type": "beige", "url": link}
        events.append(item)
        stored[("beige", day)] = item
        added += 1

    filled = backfill(meetings)
    events.sort(key=lambda e: (e["date"], e["type"]))

    if json.dumps(events, sort_keys=True) == before:
        print(f"{len(events)} entries, no change")
        return 0

    with open(CAL, "w", encoding="utf-8") as fh:
        json.dump({"updated": date.today().isoformat(), "events": events}, fh,
                  ensure_ascii=False, indent=0)

    counts = {}
    for ev in events:
        counts[ev["type"]] = counts.get(ev["type"], 0) + 1
    print(f"{len(events)} entries, {added} added, {filled} linked: " +
          ", ".join(f"{k}:{v}" for k, v in sorted(counts.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
