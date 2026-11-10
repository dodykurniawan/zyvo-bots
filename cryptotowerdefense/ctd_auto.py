#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ctd_auto.py — Auto untuk CryptoTowerDefense.com (murni Python requests).

Tanpa playwright, tanpa selenium. Login & captcha Turnstile diselesaikan lewat
API solver xsolve yang SUDAH ADA di setup ini (key di lm_config.json).

Alur yang diotomatiskan:
    1. Login otomatis  : challenge Turnstile -> xsolve -> /api/account/login
                         (cookie disimpan ke ctd_cookie.txt, dipakai ulang)
    2. Jendela verifikasi (security window) diperpanjang otomatis lewat
       /api/security/verify + xsolve kalau sudah habis
    3. Auto faucet     : quick (5 coins/5 menit) + reguler (50 coins/4 jam),
                         lengkap dengan proof Turnstile yang dituntut server
    4. Auto beli chest : Supply Chest (50 coins -> mahal, 500) dibeli kalau
                         koin mencukupi (matikan: auto_buy_chests = False)
    5. Auto withdraw   : begitu ada hadiah pool SUDAH settle >= minimum,
                         langsung tarik ke FaucetPay (withdraw_available > 0)
    6. Loop jalan terus (Ctrl+C untuk berhenti)

CATATAN JUJUR soal "auto all":
    Permainan (run Daily/Weekly) divalidasi server dengan REPLAY engine
    mereka sendiri (game-engine.js). Bagian itu butuh bot yang menjalankan
    engine identik — masih tahap berikutnya (lihat TASK.md). Faucet/chest/
    withdraw/loop sudah otomatis penuh di script ini.
