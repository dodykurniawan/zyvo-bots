# STRATEGI — Scrapper Suite (BTC/PEPE/TRX/DOGE/LTC)

**Goal**: level-rush (hashrate/traits) + earn power harian + auto-WD berkali ke FaucetPay `dodykurniaw4n@gmail.com`.

## Situs (satu kode, 5 domain)
| key | URL | koin |
|-----|-----|------|
| btc | satoshiscrapper.com | BTC (sats display) |
| pepe | pepescrapper.com | PEPE |
| tron | tronscrapper.com | TRX |
| doge | dogescrapper.com | DOGE |
| ltc | ltcscrapper.com | LTC |

Login **passwordless** = email FaucetPay (bukan password).

## Loop per siklus (urutan)
1. **free-gift** (`POST /api/game/free-gift`) — +5 Screws/hari
2. **faucet** — challenge → tunggu `steps*adSeconds` → claim (image captcha = pilih URL == target)
3. **spin** → **spin claim** (kalau `spinPending`)
4. **streak** — confirm ke `POST /api/game/streak` (bukan `/streak/claim`)
5. **quests** — yang `complete && !claimed`
6. **alloc** → 100% coin (ZERO), Screws hanya untuk unlock rig
7. **upgrade** trait termurah (utamakan `strength` = +H/s) selama saldo cukup
8. **girl unlock** kalau `girlReady`
9. **WD** terakhir: `claimReady` + `balance >= minClaim` → funnel claim → FaucetPay
   - cooldown WD = `claimCooldownSec` (21600s = 6 jam) → WD berulang tiap 6 jam

## Human gate
`403 code=human` → `GET /api/human/challenge` → SHA-256 `prefix:nonce` leading-zero bits → `POST /api/human`.

## Proof
WD dihitung hanya kalau response claim `ok` + amount; state balance bergerak.

## Run
```bash
cd /storage/emulated/0/Download/ZYVO/sites/scrapper_suite
bash run_all.sh                 # loop 5 situs
python3 scrapper_auto.py --site all --once
python3 scrapper_auto.py --site btc --status
```

## Catatan
- PTC (`/api/game/ptc-url`) butuh buka iklan browser — tidak diotomasi HTTP.
- VIP/membership = bayar — skip.
- Jangan jalankan 2 proses suite bareng (tabrak session).
