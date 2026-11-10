#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cryptofisher_level.py — LEVEL RUSH CryptoFisher (murni HTTP, tanpa browser)

Fokus: crypto catch per jam MAXIMAL → level naik secepat mungkin.
EXP = jumlah crypto catch (trash tidak dapat exp). Hit rate server ±5.4%.
Satu-satunya lever yang kita kendalikan: cast/jam (buang idle).

Bedanya dengan bot lama:
  - Loop cast→hook tanpa jeda panjang (0.6–1.4s, bukan 2.5s + PTC tiap siklus)
  - Kantong dikosongkan HANYA saat hampir penuh (bukan tiap cast)
  - PTC/market default MATI (curi waktu mancing) — nyalakan: --ptc / --market
  - HP Chest di-claim saat menunggu nibble (gratis, tidak menambah latency)
  - Status premium: progress bar level, exp/jam, ETA level berikutnya
  - WD cek jarang (tiap N cast) biar tidak memutus ritme

Cara pakai:
  python3 cryptofisher_level.py              # jalan terus
  python3 cryptofisher_level.py --once       # tes satu cast lalu keluar
  python3 cryptofisher_level.py --ptc        # sambil sweep iklan (lebih lambat)
  python3 cryptofisher_level.py --no-wd      # matikan auto withdraw

Jangan jalankan bersama cryptofisher_auto.py / auto2 (SATU akun → tabrak cast).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import requests

# ---------------- paths / config ----------------
HERE = Path(__file__).resolve().parent
CFG_PATH = HERE / "cf_config.json"

BASE = "https://cryptofisher.online"
UA = (
    "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)

# Threshold exp per level yang PERNAH terlihat (update otomatis saat naik level).
# Dipakai buat ETA — kalau belum ada, estimasi delta rata-rata.
KNOWN_LEVEL_EXP: dict[int, int] = {
    5: 171,
    6: 202,
    7: 233,
    8: 266,
}


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def jitter(base: float, spread: float = 0.35) -> float:
    return max(0.15, random.uniform(base - spread, base + spread))


def sleep_humans(base: float, spread: float = 0.3) -> None:
    time.sleep(jitter(base, spread))


def load_config() -> dict:
    if CFG_PATH.exists():
        return json.loads(CFG_PATH.read_text(encoding="utf-8"))
    return {}


def save_config(cfg: dict) -> None:
    CFG_PATH.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def extract_phpsessid(raw: str) -> str:
    raw = raw.strip().strip('"').strip("'")
    m = re.search(r"PHPSESSID\s*=\s*([^;\s]+)", raw, re.I)
    if m:
        return m.group(1).strip()
    if re.fullmatch(r"[A-Za-z0-9,._\-]+", raw) and "=" not in raw:
        return raw
    raise ValueError("PHPSESSID tidak ditemukan.")


def try_relogin(cfg: dict) -> Optional[str]:
    """Auto-login (server CF tidak validasi captcha → token dummy cukup).
    Kredensial dari env CF_EMAIL/CF_PASSWORD dulu, lalu config."""
    email = (os.environ.get("CF_EMAIL") or cfg.get("email") or "").strip()
    password = (os.environ.get("CF_PASSWORD") or cfg.get("password") or "").strip()
    if not email or not password:
        log("relogin butuh CF_EMAIL + CF_PASSWORD (env/config) — tidak ada.")
        return None
    log(f"  auto-login {email}…")
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Origin": BASE,
            "Referer": BASE + "/",
        }
    )
    try:
        resp = s.post(
            BASE + "/ajax.php",
            data={
                "action": "auth_login",
                "email": email,
                "password": password,
                "h-captcha-response": "00000000-0000-0000-0000-000000000000",
            },
            timeout=30,
        )
        data = resp.json()
    except Exception as e:
        log(f"  relogin gagal: {e}")
        return None
    if not data.get("success"):
        log(f"  relogin ditolak: {data.get('error') or data}")
        return None
    sid = None
    for c in s.cookies:
        if c.name == "PHPSESSID":
            sid = c.value
            break
    if not sid:
        log("  login OK tapi PHPSESSID tidak ada di cookie.")
        return None
    cfg["phpsessid"] = sid
    cfg.setdefault("email", email)
    # password TIDAK ditulis ke config (cukup env) — kecuali sudah ada
    if cfg.get("password"):
        cfg["password"] = password
    save_config(cfg)
    log("  login OK — PHPSESSID baru tersimpan.")
    return sid


