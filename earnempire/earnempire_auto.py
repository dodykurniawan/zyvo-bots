#!/usr/bin/env python3
"""earnempire_auto.py — bot premium EarnEmpire (auto-all, fokus UPGRADE + auto-WD).

Situs: https://earnempire.net/  (PHP session, JSON game API)
Fokus siklus: build → upgrade → refill → collect → quest → alokasi daya →
jual gem (market) → cek WD FaucetPay.

Usage:
  python3 earnempire_auto.py --once        # satu siklus penuh
  python3 earnempire_auto.py               # loop (interval config)
  python3 earnempire_auto.py --login       # paksa login ulang
  python3 earnempire_auto.py --status      # ringkasan state + saldo
  python3 earnempire_auto.py --verify 123456   # lengkapi WD (kode OTP email)

Config: config.json di folder ini (email/password/wd/interval).
State : state.json (cookie sesi, pending verify, statistik).
Password HANYA di config.json — jangan salin ke file lain.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from typing import Any, Optional

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
CFG_FILE = os.path.join(HERE, "config.json")
STATE_FILE = os.path.join(HERE, "state.json")
LOG_FILE = os.path.join(HERE, "bot.log")

BASE = "https://earnempire.net"
API = f"{BASE}/game/api/actions"
UA = ("Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")

# Urutan build (dibaca type_id dari state.catalog lewat kode — jangan hardcode).
BUILD_ORDER = [
    "sawmill", "farm",
    "gold_mine", "crystal_mine", "ruby_mine", "emerald_mine",
    "market", "warehouse",
    "barracks_infantry", "research_lab", "camp", "expedition_hall",
    "barracks_archer", "barracks_cavalry",
]
# Prioritas upgrade (fokus user): inti dulu, lalu penghasil, lalu sisanya.
# Barracks/camp/expedition di depan — gold murah (20–130) → power besar,
# power = share pool crystal (jalur WD).
UPGRADE_ORDER = [
    "town_hall", "barracks_infantry", "barracks_archer", "barracks_cavalry",
    "expedition_hall", "camp",
    "gold_mine", "crystal_mine", "ruby_mine", "emerald_mine",
    "sawmill", "farm", "warehouse", "market", "research_lab",
]
GEMS = ("crystal", "ruby", "emerald")


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_json(path: str, default: Any = None) -> Any:
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def save_json(path: str, data: Any) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, path)


def pace(lo: float = 2.0, hi: float = 5.0) -> None:
    time.sleep(random.uniform(lo, hi))


class EE:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": UA,
            "Accept": "application/json, text/html, */*",
            "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
        })
        st = load_json(STATE_FILE, {})
        if st.get("cookies"):
            self.s.cookies.update(st["cookies"])
        self.csrf = st.get("csrf", "")

    # ---------------------------------------------------------- auth ---
    def login(self, force: bool = False) -> dict:
        if not force and self.csrf and self.session_ok():
            return {"success": True, "cached": True}
        self.s.cookies.clear()
        r = self.s.get(f"{BASE}/signin", timeout=30)
        m = re.search(r'name="csrf_token" value="([^"]+)"', r.text)
        if not m:
            raise RuntimeError("csrf_token tidak ditemukan di /signin")
        self.csrf = m.group(1)
        pace(1.0, 2.0)
        r = self.s.post(
            f"{BASE}/includes/ajax/signin.php",
            data={"csrf_token": self.csrf,
                  "username_email": self.cfg["email"],
                  "password": self.cfg["password"]},
            headers={"X-Requested-With": "XMLHttpRequest"},
            timeout=30)
        try:
            j = r.json()
        except Exception:
            raise RuntimeError(f"login respons bukan JSON: {r.text[:200]}")
        if not j.get("success"):
            raise RuntimeError(f"login gagal: {j.get('message') or j}")
        self._persist()
        log(f"login OK: {j.get('user', {}).get('username')} "
            f"(id={j.get('user', {}).get('id')})")
        return j

    def session_ok(self) -> bool:
        try:
            j = self.api("state")
            return bool(j.get("ok"))
        except Exception:
            return False

    def _persist(self) -> None:
        st = load_json(STATE_FILE, {})
        st["cookies"] = {c.name: c.value for c in self.s.cookies}
        st["csrf"] = self.csrf
        save_json(STATE_FILE, st)

    # ------------------------------------------------------ game API ---
    def api(self, action: str, body: Optional[dict] = None,
            method: str = "POST") -> dict:
        url = f"{API}/{action}.php"
        for attempt in range(3):
            try:
                if method == "GET":
                    r = self.s.get(url, timeout=30)
                else:
                    r = self.s.post(url, json=body or {},
                                    headers={"Content-Type":
                                             "application/json"},
                                    timeout=30)
            except requests.RequestException as e:
                if attempt == 2:
                    raise
                log(f"  net error {action}: {e} → retry")
                time.sleep(4 + attempt * 4)
                continue
            if r.status_code == 401:
                log("  sesi mati (401) → relogin")
                self.login(force=True)
                continue
            try:
                j = r.json()
            except Exception:
                raise RuntimeError(
                    f"{action}: respons bukan JSON "
                    f"(HTTP {r.status_code}): {r.text[:160]}")
            if j.get("ok") is False or (not r.ok and "error" in j):
                raise RuntimeError(f"{action}: {j.get('error') or j}")
            return j
        raise RuntimeError(f"{action}: gagal setelah retry")

    # ------------------------------------------------------- helpers ---
    @staticmethod
    def occupied(state: dict) -> set:
        return {(b.get("grid_x"), b.get("grid_z"))
                for b in state.get("buildings", [])}

    @staticmethod
    def by_code(state: dict) -> dict:
        return {b.get("code"): b for b in state.get("buildings", [])}

    @staticmethod
    def catalog(state: dict) -> dict:
        return {c.get("code"): c for c in state.get("catalog", [])}

    @staticmethod
    def affordable(cost: Any, res: dict) -> bool:
        if not cost:
            return True
        if isinstance(cost, list):
            return all(affordable(c, res) for c in cost)
        return all(int(res.get(k) or 0) >= int(v) for k, v in cost.items())

    # ------------------------------------------------------- actions ---
    def build_pass(self, state: dict) -> int:
        cat = self.catalog(state)
        owned = self.by_code(state)
        built = 0
        for code in BUILD_ORDER:
            meta = cat.get(code)
            if not meta:
                continue
            have = sum(1 for b in state.get("buildings", [])
                       if b.get("code") == code)
            # bangunan non-unik: bangun terus sampai max_count saat murah
            if have >= int(meta.get("max_count") or 1):
                continue
            if have and code in ("sawmill", "farm"):
                # cukup 1 dulu tiap tipe; sisa nyusul kalau sisa wood/food besar
                if int((state.get("user", {}).get("resources") or {})
                       .get("wood") or 0) < 20000:
                    continue
            if not self.affordable(meta.get("cost"), 
                                  state.get("user", {}).get("resources") or {}):
                continue
            # coba beberapa kandidat slot — server bisa menolak jarak
            tried: set = set()
            built_this = False
            rejected_all = False
            for _try in range(12):
                slot = self._find_slot(state, exclude=tried)
                if not slot:
                    rejected_all = True
                    break
                gx, gz = slot
                tried.add((gx, gz))
                pace()
                try:
                    j = self.api("build_building",
                                 {"type_id": meta["type_id"],
                                  "grid_x": gx, "grid_z": gz})
                except RuntimeError as e:
                    msg = str(e)
                    if any(k in msg for k in ("Terlalu dekat", "Sudah ada",
                                              "di sini")):
                        continue  # slot jelek → kandidat berikut
                    log(f"  build {code}: {msg}")
                    break
                log(f"  BUILD {code} @({gx},{gz}) OK")
                built += 1
                built_this = True
                state = j  # respons berisi state segar
                pace()
                break
            if not built_this and rejected_all:
                log(f"  build {code}: slot grid habis")
            elif not built_this and len(tried) >= 12:
                log(f"  build {code}: 12 slot ditolak server")
        return built

    @staticmethod
    def _find_slot(state: dict, exclude: Optional[set] = None) -> Optional[tuple]:
        """Cari slot bebas dengan jarak Chebyshev ≥ 2 dari semua okupansi
        (aturan server — teruji: (-1,-1) ditolak, (-1,-3) lolos)."""
        occ = EE.occupied(state)
        if exclude:
            occ = occ | set(exclude)
        cands = []
        for x in range(-5, 6):
            for z in range(-5, 6):
                if (x, z) in occ:
                    continue
                # jarak Chebyshev minimum ke okupansi terdekat
                d = min(max(abs(x - ox), abs(z - oz)) for ox, oz in occ) \
                    if occ else 99
                if d < 2:
                    continue
                cands.append((abs(x) + abs(z), d, x, z))
        # dekat pusat dulu, lalu clearance lega
        cands.sort(key=lambda t: (-t[1], t[0]))
        return (cands[0][2], cands[0][3]) if cands else None

    def upgrade_pass(self, state: dict) -> int:
        """Satu percobaan upgrade per cycle. town_hall DULU — semua bangunan
        lain `town_hall_blocked` sampai balai kota naik level."""
        res = state.get("user", {}).get("resources") or {}
        owned = self.by_code(state)
        up = 0
        blocked_th = 0
        for code in UPGRADE_ORDER:
            b = owned.get(code)
            if not b:
                continue
            if b.get("upgrade_remaining") is not None:
                continue  # masih proses
            if b.get("town_hall_blocked"):
                blocked_th += 1
                continue
            if int(b.get("level") or 0) >= int(b.get("max_level") or 0):
                continue
            cost = b.get("upgrade_cost")
            if not cost:
                continue
            if not self.affordable(cost, res):
                if code == "town_hall":
                    log(f"  town_hall butuh {cost} (ada {res})")
                continue
            pace()
            try:
                j = self.api("upgrade_building", {"building_id": b["id"]})
            except RuntimeError as e:
                log(f"  upgrade {code} lv{b.get('level')}: {e}")
                if any(k in str(e).lower() for k in
                       ("cukup", "sufficient", "cost", "biaya", "butuh")):
                    break
                continue
            log(f"  UPGRADE {code} → lv{(b.get('level') or 0) + 1} OK")
            up += 1
            state = j
            res = state.get("user", {}).get("resources") or {}
            owned = self.by_code(state)
            pace()
        if up == 0 and blocked_th and not owned.get("town_hall", {}).get(
                "upgrade_remaining"):
            pass  # sudah dilog via town_hall butuh …
        return up

    def quests_pass(self, state: dict) -> int:
        n = 0
        for q in state.get("quests", []):
            if q.get("claimable") and not q.get("claimed"):
                pace()
                try:
                    self.api("claim_quest", {"quest": q["code"]})
                    rw = q.get("reward") or {}
                    log(f"  QUEST {q['code']} claimed {rw}")
                    n += 1
                except RuntimeError as e:
                    log(f"  quest {q['code']}: {e}")
        return n

    def research_pass(self, state: dict) -> int:
        """Mulai riset pertama yang available & muat biaya; skip kalau lab sibuk."""
        techs = state.get("research") or []
        res = state.get("user", {}).get("resources") or {}
        for t in techs:
            if t.get("remaining") and int(t.get("remaining") or 0) > 0:
                return 0  # masih jalan
            if t.get("busy"):
                return 0
            if int(t.get("level") or 0) >= int(t.get("max_level") or 0):
                continue
            if t.get("requires_done") is False:
                continue
            if t.get("lab_blocked"):
                continue
            cost = t.get("cost") or {}
            if not self.affordable(cost, res):
                continue
            pace()
            try:
                j = self.api("research_upgrade", {"tech_id": t["tech_id"]})
            except RuntimeError as e:
                log(f"  research {t.get('code')}: {e}")
                continue
            log(f"  RESEARCH {t.get('code')} mulai "
                f"({t.get('research_time')}s) OK")
            return 1
        return 0

    def energy_collect(self) -> None:
        pace()
        try:
            self.api("refill_all", {})
        except RuntimeError as e:
            log(f"  refill_all: {e}")
        pace()
        try:
            self.api("collect_all", {"scope": "all", "resource": ""})
        except RuntimeError as e:
            log(f"  collect_all: {e}")

    def allocation_pass(self, state: dict) -> None:
        """Pool butuh ≥800 daya di SATU koin — split rata = dapat nol.
        Konsentrasikan SELURUH daya ke koin target (config `wd.pool_coin`,
        default crystal = harga jual terbaik)."""
        u = state.get("user", {}) or {}
        power = int(u.get("power") or 0)
        if power <= 0:
            return
        mines = [b for b in state.get("buildings", [])
                 if b.get("category") == "mine"]
        if not mines:
            return
        # pilih koin: yang sudah punya mine + preferensi config
        want = ((self.cfg.get("wd") or {}).get("pool_coin") or "crystal")
        have = {m.get("resource") for m in mines if m.get("resource")}
        if want not in have:
            want = next(iter(have)) if have else None
        if not want:
            return
        cur = u.get("power_split") or {}
        # sudah 100% di target & total pas → skip
        if (int(cur.get(want) or 0) >= power and
                sum(int(v or 0) for v in cur.values()) <= power):
            return
        body = {"mode": "power"}
        for k in ("gold", "crystal", "emerald", "ruby"):
            body[k] = power if k == want else 0
        pace()
        try:
            self.api("set_allocation", body)
            log(f"  ALLOCATION {power} → semua ke {want}")
        except RuntimeError as e:
            log(f"  allocation: {e}")

    # --------------------------------------------------- youtube wall ---
    def youtube_pass(self) -> float:
        """Runner aviso.bz (widget YouTube di PTC tab youtube) → GOLD.
        Gold = bahan upgrade → power naik → pool crystal naik → WD cepat.
        Flow: widget attrs → identify → available → start → timer → complete."""
        try:
            r = self.s.get(f"{BASE}/dashboard/ptc?tab=youtube", timeout=30)
            wm = re.search(r'<div class="ee-av__widget"[^>]*>', r.text)
            if not wm:
                return 0.0
            attrs = dict(re.findall(r'data-([a-z-]+)="([^"]*)"', wm.group(0)))
            api = attrs.get("api-endpoint") or "https://aviso.bz/api/v1"
            key = attrs.get("api-key") or ""
            hsh = (attrs.get("user-hash") or "").lower()
            uid = attrs.get("user-id") or ""
            sig = attrs.get("user-sig") or ""
            if not (key and hsh and uid and sig):
                return 0.0
        except Exception as e:
            log(f"  yt widget: {e}")
            return 0.0

        plat = "Linux aarch64"
        H = {"X-API-Key": key, "Accept-Language": "en",
             "Content-Type": "application/json", "User-Agent": UA}
        earned = 0.0
        try:
            self.s.post(f"{api}/youtube/tasks/identify", json={
                "hash": hsh, "ip": None, "userAgent": UA,
                "fingerprint": None}, headers=H, timeout=20)
        except Exception as e:
            log(f"  yt identify: {e}")
            return 0.0

        for typ in ("ads", "like", "sub"):
            try:
                rr = self.s.get(
                    f"{api}/youtube/tasks/available",
                    params={"hash": hsh, "type": typ, "platform": plat},
                    headers=H, timeout=20)
                tasks = (rr.json().get(typ) or [])
            except Exception as e:
                log(f"  yt available {typ}: {e}")
                continue
            if not tasks:
                continue
            log(f"  YT {typ}: {len(tasks)} task")
            for task in tasks[:12]:  # batas per cycle — pacing
                body = {"taskId": task["id"], "hash": hsh, "type": typ,
                        "platform": plat, "userId": int(uid), "userSig": sig}
                try:
                    rr = self.s.post(f"{api}/youtube/tasks/start",
                                     json=body, headers=H, timeout=20)
                    st = rr.json()
                    attempt = st.get("attemptId")
                    if not attempt:
                        log(f"  yt {typ} start: "
                            f"{(st.get('error') or rr.text)[:100]}")
                        continue
                    dur = int(task.get("duration") or 5) or 3
                    pace(1.0, 2.0)
                    self.s.post(f"{api}/youtube/tasks/timer-status",
                                json={"attemptId": attempt,
                                      "action": "start", "watchedTime": 0},
                                headers=H, timeout=15)
                    time.sleep(dur + 0.8)
                    self.s.post(f"{api}/youtube/tasks/timer-status",
                                json={"attemptId": attempt,
                                      "watchedTime": dur},
                                headers=H, timeout=15)
                    rr = self.s.post(f"{api}/youtube/tasks/complete",
                                     json={"attemptId": attempt},
                                     headers=H, timeout=20)
                    j = rr.json()
                    if j.get("earned") is not None:
                        got = float(j["earned"])
                        earned += got
                        log(f"  YT {typ} +{got} "
                            f"{j.get('currencySymbol') or ''}")
                    elif j.get("code") == "subscribe_check_retry":
                        time.sleep(6)
                        rr = self.s.post(
                            f"{api}/youtube/tasks/complete",
                            json={"attemptId": attempt},
                            headers=H, timeout=20)
                        j = rr.json()
                        if j.get("earned") is not None:
                            earned += float(j["earned"])
                            log(f"  YT {typ} (retry) +{j['earned']}")
                    else:
                        log(f"  yt {typ} complete: "
                            f"{(j.get('error') or j)[:100]}")
                    time.sleep(1.5)
                except Exception as e:
                    log(f"  yt {typ} task: {e}")
                    time.sleep(2)
        return earned

    def market_pass(self, state: dict) -> int:
        """Jual semua gem kalau nilainya ≥ min jual ($0.01) → saldo USD."""
        m = state.get("market") or {}
        if not m.get("open"):
            return 0
        min_usd = float(m.get("min_sell_usd") or 0.01)
        res = state.get("user", {}).get("resources") or {}
        prices = m.get("prices") or {}
        sold = 0
        for gem in GEMS:
            stock = int(res.get(gem) or 0)
            price = float((prices.get(gem) or {}).get("price") or 0)
            if stock <= 0 or price <= 0:
                continue
            if stock * price < min_usd:
                continue  # kumpulkan dulu sampai tembus min
            pace()
            try:
                j = self.api("market_sell", {"resource": gem, "amount": stock})
            except RuntimeError as e:
                log(f"  sell {gem}: {e}")
                continue
            usd = (j.get("market") or {}).get("usd")
            msg = (j.get("market_sale") or {}).get("message")
            log(f"  SELL {gem} ×{stock} → USD {usd} ({msg or 'ok'})")
            sold += 1
            state = j
        return sold

    # ------------------------------------------------------- withdraw ---
    def wd_page(self) -> dict:
        r = self.s.get(f"{BASE}/dashboard/withdraw", timeout=30)
        if r.status_code == 401 or "signin" in r.url:
            self.login(force=True)
            r = self.s.get(f"{BASE}/dashboard/withdraw", timeout=30)
        cfgm = re.search(r"window\.bcWithdrawConfig\s*=\s*(\{.*?\});",
                         r.text, re.S)
        cfg = json.loads(cfgm.group(1)) if cfgm else {}
        methods = []
        for m in re.finditer(
                r'<input[^>]*name="method_id"[^>]*value="(\d+)"[^>]*'
                r'data-min="(\d+)"[^>]*data-label="([^"]*)"', r.text):
            methods.append({"id": int(m.group(1)), "min": int(m.group(2)),
                            "label": m.group(3)})
        if not methods:  # urutan atribut bisa beda
            for m in re.finditer(
                    r'<input[^>]*name="method_id"[^>]*value="(\d+)"[^>]*>',
                    r.text):
                seg = r.text[m.start():m.start() + 600]
                min_m = re.search(r'data-min="(\d+)"', seg)
                lab_m = re.search(r'data-label="([^"]*)"', seg)
                methods.append({"id": int(m.group(1)),
                                "min": int(min_m.group(1)) if min_m else 0,
                                "label": lab_m.group(1) if lab_m else "?"})
        return {"config": cfg, "methods": methods, "html": r.text}

    def wd_submit(self, method_id: int, details: str, points: int,
                  verify_code: str = "") -> dict:
        data = {"method_id": str(method_id), "payout_details": details,
                "points_amount": str(points)}
        if verify_code:
            data["verify_code"] = verify_code
        pace(2.0, 4.0)
        r = self.s.post(
            f"{BASE}/includes/ajax/withdraw/submit.php", data=data,
            headers={"X-Requested-With": "XMLHttpRequest"},
            timeout=30)
        try:
            return r.json()
        except Exception:
            return {"success": False, "message": r.text[:200]}

    def wd_pass(self, state: dict) -> None:
        st = load_json(STATE_FILE, {})
        if st.get("pending_verify"):
            log("  WD: menunggu kode OTP (jalankan --verify <kode>) — lewati")
            return
        wd_cfg = self.cfg.get("wd") or {}
        if not wd_cfg.get("enabled", True):
            return
        page = self.wd_page()
        avail = int((page["config"] or {}).get("availablePoints") or 0)
        rate = int((page["config"] or {}).get("pointsPerDollar") or 10000)
        fp = next((m for m in page["methods"]
                   if "faucetpay" in (m.get("label") or "").lower()), None)
        if not fp:
            log("  WD: method FaucetPay tak ditemukan di halaman")
            return
        min_pts = max(int(wd_cfg.get("min_points") or 0), int(fp["min"]))
        log(f"  WD saldо {avail} poin (${avail / rate:.4f}) "
            f"min {min_pts} (${min_pts / rate:.2f})")
        if avail < min_pts:
            return
        details = wd_cfg.get("payout_details") or self.cfg["email"]
        resp = self.wd_submit(fp["id"], details, avail)
        if resp.get("success") and resp.get("require_verify"):
            st = load_json(STATE_FILE, {})
            st["pending_verify"] = {
                "method_id": fp["id"], "payout_details": details,
                "points_amount": avail, "ts": int(time.time()),
                "message": resp.get("message"),
            }
            save_json(STATE_FILE, st)
            log(f"  WD BUTUH KODE EMAIL: {resp.get('message')} "
                f"→ jalankan: python3 {os.path.basename(__file__)} "
                f"--verify <6 digit>")
            try:
                os.system(f"termux-notification --title 'EarnEmpire WD' "
                          f"--content 'Butuh kode OTP email: "
                          f"{resp.get('message', '')}' 2>/dev/null")
            except Exception:
                pass
            return
        if resp.get("success"):
            st = load_json(STATE_FILE, st)
            st["wd_last"] = {"points": avail, "ts": int(time.time()),
                             "resp": resp}
            save_json(STATE_FILE, st)
            log(f"  *** WD OK: {avail} poin → {details} "
                f"({resp.get('message') or 'diterima'}) ***")
            return
        log(f"  WD gagal: {resp.get('message') or resp}")

    def wd_verify(self, code: str) -> None:
        st = load_json(STATE_FILE, {})
        pv = st.get("pending_verify")
        if not pv:
            log("tidak ada WD pending — tak perlu kode")
            return
        if time.time() - int(pv.get("ts") or 0) > 900:
            log("kode kedaluwarsa (>15 mnt) — submit ulang saja "
                "(jalankan cycle lagi)")
            st.pop("pending_verify", None)
            save_json(STATE_FILE, st)
            return
        resp = self.wd_submit(pv["method_id"], pv["payout_details"],
                              pv["points_amount"], verify_code=code)
        if resp.get("success"):
            st.pop("pending_verify", None)
            st["wd_last"] = {"points": pv["points_amount"],
                             "ts": int(time.time()), "resp": resp}
            save_json(STATE_FILE, st)
            log(f"  *** WD VERIFIED OK: {pv['points_amount']} poin "
                f"→ {pv['payout_details']} ({resp.get('message')}) ***")
        else:
            log(f"  verifikasi gagal: {resp.get('message') or resp}")

    # --------------------------------------------------------- cycle ---
    def cycle(self) -> dict:
        stats = {"built": 0, "upgraded": 0, "quests": 0, "sold": 0}
        state = self.api("state", method="GET")
        u = state.get("user", {}) or {}
        if not u.get("tutorial_done"):
            pace()
            try:
                self.api("tutorial_done", {})
                log("  tutorial_done")
            except RuntimeError as e:
                log(f"  tutorial_done: {e}")
            state = self.api("state", method="GET")

        stats["built"] = self.build_pass(state)
        state = self.api("state", method="GET")
        stats.setdefault("yt_gold", 0.0)
        stats["yt_gold"] = self.youtube_pass()  # gold dulu → upgrade cycle ini
        state = self.api("state", method="GET")
        stats["upgraded"] = self.upgrade_pass(state)
        state = self.api("state", method="GET")
        self.energy_collect()
        state = self.api("state", method="GET")
        stats["quests"] = self.quests_pass(state)
        state = self.api("state", method="GET")
        stats.setdefault("research", 0)
        stats["research"] = self.research_pass(state)
        state = self.api("state", method="GET")
        self.allocation_pass(state)
        state = self.api("state", method="GET")
        stats["sold"] = self.market_pass(state)
        state = self.api("state", method="GET")

        u = state.get("user", {}) or {}
        res = u.get("resources") or {}
        m = state.get("market") or {}
        bset = {b["code"]: b.get("level")
                for b in state.get("buildings", [])}
        log(f"STATE gold={res.get('gold')} wood={res.get('wood')} "
            f"food={res.get('food')} crystal={res.get('crystal')} "
            f"ruby={res.get('ruby')} emerald={res.get('emerald')} "
            f"USD={m.get('usd')} power={u.get('power')} "
            f"yt+{stats.get('yt_gold') or 0} "
            f"| bangunan: " +
            ", ".join(f"{k}v{v}" for k, v in sorted(bset.items())))

        self.wd_pass(state)
        self._persist()
        return stats


def cmd_status() -> None:
    ee = EE(load_json(CFG_FILE))
    if not ee.csrf and not ee.login():
        return
    st = ee.api("state", method="GET")
    u = st.get("user", {}) or {}
    res = u.get("resources") or {}
    m = st.get("market") or {}
    print(json.dumps({
        "user": u.get("name"), "level": u.get("level"),
        "power": u.get("power"), "resources": res,
        "market_usd": m.get("usd"),
        "buildings": [(b["code"], b.get("level"),
                       b.get("upgrade_remaining"))
                      for b in st.get("buildings", [])],
        "quests_claimable": [q["code"] for q in st.get("quests", [])
                             if q.get("claimable")],
    }, ensure_ascii=False, indent=1))


def main() -> int:
    ap = argparse.ArgumentParser(description="EarnEmpire auto upgrade + WD")
    ap.add_argument("--once", action="store_true", help="satu siklus")
    ap.add_argument("--login", action="store_true", help="paksa login")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--verify", metavar="KODE",
                    help="kode OTP email utk WD pending")
    ap.add_argument("--interval", type=int, default=0,
                    help="detik antar cycle (default dari config)")
    args = ap.parse_args()

    cfg = load_json(CFG_FILE)
    if not cfg.get("email") or not cfg.get("password"):
        log(f"config.json belum lengkap: {CFG_FILE}")
        return 1
    cfg.setdefault("interval", 300)
    cfg.setdefault("wd", {"enabled": True, "min_points": 500,
                          "payout_details": cfg.get("email", "")})

    ee = EE(cfg)
    if args.verify:
        ee.wd_verify(args.verify)
        return 0
    if args.status:
        cmd_status()
        return 0
    if args.login:
        ee.login(force=True)
        if not args.once:
            return 0
        print("--once lanjut…")
    try:
        if not ee.login():
            return 1
    except RuntimeError as e:
        log(f"login gagal: {e}")
        return 1

    if args.once:
        ee.cycle()
        return 0

    interval = int(args.interval or cfg.get("interval") or 300)
    log(f"loop mulai (interval {interval}s)")
    while True:
        t0 = time.time()
        try:
            ee.cycle()
        except RuntimeError as e:
            log(f"cycle error: {e}")
            if "login" in str(e).lower() or "csrf" in str(e).lower():
                try:
                    ee.login(force=True)
                except Exception as e2:
                    log(f"relogin gagal: {e2}")
        except Exception as e:
            log(f"cycle CRASH: {type(e).__name__}: {e}")
        left = interval - (time.time() - t0)
        if left > 0:
            time.sleep(left)


if __name__ == "__main__":
    sys.exit(main())
