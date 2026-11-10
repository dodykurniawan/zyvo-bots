#!/usr/bin/env python3
"""
CryptoFisher Auto-All — bot Python untuk akun sendiri (cryptofisher.online).

Fitur:
  - Auto login Python: hCaptcha di-solve via NoneCap/MythiX (`--login`)
  - Auto cast → tunggu nibble (delay dari server) → hook/reel
  - Auto recycle ikan (discard_item) + deposit kripto (deposit_crypto)
  - Auto jawab "Coast Guard" fishing captcha (cocokkan nama target)
  - Sweep PTC (opsional, --ptc) + dump halaman view_ad (--dump-view-ad)
  - Human pacing: jitter acak, backoff saat error

Pakai:
  1) Key hCaptcha (pilih satu):
     a) MythiX GRATIS 1000 kredit: https://mythixsolve.tech/register
        python3 cryptofisher_auto.py --set-key mythix_key mx_live_…
     b) NoneCap 1300 kredit: https://dashboard.nonecap.com/signup
        python3 cryptofisher_auto.py --set-key nonecap_key nc_live_…
  2) python3 cryptofisher_auto.py --login EMAIL --password PASS
     (atau --setup kalau mau tempel cookie manual)
  3) python3 cryptofisher_auto.py             # jalankan bot
  4) python3 cryptofisher_auto.py --coin TRX --ptc

Config: cf_config.json di folder yang sama dengan skrip ini.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Any, Optional

import requests

# ─── Rich TUI Dashboard ──────────────────────────────────────────────
try:
    from _tools.rich_tui import (
        BotDashboard, BotStats, DashboardConfig, Palette,
        create_dashboard, print_banner
    )
    HAS_TUI = True
except ImportError:
    HAS_TUI = False

BASE = "https://cryptofisher.online"
NONECAP_API = "https://api.nonecap.com/v1"
# fallback kalau scrape sitekey gagal (dari cf_home.html)
CF_SITEKEY_FALLBACK = "b6fc55b6-7668-4a7c-be36-58644d3c5c52"
CFG_PATH = Path(__file__).resolve().parent / "cf_config.json"
UA = (
    "Mozilla/5.0 (Linux; Android 14; Phone) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)

VALID_COINS = {
    "USDT", "TRX", "BTC", "ETH", "LTC", "BNB", "SOL",
    "DOGE", "DASH", "TON", "ZEC", "XRP", "SHIB", "PEPE", "TRUMP",
}

# Harga USD per unit (dari cryptoList homepage) + range drop per cast.
# EV/cast = rata2(min,max) × harga — BTC unggul telak ($0.000387 vs
# USDT $0.000010) → koin mancing default BTC, diverifikasi via stats.
COIN_USD = {
    "USDT": 1.0, "TRX": 0.316145, "BTC": 77414.0, "ETH": 2250.47,
    "LTC": 55.2, "BNB": 703.7, "SOL": 95.68, "DOGE": 0.075343,
    "DASH": 48.35, "TON": 1.19, "ZEC": 1280.2, "XRP": 1.25,
    "SHIB": 4.71e-6, "PEPE": 5.0e-6, "TRUMP": 1.58,
}
COIN_RANGE = {
    "USDT": (1e-8, 2e-5), "TRX": (1e-8, 5e-5), "BTC": (0, 1e-8),
    "ETH": (0, 1e-8), "LTC": (1e-8, 3e-7), "BNB": (1e-8, 3e-8),
    "SOL": (1e-8, 2.5e-7), "DOGE": (1e-8, 1e-4), "DASH": (1e-8, 1e-6),
    "TON": (1e-8, 5e-6), "ZEC": (0, 3e-8), "XRP": (1e-8, 1.5e-5),
    "SHIB": (1e-8, 1.5), "PEPE": (1e-8, 2.0), "TRUMP": (1e-8, 5e-6),
}


def coin_ev_usd(coin: str) -> float:
    lo, hi = COIN_RANGE.get(coin, (0.0, 0.0))
    return (lo + hi) / 2 * COIN_USD.get(coin, 0.0)


# Harga recycle per ikan (trashCatalog). Upgrade backpack → multiplier
# 1 + floor((cap-8)/8)*10 (cap 16 = 11×, cap 48 = 51×) — inilah alasan
# milestone PERTAMA adalah backpack, bukan WD.
TRASH_PRICE = {
    "Clownfish": 1.1e-07, "Blue Tang": 1.2e-07, "Shark": 1.3e-07,
    "Pufferfish": 1.4e-07, "Anglerfish": 1.5e-07, "Swordfish": 1.6e-07,
    "Goldfish": 1.7e-07, "Jellyfish": 1.8e-07, "Seahorse": 1.9e-07,
    "Whale": 2e-07, "Stingray": 1e-08, "Octopus": 2e-08, "Crab": 3e-08,
    "Tuna": 4e-08, "Piranha": 5e-08, "Butterflyfish": 6e-08,
    "Flying Fish": 7e-08, "Moray Eel": 8e-08, "Hammerhead": 9e-08,
    "Neon Tetra": 1e-07, "Duckweed": 0.0, "Seaweed": 0.0,
    "River Reeds": 0.0, "Sea Shell": 0.0, "River Pebble": 0.0,
    "Dry Straw": 0.0,
}

# Statistik EV terukur per koin (persist ke config) → bukti mana koin terbaik
COIN_STATS: dict = {}


# ---------------------------------------------------------------- helpers

_dashboard: Optional["BotDashboard"] = None

def log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    if _dashboard:
        _dashboard.log(msg)
    else:
        print(f"[{ts}] {msg}", flush=True)


def set_dashboard(dash: "BotDashboard") -> None:
    global _dashboard
    _dashboard = dash


def jitter(base: float, spread: float = 0.4) -> float:
    return max(0.1, random.uniform(base - spread, base + spread))


def sleep_humans(base: float, spread: float = 0.4) -> None:
    time.sleep(jitter(base, spread))


def load_config() -> dict:
    if CFG_PATH.exists():
        return json.loads(CFG_PATH.read_text(encoding="utf-8"))
    return {}


def save_config(cfg: dict) -> None:
    CFG_PATH.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def is_online(host: str = "cryptofisher.online") -> bool:
    """Cek koneksi murah (TCP 443). Dipakai standby offline — tanpa internet
    bot TIDAK bisa income, tapi proses tetap hidup dan auto-resume."""
    import socket

    try:
        with socket.create_connection((host, 443), timeout=5):
            return True
    except OSError:
        return False


def offline_standby(host: str = "cryptofisher.online") -> None:
    """Tidur sampai internet balik. Jangan exit, jangan hitung error streak."""
    log(f"OFFLINE — tidak ada internet ke {host}. "
        "Bot standby (hemat kuota/baterai), auto-resume saat koneksi balik.")
    while not is_online(host):
        time.sleep(30)
    log("ONLINE lagi — lanjut farming.")


def extract_phpsessid(raw: str) -> str:
    """Terima 'PHPSESSID=abc' atau seluruh header Cookie."""
    raw = raw.strip().strip('"').strip("'")
    m = re.search(r"PHPSESSID\s*=\s*([^;\s]+)", raw, re.I)
    if m:
        return m.group(1).strip()
    # mungkin cuma nilai polos
    if re.fullmatch(r"[A-Za-z0-9,._\-]+", raw) and "=" not in raw:
        return raw
    raise ValueError("PHPSESSID tidak ditemukan di string yang ditempel.")


# ---------------------------------------------------------------- client

class CFSess:
    def __init__(self, phpsessid: str):
        self.s = requests.Session()
        self.s.headers.update(
            {
                "User-Agent": UA,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Origin": BASE,
                "Referer": BASE + "/",
            }
        )
        self.s.cookies.set("PHPSESSID", phpsessid, domain="cryptofisher.online")

    def get(self, path: str, **kw) -> Any:
        r = self.s.get(BASE + "/" + path.lstrip("/"), timeout=30, **kw)
        return self._parse(r)

    def post(self, path: str, data: Optional[dict] = None, **kw) -> Any:
        r = self.s.post(BASE + "/" + path.lstrip("/"), data=data or {}, timeout=30, **kw)
        return self._parse(r)

    def post_action(self, action: str, **fields) -> Any:
        """ajax.php dengan action di body (gaya verify_fishing_captcha)."""
        body = {"action": action}
        body.update({k: str(v) for k, v in fields.items()})
        return self.post("ajax.php", data=body)

    @staticmethod
    def _parse(r: requests.Response) -> Any:
        ctype = r.headers.get("Content-Type", "")
        if "json" in ctype:
            try:
                return r.json()
            except Exception:
                return {"_raw": r.text[:500], "_status": r.status_code}
        return {"_text": r.text[:800], "_status": r.status_code}


# ---------------------------------------------------------------- core ops

def get_state(cf: CFSess) -> dict:
    return cf.get("ajax.php?action=get_state")


def manage_backpack(cf: CFSess, state: dict, dry: bool = False) -> tuple[int, int]:
    """Deposit semua crypto item, discard semua fish. Balas: (deposited, recycled)."""
    dep = rec = 0
    items = state.get("backpack") or []
    for it in items:
        iid = it.get("id")
        if iid is None:
            continue
        if dry:
            continue
        if it.get("item_type") == "crypto":
            resp = cf.post("ajax.php?action=deposit_crypto", data={"item_id": iid})
            if resp.get("success") or not resp.get("error"):
                dep += 1
                log(f"  deposit: {it.get('item_name')} +{it.get('amount')}")
            else:
                log(f"  deposit GAGAL: {resp}")
        else:
            # fish / worthless → recycle (discard_item)
            resp = cf.post("ajax.php?action=discard_item", data={"item_id": iid})
            if resp.get("success") or not resp.get("error"):
                rec += 1
                amt = float(it.get("amount") or 0)
                label = f"+{amt:.8f} USDT" if amt > 0 else "worthless"
                log(f"  recycle: {it.get('item_name')} ({label})")
            else:
                log(f"  recycle GAGAL: {resp}")
        sleep_humans(0.35, 0.2)
    return dep, rec


def solve_fishing_captcha(cf: CFSess) -> bool:
    d = cf.post_action("get_fishing_captcha")
    if not d.get("success"):
        log(f"  captcha fetch gagal: {d}")
        return False
    token = d.get("token")
    target = (d.get("target_name") or "").strip()
    options = d.get("options") or []
    pick = None
    for opt in options:
        if (opt.get("name") or "").strip() == target:
            pick = opt
            break
    if pick is None and target:
        # fallback: cocokkan ikon
        ticon = (d.get("target_icon") or "").strip()
        for opt in options:
            if (opt.get("icon") or "").strip() == ticon:
                pick = opt
                break
    if pick is None and options:
        pick = options[0]  # last resort — lebih baik coba daripada timeout kick
    if pick is None:
        log("  captcha: tidak ada opsi")
        return False
    log(f"  captcha: target='{target}' → pilih '{pick.get('name')}'")
    sleep_humans(0.6, 0.3)
    v = cf.post_action(
        "verify_fishing_captcha", token=token, selected_key=pick.get("key")
    )
    if v.get("kicked"):
        log(f"  KICKED: {v.get('error')}")
        return False
    if v.get("error"):
        log(f"  captcha error: {v.get('error')}")
        return False
    log(f"  captcha LOLOS: {v.get('msg', 'ok')}")
    return True


def cast(cf: CFSess, coin: str) -> Optional[dict]:
    r = cf.post("ajax.php?action=cast_rod", data={"currency": coin})
    if r.get("error") == "bot_check_required" or r.get("captcha_needed"):
        log("  Coast Guard minta inspeksi → solve captcha…")
        if solve_fishing_captcha(cf):
            sleep_humans(1.0, 0.4)
            r = cf.post("ajax.php?action=cast_rod", data={"currency": coin})
        else:
            return None
    if r.get("error"):
        err = r.get("error") or ""
        if "already in the water" in err:
            log("  umpan nyangkut → cancel_cast…")
            cf.post("ajax.php?action=cancel_cast")
            sleep_humans(1.2, 0.4)
            r = cf.post("ajax.php?action=cast_rod", data={"currency": coin})
            if r.get("success"):
                return r
        log(f"  cast error: {err}")
        return None
    return r


def hook(cf: CFSess, coin: str, token: str) -> dict:
    return cf.post(
        "ajax.php?action=hook_catch", data={"currency": coin, "token": token}
    )


# ---------------------------------------------------------------- PTC (verified live)

def ptc_list(cf: CFSess) -> dict:
    return cf.get("ptc_engine.php?action=get_ptc_data")


def ptc_watch_one(cf: CFSess, ad: dict) -> bool:
    """View_ad → tunggu timer → get_captcha → cocok ikon target → verify_view."""
    ad_id = int(ad.get("id") or 0)
    if ad_id <= 0:
        return False
    title = (ad.get("title") or "")[:40]
    dur = int(ad.get("duration") or 10)
    price = ad.get("price_per_view")
    log(f"  PTC #{ad_id} '{title}' {dur}s (+{price} USDT)…")

    # buka halaman iklan (server mencatat view dimulai)
    r = cf.s.get(f"{BASE}/view_ad.php?id={ad_id}", timeout=30)
    if r.status_code != 200 or "Viewing Ad" not in r.text:
        log(f"    view_ad gagal HTTP {r.status_code}")
        return False

    # tunggu timer di halaman (client-side); + jitter
    time.sleep(dur + random.uniform(0.3, 1.2))

    # captcha PTC: target ditandai ikon, opsi {icon, name}
    d = cf.get("ptc_engine.php?action=get_captcha")
    if not d.get("success"):
        log(f"    get_captcha: {d}")
        return False
    token = d.get("token")
    target_icon = (d.get("target_icon") or "").strip()
    options = d.get("options") or []
    pick = None
    for opt in options:
        if (opt.get("icon") or "").strip() == target_icon:
            pick = opt
            break
    if pick is None and options:
        pick = options[0]
    if pick is None:
        log("    captcha PTC: tidak ada opsi")
        return False
    selected = pick.get("name")
    log(f"    captcha PTC: pilih '{selected}'")
    sleep_humans(0.5, 0.3)

    v = cf.post(
        "ptc_engine.php",
        data={
            "action": "verify_view",
            "ad_id": str(ad_id),
            "token": token,
            "selected_fish": selected,
        },
    )
    if v.get("success"):
        log(f"    PTC LOLOS +{v.get('reward')} USDT")
        return True
    log(f"    PTC gagal: {v.get('error') or v}")
    return False


def ptc_sweep(cf: CFSess, max_ads: int = 10) -> int:
    data = ptc_list(cf)
    if not data.get("success"):
        log(f"PTC get_ptc_data: {data}")
        return 0
    ads = [
        a
        for a in (data.get("available_ads") or [])
        if int(a.get("is_viewed") or 0) != 1 and int(a.get("is_own") or 0) != 1
    ]
    if not ads:
        # senyap — iklan refill 12/24 jam, cek tiap siklus cukup 1 GET murah
        return 0
    bal = data.get("balance")
    if bal is not None:
        log(f"PTC balance site: {float(bal):.8f} USDT · {len(ads)} iklan siap")
    done = 0
    for ad in ads[:max_ads]:
        try:
            if ptc_watch_one(cf, ad):
                done += 1
        except Exception as e:
            log(f"    PTC error #{ad.get('id')}: {e}")
        sleep_humans(2.5, 1.0)
    return done


# ---------------------------------------------------------------- Auto Withdraw

def wd_cfg(cfg: dict) -> dict:
    return {
        "gateway": (cfg.get("wd_gateway") or "").strip(),
        "address": (cfg.get("wd_address") or "").strip(),
        "currency": (cfg.get("wd_currency") or "USDT").upper(),
        "min_usd": float(cfg.get("wd_min_usd") or 0.001),
    }


def try_withdraw(cf: CFSess, cfg: dict, force: bool = False) -> float:
    """Tarik saldo koin apa pun yang USD-nya >= min. Balas: total USD ditarik.

    Kebijakan GROWTH (default, matikan: hold_wd_until_upgrade=false di config):
    withdraw selalu menarik SELURUH saldo, jadi sambil nabung milestone
    upgrade PERTAMA (backpack 11× recycle + Pro Rod) WD ditahan sampai
    saldo >= 1.002 USDT → status tick langsung beli upgrade → sisa ditarik.
    Setelah 2 milestone itu, WD bebas terus. Override sekali: --wd-now.
    """
    w = wd_cfg(cfg)
    if not w["gateway"] or not w["address"]:
        if force:
            log("WD belum dikonfigurasi. Set dulu:")
            log('  python3 cryptofisher_auto.py --set-wd faucetpay user@email.com')
        return 0.0
    st = get_state(cf)
    if not st.get("success"):
        log(f"WD: get_state gagal {st}")
        return 0.0
    bals = st.get("balances") or {}
    usdt = float(bals.get("USDT") or 0)
    milestones_done = int(st.get("has_pro_rod") or 0) == 1 and int(st.get("capacity") or 8) > 8

    if cfg.get("hold_wd_until_upgrade", True) and not milestones_done and usdt < 1.002:
        if force:
            log(f"WD ditahan — nabung milestone upgrade ({usdt:.6f}/1.002 USDT)")
        return 0.0

    cands = []
    for cur, raw in bals.items():
        try:
            amt = float(raw)
        except (TypeError, ValueError):
            continue
        if amt <= 0:
            continue
        usd = amt * COIN_USD.get(cur, 0.0)
        if usd >= w["min_usd"]:
            cands.append((usd, cur, amt))
    # koin terkonfigurasi dulu, lalu nilai USD terbesar
    cands.sort(key=lambda x: (x[1] != w["currency"], -x[0]))
    if not cands:
        return 0.0

    total_usd = 0.0
    for usd, cur, amt in cands[:3]:
        log(f"WD → {w['gateway']} · {w['address']} · {amt:.8f} {cur} (≈${usd:.5f})")
        r = cf.post(
            "ajax.php?action=withdraw",
            data={"currency": cur, "gateway": w["gateway"], "address": w["address"]},
        )
        if r.get("error"):
            log(f"  WD gagal {cur}: {r.get('error')}")
            continue
        log(f"  WD OK {cur}: {r.get('msg') or r}")
        total_usd += usd
        sleep_humans(1.5, 0.5)
    return total_usd


# ---------------------------------------------------------------- EXP (HP Chest)

def claim_chest_if_active(cf: CFSess) -> bool:
    """EXP: HP Chest melayang di air ±30 detik → claim. Poll dari loop."""
    try:
        ang = cf.get("ajax.php?action=get_online_anglers")
    except Exception as e:
        log(f"  chest poll error: {e}")
        return False
    chest = ang.get("chest") or {}
    if not chest.get("active"):
        return False
    cid = chest.get("id")
    log(f"  📦 HP CHEST AKTIF! ({cid}, dur {chest.get('duration')}s) → claim…")
    r = cf.post_action("claim_hp_chest", chest_id=cid)
    if r.get("success"):
        log(
            f"  📦 EXP +{r.get('hp_gained')} → hp={r.get('hp')} "
            f"level={r.get('level')}"
        )
        return True
    log(f"  chest claim gagal: {r}")
    return False


# ---------------------------------------------------------------- MARKET

FLOORS: dict = {}  # fish → harga jual terendah aktif (cache 5 menit)


def market_sweep(cf: CFSess, st: dict, dry: bool = False) -> tuple[int, int]:
    """Claim penjualan masuk + listing ikan yang floor market ≥10× recycle.

    Listing = tahan ikan di order 48 jam (jual jauh di atas recycle, mis. Whale
    recycle 2e-7 vs floor ~5e-6). Max 2 order aktif biar slot keranjang tidak
    tersendat. Balas: (claimed, listed).
    """
    mk = cf.get("market_engine.php?action=get_market_data")
    if not mk.get("success"):
        return 0, 0

    floors: dict = {}
    for o in mk.get("sell_orders") or []:
        if o.get("status") != "active":
            continue
        name = o.get("fish_name")
        price = float(o.get("price_usdt") or 0)
        if name and price > 0:
            floors[name] = min(floors.get(name, price), price)
    FLOORS.clear()
    FLOORS.update(floors)

    claimed = listed = 0
    for c in mk.get("claimable") or []:
        if dry:
            break
        r = cf.post(
            "market_engine.php",
            data={"action": "claim_fish", "order_id": c.get("id")},
        )
        if r.get("success"):
            claimed += 1
            log(f"  market claim: {c.get('fish_name')} x{c.get('quantity')} → basket")
        else:
            log(f"  market claim gagal: {r}")

    my_active = [
        o
        for o in (mk.get("my_orders") or [])
        if o.get("status") == "active" and o.get("order_type") == "sell"
    ]
    for it in st.get("backpack") or []:
        if dry or len(my_active) + listed >= 2:
            break
        if it.get("item_type") == "crypto":
            continue
        name = it.get("item_name") or ""
        base = TRASH_PRICE.get(name, -1)
        floor = FLOORS.get(name, 0)
        if base <= 0 or floor < base * 10:
            continue
        price = floor * 0.95  # undercut tipis biar cepat laku
        r = cf.post(
            "market_engine.php",
            data={
                "action": "create_sell_order",
                "item_id": it.get("id"),
                "quantity": 1,
                "price": f"{price:.8f}",
            },
        )
        if r.get("error"):
            log(f"  list market gagal {name}: {r.get('error')}")
        else:
            listed += 1
            log(f"  list market: {name} @{price:.8f} USDT (recycle {base:.1e} → {floor / base:.0f}×)")
    return claimed, listed


# ---------------------------------------------------------------- main loop

def _safe_get_state(cf: "CFSess") -> dict:
    """get_state yang tidak pernah crash standby — network reset di-catch."""
    try:
        return get_state(cf)
    except requests.RequestException as e:
        log(f"get_state network: {e.__class__.__name__} — coba lagi nanti")
        return {}


def _is_net_err(e: BaseException) -> bool:
    if isinstance(e, requests.RequestException):
        return True
    return isinstance(e, (ConnectionError, OSError, TimeoutError))


def _wait_session_valid(cf: "CFSess") -> None:
    """Session mati → standby: reload config tiap 2 menit sampai cookie
    baru valid. Script tetap hidup tanpa apikey (login --login butuh
    hCaptcha; --setup tempel cookie manual tanpa key). Network reset juga
    tidak boleh membunuh proses (CF sering ConnectionReset)."""
    log("Session expired — standby mode (script tetap jalan). "
        "Tempel cookie baru: python3 sites/cryptofisher/cryptofisher_auto.py --setup "
        "| cek ulang tiap 2 menit")
    while True:
        if not is_online():
            offline_standby()
            continue
        time.sleep(120)
        try:
            raw = str(load_config().get("phpsessid") or "")
            sid = extract_phpsessid(raw)
        except (ValueError, AttributeError):
            continue
        cf.s.cookies.set("PHPSESSID", sid, domain="cryptofisher.online")
        st = _safe_get_state(cf)
        if st.get("success"):
            log("Session baru valid — lanjut farming.")
            return


def run(args: argparse.Namespace) -> int:
    # ─── Initialize TUI Dashboard ─────────────────────────────────────
    global _dashboard
    if HAS_TUI and not args.once and not args.dump_view_ad:
        stats = BotStats(current_coin=(args.coin or cfg.get("coin") or "USDT").upper())
        config = DashboardConfig(
            title="CRYPTOFISHER AUTO-FARM",
            subtitle="Fishing • PTC • Market • WD",
            theme_color=Palette.ACCENT,
            show_banner=True,
            show_stats=True,
            show_logs=True,
            show_progress=True,
            log_lines=14,
            refresh_rate=0.5,
        )
        _dashboard = BotDashboard(config, stats)
        _dashboard.start()
    else:
        _dashboard = None

    cfg = load_config()
    raw_cookie = args.session or cfg.get("phpsessid") or ""
    if not raw_cookie:
        log("Belum ada session — standby (script tetap jalan). "
            "Pilih salah satu:")
        log("  python3 cryptofisher_auto.py --login            # otomatis (NoneCap API)")
        log("  python3 sites/cryptofisher/cryptofisher_auto.py --setup            # tempel cookie manual")
        # standby: nunggu cookie ditempel via --setup dari proses lain
        cf = CFSess("")
        _wait_session_valid(cf)
        raw_cookie = str(load_config().get("phpsessid") or "")
    try:
        sid = extract_phpsessid(raw_cookie)
    except ValueError as e:
        log(str(e))
        if _dashboard:
            _dashboard.stop()
        return 2

    coin = (args.coin or cfg.get("coin") or "USDT").upper()
    if coin not in VALID_COINS:
        log(f"Koin '{coin}' tidak dikenal. Pilihan: {', '.join(sorted(VALID_COINS))}")
        if _dashboard:
            _dashboard.stop()
        return 2

    cf = CFSess(sid)
    st = _safe_get_state(cf)
    if not st.get("success") and not is_online():
        offline_standby()
        st = _safe_get_state(cf)
    if not st.get("success"):
        log(f"get_state gagal: {st or 'network error'}")
        _wait_session_valid(cf)
        st = _safe_get_state(cf)
        if not st.get("success"):
            # masih gagal → standby offline, jangan exit
            if not is_online():
                offline_standby()
                st = _safe_get_state(cf)
            if not st.get("success"):
                _wait_session_valid(cf)
                if _dashboard:
                    _dashboard.stop()
                return 3

    if _dashboard:
        _dashboard.stats.current_coin = coin
        _dashboard.update_balance(st.get("balances") or {})
        _dashboard.set_last_action("Login verified")

    log(
        f"Login OK — level {st.get('level')}, HP {st.get('hp')}, "
        f"backpack {len(st.get('backpack') or [])}/{st.get('capacity')}, "
        f"coin={coin}"
    )
    balances = st.get("balances") or {}
    if balances:
        log("Balance: " + ", ".join(f"{k}={float(v):.8f}" for k, v in balances.items()))

    # ---- strategi profit: statistik session + persist stats koin
    COIN_STATS.clear()
    COIN_STATS.update(cfg.get("coin_stats") or {})
    COIN_STATS.setdefault(coin, {"casts": 0, "hits": 0, "usd": 0.0})

    def _total_usd(b: dict) -> float:
        return sum(float(v or 0) * COIN_USD.get(k, 0.0) for k, v in (b or {}).items())

    t0 = time.time()
    usd0 = _total_usd(balances)
    wd_session = 0.0
    log(
        f"Strategi: EV teori {coin}=${coin_ev_usd(coin):.2e}/cast · "
        f"hold WD={'ON' if cfg.get('hold_wd_until_upgrade', True) else 'off'} → "
        f"milestone backpack(11×)+ProRod @1.002 USDT"
    )

    if args.dump_view_ad is not None:
        r = cf.s.get(f"{BASE}/view_ad.php?id={args.dump_view_ad}", timeout=30)
        p = Path.cwd() / f"view_ad_{args.dump_view_ad}.html"
        p.write_text(r.text, encoding="utf-8", errors="replace")
        log(f"dump view_ad id={args.dump_view_ad} → {p} ({len(r.text)} bytes)")
        if not args.loop and not args.once:
            if _dashboard:
                _dashboard.stop()
            return 0

    if args.once:
        rc = _one_cycle(cf, coin, args, 1)
        if args.auto_wd:
            try_withdraw(cf, load_config(), force=True)
        if _dashboard:
            _dashboard.stop()
        return rc

    if args.wd_now:
        wd_session += try_withdraw(cf, cfg, force=True) or 0.0

    log(
        f"Loop auto-all dimulai (Ctrl+C untuk berhenti). "
        f"PTC={'ON' if args.ptc else 'off'} WD={'ON' if args.auto_wd else 'off'}"
    )
    cycles = 0
    errors = 0
    wd_cfg_live = load_config()
    try:
        while True:
            # offline → standby dulu (proses hidup, kuota nol, resume otomatis)
            if not is_online():
                if _dashboard:
                    _dashboard.set_last_action("OFFLINE — waiting for connection")
                offline_standby()
                if _dashboard:
                    _dashboard.set_last_action("ONLINE — resuming")
                continue
            cycles += 1
            if _dashboard:
                _dashboard.stats.cycles = cycles
                _dashboard.refresh()

            try:
                if _dashboard:
                    _dashboard.set_last_action(f"Cycle #{cycles} — cast & hook")
                rc = _one_cycle(cf, coin, args, cycles)
                if _dashboard:
                    _dashboard.increment_cycle(rc == 0)
            except (requests.RequestException, ConnectionError, OSError, TimeoutError) as e:
                log(f"network di siklus: {e.__class__.__name__} → standby offline")
                offline_standby()
                continue
            if rc == 3:
                _wait_session_valid(cf)
                continue
            if rc != 0:
                errors += 1
                backoff = min(60, 5 * errors)
                log(f"error streak={errors} → tunggu {backoff}s")
                time.sleep(backoff)
                if errors >= 8:
                    # jangan mati — coba standby offline / tunggu session
                    if not is_online():
                        offline_standby()
                        errors = 0
                        continue
                    log("terlalu banyak error → standby (reload config tiap 2 menit)")
                    _wait_session_valid(cf)
                    errors = 0
            else:
                errors = 0

            if args.ptc and args.ptc_every > 0 and cycles % args.ptc_every == 0:
                try:
                    if _dashboard:
                        _dashboard.set_last_action("PTC sweep")
                    n = ptc_sweep(cf, max_ads=args.ptc_max)
                    if n:
                        log(f"PTC sweep selesai: {n} iklan")
                except Exception as e:
                    log(f"PTC error: {e}")

            if args.auto_wd and cycles % args.wd_every == 0:
                try:
                    if _dashboard:
                        _dashboard.set_last_action("Auto Withdraw check")
                    wd_cfg_live = load_config()  # reload agar --set-wd berlaku tanpa restart
                    wd_session += try_withdraw(cf, wd_cfg_live, force=False) or 0.0
                except Exception as e:
                    log(f"WD error: {e}")

            # HP Chest poll tambahan tiap siklus (jendela claim hanya ±30 detik)
            claim_chest_if_active(cf)

            if cycles % 5 == 0:
                try:
                    st = get_state(cf)
                    if st.get("success"):
                        b = st.get("balances") or {}
                        if _dashboard:
                            _dashboard.update_balance(b)
                            _dashboard.stats.extra = {
                                "level": st.get("level"),
                                "exp": st.get("exp"),
                                "hp": f"{st.get('hp')}/100",
                                "backpack": f"{len(st.get('backpack') or [])}/{st.get('capacity')}",
                                "has_pro_rod": bool(st.get("has_pro_rod")),
                                "capacity": st.get("capacity"),
                                "wd_session_usd": f"${wd_session:.5f}",
                            }
                        log(
                            f"#status lv{st.get('level')} exp={st.get('exp')} "
                            f"hp={st.get('hp')}/100 "
                            f"bp {len(st.get('backpack') or [])}/{st.get('capacity')} | "
                            + ", ".join(f"{k}={float(v):.8f}" for k, v in b.items())
                        )

                        # --- stats EV koin terukur (bukti koin mana yang terbaik)
                        s = COIN_STATS.get(coin) or {}
                        casts = int(s.get("casts") or 0)
                        if casts:
                            ev_meas = float(s.get("usd") or 0) / casts
                            log(
                                f"#ev {coin}: {casts} cast, {s.get('hits')} kripto, "
                                f"EV terukur ${ev_meas:.2e}/cast "
                                f"(teori ${coin_ev_usd(coin):.2e})"
                            )
                            # guard: BTC/ETH/ZEC min=0 — kalau 40 cast 0 kripto, balik ke USDT
                            if coin != "USDT" and casts >= 40 and int(s.get("hits") or 0) == 0:
                                log(f"#ev {coin} 0 hit dalam 40 cast → balik ke USDT")
                                coin = "USDT"
                                cfg["coin"] = coin
                                save_config(cfg)
                                COIN_STATS.setdefault(coin, {"casts": 0, "hits": 0, "usd": 0.0})
                                if _dashboard:
                                    _dashboard.stats.current_coin = coin

                        # --- auto upgrade saat saldo >= milestone
                        usdt = float(b.get("USDT") or 0)
                        cap = int(st.get("capacity") or 8)
                        if usdt >= 1.002:
                            if cap == 8:
                                r = cf.get("ajax.php?action=upgrade_backpack")
                                log(f"  MILESTONE backpack → {r}")
                            elif not int(st.get("has_pro_rod") or 0):
                                r = cf.post("ajax.php?action=buy_rod_balance")
                                log(f"  MILESTONE Pro Rod → {r}")
                            elif cap < 48:
                                r = cf.get("ajax.php?action=upgrade_backpack")
                                log(f"  upgrade backpack lagi → {r}")

                        # --- rate session + ETA milestone + status WD
                        hours = max((time.time() - t0) / 3600.0, 1e-9)
                        net = _total_usd(b) + wd_session - usd0
                        rate = net / hours
                        st_holding = (
                            cfg.get("hold_wd_until_upgrade", True)
                            and (
                                not int(st.get("has_pro_rod") or 0)
                                or int(st.get("capacity") or 8) == 8
                            )
                        )
                        if st_holding and usdt < 1.002 and rate > 1e-9:
                            eta = (1.002 - usdt) / rate
                            log(
                                f"#rate +${net:.5f} ({rate:.5f} $/j) · WD HOLD → "
                                f"milestone dalam ±{eta:.1f} jam · WD session ${wd_session:.5f}"
                            )
                        else:
                            log(
                                f"#rate +${net:.5f} ({rate:.5f} $/j) · "
                                f"WD session ${wd_session:.5f} "
                                f"({'milestone DONE — WD bebas' if not st_holding else 'hold, menunggu 1.002'})"
                            )
                        # persist stats EV ke config
                        cfg["coin_stats"] = COIN_STATS
                        save_config(cfg)
                except Exception as e:
                    log(f"#status error: {e}")

            time.sleep(jitter(args.between_casts, 0.8))
    except KeyboardInterrupt:
        log("Dihentikan user.")
        cfg["coin_stats"] = COIN_STATS
        save_config(cfg)
    finally:
        if _dashboard:
            _dashboard.stop()
    return 0


def _one_cycle(cf: CFSess, coin: str, args: argparse.Namespace, cycles: int = 0) -> int:
    st = get_state(cf)
    if not st.get("success"):
        log(f"get_state: {st}")
        if st.get("error") == "Unauthorized":
            return 3
        return 1

    # market dulu (listing/claim) — SEBELUM recycle, kalau tidak ikannya sudah hilang
    if args.market_every > 0 and cycles % args.market_every == 1:
        try:
            market_sweep(cf, st, dry=args.dry)
        except Exception as e:
            log(f"market error: {e}")

    manage_backpack(cf, st, dry=args.dry)

    r = cast(cf, coin)
    if r is None:
        return 1
    token = r.get("token") or ""
    delay = float(r.get("delay") or 10)
    # server kirim delay; tunggu delay + jitter manusiawi (jangan telat > ~1.5s)
    wait = delay + random.uniform(0.15, 1.1)
    log(f"  cast ok — tunggu {wait:.1f}s (nibble)…")
    # tidur potong-potong 4s → poll HP Chest (jendela cuma ±30s, jangan kelewat)
    end = time.time() + wait
    while time.time() < end:
        chunk = min(4.0, end - time.time())
        if chunk <= 0:
            break
        time.sleep(chunk)
        claim_chest_if_active(cf)

    h = hook(cf, coin, token)
    # stat EV per koin (cast dihitung setiap hook terjawab, termasuk escaped)
    s = COIN_STATS.setdefault(coin, {"casts": 0, "hits": 0, "usd": 0.0})
    s["casts"] = s.get("casts", 0) + 1
    if h.get("escaped"):
        log("  ikan LEWAT (escaped) — coba lagi")
        if _dashboard:
            _dashboard.set_last_action("Escaped — retrying")
        return 0
    if h.get("success"):
        if h.get("type") == "trash":
            log(f"  ikan: {h.get('name')} (masuk keranjang)")
        else:
            s["hits"] = s.get("hits", 0) + 1
            try:
                usd_earned = float(h.get("amount") or 0) * COIN_USD.get(coin, 0.0)
                s["usd"] = s.get("usd", 0.0) + usd_earned
                if _dashboard:
                    _dashboard.add_earned(usd_earned)
            except (TypeError, ValueError):
                pass
            log(
                f"  KRIPTO: +{h.get('amount')} {h.get('name') or h.get('currency')} "
                f"({h.get('type')})"
            )
        return 0
    if h.get("error"):
        log(f"  hook error: {h.get('error')}")
        return 1
    log(f"  hook respons tak dikenal: {h}")
    return 0


# ---------------------------------------------------------------- NoneCap + login

def get_nonecap_key() -> str:
    cfg = load_config()
    return (
        os.environ.get("NONECAP_KEY")
        or cfg.get("nonecap_key")
        or ""
    ).strip()


def fetch_sitekey(cf: Optional[CFSess] = None) -> str:
    """Baca data-sitekey dari halaman login (fallback ke key yang diketahui)."""
    try:
        r = requests.get(
            BASE + "/",
            headers={"User-Agent": UA},
            timeout=30,
        )
        m = re.search(r'data-sitekey="([0-9a-fA-F-]{30,})"', r.text)
        if m:
            return m.group(1)
    except Exception as e:
        log(f"  scrape sitekey gagal: {e}")
    return CF_SITEKEY_FALLBACK


def nonecap_solve(api_key: str, sitekey: str, url: str, user_agent: str) -> dict:
    """Mint token hCaptcha P1_ via NoneCap API. Balas dict solve (terminal)."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {"type": "hcaptcha", "sitekey": sitekey, "url": url}
    if user_agent:
        body["user_agent"] = user_agent
    log(f"  NoneCap solve… sitekey={sitekey[:8]}… url={url}")
    r = requests.post(
        f"{NONECAP_API}/solves",
        params={"wait": 60},
        headers=headers,
        json=body,
        timeout=90,
    )
    data = r.json() if r.headers.get("Content-Type", "").find("json") >= 0 else {}
    if r.status_code >= 400:
        err = data.get("error") or {}
        raise RuntimeError(
            f"NoneCap HTTP {r.status_code}: {err.get('code')} — {err.get('message')}"
        )
    # 202 = masih pending → poll
    deadline = time.time() + 90
    while data.get("status") in ("pending", "solving") and time.time() < deadline:
        time.sleep(2)
        pr = requests.get(
            f"{NONECAP_API}/solves/{data['id']}",
            params={"wait": 30},
            headers=headers,
            timeout=45,
        )
        data = pr.json()
    if data.get("status") != "solved":
        err = data.get("error") or {}
        raise RuntimeError(
            f"solve {data.get('status')}: {err.get('code')} — {err.get('message')}"
        )
    return data


