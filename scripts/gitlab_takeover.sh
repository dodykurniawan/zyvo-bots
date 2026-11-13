#!/usr/bin/env bash
# Takeover GitLab — jalankan SEMUA bot paralel saat GH Actions mati.
# Dipanggil .gitlab-ci.yml setelah ci_gate.py bilang TAKEOVER.
#
# Kenapa SATU job, bukan 5 job: kuota GitLab free = 400 mnt/bln.
# 5 job paralel × 165 mnt = 825 mnt per takeover (habis bulan itu juga);
# 1 job dengan 5 proses paralel di dalamnya = cuma ±170 mnt (durasi
# wall-clock). Sehat pun cuma bakar ±40 dtk (image + gate + keluar).
#
# Semua config ditulis dari environment (GitLab CI/CD variables) —
# password TIDAK pernah ditulis ke file.
set -uo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs

# --- anti-dobel: bot yang SUDAH jalan lokal (failover) jangan di-start --
# Runner GitLab = HP yg sama dgn failover_watch → kalau GH mati, failover
# sudah menyalakan bot lokal; takeover cuma mengisi yang mati.
declare -A SKIP
check_skip() {
  if pgrep -f "$2" >/dev/null 2>&1; then
    SKIP[$1]=1
    echo "==> $1 DILEWATI — sudah jalan lokal (failover): $2"
  fi
}
check_skip cf   'cryptofisher_(premium|level|auto2?)\.py'
check_skip ctd  'ctd_auto\.py'
check_skip lm   'lightningminer_auto\.py'
check_skip clip 'clipcoin_auto\.py'
check_skip scrp 'scrapper_auto\.py'
if [ "${#SKIP[@]}" -ge 5 ]; then
  echo "==> semua 5 bot sudah jalan lokal — takeover tidak perlu, hijau"
  exit 0
fi

# --- wajib: minimal yang dibutuhkan untuk jalan -------------------------
: "${CF_EMAIL:?CF_EMAIL kosong (set CI/CD variable)}"
: "${CTD_EMAIL:?CTD_EMAIL kosong}"
: "${CTD_PASSWORD:?CTD_PASSWORD kosong}"
: "${LM_CONFIG_JSON:?LM_CONFIG_JSON kosong}"
: "${TG_BOT_TOKEN:?TG_BOT_TOKEN kosong}"
: "${TG_CHAT_ID:?TG_CHAT_ID kosong}"

TEST="${TEST:-0}"
if [ "$TEST" = "1" ]; then
  TMO="10m"          # test singkat (--once per bot)
else
  TMO="155m"         # < timeout job 170m (runner cap 3 jam)
fi

export CF_EMAIL CTD_EMAIL CTD_PASSWORD CLIPCOIN_PASSWORD \
       SOLVERCF_KEY GEMINI_KEY CTD_COOKIE CF_PASSWORD
export LM_CONFIG_PATH="$PWD/lightningminer/lm_config.json"

# --- config dari Secrets (port dari .github/workflows/bots.yml) ---------
python3 - <<'PY'
import json, os, sys
try:
    cfg = {
        "email": os.environ["CF_EMAIL"],
        "coin": "BTC", "wd_gateway": "faucetpay",
        "wd_address": "dodykurniaw4n@gmail.com",
        "wd_currency": "USDT", "wd_min_usd": 0.001,
        "hold_wd_until_upgrade": False,
        "hold_usdt_for_upgrade": True, "auto_wd": True,
    }
    os.makedirs("cryptofisher", exist_ok=True)
    json.dump(cfg, open("cryptofisher/cf_config.json", "w"), indent=2)

    os.makedirs("lightningminer", exist_ok=True)
    c = json.loads(os.environ["LM_CONFIG_JSON"])
    c.pop("local_ts_url", None); c.pop("local_hc_url", None)
    json.dump(c, open("lightningminer/lm_config.json", "w"), indent=2)

    os.makedirs("cryptotowerdefense", exist_ok=True)
    open("cryptotowerdefense/ctd_cookie.txt", "w").write(
        os.environ.get("CTD_COOKIE", ""))
    open("cryptotowerdefense/ctd_email.txt", "w").write(
        os.environ["CTD_EMAIL"])
    open("cryptotowerdefense/ctd_secret.txt", "w").write(
        os.environ["CTD_PASSWORD"])

    os.makedirs("clipcoin", exist_ok=True)
    json.dump({
        "email": os.environ["CF_EMAIL"], "password": "",
        "wallet_bep20": "0xfd8e65eae62f33652400a2f7a5ee3a6e87457f7a",
        "service": "usdt_bep20", "min_wd": 0.3,
    }, open("clipcoin/config.json", "w"), indent=2)
    print("config siap (password tidak ditulis ke file)")
