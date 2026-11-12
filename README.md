# zyvo-bots

Bot faucet jalan di **GitHub Actions** (bukan HP) — kuota HP hemat,
24/7 selama repo public. Mode **premium**: fokus naik level/power + auto WD,
plus **self-heal harian** (auto-relogin tanpa perintah).

**Failover otomatis (2026-11-12):** watcher di HP
(`scripts/failover_watch.py`) memantau Actions — GH mati → CF/CTD/LM
langsung jalan di Termux; GH hidup → lokal berhenti (satu akun, jangan
dobel). **Limefaucet selalu di HP**, tidak ada di Actions (IP ditolak).

| Job | Script | Fokus premium |
|-----|--------|----------------|
| `cf` | `cryptofisher/cryptofisher_premium.py` | Naik level (EXP catch) + auto-upgrade + auto WD multi-koin |
| `ctd` | `cryptotowerdefense/ctd_auto.py` | Tower permanen LV + firstClear campaign + auto WD |
| `lm` | `lightningminer/lightningminer_auto.py` | Shop miner (miningPower) + auto WD USDC |
| *(HP only)* | `limefaucet_auto.py` + clipcoin + scrapper | Lime rotasi captcha + YouTube; scrapper 5 situs; clipcoin watch |

## Cara kerja

- **Cron tiap 6 jam** (`17 */6 * * *`) → tiap job maks ~340 menit.
  (Batas GitHub = 360 menit/job; exit 124/130 = timeout, bukan gagal.)
- **Failover**: `scripts/failover_watch.py` cek GH tiap 60–300 dtk.
  GH OFF (workflow disabled / schedule basi > 8 jam) → start lokal;
  GH ON → `SIGTERM`/`SIGKILL` pola CF/CTD/LM saja — lime/clipcoin/
  scrapper tidak disentuh. API GH gagal → mode tidak diubah.
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

(`LIME_EMAIL` / `CAPTCHA_APIKEY` legacy — lime sudah tidak ada di Actions.)

## Jalankan manual

Actions → **bots** → **Run workflow**:
- `test=true` → mode `--once` (tes singkat)
- `only` → `all` / `cf` / `ctd` / `lm`

Actions → **selfheal** → Run workflow (cek + relogin sekarang).

Failover di HP:
```bash
python3 scripts/failover_watch.py --check          # status GH + lokal
python3 scripts/failover_watch.py --once           # satu siklus
python3 scripts/failover_watch.py                  # loop adaptif 60/300 dtk
```

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
python3 scripts/failover_watch.py --check
```
