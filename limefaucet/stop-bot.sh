#!/data/data/com.termux/files/usr/bin/bash
# Hentikan bot LimeFaucet.
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit 1

PIDS=$(pgrep -f "limefaucet_auto\.py" 2>/dev/null)
if [ -z "$PIDS" ]; then
  echo "[bot] tidak ada proses yang berjalan"
else
  echo "[bot] menghentikan PID: $PIDS"
  kill $PIDS 2>/dev/null
  sleep 3
  PIDS2=$(pgrep -f "limefaucet_auto\.py" 2>/dev/null)
  [ -n "$PIDS2" ] && { echo "[bot] paksa kill: $PIDS2"; kill -9 $PIDS2 2>/dev/null; }
  echo "[bot] berhenti"
fi

command -v termux-wake-unlock >/dev/null 2>&1 && termux-wake-unlock
