#!/usr/bin/env python3
"""Scrape dryday.in for upcoming dry days and emit an iCalendar feed.

dryday.in is a static site that only publishes a rolling four-week window.
This script scrapes the today / tomorrow / ahead sections of a region page,
merges them into a JSON history (so past dry days don't vanish from the
calendar once they roll out of the site's window), and writes an .ics file.

Stdlib only. Usage: python scrape.py [region ...]   (default: maharashtra)
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from html import unescape
from pathlib import Path

BASE = "https://dryday.in"
REGIONS = {
    # slug: (site path, display name)
    "maharashtra": ("india/maharashtra", "Maharashtra"),
}
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
FEED_DIR = ROOT / "docs"
USER_AGENT = "dryday-ics (+https://github.com/ayamdobhal/dryday-ics)"

SECTION_RE = re.compile(r'<section class="focus (\w+)" id=\1>(.*?)</section>', re.S)
TODAY_RE = re.compile(
    r"<time datetime=(\d{4}-\d{2}-\d{2})>(?:Today|Tomorrow)</time>\s*is\s*<span class=dry>(.*?)</span>",
    re.S,
)
TODAY_DATE_RE = re.compile(r"<time datetime=(\d{4}-\d{2}-\d{2})>Today</time>")
AHEAD_ITEM_RE = re.compile(
    r"<time class=dd-date datetime=(\d{4}-\d{2}-\d{2})>.*?<summary class=why>(.*?)</summary>(.*?)</details>",
    re.S,
)
SPAN_RE = re.compile(r"<span class=(what|where|when)>(.*?)</span>", re.S)


def clean(s: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", s)).split())


def details(block: str) -> dict[str, str]:
    return {k: clean(v) for k, v in SPAN_RE.findall(block)}


def fetch(path: str) -> str:
    req = urllib.request.Request(f"{BASE}/{path}/", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def parse(html: str) -> tuple[date, dict[str, dict]]:
    """Return (site's idea of today, {iso date: event}) from a region page."""
    sections = {name: body for name, body in SECTION_RE.findall(html)}
    today_match = TODAY_DATE_RE.search(sections.get("today", ""))
    if not today_match:
        raise RuntimeError("could not find today's date on page; markup changed?")
    today = date.fromisoformat(today_match.group(1))

    events: dict[str, dict] = {}
    for key in ("today", "tomorrow"):
        m = TODAY_RE.search(sections.get(key, ""))
        if m:
            events[m.group(1)] = {"reason": clean(m.group(2)), **details(sections[key])}
    for iso, reason, block in AHEAD_ITEM_RE.findall(sections.get("ahead", "")):
        events[iso] = {"reason": clean(reason), **details(block)}
    return today, events


def merge(history: dict[str, dict], today: date, scraped: dict[str, dict]) -> dict[str, dict]:
    """Keep past entries, replace everything from today onwards with the fresh scrape."""
    kept = {d: e for d, e in history.items() if date.fromisoformat(d) < today}
    stamp = today.isoformat()
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
        f"X-WR-CALDESC:Dry days in {name}, scraped daily from dryday.in",
        "X-WR-TIMEZONE:Asia/Kolkata",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
        "X-PUBLISHED-TTL:PT12H",
    ]
    for iso, e in events.items():
        d = date.fromisoformat(iso)
        closed = " ".join(e.get(k, "") for k in ("what", "where", "when")).strip()
        desc = f"Closed: {closed}\nSource: {BASE}/{path}/" if closed else f"Source: {BASE}/{path}/"
        lines += [
            "BEGIN:VEVENT",
            f"UID:{slug}-{iso}@dryday-ics",
            f"DTSTAMP:{now}",
            f"DTSTART;VALUE=DATE:{d:%Y%m%d}",
            f"DTEND;VALUE=DATE:{d + timedelta(days=1):%Y%m%d}",
            f"SUMMARY:{ics_escape('Dry day: ' + e['reason'])}",
            f"DESCRIPTION:{ics_escape(desc)}",
            f"URL:{BASE}/{path}/",
            "TRANSP:TRANSPARENT",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(l) for l in lines) + "\r\n"


def run(slug: str) -> None:
    path, name = REGIONS[slug]
    today, scraped = parse(fetch(path))
    hist_file = DATA_DIR / f"{slug}.json"
    history = json.loads(hist_file.read_text()) if hist_file.exists() else {}
    merged = merge(history, today, scraped)

    DATA_DIR.mkdir(exist_ok=True)
    FEED_DIR.mkdir(exist_ok=True)
    hist_file.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n")
    (FEED_DIR / f"{slug}.ics").write_text(to_ics(slug, name, path, merged), newline="")

    upcoming = [d for d in merged if date.fromisoformat(d) >= today]
    print(f"{name}: site date {today}, {len(scraped)} upcoming scraped, {len(merged)} total in feed")
    for d in upcoming:
        print(f"  {d}  {merged[d]['reason']}")


if __name__ == "__main__":
    for slug in sys.argv[1:] or ["maharashtra"]:
        run(slug)
