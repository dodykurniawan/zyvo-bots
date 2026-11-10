# LimeFaucet Auto-All

Bot otomatis **limefaucet.com** memakai HTTP murni (`requests`) — **tanpa Playwright,
Selenium, pyppeteer, atau browser apa pun**.

## Fitur

| Tugas | Endpoint yang dipakai | Captcha |
|---|---|---|
| Login (email FaucetPay, no password) | `POST /api/auth/login` | — |
| Claim faucet tiap 5 menit | `GET /api/faucet/info` → `POST /api/faucet/rotation-captcha/challenge` → `/verify` → `POST /api/faucet/claim` | **Rotasi** (di-solve lokal, gratis) |
| PTC internal (semua iklan) | `GET /api/ptc/campaigns` → `POST /api/ptc/view/start` → tunggu durasi → `POST /api/ptc/view/complete` | Turnstile (`action=ptc`) |
| Daily bonus | `GET /api/daily/status` → `POST /api/daily/claim` | Turnstile (`action=daily_bonus`) |
| Shortlink BitcoTasks / OctoClix | `GET /api/shortlinks/{source}` + solver `methods=shortlink` | best-effort |
| **Auto nonton YouTube** | `GET /api/youtube/identity` → aviso.bz `POST /youtube/tasks/{identify,start,timer-status,complete}` | **tanpa captcha, gratis** |
| Offerwall / Watch (subscribe) | dilaporkan saja | tugas eksternal |
| Statistik & histori | `GET /api/history`, `/api/faucet/crypto-prices` | — |

## Instalasi

```bash
cd limefaucet-auto
python3 -m venv venv && source venv/bin/activate   # opsional
pip install -r requirements.txt
cp config.env.example config.env                   # lalu isi email + apikey
```

## Pemakaian

```bash
# 1. Test solver captcha rotasi (tanpa login, offline)
python limefaucet_auto.py --selftest

# 2. Satu siklus (test cepat)
python limefaucet_auto.py --email kamu@faucetpay.email --captcha-key APIKEY --once

# 3. Jalan terus 24/7
python limefaucet_auto.py --email kamu@faucetpay.email --captcha-key APIKEY

# Faucet saja, tanpa solver berbayar
python limefaucet_auto.py --email kamu@faucetpay.email --no-ptc --no-daily --no-shortlinks

# Debug mentah + log file
python limefaucet_auto.py --email ... --debug --log-file bot.log
```

Semua argumen juga bisa lewat `config.env` (`LIME_EMAIL`, `CAPTCHA_APIKEY`,
`LIME_PROXY`, `TOKEN_BUDGET`, `TOKEN_RESERVE`, `TOKEN_PRICE`).

## Opsi lengkap

```
--email EMAIL             Email FaucetPay (wajib)
--captcha-key KEY         API key api.waryono.my.id (opsional)
--proxy URL               Proxy opsional, format http://user:pass@host:port
--once                    Jalankan satu siklus lalu keluar
--tick N                  Jeda antar siklus (detik, default 15)
--no-faucet               Matikan claim faucet
--no-ptc                  Matikan PTC
--no-daily                Matikan daily bonus
--no-shortlinks           Matikan shortlink
--no-youtube              Matikan auto nonton YouTube
--youtube-max N           Maks video YouTube per siklus (default 10)
--youtube-type TYPE       ads (nonton, gratis) | sub | like | all
--youtube-interval N      Jeda antar batch YouTube (detik, default 600)
--yt-visit-partner        Buka halaman partner blogspot (tidak wajib, boros)
--shortlink-max N         Maks shortlink per siklus (default 10)
--cookie-file PATH        File sesi cookie (default .lime_session.json)
--bg-image PATH           Lokal captcha-lime.jpg (default: diunduh otomatis)
--captcha-revalidate N    Cek perubahan captcha tiap N detik
                          (default 86400 = 1x/24 jam; 0 = matikan)
--token-budget N          Batas token solver per hari
--token-reserve N         Token yang disisakan sebagai cadangan
--token-price N           Harga token (untuk laporan ROI)
--min-ptc-reward X        Reward PTC minimum agar layak dikerjakan
--min-shortlink-reward X  Reward shortlink minimum
--max-ptc N               Maks iklan PTC per siklus (0 = tanpa batas)
--no-token-reuse          Matikan pemakaian ulang token Turnstile
--debug                   Log raw response API
--log-file PATH           Salin log ke file
--selftest                Test solver rotasi (tanpa login)
```

