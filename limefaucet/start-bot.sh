#!/data/data/com.termux/files/usr/bin/bash
# Launcher LimeFaucet — jalan 24/7, hemat kuota, tahan HP sleep.
# Dipakai manual  :  ./start-bot.sh
# Dipakai Termux:Boot (auto-start saat HP menyala) juga memakai file ini.

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit 1

LOG="bot.log"
PY=""

# pilih python yang punya Pillow + numpy
for CAND in /usr/bin/python3 python3 python; do
  if command -v "$CAND" >/dev/null 2>&1 && \
     "$CAND" -c "import PIL, numpy, requests" >/dev/null 2>&1; then
    PY="$CAND"; break
  fi
done

if [ -z "$PY" ]; then
  echo "[bot] TIDAK ADA python dengan PIL+numpy+requests"
  echo "[bot] jalankan: pkg install python && pip install -r requirements.txt"
  exit 1
fi

# cegah proses dobel
if pgrep -f "${PY} .*limefaucet_auto" >/dev/null 2>&1; then
  echo "[bot] sudah berjalan (PID $(pgrep -f "${PY} .*limefaucet_auto" | head -1)) — batal"
  exit 0
fi

# cegah HP sleep (butuh termux-api)
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock

echo "[bot] start dengan $PY  (log: $LOG)"
nohup "$PY" limefaucet_auto.py \
  --youtube-max 10 \
  --youtube-interval 600 \
  >> "$LOG" 2>&1 &
disown

sleep 5
if pgrep -f "${PY} .*limefaucet_auto" >/dev/null 2>&1; then
  echo "[bot] OK — PID $(pgrep -f "${PY} .*limefaucet_auto" | head -1)"
else
  echo "[bot] GAGAL start, lihat $LOG:"
  tail -20 "$LOG"
  exit 1
fi