def nonecap_report_rejected(api_key: str, solve_id: str) -> None:
    """Laporkan token yang ditolak situs (opsional, bantu kualitas)."""
    try:
        requests.post(
            f"{NONECAP_API}/feedback",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"feedback": [{"solve_id": solve_id, "outcome": "rejected"}]},
            timeout=15,
        )
    except Exception:
        pass


# ---------------------------------------------------- hCaptcha multi-provider
# NoneCap bisa kredit habis → dispatcher coba tiap provider yang key-nya ada
# di cf_config.json (atau env) sampai satu balik token.

MYTHIX_API = "https://mythixsolve.tech/api"  # docs bilang mythix.io — host aslinya ini (terverifikasi 401 live)   # hCaptcha-only, 1000 kredit gratis signup
HCAPTCHA_KEYS = (("nonecap_key", "NoneCap"), ("mythix_key", "MythiX"))


def mythix_solve(api_key: str, sitekey: str, url: str,
                 user_agent: str = "") -> dict:
    """Mint token hCaptcha via MythiX (sync envelope). Balas dict {token}."""
    headers = {"Authorization": f"Bearer {api_key}",
               "Content-Type": "application/json"}
    body = {"captcha_type": "HCaptchaTask", "site_key": sitekey,
            "site_url": url}
    log(f"  MythiX solve… sitekey={sitekey[:8]}… url={url}")
    r = requests.post(f"{MYTHIX_API}/tasks/create", headers=headers,
                      json=body, timeout=90)
    try:
        j = r.json()
    except Exception:
        raise RuntimeError(f"MythiX HTTP {r.status_code} non-JSON: "
                           f"{r.text[:200]}")
    if j.get("errorId"):
        raise RuntimeError(f"MythiX error {j.get('errorId')}: "
                           f"{j.get('errorCode')} (HTTP {r.status_code})")
    if j.get("status") == "processing" and j.get("taskId"):  # async fallback
        tid = j["taskId"]
        deadline = time.time() + 90
        while time.time() < deadline:
            time.sleep(2)
            p = requests.get(f"{MYTHIX_API}/tasks/get",
                             params={"taskId": tid}, headers=headers,
                             timeout=45).json()
            if p.get("status") == "ready":
                j = p
                break
            if p.get("errorId") or p.get("status") == "failed":
                raise RuntimeError(f"MythiX poll: {p}")
        else:
            raise RuntimeError("MythiX: timeout polling token")
    tok = ((j.get("solution") or {}).get("token")) or ""
    if not tok:
        raise RuntimeError(f"MythiX tanpa token: {j}")
    return {"token": tok, "provider": "mythix"}


