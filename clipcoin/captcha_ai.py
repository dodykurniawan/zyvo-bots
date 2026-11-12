#!/usr/bin/env python3
# captcha_ai.py — bypass captcha dengan AI (Gemini vision) + rantai solver token.
#
# Mode:
#   image     FILE                 → baca teks captcha pakai AI vision
#   click     FILE --targets a,b,c → captcha klik-gambar: AI kasih koordinat (genap, px)
#   turnstile URL SITEKEY          → token Turnstile: xsolve → peak → solvercf
#   hcaptcha  URL SITEKEY          → token hCaptcha: nonecap
#   balance                        → cek kredit solver + status key
#   selftest                       → uji AI baca captcha sintetis
#
# Key: baca lm_config.json (otomatis) + override env
#   GEMINI_KEY / XSOLVE_KEY / PEAK_KEY / SOLVERCF_KEY / NONECAP_KEY
# Output: teks biasa; --json untuk JSON; -q hanya hasil bersih (buat pipe).

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

# ---------------------------------------------------------------- config ---

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
            break  # jalur pertama yang ada = sumber utama
    for env, k in [("GEMINI_KEY", "gemini_key"), ("XSOLVE_KEY", "xsolve_key"),
                   ("PEAK_KEY", "peak_key"), ("SOLVERCF_KEY", "solvercf_key"),
                   ("NONECAP_KEY", "nonecap_key")]:
        if os.environ.get(env):
            cfg[k] = os.environ[env]
    return cfg


def log(msg: str, quiet: bool = False):
    if not quiet:
        print(msg, file=sys.stderr)


# ------------------------------------------------------------ AI (Gemini) ---

# Model dipesan dari yang paling stabil; 2.0/2.5 sudah dihapus Google (404),
# 3.8 sering 503 → 3.5-flash terbukti baca captcha bener (2026-11-12).
GEMINI_MODELS = [
    "gemini-3.5-flash",
    "gemini-flash-latest",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
]
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def _gemini_call(key: str, model: str, parts: list,
                 timeout: int = 45) -> str:
    body = json.dumps({"contents": [{"parts": parts}]}).encode()
    url = f"{GEMINI_BASE}/{model}:generateContent?key={key}"
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        j = json.loads(r.read())
    return j["candidates"][0]["content"]["parts"][0]["text"]


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
    """Kirim 1+ gambar ke Gemini → teks. Rantai model + retry 503/429/timeout."""
    if not key:
        raise RuntimeError("gemini_key kosong (isi di lm_config.json / env GEMINI_KEY)")
    paths = [img_path] if isinstance(img_path, (str, os.PathLike)) \
        else list(img_path)
    parts = [{"text": prompt}] + [_img_part(p) for p in paths]
    errs = []
    for model in GEMINI_MODELS:
        for attempt in range(2):
            try:
                return _gemini_call(key, model, parts).strip()
            except urllib.error.HTTPError as e:
                detail = e.read()[:150].decode(errors="replace").replace("\n", " ")
                errs.append(f"{model}: HTTP{e.code} {detail}")
                if e.code in (404, 403):  # model mati / key salah → model berikut
                    break
                time.sleep(2 + attempt * 3)  # 429/503 → backoff lalu ulang
            except Exception as e:
                errs.append(f"{model}: {e}")
                time.sleep(2 + attempt * 3)
    raise RuntimeError("AI vision gagal semua: " + " | ".join(errs[-4:]))


ANSWER_PROMPT = (
    "This is a captcha image. Read the text/code shown and reply with ONLY "
    "the characters (letters and digits), no spaces, no explanation, no quotes."
)


def mode_image(args) -> str:
    cfg = load_cfg()
    ans = gemini_vision(cfg.get("gemini_key", ""),
                        args.prompt or ANSWER_PROMPT, args.file, args.quiet)
    # bersihkan artefak kalau model masih ngoceh
    ans = ans.strip().strip("`\"' \n")
    m = re.search(r"[A-Za-z0-9]{3,}", ans)
    if m and len(ans) > 12:
        ans = m.group(0)
    return ans


