#!/usr/bin/env node
// ctd_run_bot.mjs — auto-run campaign CryptoTowerDefense
// Pakai mesin game ASLI (game-engine.js) supaya log aksi valid saat server replay.
// Pemakaian:  node ctd_run_bot.mjs [--level N] [--once] [--max N] [TICK_MS env]
import fs from 'node:fs';
import crypto from 'node:crypto';
import { createGame, stepGame, applyAction, TOWER_DEFS, getUpgradeChoices, getUpgradeCost } from './game-engine.js';
import { getPlacementValidity } from './terrain-placement.js';
import { BattleSession } from './battle-session.js';

const BASE = 'https://cryptotowerdefense.com';
const UA = 'Mozilla/5.0 (Linux; Android 14) Chrome/120';
const COOKIE = fs.readFileSync(new URL('./ctd_cookie.txt', import.meta.url), 'utf8').trim();
const LMCFG = JSON.parse(fs.readFileSync(
  process.env.LM_CONFIG_PATH || new URL('../lightningminer/lm_config.json', import.meta.url),
  'utf8'));
let csrf = null;
let tickMs = Number(process.env.TICK_MS || 25); // default 4× (client punya tombol speed — server menerima tick percepat)
const args = process.argv.slice(2);
const argNum = (k, d) => { const i = args.indexOf(k); return i >= 0 ? Number(args[i + 1]) : d; };
const START_LEVEL = argNum('--level', 0);
const MAX_RUNS = args.includes('--once') ? 1 : argNum('--max', 6);

const log = (m) => console.log(`[${new Date().toISOString().slice(11, 19)}] ${m}`);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function hdr(extra = {}) {
  const h = { 'Cookie': COOKIE, 'User-Agent': UA, 'Accept': 'application/json',
    'Content-Type': 'application/json', 'Origin': BASE, 'Referer': BASE + '/' };
  if (csrf) h['x-csrf-token'] = csrf;
  return { ...h, ...extra };
}
async function GET(path) {
  const r = await fetch(BASE + path, { headers: hdr(), redirect: 'manual' });
  const j = await r.json().catch(() => null);
  if (!r.ok) throw new Error(`GET ${path} ${r.status} ${JSON.stringify(j).slice(0, 200)}`);
  return j;
}
async function POST(path, body) {
  const r = await fetch(BASE + path, { method: 'POST', headers: hdr(), body: JSON.stringify(body) });
  const j = await r.json().catch(() => null);
  if (j && j.csrfToken) csrf = j.csrfToken;
  if (r.status === 428 && j && (j.code === 'HUMAN_VERIFICATION_REQUIRED' || j.code === 'HUMAN_REQUIRED')) {
    if (globalThis.__verifying) { const e = new Error('HUMAN_VERIFICATION_REQUIRED (lagi verify)'); e.status = 428; throw e; }
    globalThis.__verifying = true;
    try { log('server minta verifikasi segar → ensureHuman…'); await ensureHuman(); }
    finally { globalThis.__verifying = false; }
    const r2 = await fetch(BASE + path, { method: 'POST', headers: hdr(), body: JSON.stringify(body) });
    const j2 = await r2.json().catch(() => null);
    if (j2 && j2.csrfToken) csrf = j2.csrfToken;
    if (!r2.ok) { const e = new Error(`POST ${path} ${r2.status} ${JSON.stringify(j2).slice(0, 300)}`); e.status = r2.status; e.body = j2; throw e; }
    return j2;
  }
  if (!r.ok) { const e = new Error(`POST ${path} ${r.status} ${JSON.stringify(j).slice(0, 300)}`); e.status = r.status; e.body = j; throw e; }
  return j;
}