# ---------------- HTTP client ----------------
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


# ---------------- core ops ----------------
def get_state(cf: CFSess) -> dict:
    return cf.get("ajax.php?action=get_state")


def solve_guard(cf: CFSess) -> bool:
    d = cf.post_action("get_fishing_captcha")
    if not d.get("success"):
        log(f"  guard fetch gagal: {d}")
        return False
    target = (d.get("target_name") or "").strip()
    options = d.get("options") or []
    pick = None
    for opt in options:
        if (opt.get("name") or "").strip() == target:
            pick = opt
            break
    if pick is None:
        ticon = (d.get("target_icon") or "").strip()
        for opt in options:
            if (opt.get("icon") or "").strip() == ticon:
                pick = opt
                break
    if pick is None and options:
        pick = options[0]
    if pick is None:
        log("  guard: tidak ada opsi")
        return False
    log(f"  guard: target='{target}' → '{pick.get('name')}'")
    sleep_humans(0.5, 0.25)
    v = cf.post_action(
        "verify_fishing_captcha", token=d.get("token"), selected_key=pick.get("key")
    )
    if v.get("kicked"):
        log(f"  KICKED: {v.get('error')}")
        return False
    if v.get("error"):
        log(f"  guard error: {v.get('error')}")
        return False
    log(f"  guard LOLOS: {v.get('msg', 'ok')}")
    return True


def cast(cf: CFSess, coin: str) -> Optional[dict]:
    r = cf.post("ajax.php?action=cast_rod", data={"currency": coin})
    if r.get("error") == "bot_check_required" or r.get("captcha_needed"):
        log("  Coast Guard → solve captcha…")
        if solve_guard(cf):
            sleep_humans(0.8, 0.3)
            r = cf.post("ajax.php?action=cast_rod", data={"currency": coin})
        else:
            return None
    if r.get("error"):
        err = str(r.get("error") or "")
        if "already in the water" in err:
            log("  umpan nyangkut → cancel_cast…")
            cf.post("ajax.php?action=cancel_cast")
            sleep_humans(1.0, 0.3)
            r = cf.post("ajax.php?action=cast_rod", data={"currency": coin})
            if r.get("success"):
                return r
        if "Please wait" in err:
            log("  server cooldown — tunggu 3s…")
            time.sleep(3)
            r = cf.post("ajax.php?action=cast_rod", data={"currency": coin})
            if r.get("success"):
                return r
        if "Basket is full" in err or "basket is full" in err.lower():
            log("  kantong penuh → kosongkan dulu…")
            st = get_state(cf)
            if st.get("success"):
                empty_backpack(cf, st)
                sleep_humans(0.6, 0.3)
                r = cf.post("ajax.php?action=cast_rod", data={"currency": coin})
                if r.get("success"):
                    return r
                err = str(r.get("error") or err)
        log(f"  cast error: {err}")
        return None
    return r


def hook(cf: CFSess, coin: str, token: str) -> dict:
    return cf.post("ajax.php?action=hook_catch", data={"currency": coin, "token": token})


def claim_chest(cf: CFSess) -> bool:
    try:
        ang = cf.get("ajax.php?action=get_online_anglers")
    except Exception:
        return False
    chest = (ang or {}).get("chest") or {}
    if not chest.get("active"):
        return False
    cid = chest.get("id")
    log(f"  📦 HP CHEST aktif ({cid}) → claim…")
    r = cf.post_action("claim_hp_chest", chest_id=cid)
    if r.get("success"):
        log(
            f"  📦 +{r.get('hp_gained')} → hp={r.get('hp')} "
            f"level={r.get('level')} exp={r.get('exp', '?')}"
        )
        return True
    log(f"  chest gagal: {r}")
    return False


