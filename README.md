# zyvo-bots

Tiga bot faucet jalan di **GitHub Actions** (bukan HP) — kuota HP hemat,
24/7 selama repo public. Mode **premium**: fokus naik level/power + auto WD,
plus **self-heal harian** (auto-relogin tanpa perintah).

| Job | Script | Fokus premium |
|-----|--------|----------------|
| `cf` | `cryptofisher/cryptofisher_premium.py` | Naik level (EXP catch) + auto-upgrade + auto WD multi-koin |
| `ctd` | `cryptotowerdefense/ctd_auto.py` | Tower permanen LV + firstClear campaign + auto WD |
| `lm` | `lightningminer/lightningminer_auto.py` | Shop miner (miningPower) + auto WD USDC |

## Cara kerja

- **Cron tiap 6 jam** (`17 */6 * * *`) → tiap job maks ~340 menit.
  (Batas GitHub = 360 menit/job; exit 124/130 = timeout, bukan gagal.)
- **Self-heal sebelum run**: `scripts/selfheal.py` cek sesi → relogin
  otomatis (CF dummy captcha, CTD xsolve, LM password). Gagal bot →
  self-heal lagi → **retry 1x**.
- **Self-heal harian** (`selfheal.yml`, cron `17 3 * * *` ≈ 10:17 WIB):
  probe 3 situs + kirim status ke Telegram (sehat / masih rusak).
- **Secrets** hanya di GitHub Settings → Secrets, tidak masuk repo.
- Session mati → auto-relogin; site down → lapor TG (API berubah total
  tetap butuh patch kode, bukan tebak).

## Secrets yang disetel

| Nama | Isi |
|------|-----|
| `CF_EMAIL` | email akun CryptoFisher |
| `CF_PASSWORD` | password akun CryptoFisher |
| `CTD_EMAIL` | email akun CryptoTowerDefense |
| `CTD_PASSWORD` | password akun CryptoTowerDefense |
| `CTD_COOKIE` | cookie sesi CTD — dipakai dulu; kalau mati baru login Turnstile |
| `LM_CONFIG_JSON` | isi `lm_config.json` (password LM + key solver), **tanpa** `local_ts_url`/`local_hc_url` |
| `TG_BOT_TOKEN` | token bot Telegram (@BotFather) |
| `TG_CHAT_ID` | chat ID kamu |

## Jalankan manual

Actions → **bots** → **Run workflow**:
- `test=true` → mode `--once` (tes singkat)
- `only` → `all` / `cf` / `ctd` / `lm`

Actions → **selfheal** → Run workflow (cek + relogin sekarang).

## Telegram

| Perintah / event | Fungsi |
|------------------|--------|
| `/balance` atau `/saldo` | Balas saldo CF + CTD + LM (webhook Worker = instan) |
| `/start` | Sapaan + saldo |
| Notifikasi run | Detail per job + ringkasan |
| Self-heal harian | “SEMUA SEHAT” atau detail masalah |

## Lokal (opsional)

```bash
pip install requests
export CF_EMAIL=... CF_PASSWORD=...
python3 scripts/selfheal.py          # cek + relogin 3 situs
python3 cryptofisher/cryptofisher_premium.py --once
python3 scripts/balance_all.py
```
