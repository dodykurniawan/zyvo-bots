#!/usr/bin/env python3
"""Gate rotasi CI — cek apakah GitHub Actions (primary) masih sehat.

Dipakai di awal job `takeover` (.gitlab-ci.yml):
  exit 0 = TAKEOVER  → GH tidak punya run schedule dalam N jam terakhir
                       (mati / delay parah) → job lanjut jalanin bot
  exit 1 = SKIP      → GH sehat ATAU status tidak bisa dipastikan aman
                       → pemanggil keluar dengan exit 0 juga (hijau)

Jadwal: GH `17 */6` UTC. GitLab `17 3,9,15,21` UTC = slot + 3 jam,
biar run GH yang telat (pernah 1j38m delay) sempat mulai lebih dulu.
FORCE=1 (env) / --force = paksa takeover, untuk test.

Stdlib only — jalan di python:3.11 manapun.
"""
import argparse
import datetime
import json
import os
import sys
import urllib.error
import urllib.request

API = ("https://api.github.com/repos/{repo}/actions/workflows/{wf}"
       "/runs?event=schedule&per_page=10")


def log(*a):
    print("[ci_gate]", *a, flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default="dodykurniawan/zyvo-bots")
    p.add_argument("--workflow", default="bots.yml")
    p.add_argument("--window", type=float, default=5.0,
                   help="jam — run schedule dalam jendela ini = GH sehat")
    p.add_argument("--force", action="store_true")
    args = p.parse_args()

    if args.force or os.environ.get("FORCE") == "1":
        log("FORCE=1 → TAKEOVER (test)")
        return 0

    url = API.format(repo=args.repo, wf=args.workflow)
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "zyvo-ci-gate",
    })
    tok = os.environ.get("GH_TOKEN", "").strip()
    if tok:
        req.add_header("Authorization", "Bearer " + tok)

    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 429):
            # rate-limit / token bermasalah → tak bisa pastikan → JANGAN
            # takeover dulu (risiko tabrak cast dengan run GH yang telat)
            log(f"HTTP {e.code} → tidak bisa verifikasi, SKIP")
            return 1
        # 5xx dll — GitHub API rusak → Actions kemungkinan ikut mati
        log(f"HTTP {e.code} → GH API bermasalah, TAKEOVER")
        return 0
    except Exception as e:  # koneksi total mati
        log(f"koneksi gagal ({e!r}) → TAKEOVER")
        return 0

    runs = data.get("workflow_runs") or []
    now = datetime.datetime.now(datetime.timezone.utc)
    newest = None
    for run in runs:
        started = run.get("run_started_at") or run.get("created_at")
        if not started:
            continue
        t = datetime.datetime.fromisoformat(started.replace("Z", "+00:00"))
        age_h = (now - t).total_seconds() / 3600.0
        if newest is None or age_h < newest:
            newest = age_h
        if age_h <= args.window:
            log(f"GH SEHAT — run #{run.get('run_number')} mulai "
                f"{age_h:.1f} jam lalu ({run.get('status')}) → SKIP")
            return 1

    if newest is None:
        log("tidak ada run schedule sama sekali (workflow mati/terhapus)"
            " → TAKEOVER")
    else:
        log(f"run terakhir {newest:.1f} jam lalu (> {args.window} jam)"
            " → TAKEOVER")
    return 0


if __name__ == "__main__":
    sys.exit(main())
