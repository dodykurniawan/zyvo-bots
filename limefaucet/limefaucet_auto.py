#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LimeFaucet Auto-All
===================
Bot otomatis untuk limefaucet.com memakai HTTP murni (requests) — TANPA
Playwright, Selenium, pyppeteer, atau browser apa pun.

Fitur:
  * Auto login (email FaucetPay, tanpa password) + sesi persisten (cookie)
  * Faucet claim tiap 5 menit, captcha ROTASI di-solve lokal (gratis, PIL+numpy)
    dengan fallback solver online (api.waryono.my.id method "lime")
  * PTC internal: start -> tunggu durasi -> Turnstile -> complete (semua iklan)
  * Daily bonus: cek status -> Turnstile -> claim
  * Shortlink BitcoTasks/OctoClix: best-effort via solver (flag --shortlinks)
  * Watch/offerwall: dilaporkan (tugas eksternal, di luar kendali API)
  * Statistik, retry/backoff, anti-fingerprint "client" ala browser asli

Pemakaian:
    python limefaucet_auto.py --email kamu@faucetpay.email
    python limefaucet_auto.py --email ... --once        # satu siklus (test)
    python limefaucet_auto.py --email ... --no-ptc      # faucet saja
    python limefaucet_auto.py --selftest                # test solver rotasi

Konfigurasi (opsional, lewat file config.env / environment / CLI):
    LIME_EMAIL=email@faucetpay.email
    CAPTCHA_APIKEY=apikey-waryono
    CAPTCHA_APIKEY=... (alias CAPTCHA_APIKEY lain didukung)

Dependencies:  pip install -r requirements.txt
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import logging
import os
import random
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

try:
    import requests
except ImportError:  # pragma: no cover
    print("!! requests belum terpasang:  pip install requests", file=sys.stderr)
    raise

try:
    import numpy as np
    from PIL import Image
except ImportError:  # pragma: no cover
    print("!! Pillow & numpy dibutuhkan:  pip install pillow numpy", file=sys.stderr)
    raise


# ---------------------------------------------------------------------------
# Konstanta situs
# ---------------------------------------------------------------------------

SITE = "https://limefaucet.com"
API = SITE + "/api"
BG_IMAGE_URL = SITE + "/captcha-lime.jpg"
DEFAULT_TURNSTILE_SITEKEY = "0x4AAAAAAD_JMYUykdNqm47T"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

BROWSER_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": SITE,
    "Referer": SITE + "/",
    "sec-ch-ua": '"Chromium";v="131", "Not_A Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
}

# Endpoint solver (2Captcha-compatible, JSON)
SKB_IN = "https://api.waryono.my.id/in.php"
SKB_RES = "https://api.waryono.my.id/res.php"
SKB_BALANCE = "https://api.waryono.my.id/balance.php"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