except KeyError as e:
    print("VARIABLE HILANG:", e); sys.exit(11)
PY
[ $? -eq 0 ] || exit 11

# --- self-heal singkat (sesi mati → relogin) sebelum bot ---------------
# Bot lokal yang sedang jalan TIDAK di-heal (relogin memutar sesi di
# bawahnya → bikin bot lokal error).
if [ -z "${SKIP[cf]:-}" ]; then
  python3 -u scripts/selfheal.py --only cf  2>&1 | sed -u 's/^/[heal-cf] /'  || true
fi
if [ -z "${SKIP[ctd]:-}" ]; then
  python3 -u scripts/selfheal.py --only ctd 2>&1 | sed -u 's/^/[heal-ctd] /' || true
fi
if [ -z "${SKIP[lm]:-}" ]; then
  python3 -u scripts/selfheal.py --only lm  2>&1 | sed -u 's/^/[heal-lm] /' || true
fi

# --- jalankan 5 bot paralel --------------------------------------------
# Semua output di-stream ke log GitLab (biar job tidak di-drop 1 jam
# tanpa output) + di-tee ke logs/<bot>.log per bot.
declare -A PID RC
ARGS=""
[ "$TEST" = "1" ] && ARGS="--once"

run_bot() {
  local name="$1" dir="$2"; shift 2
  [ -n "${SKIP[$name]:-}" ] && return 0
  (
    ec=99
    for try in 1 2; do
      ( cd "$dir" && timeout -s INT -k 60 "$TMO" python3 -u "$@" $ARGS ) \
        2>&1 | tee -a "logs/$name.log" | sed -u "s/^/[$name] /"
      ec=${PIPESTATUS[0]}
      # 0 sukses; 124/130 = timeout/signal (normal, bukan error bot)
      if [ "$ec" -eq 0 ] || [ "$ec" -eq 124 ] || [ "$ec" -eq 130 ]; then
        ec=0; break
      fi
      [ "$try" -eq 2 ] && break
      echo "[$name] retry setelah self-heal…"
      case "$name" in
        cf|ctd|lm)
          python3 -u scripts/selfheal.py --only "$name" 2>&1 \
            | sed -u "s/^/[$name-heal] /" || true ;;
      esac
    done
    exit "$ec"
  ) &
  PID[$name]=$!
}

run_bot cf   cryptofisher         cryptofisher_premium.py --wd-every 15
run_bot ctd  cryptotowerdefense   ctd_auto.py
run_bot lm   lightningminer       lightningminer_auto.py --interval 180
run_bot clip clipcoin             clipcoin_auto.py --interval 180
run_bot scrp scrapper             scrapper_auto.py --site all --interval 180

N_RUN=$(( 5 - ${#SKIP[@]} ))
echo "==> $N_RUN bot berjalan paralel (dilewati lokal: ${#SKIP[@]}, TEST=$TEST, timeout per bot $TMO)"
FAIL=0
for n in cf ctd lm clip scrp; do
  if [ -n "${SKIP[$n]:-}" ]; then
    RC[$n]=0
    echo "===> $n dilewati (sudah jalan lokal)"
    continue
  fi
  wait "${PID[$n]}"; rc=$?
  RC[$n]=$rc
  if [ "$rc" -ne 0 ]; then FAIL=$((FAIL + 1)); fi
  echo "===> $n selesai rc=$rc"
done

# node sisa dari CTD
pkill -f "[c]td_run_bot.mjs" 2>/dev/null || true

# --- notifikasi Telegram (1 pesan hasil takeover) -----------------------
badge() {
  if [ -n "${SKIP[$1]:-}" ]; then echo "⏭️ dilewati (lokal jalan)"
  elif [ "$2" -eq 0 ]; then echo "✅ sukses"
  else echo "❌ gagal (rc=$2)"; fi
}
BAL=$(python3 scripts/balance_all.py 2>/dev/null | tail -6 || true)
TEXT="🔁 TAKEOVER GitLab (GitHub Actions mati)
🎣 CF:   $(badge cf "${RC[cf]}")
🛡️ CTD:  $(badge ctd "${RC[ctd]}")
⛏️ LM:   $(badge lm "${RC[lm]}")
🪙 clip: $(badge clip "${RC[clip]}")
🦎 scrp: $(badge scrp "${RC[scrp]}")
$BAL
🕐 $(date -u '+%Y-%m-%d %H:%M UTC')
🔗 ${CI_PIPELINE_URL:-gitlab}"
curl -s -o /dev/null --max-time 20 \
  "https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage" \
  --data-urlencode "chat_id=${TG_CHAT_ID}" \
  --data-urlencode "text=${TEXT}" || echo "(TG gagal kirim — abaikan)"

# 0 = semua bot sukses; >0 = ada yang gagal → pipeline merah (perlu lihat)
exit "$FAIL"
