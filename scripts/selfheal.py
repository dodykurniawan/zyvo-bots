#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""selfheal.py — cek + perbaiki sesi 3 bot sebelum run (GitHub Actions / lokal).

Deteksi umum → recovery otomatis:
  CF  : get_state mati  → re-login dummy captcha (CF_EMAIL/CF_PASSWORD)
  CTD : identity mati   → login xsolve (CTD_EMAIL/CTD_PASSWORD + solver)
  LM  : /me mati        → re-login password (email/password di lm_config)
  Site down / endpoint hilang → lapor (tidak nebak patch API)

Pemakaian:
  python3 scripts/selfheal.py              # semua situs
  python3 scripts/selfheal.py --only cf
  python3 scripts/selfheal.py --json

Exit: 0 = sehat / sudah sembuh, 1 = masih rusak (job boleh lanjut atau retry).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def log(msg: str) -> None:
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}Z] {msg}", flush=True)


def _env(*names: str) -> str:
    for n in names:
        v = (os.environ.get(n) or "").strip()
        if v:
            return v
    return ""


# ---------------- CF ----------------
def heal_cf() -> dict[str, Any]:
    out: dict[str, Any] = {"site": "cf", "ok": False, "actions": []}
    cfg_path = os.path.join(ROOT, "cryptofisher", "cf_config.json")
    sid = ""
    if os.path.isfile(cfg_path):
        try:
            sid = (json.load(open(cfg_path)) or {}).get("phpsessid") or ""
        except Exception:
            sid = ""

    def probe(session_id: str) -> dict:
        s = requests.Session()
        s.headers.update(
            {
                "User-Agent": UA,
                "Accept": "application/json",
                "Origin": "https://cryptofisher.online",
                "Referer": "https://cryptofisher.online/",
            }
        )
        s.cookies.set("PHPSESSID", session_id, domain="cryptofisher.online")
        r = s.get(
            "https://cryptofisher.online/ajax.php?action=get_state", timeout=25
        )
        try:
            return r.json()
        except Exception:
            return {"success": False, "error": f"HTTP {r.status_code}"}

    st = probe(sid) if sid else {"success": False, "error": "no session"}
    if st.get("success"):
        out["ok"] = True
        out["actions"].append("session ok")
        b = st.get("balances") or {}
        out["detail"] = (
            f"lv{st.get('level')} exp={st.get('exp')} "
            f"USDT={float(b.get('USDT') or 0):.8f}"
        )
        # sinkronkan sid hidup ke SEMUA config (Actions repo + Termux sites/)
        for cfg_out in (
            cfg_path,
            "/storage/emulated/0/Download/ZYVO/sites/cryptofisher/cf_config.json",
        ):
            if not os.path.isfile(cfg_out):
                continue
            try:
                cfg = json.load(open(cfg_out))
            except Exception:
                continue
            if cfg.get("phpsessid") != sid:
                cfg["phpsessid"] = sid
                try:
                    json.dump(cfg, open(cfg_out, "w"), indent=2)
                    out["actions"].append(f"sid sync → {cfg_out}")
                except OSError:
                    pass
        return out

    email = _env("CF_EMAIL")
    password = _env("CF_PASSWORD")
    if not email or not password:
        # fallback lokal: file secret di folder situs (Termux)
        for base in (
            os.path.join(ROOT, "cryptofisher"),
            "/storage/emulated/0/Download/ZYVO/sites/cryptofisher",
        ):
            for fname, slot in (("cf_email.txt", "email"), ("cf_secret.txt", "password")):
                p = os.path.join(base, fname)
                try:
                    val = open(p, encoding="utf-8").read().strip()
                except OSError:
                    continue
                if val and not email and slot == "email":
                    email = val
                if val and not password and slot == "password":
                    password = val
        # config lama kadang simpan email saja
        if not email and os.path.isfile(cfg_path):
            try:
                email = (json.load(open(cfg_path)) or {}).get("email") or ""
            except Exception:
                pass
    if not email or not password:
        out["error"] = f"session mati + CF_EMAIL/CF_PASSWORD kosong ({st.get('error')})"
        return out

    # re-login dummy captcha (server tidak validasi isi captcha)
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": UA,
            "Accept": "application/json",
            "Origin": "https://cryptofisher.online",
            "Referer": "https://cryptofisher.online/",
        }
    )
    r = s.post(
        "https://cryptofisher.online/ajax.php",
        data={
            "action": "auth_login",
            "email": email,
            "password": password,
            "h-captcha-response": "00000000-0000-0000-0000-000000000000",
        },
        timeout=25,
    )
    try:
        data = r.json()
    except Exception:
        data = {"success": False, "error": f"HTTP {r.status_code}"}
    sid2 = s.cookies.get("PHPSESSID") or ""
    if not sid2:
        m = re.search(
            r"PHPSESSID=([^;]+)",
            str(data.get("cookie") or (r.headers.get("Set-Cookie") or "")),
        )
        sid2 = m.group(1) if m else ""
    if not (data.get("success") and sid2):
        out["error"] = f"re-login CF gagal: {data.get('error') or data}"
        return out

    # tulis ke SEMUA lokasi config yang ada (Actions = repo; Termux = sites/)
    for cfg_out in (
        cfg_path,
        "/storage/emulated/0/Download/ZYVO/sites/cryptofisher/cf_config.json",
    ):
        if not os.path.isfile(cfg_out) and cfg_out != cfg_path:
            continue
        try:
            if os.path.isfile(cfg_out):
                cfg = json.load(open(cfg_out))
            else:
                cfg = {}
        except Exception:
            cfg = {}
        cfg["phpsessid"] = sid2
        cfg["email"] = email
        try:
            json.dump(cfg, open(cfg_out, "w"), indent=2)
        except OSError:
            pass
    out["actions"].append("re-login dummy captcha OK")
    st2 = probe(sid2)
    out["ok"] = bool(st2.get("success"))
    if not out["ok"]:
        out["error"] = f"get_state masih gagal: {st2.get('error')}"
    else:
        b = st2.get("balances") or {}
        out["detail"] = f"lv{st2.get('level')} USDT={float(b.get('USDT') or 0):.8f}"
    return out