class _ColorFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\033[90m",
        logging.INFO: "\033[96m",
        logging.WARNING: "\033[33m",
        logging.ERROR: "\033[31m",
        logging.CRITICAL: "\033[1;31m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        color = self.COLORS.get(record.levelno, "")
        return f"{color}{msg}{self.RESET}" if color else msg


def setup_logging(debug: bool = False, log_file: Optional[str] = None) -> logging.Logger:
    logger = logging.getLogger("lime")
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.handlers.clear()

    fmt = "%(asctime)s │ %(levelname)-7s │ %(message)s"
    datefmt = "%H:%M:%S"

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(_ColorFormatter(fmt, datefmt))
    console.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.addHandler(console)

    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(logging.Formatter(fmt.replace(" │ ", " "), datefmt))
        fh.setLevel(logging.DEBUG)
        logger.addHandler(fh)

    return logger


log = logging.getLogger("lime")


# ---------------------------------------------------------------------------
# Util
# ---------------------------------------------------------------------------

def now() -> float:
    return time.time()


def sleep(sec: float) -> None:
    if sec > 0:
        time.sleep(sec)


def rnd(a: float, b: float) -> float:
    return random.uniform(a, b)


def load_dotenv(path: str = "config.env") -> None:
    """Baca KEY=VALUE sederhana tanpa dependensi python-dotenv."""
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v


def hms(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def as_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def circ_diff(a: float, b: float) -> float:
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


# ---------------------------------------------------------------------------
# Error API
# ---------------------------------------------------------------------------

class ApiError(Exception):
    def __init__(self, status: int, payload: Any, path: str):
        self.status = status
        self.payload = payload
        self.path = path
        if isinstance(payload, dict):
            msg = payload.get("error") or payload.get("message") or json.dumps(payload)[:200]
        else:
            msg = str(payload)[:200]
        super().__init__(f"[{status} {path}] {msg}")

    @property
    def error(self) -> str:
        if isinstance(self.payload, dict):
            return str(self.payload.get("error") or self.payload.get("message") or "")
        return ""


class AuthError(Exception):
    """401/403 'Authentication required' — sesi hilang, perlu login ulang.

    Sengaja TURUNAN dari Exception biasa (bukan ApiError) supaya ditangkap
    oleh handler siklus utama, bukan tertelan oleh try/except di tiap tugas.
    """

    def __init__(self, status: int, payload: Any, path: str):
        self.status = status
        self.payload = payload
        self.path = path
        msg = payload.get("error") if isinstance(payload, dict) else str(payload)
        super().__init__(f"[{status} {path}] {msg}")

    @property
    def error(self) -> str:
        if isinstance(self.payload, dict):
            return str(self.payload.get("error") or self.payload.get("message") or "")
        return ""


# ---------------------------------------------------------------------------
# Client LimeFaucet
# ---------------------------------------------------------------------------


class LimeClient:
    """HTTP client untuk API limefaucet.com (cookie session)."""

    def __init__(self, email: str, cookie_file: str = ".lime_session.json",
                 proxy: Optional[str] = None, debug: bool = False):
        self.email = email
        self.cookie_file = cookie_file
        self.debug = debug
        self.s = requests.Session()
        self.s.headers.update(BROWSER_HEADERS)
        self.s.verify = True
        if proxy:
            self.s.proxies.update({"http": proxy, "https": proxy})
        self.user: Dict[str, Any] = {}
        self.sitekey: str = DEFAULT_TURNSTILE_SITEKEY
        self._load_cookies()

    # --- util ------------------------------------------------------------
    def _log_debug(self, method: str, url: str, resp: Any) -> None:
        if self.debug:
            body = resp if isinstance(resp, str) else json.dumps(resp, ensure_ascii=False)
            log.debug("HTTP %s %s -> %s", method, url, body[:1200])

    def call(self, method: str, path: str, _retried: bool = False, **kw) -> Any:
        url = path if path.startswith("http") else API + path
        kw.setdefault("timeout", 45)
        try:
            r = self.s.request(method, url, **kw)
        except requests.RequestException as exc:
            if not _retried:
                log.warning("Koneksi gagal (%s), coba ulang…", exc.__class__.__name__)
                sleep(4)
                return self.call(method, path, _retried=True, **kw)
            raise ApiError(0, {"error": f"connection: {exc}"}, path) from exc

        try:
            data = r.json()
        except ValueError:
            data = {"_raw": r.text[:400]}

        self._log_debug(method, url, data)

        if r.status_code in (401, 403) and isinstance(data, dict) and \
                "authentication" in str(data.get("error", "")).lower():
            raise AuthError(r.status_code, data, path)
        # 401 apa pun = sesi tak berlaku lagi (termasuk "IP changed,
        # please login again" pada sesi yang terikat IP) → AuthError supaya
        # ditangkap ensure_auth() untuk login ulang, bukan mematikan bot.
        if r.status_code == 401:
            raise AuthError(r.status_code, data, path)
        if r.status_code >= 500 and not _retried:
            log.warning("Server %s di %s, retry…", r.status_code, path)
            sleep(5)
            return self.call(method, path, _retried=True, **kw)
        if r.status_code >= 400:
            raise ApiError(r.status_code, data, path)
        return data

    # --- sesi ------------------------------------------------------------
    def _load_cookies(self) -> None:
        if not os.path.isfile(self.cookie_file):
            return
        try:
            with open(self.cookie_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if data.get("email") == self.email:
                self.s.cookies.update(data.get("cookies") or {})
        except (OSError, ValueError):
            pass

    def _save_cookies(self) -> None:
        try:
            with open(self.cookie_file, "w", encoding="utf-8") as fh:
                json.dump({"email": self.email, "cookies": dict(self.s.cookies)}, fh)
            os.chmod(self.cookie_file, 0o600)
        except OSError:
            pass

    # --- endpoints -------------------------------------------------------
    def config(self) -> Dict[str, Any]:
        r = requests.get(API + "/config", headers=BROWSER_HEADERS, timeout=30)
        cfg = r.json() if r.status_code == 200 else {}
        if cfg.get("turnstile_site_key"):
            self.sitekey = cfg["turnstile_site_key"]
        return cfg

    def login(self) -> Dict[str, Any]:
        # Sesi lama terikat IP lama → buang dulu supaya tidak ikut terkirim
        # (penting kalau IP berubah, mis. pindah WiFi → mobile data).
        self.s.cookies.clear()
        payload = {"email": self.email, "referral_code": None, "referrer": None}
        data = self.call("POST", "/auth/login", json=payload)
        self.user = data.get("user") or {}
        self._save_cookies()
        log.info("Login OK → %s (currency: %s, id: %s)",
                 self.email,
                 self.user.get("preferred_currency", "?"),
                 self.user.get("id", "?"))
        return data

    def ensure_auth(self) -> None:
        """Cek sesi; login kalau belum ada cookie, 401, IP berubah, atau JWT rusak."""
        if not self.s.cookies:
            log.info("Belum ada sesi tersimpan → login…")
            self.login()
        try:
            data = self.call("GET", "/auth/me")
        except (AuthError, ApiError) as exc:
            if not self._session_dead(exc):
                raise
            log.warning("Sesi tak berlaku (%s) → login ulang…",
                        str(exc)[:60])
            self.login()
            data = self.call("GET", "/auth/me")
        user = data.get("user")
        if isinstance(user, dict):
            self.user = user

    @staticmethod
    def _session_dead(exc: Exception) -> bool:
        """True kalau error berarti sesi/cookie tak berlaku (bukan masalah lain)."""
        status = getattr(exc, "status", 0)
        if status in (401, 403):
            return True
        msg = str(exc).lower()
        return any(k in msg for k in ("jwt", "ip changed", "malformed",
                                      "authentication", "session"))

    def me(self) -> Dict[str, Any]:
        data = self.call("GET", "/auth/me")
        if isinstance(data.get("user"), dict):
            self.user = data["user"]
        return data

    def faucet_info(self) -> Dict[str, Any]:
        return self.call("GET", "/faucet/info")

    def crypto_prices(self) -> Dict[str, float]:
        try:
            data = self.call("GET", "/faucet/crypto-prices")
            return {k: as_float(v) for k, v in (data.get("prices") or {}).items()}
        except (ApiError, AuthError):
            return {}

    def rotation_status(self) -> Dict[str, Any]:
        return self.call("GET", "/faucet/rotation-captcha/status")

    def rotation_challenge(self) -> Dict[str, Any]:
        return self.call("POST", "/faucet/rotation-captcha/challenge")

    def rotation_verify(self, session_id: str, angle: float) -> Dict[str, Any]:
        return self.call("POST", "/faucet/rotation-captcha/verify",
                         json={"session_id": session_id, "angle": angle})

    def faucet_claim(self, captcha_token: str, client_fp: Dict[str, Any]) -> Dict[str, Any]:
        return self.call("POST", "/faucet/claim",
                         json={"captcha_token": captcha_token, "client": client_fp})

    def ptc_campaigns(self) -> List[Dict[str, Any]]:
        data = self.call("GET", "/ptc/campaigns")
        return list(data.get("campaigns") or [])

    def ptc_campaign_page(self, slug: str) -> Dict[str, Any]:
        """Dipanggil halaman iframe iklan sebelum start (warm-up)."""
        return self.call("GET", f"/ptc/campaign/{slug}")

    def ptc_start(self, campaign_id: Any) -> Dict[str, Any]:
        return self.call("POST", "/ptc/view/start", json={"campaign_id": campaign_id})

    def ptc_complete(self, session_token: str, turnstile_token: str) -> Dict[str, Any]:
        return self.call("POST", "/ptc/view/complete",
                         json={"session_token": session_token,
                               "turnstile_token": turnstile_token})

    def daily_status(self) -> Dict[str, Any]:
        return self.call("GET", "/daily/status")

    def daily_claim(self, turnstile_token: str) -> Dict[str, Any]:
        return self.call("POST", "/daily/claim", json={"turnstile_token": turnstile_token})

    def shortlinks(self, source: str) -> List[Dict[str, Any]]:
        data = self.call("GET", f"/shortlinks/{source}")
        for key in ("shortlinks", "data", "offers", "items", "links"):
            if isinstance(data.get(key), list):
                return list(data[key])
        if isinstance(data, list):
            return list(data)
        return []

    def history(self, page: int = 1, limit: int = 20) -> Dict[str, Any]:
        return self.call("GET", f"/history?page={page}&limit={limit}")

    def notifications(self) -> Dict[str, Any]:
        return self.call("GET", "/notifications")

    def watch_offers(self) -> Dict[str, Any]:
        return self.call("GET", "/watch/offers")

    def offerwall_urls(self) -> Dict[str, Any]:
        return self.call("GET", "/offerwalls/urls")

    def youtube_identity(self) -> Dict[str, Any]:
        """Identitas widget YouTube (aviso.bz) milik akun kita."""
        return self.call("GET", "/youtube/identity")


# ---------------------------------------------------------------------------
# YouTube Tasks (aviso.bz widget API) — nonton video otomatis, GRATIS
# ---------------------------------------------------------------------------

class AvisoYouTube:
    """Client API widget YouTube aviso.bz.

    Endpoint dipakai (dari reverse widget.js):
        POST /youtube/tasks/identify      → daftarkan hash browser
        GET  /youtube/tasks/counters      → sisa kuota per tipe
        GET  /youtube/tasks/available     → daftar tugas (type=ads/sub/like)
        POST /youtube/tasks/start         → mulai, balikan attemptId + url
        POST /youtube/tasks/timer-status  → {action:start|complete, watchedTime}
        POST /youtube/tasks/complete      → terima hadiah (points)

    Auth: header `X-API-Key` + body/param `hash` (user_hash dari limefaucet).
    Tugas `ads` cukup durasi 1 detik → murni HTTP, tanpa browser.
    """

    def __init__(self, ident: Dict[str, Any], proxy: Optional[str] = None,
                 timeout: int = 30, debug: bool = False):
        self.endpoint = str(ident.get("api_endpoint") or "").rstrip("/")
        self.api_key = str(ident.get("api_key") or "")
        self.user_hash = str(ident.get("user_hash") or "")
        self.user_id = str(ident.get("user_id") or "")
        self.user_sig = str(ident.get("user_sig") or "")
        self.points_per_usd = as_float(ident.get("points_per_usd"), 100000.0)
        self.timeout = timeout
        self.debug = debug
        self.s = requests.Session()
        self.s.headers.update({
            "X-API-Key": self.api_key,
            "Accept-Language": "en",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
            "Origin": SITE,
            "Referer": SITE + "/",
        })
        if proxy:
            self.s.proxies.update({"http": proxy, "https": proxy})
        self.identified = False

    # --- util ------------------------------------------------------------
    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.endpoint}{path}"
        r = self.s.post(url, json=payload, timeout=self.timeout)
        try:
            data = r.json()
        except ValueError:
            data = {"raw": r.text[:300]}
        if r.status_code >= 400:
            code = str(data.get("code") or data.get("error") or r.status_code)
            raise ApiError(r.status_code, {"error": code}, path)
        return data

    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.endpoint}{path}"
        r = self.s.get(url, params=params, timeout=self.timeout)
        try:
            data = r.json()
        except ValueError:
            data = {"raw": r.text[:300]}
        if r.status_code >= 400:
            code = str(data.get("code") or data.get("error") or r.status_code)
            raise ApiError(r.status_code, {"error": code}, path)
        return data

    def _identity_body(self) -> Dict[str, Any]:
        return {"hash": self.user_hash, "ip": None,
                "userAgent": self.s.headers.get("User-Agent", "")}

    # --- API -------------------------------------------------------------
    def identify(self) -> Dict[str, Any]:
        data = self._post("/youtube/tasks/identify", self._identity_body())
        self.identified = True
        return data

    def counters(self) -> Dict[str, Any]:
        data = self._get("/youtube/tasks/counters",
                         {"hash": self.user_hash, "platform": "Win32"})
        return data.get("counters") if isinstance(data.get("counters"), dict) else data

    def available(self, kind: str = "ads") -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"hash": self.user_hash, "platform": "Win32"}
        if kind and kind != "all":
            params["type"] = kind
        data = self._get("/youtube/tasks/available", params)
        items = data.get(kind) if kind != "all" else None
        if isinstance(items, list):
            return items
        for v in data.values():
            if isinstance(v, list):
                return v
        return []

    def start(self, task_id: Any, kind: str = "ads") -> Dict[str, Any]:
        body: Dict[str, Any] = {"taskId": task_id, "type": kind,
                                "platform": "Win32"}
        body.update(self._identity_body())
        if self.user_id:
            body["userId"] = self.user_id
        if self.user_sig:
            body["userSig"] = self.user_sig
        return self._post("/youtube/tasks/start", body)

    def timer_status(self, attempt_id: Any, action: Optional[str] = None,
                     watched_time: Optional[float] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {"attemptId": attempt_id}
        if action:
            body["action"] = action
        if watched_time is not None:
            body["watchedTime"] = watched_time
        return self._post("/youtube/tasks/timer-status", body)

    def complete(self, attempt_id: Any) -> Dict[str, Any]:
        return self._post("/youtube/tasks/complete", {"attemptId": attempt_id})

    def to_usd(self, points: float) -> float:
        return points / self.points_per_usd if self.points_per_usd else 0.0


# ---------------------------------------------------------------------------
# Fingerprint "client" (sesuai field yang dikirim UI asli sebelum claim)
# ---------------------------------------------------------------------------

def build_client_fingerprint() -> Dict[str, Any]:
    return {
        "webdriver": False,
        "chrome_runtime": True,
        "plugins": 5,
        "ua_mobile": False,
        "ua_platform": "Win32",
        "max_touch_points": 0,
        "hardware_concurrency": random.choice([4, 8, 12, 16]),
        "device_memory": random.choice([8, 8, 16]),
        "screen": random.choice(["1920x1080", "1536x864", "1366x768", "2560x1440"]),
        "viewport": random.choice(["1920x945", "1536x755", "1366x657", "2560x1369"]),
        "dpr": 1,
        "languages": 2,
        "webgl_vendor": "Google Inc. (NVIDIA)",
        "webgl_renderer": ("ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 Ti Direct3D11 "
                           "vs_5_0 ps_5_0, D3D11)"),
        "pointer_events": random.randint(10, 400),
        "key_events": random.randint(0, 60),
        "visibility_changes": random.randint(1, 12),
    }


# ---------------------------------------------------------------------------
# Solver captcha rotasi (lokal, gratis)
# ---------------------------------------------------------------------------
#
# Mekanik puzzle di situsnya:
#   ctx.drawImage(bg, 0,0,c,c)                       -> latar /captcha-lime.jpg
#   clip lingkaran di (crop.x*c, crop.y*c) r=crop.radius*c
#   ctx.rotate(m) ; ctx.drawImage(piece, -A,-A,2A,2A) -> potongan gambar
# Pengguna memutar slider sampai potongan menyatu dengan latar; nilai m itulah
# jawaban yang dikirim ke /verify.
#
# Kanvas rotate(m) (y ke bawah) = PIL rotate(-m). Solver mencari angle `a`
# sedemikian rupa sehingga piece.rotate(-a) ≈ patch latar → jawaban = a.

class RotationSolver:
    CANVAS = 512          # resolusi kerja (latar diskalakan ke sini)
    MIN_SCORE = 0.35      # korelasi minimal untuk percaya hasil lokal

    def __init__(self, bg_path: Optional[str] = None):
        self._bg_cache: Optional[Image.Image] = None
        self.bg_path = bg_path
        self._flip = False               # False = jawaban = angle hasil solver
        self._flips = 0
        # --- auto-update: penanda versi gambar di server -------------
        # Disimpan di file .meta.json supaya lintas restart tetap bisa
        # pakai If-None-Match (server balas 304 = 0 byte = hemat kuota).
        self._etag: Optional[str] = None
        self._last_modified: Optional[str] = None
        self._load_meta()

    # --- auto-update: deteksi perubahan gambar captcha di situs --------
    # Catatan penting soal kuota: /captcha-lime.jpg TIDAK mendukung
    # ETag/Last-Modified/Range — server SELALU mengirim 141 KB penuh.
    # Karena itu pengecekan dibuat jarang (default 1x/24 jam) lewat
    # --captcha-revalidate, bukan tiap siklus.
    def _meta_path(self) -> Optional[str]:
        return (self.bg_path + ".meta.json") if self.bg_path else None

    def _read_meta(self) -> Dict[str, Any]:
        p = self._meta_path()
        if p and os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as fh:
                    m = json.load(fh)
                if isinstance(m, dict):
                    self._etag = m.get("etag")
                    self._last_modified = m.get("last_modified")
                    return m
            except (OSError, ValueError):
                pass
        return {}

    def _load_meta(self) -> None:
        self._read_meta()

    def _save_meta(self, resp: Any = None, extra: Optional[Dict[str, Any]] = None) -> None:
        """Catat ETag/Last-Modified dari server + sha256 file lokal."""
        p = self._meta_path()
        if not p:
            return
        if resp is not None:
            self._etag = resp.headers.get("ETag") or self._etag
            self._last_modified = resp.headers.get("Last-Modified") or self._last_modified
        m = self._read_meta()
        m.update({"etag": self._etag,
                  "last_modified": self._last_modified,
                  "sha256": self.file_sha(),
                  "checked_at": int(time.time())})
        if extra:
            m.update(extra)
        try:
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(m, fh)
        except OSError:
            pass

    def file_sha(self) -> str:
        """sha256 file latar di disk ("" kalau belum ada)."""
        if not self.bg_path or not os.path.isfile(self.bg_path):
            return ""
        h = hashlib.sha256()
        try:
            with open(self.bg_path, "rb") as fh:
                for chunk in iter(lambda: fh.read(65536), b""):
                    h.update(chunk)
        except OSError:
            return ""
        return h.hexdigest()

    def _fetch_from_site(self, sha_old: str) -> str:
        """Unduh gambar dari situs, timpa kalau sha-nya berbeda."""
        try:
            r = requests.get(BG_IMAGE_URL, headers=BROWSER_HEADERS, timeout=30)
        except requests.RequestException as exc:
            log.debug("Unduh captcha gagal: %s", exc)
            return "error"
        if r.status_code != 200:
            log.debug("Unduh captcha: HTTP %s", r.status_code)
            return "error"
        new_sha = hashlib.sha256(r.content).hexdigest()
        if new_sha == sha_old:
            self._save_meta(r, {"last_direct_check": int(time.time())})
            return "unchanged"
        # --- GAMBAR BERUBAH → timpa, buang cache, reset konvensi -----
        try:
            with open(self.bg_path, "wb") as fh:
                fh.write(r.content)
            os.chmod(self.bg_path, 0o644)
        except OSError as exc:
            log.error("Gagal menulis gambar captcha baru: %s", exc)
            return "error"
        self._save_meta(r, {"last_direct_check": int(time.time())})
        self._bg_cache = None
        self.reset_sign()
        log.warning("CAPTCHA BARU TERDETEKSI — /captcha-lime.jpg berganti "
                    "(sha256 %s… → %s…). Latar & konvensi rotasi di-reset, "
                    "solver memakai gambar baru tanpa restart.",
                    (sha_old or "kosong")[:12], new_sha[:12])
        return "updated"

    def revalidate(self, force: bool = False) -> str:
        """Cek apakah gambar captcha di situs sudah berganti.

        Murni lokal: langsung mengunduh /captcha-lime.jpg lalu membandingkan
        sha256-nya dengan file di disk. Karena server tidak mendukung
        ETag/Range, tiap pengecekan berarti unduh 141 KB — jadi frekuensinya
        dibatasi --captcha-revalidate (default 24 jam ≈ 141 KB/hari).

        force=True dipakai saat solver gagal 6x berturut-turut (kemungkinan
        algoritma captcha berubah) supaya tidak perlu menunggu jadwal.

        Mengembalikan: "unchanged" | "updated" | "error" | "skipped".
        """
        if not self.bg_path:
            return "skipped"
        return self._fetch_from_site(self.file_sha())

    # --- latar -----------------------------------------------------------
    def background(self) -> Image.Image:
        if self._bg_cache is not None:
            return self._bg_cache
        img: Optional[Image.Image] = None
        # pakai file lokal kalau ada dan belum basi (>7 hari) — hemat kuota
        if self.bg_path and os.path.isfile(self.bg_path):
            age = time.time() - os.path.getmtime(self.bg_path)
            if age < 7 * 86400:
                try:
                    img = Image.open(self.bg_path)
                except OSError:
                    img = None
        if img is None:
            r = requests.get(BG_IMAGE_URL, headers=BROWSER_HEADERS, timeout=30)
            r.raise_for_status()
            img = Image.open(io.BytesIO(r.content))
            if self.bg_path:
                try:
                    with open(self.bg_path, "wb") as fh:
                        fh.write(r.content)
                    os.chmod(self.bg_path, 0o644)
                    self._save_meta(r)   # simpan ETag → cek berikutnya 304
                except OSError:
                    pass
        self._bg_cache = img.convert("RGB")
        return self._bg_cache

    # --- ambil potongan gambar dari challenge -----------------------------
    @staticmethod
    def load_piece(challenge: Dict[str, Any], referer: str = SITE + "/faucet",
                   session: Optional[Any] = None) -> Image.Image:
        """Unduh gambar piece/variant.

        `session` WAJIB berupa requests.Session yang sudah login: endpoint
        /rotation-captcha/variant/ menolak akses tanpa cookie sesi (401).
        """
        src = (challenge.get("image") or challenge.get("url") or
               challenge.get("piece_url") or challenge.get("piece"))
        if not src:
            raise ValueError("challenge tidak memuat url gambar piece")

        http = session or requests
        if isinstance(src, str) and src.startswith("data:"):
            b64 = src.split(",", 1)[1]
            raw = base64.b64decode(b64)
        elif src.startswith("http://") or src.startswith("https://"):
            r = http.get(src, headers={**BROWSER_HEADERS, "Referer": referer}, timeout=30)
            r.raise_for_status()
            raw = r.content
        else:
            url = src if src.startswith("/") else "/" + src
            r = http.get(SITE + url, headers={**BROWSER_HEADERS, "Referer": referer},
                         timeout=30)
            r.raise_for_status()
            raw = r.content
        return Image.open(io.BytesIO(raw))

    # --- inti solver ------------------------------------------------------
    def solve(self, piece: Image.Image, crop: Dict[str, Any]) -> Tuple[int, float]:
        """Kembalikan (angle_derajat, skor_korelasi_0..1)."""
        c = self.CANVAS
        cx = as_float(crop.get("x"), 0.5) * c
        cy = as_float(crop.get("y"), 0.5) * c
        radius = as_float(crop.get("radius"), 0.1) * c

        box = int(max(24, round(2 * radius)))
        if box % 2:
            box += 1

        bg = self.background().resize((c, c), Image.BILINEAR)
        left = int(round(cx - box / 2.0))
        top = int(round(cy - box / 2.0))
        left = max(0, min(left, c - box))
        top = max(0, min(top, c - box))
        patch = bg.crop((left, top, left + box, top + box))

        p = piece.convert("RGBA").resize((box, box), Image.BILINEAR)

        # masker lingkaran
        yy, xx = np.ogrid[:box, :box]
        rr = radius
        mask = ((xx - box / 2.0) ** 2 + (yy - box / 2.0) ** 2) <= (rr ** 2)
        mask_f = mask.astype(np.float32)

        patch_arr = np.asarray(patch, dtype=np.float32)
        patch_flat = patch_arr[mask]                       # (N,3)
        patch_vec = (patch_flat - patch_flat.mean(axis=0)).ravel()
        patch_norm = np.linalg.norm(patch_vec)
        if patch_norm < 1e-6:
            return 0, 0.0

        best_angle, best_score = 0, -2.0
        for a in range(360):
            rot = p.rotate(-a, resample=Image.BILINEAR, expand=False,
                           fillcolor=(0, 0, 0, 0))
            arr = np.asarray(rot.convert("RGB"), dtype=np.float32)
            vals = arr[mask]
            vec = vals - vals.mean(axis=0)
            denom = np.linalg.norm(vec) * patch_norm
            if denom < 1e-6:
                continue
            score = float(np.dot(vec.ravel(), patch_vec) / denom)
            if score > best_score:
                best_score, best_angle = score, a

        # refine halus di sekitar best (opsional, mempertajam)
        fine_angle, fine_score = float(best_angle), best_score
        for da in (-1.5, -1.0, -0.5, 0.5, 1.0, 1.5):
            a = (best_angle + da) % 360.0
            rot = p.rotate(-a, resample=Image.BICUBIC, expand=False, fillcolor=(0, 0, 0, 0))
            arr = np.asarray(rot.convert("RGB"), dtype=np.float32)
            vals = arr[mask]
            vec = vals - vals.mean(axis=0)
            denom = np.linalg.norm(vec) * patch_norm
            if denom < 1e-6:
                continue
            score = float(np.dot(vec.ravel(), patch_vec) / denom)
            if score > fine_score:
                fine_score, fine_angle = score, a

        # Jawaban slider = nilai m yang membuat ctx.rotate(m) menyatukan potongan
        # dengan latar. Kanvas rotate(m) == PIL rotate(-m); solver sudah mencari a
        # dari piece.rotate(-a) ≈ patch, sehingga jawaban = a itu sendiri.
        # self._flip dipakai sebagai jaring pengaman bila server menolak jawaban.
        answer = (-fine_angle if self._flip else fine_angle) % 360.0
        return int(round(answer)) % 360, max(0.0, fine_score)

    def flip_sign(self) -> int:
        """Dipanggil kalau server menolak jawaban → balik konvensi rotasi."""
        self._flip = not self._flip
        self._flips += 1
        log.warning("Konvensi rotasi dibalik (flip=%s, ke-%d kali)",
                    self._flip, self._flips)
        return -1 if self._flip else 1

    def reset_sign(self) -> None:
        self._flip = False
        self._flips = 0

    # --- selftest ---------------------------------------------------------
    @staticmethod
    def selftest(verbose: bool = True) -> bool:
        """Buat puzzle sintetis dari latar, lalu coba tebak sudutnya."""
        solver = RotationSolver(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                             ".captcha-lime.jpg"))
        bg = solver.background().resize((512, 512), Image.BILINEAR)
        ok_all = True
        for trial in range(5):
            crop = {"x": round(random.uniform(0.2, 0.8), 3),
                    "y": round(random.uniform(0.2, 0.8), 3),
                    "radius": round(random.uniform(0.09, 0.14), 3)}
            true_m = random.randint(0, 359)
            # potongan dibuat dari latar lalu diputar sebesar +true_m (PIL CCW),
            # sehingga jawaban yang benar = true_m
            box = 2 * int(round(crop["radius"] * 512))
            if box % 2:
                box += 1
            cx, cy = crop["x"] * 512, crop["y"] * 512
            left, top = int(round(cx - box / 2)), int(round(cy - box / 2))
            patch = bg.crop((left, top, left + box, top + box))
            piece = patch.rotate(true_m, resample=Image.BICUBIC, expand=False)
            solver.reset_sign()
            angle, score = solver.solve(piece, crop)
            diff = circ_diff(angle, true_m)
            good = diff <= 2.0 and score > 0.5
            ok_all = ok_all and good
            if verbose:
                log.info("selftest#%d  crop=(%.2f,%.2f,r%.3f)  true=%3d  got=%3d  "
                         "diff=%4.1f  score=%.3f  %s",
                         trial, crop["x"], crop["y"], crop["radius"], true_m, angle,
                         diff, score, "OK" if good else "GAGAL")
        return ok_all


