#!/usr/bin/env bash
# Share the local Kavosh backend with the deployed site (phones, Safari, other
# computers) through a free Cloudflare quick tunnel.
#
#   ./dev.sh          # in one terminal: backend on localhost:8000
#   ./tunnel.sh       # in another: prints the link to open or share
#
# The tunnel URL changes every run, so share the new link each time. It works
# only while this script and the backend are running. Ctrl-C stops it.
set -euo pipefail

SITE_URL="${SITE_URL:-https://btp-sem-07.vercel.app}"
BACKEND="${BACKEND:-http://localhost:8000}"

command -v cloudflared >/dev/null || { echo "cloudflared is not installed: brew install cloudflared"; exit 1; }
curl -fsS -m 5 "$BACKEND/health" >/dev/null || { echo "No backend at $BACKEND. Start it first with ./dev.sh"; exit 1; }

LOG="$(mktemp -t kavosh-tunnel)"
cloudflared tunnel --no-autoupdate --url "$BACKEND" >"$LOG" 2>&1 &
PID=$!
trap 'kill $PID 2>/dev/null; rm -f "$LOG"' EXIT

echo "Starting tunnel..."
URL=""
for _ in $(seq 1 60); do
  URL="$(grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" | head -1 || true)"
  [ -n "$URL" ] && break
  kill -0 $PID 2>/dev/null || { cat "$LOG"; echo "cloudflared exited."; exit 1; }
  sleep 1
done
[ -n "$URL" ] || { cat "$LOG"; echo "No tunnel URL after 60 s."; exit 1; }

# Wait until the new hostname resolves. Ask public DNS rather than this Mac:
# an early local lookup gets a cached "not found" that lasts for minutes.
HOST="${URL#https://}"
for _ in $(seq 1 30); do [ -n "$(dig +short @1.1.1.1 "$HOST" 2>/dev/null)" ] && break; sleep 1; done

echo
echo "Backend tunnel: $URL"
echo "Open or share:  $SITE_URL/?api=$URL"
echo
echo "If this Mac says the address cannot be found, wait a minute: new tunnel"
echo "names can take a moment to reach every DNS server. Phones usually work at once."
echo "Keep this running. Ctrl-C to stop."
wait $PID
