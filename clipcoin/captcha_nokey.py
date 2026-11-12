#!/usr/bin/env python3
# captcha_nokey.py — bypass SEMUA kelas captcha TANPA API KEY.
#
# AI vision KEYLESS: OVH anonymous endpoint (Qwen2.5-VL-72B) — tanpa
# signup, tanpa token, tanpa Gemini key. Cadangan: Gemini (kalau key ada),
# CV lokal (match, terbukti clipcoin), tesseract (image, last resort).
#
# Mode (CLI identik captcha_ai.py → drop-in):
#   image     FILE                 → baca teks captcha (vision keyless)
#   click     FILE --targets a,b,c → klik-gambar → koordinat genap
#   match     SCENE QUEUE          → scene + strip 3 ikon → 3 koordinat
#                                    (CV lokal dulu, nol jaringan)
#   grid      FILE --title "..."   → tile reCAPTCHA 3x3/4x4 → indeks
#   turnstile URL SITEKEY          → token: xsolve → peak → solvercf
#                                    (butuh solver key di lm_config —
#                                     itu service berbayar, BUKAN AI)
#   hcaptcha  URL SITEKEY          → token: nonecap
#   balance                        → status endpoint keyless + key
#   selftest                       → uji image/click/grid/match tanpa key
#
# Output: teks biasa; --json JSON; -q bersih (buat pipe).
#
# Rate-limit OVH: ±2 panggilan/menit per IP → pacing 12 dtk antar call,
# 429/402 → tunggu 55 dtk, retry maks 3.

import argparse
import base64
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

try:
    import requests
except ImportError:
    requests = None

# ------------------------------------------------------- keyless vision ---

OVH_URL = "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1/chat/completions"
OVH_MODEL = "Qwen2.5-VL-72B-Instruct"
OVH_MIN_GAP = 12.0      # dtk antar panggilan sukses (jaga jendela rate)
OVH_WAIT = 55.0         # dtk tunggu saat 429/402
_last_ovh = [0.0]       # timestamp panggilan OVH terakhir


def _data_uri(path) -> str:
    raw = open(path, "rb").read()
    mime = "image/png"
    if raw[:3] == b"\xff\xd8\xff":
        mime = "image/jpeg"
    elif raw[:4] == b"RIFF":
        mime = "image/webp"
    return f"data:{mime};base64," + base64.b64encode(raw).decode()


