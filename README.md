# zyvo-bots

Tiga bot faucet jalan di **GitHub Actions** (bukan HP) — kuota HP hemat,
24/7 selama repo public.

| Job | Script | Fungsi |
|-----|--------|--------|
| `cf` | `cryptofisher/cryptofisher_level.py` | CryptoFisher level rush (EXP = crypto catch) |
| `ctd` | `cryptotowerdefense/ctd_auto.py` | CryptoTowerDefense faucet + battle |
| `lm` | `lightningminer/lightningminer_auto.py` | LightningMiner faucet harian |

## Cara kerja

- **Cron tiap 6 jam** → tiap job jalan maksimal ~340 menit lalu berhenti,
  job berikutnya lanjut. (Batas GitHub = 360 menit/job.)
- **Secrets** (password, key solver) hanya ada di GitHub Settings → Secrets,
  tidak pernah masuk file repo.
- Session mati → **auto-relogin** (CF: captcha dummy gratis; CTD: xsolve;
  LM: password).

## Secrets yang disetel

| Nama | Isi |
|------|-----|
| `CF_EMAIL` | email akun CryptoFisher |
| `CF_PASSWORD` | password akun CryptoFisher |
| `CTD_EMAIL` | email akun CryptoTowerDefense |
| `CTD_PASSWORD` | password akun CryptoTowerDefense |
| `CTD_COOKIE` | cookie sesi CTD (`ctd_cookie.txt`) — dipakai dulu; kalau mati baru login Turnstile |
| `LM_CONFIG_JSON` | isi lengkap `lm_config.json` (password LM + key solver xsolve/peak/nonecap), **tanpa** `local_ts_url`/`local_hc_url` |
| `TG_BOT_TOKEN` | token bot Telegram (@BotFather) |
| `TG_CHAT_ID` | chat ID kamu (pesan dulu ke bot, lalu ambil dari getUpdates) |

## Jalankan manual

Actions → **bots** → **Run workflow**:
- `test=true` → mode `--once` (tes singkat, keluar setelah 1 siklus)
- `only` → pilih bot (`all` / `cf` / `ctd` / `lm`)

## Telegram

Notifikasi otomatis (detail per job + ringkasan per run) + **cek saldo**:

| Perintah | Fungsi |
|----------|--------|
| `/balance` atau `/saldo` | Balas saldo CF + CTD + LM terbaru (≤5 menit) |
| `/start` | Sapaan + saldo |

- Polling workflow **balance.yml** jalan tiap 5 menit.
- Pesan run (`bots.yml`) juga menyertakan baris saldo.
- Secrets: `TG_BOT_TOKEN`, `TG_CHAT_ID`.

## Lokal (opsional)

```bash
pip install requests
export CF_EMAIL=... CF_PASSWORD=...
python3 cryptofisher/cryptofisher_level.py --ptc
python3 scripts/balance_all.py   # cek saldo 3 situs
```
