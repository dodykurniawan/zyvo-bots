#!/usr/bin/env python3
"""clipcoin.pro AUTO — pure HTTP (Nuxt form-urlencoded API).

Premium auto-all: nonton video (tasks) + daily bonus + simpan wallet
USDT BEP20 + auto-WD saat balance >= min.

Login: method=mailAuth + Turnstile captchaResponse (solvercf).
Session: cookie `hash` dipersist ke state.json (1 tahun).

Usage:
  python3 clipcoin_auto.py --status
  python3 clipcoin_auto.py --login          # paksa re-login
  python3 clipcoin_auto.py --once           # 1 siklus penuh
  python3 clipcoin_auto.py                  # loop terus
"""
from __future__ import annotations

import argparse
import json
import pathlib
import random
import sys
import time
import urllib.parse
from typing import Any, Optional

import requests

BASE = "https://clipcoin.pro"
API = BASE + "/api"
SITEKEY = "0x4AAAAAAF2fs7K06aFo4dK_"
PAGEURL = BASE + "/signin"
# WAJIB sama persis dengan UA saat login — server set checkUA=1
# (UA beda → checkSecurity). Kalau re-login, pakai UA ini juga.
UA = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36"
WALLET_BEP20 = "0xfd8e65eae62f33652400a2f7a5ee3a6e87457f7a"
SERVICE = "usdt_bep20"
MIN_WD = 0.3

HERE = pathlib.Path(__file__).resolve().parent
STATE = HERE / "state.json"
CFG = HERE / "config.json"
LOG = HERE / "bot.log"


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_cfg() -> dict:
    if CFG.exists():
        return json.loads(CFG.read_text())
    return {}


def save_state(s: dict) -> None:
    STATE.write_text(json.dumps(s, indent=2))


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {}


def load_email() -> str:
    cfg = load_cfg()
    email = cfg.get("email") or __import__("os").environ.get("CLIPCOIN_EMAIL", "")
    if not email:
        raise SystemExit("config.json butuh field email (atau env CLIPCOIN_EMAIL)")
    return email


def load_password() -> str:
    cfg = load_cfg()
    pw = cfg.get("password") or __import__("os").environ.get("CLIPCOIN_PASSWORD", "")
    if not pw:
        raise SystemExit("config.json butuh field password (atau env CLIPCOIN_PASSWORD)")
    return pw


def solve_turnstile() -> str:
    """Turnstile: rantai xsolve → peak → solvercf via captcha_ai.py.

    Key: env SOLVERCF_KEY/XSOLVE_KEY/PEAK_KEY dulu → lm_config.json.
    captcha_ai.py hilang → jalur lama (solvercf saja) tetap jalan.
    """
    ca = _ca()
    if ca is None:
        return _solve_turnstile_solvercf_only()
    cfg = ca.load_cfg()
    errs, have_key = [], False
    for key_name, name, fn in ca.TURNSTILE_CHAIN:
        key = cfg.get(key_name) or ""
        if not key:
            errs.append(f"{name}: key kosong")
            continue
        have_key = True
        log(f"turnstile: coba {name}…")
        try:
            return fn(key, SITEKEY, PAGEURL, None, None, UA)["token"]
        except Exception as e:
            errs.append(f"{name}: {e}")
            log(f"turnstile {name} gagal: {e}")
    if not have_key:  # tak ada key sama sekali → jalur lama
        return _solve_turnstile_solvercf_only()
    raise RuntimeError("turnstile semua solver gagal: " + " | ".join(errs))


_CA = None  # modul captcha_ai (rantai solver + AI vision) — dimuat sekali