def _even(v: float, limit: int) -> int:
    """Klik genap + clamp (pola clipcoin: server terima koordinat genap)."""
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
    cfg = load_cfg()
    im = Image.open(args.file)
    w, h = im.size
    targets = [t.strip() for t in args.targets.split(",") if t.strip()]
    if not targets:
        raise RuntimeError("--targets wajib, mis --targets 'star,moon,key'")
    prompt = CLICK_PROMPT.format(targets=", ".join(targets), w=w, h=h)
    ans = gemini_vision(cfg.get("gemini_key", ""), prompt, args.file, args.quiet)
    # parse JSON dari balasan (toleran code-fence)
    m = re.search(r"\[.*\]", ans, re.S)
    if not m:
        raise RuntimeError(f"AI tidak balas JSON: {ans[:200]}")
    items = json.loads(m.group(0))
    out = []
    for i, it in enumerate(items):
        name = targets[i] if i < len(targets) else "?"
        if isinstance(it, dict):
            # bentuk bisa: {name/target,label, x,y} atau {center:{x,y}}
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
    # body format klip-clip: coor[i][x] — siap dipakai
    return json.dumps(out)


# --------------------------------- match: scene + strip target (clipcoin) ---

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


def match_icons(scene_path, queue_path, quiet: bool = True) -> list:
    """AI cocokkan 3 ikon strip ke scene → [{"i","x","y"}] genap, urut strip."""
    from PIL import Image
    cfg = load_cfg()
    w, h = Image.open(scene_path).size
    prompt = MATCH_PROMPT.format(w=w, h=h)
    ans = gemini_vision(cfg.get("gemini_key", ""), prompt,
                        [str(scene_path), str(queue_path)], quiet)
    m = re.search(r"\[.*\]", ans, re.S)
    if not m:
        raise RuntimeError(f"AI balas bukan JSON: {ans[:200]}")
    items = json.loads(m.group(0))
    out = []
    for idx, it in enumerate(items):  # percaya URUTAN array = urutan strip
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
        raise RuntimeError(f"AI balas {len(out)} koordinat, harus 3")
    return out


def mode_match(args) -> str:
    clicks = match_icons(args.scene, args.queue, quiet=args.quiet)
    return json.dumps(clicks) if args.json else \
        " ".join(f"({c['x']},{c['y']})" for c in clicks)


# ------------------------------------------------- token chain (Turnstile) ---

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
    if tok and str(j.get("status", "completed")) in ("completed", "ready", "success"):
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
        task["pageAction"] = action      # field ASLI (bukan "action")
    if cdata:
        task["data"] = cdata
    if ua:
        task["userAgent"] = ua           # wajib sama dgn UA submit token
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
            # errorId bisa 0 meski gagal — baca errorCode/errorDescription
            raise RuntimeError(
                f"solvercf failed: {p.get('errorCode')} "
                f"{p.get('errorDescription') or p.get('error') or ''}")
        if p.get("errorId") not in (0, None, "0"):
            raise RuntimeError(f"solvercf: {str(p)[:180]}")
    raise RuntimeError("solvercf timeout")


# Rantai urut: xsolve → peak → solvercf (terbukti 2026-11-12: dua pertama
# 402 insufficient, solvercf tetap hijau).
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
    raise RuntimeError("semua solver gagal: " + " | ".join(errs))


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
        raise RuntimeError("nonecap_key kosong (signup dashboard.nonecap.com → 1300 kredit gratis)")
    res = solve_nonecap(key, args.sitekey, args.url, args.ua)
    return json.dumps(res) if args.json else res["token"]


# ------------------------------------------------------------- util modes ---

def mode_balance(args) -> str:
    cfg = load_cfg()
    out = {}
    for k in ("gemini_key", "xsolve_key", "peak_key", "solvercf_key",
              "nonecap_key"):
        v = cfg.get(k) or ""
        out[k] = ("ada" if v else "KOSONG") + (f" ({len(v)} ch)" if v else "")
    if requests and cfg.get("nonecap_key"):
        try:
            r = requests.get("https://api.nonecap.com/v1/me",
                             headers={"Authorization":
                                      f"Bearer {cfg['nonecap_key']}"},
                             timeout=15)
            out["nonecap_kredit"] = r.json().get("credits_balance")
        except Exception as e:
            out["nonecap_kredit"] = f"cek gagal: {e}"
    # tes ringan Gemini (1 panggilan kecil, model murah)
    if cfg.get("gemini_key"):
        try:
            body = json.dumps({"contents": [{"parts": [{"text": "balas OK"}]}]}).encode()
            req = urllib.request.Request(
                f"{GEMINI_BASE}/gemini-3.5-flash-lite:generateContent"
                f"?key={cfg['gemini_key']}", data=body,
                headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=20)
            out["gemini_api"] = "HIDUP"
        except Exception as e:
            out["gemini_api"] = f"mati: {e}"
    return json.dumps(out, indent=2, ensure_ascii=False) if not args.json \
        else json.dumps(out, ensure_ascii=False)


