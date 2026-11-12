#!/usr/bin/env python3
"""Scrapper-suite bot — pure HTTP, 5 sister sites (BTC/PEPE/TRX/DOGE/LTC).

Same codebase as the live frontend (/js/app.js, faucet.js, pow.js).
Passwordless login = FaucetPay email. Image captcha = pick candidate whose
URL equals target (no image download). Human gate = SHA-256 PoW.

Usage:
  python3 scrapper_auto.py --site all --once
  python3 scrapper_auto.py --site btc
  python3 scrapper_auto.py --site all --status
  python3 scrapper_auto.py --site all          # loop forever
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "config.json"
FP_EMAIL = os.environ.get("SCRP_FP_EMAIL", "dodykurniaw4n@gmail.com")

SITES: dict[str, str] = {
    "btc": "https://satoshiscrapper.com",
    "pepe": "https://pepescrapper.com",
    "tron": "https://tronscrapper.com",
    "doge": "https://dogescrapper.com",
    "ltc": "https://ltcscrapper.com",
}

UA = (
    "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
    "Chrome/120.0.0.0 Mobile Safari/537.36"
)


def log(site: str, msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] [{site}] {msg}", flush=True)


def lzb(data: bytes) -> int:
    n = 0
    for b in data:
        if b == 0:
            n += 8
            continue
        n += 8 - b.bit_length()
        break
    return n


class Scrapper:
    def __init__(self, key: str, base: str, email: str, state_path: Path):
        self.key = key
        self.base = base.rstrip("/")
        self.email = email
        self.state_path = state_path
        self.cj = CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj)
        )
        self.opener.addheaders = [
            ("User-Agent", UA),
            ("Origin", self.base),
            ("Referer", self.base + "/"),
            ("Accept", "application/json, text/plain, */*"),
            ("Accept-Language", "en-US,en;q=0.9"),
        ]
        self._load_state()

    def _load_state(self) -> None:
        try:
            self.state = json.loads(self.state_path.read_text())
        except Exception:
            self.state = {}
        # restore session cookies (needed across process restarts)
        for c in self.state.get("cookies") or []:
            try:
                self.cj.set_cookie(
                    __import__("http.cookiejar", fromlist=["Cookie"]).Cookie(
                        version=0,
                        name=c["name"],
                        value=c["value"],
                        port=None,
                        port_specified=False,
                        domain=c.get("domain") or urllib.request.urlparse(self.base).hostname,
                        domain_specified=True,
                        domain_initial_dot=False,
                        path=c.get("path") or "/",
                        path_specified=True,
                        secure=c.get("secure", True),
                        expires=c.get("expires"),
                        discard=False,
                        comment=None,
                        comment_url=None,
                        rest={"HttpOnly": None},
                        rfc2109=False,
                    )
                )
            except Exception:
                pass

    def _save_state(self) -> None:
        try:
            cookies = []
            for c in self.cj:
                cookies.append(
                    {
                        "name": c.name,
                        "value": c.value,
                        "domain": c.domain,
                        "path": c.path,
                        "secure": bool(c.secure),
                        "expires": c.expires,
                    }
                )
            self.state["cookies"] = cookies
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(json.dumps(self.state, indent=2))
        except Exception:
            pass

    def req(
        self, path: str, body: Any = None, timeout: int = 30
    ) -> tuple[int, Any]:
        url = self.base + path
        data = json.dumps(body).encode() if body is not None else None
        r = urllib.request.Request(
            url, data=data, method="POST" if body is not None else "GET"
        )
        if data:
            r.add_header("content-type", "application/json")
        try:
            with self.opener.open(r, timeout=timeout) as resp:
                raw = resp.read().decode(errors="replace")
                try:
                    return resp.status, json.loads(raw or "{}")
                except json.JSONDecodeError:
                    return resp.status, {"raw": raw[:400]}
        except urllib.error.HTTPError as e:
            raw = e.read().decode(errors="replace")
            try:
                return e.code, json.loads(raw)
            except json.JSONDecodeError:
                return e.code, {"raw": raw[:400], "error": raw[:200]}
        except Exception as e:
            return 0, {"error": str(e)}

    def ensure_human(self) -> bool:
        code, powj = self.req("/api/human/challenge")
        if code != 200 or not isinstance(powj, dict) or not powj.get("prefix"):
            return False
        prefix = powj["prefix"]
        bits = int(powj.get("bits") or 14)
        nonce = 0
        # cap grind — 14 bits is usually <100ms
        while nonce < 5_000_000:
            digest = hashlib.sha256(f"{prefix}:{nonce}".encode()).digest()
            if lzb(digest) >= bits:
                break
            nonce += 1
        else:
            return False
        code, j = self.req("/api/human", {"prefix": prefix, "nonce": str(nonce)})
        ok = code == 200
        if ok:
            self.state["human"] = True
            self._save_state()
        return ok

    def api(self, path: str, body: Any = None) -> tuple[int, Any]:
        code, j = self.req(path, body)
        if code == 403 and isinstance(j, dict) and j.get("code") == "human":
            if self.ensure_human():
                code, j = self.req(path, body)
        # persist session after any successful auth-ish call
        if code in (200, 401) or (isinstance(j, dict) and j.get("ok")):
            self._save_state()
        return code, j

    def login(self) -> bool:
        # human gate first (register itself is gated)
        self.ensure_human()
        code, j = self.api(
            "/api/register", {"address": self.email, "lang": "en"}
        )
        if code == 200:
            self.state["logged_in"] = True
            self._save_state()
            return True
        # already has session?
        code2, me = self.api("/api/me")
        if code2 == 200 and me.get("address"):
            self.state["logged_in"] = True
            self._save_state()
            return True
        log(self.key, f"login gagal: {code} {j}")
        return False

    def me(self) -> dict:
        code, j = self.api("/api/me")
        return j if code == 200 else {}

    def state_game(self) -> dict:
        code, j = self.api("/api/game/state")
        return j if code == 200 else {}

    @staticmethod
    def choice_for(ch: dict) -> int:
        target = ch.get("target")
        cands = ch.get("candidates") or []
        if target in cands:
            return cands.index(target)
        # fallback: hash-equal if URLs differ only by query
        return 0

    def solve_chained(
        self, challenge_path: str, confirm_path: str, body_extra: dict | None = None
    ) -> tuple[bool, Any]:
        code, ch = self.api(challenge_path)
        if code != 200 or not isinstance(ch, dict) or not ch.get("challengeId"):
            return False, ch
        # faucet multi-step: server enforces steps*adSeconds view time
        steps = int(ch.get("steps") or 1)
        ad_sec = int(ch.get("adSeconds") or 5)
        wait = max(ad_sec, steps * ad_sec) + random.uniform(1.0, 2.5)
        time.sleep(wait)
        choice = self.choice_for(ch)
        payload = {
            "challengeId": ch["challengeId"],
            "choiceIndex": choice,
        }
        if body_extra:
            payload.update(body_extra)
        # amount may be needed for zero claim
        if "amount" in (body_extra or {}):
            payload["amount"] = body_extra["amount"]
        code, j = self.api(confirm_path, payload)
        return code == 200 and (
            not isinstance(j, dict) or j.get("ok") is not False
        ), j

    # ── actions ──────────────────────────────────────────────
    def act_free_gift(self) -> bool:
        st = self.state_game()
        if not st.get("freeGiftReady"):
            return False
        code, j = self.api("/api/game/free-gift", {})
        ok = code == 200 and isinstance(j, dict) and j.get("gifted") is not None
        if ok:
            log(self.key, f"free-gift +{j.get('gifted')} screws")
        else:
            log(self.key, f"free-gift gagal: {code} {j}")
        return ok

    def act_faucet(self) -> bool:
        st = self.state_game()
        if not st.get("faucetReady") and not st.get("faucetEnabled"):
            return False
        if not st.get("faucetReady"):
            return False
        ok, j = self.solve_chained(
            "/api/game/faucet/challenge", "/api/game/faucet/claim"
        )
        if ok:
            log(
                self.key,
                f"faucet OK zero={j.get('zero')} zems+={j.get('gotZems')}",
            )
        else:
            log(self.key, f"faucet gagal: {j}")
        return ok

    def act_spin(self) -> bool:
        st = self.state_game()
        if st.get("spinPending"):
            ok, j = self.solve_chained(
                "/api/game/spin/claim/challenge", "/api/game/spin/claim"
            )
            if ok:
                log(self.key, f"spin-claim OK zems+={j.get('prizeZems')}")
            else:
                log(self.key, f"spin-claim gagal: {j}")
            return ok
        if not st.get("spinReady"):
            return False
        code, j = self.api("/api/game/spin", {})
        if code != 200:
            log(self.key, f"spin gagal: {code} {j}")
            return False
        # prize may be pending claim
        if isinstance(j, dict) and j.get("spinPending") or (
            isinstance(j, dict) and j.get("prizeZems") is not None and j.get("ok")
        ):
            # some sites auto-credit spin; if spinPending still set, claim
            st2 = self.state_game()
            if st2.get("spinPending"):
                ok, j2 = self.solve_chained(
                    "/api/game/spin/claim/challenge", "/api/game/spin/claim"
                )
                if ok:
                    log(self.key, f"spin+claim OK zems+={j2.get('prizeZems')}")
                    return True
            # spin already returned prize fields
            if isinstance(j, dict) and j.get("prizeZems") is not None:
                # still need claim modal on some deploys — try claim challenge once
                ok, j2 = self.solve_chained(
                    "/api/game/spin/claim/challenge", "/api/game/spin/claim"
                )
                if ok:
                    log(self.key, f"spin claim OK zems+={j2.get('prizeZems')}")
                    return True
                # auto-credited path
                log(self.key, f"spin OK (auto?) prize={j.get('prizeZems')}")
                return True
        log(self.key, f"spin: {code} keys={list(j)[:8] if isinstance(j, dict) else j}")
        return code == 200

    def act_streak(self) -> bool:
        st = self.state_game()
        if not st.get("streakReady"):
            return False
        ok, j = self.solve_chained("/api/game/streak/challenge", "/api/game/streak")
        if ok:
            log(
                self.key,
                f"streak OK day={j.get('streakDay')} reward={j.get('streakReward')}",
            )
        else:
            log(self.key, f"streak gagal: {j}")
        return ok

    def act_quests(self) -> int:
        st = self.state_game()
        n = 0
        for q in st.get("quests") or []:
            if q.get("complete") and not q.get("claimed"):
                key = q.get("key")
                ok, j = self.solve_chained(
                    f"/api/game/quests/challenge?key={key}",
                    f"/api/game/quests/claim?key={key}",
                )
                if ok:
                    log(self.key, f"quest {key} OK +{q.get('reward')}")
                    n += 1
                else:
                    log(self.key, f"quest {key} gagal: {j}")
                time.sleep(random.uniform(2, 4))
        return n

    def act_upgrade(self) -> int:
        """Spend ZERO on cheapest trait that still levels (prefer strength)."""
        st = self.state_game()
        bal = float(st.get("balance") or 0)
        traits = st.get("traits") or []
        # prefer strength → charm → looks (hashrate first)
        order = {"strength": 0, "charm": 1, "looks": 2}
        cands = []
        for tr in traits:
            if tr.get("maxed") or (
                tr.get("maxLevel") and tr.get("level", 0) >= tr["maxLevel"]
            ):
                continue
            cost = float(tr.get("cost") or 0)
            if cost <= 0 or cost > bal:
                continue
            cands.append((order.get(tr.get("key"), 9), cost, tr.get("key")))
        cands.sort()
        n = 0
        # upgrade until we can't afford next (keep a tiny buffer for claim min)
        while cands:
            _, cost, key = cands[0]
            if cost > bal * 0.98:
                break
            code, j = self.api("/api/game/upgrade", {"key": key})
            if code == 200:
                log(self.key, f"upgrade {key} OK cost≈{cost:.3e} bal→{j.get('balance')}")
                n += 1
                bal = float(j.get("balance") or bal)
                # refresh candidates costs
                traits = j.get("traits") or traits
                cands = []
                for tr in traits:
                    if tr.get("maxed") or (
                        tr.get("maxLevel")
                        and tr.get("level", 0) >= tr["maxLevel"]
                    ):
                        continue
                    c = float(tr.get("cost") or 0)
                    if c <= 0 or c > bal * 0.98:
                        continue
                    cands.append((order.get(tr.get("key"), 9), c, tr.get("key")))
                cands.sort()
                time.sleep(random.uniform(1.5, 3))
            else:
                log(self.key, f"upgrade {key} gagal: {code} {j}")
                break
        return n

    def act_alloc(self) -> None:
        """100% coin (ZERO) mining — Screws only useful for unlocks."""
        st = self.state_game()
        if int(st.get("allocZero") or 0) != 100:
            code, j = self.api("/api/game/alloc", {"zero": 100})
            if code == 200:
                log(self.key, "alloc → 100% coin")

    def act_donate_unlock(self) -> bool:
        """If next rig is ready to unlock via donated screws, push it."""
        st = self.state_game()
        if not st.get("girlReady"):
            return False
        ok, j = self.solve_chained(
            "/api/game/girl/challenge", "/api/game/girl/claim"
        )
        if ok:
            log(self.key, f"girl unlock OK hash={j.get('hashrate')}")
        else:
            log(self.key, f"girl unlock gagal: {j}")
        return ok

    def act_withdraw(self) -> bool:
        """Auto-WD when balance ≥ minClaim and cooldown ready (FaucetPay)."""
        st = self.state_game()
        if not st.get("claimReady"):
            return False
        bal = float(st.get("balance") or 0)
        min_c = float(st.get("minClaim") or 0)
        if bal < min_c or min_c <= 0:
            return False
        code, ch = self.api("/api/game/claim/challenge")
        if code != 200:
            log(self.key, f"wd challenge: {code} {ch}")
            return False
        steps = int(ch.get("steps") or 1)
        ad_sec = int(ch.get("adSeconds") or 5)
        time.sleep(max(ad_sec, steps * ad_sec) + random.uniform(1.5, 3))
        choice = self.choice_for(ch)
        # full balance (amount null) — partial only if server wants explicit
        payload: dict[str, Any] = {
            "challengeId": ch["challengeId"],
            "choiceIndex": choice,
        }
        # send full native balance (display conversion is client-side)
        if ch.get("balance") is not None:
            # amount omitted → withdraw whole balance on this codebase
            pass
        code, j = self.api("/api/game/claim", payload)
        if code == 200 and (not isinstance(j, dict) or j.get("ok") is not False):
            amt = j.get("amount") if isinstance(j, dict) else None
            log(self.key, f"WD OK amount={amt} → FaucetPay")
            return True
        log(self.key, f"WD gagal: {code} {j}")
        return False

    def act_ptc_probe(self) -> None:
        """PTC needs a real browser ad view — only fetch URL for status."""
        code, j = self.api("/api/game/ptc-url")
        if code == 200 and isinstance(j, dict):
            log(self.key, f"ptc enabled={j.get('enabled')} perView={j.get('perView')}")

    def status(self) -> dict:
        st = self.state_game()
        if not st:
            self.state["logged_in"] = False
            if not self.login():
                return {"site": self.key, "error": "login"}
            st = self.state_game()
        if not st:
            return {"site": self.key, "error": "state"}
        me = self.me()
        member = me.get("member") or {}
        power = st.get("power") or {}
        traits = [
            f"{t.get('key')}:{t.get('level')}" for t in st.get("traits") or []
        ]
        info = {
            "site": self.key,
            "url": self.base,
            "balance": st.get("balance"),
            "minClaim": st.get("minClaim"),
            "claimReady": st.get("claimReady"),
            "claimIn": st.get("claimIn"),
            "zems": st.get("zems"),
            "hashrate": st.get("hashrate"),
            "zeroPerSec": st.get("zeroPerSec"),
            "power": power.get("charge"),
            "traits": traits,
            "unlocked": f"{st.get('unlockedCount')}/{st.get('catalogSize')}",
            "streak": st.get("streakCount"),
            "faucetReady": st.get("faucetReady"),
            "spinReady": st.get("spinReady"),
            "freeGiftReady": st.get("freeGiftReady"),
            "vip": bool(member.get("active")),
            "payoutsEnabled": st.get("payoutsEnabled"),
        }
        return info

    def cycle(self) -> dict:
        """One full premium auto-all pass. Returns counters."""
        if not self.state.get("logged_in"):
            if not self.login():
                return {"ok": False, "err": "login"}
        # refresh human cookie if needed early
        st = self.state_game()
        if not st:
            self.ensure_human()
            st = self.state_game()
        if not st:
            return {"ok": False, "err": "state"}

        res = {
            "ok": True,
            "gift": False,
            "faucet": False,
            "spin": False,
            "streak": False,
            "quests": 0,
            "upgrades": 0,
            "unlock": False,
            "wd": False,
            "balance": st.get("balance"),
            "zems": st.get("zems"),
            "hashrate": st.get("hashrate"),
        }

        # order: free rewards → earn power → spend → withdraw
        res["gift"] = self.act_free_gift()
        time.sleep(random.uniform(2, 4))
        res["faucet"] = self.act_faucet()
        time.sleep(random.uniform(2, 4))
        res["spin"] = self.act_spin()
        time.sleep(random.uniform(2, 4))
        res["streak"] = self.act_streak()
        time.sleep(random.uniform(2, 4))
        res["quests"] = self.act_quests()
        time.sleep(random.uniform(1, 2))
        self.act_alloc()
        # WD BEFORE upgrade so we never spend below minClaim
        res["wd"] = self.act_withdraw()
        res["upgrades"] = self.act_upgrade()
        res["unlock"] = self.act_donate_unlock()

        st2 = self.state_game()
        res["balance"] = st2.get("balance")
        res["zems"] = st2.get("zems")
        res["hashrate"] = st2.get("hashrate")
        return res


def load_sites() -> dict:
    try:
        cfg = json.loads(CONFIG_PATH.read_text())
    except Exception:
        cfg = {}
    sites = cfg.get("sites") or SITES
    email = cfg.get("fp_email") or FP_EMAIL
    return {"sites": sites, "email": email}


def main() -> int:
    ap = argparse.ArgumentParser(description="Scrapper suite auto-all bot")
    ap.add_argument("--site", default="all", help="btc|pepe|tron|doge|ltc|all")
    ap.add_argument("--once", action="store_true", help="one cycle then exit")
    ap.add_argument("--status", action="store_true", help="print status JSON")
    ap.add_argument("--login", action="store_true", help="force re-login")
    ap.add_argument(
        "--interval", type=int, default=180, help="seconds between cycles"
    )
    args = ap.parse_args()

    cfg = load_sites()
    sites_map: dict[str, str] = cfg["sites"]
    email: str = cfg["email"]

    keys = list(sites_map.keys()) if args.site == "all" else [args.site]
    for k in keys:
        if k not in sites_map:
            print(f"unknown site {k}; choices: {list(sites_map)}", file=sys.stderr)
            return 2

    bots = []
    for k in keys:
        state_path = HERE / f"state_{k}.json"
        bots.append(Scrapper(k, sites_map[k], email, state_path))

    if args.status:
        out = []
        for b in bots:
            try:
                out.append(b.status())
            except Exception as e:
                out.append({"site": b.key, "error": str(e)})
            time.sleep(random.uniform(1, 2))
        print(json.dumps(out, indent=2))
        return 0

    if args.login:
        for b in bots:
            b.state["logged_in"] = False
            b._save_state()
            ok = b.login()
            log(b.key, f"login={'OK' if ok else 'FAIL'}")
            time.sleep(random.uniform(2, 4))
        if args.once:
            return 0

    if args.once:
        codes = 0
        for b in bots:
            try:
                r = b.cycle()
                log(b.key, f"cycle {json.dumps({k: v for k, v in r.items() if k != 'ok'})}")
                if r.get("ok"):
                    codes += 1
            except Exception as e:
                log(b.key, f"cycle EXC {e}")
            time.sleep(random.uniform(3, 6))
        return 0 if codes == len(bots) else 1

    # forever loop
    log("suite", f"loop start sites={keys} interval={args.interval}s email={email}")
    while True:
        for b in bots:
            try:
                r = b.cycle()
                log(
                    b.key,
                    f"cycle ok={r.get('ok')} wd={r.get('wd')} "
                    f"bal={r.get('balance')} zems={r.get('zems')} "
                    f"h={r.get('hashrate')} up={r.get('upgrades')}",
                )
            except Exception as e:
                log(b.key, f"cycle EXC {e}")
                b.state["logged_in"] = False
                b._save_state()
            time.sleep(random.uniform(8, 15))
        time.sleep(max(30, args.interval))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nbye")
        sys.exit(0)