def solve_hcaptcha(sitekey: str, url: str, user_agent: str = UA) -> dict:
    """Solve hCaptcha → dict dengan 'token' + 'provider'. Coba tiap key ada."""
    cfg = load_config()
    errors: list = []
    tried = False
    for name, label in HCAPTCHA_KEYS:
        key = (os.environ.get(name.upper()) or cfg.get(name) or "").strip()
        if not key:
            continue
        tried = True
        try:
            if name == "nonecap_key":
                d = nonecap_solve(key, sitekey, url, user_agent)
                d.setdefault("provider", "nonecap")
            else:
                d = mythix_solve(key, sitekey, url, user_agent)
            d["_key"] = key
            d["_keyname"] = name
            if d.get("token"):
                return d
            errors.append(f"{label}: token kosong")
        except Exception as e:
            errors.append(f"{label}: {e}")
            log(f"  {label} hCaptcha gagal: {e}")
    if not tried:
        raise RuntimeError("tanpa key hCaptcha (nonecap_key/mythix_key)")
    raise RuntimeError("; ".join(errors))


def do_login(args: argparse.Namespace) -> int:
    """Login penuh via Python: hCaptcha (NoneCap/MythiX) → auth_login → simpan cookie."""
    email = args.email or input("Email: ").strip()
    password = args.password or getpass.getpass("Password: ")
    if not email or not password:
        log("Email/password kosong.")
        return 2

    cfg = load_config()
    has_key = any(
        (os.environ.get(n.upper()) or cfg.get(n) or "").strip()
        for n, _ in HCAPTCHA_KEYS
    )
    if not has_key:
        # Temuan 2026-11-08: server CF TIDAK memvalidasi isi captcha —
        # field "h-captcha-response" cukup terisi (token dummy lolos login).
        log("Tanpa key hCaptcha — pakai jalur cadangan token dummy "
            "(server hanya cek field terisi).")

    # cek saldo dulu (hemat solve yang gagal) — NoneCap punya endpoint /me
    nkey = (os.environ.get("NONECAP_KEY") or cfg.get("nonecap_key") or "").strip()
    if nkey:
        try:
            me = requests.get(
                f"{NONECAP_API}/me",
                headers={"Authorization": f"Bearer {nkey}"},
                timeout=15,
            ).json()
            bal = me.get("credits_balance")
            log(f"NoneCap balance: {bal} kredit")
        except Exception as e:
            log(f"  cek balance gagal (lanjut): {e}")

    sitekey = ""
    login_url = BASE + "/"
    solve = None
    token = ""
    solve_ua = UA
    if has_key:
        sitekey = fetch_sitekey()
        # UA netral; provider boleh balas user_agent sendiri untuk submit
        try:
            solve = solve_hcaptcha(sitekey, login_url, user_agent=UA)
        except Exception as e:
            log(f"hCaptcha solve gagal: {e} -> jalur cadangan")
        if solve:
            token = solve.get("token") or ""
            solve_ua = solve.get("user_agent") or UA
            if token:
                log(f"  token OK via {solve.get('provider')} ({token[:16]}…) "
                    f"credits_charged={solve.get('credits_charged')}")
    if not token:
        token = "00000000-0000-0000-0000-000000000000"
        log("  token cadangan dummy dipakai (server tidak memvalidasi isi captcha)")

    # submit login — pakai UA yang sama dengan yang dipakai solve (beberapa situs binding)
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": solve_ua,
            "Accept": "application/json, text/plain, */*",
            "Origin": BASE,
            "Referer": BASE + "/",
        }
    )
    resp = s.post(
        BASE + "/ajax.php",
        data={
            "action": "auth_login",
            "email": email,
            "password": password,
            "h-captcha-response": token,
        },
        timeout=30,
    )
    try:
        data = resp.json()
    except Exception:
        log(f"auth_login respons bukan JSON: HTTP {resp.status_code} {resp.text[:200]!r}")
        return 1

    if not data.get("success"):
        log(f"auth_login gagal: {data.get('error') or data}")
        if solve and solve.get("provider") == "nonecap" and solve.get("id"):
            nonecap_report_rejected(solve.get("_key", ""), solve.get("id", ""))
        # retry 1x dengan solve baru (token bisa sekali-pakai / hang)
        log("  retry login sekali…")
        if has_key and sitekey:
            try:
                solve = solve_hcaptcha(sitekey, login_url, user_agent=UA)
            except Exception as e:
                log(f"retry solve gagal: {e}")
                return 1
            token = solve.get("token") or token
            solve_ua = solve.get("user_agent") or UA
            s.headers["User-Agent"] = solve_ua
        resp = s.post(
            BASE + "/ajax.php",
            data={
                "action": "auth_login",
                "email": email,
                "password": password,
                "h-captcha-response": token,
            },
            timeout=30,
        )
        try:
            data = resp.json()
        except Exception:
            log(f"retry gagal: HTTP {resp.status_code}")
            return 1
        if not data.get("success"):
            log(f"auth_login tetap gagal: {data.get('error') or data}")
            if solve and solve.get("provider") == "nonecap" and solve.get("id"):
                nonecap_report_rejected(solve.get("_key", ""),
                                        solve.get("id", ""))
            return 1

    sid = s.cookies.get("PHPSESSID")
    if not sid:
        # coba juga dari cookie jar domain apa pun
        for c in s.cookies:
            if c.name == "PHPSESSID":
                sid = c.value
                break
    if not sid:
        log("Login sukses tapi PHPSESSID tidak ada di cookie — cek respons.")
        log(f"  cookies: {list(s.cookies)}")
        return 1

    cfg = load_config()
    cfg["phpsessid"] = sid
    if args.coin:
        cfg["coin"] = args.coin.upper()
    cfg.setdefault("coin", "USDT")
    # (key solver tidak disimpan otomatis — pakai --set-key kalau perlu)
    save_config(cfg)

    # verifikasi get_state
    cf = CFSess(sid)
    st = get_state(cf)
    if not st.get("success"):
        log(f"Login OK (cookie ada) tapi get_state gagal: {st}")
        return 1
    log(
        f"LOGIN SUKSES — level {st.get('level')}, "
        f"backpack {len(st.get('backpack') or [])}/{st.get('capacity')}. "
        f"PHPSESSID tersimpan di {CFG_PATH}"
    )
    balances = st.get("balances") or {}
    if balances:
        log("Balance: " + ", ".join(f"{k}={float(v):.8f}" for k, v in balances.items()))
    log("Jalankan:  python3 cryptofisher_auto.py")
    return 0