// ---------- Verifikasi Turnstile (xsolve → peak, sama seperti client ensureHuman) ----------
async function solveXsolve(siteKey, action, cdata) {
  const key = LMCFG.xsolve_key; if (!key) throw new Error('xsolve key kosong');
  const t = await (await fetch('https://api.xsolve.me/task', {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Api-Key': key },
    body: JSON.stringify({ mode: 'turnstile', url: BASE + '/', sitekey: siteKey, action, cdata }),
  })).json();
  if (t.token) return t.token;
  const tid = t.taskId || t.task_id; if (!tid) throw new Error('xsolve: ' + JSON.stringify(t).slice(0, 180));
  for (let i = 0; i < 30; i++) {
    await sleep(3000);
    const p = await (await fetch('https://api.xsolve.me/getTaskResult', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ clientKey: key, taskId: tid }),
    })).json();
    if (['ready', 'success', 'completed'].includes(p.status)) {
      const tok = (p.solution || {}).token || ''; if (tok) return tok;
    }
    if (p.status === 'error') throw new Error('xsolve: ' + (p.message || '').slice(0, 160));
  }
  throw new Error('xsolve timeout');
}
async function solvePeak(siteKey, action, cdata) {
  const key = LMCFG.peak_key; if (!key) throw new Error('peak key kosong');
  const r = await (await fetch('https://api.peak.fo/solve', {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-API-Key': key },
    body: JSON.stringify({ task_type: 'turnstiletaskproxyless', url: BASE + '/', sitekey: siteKey, action, cdata }),
  })).json();
  if (!r.success) throw new Error('peak: ' + JSON.stringify(r).slice(0, 160));
  const tok = (r.data || {}).token; if (!tok) throw new Error('peak tanpa token');
  return tok;
}
async function ensureHuman(purpose = 'play') {
  const status = await GET('/api/security/status');
  if (Number(status.verifiedUntil) > Date.now() + 5000) return status;
  const ch = await GET('/api/security/challenge?purpose=' + encodeURIComponent(purpose));
  if (!ch.siteKey || !ch.challengeId) throw new Error('challenge tidak tersedia');
  const action = ch.action || purpose, cdata = ch.cData || ch.challengeId;
  let tok, via;
  try { tok = await solveXsolve(ch.siteKey, action, cdata); via = 'xsolve'; }
  catch (e) { log(`xsolve gagal (${e.message}) → coba peak`); tok = await solvePeak(ch.siteKey, action, cdata); via = 'peak'; }
  const v = await POST('/api/security/verify', { purpose, challengeId: ch.challengeId, turnstileToken: tok });
  log(`verify OK via ${via}`);
  return v;
}

// ---------- AI ----------
function distToPolyline(x, y, pts) {
  let best = Infinity;
  for (let i = 0; i < pts.length - 1; i++) {
    const a = pts[i], b = pts[i + 1];
    const dx = b.x - a.x, dy = b.y - a.y;
    const len2 = dx * dx + dy * dy || 1;
    let t = ((x - a.x) * dx + (y - a.y) * dy) / len2;
    t = Math.max(0, Math.min(1, t));
    const px = a.x + t * dx, py = a.y + t * dy;
    const d = Math.hypot(x - px, y - py);
    if (d < best) best = d;
  }
  return best;
}
function makeCandidates(game) {
  const path = game.pathPoints;
  // Battle LEGACY (mapLayoutVersion < 4): engine hanya menerima build di pad
  // bawaan peta ({pad}); build bebas {x,y} ditolak (maskFor null → invalid).
  if (!(game.mapLayoutVersion >= 4)) {
    const out = game.padPositions.map((p, i) => ({ pad: i, x: p.x, y: p.y, d: distToPolyline(p.x, p.y, path) }));
    out.sort((a, b) => a.d - b.d);
    return out;
  }
  const xs = path.map((p) => p.x), ys = path.map((p) => p.y);
  const x0 = Math.min(...xs) - 140, x1 = Math.max(...xs) + 140;
  const y0 = Math.min(...ys) - 140, y1 = Math.max(...ys) + 140;
  const lvl = game.mapLevel ?? game.level;
  const out = [];
  for (let x = x0; x <= x1; x += 10) for (let y = y0; y <= y1; y += 10) {
    if (!Number.isInteger(x) || !Number.isInteger(y)) continue;
    const v = getPlacementValidity(lvl, x, y, [], game.mapLayoutVersion);
    if (v.valid) out.push({ x, y, d: distToPolyline(x, y, path) });
  }
  out.sort((a, b) => a.d - b.d);
  return out;
}
const dpsPerCost = (t) => { const d = TOWER_DEFS[t]; return (d.damage / d.cooldown) / d.cost; };

