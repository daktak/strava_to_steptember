# strava_to_steptember

Fetches your daily cycling time from Strava and logs it into Steptember as duration.

## Prerequisites

- Python 3
- Install dependencies:

  ```bash
  pip install requests beautifulsoup4
  ```

## 1. Create `session.json` (Strava authentication)

`get_strava_duration.py` authenticates to Strava using a saved session cookie. Create
`session.json` in the repository root with this structure:

```json
{
  "cookies": [
    {
      "name": "_strava4_session",
      "value": "<your logged-in _strava4_session cookie value>",
      "domain": ".strava.com",
      "path": "/"
    }
  ]
}
```

To get the value:

1. Log into <https://www.strava.com> in your browser.
2. Open DevTools (F12) → **Application** → **Cookies** → `strava.com`, and copy the value of
   `_strava4_session` (you can also grab it from the `Cookie` request header in the **Network** tab).
3. Paste it as the `value` above.

## 2. Run `sync.sh`

```bash
./sync.sh <steptember_email> <steptember_password> [YYYY-MM-DD]
```

- `steptember_email` / `steptember_password` — your Steptember (steptember.org.au) login.
- `DATE` is optional and defaults to **today** (`YYYY-MM-DD`).

What it does:

1. Fetches your total cycling minutes from Strava for the date using `session.json`.
2. If the total is greater than 0, logs that duration into Steptember as
   "Cycling (outdoor, stationary)" steps (converted using Steptember's activity rate).

Example (log today):

```bash
./sync.sh me@example.com my_password
```

> Security note: the Steptember password is passed on the command line, so it is visible in your
> shell history and to other users via the process list. Use a dedicated/limited password and be
> aware of this trade-off.

## Automating with cron

Because `sync.sh` defaults to today when no date is given, you can log daily without passing a
date. For example, to run it every day at 11pm, add a line like this to your crontab
(`crontab -e`):

```cron
0 23 * * * cd /path/to/strava_to_steptember && ./sync.sh me@example.com my_password >> /dev/null 2>&1
```

(Adjust the path and credentials.)