def empty_backpack(cf: CFSess, st: dict) -> tuple[int, int]:
    """Deposit crypto, recycle sampah. Balas: (deposited, recycled)."""
    dep = rec = 0
    for it in st.get("backpack") or []:
        iid = it.get("id")
        if iid is None:
            continue
        if it.get("item_type") == "crypto":
            resp = cf.post("ajax.php?action=deposit_crypto", data={"item_id": iid})
            if resp.get("success") or not resp.get("error"):
                dep += 1
                log(f"  deposit: {it.get('item_name')} +{it.get('amount')}")
            else:
                log(f"  deposit GAGAL: {resp}")
        else:
            resp = cf.post("ajax.php?action=discard_item", data={"item_id": iid})
            if resp.get("success") or not resp.get("error"):
                rec += 1
                amt = float(it.get("amount") or 0)
                label = f"+{amt:.8f} USDT" if amt > 0 else "worthless"
                log(f"  recycle: {it.get('item_name')} ({label})")
            else:
                log(f"  recycle GAGAL: {resp}")
        sleep_humans(0.3, 0.15)
    return dep, rec


def try_withdraw(cf: CFSess, cfg: dict) -> float:
    w_cur = cfg.get("wd_currency") or "USDT"
    gw = cfg.get("wd_gateway") or ""
    addr = cfg.get("wd_address") or ""
    if not gw or not addr:
        return 0.0
    st = get_state(cf)
    if not st.get("success"):
        return 0.0
    bals = st.get("balances") or {}
    usdt = float(bals.get("USDT") or 0)
    # jangan tarik kalau masih nabung milestone Pro Rod (hold=true saja)
    if cfg.get("hold_wd_until_upgrade") and usdt < 1.002:
        if int(st.get("has_pro_rod") or 0) == 0:
            return 0.0
    min_usd = float(cfg.get("wd_min_usd") or 0.001)
    # BTC min withdrawal site: 2 sat ≈ $0.0015 — cek USD equivalent kasar
    COIN_USD = {"USDT": 1.0, "BTC": 58000.0}
    total = 0.0
    # koin terkonfigurasi dulu
    order = [w_cur] + [c for c in bals if c != w_cur]
    for cur in order:
        try:
            amt = float(bals.get(cur) or 0)
        except (TypeError, ValueError):
            continue
        if amt <= 0:
            continue
        usd = amt * COIN_USD.get(cur, 0.0)
        if usd < min_usd:
            continue
        r = cf.post(
            "ajax.php?action=withdraw",
            data={"currency": cur, "gateway": gw, "address": addr},
        )
        if r.get("error"):
            log(f"  WD gagal {cur}: {r.get('error')}")
            continue
        log(f"  💸 WD OK {cur} {amt:.8f} → {gw}: {r.get('msg') or r}")
        total += usd
        sleep_humans(1.2, 0.4)
        break  # satu koin per cek cukup
    return total


def ptc_sweep(cf: CFSess, limit: int = 5) -> int:
    d = cf.get("ptc_engine.php?action=get_ptc_data")
    if not d.get("success"):
        return 0
    ads = [
        a
        for a in d.get("available_ads") or []
        if not a.get("is_viewed")
        and not a.get("is_own")
        and int(a.get("views_left", 0) or 0) > 0
    ]
    done = 0
    for ad in ads[:limit]:
        aid, dur = ad["id"], int(ad.get("duration", 10))
        log(f"  PTC #{aid} '{str(ad.get('title', ''))[:24]}' {dur}s → +{ad.get('price_per_view')}")
        try:
            cf.get(f"view_ad.php?id={aid}")
        except Exception as e:
            log(f"    buka iklan gagal: {e}")
            continue
        time.sleep(dur + random.uniform(0.8, 2.0))
        cap = cf.get("ptc_engine.php?action=get_captcha")
        if not cap.get("success"):
            continue
        target = cap.get("target_name", "")
        chosen = next(
            (o["name"] for o in cap.get("options", []) if o["name"] == target), target
        )
        v = cf.post(
            "ptc_engine.php",
            data={
                "action": "verify_view",
                "ad_id": aid,
                "token": cap.get("token", ""),
                "selected_fish": chosen,
            },
        )
        if v.get("success"):
            done += 1
            log(f"    VERIFIED +{v.get('reward')} USDT")
        time.sleep(random.uniform(1.5, 3.0))
    return done