function ai(game, cands) {
  const acts = [];
  const legacy = !(game.mapLayoutVersion >= 4);
  const owned = [...new Set(game.roster.map((t) => t.type))].filter((t) => TOWER_DEFS[t]);
  const affordable = owned.filter((t) => game.energy >= TOWER_DEFS[t].cost);

  // BUILD — paling dekat ke jalur musuh, DPS/cost terbaik
  const reserveAfter2 = 80;
  if (affordable.length && game.towers.length < 20) {
    const type = affordable.sort((a, b) => dpsPerCost(b) - dpsPerCost(a))[0];
    const range = TOWER_DEFS[type].range;
    for (const c of cands) {
      if (c.d > range * 0.98) break; // sudah terurut menaik — sisanya terlalu jauh
      if (legacy) {
        if (game.towers.some((t) => t.pad === c.pad)) continue;
      } else {
        if (game.towers.some((t) => { const p = game.padPositions[t.pad]; return Math.hypot(p.x - c.x, p.y - c.y) < 48; })) continue;
      }
      if (game.towers.length >= 2 && game.energy - TOWER_DEFS[type].cost < reserveAfter2 && game.towers.length < 4) continue;
      const act = legacy
        ? { type: 'build', tower: type, pad: c.pad, tick: game.tick }
        : { type: 'build', tower: type, x: c.x, y: c.y, tick: game.tick };
      if (applyAction(game, act)) { acts.push(act); break; }
    }
  }
  // UPGRADE — termurah dulu, jangan habiskan energy kalau tower masih < 4
  if (game.towers.length >= 2) {
    const keep = game.towers.length < 4 ? 80 : 0;
    const options = [];
    for (const t of game.towers) for (const ch of getUpgradeChoices(game, t)) {
      if (ch && ch.affordable && ch.cost != null && ch.nextTier != null && game.energy - ch.cost >= keep)
        options.push({ t, ch });
    }
    options.sort((a, b) => a.ch.cost - b.ch.cost);
    for (const o of options.slice(0, 2)) {
      const act = { type: 'upgrade', pad: o.t.pad, path: o.ch.path, tick: game.tick };
      if (applyAction(game, act)) { acts.push(act); break; }
    }
    // Engine lama (tanpa jalur upgrade) — getUpgradeChoices=[] → upgrade polos {pad}
    if (!acts.some((a) => a.type === 'upgrade')) {
      for (const t of game.towers) {
        const cost = getUpgradeCost(t);
        if (cost == null || game.energy - cost < keep) continue;
        const act = { type: 'upgrade', pad: t.pad, tick: game.tick };
        if (applyAction(game, act)) { acts.push(act); break; }
      }
    }
  }
  // RUSH — wave berikutnya masih jauh & musuh di layar habis → bonus orbs
  const next = game.spawnPlan[game.spawnCursor];
  if (next && game.enemies.length === 0 && next.tick - game.tick >= 90 && game.towers.length >= 2) {
    const act = { type: 'rush', tick: game.tick };
    if (applyAction(game, act)) acts.push(act);
  }
  return acts;
}