# ---------------- CTD ----------------
def _ctd_secret(fname: str, env: str) -> str:
    v = _env(env)
    if v:
        return v
    for base in (
        os.path.join(ROOT, "cryptotowerdefense"),
        "/storage/emulated/0/Download/ZYVO/sites/cryptotowerdefense",
    ):
        p = os.path.join(base, fname)
        try:
            with open(p, encoding="utf-8") as f:
                return f.read().strip()
        except OSError:
            pass
    return ""


def _load_solver_cfg() -> dict:
    path = os.environ.get("LM_CONFIG_PATH") or os.path.join(
        ROOT, "lightningminer", "lm_config.json"
    )
    if not os.path.isfile(path):
        path = "/storage/emulated/0/Download/ZYVO/sites/lightningminer/lm_config.json"
    try:
        return json.load(open(path))
    except Exception:
        return {}


def _solve_turnstile(sitekey: str, url: str, action: Optional[str], cdata: Optional[str]) -> str:
    cfg = _load_solver_cfg()
    key = cfg.get("xsolve_key") or ""
    if key:
        try:
            body = {"mode": "turnstile", "url": url, "sitekey": sitekey}
            if action:
                body["action"] = action
            if cdata:
                body["cdata"] = cdata
            r = requests.post(
                "https://api.xsolve.me/task",
                headers={"X-Api-Key": key},
                json=body,
                timeout=90,
            )
            j = r.json()
            tok = j.get("token") or ""
            if tok and str(j.get("status", "completed")) in (
                "completed",
                "ready",
                "success",
            ):
                return tok
            tid = j.get("taskId") or j.get("task_id")
            if tid:
                import time

                t0 = time.time()
                while time.time() - t0 < 60:
                    time.sleep(3)
                    p = requests.post(
                        "https://api.xsolve.me/getTaskResult",
                        json={"clientKey": key, "taskId": tid},
                        timeout=40,
                    ).json()
                    if p.get("status") in ("ready", "success", "completed"):
                        sol = p.get("solution") or {}
                        tok = sol.get("token") or sol.get("value") or ""
                        if tok:
                            return tok
        except Exception as e:
            log(f"  xsolve: {e}")
    peak = cfg.get("peak_key") or ""
    if peak:
        body = {"task_type": "turnstiletaskproxyless", "url": url, "sitekey": sitekey}
        if action:
            body["action"] = action
        if cdata:
            body["cdata"] = cdata
        r = requests.post(
            "https://api.peak.fo/solve",
            headers={"X-API-Key": peak},
            json=body,
            timeout=60,
        ).json()
        tok = ((r.get("data") or {}).get("token")) or ""
        if tok:
            return tok
        raise RuntimeError(f"peak gagal: {str(r.get('error'))[:160]}")
    raise RuntimeError("tidak ada solver (xsolve/peak)")


