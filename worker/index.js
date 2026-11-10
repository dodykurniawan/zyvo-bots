// Cloudflare Worker — Telegram webhook /balance instan (tanpa cron GitHub)
// Deploy: wrangler deploy  ·  Secret: wrangler secret put <NAME>
// setWebhook sekali setelah deploy (lihat scripts/deploy_worker.sh)

const CMDS = new Set(["/balance", "/bal", "/saldo", "/start"]);
const UA =
  "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36";

async function tg(method, token, params) {
  const r = await fetch(`https://api.telegram.org/bot${token}/${method}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(params),
  });
  const j = await r.json();
  if (!j.ok) throw new Error(`TG ${method}: ${j.description}`);
  return j;
}

function fmt(x, nd = 8) {
  const v = Number(x);
  if (!Number.isFinite(v)) return String(x ?? "");
  if (Number.isInteger(v) && Math.abs(v) >= 100) return String(v);
  return v.toFixed(nd).replace(/0+$/, "").replace(/\.$/, "");
}

async function cfLogin(email, password) {
  const body = new URLSearchParams({
    action: "auth_login",
    email,
    password,
    "h-captcha-response": "00000000-0000-0000-0000-000000000000",
  });
  const r = await fetch("https://cryptofisher.online/ajax.php", {
    method: "POST",
    headers: {
      "user-agent": UA,
      accept: "application/json",
      "content-type": "application/x-www-form-urlencoded",
      origin: "https://cryptofisher.online",
      referer: "https://cryptofisher.online/",
    },
    body,
  });
  const setCookie = r.headers.get("set-cookie") || "";
  const m = setCookie.match(/PHPSESSID=([^;]+)/);
  if (m) return m[1];
  try {
    const j = await r.json();
    // fallback: beberapa deploy kirim sid di body
    return j.phpssid || j.session || "";
  } catch {
    return "";
  }
}

async function cfBalance(sid) {
  const r = await fetch(
    "https://cryptofisher.online/ajax.php?action=get_state",
    {
      headers: {
        "user-agent": UA,
        accept: "application/json",
        cookie: `PHPSESSID=${sid}`,
        referer: "https://cryptofisher.online/",
      },
    },
  );
  const j = await r.json();
  const st = j.state || j;
  const p = st.player || st.profile || st;
  const usdt = st.usdt ?? p.usdt ?? st.balanceUsdt ?? 0;
  const btc = st.btc ?? p.btc ?? 0;
  const lv = st.level ?? p.level ?? "?";
  const exp = st.exp ?? p.exp ?? 0;
  const hp = st.hp ?? p.hp ?? "?";
  return `🎣 CF: USDT ${fmt(usdt)} · BTC ${fmt(btc)} · lv${lv} exp ${fmt(exp, 0)} · hp ${fmt(hp, 0)}`;
}

async function ctdBalance(cookie) {
  const h = {
    "user-agent": UA,
    accept: "application/json",
    cookie,
    "x-ctd-client-version": "0.19.0",
    referer: "https://cryptotowerdefense.com/",
  };
  const r = await fetch("https://cryptotowerdefense.com/api/bootstrap", {
    headers: h,
  });
  let b;
  try {
    b = await r.json();
  } catch {
    return "🛡️ CTD: respons bukan JSON";
  }
  if (b.error || b.code === "unauthorized")
    return "🛡️ CTD: sesi mati (cookie expired)";
  const coins = fmt(b.player?.coins ?? 0, 0);
  let pid = "";
  try {
    const ident = await fetch(
      "https://cryptotowerdefense.com/api/session/identity",
      { headers: h },
    );
    pid = ((await ident.json())?.profileId || "").slice(0, 8);
  } catch {}
  return pid
    ? `🛡️ CTD: ${coins} koin · akun …${pid}`
    : `🛡️ CTD: ${coins} koin`;
}

async function lmBalance(session) {
  const r = await fetch("https://lightningminer.com/api/me", {
    headers: {
      "user-agent": UA,
      accept: "application/json",
      cookie: `lm_session=${session}`,
    },
  });
  let d;
  try {
    d = await r.json();
  } catch {
    return "⛏️ LM: respons bukan JSON";
  }
  if (d.ok === false && d.error) return `⛏️ LM: sesi mati (${d.error})`;
  const u = d.user || d;
  const coins = fmt(u.coins ?? 0, 2);
  const settled = fmt((u.settledCryptoBalanceAtomic ?? 0) / 1e8, 8);
  const power = fmt(u.miningPower ?? 0, 2);
  return `⛏️ LM: ${coins} koin · settled ${settled} · power ${power}`;
}

async function fetchBalances(env) {
  const out = [];
  try {
    let sid = "";
    if (env.CF_PHPSESSID) sid = env.CF_PHPSESSID;
    else if (env.CF_EMAIL && env.CF_PASSWORD)
      sid = await cfLogin(env.CF_EMAIL, env.CF_PASSWORD);
    out.push(sid ? await cfBalance(sid) : "🎣 CF: (tidak ada kredensial)");
  } catch (e) {
    out.push(`🎣 CF: error ${e.message}`);
  }
  try {
    out.push(
      env.CTD_COOKIE
        ? await ctdBalance(env.CTD_COOKIE)
        : "🛡️ CTD: (cookie tidak ada)",
    );
  } catch (e) {
    out.push(`🛡️ CTD: error ${e.message}`);
  }
  try {
    out.push(
      env.LM_SESSION
        ? await lmBalance(env.LM_SESSION)
        : "⛏️ LM: (session tidak ada)",
    );
  } catch (e) {
    out.push(`⛏️ LM: error ${e.message}`);
  }
  return out.join("\n");
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // health
    if (request.method === "GET" && url.pathname === "/health")
      return new Response("ok", { status: 200 });

    // webhook
    if (request.method === "POST" && url.pathname === "/telegram") {
      // verifikasi secret header dari setWebhook(secret_token=...)
      const got = request.headers.get("x-telegram-bot-api-secret-token");
      if (env.WEBHOOK_SECRET && got !== env.WEBHOOK_SECRET)
        return new Response("forbidden", { status: 403 });

      let update;
      try {
        update = await request.json();
      } catch {
        return new Response("bad json", { status: 400 });
      }
      const msg = update.message || update.edited_message;
      if (!msg || !msg.text) return new Response("ok", { status: 200 });

      const chatId = String(msg.chat.id);
      if (env.TG_CHAT_ID && chatId !== env.TG_CHAT_ID)
        return new Response("ok", { status: 200 });

      const cmd = msg.text.trim().split(/\s+/)[0].toLowerCase();
      if (!CMDS.has(cmd)) return new Response("ok", { status: 200 });

      const bal = await fetchBalances(env);
      const head =
        cmd === "/start"
          ? "👋 halo! Balas /balance utk cek saldo.\n"
          : "💰 Saldo akun kamu:\n";
      try {
        await tg("sendMessage", env.TG_BOT_TOKEN, {
          chat_id: chatId,
          text: head + bal,
        });
      } catch (e) {
        return new Response(e.message, { status: 500 });
      }
      return new Response("ok", { status: 200 });
    }

    return new Response("not found", { status: 404 });
  },
};