# ---------------- level tracker ----------------
class LevelTracker:
    def __init__(self):
        self.t0 = time.time()
        self.exp0: Optional[int] = None
        self.level0: Optional[int] = None
        self.casts = 0
        self.hits = 0
        self.samples: deque[tuple[float, int, int]] = deque(maxlen=40)  # (ts, level, exp)
        self.thresholds: dict[int, int] = dict(KNOWN_LEVEL_EXP)

    def note_state(self, level: int, exp: int) -> None:
        if self.exp0 is None:
            self.exp0 = exp
            self.level0 = level
        # catat threshold saat level pertama kali terlihat
        if level not in self.thresholds:
            self.thresholds[level] = exp
        # deteksi naik level → threshold level baru = exp saat itu
        if self.samples:
            _, prev_lv, _ = self.samples[-1]
            if level > prev_lv and level not in self.thresholds:
                self.thresholds[level] = exp
            elif level > prev_lv:
                self.thresholds[level] = min(self.thresholds[level], exp)
        self.samples.append((time.time(), level, exp))

    def exp_rate(self) -> float:
        """exp/jam dari sampel ±10 menit terakhir (atau seluruh sesi)."""
        if len(self.samples) < 2:
            return 0.0
        ts1, _, e1 = self.samples[0]
        ts2, _, e2 = self.samples[-1]
        hours = max((ts2 - ts1) / 3600.0, 1e-9)
        return max(0.0, (e2 - e1) / hours)

    def next_threshold(self, level: int, exp: int) -> int:
        if (level + 1) in self.thresholds:
            return self.thresholds[level + 1]
        # estimasi: delta rata-rata dari threshold yang diketahui
        keys = sorted(self.thresholds)
        if len(keys) >= 2:
            deltas = [
                self.thresholds[keys[i + 1]] - self.thresholds[keys[i]]
                for i in range(len(keys) - 1)
                if keys[i + 1] == keys[i] + 1
            ]
            if deltas:
                avg = sum(deltas) / len(deltas)
                return int(exp + max(20.0, avg))  # dari exp sekarang kalau threshold berikutnya belum ada
        # fallback kasar
        base = self.thresholds.get(level, exp)
        return base + 32

    def bar(self, level: int, exp: int, width: int = 20) -> str:
        nxt = self.next_threshold(level, exp)
        # kalau next dihitung dari exp sekarang, ambil floor = threshold level ini
        floor = self.thresholds.get(level, 0)
        if nxt <= floor:
            nxt = floor + 32
        pct = 0.0 if nxt <= floor else (exp - floor) / (nxt - floor)
        pct = max(0.0, min(1.0, pct))
        filled = int(round(pct * width))
        return "[" + "█" * filled + "░" * (width - filled) + f"] {int(pct * 100):3d}%"

    def status_line(self, level: int, exp: int) -> str:
        rate = self.exp_rate()
        nxt = self.next_threshold(level, exp)
        remain = max(0, nxt - exp)
        if rate > 0.05:
            eta_h = remain / rate
            if eta_h < 1:
                eta = f"{eta_h * 60:.0f}m"
            elif eta_h < 48:
                eta = f"{eta_h:.1f}j"
            else:
                eta = f"{eta_h / 24:.1f}h"
        else:
            eta = "?"
        hit_pct = (100.0 * self.hits / self.casts) if self.casts else 0.0
        up = (time.time() - self.t0) / 60.0
        return (
            f"lv{level} {self.bar(level, exp)} exp={exp}→{nxt} "
            f"| {rate:.1f} exp/j | ETA lv{level + 1} ±{eta} "
            f"| cast={self.casts} hit={self.hits} ({hit_pct:.1f}%) "
            f"| {up:.0f}m"
        )