# ---------------------------------------------------------------------------
# Solver eksternal (api.waryono.my.id — 2Captcha compatible)
# ---------------------------------------------------------------------------

class SkibidiSolver:
    """Wrapper API SKIBIDIXXX (waryono.my.id): turnstile / lime / shortlink."""

    def __init__(self, apikey: str, timeout: int = 300, poll: float = 2.5):
        self.apikey = apikey
        self.timeout = timeout
        self.poll = poll
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": USER_AGENT,
                                      "Content-Type": "application/json"})

    # --- util ------------------------------------------------------------
    def balance(self) -> Optional[float]:
        try:
            r = self._session.get(SKB_BALANCE, params={"apikey": self.apikey, "json": 1},
                                  timeout=20)
            data = r.json()
            if data.get("status") == 1:
                return float(data.get("balance", 0))
        except Exception as exc:  # noqa: BLE001
            log.debug("balance error: %s", exc)
        return None

    def _submit(self, payload: Dict[str, Any]) -> str:
        payload = {"apikey": self.apikey, "json": 1, **payload}
        r = self._session.post(SKB_IN, json=payload, timeout=30)
        try:
            data = r.json()
        except ValueError:
            data = {"status": 0, "request": r.text[:200]}
        if data.get("status") != 1:
            raise RuntimeError(f"submit gagal: {data.get('request')}")
        return str(data.get("request"))

    def _poll(self, task_id: str) -> str:
        deadline = now() + self.timeout
        while now() < deadline:
            r = self._session.get(SKB_RES, params={
                "apikey": self.apikey, "id": task_id, "action": "get", "json": 1},
                timeout=30)
            try:
                data = r.json()
            except ValueError:
                data = {"status": 0, "request": "CAPCHA_NOT_READY"}
            req = str(data.get("request", ""))
            if data.get("status") == 1:
                return req
            if req and req != "CAPCHA_NOT_READY":
                raise RuntimeError(f"poll gagal: {req}")
            sleep(self.poll)
        raise RuntimeError("timeout menunggu hasil solver")

    # --- metode ----------------------------------------------------------
    def turnstile(self, action: Optional[str] = None,
                  pageurl: str = SITE, sitekey: Optional[str] = None) -> str:
        payload: Dict[str, Any] = {
            "methods": "turnstile",
            "sitekey": sitekey or DEFAULT_TURNSTILE_SITEKEY,
            "domain": pageurl,
            "pageurl": pageurl,
        }
        if action:
            payload["action"] = action
        tid = self._submit(payload)
        token = self._poll(tid)
        log.debug("turnstile(%s) → %s…", action, token[:40])
        return token

    def lime(self, piece_b64: str, x: float, y: float, radius: float) -> int:
        """Solver khusus captcha rotasi LimeFaucet (method 'lime')."""
        tid = self._submit({"methods": "lime", "base64": piece_b64,
                            "x": x, "y": y, "radius": radius})
        ans = self._poll(tid)
        m = re.search(r"(-?\d+(?:\.\d+)?)", str(ans))
        if not m:
            raise RuntimeError(f"format jawaban lime tak dikenal: {ans!r}")
        return int(round(float(m.group(1)))) % 360

    def shortlink(self, url: str) -> str:
        tid = self._submit({"methods": "shortlink", "url": url})
        return self._poll(tid)


