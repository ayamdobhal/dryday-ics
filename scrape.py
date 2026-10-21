#!/usr/bin/env python3
"""Fetch the full Mumbai calendar from isitadryday.in and emit iCalendar.

Reads structured page data, validates location and dates before writing, and
retains history from previous years. Stdlib only; python scrape.py maharashtra.
The legacy maharashtra slug is retained for existing calendar subscriptions.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from zoneinfo import ZoneInfo
from pathlib import Path

BASE = "https://isitadryday.in"
REGIONS = {
    # slug: (site path, display name)
    "maharashtra": ("city/mumbai-dry-days", "Mumbai"),
}
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
FEED_DIR = ROOT / "docs"
USER_AGENT = "dryday-ics (+https://github.com/ayamdobhal/dryday-ics)"

class PageDataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.capture = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script" and dict(attrs).get("id") == "__NEXT_DATA__":
            self.capture = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self.capture = False

    def handle_data(self, data: str) -> None:
        if self.capture:
            self.parts.append(data)


def fetch(path: str) -> str:
    req = urllib.request.Request(f"{BASE}/{path}", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def parse(html: str) -> tuple[int, dict[str, dict]]:
    """Validate the annual Mumbai list; fail closed on changed/empty source data."""
    parser = PageDataParser()
    parser.feed(html)
    if not parser.parts:
        raise ValueError("Missing structured calendar data; leaving existing feed intact")
    props = json.loads("".join(parser.parts))["props"]["pageProps"]
    if props.get("slug") != "mumbai-dry-days" or props.get("mode") != "list":
        raise ValueError("Source is not the Mumbai annual calendar")
    year = props.get("currentYear")
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    if type(year) is not int or year != today.year:
        raise ValueError("Source calendar year is stale or unexpected")
    entries = props.get("dryDays")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Source calendar is missing or empty; leaving existing feed intact")
    events: dict[str, dict] = {}
    for entry in entries:
        iso, reason = entry.get("date"), entry.get("reason")
        if not isinstance(iso, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", iso):
            raise ValueError("Invalid calendar date")
        if date.fromisoformat(iso).year != year:
            raise ValueError("Event outside the source calendar year")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("Event reason is missing")
        if iso in events:
            raise ValueError(f"Duplicate calendar date: {iso}")
        events[iso] = {"reason": reason.strip(), "where": "Mumbai", "source": f"{BASE}/city/mumbai-dry-days"}
    return year, events


def merge(history: dict[str, dict], year: int, scraped: dict[str, dict]) -> dict[str, dict]:
    """Replace the source year (including corrections); retain prior-year history."""
    kept = {d: e for d, e in history.items() if date.fromisoformat(d).year < year}
    stamp = datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat()
    for d, e in scraped.items():
        prev = history.get(d, {})
        kept[d] = {**e, "first_seen": prev.get("first_seen", stamp), "last_seen": stamp}
    return dict(sorted(kept.items()))


def ics_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fold(line: str) -> str:
    out, raw = [], line.encode("utf-8")
    while len(raw) > 75:
        cut = 75
        while cut > 0 and (raw[cut] & 0xC0) == 0x80:  # don't split a UTF-8 sequence
            cut -= 1
        out.append(raw[:cut].decode("utf-8"))
        raw = b" " + raw[cut:]
    out.append(raw.decode("utf-8"))
    return "\r\n".join(out)


def to_ics(slug: str, name: str, path: str, events: dict[str, dict]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//dryday-ics//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:Dry Days - {name}",
        f"X-WR-CALDESC:Dry days in {name}, updated daily from isitadryday.in",
        "X-WR-TIMEZONE:Asia/Kolkata",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
        "X-PUBLISHED-TTL:PT12H",
    ]
    for iso, e in events.items():
        d = date.fromisoformat(iso)
        source = e.get("source", f"{BASE}/{path}")
        desc = f"Location: {e.get('where', name)}\nSource: {source}"
        lines += [
            "BEGIN:VEVENT",
            f"UID:{slug}-{iso}@dryday-ics",
            f"DTSTAMP:{now}",
            f"DTSTART;VALUE=DATE:{d:%Y%m%d}",
            f"DTEND;VALUE=DATE:{d + timedelta(days=1):%Y%m%d}",
            f"SUMMARY:{ics_escape('Dry day: ' + e['reason'])}",
            f"DESCRIPTION:{ics_escape(desc)}",
            f"URL:{source}",
            f"LOCATION:{ics_escape(e.get('where', name))}",
            "TRANSP:TRANSPARENT",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(l) for l in lines) + "\r\n"


def run(slug: str) -> None:
    path, name = REGIONS[slug]
    year, scraped = parse(fetch(path))
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    hist_file = DATA_DIR / f"{slug}.json"
    history = json.loads(hist_file.read_text()) if hist_file.exists() else {}
    merged = merge(history, year, scraped)

    DATA_DIR.mkdir(exist_ok=True)
    FEED_DIR.mkdir(exist_ok=True)
    hist_file.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n")
    (FEED_DIR / f"{slug}.ics").write_text(to_ics(slug, name, path, merged), newline="")

    upcoming = [d for d in merged if date.fromisoformat(d) >= today]
    print(f"{name}: source year {year}, {len(scraped)} dates fetched, {len(merged)} total in feed")
    for d in upcoming:
        print(f"  {d}  {merged[d]['reason']}")


if __name__ == "__main__":
    for slug in sys.argv[1:] or ["maharashtra"]:
        run(slug)
