#!/usr/bin/env python3
"""Poll Telegram getUpdates — balas /balance dengan saldo 3 situs.

Offset disimpan ke tg_offset.txt (di-cache GitHub Actions antar run).
Hanya membalas chat yang cocok TG_CHAT_ID.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

OFFSET_FILE = os.environ.get("TG_OFFSET_FILE", "tg_offset.txt")
BOT = os.environ["TG_BOT_TOKEN"]
CHAT_OK = os.environ.get("TG_CHAT_ID", "")
BALANCE_CMDS = {"/balance", "/bal", "/saldo", "/start"}


def api(method: str, **params) -> dict:
    url = f"https://api.telegram.org/bot{BOT}/{method}"
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=30) as r:
        resp = json.loads(r.read().decode())
    if not resp.get("ok"):
        raise RuntimeError(f"TG {method} gagal: {resp.get('description')}")
    return resp


def send(text: str) -> None:
    api("sendMessage", chat_id=CHAT_OK, text=text)


def fetch_balances() -> str:
    """Jalankan balance_all.py (sudah ada config di workspace)."""
    try:
        out = subprocess.check_output(
            [sys.executable, "scripts/balance_all.py"],
            stderr=subprocess.DEVNULL,
            timeout=60,
            text=True,
        )
        return out.strip()
    except Exception as e:
        return f"(gagal ambil balance: {e})"


def main() -> int:
    offset = 0
    if os.path.isfile(OFFSET_FILE):
        try:
            offset = int(open(OFFSET_FILE).read().strip() or "0")
        except ValueError:
            offset = 0

    resp = api("getUpdates", offset=offset, timeout=0, allowed_updates=["message"])
    updates = resp.get("result") or []
    if not updates:
        print("no updates")
        return 0

    last_id = offset
    for u in updates:
        last_id = max(last_id, u["update_id"] + 1)
        msg = u.get("message") or {}
        text = (msg.get("text") or "").strip()
        chat_id = str((msg.get("chat") or {}).get("id", ""))
        if CHAT_OK and chat_id != CHAT_OK:
            continue
        cmd = text.split()[0].lower() if text else ""
        if cmd in BALANCE_CMDS:
            print(f"balance request from {chat_id}")
            bal = fetch_balances()
            head = "💰 Saldo akun kamu:" if cmd != "/start" else "👋 halo! Balas /balance utk cek saldo."
            try:
                if cmd == "/start":
                    send(head + "\n\n" + bal)
                else:
                    send(head + "\n" + bal)
                print("sent")
            except Exception as e:
                print(f"send gagal: {e}")

    with open(OFFSET_FILE, "w") as f:
        f.write(str(last_id))
    print(f"offset -> {last_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