def heal_ctd() -> dict[str, Any]:
    out: dict[str, Any] = {"site": "ctd", "ok": False, "actions": []}
    cookie_path = os.path.join(ROOT, "cryptotowerdefense", "ctd_cookie.txt")
    cookie = ""
    if os.path.isfile(cookie_path):
        cookie = open(cookie_path).read().strip()

    def identity(ck: str) -> dict:
        s = requests.Session()
        s.headers.update(
            {
                "User-Agent": UA,
                "Accept": "application/json",
                "Origin": "https://cryptotowerdefense.com",
                "Referer": "https://cryptotowerdefense.com/",
                "x-ctd-client-version": "0.19.0",
                "Cookie": ck,
            }
        )
        r = s.get(
            "https://cryptotowerdefense.com/api/session/identity", timeout=25
        )
        try:
            return r.json()
        except Exception:
            return {"error": f"HTTP {r.status_code}"}

    ident = identity(cookie) if cookie else {"error": "no cookie"}
    if ident.get("profileId"):
        out["ok"] = True
        out["actions"].append("cookie ok")
        out["detail"] = f"profile …{str(ident.get('profileId'))[:8]}"
        return out

    email = _ctd_secret("ctd_email.txt", "CTD_EMAIL")
    password = _ctd_secret("ctd_secret.txt", "CTD_PASSWORD")
    if not email or not password:
        out["error"] = f"cookie mati + CTD_EMAIL/CTD_PASSWORD kosong ({ident.get('error')})"
        return out

    try:
        s = requests.Session()
        s.headers.update(
            {
                "User-Agent": UA,
                "Origin": "https://cryptotowerdefense.com",
                "Referer": "https://cryptotowerdefense.com/",
                "x-ctd-client-version": "0.19.0",
            }
        )
        ch = s.get(
            "https://cryptotowerdefense.com/api/security/challenge?purpose=login",
            timeout=25,
        ).json()
        if not ch.get("siteKey"):
            out["error"] = f"challenge login gagal: {ch}"
            return out
        tok = _solve_turnstile(
            ch["siteKey"],
            "https://cryptotowerdefense.com/signin",
            ch.get("action") or "login",
            ch.get("cData") or ch.get("challengeId"),
        )
        r = s.post(
            "https://cryptotowerdefense.com/api/account/login",
            json={
                "identifier": email,
                "password": password,
                "challengeId": ch["challengeId"],
                "turnstileToken": tok,
            },
            timeout=30,
        )
        data = r.json()
        if not (data.get("account") or {}).get("authenticated"):
            out["error"] = f"login CTD ditolak: {data.get('error') or data}"
            return out
        parts = [f"{c.name}={c.value}" for c in s.cookies]
        # cookie mentah dari Set-Cookie juga
        raw = "; ".join(parts)
        sc = r.headers.get("Set-Cookie") or ""
        if not raw and sc:
            raw = sc
        if not raw:
            # bangun dari jar + header
            raw = "; ".join(
                f"{c.name}={c.value}" for c in s.cookies
            )
        # fallback: kalau jar kosong, parse Set-Cookie pairs
        if not raw:
            pairs = re.findall(r"([^=;\s]+)=([^;]+)", sc)
            raw = "; ".join(f"{k}={v}" for k, v in pairs)
        if not raw:
            out["error"] = "login OK tapi cookie tidak bisa dibaca"
            return out
        os.makedirs(os.path.dirname(cookie_path), exist_ok=True)
        open(cookie_path, "w").write(raw)
        try:
            os.chmod(cookie_path, 0o600)
        except OSError:
            pass
        out["actions"].append("re-login xsolve OK (cookie disimpan)")
        ident2 = identity(raw)
        out["ok"] = bool(ident2.get("profileId"))
        if not out["ok"]:
            out["error"] = f"identity setelah login: {ident2}"
        else:
            out["detail"] = f"profile …{str(ident2.get('profileId'))[:8]}"
        return out
    except Exception as e:
        out["error"] = f"re-login CTD gagal: {e}"
        return out


