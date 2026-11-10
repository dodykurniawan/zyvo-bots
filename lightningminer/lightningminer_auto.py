#!/usr/bin/env python3
"""
LightningMiner Auto-All — bot Python untuk akun sendiri (lightningminer.com).

Fitur (semua DEFAULT ON — jalan polos `python3 lightningminer_auto.py`):
  - Auto login (simpan lm_session) → sync-mining berkala
  - Auto faucet: challenge → hCaptcha (dispatcher NoneCap→MythiX) →
    tunggu readyAt → claim
  - Auto daily-bonus (cooldown 24h)
  - Auto claim quests + battlepass tasks/rewards yang bisa diklaim
  - Auto beli miner ROI terbaik (basePower/cost) + upgrade saat sisa coins cukup
  - Auto beli energy-cell / rack / recharge-energy saat tersedia
  - Auto shortlinks best-effort (follow /start sampai selesai / gagal)
  - Auto WD FaucetPay (USDC) saat settled ≥ min; `--wd-now` force

Turnstile (PTC self-serve view-complete + shortlink CXL/shrink) butuh solver
key di lm_config.json — provider otomatis dicoba berurutan:
  xsolve_key (https://xsolve.me — $0.08/1k, native /task, sync) →
  nocaptchaai_key (6000 gratis/bulan) → peak_key (1000 gratis) →
  capsolver_key → twocaptcha_key → nopecha_key (butuh plan berbayar)
Tanpa key: fitur itu auto-skip, bot tetap jalan (faucet/daily/quest/WD).

hCaptcha (faucet + form shortlink) pakai dispatcher terpisah — provider
dicoba berurutan sampai satu balik token:
  nonecap_key (https://dashboard.nonecap.com — 1300 kredit signup) →
  mythix_key (https://mythixsolve.tech — 1000 kredit gratis, hCaptcha-only)

Pakai:
  python3 lightningminer_auto.py --login EMAIL --password PASS   # sekali
  python3 lightningminer_auto.py                                 # loop
  python3 lightningminer_auto.py --once                          # satu siklus
  python3 lightningminer_auto.py --set-wd faucetpay YOU@x.com    # set WD
  python3 lightningminer_auto.py --set-key peak_key pk_xxx       # set solver
  python3 lightningminer_auto.py --no-faucet --no-shop           # opt-out

Config: lm_config.json (chmod 600) di folder skrip.
"""

from __future__ import annotations

import argparse
import getpass
import html as html_mod
import json
import os
import random
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin, urlsplit, unquote

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