"""

import argparse
import json
import os
import random
import subprocess
import sys
import time
import uuid
from datetime import datetime

import requests

# ============================ KONFIGURASI ============================
def _secret(fname: str, env: str, default: str = "") -> str:
    """Ambil rahasia: env dulu (GitHub Actions), lalu file lokal (Termux)."""
    v = os.environ.get(env, "").strip()
    if v:
        return v
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               fname), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return default


CONFIG = {
    "email": _secret("ctd_email.txt", "CTD_EMAIL"),
    "password": _secret("ctd_secret.txt", "CTD_PASSWORD"),

    # Solver Turnstile — key dibaca dari lm_config.json / env
    # Path RELATIVE: satu folder dengan ../lightningminer (Termux & GitHub)
    "xsolve_key_file": os.environ.get("LM_CONFIG_PATH") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "lightningminer", "lm_config.json"),
    "xsolve_key_env": "XSOlVE_KEY",

    # --- Withdraw FaucetPay (hadiah pool yang SUDAH settle) ---
    "auto_withdraw": True,
    "withdraw_recipient": "dodykurniaw4n@gmail.com",  # email FaucetPay user
    "withdraw_currency": "USDT",
    "withdraw_min_usdmicros": 1,      # minimum server = $0.000001

    # --- Chest ---
    "auto_buy_chests": True,          # beli Supply Chest (500 coins) saat koin cukup

    # --- Tower permanen (PRIORITAS di atas chest: +12% dmg/level, murah) ---
    # Server settle sendiri nyaranin: "Upgrade your permanent tower levels".
    "auto_upgrade_towers": True,
    "battle_tower_types": ["arc", "pulse"],  # tipe yang dipakai AI run bot

    # --- Loop ---
    "poll_seconds": 60,
    "xsolve_cost_note": "1 kredit xsolve per solve; faucet claim = 1 solve",

    "request_timeout": 25,
    "site": "https://cryptotowerdefense.com",
    "signin_url": "https://cryptotowerdefense.com/signin",
}

UA = ("Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")
HERE = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(HERE, "ctd_cookie.txt")


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def load_xsolve_key() -> str:
    k = os.environ.get("XSOlVE_KEY") or os.environ.get("XSOLVE_KEY") or ""
    if not k:
        try:
            k = json.load(open(CONFIG["xsolve_key_file"])).get("xsolve_key", "")
        except Exception:
            k = ""
    return k.strip()


class Xsolve:
    """Solve Turnstile lewat xsolve.me (sudah terbukti di bot LightningMiner)."""
    TASK = "https://api.xsolve.me/task"
    RESULT = "https://api.xsolve.me/getTaskResult"

    def __init__(self, key):
        self.key = key

    def solve(self, sitekey, url, action=None, cdata=None) -> str:
        # xsolve kadang balas token langsung, kadang 600010 — retry 1x dulu
        try:
            return self._xsolve(sitekey, url, action, cdata)
        except Exception as e:
            log(f"xsolve gagal ({e}) → retry 1x")
            try:
                time.sleep(2)
                return self._xsolve(sitekey, url, action, cdata)
            except Exception as e2:
                log(f"xsolve retry gagal ({e2}) → fallback peak")
                return self._peak(sitekey, url, action, cdata)

    def _peak(self, sitekey, url, action=None, cdata=None) -> str:
        """Peak fallback (2026-11-09): xsolve rusak global, peak sehat."""
        try:
            key = json.load(open(CONFIG["xsolve_key_file"])).get("peak_key", "")
        except Exception:
            key = ""
        if not key:
            raise RuntimeError("peak key tidak ditemukan di lm_config.json")
        body = {"task_type": "turnstiletaskproxyless", "url": url, "sitekey": sitekey}
        if action:
            body["action"] = action
        if cdata:
            body["cdata"] = cdata
        r = requests.post("https://api.peak.fo/solve",
                          headers={"X-API-Key": key}, json=body, timeout=60).json()
        tok = ((r.get("data") or {}).get("token")) or ""
        if not tok:
            raise RuntimeError(f"peak gagal: {str(r.get('error'))[:160]}")
        return tok

    def _xsolve(self, sitekey, url, action=None, cdata=None) -> str:
        if not self.key:
            raise RuntimeError("xsolve key tidak ditemukan (lm_config.json / env)")
        body = {"mode": "turnstile", "url": url, "sitekey": sitekey}
        if action:
            body["action"] = action
        if cdata:
            body["cdata"] = cdata
        r = requests.post(self.TASK, headers={"X-Api-Key": self.key},
                          json=body, timeout=90)
        j = r.json()
        tok = j.get("token") or ""
        if tok and str(j.get("status", "completed")) in ("completed", "ready", "success"):
            return tok
        tid = j.get("taskId") or j.get("task_id")
        if not tid:
            raise RuntimeError(f"xsolve gagal: {str(j)[:200]}")
        t0 = time.time()
        while time.time() - t0 < 90:
            time.sleep(3)
            p = requests.post(self.RESULT,
                              json={"clientKey": self.key, "taskId": tid},
                              timeout=40).json()
            if p.get("status") in ("ready", "success", "completed"):
                sol = p.get("solution") or {}
                tok = sol.get("token") or sol.get("value") or ""
                if tok:
                    return tok
                raise RuntimeError(f"xsolve ready tanpa token: {p}")
            if p.get("errorId") or p.get("errorCode") or p.get("error"):
                raise RuntimeError(f"xsolve result: {p}")
        raise RuntimeError("xsolve: timeout polling")


class CTD:
    def __init__(self, cfg, cookie=None):
        self.cfg = cfg
        self.base = cfg["site"]
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": UA,
            "Origin": self.base,
            "Referer": self.base + "/",
            "x-ctd-client-version": "0.19.0",
        })
        self.csrf = None
        if cookie:
            # tempel mentah sebagai header Cookie (aman untuk __Host-* prefix)
            self.s.headers["Cookie"] = cookie
        self.solver = Xsolve(load_xsolve_key())

    def _save_cookie(self):
        # bangun ulang string cookie dari jar hasil login
        parts = [f"{c.name}={c.value}" for c in self.s.cookies]
        raw = "; ".join(parts)
        self.s.headers["Cookie"] = raw
        try:
            with open(COOKIE_FILE, "w") as f:
                f.write(raw)
            os.chmod(COOKIE_FILE, 0o600)
        except OSError:
            pass

    # ---------------- HTTP ----------------
    def _req(self, method, path, body=None):
        url = self.base + path
        headers = {}
        if body is not None:
            headers["content-type"] = "application/json"
            if self.csrf:
                headers["x-csrf-token"] = self.csrf
        for attempt in (1, 2, 3):
            try:
                r = self.s.request(method, url,
                                   data=json.dumps(body) if body is not None else None,
                                   headers=headers,
                                   timeout=self.cfg["request_timeout"])
                try:
                    data = r.json()
                except ValueError:
                    data = {"error": f"HTTP {r.status_code} non-json"}
                if r.status_code in (429, 500, 502, 503):
                    log(f"server sibuk ({r.status_code}), tunggu {10*attempt}s")
                    time.sleep(10 * attempt)
                    continue
                if isinstance(data, dict):
                    data["_http"] = r.status_code
                return data
            except requests.RequestException as e:
                if attempt == 3:
                    return {"error": f"network: {e}"}
                time.sleep(4 * attempt)
        return {"error": "gagal 3x"}

    def get(self, path):
        return self._req("GET", path)

    def post(self, path, body=None):
        return self._req("POST", path, body if body is not None else {})

    # ---------------- Auth ----------------
    def _challenge(self, purpose):
        c = self.get(f"/api/security/challenge?purpose={purpose}")
        if not c.get("siteKey"):
            raise RuntimeError(f"challenge gagal: {c}")
        return c

    def login(self) -> bool:
        """Login penuh: challenge -> xsolve -> /api/account/login."""
        try:
            ch = self._challenge("login")
            tok = self.solver.solve(
                ch["siteKey"], self.cfg["signin_url"],
                ch.get("action") or "login",
                ch.get("cData") or ch.get("challengeId"))
            r = self.post("/api/account/login", {
                "identifier": self.cfg["email"],
                "password": self.cfg["password"],
                "challengeId": ch["challengeId"],
                "turnstileToken": tok,
            })
            if (r.get("account") or {}).get("authenticated"):
                self.csrf = r.get("csrfToken")
                self._save_cookie()
                log(f"LOGIN OK sebagai {r['account'].get('username')} "
                    f"(cookie disimpan)")
                return True
            log(f"login ditolak: {r.get('error') or r}")
            return False
        except RuntimeError as e:
            log(f"login gagal: {e}")
            return False

    def session_ok(self) -> bool:
        ident = self.get("/api/session/identity")
        ok = bool(ident.get("profileId"))
        if ok and not self.csrf:
            self.csrf = ident.get("csrfToken")
        return ok

    def bootstrap(self):
        b = self.get("/api/bootstrap")
        if b.get("csrfToken"):
            self.csrf = b["csrfToken"]
        return b

    # ---------------- Security window ----------------
    def maybe_start_run_bot(self):
        """Begitu jendela verifikasi aktif, jalankan bot run campaign (Node).

        Kunci lock O_EXCL supaya TIDAK dobel dengan ctd_probe.py — proses
        run menghapus lock-nya sendiri saat selesai (boleh diluncurkan lagi)."""
        lock = os.path.join(HERE, "ctd_run.lock")
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
        except FileExistsError:
            # Lock basi: proses run bisa mati (Android kill) tanpa sempat
            # `rm -f lock` → cek proses beneran, kalau sudah mati hapus lock.
            out_ps = subprocess.run(["ps", "-eo", "args"],
                                    capture_output=True, text=True).stdout
            if "ctd_run_bot.mjs" in out_ps:
                return  # run bot masih jalan — lock valid
            log("lock basi ditemukan (run bot sudah mati) → dihapus")
            try:
                os.unlink(lock)
            except OSError:
                return
            try:
                fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
            except FileExistsError:
                return
        out = open(os.path.join(HERE, "ctd_run.log"), "a")
        try:
            subprocess.Popen(
                ["setsid", "nohup", "bash", "-c",
                 f"node ctd_run_bot.mjs --max 6; rm -f '{lock}'"],
                cwd=HERE, stdout=out, stderr=out,
                stdin=subprocess.DEVNULL, start_new_session=True)
            log("run bot (ctd_run_bot.mjs --max 6) diluncurkan otomatis")
        except Exception as ex:
            log(f"gagal luncurkan run bot: {ex}")
            try: os.unlink(lock)
            except OSError: pass

    def ensure_window(self, purpose="play") -> bool:
        st = self.get("/api/security/status")
        try:
            until = int(st.get("verifiedUntil") or 0)
        except (TypeError, ValueError):
            until = 0
        if until > time.time() * 1000 + 60_000:
            # jendela masih aktif → pastikan run bot campaign jalan terus
            # (O_EXCL lock + cek ps mencegah dobel launch)
            self.maybe_start_run_bot()
            return True
        # verify butuh x-csrf-token — refresh dari identity kalau kosong/basi
        if not self.csrf:
            ident = self.get("/api/session/identity")
            self.csrf = ident.get("csrfToken") or self.csrf
        # perpanjang: challenge purpose=play -> xsolve -> verify
        # 3x percobaan + challenge BARU tiap putaran (600010 sering challenge-specific)
        last = ""
        for attempt in range(3):
            try:
                ch = self._challenge(purpose)
                tok = self.solver.solve(
                    ch["siteKey"], self.base + "/", ch.get("action") or purpose,
                    ch.get("cData") or ch.get("challengeId"))
                r = self.post("/api/security/verify", {
                    "purpose": purpose,
                    "challengeId": ch["challengeId"],
                    "turnstileToken": tok,
                })
                until2 = int((r.get("status") or r).get("verifiedUntil") or 0) \
                    if isinstance(r.get("status") or r, dict) else 0
                if until2 or r.get("status") == "active" or r.get("verifiedUntil"):
                    log("jendela verifikasi diperpanjang (xsolve)")
                    self.maybe_start_run_bot()
                    return True
                last = str(r)[:200]
                log(f"verify gagal (try {attempt + 1}/3): {last}")
                # CSRF → ambil token baru lalu ulang
                if "CSRF" in last.upper() or "Refresh the page" in last:
                    ident = self.get("/api/session/identity")
                    self.csrf = ident.get("csrfToken") or self.csrf
            except RuntimeError as e:
                last = str(e)
                log(f"perpanjang gagal (try {attempt + 1}/3): {e}")
            time.sleep(3 * (attempt + 1))
        log(f"jendela verifikasi GAGAL setelah 3x: {last}")
        return False

    # ---------------- Faucet ----------------
    def claim(self, kind) -> bool:
        path = f"/api/faucet/{kind}"
        # server menuntut proof turnstile pada body (lihat security-ui.js faucetProof)
        proof = {"operationId": str(uuid.uuid4())}
        try:
            ch = self._challenge("play")
            tok = self.solver.solve(
                ch["siteKey"], self.base + "/", ch.get("action") or "play",
                ch.get("cData") or ch.get("challengeId"))
            proof.update({"challengeId": ch["challengeId"], "turnstileToken": tok})
        except RuntimeError as e:
            log(f"proof {kind} gagal: {e} — coba tanpa proof")
        r = self.post(path, proof)
        if r.get("nextClaimAt"):
            nxt = datetime.fromtimestamp(r["nextClaimAt"] / 1000).strftime("%H:%M:%S")
            log(f"faucet {kind}: +{r.get('coinsAwarded')} coins "
                f"(berikutnya {nxt})")
            return True
        code = r.get("code") or ""
        if code in ("HUMAN_VERIFICATION_REQUIRED", "HUMAN_REQUIRED"):
            log(f"faucet {kind}: server minta verifikasi ulang")
            return False
        log(f"faucet {kind}: {r.get('error') or r}")
        return False

    @staticmethod
    def _due(earning, key):
        try:
            return int(earning.get(key) or 0) <= time.time() * 1000
        except (TypeError, ValueError):
            return False

    # ---------------- Chest ----------------
    def maybe_upgrade_towers(self, b) -> bool:
        """Tower permanen naik level pakai koin — +12% damage/level
        (game-engine: damage*1.12**(permanentLevel-1)). Endpoint:
        POST /api/towers/upgrade {towerType} → {level, coinsSpent,
        upgradeCost}. PRIORITAS di atas chest: murah (LV1→2 = 35 coins)
        dan langsung menguatkan tipe yang dipakai AI saat battle.
        Return True kalau ada minimal 1 upgrade sukses (caller refresh bootstrap)."""
        if not self.cfg.get("auto_upgrade_towers", True):
            return False
        player = b.get("player") or {}
        coins = int(player.get("coins") or 0)
        coll = b.get("collection") or []
        battle = set(self.cfg.get("battle_tower_types") or ["arc", "pulse"])
        upgraded = False
        # maks 2 upgrade per tick — pacing wajar, sisa koin buat chest
        for _ in range(2):
            opts = []
            for t in coll:
                typ = t.get("type")
                cost = int(t.get("upgradeCost") or 0)
                if typ in battle and cost and cost <= coins:
                    opts.append((cost, typ))
            if not opts:
                break
            opts.sort()
            cost, typ = opts[0]
            r = self.post("/api/towers/upgrade",
                          {"towerType": typ,
                           "operationId": str(uuid.uuid4())})
            level = r.get("level")
            if level:
                spent = int(r.get("coinsSpent") or cost)
                coins -= spent
                upgraded = True
                log(f"tower {typ} permanen → LV {level} "
                    f"(-{spent} coins, dmg +12%)")
                for t in coll:
                    if t.get("type") == typ:
                        t["level"] = level
                        t["upgradeCost"] = r.get("upgradeCost")
            else:
                log(f"upgrade {typ} gagal: {r.get('error') or r}")
                break
        return upgraded

    def maybe_buy_chest(self, b):
        if not self.cfg.get("auto_buy_chests"):
            return
        player = b.get("player") or {}
        coins = int(player.get("coins") or 0)
        for ch in (b.get("chests") or []):
            cost = int(ch.get("cost") or 0)
            if cost and coins >= cost:
                r = self.post("/api/chests/open",
                              {"chestId": ch["id"],
                               "operationId": str(uuid.uuid4())})
                tower = r.get("tower") or {}
                if tower or r.get("success"):
                    log(f"chest '{ch['id']}' dibuka (-{cost} coins): "
                        f"{json.dumps(tower)[:160]}")
                    coins -= cost
                else:
                    log(f"chest '{ch['id']}': {r.get('error') or r}")

    # ---------------- Withdraw ----------------
    def maybe_withdraw(self):
        if not self.cfg.get("auto_withdraw"):
            return
        w = self.get("/api/withdrawals")
        if "minUsdMicros" not in w:
            return
        avail = int(w.get("availableUsdMicros") or 0)
        mini = max(int(w.get("minUsdMicros") or 0),
                   int(self.cfg.get("withdraw_min_usdmicros") or 0))
        if avail < mini or avail <= 0:
            return
        currencies = w.get("currencies") or []
        cur = self.cfg["withdraw_currency"]
        if cur not in currencies:
            cur = currencies[0]
        draft = {
            "id": str(uuid.uuid4()),
            "amountUsdMicros": avail,
            "currency": cur,
            "recipient": self.cfg["withdraw_recipient"].strip().lower(),
        }
        r = self.post("/api/withdrawals", draft)
        if r.get("withdrawals") is not None or r.get("id") or r.get("success"):
            log(f"WITHDRAW OK: {avail/1e6:.6f} USD {cur} -> {draft['recipient']}")
        else:
            log(f"withdraw ditolak: {r.get('error') or r.get('code') or r}")

    # ---------------- Status ----------------
    def print_status(self):
        b = self.bootstrap()
        if b.get("code") == "LOGIN_REQUIRED" or not b.get("player"):
            log(f"bootstrap gagal: {b.get('error') or b.get('code')} "
                f"-> cookie mati, login ulang (script login otomatis pakai xsolve)")
            return False
        p = b.get("player") or {}
        e = b.get("earning") or {}
        log(f"player: {p.get('alias')} | coins: {p.get('coins')} | "
            f"lifetimeShares: {p.get('lifetimeShares')}")
        for label, key, ckey in (("faucet reguler", "nextClaimAt", "faucetCoins"),
                                 ("faucet cepat", "quickNextClaimAt", "quickFaucetCoins")):
            left = max(0, (int(e.get(key) or 0) - time.time() * 1000) / 1000)
            log(f"{label}: {'SIAP' if left == 0 else f'{int(left)}s lagi'} "
                f"({e.get(ckey)} coins)")
        f = b.get("faucet") or {}
        log(f"pool harian: status={f.get('status')} payoutsEnabled={f.get('payoutsEnabled')} "
            f"| rewardedRuns {f.get('rewardedRunsUsed')}/{f.get('rewardedRunsLimit')}")
        w = self.get("/api/withdrawals")
        if "minUsdMicros" in w:
            log(f"dompet: available ${w.get('availableUsdMicros',0)/1e6:.6f} | "
                f"min ${w.get('minUsdMicros',0)/1e6:.6f} | paid ${w.get('paidUsdMicros',0)/1e6:.6f} | "
                f"currencies={w.get('currencies')}")
        st = self.get("/api/security/status")
        left = (int(st.get("verifiedUntil") or 0) - time.time() * 1000) / 60000
        log(f"jendela verifikasi: {left:.1f} menit lagi")
        log(f"chests: " + ", ".join(
            f"{c['id']}({c.get('cost')}c)" for c in (b.get("chests") or [])))
        return True

    # ---------------- Loop ----------------
    def run_loop(self, once=False):
        while True:
            try:
                if not self.ensure_window("play"):
                    log("jendela verifikasi gagal diperpanjang — tunggu & ulangi")
                    if once:
                        return
                    time.sleep(600)  # cool-off: jangan serang challenge tiap 2 menit
                    continue
                b = self.bootstrap()
                if b.get("code") == "LOGIN_REQUIRED" or not b.get("player"):
                    log("sesi mati — login ulang otomatis...")
                    if not self.login():
                        time.sleep(60)
                        continue
                    b = self.bootstrap()

                e = b.get("earning") or {}
                if self._due(e, "quickNextClaimAt"):
                    self.claim("quick")
                    b = self.bootstrap()
                    e = b.get("earning") or {}
                if self._due(e, "nextClaimAt"):
                    self.claim("claim")

                if self.maybe_upgrade_towers(b):
                    b = self.bootstrap()  # koin/collection berubah → segarkan
                self.maybe_buy_chest(b)
                self.maybe_withdraw()

                p = b.get("player") or {}
                log(f"posisi: coins={p.get('coins')} | "
                    f"quick next in {max(0,(int(e.get('quickNextClaimAt') or 0)-time.time()*1000)/1000):.0f}s")
                if once:
                    return
                time.sleep(self.cfg["poll_seconds"] + random.uniform(0, 20))
            except Exception as ex:
                # jaringan blip / respons aneh JANGAN matikan bot (2026-11-08:
                # ConnectionError sempat mematikan proses — lihat ctd.log lama)
                log(f"loop error (akan ulangi): {type(ex).__name__}: {ex}")
                if once:
                    raise
                time.sleep(60)


def main():
    ap = argparse.ArgumentParser(description="CryptoTowerDefense auto (requests only)")
    ap.add_argument("--status", action="store_true", help="cek status lalu keluar")
    ap.add_argument("--once", action="store_true", help="satu putaran lalu keluar")
    ap.add_argument("--login", action="store_true", help="paksa login ulang (xsolve)")
    ap.add_argument("--no-withdraw", action="store_true")
    ap.add_argument("--no-chest", action="store_true")
    args = ap.parse_args()

    if args.no_withdraw:
        CONFIG["auto_withdraw"] = False
    if args.no_chest:
        CONFIG["auto_buy_chests"] = False

    log("=== CryptoTowerDefense AUTO — requests + xsolve, tanpa browser ===")
    cookie = None
    if os.path.exists(COOKIE_FILE):
        cookie = open(COOKIE_FILE).read().strip() or None
    ctd = CTD(CONFIG, cookie)

    if args.login or not (cookie and ctd.session_ok()):
        if cookie and not args.login:
            log("cookie lama tidak valid — login ulang otomatis")
        if not ctd.login():
            sys.exit(1)
    else:
        log("cookie aktif — tidak perlu login")

    if args.status:
        ctd.print_status()
        return

    try:
        ctd.run_loop(once=args.once)
    except KeyboardInterrupt:
        log("dihentikan user (Ctrl+C).")


if __name__ == "__main__":
    main()