### Opsi hemat token (apikey solver)

```
--token-budget N        Maks token dipakai per proses (0=tanpa batas)
--token-reserve N       Tak pernah pakai token sampai saldo tinggal segini (default 100)
--token-price X         Harga token USD per 1000 → aktifkan filter ROI + laporan biaya
--min-ptc-reward X      Reward PTC minimum USD (0=otomatis = biaya 1 token)
--min-shortlink-reward  Reward shortlink minimum USD (0=otomatis = biaya 1 token)
--max-ptc N             Maks iklan PTC per siklus (0=tanpa batas)
--no-token-reuse        Matikan percobaan pakai-ulang token Turnstile
```

## Auto nonton YouTube (gratis, tanpa token)

limefaucet menyewa widget **aviso.bz** untuk tugas "nonton video". Widget
aslinya butuh browser, tapi API-nya murni JSON → bot memakainya langsung:

1. `GET /api/youtube/identity` → `api_endpoint`, `api_key`, `user_hash`,
   `user_id`, `user_sig`, `points_per_usd` (100000 poin = 1 USD).
2. `POST /youtube/tasks/identify` (header `X-API-Key`) → daftarkan sesi.
3. `GET /youtube/tasks/counters` → kuota harian (mis. 800 tugas `ads`).
4. `GET /youtube/tasks/available?type=ads` → daftar video + `amount` poin.
5. Per tugas: `start` → balik `attemptId` + `url` partner (dibuka best-effort)
   → `timer-status {action:start}` → tunggu `duration` detik
   → `timer-status {action:complete, watchedTime}` → `complete` → `earned`.
6. Poin dikonversi limefaucet ke saldo LTC (muncul di histori bertipe
   `offerwall`) — delay beberapa menit.

Hasil uji live: **5 video sukses / 0 gagal = 83 poin (≈0,00083 USD) dengan
0 token solver**. Durasi tiap video cuma 1 detik.

```bash
# 10 video tiap siklus (default), gratis — aman untuk 24/7
python limefaucet_auto.py --email kamu@x.com --youtube-max 10

# matikan / batasi
python limefaucet_auto.py --email kamu@x.com --no-youtube
```

Catatan: tipe `ads` (nonton) bisa 100% otomatis. Tipe `sub`/`like` butuh
interaksi YouTube asli (subscribe/like) + upload bukti screenshot → tidak
diotomatisasi.

## Strategi supaya token tidak cepat habis

Perkiraan biaya nyata dari pengujian live: **1 Turnstile ≈ 0,87 token**,
1 shortlink ≈ 0,2 token, sedangkan hadiahnya PTC hanya 0,000003–0,00001 USD.
Karena itu bot memakai 5 lapis penghematan, berurutan dari yang paling berdampak:

1. **Captcha rotasi faucet = gratis.** Di-solve lokal (korelasi gambar), tanpa
   API. Hanya kalau skor < 0,35 baru fallback berbayar `methods=lime`.
   Gambar variant diunduh memakai **cookie sesi login** (tanpa itu 401).
2. **Cadangan + anggaran.** `--token-reserve` menjamin selalu ada token tersisa
   untuk daily bonus; `--token-budget` mematikan semua tugas ber-captcha begitu
   tercapai — faucet tetap jalan karena gratis.
3. **Pakai ulang token Turnstile.** Token terakhir disimpan 240 detik lalu
   dicoba lagi untuk tugas berikutnya. Percobaan ulang **tidak membeli token
   baru**, jadi gratis: kalau server menerima → hemat 1 token (terbukti live:
   3 iklan PTC selesai dengan 2 token); kalau menolak → otomatis beli token
   baru seperti biasa. Token palsu sudah dipastikan ditolak server, jadi
   alur klaim tetap aman.
4. **Urutan ROI.** `cycle()` = faucet (gratis) → YouTube (gratis) → daily
   (1 token, hadiah 0,0001–0,0005 USD) → shortlink (hadiah ~0,0008 USD) →
   PTC (paling rugi). Anggaran selalu terpakai untuk yang paling
   menguntungkan lebih dulu.