BASE = "https://lightningminer.com"
API = f"{BASE}/api"
NONECAP_API = "https://api.nonecap.com/v1"
CFG_PATH = Path(__file__).resolve().parent / "lm_config.json"
UA = (
    "Mozilla/5.0 (Linux; Android 14; Phone) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)

FAUCET_SITEKEY = "764c22e4-3102-4218-8130-1c848c282506"
MIN_WD_ATOMIC = 10000  # USDC 0.01 (atomsPerDisplayUnit 1e6)

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


def is_online(host: str = "lightningminer.com") -> bool:
    """TCP 443 murah — tanpa internet bot standby, proses tetap hidup."""
    import socket

    try:
        with socket.create_connection((host, 443), timeout=5):
            return True
    except OSError:
        return False


def offline_standby(host: str = "lightningminer.com") -> None:
    log(f"OFFLINE — tidak ada internet ke {host}. "
        "Standby (hemat kuota), auto-resume saat koneksi balik.")
    while not is_online(host):
        time.sleep(30)
    log("ONLINE lagi — lanjut siklus.")
    try:
        CFG_PATH.chmod(0o600)
    except Exception:
        pass


# ---------------------------------------------------------------- session


class LMClient:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept": "application/json"})
        cookie = cfg.get("lm_session")
        if cookie:
            self.s.cookies.set("lm_session", cookie, domain="lightningminer.com")
        self.state: dict = {}

    def api(
        self,
        method: str,
        path: str,
        json_body: Optional[dict] = None,
        timeout: int = 30,
        allow_redirect: bool = False,
    ) -> dict:
        if path.startswith("http"):
            url = path
        elif path.startswith("/api/"):
            url = BASE + path
        else:
            url = API + path
        try:
            r = self.s.request(
                method,
                url,
                json=json_body if json_body is not None else None,
                timeout=timeout,
                allow_redirects=allow_redirect,
            )
        except requests.RequestException as e:
            return {"ok": False, "error": f"network: {e}"}
        ctype = r.headers.get("Content-Type", "")
        if r.status_code >= 400:
            try:
                data = r.json()
            except Exception:
                data = {"ok": False, "error": f"HTTP {r.status_code}"}
            if not data.get("error"):
                data["error"] = f"HTTP {r.status_code}"
            data["ok"] = False
            return data
        if "json" in ctype:
            data = r.json()
            if isinstance(data, dict) and "ok" not in data and "error" not in data:
                data["ok"] = True
            return data
        return {"ok": True, "status": r.status_code, "text": r.text[:300]}

    def login(self, email: str, password: str) -> bool:
        r = self.api("POST", "/login", {"email": email, "password": password})
        if not r.get("ok"):
            log(f"Login GAGAL: {r.get('error')}")
            return False
        sess = self.s.cookies.get("lm_session")
        if not sess:
            log("Login: cookie lm_session tidak ada di response.")
            return False
        self.cfg["lm_session"] = sess
        self.cfg["email"] = email
        self.cfg["password"] = password  # chmod 600; convenience re-login
        save_config(self.cfg)
        self.state = r
        log(f"Login OK — user={r.get('user', {}).get('username', '?')} "
            f"coins={r.get('user', {}).get('coins', 0):.2f} "
            f"power={r.get('user', {}).get('miningPower', 0)}")
        return True

    def ensure_login(self) -> bool:
        if not self.cfg.get("lm_session"):
            email = self.cfg.get("email")
            password = self.cfg.get("password")
            if not email or not password:
                log("Belum ada session/email/password. Jalankan: "
                    "python3 lightningminer_auto.py --login EMAIL --password PASS")
                return False
            return self.login(email, password)
        # validate session
        me = self.api("GET", "/me")
        if me.get("ok"):
            self.state = me
            return True
        log(f"Session expired ({me.get('error')}) → re-login…")
        email = self.cfg.get("email")
        password = self.cfg.get("password")
        if email and password:
            return self.login(email, password)
        return False

    def me(self) -> dict:
        r = self.api("GET", "/me")
        if r.get("ok"):
            self.state = r
        return self.state


# ---------------------------------------------------------------- NoneCap


def nonecap_balance(api_key: str) -> Optional[int]:
    try:
        r = requests.get(
            f"{NONECAP_API}/me",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        if r.ok:
            return r.json().get("credits_balance")
    except Exception:
        pass
    return None


def nonecap_solve(api_key: str, sitekey: str, url: str, user_agent: str) -> dict:
    global _nonecap_dead
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {"type": "hcaptcha", "sitekey": sitekey, "url": url}
    if user_agent:
        body["user_agent"] = user_agent
    log(f"  NoneCap hCaptcha… sitekey={sitekey[:8]}…")
    r = requests.post(
        f"{NONECAP_API}/solves",
        params={"wait": 60},
        headers=headers,
        json=body,
        timeout=90,
    )
    data = r.json() if "json" in r.headers.get("Content-Type", "") else {}
    if r.status_code >= 400:
        err = data.get("error") or {}
        if r.status_code == 402 or "insufficient" in str(err.get("code", "")):
            _nonecap_dead = True
            log("  NoneCap kredit habis → semua fitur hCaptcha "
                "dilewati sesi ini (script tetap jalan).")
        raise RuntimeError(
            f"NoneCap HTTP {r.status_code}: {err.get('code')} — {err.get('message')}"
        )
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


def get_nonecap_key(cfg: dict) -> str:
    import os
    if _nonecap_dead:  # kredit habis (402) → anggap tanpa key, jangan spam
        return ""
    return os.environ.get("NONECAP_KEY") or cfg.get("nonecap_key") or ""


# ---------------------------------------------------- hCaptcha multi-provider
# NoneCap (hCaptcha-only) kadang kredit habis. Dispatcher ini mencoba tiap
# provider yang key-nya ada di lm_config.json sampai satu balik token.
# Provider mati permanen (401/402/invalid) di-blacklist sesi ini.

MYTHIX_API = "https://mythixsolve.tech/api"  # docs bilang mythix.io — host aslinya ini (terverifikasi 401 live)   # hCaptcha-only, 1000 kredit gratis signup

HCAPTCHA_ORDER = (
    ("local_hc_url", "Local"),
    ("nonecap_key", "NoneCap"),
    # mythix_key DIHAPUS (keputusan 2026-11-03): token MX1 terbukti palsu.
)
_hc_dead: set = set()


def mythix_solve(api_key: str, sitekey: str, url: str,
                 user_agent: str = "") -> dict:
    """Mint token hCaptcha via MythiX (sync envelope). Balas dict {token}."""
    headers = {"Authorization": f"Bearer {api_key}",
               "Content-Type": "application/json"}
    body = {"captcha_type": "HCaptchaTask", "site_key": sitekey,
            "site_url": url}
    log(f"  MythiX hCaptcha… sitekey={sitekey[:8]}…")
    r = requests.post(f"{MYTHIX_API}/tasks/create", headers=headers,
                      json=body, timeout=90)
    try:
        j = r.json()
    except Exception:
        raise RuntimeError(f"MythiX HTTP {r.status_code} non-JSON: "
                           f"{r.text[:200]}")
    if j.get("errorId"):
        raise RuntimeError(
            f"MythiX error {j.get('errorId')}: {j.get('errorCode')} "
            f"(HTTP {r.status_code})")
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


def has_hcaptcha_key(cfg: dict) -> bool:
    """Ada satu pun key hCaptcha yang belum mati sesi ini?"""
    return any(n not in _hc_dead
               and not (n == "nonecap_key" and _nonecap_dead)
               and get_solver_key(cfg, n)
               for n, _ in HCAPTCHA_ORDER)


def solve_hcaptcha(cfg: dict, sitekey: str, url: str,
                   user_agent: str = "") -> dict:
    """Solve hCaptcha → dict dengan 'token'. Coba tiap provider sampai OK.

    Raise RuntimeError kalau tidak ada key atau semua provider gagal.
    """
    errors: list = []
    tried = False
    for name, label in HCAPTCHA_ORDER:
        if name in _hc_dead:
            continue
        if name == "nonecap_key" and _nonecap_dead:
            continue
        key = get_solver_key(cfg, name)
        if not key:
            continue
        tried = True
        try:
            if name == "local_hc_url":
                d = _solve_local_hcaptcha(cfg, key, sitekey, url, user_agent)
                d.setdefault("provider", "local")
            elif name == "nonecap_key":
                d = nonecap_solve(key, sitekey, url, user_agent)
                d.setdefault("provider", "nonecap")
            else:
                d = mythix_solve(key, sitekey, url, user_agent)
            if d.get("token"):
                return d
            errors.append(f"{label}: token kosong")
        except Exception as e:
            msg = str(e)
            errors.append(f"{label}: {msg}")
            log(f"  {label} hCaptcha gagal: {msg}")
            if re.search(r"401|402|403|invalid.?key|insufficient|"
                         r"zero.?balance|ERROR_KEY|suspended", msg, re.I):
                _hc_dead.add(name)
                log(f"  {label} ditandai mati sesi ini (cek key/kredit).")
    if not tried:
        raise RuntimeError("tanpa key hCaptcha")
    raise RuntimeError("; ".join(errors))


def get_nopecha_key(cfg: dict) -> str:
    import os
    return os.environ.get("NOPECHA_KEY") or cfg.get("nopecha_key") or ""


# ---------------------------------------------------------------- NopeCHA (Turnstile)

NOPECHA_TOKEN_API = "https://api.nopecha.com/token"


def nopecha_turnstile(key: str, sitekey: str, url: str,
                      action: Optional[str] = None,
                      timeout_s: int = 150) -> str:
    """Solve Cloudflare Turnstile via NopeCHA Token API (pure requests).

    Return token string. Raise RuntimeError kalau gagal.
    """
    body: dict = {"type": "turnstile", "sitekey": sitekey, "url": url, "key": key}
    if action:
        body["data"] = {"action": action}
    masked = key[:6] + "…"
    log(f"  NopeCHA turnstile solve… key={masked} site={url[:50]}")
    r = requests.post(NOPECHA_TOKEN_API, json=body, timeout=40)
    rj = r.json()
    if r.status_code >= 400 or rj.get("error"):
        raise RuntimeError(f"NopeCHA POST {r.status_code}: {rj}")
    job = rj.get("data")
    if not job:
        raise RuntimeError(f"NopeCHA: no job id {rj}")
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        time.sleep(3)
        pr = requests.get(
            NOPECHA_TOKEN_API,
            params={"key": key, "id": job},
            timeout=40,
        )
        pj = pr.json()
        data = pj.get("data", "")
        if not data or data == "PENDING":
            continue
        if str(data).startswith("ERROR"):
            raise RuntimeError(f"NopeCHA job error: {data}")
        return data
    raise RuntimeError("NopeCHA: timeout menunggu token")


# ----------------------------------------------------- Turnstile multi-provider
# NoneCap TIDAK bisa Turnstile. Dispatcher ini mencoba tiap key yang ada di
# lm_config.json (atau env) sampai satu berhasil. Key mati (plan/habis) di-
# blacklist sesi ini supaya tidak spam log.

SOLVER_ORDER = (
    ("local_ts_url", "Local"),
    ("xsolve_key", "Xsolve"),
    ("nocaptchaai_key", "NoCaptchaAI"),
    ("peak_key", "Peak"),
    ("capsolver_key", "CapSolver"),
    ("twocaptcha_key", "2Captcha"),
    ("nopecha_key", "NopeCHA"),
)
_solver_dead: set = set()
_nonecap_dead = False  # NoneCap 402 (kredit habis) → hCaptcha dilewati sesi ini
_faucet_no_key_logged = False
_ts_no_key_logged = False
_solver_warned = False


def _poll_task(create_url: str, get_url: str, key_field: str, key_val: str,
               create_body: dict, get_body_extra: dict,
               timeout_s: int = 120) -> str:
    """Pola createTask → getTaskResult (2Captcha-compatible: NCA/CapSolver/2Captcha)."""
    create_body[key_field] = key_val
    r = requests.post(create_url, json=create_body, timeout=40)
    j = r.json()
    if j.get("errorId") or j.get("errorCode") or j.get("error"):
        raise RuntimeError(f"create: {j}")
    tid = j.get("taskId") or j.get("task_id")
    if not tid:
        raise RuntimeError(f"create tanpa taskId: {j}")
    get_body = {key_field: key_val, "taskId": tid}
    get_body.update(get_body_extra)
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        time.sleep(3)
        p = requests.post(get_url, json=get_body, timeout=40).json()
        if p.get("status") in ("ready", "success", "completed"):
            sol = p.get("solution") or p.get("data") or {}
            tok = sol.get("token") if isinstance(sol, dict) else ""
            if tok:
                return tok
            raise RuntimeError(f"ready tanpa token: {p}")
        if p.get("errorId") or p.get("errorCode") or p.get("error"):
            raise RuntimeError(f"result: {p}")
    raise RuntimeError("timeout polling token")


def _solve_nocaptchaai(key: str, sitekey: str, url: str,
                       action: Optional[str], cdata: Optional[str]) -> str:
    task: dict = {"type": "TurnstileTaskProxyLess", "websiteURL": url,
                  "websiteKey": sitekey}
    if action:
        task["action"] = action
    if cdata:
        task["data"] = cdata
    return _poll_task("https://api.nocaptchaai.com/createTask",
                      "https://api.nocaptchaai.com/getTaskResult",
                      "clientKey", key, {"task": task}, {})


def _solve_peak(key: str, sitekey: str, url: str,
                action: Optional[str], cdata: Optional[str]) -> str:
    payload: dict = {"task_type": "turnstiletaskproxyless", "url": url,
                     "sitekey": sitekey}
    if action:
        payload["action"] = action
    if cdata:
        payload["cdata"] = cdata
    r = requests.post("https://api.peak.fo/solve",
                      headers={"X-API-Key": key}, json=payload, timeout=60)
    j = r.json()
    if not j.get("success"):
        raise RuntimeError(f"peak: {j}")
    tok = ((j.get("data") or {}).get("token")) or ""
    if not tok:
        raise RuntimeError(f"peak tanpa token: {j}")
    return tok


def _solve_capsolver(key: str, sitekey: str, url: str,
                     action: Optional[str], cdata: Optional[str]) -> str:
    task: dict = {"type": "AntiTurnstileTaskProxyLess", "websiteURL": url,
                  "websiteKey": sitekey}
    if action or cdata:
        task["metadata"] = {}
        if action:
            task["metadata"]["action"] = action
        if cdata:
            task["metadata"]["cdata"] = cdata
    return _poll_task("https://api.capsolver.com/createTask",
                      "https://api.capsolver.com/getTaskResult",
                      "clientKey", key, {"task": task}, {})


def _solve_2captcha(key: str, sitekey: str, url: str,
                    action: Optional[str], cdata: Optional[str]) -> str:
    task: dict = {"type": "TurnstileTaskProxyless", "websiteURL": url,
                  "websiteKey": sitekey}
    if action:
        task["action"] = action
    if cdata:
        task["data"] = cdata
    return _poll_task("https://api.2captcha.com/createTask",
                      "https://api.2captcha.com/getTaskResult",
                      "clientKey", key, {"task": task}, {})


def _solve_nopecha(key: str, sitekey: str, url: str,
                   action: Optional[str], cdata: Optional[str]) -> str:
    # token API NopeCHA = hanya plan berbayar (free → 402 error 18)
    return nopecha_turnstile(key, sitekey, url, action=action)


# --------------------------------------------------------------- Xsolve
# --- Solver LOKAL (ZYVO-BYPASS) — gratis, jalan di 127.0.0.1:8191/8192 ---
# Dipakai PERTAMA sebelum provider bayar. Kalau lokal mati/gagal → fallback
# ke key berbayar seperti biasa (urutan di SOLVER_ORDER/HCAPTCHA_ORDER).

LOCAL_TS_URL = "http://127.0.0.1:8191"
LOCAL_HC_URL = "http://127.0.0.1:8192"


def _local_post(base: str, payload: dict, timeout: int = 540) -> dict:
    """POST /solve ke service solver lokal. Balas dict JSON-nya."""
    r = requests.post(f"{base.rstrip('/')}/solve", json=payload,
                      timeout=timeout)
    try:
        j = r.json()
    except Exception:
        raise RuntimeError(f"local HTTP {r.status_code} non-JSON: "
                           f"{r.text[:200]}")
    if j.get("token"):
        return j
    status = j.get("status")
    raise RuntimeError(
        f"local {status + ': ' if status else ''}{j.get('error') or j}")


def _solve_local_turnstile(key: str, sitekey: str, url: str,
                           action: Optional[str] = None,
                           cdata: Optional[str] = None) -> str:
    base = (key or LOCAL_TS_URL).strip() or LOCAL_TS_URL
    j = _local_post(base, {"sitekey": sitekey, "siteurl": url,
                           "timeout": 60})
    log(f"  Local Turnstile OK ({len(j['token'])} chars)")
    return j["token"]


def _solve_local_hcaptcha(cfg: dict, key: str, sitekey: str, url: str,
                          user_agent: str = "") -> dict:
    base = (key or LOCAL_HC_URL).strip() or LOCAL_HC_URL
    # timeout 240: phase awal ~90s + AgentV challenge (exec timeout+60,
    # respons +90s) — latensi Gemini 42-93s/call × 2 ronde butuh ruang.
    j = _local_post(base, {"url": url, "sitekey": sitekey, "timeout": 240,
                           "user_agent": user_agent,
                           "gemini_key": (cfg or {}).get("gemini_key") or ""})
    log(f"  Local hCaptcha OK ({len(j['token'])} chars)")
    return {"token": j["token"], "provider": "local"}


# https://xsolve.me — Turnstile + IUAM (BUKAN hCaptcha). Native API:
#   POST https://api.xsolve.me/task  {mode,url,sitekey}  header X-Api-Key
#   → {token, elapsed, status:"completed"}   (sync, rata-rata <3s)
# Balas {status:"failed",message} kalau gagal; kalau dikasih taskId (async)
# → poll POST /getTaskResult {clientKey,taskId} → solution.token.

XSOLVE_TASK_API = "https://api.xsolve.me/task"
XSOLVE_RESULT_API = "https://api.xsolve.me/getTaskResult"


def _solve_xsolves(key: str, sitekey: str, url: str,
                   action: Optional[str], cdata: Optional[str]) -> str:
    payload: dict = {"mode": "turnstile", "url": url, "sitekey": sitekey}
    if action:
        payload["action"] = action
    if cdata:
        payload["cdata"] = cdata
    r = requests.post(XSOLVE_TASK_API, headers={"X-Api-Key": key},
                      json=payload, timeout=90)
    try:
        j = r.json()
    except Exception:
        raise RuntimeError(f"xsolve HTTP {r.status_code} non-JSON: "
                           f"{r.text[:200]}")
    tok = j.get("token") or ""
    if tok and str(j.get("status", "completed")) in ("completed", "ready",
                                                     "success"):
        return tok
    tid = j.get("taskId") or j.get("task_id")
    if tid:  # mode async → poll
        t0 = time.time()
        while time.time() - t0 < 90:
            time.sleep(3)
            p = requests.post(XSOLVE_RESULT_API,
                              json={"clientKey": key, "taskId": tid},
                              timeout=40).json()
            if p.get("status") in ("ready", "success", "completed"):
                sol = p.get("solution") or {}
                tok = sol.get("token") or sol.get("value") or ""
                if tok:
                    return tok
                raise RuntimeError(f"xsolve ready tanpa token: {p}")
            if p.get("errorId") or p.get("errorCode") or p.get("error"):
                raise RuntimeError(f"xsolve result: {p}")
        raise RuntimeError("xsolve: timeout polling token")
    raise RuntimeError(f"xsolve HTTP {r.status_code}: {j}")


_SOLVERS = {
    "local_ts_url": _solve_local_turnstile,
    "xsolve_key": _solve_xsolves,
    "nocaptchaai_key": _solve_nocaptchaai,
    "peak_key": _solve_peak,
    "capsolver_key": _solve_capsolver,
    "twocaptcha_key": _solve_2captcha,
    "nopecha_key": _solve_nopecha,
}


def get_solver_key(cfg: dict, name: str) -> str:
    return (os.environ.get(name.upper()) or cfg.get(name) or "").strip()


def has_turnstile_key(cfg: dict) -> bool:
    return any(get_solver_key(cfg, n) and n not in _solver_dead
               for n, _ in SOLVER_ORDER)


def solve_turnstile(cfg: dict, sitekey: str, url: str,
                    action: Optional[str] = None,
                    cdata: Optional[str] = None) -> str:
    """Solve Turnstile → token. Coba semua key yang ada sampai berhasil.

    Raise RuntimeError kalau tidak ada key atau semua provider gagal.
    """
    global _solver_warned
    errors: list = []
    tried = False
    for name, label in SOLVER_ORDER:
        if name in _solver_dead:
            continue
        key = get_solver_key(cfg, name)
        if not key:
            continue
        tried = True
        try:
            log(f"  Turnstile via {label}…")
            tok = _SOLVERS[name](key, sitekey, url, action, cdata)
            if tok:
                log(f"  {label} OK ({len(tok)} chars)")
                return tok
            errors.append(f"{label}: token kosong")
        except Exception as e:
            msg = str(e)
            errors.append(f"{label}: {msg}")
            log(f"  {label} gagal: {msg}")
            # key mati permanen (plan/habis/salah) → blacklist sesi ini
            if re.search(r"402|401|error.?18|invalid key|out of credit|"
                         r"error.?16|error.?15|ERROR_KEY|plan|"
                         r"insufficient|balance", msg, re.I):
                _solver_dead.add(name)
                log(f"  {label} ditandai mati sesi ini (cek key/plan).")
    if not tried:
        global _ts_no_key_logged
        if not _ts_no_key_logged:
            log("  Tanpa Turnstile solver key — PTC & shortlink captcha "
                "dilewati (script tetap jalan tanpa key).")
            _ts_no_key_logged = True
        raise RuntimeError("tanpa Turnstile key")
    raise RuntimeError("semua solver gagal: " + " | ".join(errors))


def _cw_match_x(img, piece, y: int, size: int, mx: int) -> int:
    """Posisi x terbaik utk slider CWCaptcha — edge-NCC + interior."""
    from PIL import Image as _Image, ImageFilter as _ImageFilter
    bge = img.convert("L").filter(_ImageFilter.FIND_EDGES)
    bgl = bge.load()
    bgr = img.load()
    pl = piece.load()
    parr = []
    prgb = _Image.new("RGB", (size, size), (0, 0, 0))
    prr = prgb.load()
    for py in range(size):
        for px in range(size):
            rr_, g, b, a = pl[px, py]
            if a > 128:
                lum = int(0.299 * rr_ + 0.587 * g + 0.114 * b)
                parr.append((px, py, rr_, g, b, lum))
                prr[px, py] = (lum, lum, lum)
    if not parr:
        return 0
    pee = prgb.filter(_ImageFilter.FIND_EDGES).convert("L")
    pel = pee.load()
    best_sc, best_x = -9e9, 0
    for x in range(mx + 1):
        if x + size > img.size[0]:
            break
        bv, pv, itot = [], [], 0
        for px, py, rr_, g, b, lum in parr:
            bv.append(bgl[x + px, y + py])
            pv.append(pel[px, py])
            br, bgc, bb = bgr[x + px, y + py]
            itot += abs(br - rr_) + abs(bgc - g) + abs(bb - b)
        n = len(bv)
        mb = sum(bv) / n
        mp = sum(pv) / n
        num = sum((bv[i] - mb) * (pv[i] - mp) for i in range(n))
        db = sum((v - mb) ** 2 for v in bv) ** 0.5
        dp = sum((v - mp) ** 2 for v in pv) ** 0.5
        ncc = num / (db * dp) if db and dp else 0
        sc = ncc * 100 - (itot / n) * 0.1
        if sc > best_sc:
            best_sc, best_x = sc, x
    return best_x


def solve_cwcaptcha(ext: requests.Session, sitekey: str, action: str,
                    origin: str) -> Optional[str]:
    """CWCaptcha (cronweb) → token `cw_t_…`. Widget POST /api/v1/challenge;
    type checkbox = auto {human:true}; slider = template-match edge-NCC.
    Lainnya (logic/icon/image) di-skip + retry. Return token atau None.
    """
    import base64 as _b64
    from io import BytesIO as _BytesIO
    from PIL import Image as _Image
    for _att in range(8):
        try:
            chan = "cw_f_" + _b64.urlsafe_b64encode(os.urandom(32)).decode().rstrip("=")
            rw = ext.get(
                "https://captcha.cronweb.co/widget",
                params={"sitekey": sitekey, "action": action, "origin": origin,
                        "channel": chan, "theme": "light", "language": "en",
                        "ui": "1.4.0-rc.1"},
                timeout=15, headers={"Referer": origin + "/"})
            mc = re.search(r'id="cw-config"[^>]*>(.*?)</script>', rw.text, re.S)
            if not mc:
                log("  CWCaptcha: widget tanpa config")
                return None
            sess = json.loads(mc.group(1))["session"]
            H = {"Content-Type": "application/json",
                 "Authorization": "Bearer " + sess,
                 "Origin": "https://captcha.cronweb.co",
                 "Referer": "https://captcha.cronweb.co/widget"}
            t_ch = time.time()
            rc = ext.post("https://captcha.cronweb.co/api/v1/challenge",
                          headers=H, json={"accessible": False}, timeout=20)
            dj = rc.json()
            if not dj.get("success"):
                time.sleep(3)
                continue
            ch = dj["challenge"]
            if ch["type"] == "checkbox":
                time.sleep(1.6)
                rs = ext.post(
                    "https://captcha.cronweb.co/api/v1/solve", headers=H,
                    json={"challenge_id": ch["id"], "nonce": ch["nonce"],
                          "answer": {"human": True}}, timeout=20)
            elif ch["type"] == "slider":
                cf = ch["config"]
                ri = ext.get("https://captcha.cronweb.co" + cf["image"],
                             headers=H, timeout=15)
                rp = ext.get("https://captcha.cronweb.co" + cf["piece"],
                             headers=H, timeout=15)
                img = _Image.open(_BytesIO(ri.content)).convert("RGB")
                piece = _Image.open(_BytesIO(rp.content)).convert("RGBA")
                x = _cw_match_x(img, piece, cf["y"], cf["size"], cf["max"])
                time.sleep(max(0, 1.2 - (time.time() - t_ch)))
                rs = ext.post(
                    "https://captcha.cronweb.co/api/v1/solve", headers=H,
                    json={"challenge_id": ch["id"], "nonce": ch["nonce"],
                          "answer": {"x": x, "trace": [
                              {"x": 0, "t": 0},
                              {"x": max(1, x // 2), "t": 330},
                              {"x": x, "t": 710}]}}, timeout=20)
                log(f"  CWCaptcha slider x={x}")
            else:
                ext.post("https://captcha.cronweb.co/api/v1/cancel",
                         headers=H, json={}, timeout=10)
                time.sleep(1.5)
                continue
            sdj = rs.json()
            tok = sdj.get("token") or ""
            if sdj.get("success") and tok:
                return tok
            log(f"  CWCaptcha solve: {rs.status_code} {rs.text[:120]}")
        except Exception as e:
            log(f"  CWCaptcha err: {e}")
        time.sleep(2)
    return None


# ---------------------------------------------------------------- actions


def fake_interaction(elapsed_s: float) -> dict:
    """Snapshot interaksi manusia-plausibel untuk body /api/faucet."""
    ms = int(elapsed_s * 1000)
    return {
        "elapsedMs": ms,
        "focusMs": max(100, ms - random.randint(50, 400)),
        "pointerDowns": random.randint(1, 3),
        "pointerUps": random.randint(1, 3),
        "pointerMoves": random.randint(8, 40),
        "touchStarts": random.randint(0, 2),
        "keydowns": random.randint(0, 2),
        "scrolls": random.randint(0, 8),
        "untrustedEvents": 0,
        "visible": True,
    }


def do_sync(c: LMClient) -> dict:
    r = c.api("POST", "/sync-mining", {})
    if r.get("ok"):
        u = r.get("user") or {}
        settled = u.get("settledCryptoBalanceAtomic", 0)
        pend = u.get("pendingMiningAtomic", 0)
        coins = u.get("coins", 0)
        log(f"Sync-mining OK — coins={coins:.2f} "
            f"settled={settled} atomic pend={pend}")
        c.state.update({k: r[k] for k in ("user", "facility") if k in r})
    else:
        log(f"Sync-mining gagal: {r.get('error')}")
    return r


def do_faucet(c: LMClient, cfg: dict) -> bool:
    global _faucet_no_key_logged
    if not has_hcaptcha_key(cfg):
        if not _faucet_no_key_logged:
            log("Faucet: tanpa API key hCaptcha — dilewati "
                "(script tetap jalan tanpa key).")
            _faucet_no_key_logged = True
        return False
    cap = c.api("GET", "/faucet/captcha")
    if not cap.get("ok"):
        log(f"Faucet captcha info gagal: {cap.get('error')}")
        return False
    provider = cap.get("provider")
    sitekey = cap.get("siteKey") or FAUCET_SITEKEY
    if provider != "hcaptcha":
        log(f"Faucet provider={provider} (bukan hCaptcha) — skip.")
        return False
    chal = c.api("GET", "/faucet/challenge")
    if not chal.get("ok"):
        log(f"Faucet challenge gagal: {chal.get('error')}")
        return False
    claim_token = chal.get("claimToken")
    ready_at = chal.get("readyAt")
    min_wait = chal.get("minWaitSeconds", 8)
    if not claim_token:
        log("Faucet: claimToken kosong — skip.")
        return False
    # solve captcha dulu (butuh waktu ~10-30s) sambil menunggu readyAt
    try:
        solve = solve_hcaptcha(cfg, sitekey, f"{BASE}/", UA)
    except Exception as e:
        log(f"hCaptcha solve gagal: {e}")
        return False
    captcha_token = solve.get("token")
    via = solve.get("provider", "?")
    # tunggu readyAt kalau masih di masa depan
    if ready_at:
        try:
            # readyAt mungkin epoch ms atau ISO
            if isinstance(ready_at, (int, float)) and ready_at > 1e12:
                wait_s = ready_at / 1000 - time.time()
            elif isinstance(ready_at, (int, float)):
                wait_s = ready_at - time.time()
            else:
                dt = datetime.fromisoformat(str(ready_at).replace("Z", "+00:00"))
                wait_s = dt.timestamp() - time.time()
            if wait_s > 0:
                log(f"  Tunggu readyAt {wait_s:.1f}s…")
                time.sleep(wait_s + jitter(0.8, 0.3))
        except Exception as e:
            log(f"  Parse readyAt gagal ({e}) → tunggu minWait {min_wait}s")
            time.sleep(min_wait + jitter(1.0, 0.4))
    else:
        time.sleep(min_wait + jitter(1.0, 0.4))
    interaction = fake_interaction(max(min_wait + 2, 9.5))
    r = c.api(
        "POST",
        "/faucet",
        {
            "captchaToken": captcha_token,
            "claimToken": claim_token,
            "interaction": interaction,
        },
    )
    if r.get("ok"):
        claimed = r.get("claimedCoins", 0)
        extra = ""
        if via == "nonecap":
            nk = get_solver_key(cfg, "nonecap_key")
            if nk:
                extra = f" (sisa NoneCap ~{nonecap_balance(nk)})"
        log(f"FAUCET claim OK +{claimed} coins via {via}{extra}")
        c.me()
        return True
    log(f"Faucet claim gagal: {r.get('error')}")
    return False


def do_daily(c: LMClient) -> None:
    r = c.api("POST", "/daily-bonus", {})
    if r.get("ok"):
        log(f"Daily-bonus OK: {r}")
        c.me()
    else:
        err = str(r.get("error", ""))
        if "cool" in err.lower() or "cooldown" in err.lower():
            log(f"Daily-bonus masih cooldown: {err}")
        else:
            log(f"Daily-bonus: {err}")


def do_quests(c: LMClient) -> None:
    r = c.api("GET", "/quests")
    if not r.get("ok"):
        log(f"Quests load gagal: {r.get('error')}")
        return
    quests = r.get("quests") or []
    claimed = 0
    for q in quests:
        if q.get("canClaim") and q.get("complete") and not q.get("claimed"):
            cr = c.api("POST", "/quests/claim", {"questId": q.get("id")})
            if cr.get("ok"):
                claimed += 1
                log(f"  Quest claim: {q.get('title', q.get('id'))} "
                    f"+{q.get('rewardAtomic')} {q.get('rewardCurrency', '')}")
            else:
                log(f"  Quest claim gagal {q.get('id')}: {cr.get('error')}")
            sleep_humans(0.8, 0.3)
    ready = sum(1 for q in quests if q.get("canClaim") and q.get("complete"))
    log(f"Quests: {len(quests)} total, {ready} siap, {claimed} diklaim")


def do_battlepass(c: LMClient) -> None:
    r = c.api("GET", "/battlepass")
    if not r.get("ok"):
        log(f"Battlepass load gagal: {r.get('error')}")
        return
    season = r.get("season") or {}
    season_key = season.get("key") or season.get("id") or r.get("seasonKey")
    n = 0
    for t in r.get("tasks") or []:
        if t.get("canClaim") and t.get("complete") and not t.get("claimed"):
            body = {"taskId": t.get("id"), "seasonKey": season_key}
            cr = c.api("POST", "/battlepass/tasks/claim", body)
            if cr.get("ok"):
                n += 1
                log(f"  BP task claim: {t.get('id')} +{t.get('bpXp')} xp")
            else:
                log(f"  BP task gagal {t.get('id')}: {cr.get('error')}")
            sleep_humans(0.6, 0.2)
    for lv in r.get("levels") or []:
        for track_name in ("free", "premium"):
            track = lv.get(track_name)
            if (
                isinstance(track, dict)
                and track.get("canClaim")
                and not track.get("claimed")
            ):
                body = {
                    "level": lv.get("level") or lv.get("index"),
                    "track": track_name,
                    "seasonKey": season_key,
                }
                cr = c.api("POST", "/battlepass/rewards/claim", body)
                if cr.get("ok"):
                    n += 1
                    log(f"  BP reward claim: L{body['level']} {track_name}")
                else:
                    log(f"  BP reward gagal L{body['level']} {track_name}: "
                        f"{cr.get('error')}")
                sleep_humans(0.6, 0.2)
    log(f"Battlepass: {n} klaim")


def do_shop(c: LMClient, cfg: dict) -> None:
    """Beli miner ROI terbaik (basePower/cost) + upgrade murah."""
    me = c.me()
    user = me.get("user") or {}
    coins = float(user.get("coins") or 0)
    catalog = me.get("catalog") or []
    owned_ids = set()
    owned_rows = {}
    # /me: top-level miners[] dengan key miner_id
    for row in me.get("miners") or []:
        mid = row.get("miner_id") or row.get("minerId") or row.get("id")
        if mid:
            owned_ids.add(mid)
            owned_rows[mid] = row

    buffer = float(cfg.get("shop_buffer", 0))
    buys = 0
    # beli dulu yang murah → mahal (power naik bertahap), semua affordable
    candidates = []
    for m in catalog:
        mid = m.get("id")
        cost = float(m.get("cost") or 0)
        base_p = float(m.get("basePower") or 0)
        if not mid or cost <= 0 or mid in owned_ids:
            continue
        if mid.startswith("lightning-quest-miner") or base_p <= 0:
            continue
        roi = base_p / cost if cost else 0
        candidates.append((cost, -roi, m))  # termurah dulu; roi tiebreak
    candidates.sort()
    for cost, _nroi, m in candidates:
        if coins < cost + buffer:
            continue
        r = c.api("POST", "/buy-miner", {"minerId": m.get("id")})
        if r.get("ok"):
            coins -= cost
            buys += 1
            log(f"  Beli miner: {m.get('id')} −{cost:.0f} coins "
                f"(power +{m.get('basePower')})")
            sleep_humans(0.7, 0.3)
        else:
            log(f"  Beli {m.get('id')} gagal: {r.get('error')}")
    # upgrade: server menyatakan "Miner upgrades are retired" → jangan coba lagi
    if buys:
        log(f"Shop: {buys} beli, sisa coins≈{coins:.2f}")


def do_facility(c: LMClient, cfg: dict) -> None:
    me = c.me()
    user = me.get("user") or {}
    coins = float(user.get("coins") or 0)
    buffer = float(cfg.get("shop_buffer", 0))

    # Energy cell: hanya saat energy hampir habis (<12 jam) — jangan tiap tick.
    expiry_ms = user.get("miningEnergyExpiresAt") or 0
    hours_left = (expiry_ms / 1000 - time.time()) / 3600 if expiry_ms else 999
    if hours_left < 12:
        ec = c.api("GET", "/facility/energy-cells")
        if ec.get("ok"):
            cells = ec.get("cells") or []
            # cell 24h paling hemat prioritas; pilih termurah yang cukup
            cells_sorted = sorted(cells, key=lambda x: float(x.get("priceCoins") or 0))
            for cell in cells_sorted:
                cid = cell.get("id")
                price = float(cell.get("priceCoins") or 0)
                if not cid or price <= 0 or coins < price + buffer:
                    continue
                r = c.api(
                    "POST",
                    "/facility/energy-cells/buy",
                    {"cellId": cid, "requestId": str(uuid.uuid4())},
                )
                if r.get("ok"):
                    log(f"  Energy-cell {cid} −{price:.0f} coins "
                        f"(sisa energy {hours_left:.1f}h)")
                    sleep_humans(0.5, 0.2)
                    break
                log(f"  Energy-cell {cid} gagal: {r.get('error')}")
                break
    else:
        log(f"  Energy {hours_left:.1f}h masih aman — cell ditahan.")

    # Rack: buy hanya menaikkan owned, installed stuck (butuh proses lain)
    # → jangan beli tiap tick (boros). Cek dulu: kalau installed < owned,
    # artinya rack cadangan belum terpasang, buy percuma.
    rs = c.api("GET", "/facility/rack-shop")
    if rs.get("ok"):
        owned = int(rs.get("owned") or 0)
        installed = int(rs.get("installed") or 0)
        if installed >= owned:
            price = float(rs.get("priceCoins") or 0)
            if price > 0 and coins >= price + buffer:
                r = c.api("POST", "/facility/rack-shop/buy", {})
                if r.get("ok"):
                    log(f"  Rack +1 −{price:.0f} coins (owned {owned}→"
                        f"{owned + 1}, installed {installed})")
                    sleep_humans(0.5, 0.2)
        else:
            log(f"  Rack: installed {installed}/{owned} — buy tidak "
                f"menaikkan installed, ditahan.")

    # recharge energy (butuh syarat shortlink/hari pertama)
    me = c.me()
    fac = me.get("facility") or {}
    user = me.get("user") or {}
    if user.get("firstEnergyRechargeAvailable") or user.get("canRechargeEnergy"):
        cost = float(user.get("energyRechargeRequiredCoins") or 10)
        if user.get("firstEnergyRechargeAvailable") or coins >= cost + buffer:
            r = c.api("POST", "/recharge-energy", {})
            if r.get("ok"):
                log(f"  Recharge-energy OK (−{cost:.0f} coins jika dikenakan)")
            else:
                log(f"  Recharge-energy: {r.get('error')}")


_sl_state: dict = {}      # id shortlink → epoch terakhir GAGAL (retry nanti)
SL_RETRY_GAP = 900        # detik: gagal baru boleh dicoba ulang
_sl_tried_total: set = set()


def _extract_sl_continue(text: str) -> tuple[Optional[str], int]:
    """Deteksi pola timer-only shortlink. Return (next_url, wait_seconds) | (None, 0).

    Dua pola terbukti credit (2026-11-01):
      A) bces2: id="continueButton" href=… + id="timerCount">N<
      B) lq/trxminer: var destination = "…" + id="partnerShortlinkTimer">N<
    Pola Turnstile (cxl advance, shrink*) sengaja TIDAK dikenali → skip.
    """
    m = re.search(r'id="continueButton"[^>]*href="([^"]+)"', text)
    if m:
        wt = re.search(r'id="timerCount">(\d+)<', text)
        return html_mod.unescape(m.group(1)), int(wt.group(1)) if wt else 12
    m = re.search(r'var destination = "([^"]+)"', text)
    if m:
        wt = re.search(r'id="partnerShortlinkTimer">(\d+)<', text)
        return html_mod.unescape(m.group(1)), int(wt.group(1)) if wt else 10
    return None, 0


def parse_captcha_widget(page: str) -> tuple:
    """Deteksi widget captcha di HTML → (kind, sitekey, action).

    kind: "hcaptcha" | "turnstile" | None.
    Urutan: div asli (h-captcha/cf-turnstile) → config JSON halaman
    ("captcha_type"/…_site_key) → data-sitekey → literal 0x4AAAAAA.
    data-action div WAJIB dibawa (CXL butuh "shortlink_complete" —
    tanpa action token ditolak server: "security check could not be
    verified", terbukti 2026-11-01).
    """
    mh = re.search(r'<div[^>]*class="[^"]*h-captcha[^"]*"[^>]*>', page, re.I)
    if mh:
        sk = re.search(r'data-sitekey="([^"]+)"', mh.group(0))
        if sk:
            return "hcaptcha", sk.group(1), None
    mt = re.search(r'<div[^>]*class="[^"]*cf-turnstile[^"]*"[^>]*>',
                   page, re.I)
    if mt:
        tag = mt.group(0)
        sk = re.search(r'data-sitekey="([^"]+)"', tag)
        if sk:
            ac = re.search(r'data-action="([^"]*)"', tag)
            return "turnstile", sk.group(1), \
                (ac.group(1) or None) if ac else None
    ctype = re.search(r'"captcha_type"\s*:\s*"([a-z_]+)"', page)
    if ctype and ctype.group(1) == "hcaptcha":
        sk = re.search(r'"hcaptcha_checkbox_site_key"\s*:\s*"([0-9a-zA-Z-]{8,})"',
                       page)
        if sk and sk.group(1):
            return "hcaptcha", sk.group(1), None
        m = re.search(r'data-sitekey="([0-9xX][A-Za-z0-9_-]+)"', page)
        if m:
            return "hcaptcha", m.group(1), None
    sk = re.search(r'"turnstile_site_key"\s*:\s*"(0x[0-9a-zA-Z_-]+)"', page)
    if sk:
        ac = re.search(r'data-action="([^"]+)"', page)
        return "turnstile", sk.group(1), (ac.group(1) if ac else None)
    m = re.search(r'data-sitekey="([0-9xX][A-Za-z0-9_-]+)"', page)
    if m:
        return ("hcaptcha" if "h-captcha" in page else "turnstile"), \
            m.group(1), None
    m = re.search(r'0x4AAAAAA[A-Za-z0-9_-]+', page)
    if m:
        ac = re.search(r'data-action="([^"]+)"', page)
        return "turnstile", m.group(0), (ac.group(1) if ac else None)
    return None, None, None


def _cxl_advance(ext: requests.Session, page: str, url: str,
                 cfg: dict) -> tuple[Optional[str], bool]:
    """Handle halaman checkpoint CXL: POST {origin}/api/shortlink/advance.

    Return (next_url, done). next_url None + done False = gagal.
    """
    msid = re.search(r'const sessionId="([^"]+)"', page)
    # pola asli: step=0,finalStep=step===3  (finalStep dihitung dari step)
    mstep = re.search(r'step=(\d+),finalStep=(?:step===(\d+)|(true|false))',
                      page)
    if not msid or not mstep:
        return None, False
    step_i = int(mstep.group(1))
    if mstep.group(2) is not None:
        final = step_i == int(mstep.group(2))
    else:
        final = mstep.group(3) == "true"
    token = ""
    if final:
        kind, sitekey, ts_action = parse_captcha_widget(page)
        if not sitekey:
            log("  CXL: sitekey turnstile tidak ditemukan di final page")
            return None, False
        try:
            # action div (shortlink_complete) harus ikut — tanpa itu
            # server tolak: "The security check could not be verified"
            token = solve_turnstile(cfg, sitekey, url, action=ts_action)
        except Exception as e:
            log(f"  CXL: turnstile gagal: {e}")
            return None, False
    # server paksa timer 10s per checkpoint (429 "keep checkpoint open")
    time.sleep(10.6 + random.uniform(0.3, 1.2))
    adv_body = {"sessionId": msid.group(1), "step": step_i,
                "turnstileToken": token}
    r3 = ext.post(urljoin(url, "/api/shortlink/advance"),
                  json=adv_body, timeout=25)
    if r3.status_code == 429:
        m429 = re.search(r'(\d+)\s*more seconds', r3.text)
        if m429:
            log(f"  CXL: tunggu {m429.group(1)}s lagi (server timer)…")
            time.sleep(int(m429.group(1)) + random.uniform(0.5, 1.5))
            r3 = ext.post(urljoin(url, "/api/shortlink/advance"),
                          json=adv_body, timeout=25)
    if r3.status_code >= 400:
        try:
            err = r3.json().get("error") or f"HTTP {r3.status_code}"
        except Exception:
            err = f"HTTP {r3.status_code}"
        log(f"  CXL advance: {err}")
        return None, False
    data = r3.json()
    nxt = data.get("nextUrl") or data.get("completeUrl")
    return (urljoin(url, nxt) if nxt else None), (nxt is None)


def _dump_debug(text: str, tag: str) -> None:
    """Simpan HTML halaman gagal ke debug/ untuk diagnosa (max 20 file)."""
    try:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "debug")
        os.makedirs(d, exist_ok=True)
        old = sorted(f for f in os.listdir(d) if f.endswith(".html"))
        for f in old[:-20]:
            os.remove(os.path.join(d, f))
        p = os.path.join(d,
                         f"{tag}_{time.strftime('%H%M%S')}.html")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        log(f"  debug HTML → {p}")
    except Exception:
        pass


def _shrink_captcha(ext: requests.Session, page: str, url: str,
                    cfg: dict) -> Optional[Any]:
    """POST form langkah shortlink (shrink srnky/shrinkearn + exeygo family).

    Kenali form pertama yang punya `_token` (Laravel) atau widget Turnstile;
    solve Turnstile-nya kalau ada, lalu POST. Return objek Response hasil
    POST (caller proses isinya langsung — GET ulang bisa reset state),
    None kalau tidak ada form yang valid / solve gagal.
    """
    chosen = None
    for mform in re.finditer(
        r'<form[^>]*action="([^"]+)"[^>]*>(.*?)</form>', page, re.S
    ):
        action, inner = mform.group(1), mform.group(2)
        if "locale" in action or 'name="locale"' in inner:
            continue
        has_token = 'name="_token"' in inner
        has_ts = "turnstile" in inner.lower()
        if has_token or has_ts:
            chosen = (action, inner)
            break
    if not chosen:
        log("  shrink_captcha: form _token/turnstile tak dikenali di halaman")
        _dump_debug(page, "shrinkcap_noform")
        return None
    action, inner = chosen
    fields: dict = {}
    for mi in re.finditer(r'<input[^>]*name="([^"]+)"[^>]*>', inner):
        name = mi.group(1)
        mv = re.search(r'value="([^"]*)"', mi.group(0))
        fields[name] = html_mod.unescape(mv.group(1)) if mv else ""
    # widget di halaman (bukan di form): div / config JSON / literal
    inner_low = inner.lower()
    form_captcha = any(w in inner_low for w in
                       ("turnstile", "h-captcha", "hcaptcha", "recaptcha",
                        "captcha"))
    if form_captcha:
        kind, sitekey, ts_action = parse_captcha_widget(page)
        if not sitekey:
            msk = re.search(
                r'turnstile_site_key\\?":\\?"([0-9xX][A-Za-z0-9_-]+)', page)
            if not msk:
                msk = re.search(r'data-sitekey="([0-9xX][A-Za-z0-9_-]+)"',
                                page)
            if not msk:
                msk = re.search(r'0x4AAAAAA[A-Za-z0-9_-]+', page)
            if msk:
                kind, sitekey = "turnstile", msk.group(1)
        if not sitekey:
            log("  form captcha tapi sitekey tak terbaca — dilewati")
            return None
        token = ""
        if kind == "hcaptcha":
            if not has_hcaptcha_key(cfg):
                log("  hCaptcha form: butuh nonecap_key/mythix_key — dilewati")
                return None
            try:
                token = (solve_hcaptcha(cfg, sitekey, url, UA)
                         .get("token")) or ""
            except Exception as e:
                log(f"  hCaptcha form gagal: {e}")
                return None
            resp_field = "h-captcha-response"
        else:
            try:
                token = solve_turnstile(cfg, sitekey, url, action=ts_action)
            except Exception as e:
                log(f"  turnstile form gagal: {e}")
                return None
            resp_field = "cf-turnstile-response"
        if not token:
            return None
        # field respons: pakai nama input yang ada di form, atau nama
        # standar. visit_token HANYA kalau form memang punya input itu —
        # field asing bikin CakePHP FormProtection tolak POST (HTTP 400,
        # terbukti di shrinkme.click 2026-11-01).
        tk_name = next((k for k in fields
                        if "turnstile" in k.lower()
                        or "captcha" in k.lower()
                        or "response" in k.lower()), None)
        if tk_name:
            fields[tk_name] = token
        fields[resp_field] = token
        if "visit_token" in fields:
            fields["visit_token"] = token
    try:
        r2 = ext.post(urljoin(url, html_mod.unescape(action)),
                      data=fields, timeout=30,
                      allow_redirects=True)
    except requests.RequestException as e:
        log(f"  POST form gagal: {e}")
        return None
    if r2.status_code >= 400:
        log(f"  shrink_captcha: POST {r2.status_code} ditolak "
            f"({action[:60]})")
        return None
    return r2


def _fnv_fp(ua: str) -> str:
    """Fingerprint 16-hex ala gateway.js ShrinkMe (FNV-ish dobel, 32-bit).

    src = UA|screen|timezone|language|gl|hardwareConcurrency — server
    memakai fp sebagai penanda device; nilai konstan per sesi cukup.
    """
    src = f"{ua}|1920x1080x24|Asia/Jakarta|id-ID||8"
    h1, h2 = 0x811c9dc5, 0x01000193
    for ch in src:
        c = ord(ch)
        h1 = ((h1 ^ c) * 16777619) & 0xFFFFFFFF
        h2 = ((h2 ^ c) * 2246822519) & 0xFFFFFFFF
    return f"{h1:08x}{h2:08x}"


def _shrinkme_sig() -> str:
    """JSON 'sig' perilaku manusia untuk /go/arm & /go/next (dinilai
    server: mousemove/scroll/visibility/fingerprint — bukan captcha)."""
    sig = {
        "m": random.randint(25, 90),       # mousemove
        "tc": random.randint(0, 4),        # touch
        "sc": random.randint(4, 18),       # scroll
        "k": random.randint(0, 2),         # keydown
        "t": random.randint(1, 6),         # putaran mouse
        "cl": [[round(random.uniform(-12, 12), 1),
                round(random.uniform(-8, 8), 1), 1]],
        "v": random.randint(9000, 16000),  # visible ms
        "wd": 0, "hl": 0, "gl": 0,         # webdriver/headless/swiftshader
        "ow": 1920,
        "fp": _fnv_fp(UA),
    }
    return json.dumps(sig, separators=(",", ":"))


def _shrink_article_form(html: str) -> Optional[tuple]:
    """Kenali form keluarga shrink multi-article (ShrinkPe/ShrinkBixby).

    Halaman pertama: field mysite+visit_token+token+alias → POST ke artikel
    publisher. Artikel lanjutan: field next_page+token+alias (id getmylink /
    go_d2 / nextpage) → POST artikel berikutnya. Return (action, fields).
    """
    for fm in re.finditer(r"<form([^>]*)>(.*?)</form>", html, re.I | re.S):
        attrs, inner = fm.group(1), fm.group(2)
        fields: dict = {}
        for mi in re.finditer(r"<input([^>]*)>", inner, re.I):
            n = re.search(r'name="([^"]+)"', mi.group(1))
            if not n:
                continue
            v = re.search(r'value="([^"]*)"', mi.group(1))
            fields[n.group(1)] = html_mod.unescape(v.group(1)) if v else ""
        if not fields:
            continue
        first = ("mysite" in fields and "visit_token" in fields
                 and "token" in fields and "alias" in fields)
        # artikel lanjutan: next_page ADA (step antara) atau TIDAK ADA
        # (step terakhir → balik ke shortener, field url=shortlink)
        nxt = ("token" in fields and "alias" in fields
               and ("next_page" in fields or "url" in fields))
        if first or nxt:
            am = re.search(r'action="([^"]*)"', attrs)
            # WAJIB unescape: action bisa bawa &amp;s=<sig> — tanpa unescape
            # server terima "amp;s" (param s hilang) → signature ditolak →
            # balik halaman wall terus (bukti replay G/H 2026-11-09 22:1x).
            return (html_mod.unescape(am.group(1)) if am else ""), fields
    return None


def _shrink_article_chain(ext: requests.Session, page: str, url: str,
                          cfg: dict, c: Optional["LMClient"] = None
                          ) -> Optional[Any]:
    """Walk rantai artikel shrink family sampai halaman final /links/go.

    Alur terbukti 2026-11-02 (ShrinkBixby CREDITED +50, Shrink.pe pola sama):
    lnbzi/aii.sh (form mysite) → artikel publisher ×2 (getmylink/go_d2) →
    balik ke domain shortener → halaman timer + Turnstile + /links/go →
    _shrinkme_final (XHR) → complete LM.
    Client-side gate (tombol disabled / timer 15s) TANPA verifikasi server
    pada POST antar artikel — POST form fields saja cukup.
    Return Response (LM complete / halaman final) atau None.
    """
    html, cur = page, url
    # 2026-11-09: cap 16 (pool artikel berputar), stall = d BERULANG
    # (s bisa rotate, d = isi langkah — beda d = maju).
    prev_d = ""
    for step in range(1, 17):
        if 'action="/links/go"' in html:
            log(f"  Shrink-article: final /links/go di step {step}")
            return _shrinkme_final(ext, html, cur, cfg, c=c)
        parsed = _shrink_article_form(html)
        if not parsed:
            log(f"  Shrink-article step{step}: form tak dikenali "
                f"({cur[:70]})")
            return None
        action, fields = parsed
        parts = urlsplit(cur)
        origin = f"{parts.scheme}://{parts.netloc}"
        target = urljoin(cur, action) if action else cur
        log(f"  Shrink-article step{step} → {target[:75]}")
        md = re.search(r"[?&]d=([^&]+)", target)
        d_now = md.group(1) if md else target
        if d_now == prev_d:
            log("  Shrink-article: d berulang (server tak maju) "
                "— stop, HTML disimpan")
            _dump_debug(html, "shrink_stall")
            return None
        prev_d = d_now
        # continue-page shrink script (app_vars.captcha_shortlink=yes,
        # dump 2026-11-09): widget #captchaShortlink + Turnstile — POST
        # tanpa token bikin server balikin halaman SAMA (loop tanpa maju).
        if "captchaShortlink" in html:
            kind, sitekey, ts_action = parse_captcha_widget(html)
            if not sitekey:
                log("  Shrink-article: captcha tanpa sitekey — stop")
                _dump_debug(html, "shrink_nositekey")
                return None
            try:
                if kind == "hcaptcha":
                    token = (solve_hcaptcha(cfg, sitekey, cur, UA)
                             .get("token")) or ""
                    fields["h-captcha-response"] = token
                else:
                    token = solve_turnstile(cfg, sitekey, cur,
                                            action=ts_action)
                    fields["cf-turnstile-response"] = token
            except Exception as e:
                log(f"  Shrink-article: captcha solve gagal: {e}")
                return None
            if not token:
                log("  Shrink-article: captcha token kosong — stop")
                return None
            log(f"  Shrink-article: {kind} solved → POST lanjut")
        try:
            r = ext.post(target, data=fields, timeout=30, allow_redirects=True,
                         headers={"Origin": origin, "Referer": cur,
                                  "Content-Type":
                                      "application/x-www-form-urlencoded"})
        except requests.RequestException as e:
            log(f"  Shrink-article POST: {e}")
            return None
        html, cur = r.text, r.url
        if "lightningminer.com" in cur:
            return r
        # POST wall diterima (307) → respon = halaman iklan luar tanpa
        # form keluarga (advertisingcamps→taboola, bukti 2026-11-09) —
        # balik ke short URL (kayak tombol Back browser) buat langkah
        # server berikutnya; kalau alias masih sama → stall di loop atas.
        if _shrink_article_form(html) is None and fields.get("url"):
            log(f"  Shrink-article: respon iklan → balik "
                f"{fields['url'][:60]}")
            try:
                rb = ext.get(fields["url"], timeout=25)
            except requests.RequestException as e:
                log(f"  Shrink-article bounce: {e}")
                return None
            if "lightningminer.com" in rb.url:
                return rb
            html, cur = rb.text, rb.url
    log("  Shrink-article: max step tercapai")
    return None


def _shrink_ac_landing(ext: requests.Session, page: str, url: str,
                       cfg: dict, c: Optional["LMClient"] = None
                       ) -> Optional[Any]:
    """ShrinkEarn/Clk.sh: form mysite → advertisingcamps → artikel publisher.

    CREDITED live 2026-11-02 (ShrinkEarn +50): POST ke action form
    (advertisingcamps.com/taboolaN/landing/) WAJIB header Referer=halaman
    asal + Origin + field `submit=Continue` + token Turnstile di
    visit_token/cf-turnstile-response — tanpa itu server 302 ke taboola.com
    (dead-end). Balas 200 halaman Advertising berisi
    `window.location.href=<loanbixby article>`. Hop pertama GET article
    DENGAN Referer=URL advertisingcamps → 301 t.co (referer lain → 302
    taboola); t.co balas halaman mini JS `location.replace(<article>)` →
    artikel (form next_page+token+alias) → _shrink_article_chain lama.
    Return hasil chain / None.
    """
    chosen = None
    for fm in re.finditer(r"<form([^>]*)>(.*?)</form>", page, re.I | re.S):
        attrs, inner = fm.group(1), fm.group(2)
        if 'name="mysite"' not in inner:
            continue
        am = re.search(r'action="([^"]*)"', attrs)
        action = am.group(1) if am else ""
        if "advertisingcamps" not in action:
            continue
        fields: dict = {}
        for mi in re.finditer(r"<input([^>]*)>", inner, re.I):
            n = re.search(r'name="([^"]+)"', mi.group(1))
            if not n:
                continue
            v = re.search(r'value="([^"]*)"', mi.group(1))
            fields[n.group(1)] = html_mod.unescape(v.group(1)) if v else ""
        chosen = (action, fields)
        break
    if not chosen:
        return None
    action, fields = chosen
    msk = re.search(r'"turnstile_site_key"\s*:\s*"([^"]+)"', page)
    if not msk:
        msk = re.search(r"0x4AAAAAA[A-Za-z0-9_-]+", page)
    if not msk:
        log("  AC landing: sitekey Turnstile tak terbaca")
        return None
    try:
        tok = solve_turnstile(cfg, msk.group(1), url)
    except Exception as e:
        log(f"  AC landing Turnstile: {e}")
        return None
    if not tok:
        return None
    if "visit_token" in fields:
        fields["visit_token"] = tok
    fields["cf-turnstile-response"] = tok
    fields["submit"] = "Continue"
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    target = urljoin(url, action)
    try:
        r0 = ext.post(target, data=fields, timeout=30, allow_redirects=False,
                      headers={"Origin": origin, "Referer": url,
                               "Content-Type":
                                   "application/x-www-form-urlencoded"})
    except requests.RequestException as e:
        log(f"  AC landing POST: {e}")
        return None
    mj = re.search(r'window\.location\.href\s*=\s*[\'"]([^\'"]+)[\'"]',
                   r0.text)
    if mj:
        cur = html_mod.unescape(mj.group(1).replace("\\/", "/"))
    elif r0.headers.get("Location") and "taboola" not in (
            r0.headers.get("Location") or "").lower():
        cur = urljoin(target, r0.headers.get("Location"))
    else:
        log(f"  AC landing: tanpa redirect (HTTP {r0.status_code})")
        return None
    log(f"  AC landing → {cur[:75]}")
    referer = target  # hop pertama (publisher) harus Referer=advertisingcamps
    final = None
    for _ in range(15):
        try:
            rr = ext.get(cur, timeout=25, allow_redirects=False,
                         headers={"Referer": referer})
        except requests.RequestException as e:
            log(f"  AC follow: {e}")
            return None
        if rr.status_code in (301, 302, 303, 307, 308):
            referer = cur
            cur = urljoin(cur, rr.headers.get("Location", ""))
            continue
        if "google.com/url" in cur:
            mq = (re.search(r"[?&](?:url|q)=([^&]+)", cur)
                  or re.search(r"[?&](?:url|q)=([^&]+)", rr.text))
            if not mq:
                log("  AC follow: google-hop tanpa tujuan")
                return None
            referer = "https://www.google.com/"
            cur = html_mod.unescape(unquote(mq.group(1)))
            continue
        if len(rr.text) < 8000:
            mjs = re.search(
                r"(?:window\.location\.href\s*=\s*|location\.replace\()\s*"
                r"[\'\"]([^\'\"]+)[\'\"]", rr.text)
            if mjs:
                referer = cur
                cur = urljoin(rr.url, mjs.group(1).replace("\\/", "/"))
                continue
            mm = re.search(
                r'http-equiv=["\']refresh["\'][^>]*content=["\']\d+;\s*'
                r'url=([^"\']+)', rr.text, re.I)
            if mm:
                referer = cur
                cur = urljoin(rr.url, mm.group(1))
                continue
        final = rr
        break
    if final is None:
        log("  AC follow: max hop tanpa artikel")
        return None
    log(f"  AC artikel: {final.url[:75]}")
    if "lightningminer.com" in final.url:
        return final
    return _shrink_article_chain(ext, final.text, final.url, cfg, c=c)


def _shrinkme_journey(ext: requests.Session, page: str, url: str,
                      cfg: dict) -> Optional[Any]:
    """Artikel journey ShrinkMe (publisher): POST /go/arm → beat → /go/next.

    Return Response halaman berikutnya (GET manual + Referer — auto-follow
    bisa 500, terbukti 2026-11-01), atau None kalau gagal.
    """
    mj = re.search(r'<div[^>]*id="j-journey"[^>]*>', page)
    if not mj:
        return None
    tag = mj.group(0)
    gx = re.search(r'data-x="([^"]+)"', tag)
    gstep = re.search(r'data-step="([^"]+)"', tag)
    gw = re.search(r'data-wait="([^"]+)"', tag)
    if not gx or not gstep:
        return None
    x, step = gx.group(1), int(gstep.group(1))
    wait = int(gw.group(1)) if gw else 10
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"

    def post_go(path: str, data: dict) -> Any:
        return ext.post(urljoin(origin, path), data=data, timeout=25,
                        allow_redirects=False)

    sig = _shrinkme_sig()
    r = post_go("/go/arm", {"sig": sig, "ts": "", "x": x, "step": step})
    if r.status_code >= 400:
        log(f"  ShrinkMe arm HTTP {r.status_code}")
        return None
    try:
        d = r.json()
    except Exception:
        log("  ShrinkMe arm: respons bukan JSON")
        return None
    if d.get("challenge"):  # protect mode: invisible Turnstile
        try:
            ts = solve_turnstile(cfg, d["challenge"], url)
        except Exception as e:
            log(f"  ShrinkMe arm challenge: {e}")
            return None
        r = post_go("/go/arm", {"sig": sig, "ts": ts, "x": x, "step": step})
        try:
            d = r.json()
        except Exception:
            return None
    if "remaining" not in d:
        log(f"  ShrinkMe arm: {str(d)[:80]}")
        return None
    rem = max(0, int(d["remaining"]))
    if rem:
        log(f"  ShrinkMe journey{step}: tunggu {rem}s (beat)…")
        t_end = time.time() + rem
        while time.time() < t_end:
            time.sleep(min(2.0, max(0.5, t_end - time.time())))
            try:
                post_go("/go/beat", {"x": x, "step": step})
            except requests.RequestException:
                pass
    r2 = post_go("/go/next", {"x": x, "step": step, "sig": _shrinkme_sig()})
    loc = r2.headers.get("Location", "")
    if not loc:
        if r2.status_code < 400 and "<form" in r2.text.lower():
            return r2  # 200 langsung halaman berikutnya
        log(f"  ShrinkMe next HTTP {r2.status_code} tanpa Location")
        return None
    nxt = urljoin(origin, loc)
    time.sleep(random.uniform(0.6, 1.4))
    try:
        r3 = ext.get(nxt, timeout=30, allow_redirects=False,
                     headers={"Referer": origin + "/"})
    except requests.RequestException as e:
        log(f"  ShrinkMe next GET: {e}")
        return None
    # ?gw=TOKEN bisa 302 sekali lagi ke halaman final — follow manual
    # (auto-follow tanpa Referer pernah 500)
    for _ in range(3):
        if r3.status_code not in (301, 302, 303, 307, 308):
            break
        loc2 = r3.headers.get("Location", "")
        if not loc2:
            break
        try:
            r3 = ext.get(urljoin(r3.url, loc2), timeout=30,
                         allow_redirects=False,
                         headers={"Referer": r3.url})
        except requests.RequestException as e:
            log(f"  ShrinkMe redirect GET: {e}")
            return None
        time.sleep(random.uniform(0.3, 0.8))
    return r3


def _shrinkme_final(ext: requests.Session, page: str, url: str,
                    cfg: dict, c: Optional["LMClient"] = None) -> Optional[Any]:
    """Halaman timer akhir shrinkme: tunggu → POST /links/go → destination.

    Endpoint /links/go HANYA menerima request ala jQuery $.ajax: wajib
    X-Requested-With (+Origin/Referer) — tanpa itu balas
    {"status":"error","message":"Bad Request."} (terbukti 2026-11-01).
    Timer juga dihitung server (POST sebelum timer = Bad Request).
    Response sukses: {"status":"success","url":<LM complete URL>}.
    """
    wt = re.search(r'id="timer"[^>]*>\s*(\d+)\s*<', page)
    wait = int(wt.group(1)) if wt else 10
    log(f"  ShrinkMe final: timer {wait}s…")
    time.sleep(wait + random.uniform(0.5, 1.5))
    mf = re.search(r'<form[^>]*action="/links/go"[^>]*>(.*?)</form>',
                   page, re.S)
    if not mf:
        return None
    fields: dict = {}
    for mi in re.finditer(r'<input[^>]*name="([^"]+)"[^>]*>', mf.group(1)):
        mv = re.search(r'value="([^"]*)"', mi.group(0))
        fields[mi.group(1)] = html_mod.unescape(mv.group(1)) if mv else ""
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    hdrs = {
        "Origin": origin,
        "Referer": url,
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
    }
    try:
        r = ext.post(urljoin(origin, "/links/go"), data=fields, timeout=30,
                     allow_redirects=False, headers=hdrs)
    except requests.RequestException as e:
        log(f"  ShrinkMe /links/go: {e}")
        return None
    try:
        dj = r.json()
    except Exception:
        dj = {}
    u = dj.get("url") or ""
    # enable_captcha=yes (xut final) tapi captcha_shortlink=no → coba dulu
    # tanpa token; kalau gagal + ada turnstile_site_key → solve + retry.
    if not (dj.get("status") == "success" and u):
        mav = re.search(r"var\s+app_vars\s*=\s*(\{.*?\});", page, re.S)
        if mav:
            try:
                av = json.loads(mav.group(1))
            except Exception:
                av = {}
            sk = av.get("turnstile_site_key") or ""
            if (av.get("enable_captcha") == "yes"
                    and av.get("captcha_type") == "turnstile"
                    and sk and not sk.startswith("YOUR_")):
                try:
                    tok = solve_turnstile(cfg, sk, url, "cwsafelink_final")
                    fields["cf-turnstile-response"] = tok
                    log("  ShrinkMe /links/go: retry + Turnstile")
                    time.sleep(random.uniform(0.5, 1.2))
                    r = ext.post(urljoin(origin, "/links/go"), data=fields,
                                 timeout=30, allow_redirects=False,
                                 headers=hdrs)
                    try:
                        dj = r.json()
                    except Exception:
                        dj = {}
                    u = dj.get("url") or ""
                except Exception as e:
                    log(f"  ShrinkMe turnstile: {e}")
    if dj.get("status") == "success" and u:
        log(f"  ShrinkMe /links/go OK → complete")
        # URL complete ada di domain LM → WAJIB pakai sesi LM (cookie).
        # Token complete SEKALI PAKAI: GET di sini, lalu follow Location
        # sampai halaman credited — caller jangan GET complete ulang
        # (GET kedua → shortlink=error, terbukti 2026-11-01).
        if "lightningminer.com" in u and c is not None:
            try:
                resp = c.s.get(u, timeout=20, allow_redirects=False)
            except requests.RequestException as e:
                log(f"  ShrinkMe complete GET: {e}")
                return None
            loc = resp.headers.get("Location", "")
            if loc:
                try:
                    return c.s.get(urljoin("https://lightningminer.com", loc),
                                   timeout=20, allow_redirects=True)
                except requests.RequestException as e:
                    log(f"  ShrinkMe complete follow: {e}")
                    return None
            return resp
        try:
            return ext.get(u, timeout=30, allow_redirects=False,
                           headers={"Referer": origin + "/"})
        except requests.RequestException as e:
            log(f"  ShrinkMe dest GET: {e}")
            return None
    log(f"  ShrinkMe /links/go: {dj.get('message') or f'HTTP {r.status_code}'}")
    return None


def _textfrog_captcha(ext: requests.Session, page: str, url: str,
                      cfg: dict) -> Optional[Any]:
    """Xut/textfrog step1: SL_CFG captchaProvider=cwcaptcha → tunggu
    countdown → solve CWCaptcha → POST verifyUrl → Response artikel."""
    try:
        sl = json.loads(re.search(r"window\.SL_CFG = (\{.*?\});", page).group(1))
    except Exception:
        return None
    csrf = sl.get("csrf") or (
        re.search(r'name="csrf" value="([^"]+)"', page) or [None, ""])[1]
    vurl = sl.get("verifyUrl") or "/cwsafelinkphp/sl-cwcaptcha-verify.php"
    cd = sl.get("countdownRemaining") or sl.get("countdown") or 10
    log(f"  CWCaptcha step1: countdown {cd}s…")
    time.sleep(cd + random.uniform(0.5, 1.5))
    sk = sl.get("cwcaptchaSiteKey") or ""
    act = sl.get("cwcaptchaAction") or "safelink"
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    tok = solve_cwcaptcha(ext, sk, act, origin)
    if not tok:
        log("  CWCaptcha: token gagal")
        return None
    time.sleep(random.uniform(1.0, 2.0))
    try:
        rv = ext.post(
            urljoin(url, vurl),
            data={"csrf": csrf, "cw-captcha-response": tok},
            timeout=20,
            headers={"Referer": url, "Origin": origin,
                     "X-Requested-With": "XMLHttpRequest",
                     "Accept": "application/json"})
    except requests.RequestException as e:
        log(f"  CWCaptcha verify: {e}")
        return None
    try:
        vdj = rv.json()
    except Exception:
        vdj = {}
    if not vdj.get("ok"):
        log(f"  CWCaptcha verify gagal: {rv.text[:140]}")
        return None
    nxt = vdj.get("redirect") or vdj.get("url") or ""
    if not nxt:
        log("  CWCaptcha verify: tanpa redirect")
        return None
    log("  CWCaptcha verify OK → artikel")
    return ext.get(urljoin(url, nxt), timeout=25)


def _sl_next_post(ext: requests.Session, page: str, url: str,
                  cfg: dict) -> Optional[Any]:
    """Halaman SL_CFG step≥2 (textfrog/eduify/gamescrate): tunggu countdown
    → POST sl-stepN.php (csrf); finalCaptcha → Turnstile Peak dulu →
    sl-final.php → 303 ke xut.io final. Return Response hasil follow."""
    try:
        sl = json.loads(re.search(r"window\.SL_CFG = (\{.*?\});", page).group(1))
    except Exception:
        return None
    mf = re.search(r'id="sl-next-form"[^>]*action="([^"]+)"', page)
    cf = re.search(r'name="csrf" value="([^"]+)"', page)
    if not (mf and cf):
        return None
    cd = sl.get("countdownRemaining") or sl.get("countdown") or 5
    log(f"  SL step{sl.get('step')}: countdown {cd}s"
        f"{' +Turnstile' if sl.get('finalCaptcha') else ''}…")
    time.sleep(cd + random.uniform(0.5, 1.5))
    data: dict = {"csrf": cf.group(1)}
    if sl.get("finalCaptcha"):
        sk = sl.get("turnstileSiteKey") or ""
        if not sk or sk.startswith("YOUR_"):
            log("  SL final: turnstile tak dikonfigurasi")
            return None
        try:
            data["turnstile_token"] = solve_turnstile(
                cfg, sk, url, sl.get("turnstileAction"))
        except Exception as e:
            log(f"  SL final turnstile: {e}")
            return None
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    try:
        return ext.post(
            urljoin(url, mf.group(1)), data=data, timeout=30,
            allow_redirects=True,
            headers={"Referer": url, "Origin": origin,
                     "X-Requested-With": "XMLHttpRequest",
                     "Accept": "application/json, text/html"})
    except requests.RequestException as e:
        log(f"  SL step POST: {e}")
        return None


def _vli_article(ext: requests.Session, page: str, url: str,
                 cfg: dict) -> Optional[Any]:
    """Article vli-platform (jobzhub dkk): start_countdown → fdata →
    tunggu 15s → POST form → article berikutnya (atau halaman final).

    Return Response atau None.
    """
    mf = re.search(
        r'<form[^>]*action="([^"]+)"[^>]*method="POST"[^>]*>(.*?)</form>',
        page, re.S)
    if not mf or 'name="form_data"' not in mf.group(2):
        return None
    action, inner = mf.group(1), mf.group(2)
    fields: dict = {}
    for mi in re.finditer(r'<input[^>]*name="([^"]+)"[^>]*>', inner):
        mv = re.search(r'value="([^"]*)"', mi.group(0))
        fields[mi.group(1)] = html_mod.unescape(mv.group(1)) if mv else ""
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    # backend countdown → nilai fdata (wajib, server cocokkan)
    try:
        rc = ext.get(urljoin(url, "?start_countdown=1"), timeout=20,
                     headers={"X-Requested-With": "XMLHttpRequest",
                              "Referer": url})
        fields["fdata"] = (rc.json() or {}).get("rand", "")
    except Exception:
        fields["fdata"] = ""
    log("  VLI: tunggu countdown 15s…")
    time.sleep(15 + random.uniform(0.5, 1.5))
    try:
        return ext.post(urljoin(url, action), data=fields, timeout=30,
                        allow_redirects=False,
                        headers={"Origin": origin, "Referer": url})
    except requests.RequestException as e:
        log(f"  VLI POST: {e}")
        return None


def _vli_final(ext: requests.Session, page: str, url: str, cfg: dict,
               c: Optional["LMClient"] = None) -> Optional[Any]:
    """Final article vli (form12): timer + turnstile → POST <domainUrl>
    (fc.lc/links/go) ala XHR → JSON {status,url} → complete LM."""
    mf = re.search(r'<form[^>]*id="form12"[^>]*>(.*?)</form>', page, re.S)
    md = re.search(r'var domainUrl = "([^"]+)"', page)
    if not mf or not md:
        return None
    fields: dict = {}
    for mi in re.finditer(r'<input[^>]*name="([^"]+)"[^>]*>', mf.group(1)):
        mv = re.search(r'value="([^"]*)"', mi.group(0))
        fields[mi.group(1)] = html_mod.unescape(mv.group(1)) if mv else ""
    wt = re.search(r'id="timer"[^>]*>\s*(\d+)', page)
    wait = int(wt.group(1)) if wt else 15
    log(f"  VLI final: timer {wait}s…")
    time.sleep(wait + random.uniform(0.5, 1.5))
    kind, sitekey, ts_action = parse_captcha_widget(page)
    token = ""
    if sitekey:
        try:
            token = solve_turnstile(cfg, sitekey, url, action=ts_action)
        except Exception as e:
            log(f"  VLI final turnstile: {e}")
            return None
    fields["token"] = token  # JS push {name:'token', value:turnstileToken}
    target = md.group(1)
    thdrs = {
        "Origin": f"{urlsplit(target).scheme}://{urlsplit(target).netloc}",
        "Referer": url,
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
    }
    try:
        r = ext.post(target, data=fields, timeout=30, allow_redirects=False,
                     headers=thdrs)
    except requests.RequestException as e:
        log(f"  VLI links/go: {e}")
        return None
    try:
        dj = r.json()
    except Exception:
        dj = {}
    u = dj.get("url") or ""
    if dj.get("status") == "success" and u:
        log("  VLI links/go OK → complete")
        # token complete sekali pakai — jangan di-GET ulang caller
        if "lightningminer.com" in u and c is not None:
            try:
                resp = c.s.get(u, timeout=20, allow_redirects=False)
            except requests.RequestException as e:
                log(f"  VLI complete GET: {e}")
                return None
            loc = resp.headers.get("Location", "")
            if loc:
                try:
                    return c.s.get(urljoin("https://lightningminer.com", loc),
                                   timeout=20, allow_redirects=True)
                except requests.RequestException as e:
                    log(f"  VLI complete follow: {e}")
                    return None
            return resp
        try:
            return ext.get(u, timeout=30, allow_redirects=False,
                           headers={"Referer": thdrs["Origin"] + "/"})
        except requests.RequestException:
            return None
    log(f"  VLI links/go: {dj.get('message') or f'HTTP {r.status_code}'}")
    return None


def _shorteio_cycle(ext: requests.Session, page: str, url: str) -> Optional[str]:
    """Sesi shorte.io (starkroboticsfrc.com): PATCH /api/session/{ssid} →
    redirect t.co → publisher → PATCH step/increment (jeda 11s, server
    paksa timer) sampai completed → return finalDestination.

    Terbukti CREDITED +50 live keyless 2026-11-02 (probe_shorte9.py):
    finalDestination = halaman shorte.io timer 1s + form /links/go
    (ad_form_data + token CakePHP, captcha mati) → POST ala XHR →
    JSON {status,url=LM complete). Halaman final kebetulan pola sama
    dengan ShrinkMe → ditangani _shrinkme_final yang sudah ada.
    """
    ms = re.search(r'const ssid = "([^"]+)"', page)
    mc = re.search(r'csrfToken = "([^"]+)"', page) or \
        re.search(r'<meta name="csrf-token" content="([^"]+)"', page)
    if not (ms and mc):
        return None
    ssid, csrf = ms.group(1), mc.group(1)
    mi = re.search(r'currentIp = "([^"]+)"', page)
    ip = mi.group(1) if mi else ""
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"

    def patch():
        body = {"ssid": ssid, "currentIp": ip,
                "ipType": "IPv4" if ip.count(".") == 3 else "unknown",
                "ipv4": ip if ip.count(".") == 3 else None,
                "ipv6": None, "hcaptchaToken": None}
        hdrs = {"Content-Type": "application/json", "X-CSRF-Token": csrf,
                "Referer": url, "Origin": origin,
                "Accept": "application/json"}
        try:
            rp = ext.patch(f"{origin}/api/session/{ssid}", json=body,
                           timeout=20, headers=hdrs)
            data = rp.json()
        except Exception:
            return None
        if data.get("error") == "SESSION_CONFLICT":
            ex = (data.get("existingSession") or {}).get("id", "").split(":")[-1]
            try:
                ext.delete(f"{origin}/api/session/{ex}", timeout=15,
                           headers={"X-CSRF-Token": csrf, "Referer": url,
                                    "Origin": origin,
                                    "Accept": "application/json"})
                rp = ext.patch(f"{origin}/api/session/{ssid}", json=body,
                               timeout=20, headers=hdrs)
                data = rp.json()
            except Exception:
                return None
        return data

    data = patch()
    if not data or data.get("error"):
        log(f"  Shorte PATCH: {str(data)[:100]}")
        return None
    tco = data.get("redirect")
    fr = data.get("finalRedirect") or (data.get("data") or {}).get("finalRedirect")
    if fr:
        return fr
    if not tco:
        return None
    try:
        rx = ext.get(tco, timeout=25, allow_redirects=False)
        pub = rx.headers.get("Location")
        if not pub:
            mr = re.search(r'http-equiv="refresh"[^>]*URL=([^">]+)',
                           rx.text, re.I)
            pub = html_mod.unescape(mr.group(1)) if mr else None
        if not pub:
            rx = ext.get(tco, timeout=25, allow_redirects=True)
            pub_url, page_html = rx.url, rx.text
        else:
            rx = ext.get(pub, timeout=25, allow_redirects=True)
            pub_url, page_html = rx.url, rx.text
    except requests.RequestException as e:
        log(f"  Shorte publisher: {e}")
        return None
    log(f"  Shorte publisher: {pub_url[:70]}")
    mp = re.search(r'data-session-id="([^"]+)"', page_html)
    sess_pub = mp.group(1) if mp else ssid
    mcsrf = re.search(r'csrfToken = "([^"]+)"', page_html) or \
        re.search(r'<meta name="csrf-token" content="([^"]+)"', page_html)
    csrf_pub = mcsrf.group(1) if mcsrf else csrf
    origin_pub = f"{urlsplit(pub_url).scheme}://{urlsplit(pub_url).netloc}"
    time.sleep(11 + random.uniform(0.3, 1.0))
    for step in range(1, 8):
        if step > 1:
            time.sleep(11 + random.uniform(0.3, 1.0))
        hi = {"Content-Type": "application/json", "X-CSRF-Token": csrf_pub,
              "Referer": pub_url, "Origin": origin_pub,
              "Accept": "application/json"}
        try:
            ri = ext.patch(f"{origin_pub}/api/session/{sess_pub}/step/increment",
                           timeout=20, headers=hi)
        except requests.RequestException as e:
            log(f"  Shorte inc{step}: {e}")
            return None
        if ri.status_code == 429:
            time.sleep(12)
            try:
                ri = ext.patch(
                    f"{origin_pub}/api/session/{sess_pub}/step/increment",
                    timeout=20, headers=hi)
            except requests.RequestException:
                return None
        try:
            dj = ri.json()
        except Exception:
            log(f"  Shorte inc{step}: HTTP {ri.status_code}")
            return None
        sess = dj.get("session") or {}
        log(f"  Shorte inc{step}: {sess.get('currentStep')}/"
            f"{sess.get('totalSteps')}")
        if sess.get("completed"):
            return sess.get("finalDestination")
    return None


def complete_timer_shortlink(c: LMClient, sid: str, name: str,
                             cfg: Optional[dict] = None) -> bool:
    """Ikuti shortlink timer-only sampai credited. Pure HTTP, tanpa browser.

    Pola timer (bces2/lq) jalan polos; halaman Turnstile (CXL checkpoint,
    form shrink) di-solve via solver key di cfg. Return True kalau credited.
    """
    cfg = cfg or {}
    r0 = c.s.get(
        f"{API}/shortlinks/{sid}/start",
        timeout=15,
        allow_redirects=False,
    )
    loc = r0.headers.get("Location", "")
    if not loc:
        log(f"  SL {name}: start HTTP {r0.status_code} tanpa Location")
        return False

    # sesi eksternal TERPISAH — cookie lm_session tidak boleh bocor
    ext = requests.Session()
    ext.headers.update({"User-Agent": UA})

    # gate internal LM: halaman timer 10s → target eksternal (shrink)
    if "lightningminer.com/shortlink-gate" in loc:
        rg = c.s.get(loc, timeout=20)
        mg = re.search(r'const target = "([^"]+)"', rg.text)
        wt = re.search(r'const totalSeconds = (\d+)', rg.text)
        if not mg:
            log(f"  SL {name}: gate tanpa target — dilewati")
            return False
        wait_g = int(wt.group(1)) if wt else 10
        log(f"  SL {name} gate: timer {wait_g}s…")
        time.sleep(wait_g + random.uniform(0.5, 1.5))
        loc = html_mod.unescape(mg.group(1))
    elif "lightningminer.com" in loc:
        rr = c.s.get(loc, timeout=15)
        if "credited" in rr.url:
            log(f"  SL {name}: credited langsung {rr.url[-60:]}")
            return True
        log(f"  SL {name}: start balik ke LM ({rr.url[-60:]})")
        return False

    url = loc
    pending: Optional[Any] = None  # hasil POST form → proses tanpa GET ulang
    for step in range(1, 9):
        try:
            if pending is not None:
                r, pending = pending, None
            else:
                r = ext.get(url, timeout=25)
        except requests.RequestException as e:
            log(f"  SL {name} step{step}: network {e}")
            return False
        if "lightningminer.com" in r.url:
            # credited perlu cookie LM → GET ulang pakai sesi LM
            rr = c.s.get(r.url, timeout=15)
            ok = "credited" in rr.url
            m = re.search(r"coins=(\d+)", rr.url)
            extra = f" +{m.group(1)} coins" if m and ok else ""
            log(f"  SL {name}: {'CREDITED' if ok else 'return'}{extra} "
                f"({rr.url[-70:]})")
            return ok
        # JSON {success, redirectUrl} — pola fc.lc POST /verify
        if r.text.lstrip().startswith("{") and "redirectUrl" in r.text:
            try:
                dj = r.json()
            except Exception:
                dj = {}
            nxt = dj.get("redirectUrl")
            if nxt:
                log(f"  SL {name}: verify OK → redirect")
                url = html_mod.unescape(nxt)
                continue
        # google.com/url interstitial (Adlink/Xut: hop 302 via
        # diudemy-style → google → artikel). Tujuan sudah ada di param
        # url=/q= link itu; halamannya hanya var redirectUrl + meta refresh.
        if "google.com/url" in r.url:
            mq = re.search(r"[?&](?:url|q)=([^&]+)", r.url)
            if mq:
                nxt = html_mod.unescape(unquote(mq.group(1)))
                log(f"  SL {name}: google-hop → {nxt[:70]}")
                url = nxt
                continue
        # ShrinkEarn/Clk.sh: form mysite action→advertisingcamps (taboolaN)
        # — solve + hop Referer-berat → artikel → chain (2026-11-02 credited).
        if 'name="mysite"' in r.text and "advertisingcamps" in r.text:
            r2 = _shrink_ac_landing(ext, r.text, r.url, cfg, c=c)
            if r2 is not None:
                log(f"  SL {name} AC-landing → lanjut")
                pending = r2
                continue
            log(f"  SL {name}: AC-landing gagal")
            return False
        # keluarga shrink multi-article (ShrinkPe / ShrinkBixby):
        # HANYA halaman pertama (field mysite+visit_token) yang jadi entry —
        # next_page saja TIDAK cukup (Clk.sh/ShrinkEarn punya field serupa).
        if 'name="mysite"' in r.text and 'name="visit_token"' in r.text:
            r2 = _shrink_article_chain(ext, r.text, r.url, cfg, c=c)
            if r2 is not None:
                log(f"  SL {name} shrink-article → lanjut")
                pending = r2
                continue
            log(f"  SL {name}: shrink-article gagal")
            return False
        # shorte.io — sesi starkroboticsfrc: PATCH → publisher → increment
        if "starkroboticsfrc.com" in r.url or (
                'const ssid = "' in r.text and "currentIp" in r.text):
            fd = _shorteio_cycle(ext, r.text, r.url)
            if fd:
                log(f"  SL {name} shorte: cycle done → halaman final")
                url = fd
                continue
            log(f"  SL {name}: shorte cycle gagal")
            return False
        # journey ShrinkMe (artikel publisher: arm/beat/next)
        if 'id="j-journey"' in r.text:
            r2 = _shrinkme_journey(ext, r.text, r.url, cfg)
            if r2 is not None:
                log(f"  SL {name} journey step → halaman berikutnya")
                pending = r2
                continue
            log(f"  SL {name}: journey ShrinkMe gagal")
            return False
        # halaman final shrinkme (timer + form /links/go)
        if 'action="/links/go"' in r.text:
            r2 = _shrinkme_final(ext, r.text, r.url, cfg, c=c)
            if r2 is not None:
                pending = r2
                continue
            log(f"  SL {name}: /links/go gagal")
            return False
        # vli-platform (jobzhub dkk) — article form_data → POST lanjut
        if 'name="form_data"' in r.text and 'id="form12"' not in r.text:
            r2 = _vli_article(ext, r.text, r.url, cfg)
            if r2 is not None:
                log(f"  SL {name} VLI article → step berikutnya")
                pending = r2
                continue
            log(f"  SL {name}: VLI article gagal")
            return False
        # final vli (form12) → POST domainUrl (fc.lc/links/go) → complete
        if 'id="form12"' in r.text and "domainUrl" in r.text:
            r2 = _vli_final(ext, r.text, r.url, cfg, c=c)
            if r2 is not None:
                pending = r2
                continue
            log(f"  SL {name}: VLI final gagal")
            return False
        # textfrog/CWCaptcha (Xut) + multi-step sl-next-form
        # (textfrog→eduify→gamescrate) — SEBELUM _extract_sl_continue
        if "window.SL_CFG" in r.text:
            if '"cwcaptcha"' in r.text:
                r2 = _textfrog_captcha(ext, r.text, r.url, cfg)
                if r2 is not None:
                    log(f"  SL {name}: CWCaptcha verified → lanjut")
                    pending = r2
                    continue
                log(f"  SL {name}: CWCaptcha gagal — dilewati")
                return False
            if 'id="sl-next-form"' in r.text:
                r2 = _sl_next_post(ext, r.text, r.url, cfg)
                if r2 is not None:
                    log(f"  SL {name}: SL step POST → lanjut")
                    pending = r2
                    continue
                log(f"  SL {name}: SL step gagal — dilewati")
                return False
        nxt, wait = _extract_sl_continue(r.text)
        if not nxt:
            # --- jalur Turnstile: CXL checkpoint atau form POST ---
            if 'const sessionId="' in r.text or "cxlgames.com" in r.url:
                try:
                    n2, done = _cxl_advance(ext, r.text, r.url, cfg)
                except Exception as e:
                    log(f"  SL {name} CXL: {e}")
                    return False
                if done:
                    log(f"  SL {name}: CXL selesai (credit server-side)")
                    return True
                if n2:
                    log(f"  SL {name} CXL advance → step lanjut")
                    url = n2
                    continue
                log(f"  SL {name}: CXL advance gagal di step {step}")
                return False
            # keluarga shrink script (shrinkearn/clk.sh + sejenis):
            # halaman continue #captchaShortlink → rantai artikel yang sama
            if 'id="captchaShortlink"' in r.text:
                r2 = _shrink_article_chain(ext, r.text, r.url, cfg, c=c)
                if r2 is not None:
                    log(f"  SL {name} shrink-captcha chain → lanjut")
                    pending = r2
                    continue
                log(f"  SL {name}: shrink-captcha chain gagal")
                return False
            low = r.text.lower()
            if "<form" in low and ("_token" in r.text or "turnstile" in low):
                n2 = _shrink_captcha(ext, r.text, r.url, cfg)
                if n2 is not None:
                    log(f"  SL {name} form POST → lanjut")
                    pending = n2
                    continue
                log(f"  SL {name}: form butuh Turnstile / gagal — dilewati")
                return False
            log(f"  SL {name}: pola tak dikenali di step {step} "
                f"({r.url[:70]}) — dilewati")
            _dump_debug(r.text, f"unknown_{name}")
            return False
        log(f"  SL {name} step{step}: timer {wait}s…")
        time.sleep(wait + random.uniform(0.5, 1.5))
        url = html_mod.unescape(urljoin(r.url, nxt))
    log(f"  SL {name}: max step tercapai — gagal")
    return False


def do_shortlinks(c: LMClient, cfg: Optional[dict] = None) -> None:
    """Sweep shortlink yang canStart: timer-only dikerjakan penuh,
    yang butuh Turnstile di-solve (butuh key solver) atau dilewati."""
    cfg = cfg or {}
    r = c.api("GET", "/shortlinks")
    if not r.get("ok"):
        log(f"Shortlinks load gagal: {r.get('error')}")
        return
    links = r.get("links") or r.get("shortlinks") or []
    n_ok = n_fail = 0
    now = time.time()
    for sl in links:
        if not sl.get("canStart"):
            continue
        sid = sl.get("id")
        # gagal baru-baru ini → tunggu SL_RETRY_GAP (sukses diatur canStart)
        last_fail = _sl_state.get(sid)
        if last_fail and now - last_fail < SL_RETRY_GAP:
            continue
        name = sl.get("name") or sid
        reward = sl.get("rewardCoins", 0)
        log(f"Shortlink {name} (+{reward} coins)…")
        ok = False
        try:
            ok = complete_timer_shortlink(c, sid, name, cfg)
            if ok:
                n_ok += 1
                c.me()
            else:
                n_fail += 1
        except Exception as e:
            log(f"  SL {name} error: {e}")
            n_fail += 1
        if ok:
            _sl_state.pop(sid, None)   # sukses → biarkan cooldown canStart
        else:
            _sl_state[sid] = time.time()
        _sl_tried_total.add(sid)
        sleep_humans(1.0, 0.4)
    if n_ok or n_fail:
        log(f"Shortlinks: {n_ok} credited, {n_fail} gagal/skip "
            f"({len(_sl_tried_total)} pernah dicoba)")


PTC_SITEKEY = "0x4AAAAAAEI2cArGyJPBwUGx"  # dari halaman /ptc-view LM
PTC_PER_CYCLE = 5
_ptc_no_key_logged = False


def do_ptc(c: LMClient, cfg: dict) -> None:
    """PTC self-serve: view iklan 15s → Turnstile → view-complete → +10 coins.

    Alur asli (dibaca dari /ptc-view):
      GET  /api/self-serve-ptc/view?id=AD   → {viewToken, durationSeconds}
      tunggu duration (client-side timer; server cek completedMs)
      POST /api/self-serve-ptc/view-complete {adId, completedMs,
             turnstileToken, viewToken}     → reward
    Satu iklan = sekali sehari (viewedToday), token Turnstile server-
    verified (dummy token ditolak — sudah dites 2026-11-01).
    """
    global _ptc_no_key_logged
    if not has_turnstile_key(cfg):
        if not _ptc_no_key_logged:
            log("PTC: belum ada Turnstile solver key — dilewati "
                "(isi lm_config.json nocaptchaai_key/peak_key/…).")
            _ptc_no_key_logged = True
        return
    r = c.api("GET", "/self-serve-ptc")
    if not r.get("ok"):
        log(f"PTC load gagal: {r.get('error')}")
        return
    ads = [a for a in (r.get("ads") or [])
           if a.get("status") == "active"
           and not a.get("viewedToday")
           and int(a.get("remainingCredits") or 0) > 0
           and int(a.get("remainingViews") or 0) > 0]
    if not ads:
        return
    n_ok = n_fail = 0
    for ad in ads[:PTC_PER_CYCLE]:
        ad_id = ad.get("id")
        reward = int(ad.get("rewardCoins") or 10)
        try:
            v = c.api("GET", f"/self-serve-ptc/view?id={ad_id}")
            if not v.get("ok"):
                log(f"  PTC start gagal: {v.get('error')}")
                continue
            if (v.get("ad") or {}).get("viewedToday"):
                continue
            view_token = v.get("viewToken") or ""
            dur = int(v.get("durationSeconds") or ad.get("durationSeconds") or 15)
            ptc_url = f"{BASE}/ptc-view?id={ad_id}"
            log(f"PTC view: {str(ad.get('title'))[:38]} (+{reward} coins, {dur}s)…")
            time.sleep(dur + random.uniform(0.5, 2.0))  # timer klien
            token = solve_turnstile(cfg, PTC_SITEKEY, ptc_url,
                                    action="ptc-view")
            done = c.api("POST", "/self-serve-ptc/view-complete", {
                "adId": ad_id,
                "completedMs": dur * 1000 + random.randint(500, 2500),
                "turnstileToken": token,
                "viewToken": view_token,
            })
            if done.get("ok"):
                n_ok += 1
                log(f"  PTC OK +{reward} coins — {str(ad.get('title'))[:36]}")
                c.me()
            else:
                n_fail += 1
                log(f"  PTC gagal: {done.get('error')}")
        except RuntimeError as e:
            n_fail += 1
            log(f"  PTC skip: {e}")
            break  # solver hilang → stop PTC cycle ini
        except Exception as e:
            n_fail += 1
            log(f"  PTC error: {e}")
        sleep_humans(3.0, 1.5)
    if n_ok or n_fail:
        log(f"PTC: {n_ok} view credited, {n_fail} gagal/skip")


def do_withdraw(c: LMClient, cfg: dict, force: bool = False) -> None:
    wd = cfg.get("wd") or {}
    method = wd.get("method")
    dest = wd.get("address")
    if not method or not dest:
        log("WD belum di-set — pakai: --set-wd faucetpay YOU@example.com")
        return
    me = c.me()
    user = me.get("user") or {}
    settled = int(user.get("settledCryptoBalanceAtomic") or 0)
    currency = (wd.get("currency") or user.get("selectedCurrency") or "USDC").upper()
    min_atomic = MIN_WD_ATOMIC
    if settled < min_atomic and not force:
        log(f"WD: settled {settled} atomic < min {min_atomic} — tunggu.")
        return
    if settled < min_atomic and force:
        log(f"WD force tapi settled {settled} < min {min_atomic} — tetap coba.")
    amount = settled if settled > 0 else min_atomic
    r = c.api(
        "POST",
        "/withdraw",
        {
            "method": method,
            "destination": dest,
            "currency": currency,
            "amountAtomic": amount,
        },
    )
    if r.get("ok"):
        log(f"WD OK: {amount} atomic {currency} → {method} {dest}")
        log(f"  resp: {r}")
    else:
        log(f"WD gagal: {r.get('error')}")
        log(f"  resp: {r}")


# ---------------------------------------------------------------- main


def print_state(c: LMClient) -> None:
    u = (c.state.get("user") or {})
    fac = (c.state.get("facility") or {})
    eh = u.get("energyHoursRemaining", fac.get("energyHoursRemaining", "?"))
    log(
        f"STATE coins={u.get('coins', 0):.2f} "
        f"power={u.get('miningPower', 0)} "
        f"settled={u.get('settledCryptoBalanceAtomic', 0)} "
        f"pend={u.get('pendingMiningAtomic', 0)} "
        f"energy={eh}h "
        f"cur={u.get('selectedCurrency', '?')}"
    )


def one_cycle(c: LMClient, cfg: dict, args: argparse.Namespace) -> None:
    c.me()
    print_state(c)
    do_sync(c)
    if not args.no_faucet:
        do_faucet(c, cfg)
    if not args.no_daily:
        do_daily(c)
    if not args.no_quests:
        do_quests(c)
        do_battlepass(c)
    if not args.no_shop:
        do_shop(c, cfg)
        do_facility(c, cfg)
    if not args.no_shortlinks:
        do_shortlinks(c, cfg)
    if not args.no_ptc:
        do_ptc(c, cfg)
    if not args.no_wd:
        do_withdraw(c, cfg, force=args.wd_now)
    c.me()
    print_state(c)


def do_login_flow(args: argparse.Namespace) -> int:
    cfg = load_config()
    email = args.login or cfg.get("email") or input("Email: ").strip()
    password = args.password or cfg.get("password") or getpass.getpass("Password: ")
    if not email or not password:
        log("Email/password kosong.")
        return 2
    key = args.set_nonecap or get_nonecap_key(cfg)
    if key and not cfg.get("nonecap_key"):
        cfg["nonecap_key"] = key
        save_config(cfg)
    if not has_hcaptcha_key(cfg):
        log("Tips: key hCaptcha untuk faucet — "
            "python3 lightningminer_auto.py --set-key nonecap_key nc_live_… "
            "(atau --set-key mythix_key mx_live_…)")
    c = LMClient(cfg)
    if not c.login(email, password):
        return 3
    print_state(c)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="LightningMiner auto-all (akun sendiri)")
    p.add_argument("--login", metavar="EMAIL", help="login sekali lalu simpan session")
    p.add_argument("--password", help="password untuk --login")
    p.add_argument("--once", action="store_true", help="satu siklus lalu keluar")
    p.add_argument("--interval", type=float, default=180,
                   help="detik antar siklus loop (default 180)")
    p.add_argument("--set-wd", nargs=2, metavar=("METHOD", "DEST"),
                   help="simpan tujuan WD (mis faucetpay you@x.com)")
    p.add_argument("--set-nonecap", metavar="KEY", help="simpan NoneCap API key")
    p.add_argument("--set-key", nargs=2, metavar=("NAMA", "NILAI"),
                   help="simpan key solver ke lm_config.json "
                        "(mis: xsolve_key 059f… / peak_key pk_xxx)")
    p.add_argument("--wd-now", action="store_true",
                   help="coba WD meski di bawah minimum")
    p.add_argument("--no-faucet", action="store_true")
    p.add_argument("--no-daily", action="store_true")
    p.add_argument("--no-quests", action="store_true")
    p.add_argument("--no-shop", action="store_true")
    p.add_argument("--no-shortlinks", action="store_true")
    p.add_argument("--no-ptc", action="store_true")
    p.add_argument("--no-wd", action="store_true")
    args = p.parse_args()

    cfg = load_config()

    if args.set_nonecap:
        cfg["nonecap_key"] = args.set_nonecap
        save_config(cfg)
        log("Nonecap key tersimpan.")
        if not args.login and not args.once:
            return 0

    if args.set_key:
        nama, nilai = args.set_key
        cfg[nama] = nilai.strip()
        save_config(cfg)
        log(f"Key tersimpan: {nama} = {nilai[:6]}… "
            f"(Turnstile: {nama in [n for n, _ in SOLVER_ORDER]}, "
            f"hCaptcha: {nama in [n for n, _ in HCAPTCHA_ORDER]})")
        if not args.login and not args.once:
            return 0

    if args.set_wd:
        method, dest = args.set_wd
        cfg["wd"] = {"method": method.lower(), "address": dest, "currency": "USDC"}
        save_config(cfg)
        log(f"WD config: {method} → {dest} (USDC)")
        if not args.login and not args.once:
            return 0

    if args.login:
        return do_login_flow(args)

    # ─── Initialize TUI Dashboard ─────────────────────────────────────
    global _dashboard
    if HAS_TUI and not args.once:
        stats = BotStats()
        config = DashboardConfig(
            title="LIGHTNINGMINER AUTO-FARM",
            subtitle="Faucet • Daily • Quests • Shop • Shortlinks • PTC • WD",
            theme_color=Palette.GOLD,
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

    c = LMClient(cfg)
    # login awal: kalau offline, standby dulu sampai internet balik
    while not c.ensure_login():
        if not is_online():
            offline_standby()
            continue
        # online tapi login gagal (session/password) — jangan exit loop utama
        log("Login gagal saat online — tunggu 60s lalu coba lagi.")
        time.sleep(60)

    if _dashboard:
        _dashboard.set_last_action("Login verified")

    if args.once:
        one_cycle(c, cfg, args)
        if _dashboard:
            _dashboard.stop()
        return 0

    log(f"Loop mulai (interval {args.interval:.0f}s) — "
        f"faucet={'OFF' if args.no_faucet else 'ON'} "
        f"shop={'OFF' if args.no_shop else 'ON'} "
        f"wd={'OFF' if args.no_wd else 'ON'}")
    cycles = 0
    try:
        while True:
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
                    _dashboard.set_last_action(f"Cycle #{cycles} — sync & farm")
                one_cycle(c, cfg, args)
                if _dashboard:
                    _dashboard.increment_cycle(True)
            except KeyboardInterrupt:
                log("Berhenti (Ctrl+C).")
                break
            except (requests.RequestException, ConnectionError, OSError, TimeoutError) as e:
                log(f"network: {e.__class__.__name__} → standby offline")
                offline_standby()
                continue
            except Exception as e:
                log(f"Siklus error: {e}")
                if _dashboard:
                    _dashboard.increment_cycle(False)

            # Update dashboard with current state
            if _dashboard:
                u = (c.state.get("user") or {})
                fac = (c.state.get("facility") or {})
                eh = u.get("energyHoursRemaining", fac.get("energyHoursRemaining", "?"))
                _dashboard.update_balance({
                    "coins": u.get("coins", 0),
                    "power": u.get("miningPower", 0),
                    "settled_atomic": u.get("settledCryptoBalanceAtomic", 0),
                    "pending_atomic": u.get("pendingMiningAtomic", 0),
                    "energy_h": eh,
                    "currency": u.get("selectedCurrency", "?"),
                })
                _dashboard.stats.extra = {
                    "miners_owned": len(c.state.get("miners") or []),
                    "rack_owned": (c.state.get("facility") or {}).get("rack", {}).get("owned", 0),
                    "rack_installed": (c.state.get("facility") or {}).get("rack", {}).get("installed", 0),
                }

            time.sleep(jitter(max(30, args.interval), 20))
    finally:
        if _dashboard:
            _dashboard.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