def mode_selftest(args) -> str:
    """Uji jalur AI: captcha sintetis → Gemini → cocok?"""
    from PIL import Image, ImageDraw
    cfg = load_cfg()
    tmp = os.environ.get("TMPDIR",
                         "/data/data/com.termux/files/usr/tmp")
    truth = "7GK9PZ"
    img = Image.new("RGB", (200, 60), (235, 235, 240))
    d = ImageDraw.Draw(img)
    d.text((12, 10), truth, fill=(15, 15, 55))
    d.line((5, 50, 195, 44), fill=(120, 60, 60), width=2)
    path = os.path.join(tmp, "captcha_ai_selftest.png")
    img.save(path)
    log("menjalankan AI vision…", args.quiet)
    ans = gemini_vision(cfg.get("gemini_key", ""), ANSWER_PROMPT, path,
                        args.quiet)
    ans = re.sub(r"[^A-Za-z0-9]", "", ans)
    ok = ans.upper() == truth
    result = {"expected": truth, "got": ans, "pass": ok}
    return json.dumps(result) if args.json else \
        (f"LULUS (AI baca '{ans}')" if ok else
         f"GAGAL (harus {truth}, dapat '{ans}')")


# ------------------------------------------------------------------- main ---

def main():
    ap = argparse.ArgumentParser(
        prog="captcha_ai.py",
        description="Bypass captcha: AI vision (teks & klik) + rantai solver token.")
    common = argparse.ArgumentParser(add_help=False)
    # SUPPRESS: jangan timpa nilai flag global di depan subcommand
    common.add_argument("-q", "--quiet", action="store_true",
                        default=argparse.SUPPRESS,
                        help="hanya hasil, tanpa log")
    common.add_argument("--json", action="store_true",
                        default=argparse.SUPPRESS, help="output JSON")
    ap.add_argument("-q", "--quiet", action="store_true",
                    help="hanya hasil, tanpa log")
    ap.add_argument("--json", action="store_true", help="output JSON")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("image", parents=[common],
                       help="baca teks captcha via AI")
    p.add_argument("file")
    p.add_argument("--prompt", help="prompt custom (default: baca teks)")

    p = sub.add_parser("click", parents=[common],
                       help="captcha klik-gambar → koordinat genap")
    p.add_argument("file")
    p.add_argument("--targets", required=True,
                   help="daftar target dipisah koma: 'star,moon,key'")

    p = sub.add_parser("match", parents=[common],
                       help="scene + strip 3 ikon → 3 koordinat genap")
    p.add_argument("scene", help="gambar scene (captcha)")
    p.add_argument("queue", help="strip 3 ikon target")

    p = sub.add_parser("turnstile", parents=[common],
                       help="token Turnstile (rantai solver)")
    p.add_argument("url", help="halaman berisi captcha")
    p.add_argument("sitekey")
    p.add_argument("--action", help="pageAction (mis 'login', 'challenge')")
    p.add_argument("--data", help="cdata/challenge payload")
    p.add_argument("--ua", help="user-agent submit token (wajib kalau site check UA)")
    p.add_argument("--only", choices=["xsolve", "peak", "solvercf"],
                   help="pakai satu provider saja")

    p = sub.add_parser("hcaptcha", parents=[common],
                       help="token hCaptcha (nonecap)")
    p.add_argument("url")
    p.add_argument("sitekey")
    p.add_argument("--ua")

    p = sub.add_parser("balance", parents=[common],
                       help="cek status key + kredit solver")
    p = sub.add_parser("selftest", parents=[common],
                       help="uji AI baca captcha sintetis")

    args = ap.parse_args()
    fn = {"image": mode_image, "click": mode_click, "match": mode_match,
          "turnstile": mode_turnstile, "hcaptcha": mode_hcaptcha,
          "balance": mode_balance, "selftest": mode_selftest}[args.cmd]
    try:
        out = fn(args)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    print(out)


if __name__ == "__main__":
    main()
