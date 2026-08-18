#!/usr/bin/env bash
set -uo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

USER="$1"
PASS="$2"
DATE="${3:-}"

ARGS=()
if [ -n "$DATE" ]; then
  ARGS+=(--date "$DATE")
fi

echo "Strava cycling minutes for ${DATE:-today}..."
OUT="$(python3 "$DIR/get_strava_duration.py" "${ARGS[@]}" 2>&1)"
RC=$?
MINS="$(printf '%s\n' "$OUT" | tail -n1 | tr -d '[:space:]')"

if [ $RC -ne 0 ] || ! [[ "$MINS" =~ ^[0-9]+$ ]]; then
  echo "get_strava_duration.py failed or returned no number. Output:"
  echo "$OUT"
  exit 1
fi

if [ "$MINS" -eq 0 ]; then
  echo "No cycling duration for ${DATE:-today} (0 min). Nothing to log."
  exit 0
fi

echo "Strava total: $MINS min -> logging into Steptember"
LOGIN_ARGS=(--duration "$MINS")
if [ -n "$DATE" ]; then
  LOGIN_ARGS+=(--date "$DATE")
fi

python3 "$DIR/log_steptember.py" "$USER" "$PASS" "${LOGIN_ARGS[@]}"