# ---------------- LM ----------------
def heal_lm() -> dict[str, Any]:
    out: dict[str, Any] = {"site": "lm", "ok": False, "actions": []}
    cfg_path = os.environ.get("LM_CONFIG_PATH") or os.path.join(
        ROOT, "lightningminer", "lm_config.json"
    )
    if not os.path.isfile(cfg_path):
        cfg_path = "/storage/emulated/0/Download/ZYVO/sites/lightningminer/lm_config.json"
    if not os.path.isfile(cfg_path):
        out["error"] = "lm_config.json tidak ada"
        return out
    cfg = json.load(open(cfg_path))
    sess = cfg.get("lm_session") or ""

    def me(session: str) -> dict:
        s = requests.Session()
        s.headers.update({"User-Agent": UA, "Accept": "application/json"})
        s.cookies.set("lm_session", session, domain="lightningminer.com")
        r = s.get("https://lightningminer.com/api/me", timeout=25)
        try:
            return r.json()
        except Exception:
            return {"ok": False, "error": f"HTTP {r.status_code}"}

    d = me(sess) if sess else {"ok": False, "error": "no session"}
    # /me kadang balas user top-level tanpa ok
    alive = d.get("ok", True) and not d.get("error") and (
        d.get("user") or d.get("username") or "coins" in d or "settledCryptoBalanceAtomic" in d
    )
    if alive and not (d.get("ok") is False):
        # pastikan bukan error object
        if d.get("error") and not (d.get("user") or d.get("settledCryptoBalanceAtomic")):
            alive = False
    if alive:
        out["ok"] = True
        out["actions"].append("session ok")
        u = d.get("user") or d
        out["detail"] = (
            f"coins={u.get('coins')} settled={u.get('settledCryptoBalanceAtomic')}"
        )
        return out

    email = cfg.get("email") or _env("LM_EMAIL")
    password = cfg.get("password") or _env("LM_PASSWORD")
    if not email or not password:
        out["error"] = f"session mati + email/password kosong ({d.get('error')})"
        return out
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "application/json"})
    r = s.post(
        "https://lightningminer.com/api/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    try:
        data = r.json()
    except Exception:
        data = {"ok": False, "error": f"HTTP {r.status_code}"}
    newsess = s.cookies.get("lm_session") or ""
    if not newsess or (data.get("ok") is False and data.get("error")):
        # coba path non-/api kalau perlu
        if not newsess:
            out["error"] = f"re-login LM gagal: {data.get('error') or data}"
            return out
    cfg["lm_session"] = newsess
    # jangan simpan password ulang kalau sudah ada
    json.dump(cfg, open(cfg_path, "w"), indent=2)
    try:
        os.chmod(cfg_path, 0o600)
    except OSError:
        pass
    out["actions"].append("re-login password OK")
    d2 = me(newsess)
    out["ok"] = bool(
        d2.get("ok", True)
        and not d2.get("error")
        and (d2.get("user") or d2.get("settledCryptoBalanceAtomic") or "coins" in d2)
    )
    if not out["ok"]:
        out["error"] = f"/me setelah login: {d2.get('error') or d2}"
    else:
        u = d2.get("user") or d2
        out["detail"] = f"coins={u.get('coins')}"
    return out


# ---------------- endpoint up-check ----------------
def probe_sites_up() -> list[str]:
    urls = [
        ("cf", "https://cryptofisher.online/"),
        ("ctd", "https://cryptotowerdefense.com/"),
        ("lm", "https://lightningminer.com/"),
    ]
    down = []
    for name, url in urls:
        try:
            r = requests.get(
                url,
                headers={"User-Agent": UA},
                timeout=20,
                allow_redirects=True,
            )
            if r.status_code >= 500:
                down.append(f"{name}: HTTP {r.status_code}")
        except Exception as e:
            down.append(f"{name}: {type(e).__name__}")
    return down


def main() -> int:
    ap = argparse.ArgumentParser(description="Self-heal sesi bot ZYVO")
    ap.add_argument("--only", choices=["cf", "ctd", "lm"], help="situs tertentu")
    ap.add_argument("--json", action="store_true", help="output JSON")
    ap.add_argument("--skip-up", action="store_true", help="lewati cek site up")
    args = ap.parse_args()

    results: list[dict] = []
    if not args.skip_up:
        down = probe_sites_up()
        if down:
            log(f"SITE DOWN: {', '.join(down)}")
            results.append({"site": "up", "ok": False, "error": "; ".join(down)})

    healers = {"cf": heal_cf, "ctd": heal_ctd, "lm": heal_lm}
    targets = [args.only] if args.only else ["cf", "ctd", "lm"]
    for t in targets:
        log(f"heal {t}…")
        try:
            r = healers[t]()
        except Exception as e:
            r = {"site": t, "ok": False, "error": f"{type(e).__name__}: {e}"}
        results.append(r)
        mark = "OK" if r.get("ok") else "RUSAK"
        acts = ", ".join(r.get("actions") or []) or "-"
        detail = r.get("detail") or r.get("error") or ""
        log(f"  {mark}: {acts} {detail}")

    ok = all(r.get("ok") for r in results if r.get("site") in ("cf", "ctd", "lm", "up"))
    # site down tapi sesi ok → tetap anggap perlu perhatian
    if any(r.get("site") == "up" and not r.get("ok") for r in results):
        ok = False

    summary = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "ok": ok,
        "results": results,
    }
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        log(f"RESULT ok={ok}")
        for r in results:
            log(f"  - {r.get('site')}: {'ok' if r.get('ok') else 'FAIL'} "
                f"{r.get('error') or r.get('detail') or ''}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