def do_set_wd(args: argparse.Namespace) -> int:
    """Simpan tujuan withdraw: --set-wd faucetpay|cryptofaucet ALAMAT"""
    gw = (args.set_wd or "").strip().lower()
    addr = (args.wd_address or "").strip()
    if gw not in ("faucetpay", "cryptofaucet"):
        log("Gateway harus faucetpay atau cryptofaucet.")
        log('  python3 cryptofisher_auto.py --set-wd faucetpay user@email.com')
        log('  python3 cryptofisher_auto.py --set-wd cryptofaucet C100000')
        return 2
    if not addr:
        log("Alamat kosong. Contoh:")
        log(f"  python3 cryptofisher_auto.py --set-wd {gw} {'user@email.com' if gw=='faucetpay' else 'C100000'}")
        return 2
    if gw == "faucetpay" and "@" not in addr:
        log("FaucetPay biasanya butuh email akun.")
    if gw == "cryptofaucet" and not re.match(r"^C\d+$", addr, re.I):
        log("CryptoFaucet biasanya butuh ID C+angka (mis. C100000).")

    cfg = load_config()
    cfg["wd_gateway"] = gw
    cfg["wd_address"] = addr
    cfg.setdefault("wd_currency", "USDT")
    cfg.setdefault("wd_min_usd", 0.001)
    save_config(cfg)
    log(f"WD tersimpan → {gw} · {addr} · {cfg.get('wd_currency')} (min ${cfg.get('wd_min_usd')})")
    log("Aktifkan dengan flag:  python3 cryptofisher_auto.py --ptc --auto-wd")
    return 0