# ---------------------------------------------------------------------------
# Pengatur token (apikey) — strategi supaya saldo solver cepat habis
# ---------------------------------------------------------------------------

class TokenBudget:
    """Penjaga saldo token solver.

    Strategi penghematan, berurutan dari yang paling menentukan:

    1. **Cadangan (reserve)**   — tak pernah memakai token sampai saldo
       tersisa di bawah angka ini, jadi selalu ada jaminan untuk daily
       bonus / klaim mendadak.
    2. **Anggaran (budget)**   — batas token per proses; sekali tercapai,
       semua tugas ber-captcha dilewati (faucet tetap jalan karena gratis).
    3. **Pakai ulang (reuse)** — token Turnstile terakhir disimpan selama
       REUSE_TTL detik lalu dicoba lagi untuk tugas berikutnya. Percobaan
       ulang TIDAK membeli token baru, jadi gratis: kalau server menerima,
       hemat 100%; kalau menolak, otomatis beli token baru seperti biasa.
    4. **Urutan ROI**          — faucet (gratis) → shortlink → daily → PTC,
       supaya anggaran terpakai untuk yang paling menguntungkan dulu.
    5. **Filter ROI**          — iklan/shortlink yang nilainya lebih kecil
       dari biaya token dilewati (kalau --token-price diisi).
    """

    TTL = 60.0          # detik cache saldo
    REUSE_TTL = 240.0   # detik umur token Turnstile (Cloudflare ~300s)

    def __init__(self, solver: Optional["SkibidiSolver"], budget: float = 0.0,
                 reserve: float = 100.0, price_per_1k: float = 0.0,
                 reuse: bool = True):
        self.solver = solver
        self.budget = float(budget or 0)
        self.reserve = float(reserve or 0)
        self.price = float(price_per_1k or 0)
        self.reuse = reuse
        self.spent = 0.0            # token keluar selama proses ini
        self.solves = 0             # jumlah solve berbayar
        self.reused_ok = 0          # reuse diterima server
        self.reused_fail = 0        # reuse ditolak → solve baru
        self._cache: Dict[str, Tuple[str, float]] = {}
        self._bal_start: Optional[float] = self._fetch()
        self._bal_live: Optional[float] = self._bal_start
        self._bal_at: float = 0.0

    # --- saldo ----------------------------------------------------------
    def _fetch(self) -> Optional[float]:
        if not self.solver:
            return None
        try:
            return self.solver.balance()
        except Exception as exc:  # noqa: BLE001
            log.debug("balance: %s", exc)
            return None

    def balance(self, refresh: bool = False) -> Optional[float]:
        if not self.solver:
            return None
        if refresh or self._bal_live is None or now() - self._bal_at > self.TTL:
            val = self._fetch()
            if val is not None:
                self._bal_live = val
                self._bal_at = now()
        return self._bal_live

    def start_balance(self) -> Optional[float]:
        return self._bal_start

    def remaining(self) -> Optional[float]:
        """Perkiraan sisa saldo: saldo awal − yang sudah dipakai."""
        if self._bal_start is None:
            return None
        return self._bal_start - self.spent

    # --- aturan pemakaian ------------------------------------------------
    def cost_usd(self, tokens: float) -> float:
        return tokens * self.price / 1000.0 if self.price > 0 else 0.0

    def min_reward_usd(self, fallback: float = 0.0) -> float:
        """Nilai minimum sebuah tugas supaya layak dibeli token-nya."""
        if self.price > 0:
            return max(fallback, self.cost_usd(1.0))
        return fallback

    def can(self, cost: float = 1.0, what: str = "tugas") -> bool:
        if not self.solver:
            return False
        if self.budget > 0 and self.spent + cost > self.budget:
            log.info("Anggaran token tercapai (%.1f/%.1f) → %s dilewati.",
                     self.spent, self.budget, what)
            return False
        rem = self.remaining()
        if rem is not None and rem - cost < self.reserve:
            log.warning("Saldo token tinggal ≈%.1f (cadangan %.1f) → %s dilewati.",
                        rem, self.reserve, what)
            return False
        return True

    def charge(self, cost: float = 1.0) -> None:
        self.spent += cost
        self.solves += 1

    # --- token Turnstile + reuse ----------------------------------------
    def turnstile(self, action: str, pageurl: str, sitekey: Optional[str],
                  cost: float = 1.0) -> Tuple[Optional[str], bool]:
        """Kembalikan (token, dipakai_ulang?).

        Kalau `reuse` aktif dan ada token lama untuk action+pageurl yang
        masih hidup, token itu dikirim dulu — percobaannya gratis.
        """
        key = f"{action}|{pageurl}"
        if self.reuse:
            hit = self._cache.get(key)
            if hit and now() - hit[1] < self.REUSE_TTL:
                log.debug("Coba pakai ulang token %s (umur %.0fs)",
                          action, now() - hit[1])
                return hit[0], True

        if not self.can(cost, what=f"solve {action}"):
            return None, False
        try:
            token = self.solver.turnstile(action=action, pageurl=pageurl,
                                          sitekey=sitekey)
        except Exception as exc:  # noqa: BLE001
            log.error("Turnstile %s gagal: %s", action, exc)
            return None, False
        self.charge(cost)
        self._cache[key] = (token, now())
        return token, False

    def reuse_ok(self) -> None:
        self.reused_ok += 1

    def invalidate(self, action: str, pageurl: str = "") -> None:
        if pageurl:
            self._cache.pop(f"{action}|{pageurl}", None)
        else:
            for k in [k for k in self._cache if k.startswith(action + "|")]:
                self._cache.pop(k, None)

    # --- laporan ---------------------------------------------------------
    def report(self) -> str:
        if not self.solver:
            return "Token: tanpa API key (Turnstile & shortlink nonaktif)"
        bal = self.balance(refresh=True)
        parts = [f"Token dipakai {self.spent:.1f} ({self.solves} solve)"]
        if self.price > 0:
            parts.append(f"≈${self.cost_usd(self.spent):.6f}")
        if self.reused_ok or self.reused_fail:
            parts.append(f"reuse OK {self.reused_ok} / gagal {self.reused_fail}")
        if bal is not None:
            parts.append(f"sisa saldo {bal:.1f}")
            if self._bal_start is not None:
                parts.append(f"Δ {self._bal_start - bal:.1f}")
        return " | ".join(parts)