5. **Filter ROI + auto-disable.** Dengan `--token-price`, iklan/shortlink yang
   nilainya di bawah biaya 1 token dilewati (`PTC: N iklan di bawah ambang
   ROI dilewati`). Kalau provider solver gagal `ERROR_CAPTCHA_UNSOLVABLE`,
   sumber shortlink dimatikan otomatis supaya tak mengulang pemborosan.

Laporan pemakaian selalu dicetak di akhir:

```
TOKEN: Token dipakai 2.0 (2 solve) | ≈$0.001000 | reuse OK 0 / gagal 0 | sisa saldo 3534.5 | Δ 2.0
```

Contoh pemakaian hemat (PTC tetap jalan, tapi dibatasi 5 iklan/hari):

```bash
python limefaucet_auto.py --email kamu@x.com --captcha-key APIKEY \
    --token-budget 10 --token-reserve 500 --max-ptc 5
```

## Cara kerja captcha rotasi (gratis, lokal)

1. `POST /api/faucet/rotation-captcha/challenge` → `{challenge:{image, crop:{x,y,radius}}, session_id}`
2. Latar puzzle selalu `/captcha-lime.jpg` (1024×1024). Script meng-crop daerah
   lingkaran `crop` dari latar, lalu mencari sudut `a` yang memaksimalkan
   korelasi terhadap potongan (`piece.rotate(-a) ≈ patch`) — 360 kandidat
   + refine 0.5°.
3. `POST /api/faucet/rotation-captcha/verify {session_id, angle}` → `token`
4. `POST /api/faucet/claim {captcha_token, client}` — `client` adalah fingerprint
   browser (webgl/screen/viewport/dll) yang meniru struktur field asli UI.

Skor korelasi lokal < 0.35 → otomatis fallback ke solver online
`methods=lime` (0.5 token). Kalau server menolak sudut (`wrong`), konvensi
rotasi dibalik otomatis dan dicoba lagi.

## Auto-update captcha (otomatis, tanpa layanan luar)

`/captcha-lime.jpg` **tidak** mengirim `ETag`/`Last-Modified` dan mengabaikan
`Range`/`If-Modified-Since` (selalu balas 200 penuh 141 KB), jadi pengecekan
dibuat jarang supaya tidak boros kuota:

```
Bot (task_captcha_watch, --captcha-revalidate 86400)
  unduh /captcha-lime.jpg  →  bandingkan sha256 dengan file di disk
  sama?     →  selesai (terjadwal 1x/24 jam ≈ 141 KB/hari)
  beda?     →  timpa file, buang cache, reset konvensi rotasi
               →  bot LANJUT jalan, tidak perlu restart
```

Tiga deteksi perubahan sekaligus:

| Perubahan di situs | Yang terjadi |
|---|---|
| Gambar captcha diganti | file ditimpa + konvensi rotasi di-reset, log `CAPTCHA BARU TERDETEKSI` |
| Sitekey Turnstile diganti | config bot diperbarui, log `Sitekey Turnstile BERUBAH` |
| Algoritma diganti (6× salah berturut-turut) | unduh ulang latar paksa, log peringatan |

Atur jadwal dengan `--captcha-revalidate N` (detik), matikan dengan `0`.
Makin besar N = makin hemat kuota; default 86400 = 1×/24 jam.

## Turnstile (PTC + Daily)

Token Turnstile dibeli dari solver (default: `api.waryono.my.id`, 2Captcha-compatible):

```
POST https://api.waryono.my.id/in.php   {apikey, methods:"turnstile", sitekey, domain, action}
GET  https://api.waryono.my.id/res.php  ?apikey&id&action=get&json=1
```

Sitekey diambil otomatis dari `GET /api/config` (`turnstile_site_key`).

## Catatan teknis

- Sesi cookie disimpan di `.lime_session.json`, jadi login cukup sekali.
- `401 Authentication required` → otomatis login ulang.
- `401 "IP changed, please login again"` → sesi terikat IP; hapus
  `.lime_session.json` lalu jalankan ulang (login baru otomatis).
- `429 locked_until` → menunggu sesuai `locked_until` dari server.
- PTC: timer durasi dihitung server, jadi script tidur `duration_seconds + 1..3s`
  sebelum `complete`.
- Loop adaptif: faucet menunggu `time_remaining_seconds`, PTC cek `can_view` /
  `next_view_at_ts`, daily cek `already_claimed` + threshold.