# ---------------------------------------------------------------- setup

def do_setup() -> int:
    print("=== Setup CryptoFisher bot ===")
    print("1) Buka https://cryptofisher.online di browser HP, LOGIN (selesaikan hCaptcha).")
    print("2) Di halaman situs yang sudah login, jalankan bookmarklet:")
    print("   javascript:prompt('PHPSESSID', (document.cookie.match(/PHPSESSID=([^;]+)/)||[])[1]||'NOT_FOUND')")
    print("   (cara pasang bookmarklet ada di cf_install.html)")
    print("3) Tempel hasilnya di bawah ini.\n")
    raw = input("PHPSESSID / Cookie: ").strip()
    if not raw:
        print("Batal.")
        return 1
    try:
        sid = extract_phpsessid(raw)
    except ValueError as e:
        print(e)
        return 1

    cfg = load_config()
    cfg["phpsessid"] = sid
    coin = input("Koin mancing [USDT]: ").strip().upper() or "USDT"
    if coin not in VALID_COINS:
        print(f"Koin tidak dikenal, pakai USDT.")
        coin = "USDT"
    cfg["coin"] = coin
    save_config(cfg)

    cf = CFSess(sid)
    st = get_state(cf)
    if not st.get("success"):
        print(f"VERIFIKASI GAGAL: {st}")
        print("Cookie mungkin salah/kedaluwarsa. Ulangi langkah 1-3.")
        return 1
    print(
        f"OK! Login terverifikasi — level {st.get('level')}, "
        f"backpack {len(st.get('backpack') or [])}/{st.get('capacity')}."
    )
    print(f"Config tersimpan: {CFG_PATH}")
    print("Jalankan:  python3 cryptofisher_auto.py")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="CryptoFisher auto-all bot (akun sendiri)")
    ap.add_argument("--setup", action="store_true", help="tempel cookie manual & verifikasi")
    ap.add_argument("--login", action="store_true",
                    help="login otomatis via solver hCaptcha (nonecap_key/mythix_key)")
    ap.add_argument("--set-key", nargs=2, metavar=("NAMA", "NILAI"),
                    help="simpan key solver ke cf_config.json "
                         "(mis: mythix_key mx_live_… / nonecap_key nc_live_…)")
    ap.add_argument("--email", help="email akun (mode --login)")
    ap.add_argument("--password", help="password akun (mode --login; lebih aman: prompt)")
    ap.add_argument("--session", help="PHPSESSID / Cookie (override config)")
    ap.add_argument("--coin", help="koin mancing, mis. USDT / TRX")
    ap.add_argument("--once", action="store_true", help="satu siklus cast→hook lalu keluar")
    ap.add_argument("--loop", action="store_true", help="(sudah default) mode loop terus-menerus")
    ap.add_argument("--dry", action="store_true", help="tanpa recycle/deposit (amati saja)")
    # SEMUA FITUR DEFAULT NYALA — jalankan cukup: python3 cryptofisher_auto.py
    ap.add_argument("--ptc", dest="ptc", action="store_true", default=True,
                    help="(default ON) sweep PTC tiap N siklus")
    ap.add_argument("--no-ptc", dest="ptc", action="store_false", help="matikan sweep PTC")
    ap.add_argument("--ptc-every", type=int, default=1,
                    help="jarak sweep PTC (siklus; 1 = tiap siklus, cek kosong cuma 1 GET)")
    ap.add_argument("--ptc-max", type=int, default=10, help="maks iklan per sweep")
    ap.add_argument("--market-every", type=int, default=3,
                    help="claim/list market tiap N siklus (0 = off)")
    ap.add_argument("--wd-now", action="store_true",
                    help="sekali paksa WD sekarang (lewati hold milestone)")
    ap.add_argument("--auto-wd", dest="auto_wd", action="store_true", default=True,
                    help="(default ON) auto withdraw saat saldo >= min (butuh --set-wd dulu)")
    ap.add_argument("--no-wd", dest="auto_wd", action="store_false", help="matikan auto WD")
    ap.add_argument("--wd-every", type=int, default=10, help="cek WD tiap N siklus")
    ap.add_argument("--set-wd", metavar="GATEWAY",
                    help="simpan tujuan WD: faucetpay | cryptofaucet")
    ap.add_argument("--wd-address", help="alamat WD (email FaucetPay / C-ID CryptoFaucet)")
    ap.add_argument("--dump-view-ad", type=int, metavar="ID",
                    help="dump HTML view_ad.php untuk analisis")
    ap.add_argument("--between-casts", type=float, default=2.5,
                    help="jeda dasar antar siklus (detik)")
    args = ap.parse_args()

    if args.set_key:
        nama, nilai = args.set_key
        cfg = load_config()
        cfg[nama] = nilai.strip()
        save_config(cfg)
        log(f"Key tersimpan: {nama} = {nilai[:6]}… "
            f"(hCaptcha: {nama in [n for n, _ in HCAPTCHA_KEYS]})")
        if not (args.setup or args.login):
            return 0
    if args.setup:
        return do_setup()
    if args.set_wd:
        return do_set_wd(args)
    if args.login:
        return do_login(args)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
