#!/usr/bin/env python3
import argparse
import re
import sys
from datetime import date
from pathlib import Path
from typing import NoReturn

import requests
from bs4 import BeautifulSoup

BASE = "https://www.steptember.org.au"
LOGIN = f"{BASE}/login"
ACTIVITY_URL = f"{BASE}/login/activity"
VALIDATE = f"{BASE}/customcode/web_validatesteps"
ADD = f"{BASE}/customcode/web_addactivity"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
ACTIVITY = "Cycling (outdoor, stationary)"


def die(msg, code=1):
    print(msg)
    raise SystemExit(code)


def dump_html(html, path="out.html"):
    try:
        Path(path).write_text(html, encoding="utf-8")
        print(f"saved html to {path} ({len(html)} bytes)")
    except Exception as e:
        print(f"failed to save {path}: {e}")


def fetch_token(session):
    r = session.get(LOGIN, headers={"X-Requested-With": "XMLHttpRequest"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    form = soup.select_one("form#form-login")
    if form is None:
        die("login form not found in AJAX fragment")
    token = form.select_one('input[name="CSRFToken"]')
    if token is None or not token.get("value"):
        die("CSRFToken not found in login form")
    return str(token.get("value"))


def do_login(session, email, password, token):
    data = {
        "CSRFToken": token,
        "login_email": email,
        "login_password": password,
    }
    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Referer": LOGIN,
    }
    r = session.post(LOGIN, data=data, headers=headers, allow_redirects=True)
    r.raise_for_status()
    return r


def logged_in(session):
    r = session.get(LOGIN)
    r.raise_for_status()
    markers = ["/login/logout", "template-login-dashboard", "Log Out", "log out"]
    return any(m in r.text for m in markers)


def form_fields(form):
    data = {}
    for el in form.find_all(["input", "select", "textarea"]):
        name = el.get("name")
        if not name:
            continue
        if el.name == "input":
            if el.get("type", "text") in ("submit", "button", "reset", "image"):
                continue
            data[name] = el.get("value", "") or ""
        elif el.name == "select":
            opt = el.find("option", selected=True) or el.find("option")
            data[name] = opt.get("value", "") if opt else ""
        else:
            data[name] = el.get_text() or ""
    return data


def get_activity_rate(html, activity):
    mapping = {
        m.group(1): int(m.group(2))
        for m in re.finditer(r'activityToSteps\["([^"]+)"\]\s*=\s*(\d+)', html)
    }
    if activity not in mapping:
        die(f"activity '{activity}' not found in activity list")
    return mapping[activity]


def _load_activity_page(session):
    r = session.get(ACTIVITY_URL)
    r.raise_for_status()
    html = r.text
    #dump_html(html, "out.html")
    if 'id="form-login"' in html:
        die("session expired before reaching activity page")
    soup = BeautifulSoup(html, "html.parser")
    form = soup.select_one("form#RegistrationForm")
    if form is None:
        die("activity form (RegistrationForm) not found (see out.html)")
    token = form.select_one('input[name="CSRFToken"]')
    if token is None or not token.get("value"):
        die("CSRFToken not found in activity form")
    csrf = str(token.get("value"))
    m = re.search(r"history_id\s*=\s*(\d+)", html)
    if not m:
        die("history_id not found on activity page (see out.html)")
    history_id = m.group(1)
    return html, soup, form, csrf, history_id


def add_activity(session, when, duration):
    html, soup, form, csrf, history_id = _load_activity_page(session)
    rate = get_activity_rate(html, ACTIVITY)
    steps = int(duration * rate / 60)
    payload = {
        "steps": steps,
        "date_from": when,
        "history_id": int(history_id),
        "activity_type": ACTIVITY,
        "duration": duration,
        "source": "manual",
    }
    v = session.post(
        VALIDATE,
        json=payload,
        headers={"X-Requested-With": "XMLHttpRequest", "Referer": ACTIVITY_URL},
    )
    try:
        vj = v.json()
    except Exception:
        vj = {}
    vok = vj.get("success") is True
    print(
        f"validate: success={vok} (steps={steps}, rate={rate}/hr) raw={vj or v.text[:500]}"
    )
    data = form_fields(form)
    data["CSRFToken"] = csrf
    data["date_from"] = when
    data["steps"] = str(steps)
    data["activity_type"] = ACTIVITY
    data["duration"] = str(duration)
    a = session.post(
        ADD,
        data=data,
        headers={"Referer": ACTIVITY_URL},
        allow_redirects=True,
    )
    a.raise_for_status()
    print(f"add: status={a.status_code} url={a.url}")
    #dump_html(a.text, "out_add.html")
    after = session.get(ACTIVITY_URL)
    after.raise_for_status()
    #dump_html(after.text, "out.html")
    ok = ACTIVITY in after.text and when in after.text
    print("ACTIVITY LOGGED" if ok else "ACTIVITY MAY NOT HAVE SAVED (check out.html)")


def add_steps(session, when, steps):
    html, soup, form, csrf, history_id = _load_activity_page(session)
    if (
        "Add your steps manually" not in html
        and "add your steps manually" not in html.lower()
    ):
        print(
            "note: 'Add your steps manually' text not found in page (see out.html), continuing with manual steps flow"
        )
    payload = {
        "steps": steps,
        "date_from": when,
        "history_id": int(history_id),
        "source": "manual",
    }
    v = session.post(
        VALIDATE,
        json=payload,
        headers={"X-Requested-With": "XMLHttpRequest", "Referer": ACTIVITY_URL},
    )
    try:
        vj = v.json()
    except Exception:
        vj = {}
    vok = vj.get("success") is True
    print(f"validate: success={vok} (steps={steps}) raw={vj or v.text[:500]}")
    data = form_fields(form)
    data["CSRFToken"] = csrf
    data["date_from"] = when
    data["steps"] = str(steps)
    data.pop("activity_type", None)
    data.pop("duration", None)
    data["activity_type"] = ""
    data["duration"] = ""
    # some implementations expect activity_type empty for manual steps; keep steps only
    a = session.post(
        ADD,
        data=data,
        headers={"Referer": ACTIVITY_URL},
        allow_redirects=True,
    )
    a.raise_for_status()
    print(f"add: status={a.status_code} url={a.url}")
    #dump_html(a.text, "out_add.html")
    after = session.get(ACTIVITY_URL)
    after.raise_for_status()
    #dump_html(after.text, "out.html")
    ok = when in after.text and str(steps) in after.text
    print("STEPS LOGGED" if ok else "STEPS MAY NOT HAVE SAVED (check out.html)")


def main():
    p = argparse.ArgumentParser(
        description="Log in to Steptember and add steps or a cycling activity."
    )
    p.add_argument("email")
    p.add_argument("password")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument(
        "--duration", type=int, help="duration in minutes (uses activity conversion)"
    )
    g.add_argument(
        "--steps", type=int, help="number of steps (uses 'Add your steps manually')"
    )
    p.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="activity date YYYY-MM-DD (default: today)",
    )
    p.add_argument(
        "--activity",
        default=ACTIVITY,
        help=f"activity name for --duration (default: {ACTIVITY})",
    )
    args = p.parse_args()
    globals()["ACTIVITY"] = args.activity
    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    token = fetch_token(session)
    res = do_login(session, args.email, args.password, token)
    if 'id="form-login"' in res.text:
        die("LOGIN FAILED (credentials rejected or form re-rendered)")
    if not logged_in(session):
        die("LOGIN FAILED (no authenticated session detected)")
    print("LOGIN OK")
    if args.steps is not None:
        if args.steps <= 0:
            die("--steps must be > 0")
        add_steps(session, args.date, args.steps)
    else:
        if args.duration <= 0:
            die("--duration must be > 0")
        add_activity(session, args.date, args.duration)


if __name__ == "__main__":
    main()