def _ca():
    """Load captcha_ai.py dari folder yang sama (ikut checkout/pull)."""
    global _CA
    if _CA is None:
        p = HERE / "captcha_ai.py"
        if not p.exists():
            return None
        import importlib.util
        spec = importlib.util.spec_from_file_location("captcha_ai", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _CA = mod
    return _CA


def _solve_turnstile_solvercf_only() -> str:
    """Jalur LAMA (solvercf saja) — fallback kalau captcha_ai.py tidak ada."""
    lm = pathlib.Path("/storage/emulated/0/Download/ZYVO/sites/lightningminer/lm_config.json")
    key = json.loads(lm.read_text()).get("solvercf_key") if lm.exists() else ""
    key = key or __import__("os").environ.get("SOLVERCF_KEY", "").strip()
    if not key:
        raise RuntimeError("solvercf_key tidak ada (env SOLVERCF_KEY / lm_config.json)")
    base = "https://solvercf.com/token/extension"
    r = requests.post(f"{base}/createTask", json={
        "clientKey": key,
        "task": {"type": "TurnstileTask", "websiteUrl": PAGEURL,
                 "websiteKey": SITEKEY, "userAgent": UA},
    }, timeout=30).json()
    tid = r.get("taskId")
    if not tid:
        raise RuntimeError(f"solvercf createTask: {r}")
    for _ in range(30):
        time.sleep(3)
        p = requests.post(f"{base}/getTaskResult",
                          json={"clientKey": key, "taskId": tid}, timeout=30).json()
        if p.get("status") == "ready":
            tok = (p.get("solution") or {}).get("token") or ""
            if tok:
                return tok
            raise RuntimeError(f"solvercf ready tanpa token: {p}")
        if p.get("status") == "failed":
            raise RuntimeError(f"solvercf failed: {p.get('errorDescription')}")
        if p.get("errorId") not in (0, None, "0"):
            raise RuntimeError(f"solvercf error: {p}")
    raise RuntimeError("solvercf timeout")


# ---- image captcha (3 klik ikon) -------------------------------------------
# queue = PNG pola 3 ikon target; image = JPEG scene (240x200) berisi ~4 ikon.
# JS: CLICKS_REQUIRED=3, offset genap, body form `coor[i][x]` / `coor[i][y]`.
def _fg_mask_scene(arr):
    """→ (mask tight, solid utk CC). Ambang lebih tinggi + close 2 — bunyi ghost."""
    import numpy as np
    a = arr.astype(np.int16)
    lum = a.mean(axis=2)
    mx, mn = a.max(axis=2), a.min(axis=2)
    mask = (lum > 78) | ((mx - mn) > 50)
    m = mask.copy()
    for _ in range(2):
        m2 = m.copy()
        m2[1:, :] |= m[:-1, :]
        m2[:-1, :] |= m[1:, :]
        m2[:, 1:] |= m[:, :-1]
        m2[:, :-1] |= m[:, 1:]
        m = m2
    return mask, m


def _components(mask, solid, min_px=45):
    import numpy as np
    from collections import deque
    H, W = solid.shape
    lab = np.zeros((H, W), np.int32)
    comps = []
    cid = 0
    for y in range(H):
        for x in range(W):
            if solid[y, x] and lab[y, x] == 0:
                cid += 1
                qq = deque([(y, x)])
                lab[y, x] = cid
                pix = []
                while qq:
                    cy, cx = qq.popleft()
                    pix.append((cy, cx))
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = cy + dy, cx + dx
                            if 0 <= ny < H and 0 <= nx < W and solid[ny, nx] and lab[ny, nx] == 0:
                                lab[ny, nx] = cid
                                qq.append((ny, nx))
                if len(pix) < min_px:
                    continue
                ys = [p[0] for p in pix]
                xs = [p[1] for p in pix]
                x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
                if (x1 - x0 + 1) < 10 or (y1 - y0 + 1) < 10:
                    continue
                cc = np.zeros((H, W), bool)
                for yy, xx in pix:
                    cc[yy, xx] = True
                crop = mask[y0:y1 + 1, x0:x1 + 1] & cc[y0:y1 + 1, x0:x1 + 1]
                if int(crop.sum()) < 20:
                    continue
                comps.append({
                    "crop": crop,
                    "center": ((x0 + x1) // 2, (y0 + y1) // 2),
                    "n": int(crop.sum()),
                })
    return comps


def _norm_shape(b, S=40):
    import numpy as np
    from PIL import Image
    ys, xs = np.where(b)
    if len(ys) == 0:
        return np.zeros((S, S), bool)
    sub = b[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = sub.shape
    sc = min(S / max(h, 1), S / max(w, 1))
    nh, nw = max(1, int(round(h * sc))), max(1, int(round(w * sc)))
    img = np.array(Image.fromarray((sub * 255).astype(np.uint8)).resize((nw, nh), Image.BILINEAR)) > 100
    c = np.zeros((S, S), bool)
    oy, ox = (S - nh) // 2, (S - nw) // 2
    c[oy:oy + nh, ox:ox + nw] = img
    return c


def _dilate(b, d=2):
    m = b.copy()
    for _ in range(d):
        m2 = m.copy()
        m2[1:, :] |= m[:-1, :]
        m2[:-1, :] |= m[1:, :]
        m2[:, 1:] |= m[:, :-1]
        m2[:, :-1] |= m[:, 1:]
        m = m2
    return m


def _diou(a, b, d=2):
    na, nb = _dilate(_norm_shape(a), d), _dilate(_norm_shape(b), d)
    u = int((na | nb).sum())
    return int((na & nb).sum()) / u if u else 0.0


def solve_image_captcha(image_b64: str, queue_b64: str):
    """→ [ {x,y}, {x,y}, {x,y} ] genap, urut sesuai queue; atau None."""
    import base64, io
    import numpy as np
    from PIL import Image
    try:
        im = np.array(Image.open(io.BytesIO(base64.b64decode(image_b64))).convert("RGB"))
        q = np.array(Image.open(io.BytesIO(base64.b64decode(queue_b64))).convert("RGBA"))
    except Exception as e:
        log(f"captcha decode gagal: {e}")
        return None
    mask, solid = _fg_mask_scene(im)
    scene = _components(mask, solid)
    qmask = q[..., 3] > 60
    cols = qmask.any(axis=0)
    segs, start = [], None
    for x, v in enumerate(cols):
        if v and start is None:
            start = x
        if not v and start is not None:
            if x - start > 3:
                segs.append((start, x))
            start = None
    if start is not None:
        segs.append((start, len(cols)))
    merged = []
    for s in segs:
        if merged and s[0] - merged[-1][1] <= 8:
            merged[-1] = (merged[-1][0], s[1])
        else:
            merged.append(s)
    if len(merged) != 3:
        xs = np.where(cols)[0]
        if len(xs) == 0:
            return None
        x0, x1 = int(xs.min()), int(xs.max()) + 1
        w = (x1 - x0) / 3.0
        merged = [(int(x0 + i * w), int(x0 + (i + 1) * w)) for i in range(3)]
    tpls = []
    for x0, x1 in merged:
        sub = qmask[:, x0:x1]
        ys = np.where(sub.any(axis=1))[0]
        if len(ys) == 0:
            return None
        tpls.append(sub[ys.min():ys.max() + 1, :])
    if len(tpls) != 3 or len(scene) < 3:
        log(f"captcha solve: tpl={len(tpls)} scene={len(scene)}")
        return None
    # skor dilated-IoU 3×N → brute-force pasangan terbaik (maks sum, tie-break min)
    import itertools
    N = len(scene)
    S = [[_diou(t, scene[j]["crop"]) for j in range(N)] for t in tpls]
    best = None
    for combo in itertools.permutations(range(N), 3):
        scs = [S[i][combo[i]] for i in range(3)]
        key = (sum(scs), min(scs))
        if best is None or key > best[0]:
            best = (key, combo, scs)
    _, combo, scs = best
    clicks = []
    for i, j in enumerate(combo):
        cx, cy = scene[j]["center"]
        x = cx - 1 if cx % 2 else cx
        y = cy - 1 if cy % 2 else cy
        clicks.append({"x": int(x), "y": int(y)})
        log(f"  captcha ikon q{i}→s{j} score={scs[i]:.2f} @({x},{y})")
    return clicks if len(clicks) == 3 else None


def _coor_body(clicks) -> str:
    """axios form: coor[0][x]=&coor[0][y]=…"""
    parts = []
    for i, c in enumerate(clicks):
        parts.append(f"coor[{i}][x]={int(c['x'])}&coor[{i}][y]={int(c['y'])}")
    return "&".join(parts)


def ai_match_captcha(image_b64: str, queue_b64: str):
    """Fallback AI (Gemini) saat CV lokal gagal → 3 klik genap atau None."""
    ca = _ca()
    if ca is None:
        return None
    import base64
    scene_p = HERE / "_ai_scene.jpg"
    queue_p = HERE / "_ai_queue.png"
    try:
        scene_p.write_bytes(base64.b64decode(image_b64))
        queue_p.write_bytes(base64.b64decode(queue_b64))
        clicks = ca.match_icons(scene_p, queue_p, quiet=True)
        log(f"  AI match: {[(c['x'], c['y']) for c in clicks]}")
        return [{"x": c["x"], "y": c["y"]} for c in clicks]
    except Exception as e:
        log(f"  AI match gagal: {e}")
        return None
    finally:
        for p in (scene_p, queue_p):
            try:
                p.unlink()
            except OSError:
                pass


class Clip:
    def __init__(self, state: dict):
        self.ck: dict = dict(state.get("cookie") or {})
        self._email = state.get("email") or ""

    def _headers(self) -> dict:
        h = {
            "User-Agent": UA,
            "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
            "Origin": BASE,
            "Referer": BASE + "/",
            "Accept": "application/json, text/plain, */*",
        }
        if self.ck.get("hash"):
            h["Cookie"] = f"hash={self.ck['hash']}; signed={self.ck.get('signed', '1')}"
        return h

    def post(self, path: str, data: Optional[dict] = None, timeout: int = 30) -> dict:
        r = requests.post(API + path, data=urllib.parse.urlencode(data or {}),
                          headers=self._headers(), timeout=timeout)
        # capture rotated cookies
        for c in r.cookies:
            self.ck[c.name] = c.value
        try:
            return r.json()
        except Exception:
            return {"status": "error", "message": "bad_json", "raw": r.text[:300]}

    def post_raw(self, path: str, body: str, timeout: int = 30) -> dict:
        """body form-urlencoded mentah (untuk coor[i][x] nested)."""
        h = self._headers()
        r = requests.post(API + path, data=body.encode(), headers=h, timeout=timeout)
        for c in r.cookies:
            self.ck[c.name] = c.value
        try:
            return r.json()
        except Exception:
            return {"status": "error", "message": "bad_json", "raw": r.text[:300]}

    def cookies_out(self) -> dict:
        return dict(self.ck)

    def login(self, email: str, password: str) -> None:
        log("login: solve turnstile…")
        tok = solve_turnstile()
        # login TANPA cookie lama (sesi baru)
        self.ck = {}
        r = requests.post(API + "/user/auth/",
                          data=urllib.parse.urlencode({
                              "method": "mailAuth", "email": email,
                              "password": password, "captchaResponse": tok,
                          }), headers=self._headers(), timeout=30)
        for c in r.cookies:
            self.ck[c.name] = c.value
        try:
            j = r.json()
        except Exception:
            j = {"status": "error", "raw": r.text[:300]}
        if j.get("status") != "ok":
            raise RuntimeError(f"login gagal: {j}")
        log(f"login OK cookie={list(self.ck)}")
        st = load_state()
        st["cookie"] = self.cookies_out()
        st["email"] = email
        save_state(st)

    def ensure_auth(self, force_login: bool = False) -> None:
        if force_login:
            self.login(load_email(), load_password())
            # login baru sering kena checkSecurity → 1x kode email manual
            j = self.post("/user/", {"method": "getCurrentUser"})
            if j.get("message") == "checkSecurity":
                raise RuntimeError(
                    "LOGIN BARU = checkSecurity (kode email). "
                    "Selesaikan sekali di browser, atau pakai cookie lama "
                    "di state.json.")
            return
        if not self.ck.get("hash"):
            self.login(load_email(), load_password())
            return
        j = self.post("/user/", {"method": "getCurrentUser"})
        msg = j.get("message") or ""
        if j.get("status") == "ok":
            return
        if msg == "checkSecurity":
            raise RuntimeError(
                "checkSecurity — sesi ini butuh konfirmasi kode email. "
                "Login via browser sekali, copy cookie `hash` ke state.json.")
        log(f"session invalid ({msg or j}) → relogin")
        self.login(load_email(), load_password())

    def dashboard(self) -> dict:
        j = self.post("/user/", {"method": "dashboard"})
        if j.get("status") != "ok":
            raise RuntimeError(f"dashboard: {j}")
        return j.get("data") or {}

    def ensure_wallet(self) -> None:
        j = self.post("/user/settings/save/", {
            "method": "payments",
            "usdt_bep20_wallet": WALLET_BEP20,
            "trx_wallet": "", "faucetpayusdt_wallet": "",
            "steam_wallet": "", "telegram_stars_wallet": "",
            "u_sbp_ru_wallet": "", "u_sbp_ru": "",
            "star_bkash_wallet": "", "star_nagad_wallet": "",
            "star_easypaisa_wallet": "", "star_jazzcash_wallet": "",
            "fkwallet_wallet": "", "code": "",
        })
        # balasan {"status":"ok","data":{"time":N}} = cooldown simpan ulang
        log(f"wallet save: {j}")

    def watch_one(self) -> dict:
        """1 video: getTask → start → tunggu duration → captcha check → reward."""
        t = self.post("/user/tasks/", {"method": "get"}).get("data") or {}
        tid = t.get("id")
        if not tid:
            return {"ok": False, "why": "no_task", "raw": t}
        # limit
        if int(t.get("limitHour") or 0) <= 0:
            return {"ok": False, "why": "limit_hour"}
        if int(t.get("limitDay") or 0) <= 0:
            return {"ok": False, "why": "limit_day"}
        if int(t.get("cnt") or 0) <= 0:
            return {"ok": False, "why": "cnt_empty"}

        st = None
        last = None
        for attempt in range(3):
            st = self.post("/user/tasks/start/", {"TaskId": tid, "fin": 0})
            if st.get("status") == "ok":
                break
            last = st
            # ErrorTryAgain = rate-limit start → backoff
            time.sleep(5 + attempt * 8)
        if not st or st.get("status") != "ok":
            return {"ok": False, "why": "start_fail", "raw": st or last}

        dur = int(t.get("duration") or 12)
        # human margin
        wait = dur + random.uniform(1.5, 3.5)
        log(f"  nonton task={tid} {dur}s → tunggu {wait:.1f}s")
        time.sleep(wait)

        ck = self.post("/user/captcha/check/", {})
        ck = self._captcha_round(ck)
        if ck is None:
            return {"ok": False, "why": "captcha", "raw": "solve_failed"}
        if ck.get("status") == "ok" and "reward" in (ck.get("data") or {}):
            rew = ck["data"].get("reward")
            coins = ck["data"].get("coins")
            log(f"  ✅ reward +{rew} USD +{coins} coins")
            return {"ok": True, "reward": rew, "coins": coins, "task": tid}
        return {"ok": False, "why": "captcha", "raw": ck}

    def _captcha_round(self, ck: dict, max_try: int = 3) -> Optional[dict]:
        """check {} → image? solve 3 klik → coor → sampai reward / gagal.

        Urutan solver: CV lokal dulu (gratis) → AI Gemini sebagai fallback;
        server tolak jawaban → putaran berikut AI duluan.
        """
        prefer_ai = False
        for attempt in range(max_try):
            data = ck.get("data") or {}
            if "reward" in data:
                return ck
            img = data.get("image")
            queue = data.get("queue")
            if not img or not queue:
                # bentuk tak dikenal
                return ck
            log(f"  image captcha (percobaan {attempt + 1}/{max_try})"
                f"{' [AI duluan]' if prefer_ai else ''}…")
            clicks = None
            if prefer_ai:
                clicks = ai_match_captcha(img, queue) \
                    or solve_image_captcha(img, queue)
            else:
                clicks = solve_image_captcha(img, queue) \
                    or ai_match_captcha(img, queue)
            if not clicks:
                # refreshTask=1 → gambar baru
                ck = self.post("/user/captcha/check/", {"refreshTask": 1})
                time.sleep(1.0 + random.random())
                continue
            ck = self.post_raw("/user/captcha/check/", _coor_body(clicks))
            msg = ck.get("message") or ""
            if ck.get("status") == "ok" and "reward" in (ck.get("data") or {}):
                return ck
            if msg in ("limitIsOver", "cannotPassTestTask", "taskBySkip", "verifTimeExpired"):
                log(f"  captcha reject: {msg}")
                return ck
            # salah klik / gambar baru → putaran berikut utamakan AI
            prefer_ai = True
            time.sleep(0.8 + random.random() * 0.7)
        return ck

    def daily_bonus(self) -> Optional[dict]:
        info = self.post("/user/tasks/dailyBonus/", {"method": "getInfo"}).get("data") or {}
        cnt = int(info.get("dailyBonusCnt") or 0)
        settings = info.get("settings") or []
        # ambil tier terbesar yang sudah tercapai viewCurDay dan belum diklaim
        views = int(info.get("viewCurDay") or 0)
        eligible = [s for s in settings if views >= int(s.get("count") or 0)]
        if not eligible:
            return None
        # getBonus klaim tier berikutnya yang belum — server yang tentukan
        j = self.post("/user/tasks/dailyBonus/", {"method": "getBonus"})
        log(f"dailyBonus getBonus: {j}")
        return j

    def try_wd(self, balance: float) -> Optional[dict]:
        if balance < MIN_WD:
            return None
        # captcha payout = Turnstile juga (field captcha)
        try:
            tok = solve_turnstile()
        except Exception as e:
            log(f"WD captcha gagal: {e}")
            return None
        j = self.post("/user/payout/send/", {
            "sum": f"{balance:.7f}".rstrip("0").rstrip("."),
            "service": SERVICE,
            "captcha": tok,
        })
        log(f"WD {balance} → {SERVICE}: {j}")
        return j

    def status(self) -> dict:
        d = self.dashboard()
        u = d.get("user") or {}
        return {
            "balance": u.get("balance"),
            "coins": u.get("coins"),
            "viewCurDay": u.get("viewCurDay"),
            "viewAll": u.get("viewAll"),
            "profitDay": u.get("profitDay"),
        }


def cycle(cl: Clip, do_wd: bool = True) -> dict:
    st = cl.status()
    log(f"STATUS balance={st['balance']} coins={st['coins']} "
        f"viewToday={st['viewCurDay']}/{st.get('viewAll')}")

    cl.ensure_wallet()

    # daily bonus (klaim kalau server izinkan)
    try:
        cl.daily_bonus()
    except Exception as e:
        log(f"daily: {e}")

    results = []
    miss_captcha = 0
    # maksimal 20 video per cycle (human-ish), limit server 540/hari
    for i in range(20):
        try:
            r = cl.watch_one()
        except Exception as e:
            log(f"watch error: {e}")
            break
        results.append(r)
        if not r.get("ok"):
            why = r.get("why")
            log(f"watch miss ({why})")
            if why == "captcha":
                # captcha 3× gagal → lewati video ini, lanjut yang lain
                miss_captcha += 1
                if miss_captcha >= 4:
                    log("captcha gagal 4x berturut → stop watch")
                    break
                time.sleep(random.uniform(3, 7))
                continue
            # start_fail / limit / no_task → stop
            break
        miss_captcha = 0
        time.sleep(random.uniform(2.5, 6.0))

    # refresh status
    st = cl.status()
    log(f"AFTER balance={st['balance']} coins={st['coins']} viewToday={st['viewCurDay']}")

    wd = None
    if do_wd:
        try:
            bal = float(st.get("balance") or 0)
            wd = cl.try_wd(bal)
        except Exception as e:
            log(f"WD error: {e}")

    return {"status": st, "watched": results, "wd": wd}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--login", action="store_true", help="paksa re-login")
    ap.add_argument("--once", action="store_true", help="satu siklus lalu keluar")
    ap.add_argument("--status", action="store_true", help="print status lalu keluar")
    ap.add_argument("--no-wd", action="store_true", help="lewati auto-WD")
    ap.add_argument("--interval", type=int, default=180, help="jeda antar siklus (detik)")
    args = ap.parse_args()

    state = load_state()
    cl = Clip(state)

    try:
        cl.ensure_auth(force_login=args.login)
    except Exception as e:
        log(f"AUTH FAIL: {e}")
        sys.exit(1)

    # simpan cookie baru
    st = load_state()
    st["cookie"] = cl.cookies_out()
    save_state(st)

    if args.status:
        print(json.dumps(cl.status(), indent=2))
        return

    if args.once:
        cycle(cl, do_wd=not args.no_wd)
        return

    log(f"loop mulai (interval {args.interval}s)")
    while True:
        try:
            cycle(cl, do_wd=not args.no_wd)
        except Exception as e:
            log(f"cycle error: {e}")
            # coba reauth sekali
            try:
                cl.ensure_auth(force_login=True)
                st = load_state()
                st["cookie"] = cl.cookies_out()
                save_state(st)
            except Exception as e2:
                log(f"reauth gagal: {e2}")
                time.sleep(60)
        time.sleep(args.interval + random.uniform(0, 15))


if __name__ == "__main__":
    main()