// ---------- Run satu level ----------
async function playLevel(level) {
  const b0 = await GET('/api/bootstrap');
  csrf = b0.csrfToken || csrf;
  try {
    const v = await ensureHuman('play');
    log(`verifikasi ok (verifiedUntil=${new Date(Number(v.verifiedUntil || 0)).toISOString().slice(11, 19)}Z)`);
  } catch (e) {
    log(`verifikasi gagal: ${e.message} — jendela belum aktif, coba lagi nanti`);
    return 'wait';
  }

  const started = await POST('/api/run/start', {
    mode: 'campaign', level, towerTypes: ['arc', 'pulse'], supportsResume: true,
    operationId: crypto.randomUUID(),
  });
  log(`run mulai: level ${level} runId=${started.runId} seed=${started.seed} mode=${started.context?.mode} mapLayV=${started.context?.mapLayoutVersion}`);
  const game = createGame(started.seed, started.context);
  const cands = makeCandidates(game);
  log(`kandidat bangun: ${cands.length} titik | orbs awal=${game.energy} lives=${game.lives} waves=${game.totalWaves}`);

  const sess = new BattleSession(async (path, payload) => POST(path, payload));
  sess.begin(started);

  let built = 0, finished = null;
  // Battle non-modern (rulesVersion !== 2): TANPA checkpoint sama sekali —
  // klien asli juga melewati checkpointBattle utk mode ini (ctd_app.js:695).
  let noCheckpoint = started.context?.rulesVersion !== 2;
  const runStartWall = Date.now();
  while (!game.ended) {
    for (const a of ai(game, cands)) { sess.actions.push(a); if (a.type === 'build') built++; }
    stepGame(game);
    if (game.tick % 100 === 0) log(`tick ${game.tick}/${game.maxTicks} wave ${game.wave}/${game.totalWaves} energy ${game.energy} lives ${game.lives} towers ${game.towers.length}${game.enemies.length ? ` musuh ${game.enemies.length}` : ''}`);
    if (!noCheckpoint && game.tick - sess.verifiedTick >= 300 && !sess.busy) {
      try {
        const ack = await sess.flush(game.tick);
        if (ack) log(`checkpoint OK → verifiedTick=${ack.verifiedTick}`);
      } catch (e) {
        if (/acknowledgement did not match/.test(e.message)) {
          // server replay realtime → sinkronkan wall-clock ke tick yang dikirim
          tickMs = 100;
          const need = runStartWall + (sess.pending?.payload?.endTick ?? 0) * 100 - Date.now();
          if (need > 0) { log(`server minta realtime — tunggu ${(need / 1000).toFixed(1)}s lalu ulang checkpoint`); await sleep(need); }
          try { const ack2 = await sess.flush(game.tick); if (ack2) log(`checkpoint OK → verifiedTick=${ack2.verifiedTick}`); }
          catch (e2) { log(`checkpoint ulang gagal: ${e2.message}`); }
        } else if (/does not support checkpoints/.test(e.message)) {
          noCheckpoint = true;
          log('server: defense ini tanpa checkpoint — percobaan checkpoint dihentikan');
        } else log(`checkpoint ditunda: ${e.message}`);
        if (!noCheckpoint) await sleep(2000);
      }
    }
    await sleep(tickMs);
  }
  log(`game selesai: victory=${game.victory} retired=${!!game.retired} score=${game.score} waves=${game.wave} ticks=${game.tick}`);
  const isModern = started.context?.rulesVersion === 2;
  if (isModern && sess.pending && !sess.pending.finish) sess.pending = null;
  if (!isModern) {
    // Klien asli utk battle non-modern (ctd_app.js:718): {runId, actions} saja.
    // Server menahan finish dengan 425 sampai level berakhir di sisi server →
    // retry sabar; payload actions = SEMUA aksi battle (belum pernah terkirim).
    const body = { runId: started.runId, actions: sess.actions };
    for (let i = 1; i <= 15 && !finished; i++) {
      try {
        finished = await POST('/api/run/finish', body);
        log(`SETTLE OK: ${JSON.stringify(finished).slice(0, 300)}`);
      } catch (e) {
        if (e.status === 425) { log(`finish ditahan server 425 (${i}/15) — level server belum berakhir, tunggu 20s`); await sleep(20000); }
        else if (e.status === 409 && /no longer be settled/i.test(e.message)) {
          // terminal: run sudah di-settle/diambil alih server — retry sia-sia
          log('server: run ini sudah tidak bisa di-settle lagi (409) — hentikan retry, cek balance/level di log berikutnya');
          break;
        }
        else { log(`finish gagal: ${e.message}`); await sleep(5000); }
      }
    }
  } else {
    try {
      finished = await sess.flush(game.tick, { finish: true });
      if (finished) log(`SETTLE OK: ${JSON.stringify(finished).slice(0, 300)}`);
    } catch (e) {
      log(`finish gagal (${e.message}) — retry 3×`);
      for (let i = 0; i < 3 && !finished; i++) { await sleep(4000); try { finished = await sess.flush(game.tick, { finish: true }); log(`SETTLE OK: ${JSON.stringify(finished).slice(0, 300)}`); } catch (e2) { log(`  retry: ${e2.message}`); } }
    }
  }
  if (finished) {
    const rw = finished.reward || {};
    log(`SETTLE: result=${finished.result?.victory ? 'VICTORY' : finished.result?.retired ? 'RETIRED' : 'DEFEAT'} reward.coins=${rw.coins ?? '-'} reward.shares=${rw.shares ?? '-'} | ${finished.message || ''}`);
    if (finished.poolClosed) log('poolClosed — run diakhiri pool');
  } else log('SETTLE GAGAL — tanpa hadiah, lanjut run berikutnya');
  return finished;
}

// ---------- Main ----------
let runs = 0;
while (runs < MAX_RUNS) {
  const b = await GET('/api/bootstrap');
  csrf = b.csrfToken || csrf;
  const levels = (b.campaign?.levels || []).filter((l) => l.unlocked && !l.cleared);
  if (START_LEVEL && runs === 0) {
    const t = (b.campaign?.levels || []).find((l) => l.id === START_LEVEL);
    if (t && !t.cleared) levels.unshift(t);
  }
  if (!levels.length) { log('tidak ada level campaign terbuka yang belum clear — selesai'); break; }
  const lv = levels[0];
  log(`=== main level ${lv.id} "${lv.name}" (${lv.waves} wave, firstClear ${lv.firstClearCoins} coins) ===`);
  const res = await playLevel(lv.id);
  if (res === 'wait') { await sleep(60_000); continue; }
  runs++;
  if (res && res.result && res.result.victory === false && !res.result?.retired) {
    log('kalah — berhenti dulu supaya tidak bakal percobaan sia-sia'); break;
  }
  if (runs < MAX_RUNS) await sleep(3000);
}
log(`selesai ${runs} run.`);