# ---------------------------------------------------------------------------
# Worker: semua tugas
# ---------------------------------------------------------------------------

@dataclass
class Stats:
    faucet_ok: int = 0
    faucet_fail: int = 0
    ptc_ok: int = 0
    ptc_fail: int = 0
    daily_ok: int = 0
    daily_fail: int = 0
    shortlink_ok: int = 0
    shortlink_fail: int = 0
    yt_ok: int = 0
    yt_fail: int = 0
    yt_points: float = 0.0
    earned: Dict[str, float] = field(default_factory=dict)

    def add(self, action: str, currency: str, amount: float) -> None:
        self.earned[currency or "?"] = self.earned.get(currency or "?", 0.0) + amount

    def summary(self, prices: Dict[str, float], currency: str) -> str:
        lines = ["─" * 52,
                 f"  Faucet claim : {self.faucet_ok} sukses / {self.faucet_fail} gagal",
                 f"  PTC          : {self.ptc_ok} sukses / {self.ptc_fail} gagal",
                 f"  Daily bonus  : {self.daily_ok} sukses / {self.daily_fail} gagal",
                 f"  Shortlink    : {self.shortlink_ok} sukses / {self.shortlink_fail} gagal",
                 f"  YouTube      : {self.yt_ok} sukses / {self.yt_fail} gagal"
                 + (f"  ({self.yt_points:.1f} pts)" if self.yt_points else "")]
        total_usd = 0.0
        for cur, amt in sorted(self.earned.items()):
            price = prices.get(cur, 0.0)
            usd = amt * price
            total_usd += usd
            extra = f"  (~{usd:.6f} USD)" if price else ""
            lines.append(f"  +{amt:.8f} {cur}{extra}")
        lines.append(f"  TOTAL ≈ {total_usd:.6f} USD (prefer: {currency})")
        lines.append("─" * 52)
        return "\n".join(lines)


