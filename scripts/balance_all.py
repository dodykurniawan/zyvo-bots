#!/usr/bin/env python3
"""Ambil balance 3 situs → teks siap kirim ke Telegram.

Pemakaian:
  python3 scripts/balance_all.py \
    --cf cryptofisher/cf_config.json \
    --ctd cryptotowerdefense/ctd_cookie.txt \
    --lm lightningminer/lm_config.json

Setiap situs independen — gagal satu, yang lain tetap tampil.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Optional

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36"
)


def _fmt(x: Any, nd: int = 8) -> str:
    try:
        v = float(x)
        if v == int(v) and abs(v) >= 100:
            return str(int(v))
        return f"{v:.{nd}f}".rstrip("0").rstrip(".")
    except Exception:
        return str(x)


def cf_login(email: str, password: str) -> str:
    """Login CF (captcha tidak divalidasi server → token dummy)."""
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
    data = r.json()
    if not data.get("success") and data.get("error"):
        return ""
    sid = s.cookies.get("PHPSESSID") or ""
    if sid:
        # simpan ke config bila path-nya ada
        pass
    return sid


def cf_balance(cfg_path: str) -> str:
    sid = ""
    cfg: dict = {}
    if os.path.isfile(cfg_path):
        cfg = json.load(open(cfg_path))
        sid = cfg.get("phpsessid") or ""
    # fallback: login dari env (dipakai balance.yml yang tidak punya sesi)
    if not sid:
        email = os.environ.get("CF_EMAIL", "")
        password = os.environ.get("CF_PASSWORD", "")
        if email and password:
            sid = cf_login(email, password)
            if sid and os.path.isfile(cfg_path):
                cfg["phpsessid"] = sid
                try:
                    json.dump(cfg, open(cfg_path, "w"), indent=2)
                except Exception:
                    pass
    if not sid:
        return "🎣 CF: (sesi kosong — belum login)"
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": UA,
            "Accept": "application/json",
            "Origin": "https://cryptofisher.online",
            "Referer": "https://cryptofisher.online/",
        }
    )
    s.cookies.set("PHPSESSID", sid, domain="cryptofisher.online")
    r = s.get("https://cryptofisher.online/ajax.php?action=get_state", timeout=25)
    st = r.json() if "json" in r.headers.get("Content-Type", "") else {}
    err = st.get("error") or ""
    if st.get("success") is False or (err and not st.get("balances")):
        # sesi mati → coba login sekali
        email = os.environ.get("CF_EMAIL", "")
        password = os.environ.get("CF_PASSWORD", "")
        if email and password:
            sid2 = cf_login(email, password)
            if sid2:
                s.cookies.set("PHPSESSID", sid2, domain="cryptofisher.online")
                r = s.get(
                    "https://cryptofisher.online/ajax.php?action=get_state",
                    timeout=25,
                )
                st = (
                    r.json()
                    if "json" in r.headers.get("Content-Type", "")
                    else {}
                )
                if os.path.isfile(cfg_path):
                    cfg["phpsessid"] = sid2
                    try:
                        json.dump(cfg, open(cfg_path, "w"), indent=2)
                    except Exception:
                        pass
            else:
                return f"🎣 CF: login gagal ({err or 'unknown'})"
        else:
            return f"🎣 CF: sesi mati ({err})"
    bals = st.get("balances") or {}
    lv = st.get("level") or st.get("userLevel") or "?"
    exp = st.get("exp") or st.get("experience") or 0
    usdt = _fmt(bals.get("USDT") or 0, 8)
    btc = _fmt(bals.get("BTC") or 0, 8)
    hp = st.get("hp") or st.get("health") or "?"
    return f"🎣 CF: USDT {usdt} · BTC {btc} · lv{lv} exp {exp} · hp {hp}"


def ctd_balance(cookie_path: str) -> str:
    if not os.path.isfile(cookie_path):
        return "🛡️ CTD: (cookie tidak ada)"
    cookie = open(cookie_path).read().strip()
    if not cookie:
        return "🛡️ CTD: (cookie kosong)"
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": UA,
            "Accept": "application/json",
            "Origin": "https://cryptotowerdefense.com",
            "Referer": "https://cryptotowerdefense.com/",
            "x-ctd-client-version": "0.19.0",
            "Cookie": cookie,
        }
    )
    r = s.get("https://cryptotowerdefense.com/api/bootstrap", timeout=25)
    try:
        b = r.json()
    except Exception:
        return "🛡️ CTD: respons bukan JSON"
    if b.get("error") or b.get("code") == "unauthorized":
        return "🛡️ CTD: sesi mati (cookie expired)"
    player = b.get("player") or {}
    coins = _fmt(player.get("coins") or 0, 0)
    ident = s.get(
        "https://cryptotowerdefense.com/api/session/identity", timeout=20
    )
    pid = ""
    try:
        pid = (ident.json() or {}).get("profileId", "")[:8]
    except Exception:
        pass
    return f"🛡️ CTD: {coins} koin · akun …{pid}" if pid else f"🛡️ CTD: {coins} koin"


def lm_balance(cfg_path: str) -> str:
    if not os.path.isfile(cfg_path):
        return "⛏️ LM: (config tidak ada)"
    cfg = json.load(open(cfg_path))
    sess = cfg.get("lm_session") or ""
    if not sess:
        return "⛏️ LM: (sesi kosong — belum login)"
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "application/json"})
    s.cookies.set("lm_session", sess, domain="lightningminer.com")
    r = s.get("https://lightningminer.com/api/me", timeout=25)
    try:
        d = r.json()
    except Exception:
        return "⛏️ LM: respons bukan JSON"
    if not d.get("ok", True) and d.get("error"):
        return f"⛏️ LM: sesi mati ({d.get('error')})"
    u = d.get("user") or d
    coins = _fmt(u.get("coins") or 0, 2)
    settled = _fmt((u.get("settledCryptoBalanceAtomic") or 0) / 1e8, 8)
    power = _fmt(u.get("miningPower") or 0, 2)
    return f"⛏️ LM: {coins} koin · settled {settled} · power {power}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cf", default="cryptofisher/cf_config.json")
    ap.add_argument("--ctd", default="cryptotowerdefense/ctd_cookie.txt")
    ap.add_argument("--lm", default="lightningminer/lm_config.json")
    args = ap.parse_args()

    lines = []
    for fn, path in (
        (cf_balance, args.cf),
        (ctd_balance, args.ctd),
        (lm_balance, args.lm),
    ):
        try:
            lines.append(fn(path))
        except Exception as e:
            lines.append(f"{fn.__name__}: error {e}")
    text = "\n".join(lines)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
