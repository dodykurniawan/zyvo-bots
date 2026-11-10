#!/data/data/com.termux/files/usr/bin/bash
# Deploy Cloudflare Worker via REST API (tanpa wrangler — workerd tidak jalan di Termux)
# Pakai: CF_API_TOKEN=... CF_ACCOUNT_ID=... ./deploy_worker.sh
set -euo pipefail
cd "$(dirname "$0")/.."

: "${CF_API_TOKEN:?isi CF_API_TOKEN}"
: "${CF_ACCOUNT_ID:?isi CF_ACCOUNT_ID}"
NAME="zyvo-balance"
JS="worker/index.js"

echo "== upload worker $NAME =="
# multipart: metadata + script
curl -sS -X PUT \
  "https://api.cloudflare.com/client/v4/accounts/${CF_ACCOUNT_ID}/workers/scripts/${NAME}" \
  -H "Authorization: Bearer ${CF_API_TOKEN}" \
  -F "metadata=@-;filename=metadata.json;type=application/json" \
  -F "index.js=@${JS};type=application/javascript+module" \
  <<'META'
{"main":{"module":"index.js"},"compatibility_date":"2026-11-10"}
META
echo

echo "== set secrets =="
put_secret() {
  local name="$1" value="$2"
  [ -n "$value" ] || { echo "skip $name (kosong)"; return; }
  curl -sS -X PUT \
    "https://api.cloudflare.com/client/v4/accounts/${CF_ACCOUNT_ID}/workers/scripts/${NAME}/secrets" \
    -H "Authorization: Bearer ${CF_API_TOKEN}" \
    -H "content-type: application/json" \
    -d "$(python3 -c "import json,sys; print(json.dumps({'name':sys.argv[1],'text':sys.argv[2],'type':'secret_text'}))" "$name" "$value")"
  echo " <- $name"
}

# WEBHOOK_SECRET diacak
WEBHOOK_SECRET="${WEBHOOK_SECRET:-$(python3 -c 'import secrets;print(secrets.token_hex(24))')}"
put_secret TG_BOT_TOKEN        "${TG_BOT_TOKEN:-}"
put_secret TG_CHAT_ID          "${TG_CHAT_ID:-}"
put_secret WEBHOOK_SECRET      "$WEBHOOK_SECRET"
put_secret CF_EMAIL            "${CF_EMAIL:-}"
put_secret CF_PASSWORD         "${CF_PASSWORD:-}"
put_secret CTD_COOKIE          "${CTD_COOKIE:-}"
put_secret LM_SESSION          "${LM_SESSION:-}"

echo "$WEBHOOK_SECRET" > worker/.webhook_secret
echo "WEBHOOK_SECRET disimpan di worker/.webhook_secret (jangan di-commit)"

echo "== selesai upload =="
echo "URL: https://${NAME}.$(python3 -c "import os;print(os.environ.get('CF_DOMAIN','workers.dev'))" )"