class Bot:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.client = LimeClient(args.email,
                                 cookie_file=args.cookie_file,
                                 proxy=args.proxy,
                                 debug=args.debug)
        # Latar captcha: pakai path lokal bawaan supaya TIDAK diunduh ulang
        # tiap proses (hemat 141 KB/run = 13 MB/hari pada mode --once).
        self.rotator = RotationSolver(
            args.bg_image or os.path.join(
                os.path.dirname(os.path.abspath(__file__)), ".captcha-lime.jpg"))
        self.solver: Optional[SkibidiSolver] = (
            SkibidiSolver(args.captcha_key) if args.captcha_key else None)
        self.budget = TokenBudget(
            self.solver,
            budget=getattr(args, "token_budget", 0.0),
            reserve=getattr(args, "token_reserve", 100.0),
            price_per_1k=getattr(args, "token_price", 0.0),
            reuse=not getattr(args, "no_token_reuse", False))
        self.stats = Stats()
        self.prices: Dict[str, float] = {}
        self.fingerprint = build_client_fingerprint()
        self.next_faucet = 0.0
        self.next_ptc = 0.0
        self.next_daily = 0.0
        self.next_shortlink = 0.0
        self.next_youtube = 0.0
        self.next_captcha_check = 0.0     # auto-update gambar captcha
        # Jadwal cek captcha diambil dari meta, supaya restart bot tidak
        # langsung mengunduh ulang gambar 141 KB.
        try:
            _last = float(self.rotator._read_meta().get("last_direct_check", 0) or 0)
        except (AttributeError, TypeError, ValueError):
            _last = 0.0
        _iv = int(getattr(self.args, "captcha_revalidate", 86400) or 0)
        self.next_captcha_check = (_last + max(300, _iv)) if _last > 0 else 0.0
        self._wrong_streak = 0            # berapa kali sudut salah berturut-turut
        self._last_report = 0.0
        # sumber shortlink yang provider-nya tak bisa solve (hemat token)
        self.state_file = f"{args.cookie_file}.state.json"
        self.shortlink_dead: set = set()
        self._load_state()
        # client YouTube (aviso.bz) — diisi saat pertama kali dipakai
        self.yt: Optional[AvisoYouTube] = None

    # --- helper ----------------------------------------------------------
    def _need_turnstile(self, action: str, pageurl: str,
                        allow_reuse: bool = True) -> Tuple[Optional[str], bool]:
        """Ambil token Turnstile dari pengatur token → (token, reuse?)."""
        if not self.solver:
            log.info("Turnstile dibutuhkan (%s) tapi tidak ada API key — dilewati.",
                     action)
            return None, False
        saved = self.budget.reuse
        self.budget.reuse = saved and allow_reuse
        try:
            return self.budget.turnstile(action, pageurl, self.client.sitekey)
        finally:
            self.budget.reuse = saved

    @staticmethod
    def _is_captcha_error(exc: Exception) -> bool:
        return "captcha" in str(exc).lower()

    # --- state lintas proses (hemat token) -------------------------------
    def _load_state(self) -> None:
        """Baca status shortlink mati; kedaluwarsa 24 jam."""
        try:
            with open(self.state_file, encoding="utf-8") as fh:
                data = json.load(fh)
            if now() - as_float(data.get("dead_at"), 0) < 86400:
                self.shortlink_dead = set(data.get("shortlink_dead") or [])
                if self.shortlink_dead:
                    log.info("Shortlink mati dari sesi sebelumnya: %s "
                             "(hemat token, kedaluwarsa 24 jam)",
                             ", ".join(sorted(self.shortlink_dead)))
        except (OSError, ValueError):
            pass

    def _save_state(self) -> None:
        try:
            with open(self.state_file, "w", encoding="utf-8") as fh:
                json.dump({"shortlink_dead": sorted(self.shortlink_dead),
                           "dead_at": now()}, fh)
            os.chmod(self.state_file, 0o600)
        except OSError:
            pass

    # --- captcha rotasi ---------------------------------------------------
    def solve_rotation(self) -> Optional[str]:
        for attempt in range(1, 6):
            try:
                st = self.client.rotation_status()
            except ApiError as exc:
                log.error("rotation status: %s", exc)
                sleep(3)
                continue

            locked_until = as_float(st.get("locked_until"), 0) / 1000.0
            if st.get("blocked") and locked_until > now():
                wait = locked_until - now() + 1
                log.warning("Captcha rotasi terkunci %s, tunggu…", hms(wait))
                sleep(wait)
                continue

            try:
                ch_resp = self.client.rotation_challenge()
            except ApiError as exc:
                if exc.status == 429:
                    wait = as_float((exc.payload or {}).get("locked_until"), 0) / 1000.0 - now() + 1 \
                        if isinstance(exc.payload, dict) else 30
                    log.warning("Terlalu banyak request challenge, tunggu %ss…", int(wait))
                    sleep(max(5, wait))
                    continue
                log.error("challenge gagal: %s", exc)
                sleep(3)
                continue

            challenge = ch_resp.get("challenge") or {} if isinstance(ch_resp, dict) else {}
            session_id = (ch_resp.get("session_id") or ch_resp.get("token")) \
                if isinstance(ch_resp, dict) else None
            if not isinstance(challenge, dict) or not challenge or not session_id:
                log.error("response challenge aneh: %s", json.dumps(ch_resp)[:300])
                return None

            angle, score = self._angle_for(challenge)
            try:
                v = self.client.rotation_verify(str(session_id), angle)
            except ApiError as exc:
                err = exc.error.lower()
                if exc.status == 429:
                    wait = 30
                    if isinstance(exc.payload, dict):
                        lu = as_float(exc.payload.get("locked_until"), 0)
                        if lu > 1e12:
                            lu /= 1000.0
                        if lu > now():
                            wait = lu - now() + 1
                    log.warning("Rate-limit verify, tunggu %ss…", int(wait))
                    sleep(max(5, wait))
                    continue
                if "wrong" in err:
                    left = None
                    if isinstance(exc.payload, dict):
                        left = exc.payload.get("attempts_left")
                    log.warning("Sudut salah (sisa %s). Coba konvensi lain…", left)
                    self._wrong_streak += 1
                    # 6 kali berturut-turut salah = gambar/solver tidak cocok
                    # lagi → paksa unduh ulang latar dari situs.
                    if self._wrong_streak >= 6:
                        log.warning("Sudut salah %d kali berturut-turut → "
                                    "kemungkinan captcha berubah, unduh ulang "
                                    "latar…", self._wrong_streak)
                        self._wrong_streak = 0
                        self.rotator.revalidate(force=True)
                    self.rotator.flip_sign()
                    continue
                if "turnstile" in err or "sitekey" in err:
                    log.error("Situs tampaknya MENGGANTI JENIS CAPTCHA ke "
                              "Turnstile (%s). Isi CAPTCHA_APIKEY di config.env "
                              "untuk fitur PTC/Daily; faucet memakai captcha "
                              "rotasi.", exc.error)
                    continue
                if "expired" in err:
                    log.warning("Challenge expired, ambil baru…")
                    continue
                log.error("verify gagal: %s", exc)
                sleep(2)
                continue

            if v.get("ok"):
                token = v.get("token") or v.get("captcha_token") or ""
                log.debug("verify OK angle=%s score=%.3f", angle, score)
                self._wrong_streak = 0
                return token
            log.warning("verify tidak ok: %s", json.dumps(v)[:200])
        return None

    def _angle_for(self, challenge: Dict[str, Any]) -> Tuple[int, float]:
        crop = challenge.get("crop") or {}
        try:
            piece = RotationSolver.load_piece(challenge, session=self.client.s)
            angle, score = self.rotator.solve(piece, crop)
        except Exception as exc:  # noqa: BLE001
            log.warning("Solver lokal gagal (%s), pakai solver online…", exc)
            score = 0.0
            angle = -1

        if score < RotationSolver.MIN_SCORE:
            if not self.solver:
                log.error("Skor lokal %.3f dan tidak ada API key solver online.", score)
                return angle % 360, score
            try:
                b64 = self._piece_b64(challenge)
                remote = self.solver.lime(b64,
                                          as_float(crop.get("x"), 0.5),
                                          as_float(crop.get("y"), 0.5),
                                          as_float(crop.get("radius"), 0.1))
                log.info("Solver online lime → angle=%d (lokal skor %.3f)", remote, score)
                return remote, score
            except Exception as exc:  # noqa: BLE001
                log.warning("Solver online lime gagal: %s", exc)
        return angle % 360, score

    def _piece_b64(self, challenge: Dict[str, Any]) -> str:
        src = (challenge.get("image") or challenge.get("url") or
               challenge.get("piece_url") or "")
        if isinstance(src, str) and src.startswith("data:"):
            return src.split(",", 1)[1]
        if src.startswith("http") or src.startswith("/"):
            url = src if src.startswith("http") else SITE + src
            r = self.client.s.get(url, headers=BROWSER_HEADERS, timeout=30)
            r.raise_for_status()
            return base64.b64encode(r.content).decode()
        raise ValueError("gambar piece tidak dikenal")

    # --- tugas ------------------------------------------------------------
    def task_faucet(self) -> None:
        if self.args.no_faucet:
            return
        if now() < self.next_faucet:
            return

        try:
            info = self.client.faucet_info()
        except ApiError as exc:
            log.error("faucet info: %s", exc)
            self.next_faucet = now() + 30
            return

        remaining = as_float(info.get("time_remaining_seconds"), 0)
        if remaining > 0:
            self.next_faucet = now() + remaining + 1
            log.debug("Faucet masih cooldown %s", hms(remaining))
            return

        if info.get("can_claim") is False:
            log.info("Faucet: can_claim=false → tunggu 60s")
            self.next_faucet = now() + 60
            return

        token = self.solve_rotation()
        if not token:
            log.error("Faucet: gagal dapat token captcha rotasi.")
            self.stats.faucet_fail += 1
            self.next_faucet = now() + 30
            return

        try:
            res = self.client.faucet_claim(token, self.fingerprint)
        except ApiError as exc:
            self.stats.faucet_fail += 1
            msg = exc.error
            if "cooldown" in msg:
                m = re.search(r"(\d+)", msg)
                wait = int(m.group(1)) if m else 300
                self.next_faucet = now() + wait + 1
                log.info("Faucet cooldown %ss", wait)
                return
            if "captcha" in msg.lower() or "token" in msg.lower():
                self.rotator.flip_sign()
            log.error("Faucet claim gagal: %s", exc)
            self.next_faucet = now() + 30
            return

        reward = as_float(res.get("reward_crypto"))
        cur = str(res.get("currency") or self.client.user.get("preferred_currency") or "?")
        roll = res.get("roll_number")
        payout = res.get("payout_status", "?")
        self.stats.faucet_ok += 1
        self.stats.add("faucet", cur, reward)
        self.next_faucet = now() + as_float(res.get("cooldown_seconds"),
                                            as_float(info.get("cooldown_minutes"), 5) * 60) + 2
        log.info("FAUCET ✔ roll=%s  +%s %s  payout=%s",
                 roll, f"{reward:.8f}", cur, payout)

    def task_ptc(self) -> None:
        if self.args.no_ptc:
            return
        # Tanpa API key, iklan tidak bisa di-complete (butuh Turnstile) →
        # jangan buang kuota memuat daftar campaign (23 KB tiap siklus).
        if not self.solver:
            return
        if now() < self.next_ptc:
            return

        try:
            camps = self.client.ptc_campaigns()
        except ApiError as exc:
            log.error("ptc list: %s", exc)
            self.next_ptc = now() + 60
            return

        viewable = [c for c in camps if c.get("can_view")]
        if not viewable:
            soonest = min((as_float(c.get("next_view_at_ts"), 0) for c in camps),
                          default=0)
            wait = 60
            if soonest > now():
                wait = int(soonest - now()) + 2
            self.next_ptc = now() + min(wait, 600)
            log.debug("PTC: tidak ada iklan available, cek lagi dalam %ss", wait)
            return

        viewable.sort(key=lambda c: as_float(c.get("user_reward_crypto"), 0), reverse=True)

        # --- filter ROI: jangan beli token untuk iklan yang rugi -------
        floor = self.budget.min_reward_usd(
            as_float(getattr(self.args, "min_ptc_reward", 0.0)))
        if floor > 0 and self.prices:
            layak, terlalu_murah = [], 0
            for c in viewable:
                cur = str(c.get("currency") or "").upper()
                usd = as_float(c.get("user_reward_crypto")) * self.prices.get(cur, 0.0)
                if usd >= floor:
                    layak.append(c)
                else:
                    terlalu_murah += 1
            if terlalu_murah:
                log.info("PTC: %d iklan di bawah ambang ROI $%.6f/token dilewati",
                         terlalu_murah, floor)
            viewable = layak

        max_ptc = int(getattr(self.args, "max_ptc", 0) or 0)
        if max_ptc > 0:
            viewable = viewable[:max_ptc]

        if not viewable:
            self.next_ptc = now() + 300
            log.info("PTC: tidak ada iklan lolos filter — cek lagi nanti")
            return

        if not self.budget.can(1.0, what="PTC"):
            self.next_ptc = now() + 600
            return

        log.info("PTC: %d iklan bisa dilihat", len(viewable))

        for camp in viewable:
            cid = camp.get("id")
            title = str(camp.get("title") or "")[:40]
            reward = as_float(camp.get("user_reward_crypto"))
            cur = str(camp.get("currency") or self.client.user.get("preferred_currency") or "?")
            slug = camp.get("slug")
            try:
                if slug and camp.get("ad_type") == "iframe":
                    try:
                        self.client.ptc_campaign_page(str(slug))
                    except ApiError:
                        pass

                start = self.client.ptc_start(cid)
                sess = start.get("session_token")
                dur = int(as_float(start.get("duration_seconds"),
                                   as_float(camp.get("duration_seconds"), 15)))
                if not sess:
                    raise ApiError(0, {"error": "session_token kosong"}, "/ptc/view/start")

                log.info("PTC ⧖ %ss  «%s»  (+%s %s)", dur, title, reward, cur)
                # timer berjalan; site juga butuh turnstile sesaat sebelum complete
                sleep(dur + rnd(1.0, 3.0))

                ptc_url = f"{SITE}/ptc"
                tok, reused = self._need_turnstile("ptc", ptc_url)
                if not tok:
                    self.stats.ptc_fail += 1
                    continue

                try:
                    res = self.client.ptc_complete(str(sess), tok)
                except ApiError as exc:
                    # Token hasil reuse kemungkinan sudah terpakai sekali.
                    # Percobaan ulang ini GRATIS (tak membeli token baru):
                    # kalau ternyata token bisa dipakai ulang, 1 token untuk
                    # banyak iklan; kalau tidak, baru beli token segar.
                    if not (reused and self._is_captcha_error(exc)):
                        raise
                    log.info("Token bekas ditolak (single-use) → beli token baru…")
                    self.budget.reused_fail += 1
                    self.budget.invalidate("ptc", ptc_url)
                    tok, _ = self._need_turnstile("ptc", ptc_url, allow_reuse=False)
                    if not tok:
                        raise
                    res = self.client.ptc_complete(str(sess), tok)
                    reused = False   # yang dipakai sekarang token segar
                if reused:
                    self.budget.reused_ok += 1
                    log.info("REUSE token Turnstile diterima server — hemat 1 token ✔")

                amt = as_float(res.get("amount_crypto"))
                c2 = str(res.get("currency") or cur)
                self.stats.ptc_ok += 1
                self.stats.add("ptc", c2, amt)
                log.info("PTC ✔ +%s %s («%s»)", f"{amt:.8f}", c2, title)
            except ApiError as exc:
                self.stats.ptc_fail += 1
                log.warning("PTC gagal («%s»): %s", title, exc)
            except AuthError:
                raise
            except Exception as exc:  # noqa: BLE001
                self.stats.ptc_fail += 1
                log.warning("PTC error («%s»): %s", title, exc)
            sleep(rnd(1.5, 4.0))

        self.next_ptc = now() + 45

    def task_daily(self) -> None:
        if self.args.no_daily:
            return
        if now() < self.next_daily:
            return

        try:
            st = self.client.daily_status()
        except ApiError as exc:
            log.debug("daily status: %s", exc)
            self.next_daily = now() + 300
            return

        if st.get("already_claimed"):
            self.next_daily = now() + 1800
            log.debug("Daily bonus sudah diklaim hari ini.")
            return

        threshold = as_float(st.get("threshold"))
        earned = as_float(st.get("earned_today"))
        if threshold > 0 and earned < threshold:
            wait = 300
            log.info("Daily bonus: %.8f / %.8f (kurang %.8f) — cek lagi nanti",
                     earned, threshold, threshold - earned)
            self.next_daily = now() + wait
            return

        if not self.budget.can(1.0, what="daily bonus"):
            self.next_daily = now() + 600
            return

        tok, _ = self._need_turnstile("daily_bonus", f"{SITE}/daily")
        if not tok:
            self.stats.daily_fail += 1
            self.next_daily = now() + 600
            return
        try:
            res = self.client.daily_claim(tok)
        except ApiError as exc:
            self.stats.daily_fail += 1
            log.warning("Daily gagal: %s", exc)
            self.next_daily = now() + 600
            return

        bonus_usd = as_float(res.get("bonus_usd"))
        cur = str(res.get("currency") or self.client.user.get("preferred_currency") or "USD")
        # situs menampilkan bonus sebagai bonus_usd / harga_koin(preferred)
        price = self.prices.get(cur.upper(), 0.0)
        amount = (bonus_usd / price) if price > 0 else bonus_usd
        self.stats.daily_ok += 1
        self.stats.add("daily", cur, amount)
        self.next_daily = now() + 3600
        log.info("DAILY BONUS ✔ +%.8f %s (≈%.6f USD)", amount, cur, bonus_usd)

    def task_shortlinks(self) -> None:
        if self.args.no_shortlinks or not self.solver:
            return
        if now() < self.next_shortlink:
            return

        # Shortlink =1 token per solve, hadiahnya jauh lebih besar daripada
        # PTC → kerjakan SEBELUM PTC, tapi tetap disaring ROI.
        floor = self.budget.min_reward_usd(
            as_float(getattr(self.args, "min_shortlink_reward", 0.0)))
        total_done = 0
        skipped_roi = 0
        for source in ("bitcotasks", "octoclix"):
            if source in self.shortlink_dead:
                continue
            try:
                items = self.client.shortlinks(source)
            except ApiError as exc:
                log.debug("shortlinks %s: %s", source, exc)
                continue

            for it in items:
                # API memakai remaining/daily_limit (bukan available/limit)
                avail = as_float(it.get("available", it.get("remaining")), 0)
                if avail <= 0:
                    continue
                url = it.get("url") or it.get("link")
                if not url:
                    continue
                title = str(it.get("title") or it.get("shortener_name") or source)[:40]
                reward = as_float(it.get("reward"))
                cur = str(it.get("currency") or self.client.user.get("preferred_currency") or "?")
                reward_usd = as_float(it.get("reward_usd"), 0.0)
                if reward_usd <= 0 and self.prices:
                    reward_usd = reward * self.prices.get(cur.upper(), 0.0)

                if floor > 0 and reward_usd < floor:
                    skipped_roi += 1
                    continue
                if not self.budget.can(1.0, what=f"shortlink «{title}»"):
                    self.next_shortlink = now() + 900
                    return

                try:
                    result = self.solver.shortlink(str(url))
                except Exception as exc:  # noqa: BLE001
                    # provider tetap menagih percobaan → selalu cegah buang token
                    self.budget.charge(1.0)
                    self.stats.shortlink_fail += 1
                    log.warning("SHORTLINK gagal «%s»: %s", title, exc)
                    if "UNSOLVABLE" in str(exc).upper():
                        self.shortlink_dead.add(source)
                        self._save_state()
                        log.warning("Provider tak bisa solve shortlink %s → "
                                    "sumber dimatikan otomatis.", source)
                        break
                else:
                    self.budget.charge(1.0)
                    if re.match(r"^https?://", result):
                        try:
                            self.client.s.get(result, headers={"Referer": SITE + "/"},
                                              timeout=30, allow_redirects=True)
                        except requests.RequestException:
                            pass
                    self.stats.shortlink_ok += 1
                    self.stats.add("shortlink", cur, reward)
                    total_done += 1
                    log.info("SHORTLINK ✔ «%s» → %s… (+%s %s ≈$%.6f)",
                             title, str(result)[:50], reward, cur, reward_usd)
                sleep(rnd(2.0, 5.0))
                if total_done >= self.args.shortlink_max:
                    break
            if total_done >= self.args.shortlink_max:
                break

        if skipped_roi:
            log.info("Shortlink: %d dilewati (di bawah ambang ROI $%.6f/token)",
                     skipped_roi, floor)
        if self.shortlink_dead >= {"bitcotasks", "octoclix"}:
            self.next_shortlink = now() + 86400
            log.warning("Semua sumber shortlink tak bisa di-solve provider → "
                        "shortlink dimatikan 24 jam (hemat token).")
        else:
            self.next_shortlink = now() + 180

    def task_youtube(self) -> None:
        """Nonton video YouTube otomatis (widget aviso.bz) — GRATIS, tanpa token."""
        if getattr(self.args, "no_youtube", False):
            return
        if now() < self.next_youtube:
            return

        try:
            if self.yt is None:
                ident = self.client.youtube_identity()
                if not ident.get("configured") or not ident.get("user_hash"):
                    log.info("YouTube: tidak dikonfigurasi di akun ini — dilewati.")
                    self.next_youtube = now() + 86400
                    return
                self.yt = AvisoYouTube(ident, proxy=self.args.proxy,
                                       debug=getattr(self.args, "debug", False))
                self.yt.identify()
                log.info("YouTube: terhubung (hash %s…, points/USD %s)",
                         self.yt.user_hash[:12], self.yt.points_per_usd)
            if self.yt is None:
                return

            kind = str(getattr(self.args, "youtube_type", "ads") or "ads")
            tasks = self.yt.available(kind)
            if not tasks:
                log.debug("YouTube: tidak ada tugas %s tersedia", kind)
                self.next_youtube = now() + 300
                return

            cap = int(getattr(self.args, "youtube_max", 0) or 0)
            # urut dari hadiah terbesar dulu, baru dipotong
            tasks.sort(key=lambda t: as_float(t.get("amount")), reverse=True)
            if cap > 0:
                tasks = tasks[:cap]

            for t in tasks:
                tid = t.get("id")
                tkind = str(t.get("type") or kind)
                if tkind == "all":
                    tkind = "ads"
                amount = as_float(t.get("amount"))
                dur = max(1, int(as_float(t.get("duration"), 1)))
                title = str(t.get("title") or "video")[:40]
                try:
                    st = self.yt.start(tid, tkind)
                    aid = st.get("attemptId") or (st.get("attempt") or {}).get("attemptId")
                    if not aid:
                        raise ApiError(0, {"error": "attemptId kosong"}, "/youtube/tasks/start")
                    real_dur = max(1, int(as_float(st.get("duration"), dur)))
                    amount = as_float(st.get("amount"), amount)

                    # Halaman partner (blogspot) TIDAK wajib — sudah diuji:
                    # earned tetap sama (59.4 vs 57.9 pts) tanpa membukanya,
                    # tapi menghemat ~8 KB/video. Nyalakan dengan
                    # --yt-visit-partner kalau ingin meniru browser penuh.
                    url = st.get("url")
                    if url and getattr(self.args, "yt_visit_partner", False):
                        try:
                            self.client.s.get(str(url), timeout=15,
                                              allow_redirects=True)
                        except requests.RequestException:
                            pass

                    self.yt.timer_status(aid, "start")
                    sleep(real_dur + rnd(0.5, 2.0))
                    self.yt.timer_status(aid, "complete", real_dur)
                    res = self.yt.complete(aid)
                    earned = as_float(res.get("earned"), amount)

                    self.stats.yt_ok += 1
                    self.stats.yt_points += earned
                    usd = self.yt.to_usd(earned)
                    log.info("YOUTUBE ✔ +%.1f pts (≈%.6f USD) dur=%ss «%s»",
                             earned, usd, real_dur, title)
                except AuthError:
                    raise
                except ApiError as exc:
                    self.stats.yt_fail += 1
                    log.warning("YouTube gagal («%s»): %s", title, exc)
                    msg = str(exc).lower()
                    if "limit" in msg or "banned" in msg:
                        self.next_youtube = now() + 3600
                        return
                except Exception as exc:  # noqa: BLE001
                    self.stats.yt_fail += 1
                    log.warning("YouTube error («%s»): %s", title, exc)
                sleep(rnd(1.0, 3.0))

            self.next_youtube = now() + max(60, int(getattr(
                self.args, "youtube_interval", 600) or 600))
        except AuthError:
            raise
        except ApiError as exc:
            log.debug("YouTube: %s", exc)
            self.next_youtube = now() + 300
        except Exception as exc:  # noqa: BLE001
            log.warning("YouTube: %s", exc)
            self.next_youtube = now() + 300

    def task_report(self, force: bool = False) -> None:
        if not force and now() - self._last_report < 900:
            return
        self._last_report = now()
        try:
            self.client.me()
        except ApiError as exc:
            log.debug("me: %s", exc)
        if not self.prices:
            self.prices = self.client.crypto_prices()
        cur = str(self.client.user.get("preferred_currency") or "?")
        bal = self.client.user.get("current_balance")
        log.info("STATUS user=%s currency=%s balance=%s | %s",
                 self.client.user.get("email") or self.client.email, cur, bal,
                 self.stats.summary(self.prices, cur).replace("\n", " "))

    # --- siklus -----------------------------------------------------------
    def task_captcha_watch(self) -> None:
        """Auto-update: pantau perubahan captcha di situs.

        Dua hal dipantau sekaligus:
          1. Gambar /captcha-lime.jpg  → kalau berganti, file solver langsung
             ditimpa + konvensi rotasi di-reset (tanpa restart bot).
          2. Sitekey Turnstile         → kalau situs mengganti jenis/param
             captcha, bot mencatatnya di log.

        Interval: --captcha-revalidate (detik, default 6 jam).
        """
        if now() < self.next_captcha_check:
            return
        interval = int(getattr(self.args, "captcha_revalidate", 86400) or 0)
        if interval <= 0:          # 0 = fitur dimatikan user
            return
        interval = max(300, interval)
        self.next_captcha_check = now() + interval

        st = self.rotator.revalidate()
        if st == "error":
            # jaringan/situs sedang bermasalah → coba lagi 5 menit lagi
            self.next_captcha_check = now() + 300

        # ikut pantau sitekey Turnstile (response /config cuma ~314 byte)
        try:
            old = self.client.sitekey
            cfg = self.client.config()
            sk = cfg.get("turnstile_site_key")
            if sk and sk != old:
                log.warning("Sitekey Turnstile BERUBAH di situs: %s → %s "
                            "(config bot diperbarui otomatis).", old, sk)
        except requests.RequestException:
            pass

    def cycle(self) -> None:
        # Urutan = urutan ROI token: faucet (gratis) dulu, lalu tugas
        # berbayar dari yang paling menguntungkan → yang paling rugi.
        # YouTube gratis & tanpa token → dikerjakan lebih awal.
        self.task_captcha_watch()   # murah: 304 = 0 byte, cek tiap 6 jam
        self.task_faucet()
        self.task_youtube()
        self.task_daily()
        self.task_shortlinks()
        self.task_ptc()
        self.task_report()

    def run(self) -> bool:
        self.client.config()
        try:
            self.client.ensure_auth()
        except (ApiError, AuthError) as exc:
            msg = exc.error or str(exc)
            if "banned" in msg.lower():
                log.error("Login DITOLAK: akun %s berstatus BANNED di limefaucet.com "
                          "(\"%s\").", self.client.email, msg)
            elif "not registered on faucetpay" in msg.lower():
                log.error("Login DITOLAK: %s belum punya akun FaucetPay. "
                          "Buat dulu di faucetpay.io lalu coba lagi.", self.client.email)
            else:
                log.error("Login gagal: %s", exc)
            return False

        bal = self.budget.balance(refresh=True) if self.solver else None
        if bal is not None:
            log.info("Saldo solver: %s token | cadangan %.0f | anggaran %s | "
                     "reuse token: %s",
                     bal, self.budget.reserve,
                     f"{self.budget.budget:.0f}" if self.budget.budget else "tanpa batas",
                     "ON" if self.budget.reuse else "OFF")
        elif not self.solver:
            log.warning("Tanpa API key → Turnstile (PTC/Daily) & shortlink dilewati.")

        if not self.prices:
            self.prices = self.client.crypto_prices()

        self.task_report(force=True)

        if self.args.once:
            self.cycle()
            print(self.stats.summary(self.prices,
                                     str(self.client.user.get("preferred_currency") or "?")))
            log.info("TOKEN: %s", self.budget.report())
            return True

        log.info("Loop otomatis dimulai (tick %ss). Ctrl+C untuk berhenti.",
                 self.args.tick)
        cycles = 0
        login_fails = 0
        try:
            while True:
                try:
                    self.cycle()
                except AuthError:
                    log.warning("Sesi hilang → login ulang…")
                    sleep(3)
                    try:
                        self.client.login()
                        login_fails = 0
                    except (ApiError, AuthError) as exc:
                        login_fails += 1
                        log.error("Login ulang gagal (%d/3): %s", login_fails, exc)
                        if login_fails >= 3:
                            log.error("Login gagal 3 kali berturut-turut → berhenti.")
                            break
                        sleep(30)
                except ApiError as exc:
                    log.error("API error: %s", exc)
                    sleep(10)
                except Exception as exc:  # noqa: BLE001
                    log.exception("Error tak terduga: %s", exc)
                    sleep(15)

                cycles += 1
                if cycles % 40 == 0:
                    self.task_report(force=True)
                sleep(self.args.tick)
        except KeyboardInterrupt:
            log.info("Dihentikan oleh user.")
        finally:
            print(self.stats.summary(self.prices,
                                     str(self.client.user.get("preferred_currency") or "?")))
            log.info("TOKEN: %s", self.budget.report())
        return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="limefaucet_auto.py",
        description="Bot auto-all limefaucet.com (requests only, tanpa browser).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    p.add_argument("--email", default=os.environ.get("LIME_EMAIL", ""),
                   help="Email FaucetPay yang terdaftar di limefaucet.com")
    p.add_argument("--captcha-key", default=os.environ.get("CAPTCHA_APIKEY", ""),
                   help="API key solver (api.waryono.my.id) untuk Turnstile/lime")
    p.add_argument("--proxy", default=os.environ.get("LIME_PROXY", ""),
                   help="Proxy opsional, format http://user:pass@host:port")

    p.add_argument("--once", action="store_true", help="Jalankan satu siklus lalu keluar")
    p.add_argument("--tick", type=int, default=15, help="Jeda antar siklus (detik)")
    p.add_argument("--debug", action="store_true", help="Log mentah response API")
    p.add_argument("--log-file", default="", help="Simpan log ke file")
    p.add_argument("--cookie-file", default=".lime_session.json",
                   help="File persistensi cookie sesi")
    p.add_argument("--bg-image", default="",
                   help="Path lokal captcha-lime.jpg (default: diunduh otomatis)")
    p.add_argument("--captcha-revalidate", type=int,
                   default=int(os.environ.get("CAPTCHA_REVALIDATE", 86400) or 86400),
                   help="Detik antar cek perubahan gambar captcha di situs "
                        "(default 86400 = 1x/24 jam ≈ 141 KB/hari). Kalau "
                        "gambar berganti, file solver ditimpa otomatis. "
                        "Pakai 0 untuk mematikan fitur ini.")

    p.add_argument("--no-faucet", action="store_true", help="Nonaktifkan claim faucet")
    p.add_argument("--no-ptc", action="store_true", help="Nonaktifkan PTC")
    p.add_argument("--no-daily", action="store_true", help="Nonaktifkan daily bonus")
    p.add_argument("--no-shortlinks", action="store_true", help="Nonaktifkan shortlink")
    p.add_argument("--no-youtube", action="store_true",
                   help="Nonaktifkan auto nonton YouTube")
    p.add_argument("--youtube-max", type=int,
                   default=int(os.environ.get("YOUTUBE_MAX", 10) or 10),
                   help="Maksimal video YouTube per siklus (default 10)")
    p.add_argument("--youtube-type",
                   default=os.environ.get("YOUTUBE_TYPE", "ads") or "ads",
                   choices=["ads", "sub", "like", "all"],
                   help="Jenis tugas YouTube (ads=nonton video, gratis)")
    p.add_argument("--youtube-interval", type=int,
                   default=int(os.environ.get("YOUTUBE_INTERVAL", 600) or 600),
                   help="Jeda antar batch YouTube (detik). Lebih besar = "
                        "lebih hemat kuota (daftar tugas 22 KB per fetch)")
    p.add_argument("--yt-visit-partner", action="store_true",
                   help="Buka halaman partner blogspot tiap video "
                        "(TIDAK wajib — hadiah sama, boros ~8 KB/video)")
    p.add_argument("--shortlink-max", type=int, default=10,
                   help="Maksimal shortlink per siklus")

    g = p.add_argument_group("hemat token (apikey solver)")
    g.add_argument("--token-budget", type=float,
                   default=float(os.environ.get("TOKEN_BUDGET", 0) or 0),
                   help="Maksimal token yang boleh dipakai per proses (0=tanpa batas)")
    g.add_argument("--token-reserve", type=float,
                   default=float(os.environ.get("TOKEN_RESERVE", 100) or 100),
                   help="Tak pernah pakai token sampai saldo tinggal segini")
    g.add_argument("--token-price", type=float,
                   default=float(os.environ.get("TOKEN_PRICE", 0) or 0),
                   help="Harga token USD per 1000 → aktifkan filter ROI + laporan biaya")
    g.add_argument("--min-ptc-reward", type=float, default=0.0,
                   help="Reward PTC minimum USD (0=otomatis biaya 1 token bila --token-price diisi)")
    g.add_argument("--min-shortlink-reward", type=float, default=0.0,
                   help="Reward shortlink minimum USD (0=otomatis biaya 1 token)")
    g.add_argument("--max-ptc", type=int, default=0,
                   help="Maksimal iklan PTC per siklus (0=tanpa batas)")
    g.add_argument("--no-token-reuse", action="store_true",
                   help="Matikan percobaan pakai-ulang token Turnstile")
    p.add_argument("--selftest", action="store_true",
                   help="Test solver captcha rotasi (tanpa login)")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    load_dotenv()
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.env"))
    args = build_parser().parse_args(argv)

    global log
    log = setup_logging(debug=args.debug, log_file=args.log_file or None)

    if args.selftest:
        ok = RotationSolver.selftest()
        log.info("Selftest %s", "LULUS ✔" if ok else "GAGAL ✖")
        return 0 if ok else 1

    if not args.email:
        log.error("Email FaucetPay wajib: --email atau LIME_EMAIL di config.env")
        return 2

    bot = Bot(args)
    return 0 if bot.run() else 3


if __name__ == "__main__":
    raise SystemExit(main())
