#!/data/data/com.termux/files/usr/bin/bash
# Start failover watcher (idempotent). Dipakai manual + Termux:Boot.
# Match HANYA proses python asli — pgrep -f longgar kena shell diri sendiri.
DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="/storage/emulated/0/Download/ZYVO/sites/failover.log"
alive() { ps -ef | grep -E "[p]ython3.*failover_watch\.py" | grep -v grep; }
if alive >/dev/null 2>&1; then
  echo "[failover] sudah jalan (PID $(alive | awk '{print $2}' | head -1))"
  exit 0
fi
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock
setsid nohup python3 "$DIR/failover_watch.py" >> "$LOG" 2>&1 &
sleep 1
if alive >/dev/null 2>&1; then
  echo "[failover] OK — PID $(alive | awk '{print $2}' | head -1)"
else
  echo "[failover] GAGAL start, log:"
  tail -20 "$LOG"
  exit 1
fi