def ovh_vision(prompt: str, img_paths, timeout: int = 70,
               max_tokens: int = 400) -> str:
    """Vision KEYLESS via OVH anonymous. Pacing + retry 429/402."""
    paths = [img_paths] if isinstance(img_paths, (str, os.PathLike)) \
        else list(img_paths)
    content = [{"type": "text", "text": prompt}]
    for p in paths:
        content.append({"type": "image_url", "image_url": {"url": _data_uri(p)}})
    body = json.dumps({
        "model": OVH_MODEL,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": max_tokens,
    }).encode()
    errs = []
    for attempt in range(4):
        gap = OVH_MIN_GAP - (time.time() - _last_ovh[0])
        if gap > 0:
            time.sleep(gap)
        try:
            req = urllib.request.Request(OVH_URL, data=body,
                                         headers={"Content-Type":
                                                  "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                j = json.loads(r.read())
            _last_ovh[0] = time.time()
            return j["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            _last_ovh[0] = time.time()
            try:
                detail = e.read()[:180].decode(errors="replace")
            except Exception:
                detail = ""
            errs.append(f"HTTP{e.code} {detail}")
            if e.code in (429, 402, 500, 502, 503):
                time.sleep(OVH_WAIT + attempt * 15)  # jendela rate / blip
                continue
            break  # 400/401/404: model/endpoint berubah → jangan loop
        except Exception as e:
            errs.append(str(e))
            time.sleep(8 + attempt * 8)
    raise RuntimeError("vision keyless gagal: " + " | ".join(errs[-3:]))


# ------------------------------------------------------------ AI (Gemini) ---
# Cadangan opsional — tool ini tetap jalan penuh tanpa key ini.

CFG_PATHS = [
    os.environ.get("LM_CONFIG", ""),
    "/storage/emulated/0/Download/ZYVO/sites/lightningminer/lm_config.json",
    "/storage/emulated/0/Download/ZYVO/zyvo-bots/lightningminer/lm_config.json",
    os.path.expanduser("~/.config/zyvo/lm_config.json"),
]


def load_cfg() -> dict:
    cfg = {}
    for p in CFG_PATHS:
        if p and os.path.isfile(p):
            try:
                cfg.update({k: v for k, v in json.load(open(p)).items() if v})
            except Exception:
                pass
            break
    for env, k in [("GEMINI_KEY", "gemini_key"), ("XSOLVE_KEY", "xsolve_key"),
                   ("PEAK_KEY", "peak_key"), ("SOLVERCF_KEY", "solvercf_key"),
                   ("NONECAP_KEY", "nonecap_key"),
                   ("CAPTCHAKINGS_KEY", "captchakings_key")]:
        if os.environ.get(env):
            cfg[k] = os.environ[env]
    return cfg


def log(msg: str, quiet: bool = False):
    if not quiet:
        print(msg, file=sys.stderr)


GEMINI_MODELS = ["gemini-3.5-flash", "gemini-flash-latest",
                 "gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def _img_part(path) -> dict:
    raw = open(path, "rb").read()
    mime = "image/png"
    if raw[:3] == b"\xff\xd8\xff":
        mime = "image/jpeg"
    elif raw[:4] == b"RIFF":
        mime = "image/webp"
    return {"inline_data": {"mime_type": mime,
                            "data": base64.b64encode(raw).decode()}}


def gemini_vision(key: str, prompt: str, img_path,
                  quiet: bool = False) -> str:
    """Cadangan ber-key — dilewati senyap kalau key kosong."""
    if not key:
        raise RuntimeError("gemini_key kosong")
    paths = [img_path] if isinstance(img_path, (str, os.PathLike)) \
        else list(img_path)
    parts = [{"text": prompt}] + [_img_part(p) for p in paths]
    errs = []
    for model in GEMINI_MODELS:
        for attempt in range(2):
            try:
                body = json.dumps({"contents": [{"parts": parts}]}).encode()
                url = f"{GEMINI_BASE}/{model}:generateContent?key={key}"
                req = urllib.request.Request(url, data=body,
                                             headers={"Content-Type":
                                                      "application/json"})
                with urllib.request.urlopen(req, timeout=45) as r:
                    j = json.loads(r.read())
                return j["candidates"][0]["content"]["parts"][0]["text"].strip()
            except urllib.error.HTTPError as e:
                detail = e.read()[:150].decode(errors="replace")
                errs.append(f"{model}: HTTP{e.code} {detail}")
                if e.code in (404, 403):
                    break
                time.sleep(2 + attempt * 3)
            except Exception as e:
                errs.append(f"{model}: {e}")
                time.sleep(2 + attempt * 3)
    raise RuntimeError("gemini gagal: " + " | ".join(errs[-3:]))


def ai_vision(prompt: str, img_paths, quiet: bool = False) -> str:
    """Ladder vision: KEYLESS OVH dulu → Gemini (kalau key ada)."""
    paths = [img_paths] if isinstance(img_paths, (str, os.PathLike)) \
        else list(img_paths)
    try:
        ans = ovh_vision(prompt, paths)
        log("  vision: OVH keyless OK", quiet)
        return ans
    except Exception as e:
        log(f"  vision OVH gagal → coba gemini: {e}", quiet)
    key = load_cfg().get("gemini_key", "")
    if key:
        return gemini_vision(key, prompt, paths, quiet)
    raise RuntimeError(f"vision keyless gagal & gemini key kosong ({e})")


# ------------------------------------------------------------ tesseract ---

def tesseract_ocr(path) -> str:
    """OCR lokal nol-jaringan — last resort utk teks captcha polos."""
    import subprocess
    import tempfile
    import numpy as np
    from PIL import Image, ImageOps
    best = ""
    try:
        im = Image.open(path).convert("L")
    except Exception:
        return ""
    im = im.resize((im.width * 4, im.height * 4), Image.LANCZOS)
    variants = [im, ImageOps.autocontrast(im),
                im.point(lambda p: 255 if p > 150 else 0)]
    for v in variants:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            v.save(f.name)
            pth = f.name
        try:
            for psm in ("7", "8", "13"):
                out = subprocess.run(
                    ["tesseract", pth, "stdout", "--psm", psm,
                     "-c", "tessedit_char_whitelist="
                           "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                           "abcdefghijklmnopqrstuvwxyz0123456789"],
                    capture_output=True, timeout=30).stdout.decode().strip()
                clean = re.sub(r"[^A-Za-z0-9]", "", out)
                if len(clean) >= 4 and len(clean) > len(best):
                    best = clean
        except Exception:
            pass
        finally:
            try:
                os.unlink(pth)
            except OSError:
                pass
    return best


# ---------------------------------------------------------------- modes ---

ANSWER_PROMPT = (
    "This is a captcha image. Read the text/code shown and reply with ONLY "
    "the characters (letters and digits), no spaces, no explanation, no quotes."
)


def mode_image(args) -> str:
    try:
        ans = ai_vision(args.prompt or ANSWER_PROMPT, args.file, args.quiet)
        ans = ans.strip().strip("`\"' \n")
        m = re.search(r"[A-Za-z0-9]{3,}", ans)
        if m and len(ans) > 12:
            ans = m.group(0)
        if re.fullmatch(r"[A-Za-z0-9]{4,12}", ans):
            return ans
        log("  vision balas aneh → fallback tesseract", args.quiet)
    except Exception as e:
        log(f"  vision gagal → tesseract: {e}", args.quiet)
    ocr = tesseract_ocr(args.file)
    if ocr:
        return ocr
    raise RuntimeError("image gagal: vision + tesseract sama-sama kosong")


def _even(v: float, limit: int) -> int:
    v = max(0, min(limit - 1, int(round(v))))
    return v - 1 if v % 2 else v


CLICK_PROMPT = (
    "This is a point-and-click captcha. Targets to find: {targets}.\n"
    "For EACH target (in the same order), locate its center in the image and "
    "reply ONLY with a JSON array of objects, like "
    '[{{"name":"<target>","x":123,"y":45}}]. Image size is {w}x{h} pixels. '
    "No explanation, JSON only."
)


def mode_click(args) -> str:
    from PIL import Image
    im = Image.open(args.file)
    w, h = im.size
    targets = [t.strip() for t in args.targets.split(",") if t.strip()]
    if not targets:
        raise RuntimeError("--targets wajib, mis --targets 'star,moon,key'")
    prompt = CLICK_PROMPT.format(targets=", ".join(targets), w=w, h=h)
    ans = ai_vision(prompt, args.file, args.quiet)
    m = re.search(r"\[.*\]", ans, re.S)
    if not m:
        raise RuntimeError(f"vision tidak balas JSON: {ans[:200]}")
    items = json.loads(m.group(0))
    out = []
    for i, it in enumerate(items):
        name = targets[i] if i < len(targets) else "?"
        if isinstance(it, dict):
            for k in ("name", "target", "label", "id"):
                if it.get(k):
                    name = str(it[k])
                    break
            pt = it.get("center") if isinstance(it.get("center"), dict) else it
            x, y = pt.get("x"), pt.get("y")
        elif isinstance(it, (list, tuple)) and len(it) >= 2:
            x, y = it[0], it[1]
        else:
            raise RuntimeError(f" bentuk item tak dikenal: {it!r}")
        if x is None or y is None:
            raise RuntimeError(f" item tanpa x/y: {it!r}")
        out.append({"name": name, "x": _even(float(x), w),
                    "y": _even(float(y), h)})
    return json.dumps(out)


# --------------------------------- match: scene + strip target (clipcoin) ---

# CV lokal (tanpa key, tanpa jaringan) — port dari clipcoin_auto.py,
# terbukti menyelesaikan image captcha live clipcoin 2026-11-12.

def _fg_mask_scene(arr):
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
                            if (0 <= ny < H and 0 <= nx < W
                                    and solid[ny, nx] and lab[ny, nx] == 0):
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
    img = np.array(Image.fromarray((sub * 255).astype(np.uint8))
                   .resize((nw, nh), Image.BILINEAR)) > 100
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


def match_cv(scene_path, queue_path) -> list:
    """CV lokal → [{"i","x","y"}] genap urut strip; None kalau gagal."""
    import itertools
    import numpy as np
    from PIL import Image
    try:
        im = np.array(Image.open(scene_path).convert("RGB"))
        q = np.array(Image.open(queue_path).convert("RGBA"))
    except Exception:
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
        return None
    N = len(scene)
    S = [[_diou(t, scene[j]["crop"]) for j in range(N)]
         for t in tpls]
    best = None
    for combo in itertools.permutations(range(N), 3):
        scs = [S[i][combo[i]] for i in range(3)]
        key = (sum(scs), min(scs))
        if best is None or key > best[0]:
            best = (key, combo, scs)
    _, combo, scs = best
    if min(scs) < 0.25:  # kecocokan terlalu lemah → jangan percaya
        return None
    from PIL import Image as _I
    W = _I.open(scene_path).size[0]
    H = _I.open(scene_path).size[1]
    out = []
    for i, j in enumerate(combo):
        cx, cy = scene[j]["center"]
        out.append({"i": i + 1,
                    "x": _even(cx, W), "y": _even(cy, H)})
    return out


MATCH_PROMPT = (
    "Image 1 is a captcha scene ({w}x{h} pixels) containing several icons. "
    "Image 2 is a horizontal strip with exactly 3 target icons in order "
    "left to right (position 1, 2, 3).\n"
    "For EACH target icon of Image 2, find the SAME icon inside Image 1 and "
    "give its center pixel coordinate, keeping strip order (1, then 2, then 3).\n"
    "Reply ONLY with a JSON array like "
    '[{{"i":1,"x":123,"y":45}},{{"i":2,"x":60,"y":90}},'
    '{{"i":3,"x":200,"y":150}}]. No explanation, JSON only.'
)


def mode_match(args) -> str:
    # 1) CV lokal — cepat, nol jaringan (terbukti clipcoin)
    clicks = match_cv(args.scene, args.queue)
    if clicks:
        log("  match: CV lokal OK", args.quiet)
        return json.dumps(clicks) if args.json else \
            " ".join(f"({c['x']},{c['y']})" for c in clicks)
    # 2) vision keyless (2 gambar)
    log("  match: CV gagal → vision keyless", args.quiet)
    from PIL import Image
    w, h = Image.open(args.scene).size
    prompt = MATCH_PROMPT.format(w=w, h=h)
    ans = ai_vision(prompt, [args.scene, args.queue], args.quiet)
    m = re.search(r"\[.*\]", ans, re.S)
    if not m:
        raise RuntimeError(f"vision balas bukan JSON: {ans[:200]}")
    items = json.loads(m.group(0))
    out = []
    for idx, it in enumerate(items):
        if isinstance(it, dict):
            x, y = it.get("x"), it.get("y")
        elif isinstance(it, (list, tuple)) and len(it) >= 2:
            x, y = it[0], it[1]
        else:
            raise RuntimeError(f"item aneh: {it!r}")
        if x is None or y is None:
            raise RuntimeError(f"item tanpa x/y: {it!r}")
        out.append({"i": idx + 1, "x": _even(float(x), w),
                    "y": _even(float(y), h)})
        if idx == 2:
            break
    if len(out) != 3:
        raise RuntimeError(f"vision balas {len(out)} koordinat, harus 3")
    return json.dumps(out) if args.json else \
        " ".join(f"({c['x']},{c['y']})" for c in out)


# ------------------------- grid: tile challenge reCAPTCHA 3x3/4x4 ---------

GRID_PROMPT = (
    "This image is a Google reCAPTCHA image-select challenge divided into a "
    "{grid} grid of equal tiles, numbered left-to-right, top-to-bottom "
    "(3x3 → tiles 0..8, 4x4 → tiles 0..15).\n"
    "Challenge instruction: find all tiles containing \"{title}\".\n"
    "Reply ONLY with a JSON array of the tile indices that contain the object, "
    'e.g. [0,4,7]. Empty array [] if none. No explanation, JSON only.'
)


def mode_grid(args) -> str:
    grid, title = args.grid, args.title
    errs = []
    prompt = GRID_PROMPT.format(grid=grid, title=title.lower().strip())
    n = 9 if grid == "3x3" else 16
    try:
        ans = ai_vision(prompt, args.file, args.quiet)
        m = re.search(r"\[.*?\]", ans, re.S)
        if not m:
            raise RuntimeError(f"vision balas bukan JSON: {ans[:200]}")
        tiles = [int(x) for x in re.findall(r"-?\d+", m.group(0))]
        tiles = sorted({t for t in tiles if 0 <= t < n})
        res = {"tiles": tiles, "grid": grid, "title": title,
               "via": "vision-keyless", "errors": errs}
        return json.dumps(res) if args.json else ",".join(map(str, tiles))
    except Exception as e:
        errs.append(f"vision: {e}")
        log(f"  vision gagal → cadangan: {e}", args.quiet)
    cfg = load_cfg()
    if cfg.get("captchakings_key") and requests:
        r = requests.post(
            "https://captchakings.com/api/recaptcha.php",
            headers={"Authorization": f"Bearer {cfg['captchakings_key']}",
                     "Content-Type": "application/json"},
            json={"grid": grid, "challenge_title": title,
                  "image_base64": base64.b64encode(
                      open(args.file, "rb").read()).decode()},
            timeout=40)
        j = r.json()
        if j.get("success"):
            tiles = sorted(int(t) for t in (j.get("tiles_to_click") or []))
            res = {"tiles": tiles, "grid": grid, "title": title,
                   "via": "captchakings", "errors": errs}
            return json.dumps(res) if args.json else \
                ",".join(map(str, tiles))
        errs.append(f"captchakings: {str(j)[:150]}")
    raise RuntimeError("grid gagal semua: " + " | ".join(errs))


# ------------------------------------------------- token chain (solver) ---
# Token captcha (Turnstile/hCaptcha) TIDAK bisa di-AI-in tanpa service —
# rantai ini pakai key solver yang SUDAH ada di lm_config (bukan AI key).
# Kalau key kosong, error jelas, bukan hang.

def solve_xsolve(key, sitekey, url, action=None, cdata=None, ua=None) -> dict:
    payload = {"mode": "turnstile", "url": url, "sitekey": sitekey}
    if action:
        payload["action"] = action
    if cdata:
        payload["cdata"] = cdata
    r = requests.post("https://api.xsolve.me/task",
                      headers={"X-Api-Key": key}, json=payload, timeout=90)
    j = r.json()
    tok = j.get("token") or ""
    if tok and str(j.get("status", "completed")) in ("completed", "ready",
                                                     "success"):
        return {"token": tok, "via": "xsolve"}
    tid = j.get("taskId") or j.get("task_id")
    if not tid:
        raise RuntimeError(f"xsolve HTTP {r.status_code}: {str(j)[:180]}")
    t0 = time.time()
    while time.time() - t0 < 90:
        time.sleep(3)
        p = requests.post("https://api.xsolve.me/getTaskResult",
                          json={"clientKey": key, "taskId": tid},
                          timeout=40).json()
        if p.get("status") in ("ready", "success", "completed"):
            tok = (p.get("solution") or {}).get("token") or \
                  (p.get("solution") or {}).get("value") or ""
            if tok:
                return {"token": tok, "via": "xsolve"}
            raise RuntimeError("xsolve ready tanpa token")
        if p.get("errorId") or p.get("errorCode") or p.get("error"):
            raise RuntimeError(f"xsolve: {str(p)[:180]}")
    raise RuntimeError("xsolve timeout")


def solve_peak(key, sitekey, url, action=None, cdata=None, ua=None) -> dict:
    payload = {"task_type": "turnstiletaskproxyless", "url": url,
               "sitekey": sitekey}
    if action:
        payload["action"] = action
    if cdata:
        payload["cdata"] = cdata
    r = requests.post("https://api.peak.fo/solve",
                      headers={"X-API-Key": key}, json=payload, timeout=60)
    j = r.json()
    if not j.get("success"):
        raise RuntimeError(f"peak: {str(j)[:180]}")
    tok = (j.get("data") or {}).get("token") or ""
    if not tok:
        raise RuntimeError("peak tanpa token")
    return {"token": tok, "via": "peak"}


def solve_solvercf(key, sitekey, url, action=None, cdata=None, ua=None) -> dict:
    task = {"type": "TurnstileTask", "websiteUrl": url, "websiteKey": sitekey}
    if action:
        task["pageAction"] = action
    if cdata:
        task["data"] = cdata
    if ua:
        task["userAgent"] = ua
    base = "https://solvercf.com/token/extension"
    r = requests.post(f"{base}/createTask",
                      json={"clientKey": key, "task": task}, timeout=30)
    j = r.json()
    tid = j.get("taskId")
    if not tid:
        raise RuntimeError(f"solvercf createTask: {str(j)[:180]}")
    for _ in range(30):
        time.sleep(3)
        p = requests.post(f"{base}/getTaskResult",
                          json={"clientKey": key, "taskId": tid},
                          timeout=30).json()
        if p.get("status") == "ready":
            tok = (p.get("solution") or {}).get("token") or ""
            if tok:
                return {"token": tok, "via": "solvercf",
                        "userAgent": (p.get("solution") or {}).get("userAgent")}
            raise RuntimeError("solvercf ready tanpa token")
        if p.get("status") == "failed":
            raise RuntimeError(
                f"solvercf failed: {p.get('errorCode')} "
                f"{p.get('errorDescription') or p.get('error') or ''}")
        if p.get("errorId") not in (0, None, "0"):
            raise RuntimeError(f"solvercf: {str(j)[:180]}")
    raise RuntimeError("solvercf timeout")


TURNSTILE_CHAIN = [
    ("xsolve_key", "xsolve", solve_xsolve),
    ("peak_key", "peak", solve_peak),
    ("solvercf_key", "solvercf", solve_solvercf),
]


def mode_turnstile(args) -> str:
    if requests is None:
        raise RuntimeError("butuh requests: pip install requests")
    cfg = load_cfg()
    errs, order = [], TURNSTILE_CHAIN
    if args.only:
        order = [c for c in TURNSTILE_CHAIN if c[1] == args.only]
    for key_name, name, fn in order:
        key = cfg.get(key_name) or ""
        if not key:
            errs.append(f"{name}: key tidak ada")
            continue
        log(f"  coba {name}…", args.quiet)
        try:
            res = fn(key, args.sitekey, args.url,
                     args.action, args.data, args.ua)
            res["errors"] = errs
            return json.dumps(res) if args.json else res["token"]
        except Exception as e:
            errs.append(f"{name}: {e}")
            log(f"  {name} gagal → lanjut: {e}", args.quiet)
    raise RuntimeError("semua solver gagal: " + " | ".join(errs) +
                       " — token butuh solver key (bukan AI)")


def solve_nonecap(key, sitekey, url, ua=None) -> dict:
    headers = {"Authorization": f"Bearer {key}",
               "Content-Type": "application/json"}
    body = {"type": "hcaptcha", "sitekey": sitekey, "url": url}
    if ua:
        body["user_agent"] = ua
    r = requests.post("https://api.nonecap.com/v1/solves", params={"wait": 60},
                      headers=headers, json=body, timeout=90)
    data = r.json() if "json" in r.headers.get("Content-Type", "") else {}
    if r.status_code >= 400:
        err = data.get("error") or {}
        raise RuntimeError(f"NoneCap HTTP {r.status_code}: "
                           f"{err.get('code')} — {err.get('message')}")
    deadline = time.time() + 90
    while data.get("status") in ("pending", "solving") and time.time() < deadline:
        time.sleep(2)
        pr = requests.get(f"https://api.nonecap.com/v1/solves/{data['id']}",
                          params={"wait": 30}, headers=headers, timeout=45)
        data = pr.json()
    if data.get("status") != "solved":
        err = data.get("error") or {}
        raise RuntimeError(f"solve {data.get('status')}: "
                           f"{err.get('code')} — {err.get('message')}")
    tok = data.get("solution", {}).get("token") or data.get("token") or ""
    if not tok:
        raise RuntimeError("NoneCap solved tanpa token")
    return {"token": tok, "via": "nonecap"}


def mode_hcaptcha(args) -> str:
    if requests is None:
        raise RuntimeError("butuh requests: pip install requests")
    cfg = load_cfg()
    key = cfg.get("nonecap_key") or ""
    if not key:
        raise RuntimeError("nonecap_key kosong (dashboard.nonecap.com → "
                           "1300 kredit gratis)")
    res = solve_nonecap(key, args.sitekey, args.url, args.ua)
    return json.dumps(res) if args.json else res["token"]


# ------------------------------------------------------------- util modes ---

def mode_balance(args) -> str:
    out = {"keyless_vision": OVH_MODEL, "keyless_url": OVH_URL.split("/v1")[0]}
    try:
        req = urllib.request.Request(
            "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1/models",
            headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            ids = [m.get("id") for m in json.loads(r.read()).get("data", [])]
        out["keyless_endpoint"] = ("HIDUP" if OVH_MODEL in ids
                                   else f"hidup, model {OVH_MODEL} tak terdaftar")
        out["model_terdaftar"] = len(ids)
    except Exception as e:
        out["keyless_endpoint"] = f"mati: {e}"
    cfg = load_cfg()
    for k in ("gemini_key", "xsolve_key", "peak_key", "solvercf_key",
              "nonecap_key"):
        v = cfg.get(k) or ""
        out[k] = ("ada" if v else "KOSONG") + (f" ({len(v)} ch)" if v else "")
    return json.dumps(out, indent=2, ensure_ascii=False) if not args.json \
        else json.dumps(out, ensure_ascii=False)


def _mk_image(truth: str):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (200, 60), (235, 235, 240))
    d = ImageDraw.Draw(img)
    d.text((12, 10), truth, fill=(15, 15, 55))
    d.line((5, 50, 195, 44), fill=(120, 60, 60), width=2)
    return img


def _mk_click():
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (300, 200), (240, 240, 245))
    d = ImageDraw.Draw(img)
    d.ellipse((20, 20, 60, 60), fill=(220, 40, 40))
    d.rectangle((130, 80, 180, 130), fill=(40, 120, 220))
    d.polygon([(240, 150), (260, 190), (220, 190)], fill=(40, 180, 60))
    return img


def _mk_grid():
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (300, 300), (200, 210, 220))
    d = ImageDraw.Draw(img)
    for ox, oy in ((0, 0), (100, 100)):
        d.rectangle((ox + 40, oy + 20, ox + 60, oy + 80), fill=(30, 30, 30))
        for i, c in enumerate(((220, 40, 40), (230, 200, 40), (40, 200, 60))):
            d.ellipse((ox + 43, oy + 25 + i * 18, ox + 57, oy + 39 + i * 18),
                      fill=c)
    for ty in range(3):
        for tx in range(3):
            if (tx, ty) not in ((0, 0), (1, 1)):
                d.ellipse((tx * 100 + 35, ty * 100 + 35,
                           tx * 100 + 65, ty * 100 + 65), fill=(60, 90, 200))
    return img


def _mk_match():
    """Scene gelap (mask ambang butuh latar redup) + strip RGBA transparan."""
    from PIL import Image, ImageDraw
    scene = Image.new("RGB", (240, 160), (18, 18, 24))
    ds = ImageDraw.Draw(scene)
    ds.ellipse((30, 30, 70, 70), fill=(200, 30, 30))
    ds.rectangle((150, 90, 190, 130), fill=(30, 30, 200))
    ds.polygon([(90, 120), (110, 150), (70, 150)], fill=(30, 150, 30))
    strip = Image.new("RGBA", (180, 50), (0, 0, 0, 0))
    st = ImageDraw.Draw(strip)
    st.rectangle((10, 10, 40, 40), fill=(30, 30, 200, 255))   # kotak
    st.polygon([(80, 40), (100, 10), (60, 10)],
               fill=(30, 150, 30, 255))                        # segitiga
    st.ellipse((130, 10, 170, 40), fill=(200, 30, 30, 255))    # lingkaran
    return scene, strip


def mode_selftest(args) -> str:
    """4 sub-test tanpa key: image / click / grid / match(CV)."""
    tmp = os.environ.get("TMPDIR", "/data/data/com.termux/files/usr/tmp")
    from PIL import Image, ImageDraw  # noqa: F401  (dipakai _mk_*)
    results = {}

    # 1) image → vision keyless harus baca 7GK9PZ
    truth = "7GK9PZ"
    p1 = os.path.join(tmp, "nokey_image.png")
    _mk_image(truth).save(p1)
    log("1/4 image (vision keyless)…", args.quiet)
    try:
        got = mode_image(argparse.Namespace(file=p1, prompt=None,
                                            quiet=args.quiet))
        results["image"] = {"expected": truth, "got": got,
                            "pass": got.upper() == truth.upper()}
    except Exception as e:
        results["image"] = {"pass": False, "error": str(e)}

    # 2) click → 3 koordinat dekat target sejati (±40 px)
    p2 = os.path.join(tmp, "nokey_click.png")
    _mk_click().save(p2)
    log("2/4 click (vision keyless)…", args.quiet)
    expect = {"red circle": (40, 40), "blue square": (155, 105),
              "green triangle": (240, 170)}
    try:
        out = json.loads(mode_click(
            argparse.Namespace(file=p2, targets="red circle,blue square,"
                                                "green triangle",
                               quiet=args.quiet)))
        ok = len(out) == 3
        for it in out:
            ex = expect.get(it["name"])
            if ex and (abs(it["x"] - ex[0]) > 45 or abs(it["y"] - ex[1]) > 45):
                ok = False
        results["click"] = {"pass": ok, "got": out}
    except Exception as e:
        results["click"] = {"pass": False, "error": str(e)}

    # 3) grid → [0,4]
    p3 = os.path.join(tmp, "nokey_grid.png")
    _mk_grid().save(p3)
    log("3/4 grid (vision keyless)…", args.quiet)
    try:
        out = mode_grid(argparse.Namespace(file=p3, title="traffic lights",
                                           grid="3x3", json=True,
                                           quiet=args.quiet))
        tiles = json.loads(out)["tiles"]
        results["grid"] = {"expected": [0, 4], "got": tiles,
                           "pass": tiles == [0, 4]}
    except Exception as e:
        results["grid"] = {"pass": False, "error": str(e)}

    # 4) match → CV lokal (nol jaringan): strip kotak,segitiga,lingkaran
    p4s = os.path.join(tmp, "nokey_scene.png")
    p4q = os.path.join(tmp, "nokey_queue.png")
    scene, strip = _mk_match()
    scene.save(p4s)
    strip.save(p4q)
    log("4/4 match (CV lokal)…", args.quiet)
    try:
        out = json.loads(mode_match(argparse.Namespace(scene=p4s, queue=p4q,
                                                       json=True,
                                                       quiet=args.quiet)))
        # GT: kotak(170,110) segitiga(90,135) lingkaran(50,50)
        gt = [(170, 110), (90, 135), (50, 50)]
        ok = len(out) == 3 and all(
            abs(c["x"] - g[0]) <= 30 and abs(c["y"] - g[1]) <= 30
            for c, g in zip(out, gt))
        results["match"] = {"expected": gt, "got": out, "pass": ok}
    except Exception as e:
        results["match"] = {"pass": False, "error": str(e)}

    all_pass = all(r.get("pass") for r in results.values())
    results["ALL"] = "LULUS TANPA API KEY" if all_pass else "ADA YANG GAGAL"
    return json.dumps(results, indent=1, ensure_ascii=False) if args.json else \
        "\n".join(
            [f"{'✔' if r.get('pass') else '✘'} {k}: "
             f"{r.get('error') or r.get('got') or r}"
             for k, r in results.items() if k != "ALL"]
            + [results["ALL"]])


# ------------------------------------------------------------------- main ---

def main():
    ap = argparse.ArgumentParser(
        prog="captcha_nokey.py",
        description="Bypass captcha TANPA API KEY: vision keyless + CV lokal "
                    "+ tesseract; token via solver key (opsional).")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-q", "--quiet", action="store_true",
                        default=argparse.SUPPRESS, help="hanya hasil")
    common.add_argument("--json", action="store_true",
                        default=argparse.SUPPRESS, help="output JSON")
    ap.add_argument("-q", "--quiet", action="store_true", help="hanya hasil")
    ap.add_argument("--json", action="store_true", help="output JSON")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("image", parents=[common],
                       help="baca teks captcha (vision keyless)")
    p.add_argument("file")
    p.add_argument("--prompt", help="prompt custom")

    p = sub.add_parser("click", parents=[common],
                       help="klik-gambar → koordinat genap")
    p.add_argument("file")
    p.add_argument("targets", help="daftar target dipisah koma")

    p = sub.add_parser("match", parents=[common],
                       help="scene + strip 3 ikon → 3 koordinat (CV dulu)")
    p.add_argument("scene")
    p.add_argument("queue")

    p = sub.add_parser("grid", parents=[common],
                       help="tile grid reCAPTCHA → indeks")
    p.add_argument("file")
    p.add_argument("--title", required=True, help="objek dicari")
    p.add_argument("--grid", default="3x3", choices=["3x3", "4x4"])

    p = sub.add_parser("turnstile", parents=[common],
                       help="token Turnstile (rantai solver — butuh key)")
    p.add_argument("url")
    p.add_argument("sitekey")
    p.add_argument("--action")
    p.add_argument("--data")
    p.add_argument("--ua")
    p.add_argument("--only", choices=["xsolve", "peak", "solvercf"])

    p = sub.add_parser("hcaptcha", parents=[common],
                       help="token hCaptcha (nonecap — butuh key)")
    p.add_argument("url")
    p.add_argument("sitekey")
    p.add_argument("--ua")

    p = sub.add_parser("balance", parents=[common],
                       help="status endpoint keyless + key solver")
    p = sub.add_parser("selftest", parents=[common],
                       help="uji 4 mode TANPA key")

    args = ap.parse_args()
    fn = {"image": mode_image, "click": mode_click, "match": mode_match,
          "grid": mode_grid, "turnstile": mode_turnstile,
          "hcaptcha": mode_hcaptcha, "balance": mode_balance,
          "selftest": mode_selftest}[args.cmd]
    try:
        out = fn(args)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    print(out)


if __name__ == "__main__":
    main()