# ---------------- main loop ----------------
def run(args: argparse.Namespace) -> int:
    cfg = load_config()
    raw_sess = cfg.get("phpsessid") or args.session or ""
    phpsessid = ""
    if raw_sess:
        try:
            phpsessid = extract_phpsessid(str(raw_sess))
        except ValueError:
            phpsessid = ""
    coin = (args.coin or cfg.get("coin") or "BTC").upper()

    cf = CFSess(phpsessid) if phpsessid else None
    st = get_state(cf) if cf else {"success": False, "error": "no session"}
    if not st.get("success"):
        log(f"get_state gagal (sesi mati?): {st}")
        sid = try_relogin(cfg)
        if not sid:
            log("Re-login manual: python3 cryptofisher_auto.py --login --email … --password …")
            return 1
        cf = CFSess(sid)
        st = get_state(cf)
        if not st.get("success"):
            log(f"get_state masih gagal setelah relogin: {st}")
            return 1

    tracker = LevelTracker()
    level = int(st.get("level") or 1)
    exp = int(st.get("exp") or 0)
    tracker.note_state(level, exp)

    bals = st.get("balances") or {}
    log("=" * 60)
    log("🎣 LEVEL RUSH CryptoFisher")
    log(f"  akun id={st.get('id') or '?'}  lv{level} exp={exp}  coin={coin}")
    log(
        f"  USDT={float(bals.get('USDT') or 0):.8f}  "
        f"BTC={float(bals.get('BTC') or 0):.8f}  "
        f"hp={st.get('hp')}/100  bp={len(st.get('backpack') or [])}/{st.get('capacity')}"
    )
    log(f"  PTC={'ON' if args.ptc else 'off'}  market={'ON' if args.market else 'off'}  "
        f"WD={'ON' if args.auto_wd else 'off'}  wd_every={args.wd_every}")
    log(f"  target: exp naik secepat mungkin (EXP = crypto catch)")
    log("=" * 60)

    wd_session = 0.0
    since_status = 0
    since_state = 0
    since_chest_try = 0
    cycles = 0
    consecutive_err = 0

    try:
        while True:
            cycles += 1

            # --- state ringkas (jarang — hemat request) ---
            since_state += 1
            if since_state >= 6 or since_status == 0:
                st = get_state(cf)
                if not st.get("success"):
                    consecutive_err += 1
                    log(f"get_state gagal x{consecutive_err}: {st}")
                    if consecutive_err >= 5:
                        log("Sesi dianggap mati — coba auto-relogin…")
                        sid = try_relogin(cfg)
                        if sid:
                            cf = CFSess(sid)
                            consecutive_err = 0
                            continue
                        log("Re-login gagal — berhenti. Re-login lalu start ulang.")
                        return 2
                    time.sleep(10)
                    continue
                consecutive_err = 0
                since_state = 0
                level = int(st.get("level") or level)
                exp = int(st.get("exp") or exp)
                tracker.note_state(level, exp)

                # kantong hampir penuh → kosongkan SEKARANG
                cap = int(st.get("capacity") or 8)
                if len(st.get("backpack") or []) >= cap - 1:
                    empty_backpack(cf, st)
                    # refresh state ringan
                    st2 = get_state(cf)
                    if st2.get("success"):
                        st = st2
                        level = int(st.get("level") or level)
                        exp = int(st.get("exp") or exp)
                        tracker.note_state(level, exp)

            # --- status premium ---
            since_status += 1
            if since_status >= 8:
                since_status = 0
                log(f"# {tracker.status_line(level, exp)}")
                cfg["coin_stats"] = cfg.get("coin_stats") or {}
                save_config(cfg)

            # --- WD jarang ---
            if args.auto_wd and cycles % args.wd_every == 0:
                try:
                    wd_session += try_withdraw(cf, cfg)
                except Exception as e:
                    log(f"  WD error: {e}")

            # --- PTC hanya kalau diminta ---
            if args.ptc and cycles % 4 == 0:
                try:
                    n = ptc_sweep(cf, limit=args.ptc_max)
                    if n:
                        log(f"  PTC +{n} iklan")
                except Exception as e:
                    log(f"  PTC error: {e}")

            # --- CAST → tunggu nibble → HOOK ---
            r = cast(cf, coin)
            if r is None:
                time.sleep(jitter(2.0, 0.6))
                continue
            token = r.get("token") or ""
            delay = float(r.get("delay") or 12)
            # buffer manusiawi: jangan hook sebelum bite, jangan telat > ~2s
            wait = delay + random.uniform(0.6, 1.6)
            log(f"  cast ok — nibble ~{delay:.0f}s, hook dalam {wait:.1f}s…")
            # poll chest tiap ~4s selama menunggu (jendela claim ±30s)
            end = time.time() + wait
            while time.time() < end:
                chunk = min(4.0, end - time.time())
                if chunk <= 0:
                    break
                time.sleep(chunk)
                since_chest_try += 1
                if since_chest_try >= 1:  # setiap chunk
                    try:
                        claim_chest(cf)
                    except Exception:
                        pass

            h = hook(cf, coin, token)
            tracker.casts += 1
            since_status += 0  # sudah diincrement di atas

            if h.get("escaped"):
                log(f"  ikan lepas ({h.get('error', '')})")
            elif h.get("success"):
                if h.get("type") == "trash":
                    log(f"  sampah: {h.get('name')}")
                else:
                    tracker.hits += 1
                    log(
                        f"  ⭐ KRIPTO +{h.get('amount')} "
                        f"{h.get('name') or h.get('currency')}  "
                        f"(hit {tracker.hits}/{tracker.casts})"
                    )
            elif h.get("error"):
                log(f"  hook error: {h.get('error')}")
            else:
                log(f"  hook aneh: {h}")

            # cadangan: refresh exp dari state tiap 12 cast (deteksi level-up cepat)
            if tracker.casts % 12 == 0:
                st = get_state(cf)
                if st.get("success"):
                    nl = int(st.get("level") or level)
                    ne = int(st.get("exp") or exp)
                    if nl != level or ne != exp:
                        old = level
                        level, exp = nl, ne
                        tracker.note_state(level, exp)
                        if level > old:
                            log(f"🎉 NAIK LEVEL! lv{old} → lv{level}  exp={exp}")
                            log(f"# {tracker.status_line(level, exp)}")
                        elif ne != exp:
                            log(f"# exp {exp} → {ne} (lv{level})")

            if args.once:
                log("--once selesai.")
                log(f"# {tracker.status_line(level, exp)}")
                break

            # jeda antar cast: cukup buat cooldown server, jangan lama-lama
            time.sleep(jitter(args.between_casts, 0.35))

    except KeyboardInterrupt:
        log("Dihentikan user (Ctrl+C).")
    finally:
        log(f"# FINAL {tracker.status_line(level, exp)}")
        if wd_session:
            log(f"# WD session total ≈${wd_session:.5f}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="CryptoFisher LEVEL RUSH (exp/jam max)")
    ap.add_argument("--once", action="store_true", help="satu cast lalu keluar (tes)")
    ap.add_argument("--coin", help="koin mancing (default: config, biasanya BTC)")
    ap.add_argument("--session", help="PHPSESSID override")
    ap.add_argument("--ptc", action="store_true", help="sweep PTC tiap 4 cast (default off)")
    ap.add_argument("--ptc-max", type=int, default=5, help="maks iklan per sweep PTC")
    ap.add_argument("--market", action="store_true", help="market sweep (default off)")
    ap.add_argument("--no-wd", dest="auto_wd", action="store_false", default=True)
    ap.add_argument("--wd-every", type=int, default=40, help="cek WD tiap N cast")
    ap.add_argument(
        "--between-casts",
        type=float,
        default=0.9,
        help="jeda dasar setelah hook sebelum cast berikutnya (detik)",
    )
    args = ap.parse_args()

    try:
        os_chmod = __import__("os").chmod
        os_chmod(__file__, 0o600)
    except OSError:
        pass

    return run(args)


if __name__ == "__main__":
    sys.exit(main())
