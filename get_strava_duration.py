#!/usr/bin/env python3
import argparse
import json
import re
from datetime import date, datetime
from html import unescape

from requests import Session

TRAINING_URL = "https://www.strava.com/athlete/training_activities"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"

CYCLING_TYPES = {
    "Ride",
    "VirtualRide",
    "EBikeRide",
    "EMountainBikeRide",
    "GravelRide",
    "Handcycle",
    "MountainBikeRide",
    "Velomobile",
}


def load_session(s, path):
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return False
    for c in data.get("cookies", []):
        s.cookies.set(
            c["name"],
            c["value"],
            domain=c.get("domain", ".strava.com"),
            path=c.get("path", "/"),
        )
    return True


def get_csrf(s):
    try:
        r = s.get(TRAINING_URL, params={"page": 1, "per_page": 1}, timeout=30)
        r.raise_for_status()
    except Exception:
        return None
    m = re.search(r'<meta name="csrf-token" content="([^"]+)"', r.text)
    if not m:
        m = re.search(r'name="authenticity_token" value="([^"]+)"', r.text)
    return unescape(m.group(1)) if m else None


def _models(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if isinstance(payload.get("models"), list):
            return payload["models"]
        for k in ("activities", "items"):
            if isinstance(payload.get(k), list):
                return payload[k]
    return []


def fetch_activities(s, csrf, target):
    items = []
    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json",
        "X-CSRF-Token": csrf,
    }
    for page in range(1, 201):
        try:
            r = s.get(
                TRAINING_URL,
                params={"page": page, "per_page": 200},
                headers=headers,
                timeout=30,
            )
            batch = _models(r.json())
        except Exception:
            break
        if not batch:
            break
        items.extend(batch)
        # activities are newest-first; once we scroll past the target day, stop
        if activity_date(batch[0]) < target:
            break
    return items


def activity_date(a):
    sd = a.get("start_date") or ""
    for fmt in ("%a, %m/%d/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(sd, fmt).date().isoformat()
        except ValueError:
            continue
    return (a.get("start_time") or "")[:10]


def cycling_minutes(items, target):
    total = 0
    for a in items:
        if activity_date(a) != target:
            continue
        t = a.get("sport_type") or a.get("type") or ""
        if t not in CYCLING_TYPES:
            continue
        total += int(a.get("elapsed_time_raw") or 0)
    return total // 60


def main():
    p = argparse.ArgumentParser(
        description="Print total cycling duration (minutes) for a day from Strava."
    )
    p.add_argument(
        "--session", default="session.json", help="Path to saved session cookies JSON"
    )
    p.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Target date YYYY-MM-DD (default: today)",
    )
    args = p.parse_args()

    s = Session()
    s.headers["User-Agent"] = UA

    if not load_session(s, args.session):
        print("Could not load session from " + args.session)
        raise SystemExit(1)
    csrf = get_csrf(s)
    if not csrf:
        print("No valid Strava session; export a logged-in session to " + args.session)
        raise SystemExit(1)

    items = fetch_activities(s, csrf, args.date)

    print(cycling_minutes(items, args.date))


if __name__ == "__main__":
    main()
