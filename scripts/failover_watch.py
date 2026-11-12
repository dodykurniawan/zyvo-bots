#!/data/data/com.termux/files/usr/bin/python3
"""failover_watch.py — GitHub Actions ↔ Termux untuk CF / CTD / LM.

Keputusan user 2026-11-12:
- GitHub OFF → bot jalan di HP ini (otomatis)
- GitHub ON  → bot lokal dihentikan (satu akun — jangan dobel)
- Limefaucet SELALU di HP — script ini TIDAK menyentuh lime/clipcoin/scrapper.

Deteksi GH ON = workflow active DAN (run aktif OR baru jalan < 2 jam
OR schedule < 8 jam). API gagal → mode tidak diubah (jangan kill/start buta).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("/storage/emulated/0/Download/ZYVO/zyvo-bots")
SITES = Path("/storage/emulated/0/Download/ZYVO/sites")
LOG_PATH = SITES / "failover.log"
STATE_PATH = SITES / "failover_state.json"
REPO_SLUG = "dodykurniawan/zyvo-bots"

# jam schedule dianggap sehat (cron 6j + grace delay GitHub)
SCHEDULE_STALE_H = 8.0
# run apa pun (dispatch test dsb) menandakan GH hidup — cegah dobel
RECENT_RUN_H = 2.0
# jeda minimum antar restart bot yang mati sendiri
MIN_RESTART_GAP_S = 90

# HANYA pola ini yang boleh di-kill. JANGAN tambah lime/clipcoin/scrapper.
KILL_PATTERNS = [
    r"cryptofisher_premium\.py",
    r"cryptofisher_level\.py",
    r"cryptofisher_auto2?\.py",
    r"run_cf\.sh",
    r"ctd_auto\.py",
    r"lightningminer_auto\.py",
]

BOTS: dict[str, dict] = {
    "cf": {
        "label": "CF",
        "probe": r"cryptofisher_premium\.py",
        "cwd": SITES / "cryptofisher",
        "cmd": ["python3", "-u", "cryptofisher_premium.py", "--wd-every", "15"],
        "env_files": {"CF_EMAIL": "cf_email.txt", "CF_PASSWORD": "cf_secret.txt"},
        "log": "cf_premium_local.log",
    },
    "ctd": {
        "label": "CTD",
        "probe": r"ctd_auto\.py",
        "cwd": SITES / "cryptotowerdefense",
        "cmd": ["python3", "-u", "ctd_auto.py"],
        "env_files": {},
        "log": "ctd_auto_local.log",
    },
    "lm": {
        "label": "LM",
        "probe": r"lightningminer_auto\.py",
        "cwd": SITES / "lightningminer",
        "cmd": ["python3", "-u", "lightningminer_auto.py", "--interval", "180"],
        "env_files": {},
        "log": "lm_auto_local.log",
    },
}


def log(msg: str) -> None:
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    try:
        with LOG_PATH.open("a") as f:
            f.write(line + "\n")
    except OSError:
        pass


def notify(title: str, content: str) -> None:
    """Notifikasi lokal (termux-notification) — bukan TG, tanpa spam."""
    try:
        subprocess.run(
            ["termux-notification", "--title", title, "--content", content],
            timeout=10,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass


def gh_token() -> str:
    cred = Path.home() / ".git-credentials"
    try:
        for line in cred.read_text().splitlines():
            m = re.search(r"https://[^:]+:([^@]+)@github", line)
            if m:
                return m.group(1)
    except OSError:
        pass
    return os.environ.get("GH_TOKEN", "")


def _gh_get(path: str, token: str) -> dict:
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "zyvo-failover",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def gh_status() -> str:
    """'on' | 'off' | 'unknown'"""
    token = gh_token()
    if not token:
        log("GH token tidak ditemukan")
        return "unknown"
    try:
        wf = _gh_get(f"/repos/{REPO_SLUG}/actions/workflows/bots.yml", token)
        if wf.get("state") != "active":
            log(f"workflow state={wf.get('state')} → GH OFF")
            return "off"
        data = _gh_get(f"/repos/{REPO_SLUG}/actions/runs?per_page=20", token)
        runs = data.get("workflow_runs") or []
    except Exception as e:  # jangan pernah ubah mode saat API gagal
        log(f"GH API gagal: {e}")
        return "unknown"

    now = time.time()
    last_sched = None
    newest = None
    for run in runs:
        created = run.get("created_at")
        if not created:
            continue
        ts = datetime.fromisoformat(created.replace("Z", "+00:00")).timestamp()
        if newest is None or ts > newest:
            newest = ts
        if run.get("event") == "schedule" and (last_sched is None or ts > last_sched):
            last_sched = ts
        if run.get("status") in ("queued", "in_progress", "waiting", "requested"):
            log(f"GH run aktif #{run.get('id')} ({run.get('status')}) → GH ON")
            return "on"

    if newest is not None and (now - newest) < RECENT_RUN_H * 3600:
        log(f"GH baru jalan {(now - newest) / 60:.0f} mnt lalu → ON")
        return "on"
    if last_sched is not None:
        age_h = (now - last_sched) / 3600
        if age_h < SCHEDULE_STALE_H:
            log(f"schedule terakhir {age_h:.1f} jam lalu → ON")
            return "on"
        log(f"schedule terakhir {age_h:.1f} jam lalu (stale > {SCHEDULE_STALE_H}j) → OFF")
        return "off"
    log("tidak ada schedule run sama sekali → OFF")
    return "off"


def pids(pattern: str) -> list[int]:
    try:
        r = subprocess.run(
            ["pgrep", "-f", pattern],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return [int(x) for x in r.stdout.split() if x.strip().isdigit()]
    except Exception:
        return []


def bot_running(name: str) -> bool:
    return bool(pids(BOTS[name]["probe"]))


def any_local_running() -> bool:
    return any(bot_running(n) for n in BOTS)


def kill_local() -> None:
    killed = []
    for pat in KILL_PATTERNS:
        for pid in pids(pat):
            try:
                os.kill(pid, signal.SIGTERM)
                killed.append(pid)
            except OSError:
                pass
    if killed:
        log(f"SIGTERM → pid {killed}")
        time.sleep(5)
    # paksa sisa yang bandel
    for pat in KILL_PATTERNS:
        for pid in pids(pat):
            try:
                os.kill(pid, signal.SIGKILL)
                log(f"SIGKILL pid {pid} ({pat})")
            except OSError:
                pass
    time.sleep(1)
    if any_local_running():
        log("WARNING: masih ada proses lokal setelah kill")
    else:
        log("semua bot lokal CF/CTD/LM berhenti")


def start_bot(name: str) -> None:
    spec = BOTS[name]
    cwd = spec["cwd"]
    if not cwd.is_dir():
        log(f"{name}: cwd tidak ada {cwd}")
        return
    env = os.environ.copy()
    for key, fname in spec["env_files"].items():
        fpath = cwd / fname
        try:
            env[key] = fpath.read_text().strip()
        except OSError as e:
            log(f"{name}: {fname} gagal dibaca: {e}")
    logf = open(cwd / spec["log"], "a")
    try:
        subprocess.Popen(
            spec["cmd"],
            cwd=str(cwd),
            env=env,
            stdout=logf,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        log(f"{spec['label']} start → {' '.join(spec['cmd'])}")
    finally:
        logf.close()


def start_missing(last_start: dict[str, float]) -> None:
    now = time.time()
    for name in BOTS:
        if bot_running(name):
            continue
        gap = now - last_start.get(name, 0)
        if gap < MIN_RESTART_GAP_S:
            continue
        start_bot(name)
        last_start[name] = now


def load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(**kw) -> None:
    st = load_state()
    st.update(kw)
    st["updated"] = datetime.now(timezone.utc).isoformat()
    try:
        STATE_PATH.write_text(json.dumps(st, indent=2))
    except OSError:
        pass


def cycle(force: str | None, last_start: dict[str, float]) -> str:
    """Satu iterasi. force: 'on'|'off'|None (override deteksi — untuk tes)."""
    st = force if force else gh_status()
    local_up = any_local_running()

    if st == "unknown":
        # mode tidak berubah — hanya restart bot yang mati kalau memang lokal
        if load_state().get("mode") == "local":
            start_missing(last_start)
        return "unknown"

    if st == "on":
        if local_up:
            log("→ GH ON: hentikan bot lokal (cegah dobel)")
            kill_local()
            save_state(mode="gh", last_switch=datetime.now(timezone.utc).isoformat())
            notify("Failover", "GitHub hidup — bot lokal CF/CTD/LM dihentikan")
        return "on"

    # st == off
    if not local_up:
        log("→ GH OFF: nyalakan bot lokal di HP")
        start_missing(last_start)
        save_state(mode="local", last_switch=datetime.now(timezone.utc).isoformat())
        notify("Failover", "GitHub mati — bot CF/CTD/LM jalan di HP")
    else:
        start_missing(last_start)  # hidupkan yang mati sendiri
        if load_state().get("mode") != "local":
            save_state(mode="local")
    return "off"


def main() -> int:
    ap = argparse.ArgumentParser(description="Failover GH Actions ↔ Termux (CF/CTD/LM)")
    ap.add_argument("--check", action="store_true", help="cetak status lalu keluar")
    ap.add_argument("--once", action="store_true", help="satu siklus lalu keluar")
    ap.add_argument("--force-on", action="store_true", help="paksa deteksi GH ON (tes)")
    ap.add_argument("--force-off", action="store_true", help="paksa deteksi GH OFF (tes)")
    ap.add_argument("--interval", type=int, default=0,
                    help="detik antar cek (0 = adaptif: 60 lokal / 300 GH)")
    args = ap.parse_args()

    force = "on" if args.force_on else ("off" if args.force_off else None)

    if args.check:
        st = force or gh_status()
        print(f"GH: {st}")
        for n in BOTS:
            print(f"local {BOTS[n]['label']}: {'RUNNING' if bot_running(n) else 'stopped'}")
        print(f"state: {load_state()}")
        return 0

    log(f"failover watcher mulai (pid {os.getpid()})")
    last_start: dict[str, float] = {}
    while True:
        try:
            st = cycle(force, last_start)
        except Exception as e:
            log(f"cycle error: {e}")
            st = "unknown"

        if args.once:
            return 0

        if args.interval:
            sleep_s = args.interval
        elif st == "off" or load_state().get("mode") == "local":
            sleep_s = 60  # lokal jalan → pantau cepat, GH balik = segera kill
        else:
            sleep_s = 300
        time.sleep(sleep_s)


if __name__ == "__main__":
    sys.exit(main())
