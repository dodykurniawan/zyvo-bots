import { TOWER_CATALOG, RARITIES, getLevel, getMapLevel, getCampaignLevel, getCampaignLevels, createStarterContext } from './game-data.js';
import { MAP_LAYOUT_VERSION, PLACEMENT_PADS, PLACEMENT_PATHS, PREVIOUS_PLACEMENT_PADS, VERSION_THREE_PLACEMENT_PADS, VERSION_THREE_PLACEMENT_PATHS, VERSION_FOUR_PLACEMENT_PADS, VERSION_FOUR_PLACEMENT_PATHS, VERSION_FIVE_PLACEMENT_PADS, VERSION_FIVE_PLACEMENT_PATHS } from './map-layout.js';
import { getPlacementValidity } from './terrain-placement.js';
import { MODE_RULES_VERSION, MAX_MODERN_TOWER_LEVEL, MAX_CAMPAIGN_BONUS_BPS } from './mode-rules.js';
import { initializeBoss, advanceBosses, getBossDamageMultiplier, getBossMovementMultiplier, getCampaignBoss, CAMPAIGN_BOSS_ENGINE_VERSION } from './boss-rules.js';
import {INVADER_DEFS,invaderBehaviorActive,pickCampaignInvader} from './invader-rules.js';
import {EMPTY_UPGRADE_TIERS,UPGRADE_PATHS,UPGRADE_PATH_ENGINE_VERSION,THEMED_UPGRADE_ENGINE_VERSION,getPathChoice,pathTowerModifiers,validUpgradeTiers} from './tower-upgrade-paths.js';
export {CAMPAIGN_INVADER_IDS,INVADER_DEFS,pickCampaignInvader,invaderBehaviorActive} from './invader-rules.js';
export {UPGRADE_PATH_ENGINE_VERSION,THEMED_UPGRADE_ENGINE_VERSION} from './tower-upgrade-paths.js';

export const ENGINE_VERSION = THEMED_UPGRADE_ENGINE_VERSION;
export const SUPPORTED_ENGINE_VERSIONS = Object.freeze([1,2,3,4,5,UPGRADE_PATH_ENGINE_VERSION,ENGINE_VERSION]);
export const TICK_MS = 100;
export const MAX_TICKS = 9000;
export const MAX_ACTIONS = 400;
export const MAX_ACTIVE_TOWERS = 40;
export const MAX_REPLAY_CHUNK_TICKS = 1200;
export const TOWER_DEFS = TOWER_CATALOG;

// Visual observers live outside replay state. Server verification and saved
// battles never acquire rendering data or depend on a renderer being present.
const damageObservers = new WeakMap();
export function observeDamage(state, listener) {
  if (!state || typeof state !== 'object' || typeof listener !== 'function') throw new TypeError('A battle and damage listener are required.');
  let listeners = damageObservers.get(state);
  if (!listeners) { listeners = new Set(); damageObservers.set(state, listeners); }
  listeners.add(listener);
  return () => { listeners.delete(listener); if (!listeners.size) damageObservers.delete(state); };
}
function reportDamage(state, enemy, previousHp, kind = 'hit') {
  const listeners = state && damageObservers.get(state);
  if (!listeners?.size) return;
  const amount = Math.max(0, Math.min(Math.max(0, previousHp), previousHp - enemy.hp));
  if (!Number.isFinite(amount) || amount <= 0) return;
  const position = pointOnPath(enemy.progress, state);
  const event = Object.freeze({ enemyId: enemy.id, kind, amount, x: position.x, y: position.y, tick: state.tick });
  for (const listener of listeners) {
    try { listener(event); } catch { /* A visual effect cannot interrupt combat. */ }
  }
}

const MAPS = Object.freeze([
  { name: 'Genesis Gardens', path: [
    { x: -30, y: 96 }, { x: 180, y: 96 }, { x: 180, y: 236 }, { x: 402, y: 236 },
    { x: 402, y: 88 }, { x: 650, y: 88 }, { x: 650, y: 352 }, { x: 846, y: 352 }, { x: 846, y: 474 }, { x: 1010, y: 474 }
  ], pads: [
    { x: 92, y: 176 }, { x: 274, y: 126 }, { x: 294, y: 320 }, { x: 482, y: 164 },
    { x: 538, y: 326 }, { x: 724, y: 180 }, { x: 746, y: 438 }, { x: 902, y: 278 },
    { x: 535, y: 55 }, { x: 777, y: 282 }, { x: 96, y: 298 }, { x: 546, y: 435 }
  ] },
  { name: 'Neon Crossing', path: [
    { x: -30, y: 274 }, { x: 150, y: 274 }, { x: 150, y: 102 }, { x: 382, y: 102 },
    { x: 382, y: 420 }, { x: 620, y: 420 }, { x: 620, y: 188 }, { x: 830, y: 188 }, { x: 830, y: 380 }, { x: 1010, y: 380 }
  ], pads: [
    { x: 76, y: 190 }, { x: 240, y: 185 }, { x: 300, y: 336 }, { x: 470, y: 200 },
    { x: 510, y: 330 }, { x: 705, y: 290 }, { x: 744, y: 458 }, { x: 900, y: 264 },
    { x: 510, y: 98 }, { x: 735, y: 105 }, { x: 213, y: 400 }, { x: 95, y: 372 }
  ] },
  { name: 'Ember Circuit', path: [
    { x: -30, y: 128 }, { x: 256, y: 128 }, { x: 256, y: 360 }, { x: 455, y: 360 },
    { x: 455, y: 178 }, { x: 728, y: 178 }, { x: 728, y: 430 }, { x: 894, y: 430 }, { x: 894, y: 286 }, { x: 1010, y: 286 }
  ], pads: [
    { x: 112, y: 210 }, { x: 340, y: 216 }, { x: 342, y: 438 }, { x: 538, y: 268 },
    { x: 630, y: 350 }, { x: 810, y: 268 }, { x: 810, y: 498 }, { x: 932, y: 179 },
    { x: 620, y: 94 }, { x: 156, y: 360 }, { x: 450, y: 88 }, { x: 525, y: 450 }
  ] },
  { name: 'Obsidian Vault', path: [
    { x: -30, y: 402 }, { x: 172, y: 402 }, { x: 172, y: 124 }, { x: 420, y: 124 },
    { x: 420, y: 320 }, { x: 650, y: 320 }, { x: 650, y: 94 }, { x: 846, y: 94 }, { x: 846, y: 442 }, { x: 1010, y: 442 }
  ], pads: [
    { x: 94, y: 302 }, { x: 264, y: 230 }, { x: 320, y: 410 }, { x: 509, y: 211 },
    { x: 546, y: 411 }, { x: 739, y: 220 }, { x: 758, y: 410 }, { x: 919, y: 313 },
    { x: 540, y: 82 }, { x: 927, y: 114 }, { x: 273, y: 54 }, { x: 70, y: 120 }
  ] }
]);
export const PATH_POINTS = MAPS[0].path;
// Missing versions in historical battle snapshots retain the original slots.
// New battles pin their layout, so visual corrections cannot change a replay.
const CURRENT_MAPS = Object.freeze(getCampaignLevels(6).filter((level,index)=>index%5===0).map((level,index)=>Object.freeze({name:level.sector,pads:PLACEMENT_PADS[index],path:PLACEMENT_PATHS[index]})));
const PREVIOUS_MAPS = Object.freeze(MAPS.map((map, index) => Object.freeze({ ...map, pads: PREVIOUS_PLACEMENT_PADS[index] })));
const VERSION_THREE_MAPS = Object.freeze(MAPS.map((map, index) => Object.freeze({ ...map, pads: VERSION_THREE_PLACEMENT_PADS[index], path: VERSION_THREE_PLACEMENT_PATHS[index] })));
const VERSION_FOUR_MAPS = Object.freeze(MAPS.map((map, index) => Object.freeze({ ...map, pads: VERSION_FOUR_PLACEMENT_PADS[index], path: VERSION_FOUR_PLACEMENT_PATHS[index] })));
const VERSION_FIVE_MAPS = Object.freeze(MAPS.map((map,index)=>Object.freeze({...map,pads:VERSION_FIVE_PLACEMENT_PADS[index],path:VERSION_FIVE_PLACEMENT_PATHS[index]})));
export const PAD_POSITIONS = CURRENT_MAPS[0].pads;
export function getMap(level = 1, mapLayoutVersion = MAP_LAYOUT_VERSION) {
  if (![1, 2, 3, 4, 5, 6].includes(mapLayoutVersion)) throw new Error('Invalid map layout version.');
  if(mapLayoutVersion>=6){
    const definition=getMapLevel(level,mapLayoutVersion);
    if(!definition)throw new Error('Invalid map level.');
    return CURRENT_MAPS[definition.map];
  }
  return (mapLayoutVersion === 1 ? MAPS : mapLayoutVersion === 2 ? PREVIOUS_MAPS : mapLayoutVersion === 3 ? VERSION_THREE_MAPS : mapLayoutVersion === 4 ? VERSION_FOUR_MAPS : VERSION_FIVE_MAPS)[(getLevel(level) || getLevel(1)).map];
}

function pathGeometry(points) {
  const segments = []; let length = 0;
  for (let index = 1; index < points.length; index += 1) {
    const from = points[index - 1]; const to = points[index];
    const segmentLength = Math.hypot(to.x - from.x, to.y - from.y);
    segments.push({ from, to, start: length, length: segmentLength }); length += segmentLength;
  }
  return { segments, length };
}
const DEFAULT_GEOMETRY = pathGeometry(PATH_POINTS);
export const PATH_LENGTH = DEFAULT_GEOMETRY.length;

export const ENEMY_DEFS = Object.freeze({
  bot: { name: 'Bit Bot', hp: 52, speed: 4, reward: 11, damage: 1, radius: 10, color: '#ff537e', armor: 0 },
  runner: { name: 'Flash Runner', hp: 39, speed: 6.2, reward: 11, damage: 1, radius: 9, color: '#ffe66b', armor: 0 },
  wraith: { name: 'Gas Wraith', hp: 90, speed: 3.1, reward: 15, damage: 1, radius: 13, color: '#ffbd5c', armor: 0 },
  whale: { name: 'Armored Whale', hp: 216, speed: 2.1, reward: 26, damage: 3, radius: 17, color: '#b887ff', armor: 0.3 },
  splitter: { name: 'Chain Splitter', hp: 112, speed: 3.55, reward: 19, damage: 2, radius: 14, color: '#63f0ad', armor: 0 },
  boss: { name: '51% Attacker', hp: 650, speed: 1.65, reward: 85, damage: 8, radius: 25, color: '#ff3b66', armor: 0.2 },
  ...INVADER_DEFS
});
function xorshift(value) { let next = value | 0; next ^= next << 13; next ^= next >>> 17; next ^= next << 5; return next >>> 0; }
function makeSpawnPlan(seed, level, engineVersion) {
  const mapBoss=engineVersion>=CAMPAIGN_BOSS_ENGINE_VERSION?getCampaignBoss(level.map):null;
  let random = (seed >>> 0) || 0x9e3779b9; const plan = []; let id = 0;
  for (let wave = 1; wave <= level.waves; wave += 1) {
    const start = 80 + (wave - 1) * 220;
    const count = 5 + wave + Math.floor((level.id - 1) / 3);
    const spacing = Math.max(5, 12 - Math.floor(level.id / 5));
    for (let index = 0; index < count; index += 1) {
      random = xorshift(random); const roll = random % 100; let kind = 'bot';
      if (wave >= 2 && roll >= 62) kind = 'wraith';
      if (level.id >= 2 && roll < 15) kind = 'runner';
      if (wave >= 3 && level.id >= 3 && roll >= 82) kind = 'splitter';
      if (wave >= 4 && level.id >= 4 && roll >= 92) kind = 'whale';
      if(mapBoss)kind=pickCampaignInvader(level.map,wave,roll,{spawnIndex:index,spawnCount:count});
      plan.push({ id: `e${id++}`, tick: start + index * spacing, wave, kind });
    }
    if (wave === level.waves || (!mapBoss && level.id >= 10 && wave % 6 === 0)) {
      plan.push({ id: `e${id++}`, tick: start + count * spacing + 8, wave, kind: 'boss', ...(mapBoss?{bossType:mapBoss.id}:{}) });
    }
  }
  return plan.sort((first, second) => first.tick - second.tick || first.wave - second.wave);
}
function queueEndlessWave(state, wave, start) {
  const plan = [], count = Math.min(80, 5 + wave + Math.floor(wave / 3));
  const spacing = Math.max(2, 10 - Math.floor(wave / 8));
  for (let index = 0; index < count; index += 1) {
    state.randomState = xorshift(state.randomState);
    const roll = state.randomState % 100;
    let kind = 'bot';
    if (wave >= 2 && roll < 18) kind = 'runner';
    if (wave >= 3 && roll >= 58) kind = 'wraith';
    if (wave >= 5 && roll >= 78) kind = 'splitter';
    if (wave >= 8 && roll >= 90) kind = 'whale';
    plan.push({ id: `e${state.enemySerial++}`, tick: start + index * spacing, wave, kind });
  }
  if (wave % 5 === 0) plan.push({ id: `e${state.enemySerial++}`, tick: start + count * spacing + 8, wave, kind: 'boss' });
  state.spawnPlan = plan; state.spawnCursor = 0;
}
export function getEndlessWaveDifficulty(wave, mode = 'daily') {
  if (!Number.isSafeInteger(wave) || wave < 1 || !['daily', 'weekly'].includes(mode)) throw new RangeError('Invalid endless wave.');
  // Numeric protection is far beyond playable progression, not a final wave.
  // The queue still advances indefinitely and never awards a victory at a cap.
  return { hpScale: Math.exp(Math.min(460, (wave - 1) * Math.log(1.16))) * (mode === 'weekly' ? 1.2 : 1),
    speedScale: 1 + Math.min(1.3, (wave - 1) * .016), count: Math.min(80, 5 + wave + Math.floor(wave / 3)) };
}
export function pointOnPath(distance, state) {
  const geometry = state?.geometry || DEFAULT_GEOMETRY;
  const clamped = Math.max(0, Math.min(geometry.length, distance));
  // New curved routes have many small segments. Find the first matching end
  // distance without rescanning the entire road for every enemy and tower.
  let segment;
  if(geometry.segments.length>24){
    let low=0,high=geometry.segments.length-1;
    while(low<high){const middle=(low+high)>>1,entry=geometry.segments[middle];if(clamped<=entry.start+entry.length)high=middle;else low=middle+1;}
    segment=geometry.segments[low];
  }else segment=geometry.segments.find((entry)=>clamped<=entry.start+entry.length)||geometry.segments.at(-1);
  const ratio = (clamped - segment.start) / segment.length;
  return { x: segment.from.x + (segment.to.x - segment.from.x) * ratio, y: segment.from.y + (segment.to.y - segment.from.y) * ratio };
}
export function createGame(seed, context = createStarterContext()) {
  // Missing fields belong to published engine-three clients. New behavior is
  // explicitly selected by the server snapshot, never inferred from a date.
  const engineVersion=context.engineVersion===undefined?3:context.engineVersion;
  if(!SUPPORTED_ENGINE_VERSIONS.includes(engineVersion))throw new Error('Invalid battle engine version.');
  const modern = context?.rulesVersion === MODE_RULES_VERSION;
  if (context?.rulesVersion !== undefined && !modern) throw new Error('Invalid battle rules version.');
  const mode = modern ? context.mode : 'campaign';
  if (modern && !['campaign', 'daily', 'weekly'].includes(mode)) throw new Error('Invalid battle mode.');
  const endless = modern && mode !== 'campaign';
  const mapLayoutVersion = context.mapLayoutVersion === undefined ? 1 : context.mapLayoutVersion;
  let level = modern && !endless ? getCampaignLevel(context?.level,mapLayoutVersion) : getLevel(context?.level);
  if (!level || !Array.isArray(context?.towers)) throw new Error('Invalid battle snapshot.');
  const roster = [];
  for (const tower of context.towers) {
    if (!TOWER_DEFS[tower.type] || !Number.isInteger(tower.level) || tower.level < 1 || tower.level > (modern ? MAX_MODERN_TOWER_LEVEL : 30)
      || !RARITIES.some((rarity) => rarity.id === tower.rarity) || roster.some((entry) => entry.type === tower.type)) throw new Error('Invalid tower snapshot.');
    roster.push({ type: tower.type, level: tower.level, rarity: tower.rarity });
  }
  if (modern && ![4, 5, 6].includes(mapLayoutVersion)) throw new Error('Modern battles require free placement.');
  const mapLevel = modern ? (endless ? context.mapLevel : level.map * 5 + 1) : level.id;
  if (modern && (endless ? ![1, 6, 11, 16].includes(mapLevel) : !getMapLevel(mapLevel,mapLayoutVersion))) throw new Error('Invalid battle map.');
  if (endless) {
    const bonus = context.campaignBonusBps ?? 0, theme = context.theme;
    if (!Number.isInteger(bonus) || bonus < 0 || bonus > MAX_CAMPAIGN_BONUS_BPS
      || !Number.isSafeInteger(context.periodStart) || !Number.isSafeInteger(context.periodEnd) || context.periodEnd <= context.periodStart
      || !theme || typeof theme.id !== 'string' || typeof theme.name !== 'string'
      || !Array.isArray(theme.favoredFamilies) || !theme.favoredFamilies.length || theme.favoredFamilies.length > 2
      || new Set(theme.favoredFamilies).size !== theme.favoredFamilies.length
      || theme.favoredFamilies.some(family => !['Assault', 'Artillery', 'Control', 'Energy', 'Support'].includes(family))
      || !Number.isInteger(theme.damageBps) || theme.damageBps < 0 || theme.damageBps > 2500
      || !Number.isInteger(theme.cooldownBps) || theme.cooldownBps < 0 || theme.cooldownBps > 1000) throw new Error('Invalid challenge snapshot.');
    level = { ...level, map: (mapLevel - 1) / 5, waves: null, hpScale: 1, speedScale: 1, startOrbs: mode === 'weekly' ? 300 : 260 };
  }
  if(!endless&&engineVersion>=CAMPAIGN_BOSS_ENGINE_VERSION){
    const boss=getCampaignBoss(level.map);
    if(boss)level={...level,boss:boss.name,bossId:boss.id};
  }
  const normalizedSeed = Number(seed) >>> 0; const map = getMap(mapLevel, mapLayoutVersion); const geometry = pathGeometry(map.path);
  const state = { engineVersion, seed: normalizedSeed, tick: 0, wave: 0,
    level: level.id, totalWaves: level.waves, levelDefinition: level, roster, mapLayoutVersion,
    mapName: map.name, pathPoints: map.path, padPositions: mapLayoutVersion >= 4 ? [] : map.pads, geometry, pathLength: geometry.length,
    ...(mapLayoutVersion >= 4 ? { actionCount: 0 } : {}),
    maxTicks: endless ? null : Math.min(modern ? 15_000 : MAX_TICKS, 80 + level.waves * 220 + 1550),
    lives: 20, energy: level.startOrbs, score: 0, kills: 0, ended: false, victory: false,
    spawnCursor: 0, spawnPlan: endless ? [] : makeSpawnPlan(normalizedSeed, level, engineVersion), enemies: [], towers: [], beams: [], bursts: [], calledWaves: 0, rushEnergy: 0, orbIncome: 0,
    traps: [], trapSerial: 0, generatedOrbs: 0, incomeByPad: Array(map.pads.length).fill(0) };
  if (modern) Object.assign(state, { rulesVersion: MODE_RULES_VERSION, mode, mapLevel, endless, wavesCleared: 0, buildCount: 0,
    campaignBonusBps: endless ? context.campaignBonusBps ?? 0 : 0,
    theme: endless ? { ...context.theme, favoredFamilies: [...context.theme.favoredFamilies] } : null,
    periodStart: endless ? context.periodStart : null, periodEnd: endless ? context.periodEnd : null,
    randomState: normalizedSeed || 0x9e3779b9, enemySerial: 0, retired: false });
  if (endless) queueEndlessWave(state, 1, 80);
  return state;
}
function towerUpgradeCost(tower) { return Math.floor(TOWER_DEFS[tower.type].cost * (0.55 + tower.level * 0.5)); }
export function getUpgradeCost(tower) { return tower.upgradeTiers || tower.level >= 3 ? null : towerUpgradeCost(tower); }
export function getUpgradeChoices(state,tower) {
  if(!(state?.engineVersion>=UPGRADE_PATH_ENGINE_VERSION)||!tower||!TOWER_DEFS[tower.type])return [];
  const definition=TOWER_DEFS[tower.type],tiers=tower.upgradeTiers||EMPTY_UPGRADE_TIERS;
  return UPGRADE_PATHS.map(path=>getPathChoice(tower.type,definition,tiers,path,state.energy,state.engineVersion));
}
export function getSellRefund(state,tower) {
  const refund=Math.floor(tower.invested*.65);
  if(!(state?.engineVersion>=UPGRADE_PATH_ENGINE_VERSION)||TOWER_DEFS[tower.type].effect?.kind!=='income')return refund;
  return Math.max(0,refund-(state.incomeByPad[tower.pad]||0));
}
function applied(state) { if(state.mapLayoutVersion >= 4)state.actionCount += 1;return true; }
export function applyAction(state, action) {
  if (state.ended || !action || action.tick !== state.tick) return false;
  if (state.endless && action.type === 'retire') { state.ended = true; state.victory = false; state.retired = true; return true; }
  if (state.mapLayoutVersion >= 4 && state.actionCount >= MAX_ACTIONS) return false;
  if (action.type === 'rush') {
    const next = state.spawnPlan[state.spawnCursor]; if (!next || next.wave <= state.wave) return false;
    const countdown = next.tick - state.tick; if (countdown < 10) return false;
    for (let index = state.spawnCursor; index < state.spawnPlan.length; index += 1) state.spawnPlan[index].tick -= countdown - 2;
    const bonus = Math.min(32, Math.floor(countdown / 2));
    state.energy += bonus; state.score += bonus * 2; state.calledWaves += 1; state.rushEnergy += bonus;
    state.bursts.push({ ...state.pathPoints[0], color: '#63f0ad', ttl: 8, size: 22 }); return applied(state);
  }
  if (state.mapLayoutVersion >= 4 && action.type === 'build') {
    const definition = TOWER_DEFS[action.tower], owned = state.roster.find(tower => tower.type === action.tower);
    if (!definition || !owned || state.energy < definition.cost || state.towers.length >= MAX_ACTIVE_TOWERS || state.padPositions.length >= MAX_ACTIONS) return false;
    const activePositions = state.towers.map(tower => ({ ...state.padPositions[tower.pad], type: tower.type, pad: tower.pad }));
    if (!getPlacementValidity(state.mapLevel || state.level, action.x, action.y, activePositions, state.mapLayoutVersion).valid) return false;
    const pad = state.padPositions.length;
    state.padPositions.push({ x: action.x, y: action.y }); state.incomeByPad.push(0);
    state.energy -= definition.cost;
    if (state.rulesVersion === MODE_RULES_VERSION) state.buildCount += 1;
    state.towers.push({ id: `t${pad}`, pad, type: action.tower, level: 1, permanentLevel: owned.level,
      rarity: owned.rarity, cooldown: 0, angle: -Math.PI / 2, invested: definition.cost,
      ...(state.engineVersion>=UPGRADE_PATH_ENGINE_VERSION?{upgradeTiers:{...EMPTY_UPGRADE_TIERS}}:{}) }); return applied(state);
  }
  if (!Number.isInteger(action.pad) || action.pad < 0 || action.pad >= state.padPositions.length) return false;
  const existingIndex = state.towers.findIndex((tower) => tower.pad === action.pad);
  if (action.type === 'build') {
    const definition = TOWER_DEFS[action.tower]; const owned = state.roster.find((tower) => tower.type === action.tower);
    if (!definition || !owned || existingIndex !== -1 || state.energy < definition.cost) return false;
    state.energy -= definition.cost;
    state.towers.push({ id: `t${action.pad}`, pad: action.pad, type: action.tower, level: 1, permanentLevel: owned.level,
      rarity: owned.rarity, cooldown: 0, angle: -Math.PI / 2, invested: definition.cost,
      ...(state.engineVersion>=UPGRADE_PATH_ENGINE_VERSION?{upgradeTiers:{...EMPTY_UPGRADE_TIERS}}:{}) }); return applied(state);
  }
  if (existingIndex === -1) return false; const tower = state.towers[existingIndex];
  if (action.type === 'upgrade') {
    if(state.engineVersion>=UPGRADE_PATH_ENGINE_VERSION) {
      const choice=getPathChoice(tower.type,TOWER_DEFS[tower.type],tower.upgradeTiers,action.path,state.energy,state.engineVersion);
      if(!choice?.affordable||choice.cost===null||choice.nextTier===null)return false;
      state.energy-=choice.cost;
      tower.upgradeTiers[choice.path]=choice.nextTier;
      tower.invested+=choice.cost;
      return applied(state);
    }
    const cost = getUpgradeCost(tower); if (cost === null || state.energy < cost) return false;
    state.energy -= cost; tower.level += 1; tower.invested += cost; return applied(state);
  }
  if (action.type === 'sell') { state.energy += getSellRefund(state,tower); state.towers.splice(existingIndex, 1); return applied(state); }
  return false;
}
function spawnEnemy(state, spawn) {
  const definition = ENEMY_DEFS[spawn.kind];
  const difficulty = state.endless ? getEndlessWaveDifficulty(spawn.wave, state.mode) : state.levelDefinition;
  const maxHp = Math.round(definition.hp * difficulty.hpScale * (1 + (spawn.wave - 1) * 0.13));
  const enemy={ id: spawn.id, kind: spawn.kind, wave: spawn.wave, hp: maxHp, maxHp, progress: 0,
    slowUntil: 0, hitFlash: 0, burnUntil: 0, burnDamage: 0, speedScale: difficulty.speedScale, reward: definition.reward };
  if(INVADER_DEFS[spawn.kind])enemy.invaderBornAt=state.tick;
  initializeBoss(state,enemy,spawn);state.enemies.push(enemy);
  state.wave = Math.max(state.wave, spawn.wave);
}
function rarityMultiplier(rarity) { return RARITIES.find((entry) => entry.id === rarity)?.multiplier || 1; }
function challengePower(state, tower) {
  if (!state?.endless) return 1;
  const favored = state.theme?.favoredFamilies.includes(TOWER_DEFS[tower.type].family);
  return (1 + state.campaignBonusBps / 10_000) * (1 + (favored ? state.theme.damageBps : 0) / 10_000);
}
function supportPower(tower, state) { return (1 + (tower.permanentLevel - 1) * .025) * rarityMultiplier(tower.rarity) * [1, 1.35, 1.75][tower.level - 1] * challengePower(state, tower); }
function pathTowerStats(state,tower,definition) {
  const upgrade=pathTowerModifiers(tower.type,definition,tower.upgradeTiers||EMPTY_UPGRADE_TIERS,state.engineVersion);
  const origin=state.padPositions[tower.pad];
  let damageAura=0,haste=0;
  for(const candidate of state.towers) {
    const support=TOWER_DEFS[candidate.type];
    if((candidate.type!=='validator'&&support.effect?.kind!=='haste')||candidate.pad===tower.pad||(candidate.jammedUntil||0)>state.tick)continue;
    const boost=pathTowerModifiers(candidate.type,support,candidate.upgradeTiers||EMPTY_UPGRADE_TIERS,state.engineVersion);
    const point=state.padPositions[candidate.pad];
    if(Math.hypot(point.x-origin.x,point.y-origin.y)>boost.range)continue;
    const scale=supportPower(candidate,state);
    damageAura+=boost.damageAura*scale;
    haste=Math.max(haste,Math.min(boost.hasteCap,boost.hasteAura*scale));
  }
  const supportBonus=Math.min(1.25,damageAura);
  const favored=state.endless&&state.theme?.favoredFamilies.includes(definition.family);
  const cooldown=favored?Math.max(1,Math.round(upgrade.cooldown*(1-state.theme.cooldownBps/10_000))):upgrade.cooldown;
  return {
    ...upgrade,
    damage:definition.damage*1.12**(tower.permanentLevel-1)*rarityMultiplier(tower.rarity)*upgrade.damageMultiplier*(1+supportBonus)*challengePower(state,tower),
    minRange:upgrade.effect?.minRange||0,
    cooldown:haste?Math.max(1,Math.round(cooldown*(1-haste))):cooldown,
    supportBonus,hasteBonus:haste,supportPower:supportPower(tower,state)*upgrade.supportMultiplier,color:definition.color
  };
}
export function getTowerStats(state, tower) {
  const definition = TOWER_DEFS[tower.type];
  if(state.engineVersion>=UPGRADE_PATH_ENGINE_VERSION)return pathTowerStats(state,tower,definition);
  const origin = state.padPositions[tower.pad];
  const validatorBonus = state.towers.filter((candidate) => candidate.type === 'validator' && candidate.pad !== tower.pad && !(state.engineVersion>=4&&(candidate.jammedUntil||0)>state.tick))
    .filter((candidate) => { const support = state.padPositions[candidate.pad]; return Math.hypot(support.x - origin.x, support.y - origin.y) <= TOWER_DEFS.validator.range + (candidate.level - 1) * 12; })
    .reduce((total, candidate) => total + (0.18 + (candidate.level - 1) * 0.12) * (1 + (candidate.permanentLevel - 1) * 0.025) * rarityMultiplier(candidate.rarity) * challengePower(state, candidate), 0);
  const haste = state.towers.filter(candidate => TOWER_DEFS[candidate.type].effect?.kind === 'haste' && candidate.pad !== tower.pad && !(state.engineVersion>=4&&(candidate.jammedUntil||0)>state.tick))
    .filter(candidate => { const pad = state.padPositions[candidate.pad]; return Math.hypot(pad.x - origin.x, pad.y - origin.y) <= TOWER_DEFS[candidate.type].range + (candidate.level - 1) * 12; })
    .reduce((best, candidate) => Math.max(best, Math.min(TOWER_DEFS[candidate.type].effect.cap, TOWER_DEFS[candidate.type].effect.bonus * supportPower(candidate, state))), 0);
  const favored = state.endless && state.theme?.favoredFamilies.includes(definition.family);
  const baseCooldown = Math.max(3, definition.cooldown - (tower.level - 1));
  const effectiveCooldown = favored ? Math.max(1, Math.round(baseCooldown * (1 - state.theme.cooldownBps / 10_000))) : baseCooldown;
  return { damage: definition.damage * 1.12 ** (tower.permanentLevel - 1) * rarityMultiplier(tower.rarity) * [1, 1.85, 3.15][tower.level - 1] * (1 + Math.min(1.25, validatorBonus)) * challengePower(state, tower),
    range: definition.range + (tower.level - 1) * 12, minRange: definition.effect?.minRange || 0,
    cooldown: haste ? Math.max(1, Math.round(effectiveCooldown * (1 - haste))) : effectiveCooldown,
    supportBonus: Math.min(1.25, validatorBonus), hasteBonus: haste, supportPower: supportPower(tower, state), color: definition.color };
}
function targetsInRange(state, tower, range, minRange = 0) {
  const origin = state.padPositions[tower.pad];
  return state.enemies.filter((enemy) => enemy.hp > 0).map((enemy) => ({ enemy, position: pointOnPath(enemy.progress, state) }))
    .filter(({ position }) => { const distance = Math.hypot(position.x - origin.x, position.y - origin.y); return distance <= range && distance >= minRange; })
    .sort((a, b) => b.enemy.progress - a.enemy.progress || a.enemy.id.localeCompare(b.enemy.id));
}
export function getTowerTargets(state, tower, stats = getTowerStats(state, tower)) {
  const definition = TOWER_DEFS[tower.type];
  if (definition.targeting === 'support') return [];
  const targets = targetsInRange(state, tower, stats.range, stats.minRange);
  if (definition.targeting === 'strongest') targets.sort((a, b) => b.enemy.maxHp - a.enemy.maxHp || b.enemy.progress - a.enemy.progress || a.enemy.id.localeCompare(b.enemy.id));
  if (definition.targeting === 'boss') targets.sort((a, b) => Number(b.enemy.kind === 'boss') - Number(a.enemy.kind === 'boss') || b.enemy.progress - a.enemy.progress || a.enemy.id.localeCompare(b.enemy.id));
  if (definition.targeting === 'fastest') targets.sort((a, b) => ENEMY_DEFS[b.enemy.kind].speed * b.enemy.speedScale - ENEMY_DEFS[a.enemy.kind].speed * a.enemy.speedScale || b.enemy.progress - a.enemy.progress || a.enemy.id.localeCompare(b.enemy.id));
  return targets;
}
function damageEnemy(enemy, damage, pierces = false, state) {
  const previousHp = enemy.hp;
  const armorBreak = state && enemy.armorBrokenUntil > state.tick ? enemy.armorBreak || 0 : 0;
  const behavior=INVADER_DEFS[enemy.kind]?.behavior;
  const burrowArmor=behavior?.kind==='burrow'&&invaderBehaviorActive(enemy,state.tick)?behavior.armorBonus:0;
  const armor = Math.max(0, ENEMY_DEFS[enemy.kind].armor + burrowArmor - armorBreak);
  const exposure = state && enemy.exposeUntil > state.tick ? enemy.exposeBonus || 0 : 0;
  const penetration = pierces === true ? 1 : Number(pierces) || 0;
  enemy.hp -= damage * (1 + exposure) * (penetration === 1 ? 1 : 1 - armor * (1 - penetration)) * getBossDamageMultiplier(state,enemy,penetration); enemy.hitFlash = 2;
  reportDamage(state, enemy, previousHp);
}
function areaTargets(state, center, radius) {
  return state.enemies.filter(enemy => enemy.hp > 0).map(enemy => ({ enemy, position: pointOnPath(enemy.progress, state) }))
    .filter(target => Math.hypot(target.position.x - center.x, target.position.y - center.y) <= radius);
}
function chillEnemy(state, enemy, tower, factor, duration, source = tower.id) {
  const until = state.tick + duration + (tower.level - 1) * 3;
  enemy.chillEffects ||= [];
  const previous = enemy.chillEffects.find(chill => chill.source === source);
  const chill = { source, factor: enemy.kind === 'boss' ? Math.max(.4, factor) : factor, until };
  if (previous) Object.assign(previous, chill); else enemy.chillEffects.push(chill);
  enemy.slowUntil = Math.max(enemy.slowUntil, until);
}
function stunEnemy(state, enemy, duration) {
  if ((enemy.stunImmuneUntil || 0) > state.tick) return;
  const ticks = enemy.kind === 'boss' ? Math.max(1, Math.ceil(duration / 2)) : duration;
  enemy.stunUntil = state.tick + ticks;
  enemy.stunImmuneUntil = enemy.stunUntil + (enemy.kind === 'boss' ? 35 : 16);
}
function dealTowerHit(state, tower, enemy, amount, stats, penetration = 0) {
  const pierces = penetration === true ? true : Math.max(penetration, stats.armorPierce || 0);
  const bossMultiplier = enemy.kind === 'boss' ? stats.bossDamageMultiplier ?? 1 : 1;
  damageEnemy(enemy, amount * bossMultiplier, pierces, state);
  if (stats.hitStunTicks) stunEnemy(state, enemy, stats.hitStunTicks);
  if (stats.hitSlowFactor && stats.hitSlowDuration) chillEnemy(state, enemy, tower, stats.hitSlowFactor, stats.hitSlowDuration, `${tower.id}:hit`);
}
function dosePoison(state, enemy, effect, damage) {
  enemy.poisonStacks = (enemy.poisonStacks || []).filter(stack => stack.until > state.tick);
  const dose = { damage, until: state.tick + effect.duration };
  if (enemy.poisonStacks.length < effect.stacks) enemy.poisonStacks.push(dose);
  else {
    enemy.poisonStacks.sort((a, b) => a.damage - b.damage || a.until - b.until);
    if (dose.damage >= enemy.poisonStacks[0].damage) enemy.poisonStacks[0] = dose;
  }
}
function spreadPoison(state, primary, stats, effect) {
  const nearby = areaTargets(state, primary.position, effect.poisonSpreadRadius)
    .filter(target => target.enemy !== primary.enemy)
    .map(target => ({ ...target, distance: Math.hypot(target.position.x - primary.position.x, target.position.y - primary.position.y) }))
    .sort((a, b) => a.distance - b.distance || b.enemy.progress - a.enemy.progress || a.enemy.id.localeCompare(b.enemy.id))
    .slice(0, effect.poisonSpreadTargets);
  const dose = stats.damage * effect.tickDamage * (effect.poisonSpreadDamage ?? .65);
  for (const target of nearby) {
    dosePoison(state, target.enemy, effect, dose);
    effectBeam(state, primary.position, target.position, stats.color, 'poison', 2);
  }
}
const SINGLE_TARGET_EFFECTS = new Set(['rapid', 'ramp', 'boss', 'execute', 'sniper', 'expose', 'shred', 'weaken', 'anchorSlow', 'deathMark']);
function effectBeam(state, from, to, color, style = 'pulse', width = 3) { state.beams.push({ from, to, color, ttl: 2, width, style }); }
function effectBurst(state, position, color, size) { state.bursts.push({ ...position, color, ttl: 7, size }); }
function fireEffectTower(state, tower, stats) {
  const effect = stats.effect || TOWER_DEFS[tower.type].effect, origin = state.padPositions[tower.pad];
  if (effect.kind === 'haste') return;
  if (effect.kind === 'cleanse') {
    const nearby = state.towers.filter(weapon => weapon.pad !== tower.pad && TOWER_DEFS[weapon.type].damage > 0
      && (weapon.auroraAssistUntil || 0) <= state.tick && (weapon.cooldown > 1 || (weapon.jammedUntil || 0) > state.tick))
      .map(weapon => ({weapon,position:state.padPositions[weapon.pad],jammed:(weapon.jammedUntil || 0) > state.tick}))
      .filter(({position}) => Math.hypot(position.x - origin.x, position.y - origin.y) <= stats.range)
      .sort((a,b) => Number(b.jammed) - Number(a.jammed) || b.weapon.cooldown - a.weapon.cooldown || a.weapon.pad - b.weapon.pad)
      .slice(0,effect.targets);
    if (!nearby.length) return;
    const advance = Math.floor(effect.advance * Math.min(2, stats.supportPower));
    for (const {weapon,position,jammed} of nearby) {
      if (jammed) weapon.jammedUntil = state.tick;
      weapon.cooldown = Math.max(0, weapon.cooldown - advance);
      weapon.auroraAssistUntil = state.tick + effect.assistCooldown;
      effectBeam(state, origin, position, stats.color, 'prism', 2);
      effectBurst(state, position, stats.color, 16);
    }
    tower.cooldown = stats.cooldown;
    return;
  }
  if (effect.kind === 'income') {
    const produced = state.incomeByPad[tower.pad] || 0, slotCap = Math.floor(effect.perSlotCap * Math.min(2, stats.supportPower));
    const amount = Math.max(0, Math.min(Math.floor(effect.amount * Math.min(2, stats.supportPower)), slotCap - produced, effect.teamCap - state.generatedOrbs));
    if (amount) { state.energy += amount; state.orbIncome += amount; state.generatedOrbs += amount; state.incomeByPad[tower.pad] = produced + amount; effectBurst(state, origin, stats.color, 18); }
    tower.cooldown = stats.cooldown; return;
  }
  const targets = getTowerTargets(state, tower, stats);
  if (!targets.length) { if (effect.kind === 'ramp') { tower.focusTarget = null; tower.focusStacks = 0; } return; }
  const primary = targets[0]; tower.angle = Math.atan2(primary.position.y - origin.y, primary.position.x - origin.x);
  if (effect.kind === 'mine') {
    if (state.traps.length < 24 && state.traps.filter(trap => trap.pad === tower.pad).length < effect.limit) {
      const trap = { id: `m${state.trapSerial++}`, pad: tower.pad, position: { ...primary.position }, damage: stats.damage,
        armAt: state.tick + effect.armTicks, expiresAt: state.tick + effect.lifetime, triggerRadius: effect.triggerRadius, radius: effect.splash, color: stats.color };
      if (state.engineVersion >= THEMED_UPGRADE_ENGINE_VERSION) Object.assign(trap, {
        armorPierce: stats.armorPierce || 0, bossDamageMultiplier: stats.bossDamageMultiplier ?? 1,
        hitStunTicks: stats.hitStunTicks || 0, hitSlowFactor: stats.hitSlowFactor || 0, hitSlowDuration: stats.hitSlowDuration || 0
      });
      state.traps.push(trap);
      effectBeam(state, origin, primary.position, stats.color, 'shell');
    }
    tower.cooldown = stats.cooldown; return;
  }
  tower.shotsFired = (tower.shotsFired || 0) + 1;
  let multiplier = 1, style = 'pulse', width = 3;
  if (effect.kind === 'rapid' && tower.shotsFired % effect.criticalEvery === 0) { multiplier = effect.criticalMultiplier; width = 5; effectBurst(state, primary.position, '#fff0bd', 14); }
  if (effect.kind === 'ramp') {
    tower.focusStacks = tower.focusTarget === primary.enemy.id ? Math.min(effect.stacks, (tower.focusStacks || 0) + 1) : 0;
    tower.focusTarget = primary.enemy.id; multiplier += tower.focusStacks * effect.step; style = 'prism'; width = 2 + tower.focusStacks * .5;
  }
  const directFan = stats.hitTargets > 1 && SINGLE_TARGET_EFFECTS.has(effect.kind);
  let selected = directFan ? targets.slice(0, stats.hitTargets) : [primary], beamEnd = primary.position;
  if (effect.kind === 'scatter') selected = targets.filter(target => {
    const angle = Math.atan2(target.position.y - origin.y, target.position.x - origin.x);
    return Math.abs(Math.atan2(Math.sin(angle - tower.angle), Math.cos(angle - tower.angle))) <= effect.angle;
  }).slice(0, effect.targets);
  if (effect.kind === 'linePierce') {
    const dx = primary.position.x - origin.x, dy = primary.position.y - origin.y, length = Math.hypot(dx,dy);
    if (length > 0) {
      const behind = targets.filter(target => target !== primary).map(target => {
        const x = target.position.x - origin.x, y = target.position.y - origin.y;
        return {target,along:(x * dx + y * dy) / length,offset:Math.abs(x * dy - y * dx) / length};
      }).filter(hit => hit.along >= length && hit.offset <= effect.lineWidth)
        .sort((a,b) => a.along - b.along || a.target.enemy.id.localeCompare(b.target.enemy.id)).slice(0,effect.targets-1);
      selected = [primary,...behind.map(hit=>hit.target)];
      const furthest = behind.at(-1)?.along || length;
      beamEnd = {x:origin.x+dx/length*furthest,y:origin.y+dy/length*furthest};
    }
    style = 'prism'; width = 4;
  }
  if (effect.kind === 'chainSlow' || effect.kind === 'chainStun') { selected = targets.slice(0, effect.targets); style = effect.kind === 'chainStun' ? 'arc' : 'frost'; }
  if (['artillery', 'shockwave', 'meteor', 'fieldSlow', 'gravity'].includes(effect.kind)) { selected = areaTargets(state, primary.position, effect.splash); style = effect.kind === 'fieldSlow' ? 'frost' : effect.kind === 'gravity' ? 'prism' : 'shell'; effectBurst(state, primary.position, stats.color, effect.splash * .6); }
  if (effect.kind === 'scorch') { selected = areaTargets(state, primary.position, effect.splash); style = 'shell'; effectBurst(state, primary.position, stats.color, effect.splash * .68); }
  if (effect.kind === 'anchorSlow') style = 'frost';
  if (effect.kind === 'sniper' || effect.kind === 'boss') { style = 'prism'; width = 4; }
  if (effect.kind === 'poison') style = 'poison';
  if (effect.kind === 'expose') style = 'prism';
  if (effect.kind === 'deathMark') style = 'fire';
  for (const target of selected) {
    const enemy = target.enemy;
    let amount = stats.damage * multiplier;
    if (effect.kind === 'boss' && enemy.kind === 'boss') amount *= effect.bossMultiplier;
    const executes = effect.kind === 'execute' && enemy.hp / enemy.maxHp <= effect.threshold;
    if (executes && enemy.kind === 'boss') amount *= effect.bossMultiplier;
    const secondaryScale = directFan && target !== primary ? stats.secondaryDamage ?? .65 : 1;
    amount *= secondaryScale;
    if (effect.kind === 'linePierce' && target !== primary) amount *= effect.secondaryDamage;
    if (effect.kind === 'meteor') { const distance = Math.hypot(target.position.x - primary.position.x, target.position.y - primary.position.y); amount *= 1 - (1 - effect.edgeDamage) * distance / effect.splash; }
    if (executes && enemy.kind !== 'boss') amount = enemy.hp + 1;
    if (effect.kind === 'expose') { enemy.exposeBonus = Math.max(enemy.exposeUntil > state.tick ? enemy.exposeBonus : 0, Math.min(.65, effect.bonus * stats.supportPower)); enemy.exposeUntil = state.tick + effect.duration; }
    if (effect.kind === 'shred') { enemy.armorBreak = Math.min(effect.maxArmorBreak, (enemy.armorBrokenUntil > state.tick ? enemy.armorBreak || 0 : 0) + effect.armorBreak * Math.min(2, stats.supportPower)); enemy.armorBrokenUntil = state.tick + effect.duration; }
    if (effect.kind === 'weaken') { enemy.weakenReduction = Math.max(enemy.weakenUntil > state.tick ? enemy.weakenReduction || 0 : 0, Math.min(enemy.kind === 'boss' ? .35 : .6, effect.reduction * stats.supportPower)); enemy.weakenUntil = state.tick + effect.duration; }
    if (effect.kind === 'chainSlow' || effect.kind === 'fieldSlow' || effect.kind === 'anchorSlow') chillEnemy(state, enemy, tower, effect.factor, effect.duration);
    if (effect.kind === 'scorch' && (!(enemy.scorchUntil > state.tick) || enemy.scorchDamage <= stats.damage * effect.tickDamage)) {
      enemy.scorchDamage = stats.damage * effect.tickDamage; enemy.scorchUntil = state.tick + effect.duration;
    }
    if (effect.kind === 'shockwave' || effect.kind === 'chainStun') stunEnemy(state, enemy, effect.stunTicks);
    if (effect.kind === 'poison') dosePoison(state, enemy, effect, stats.damage * effect.tickDamage);
    if (effect.kind === 'gravity' && (enemy.pullImmuneUntil || 0) <= state.tick) { enemy.progress = Math.max(0, enemy.progress - effect.pull * (enemy.kind === 'boss' ? .25 : 1)); enemy.pullImmuneUntil = state.tick + effect.immunity; }
    if (effect.kind === 'deathMark') { enemy.deathMarkDamage = Math.max(enemy.deathMarkUntil > state.tick ? enemy.deathMarkDamage || 0 : 0, stats.damage * effect.explosionDamage * secondaryScale); enemy.deathMarkUntil = state.tick + effect.duration; enemy.deathMarkRadius = effect.splash; enemy.deathMarkColor = stats.color; }
    dealTowerHit(state, tower, enemy, amount, stats, executes && enemy.kind !== 'boss' ? true : effect.armorPierce);
    if (effect.kind !== 'scorch' && effect.kind !== 'linePierce') effectBeam(state, origin, target.position, stats.color, style, width);
  }
  if (effect.kind === 'poison' && effect.poisonSpreadTargets > 0) spreadPoison(state, primary, stats, effect);
  if (effect.kind === 'scorch') effectBeam(state, origin, primary.position, stats.color, style, width);
  if (effect.kind === 'linePierce') effectBeam(state,origin,beamEnd,stats.color,style,width);
  tower.cooldown = stats.cooldown;
}
function resolveTraps(state) {
  const remaining = [];
  for (const trap of state.traps) {
    if (trap.expiresAt <= state.tick) continue;
    if (trap.armAt <= state.tick && areaTargets(state, trap.position, trap.triggerRadius).length) {
      const tower = { id: `t${trap.pad}`, level: 1 };
      for (const target of areaTargets(state, trap.position, trap.radius)) dealTowerHit(state, tower, target.enemy, trap.damage, trap);
      effectBurst(state, trap.position, trap.color, trap.radius);
    } else remaining.push(trap);
  }
  state.traps = remaining;
}
function resolveDeathMarks(state) {
  // Each marked enemy can explode once. This bounded loop resolves chain reactions
  // before kill rewards are collected, avoiding duplicate rewards on later ticks.
  const pending = () => state.enemies.find(enemy => enemy.hp <= 0 && enemy.hp !== -99999 && enemy.deathMarkUntil > state.tick && !enemy.deathMarkExploded);
  let enemy;
  while ((enemy = pending())) {
    enemy.deathMarkExploded = true;
    const position = pointOnPath(enemy.progress, state);
    for (const target of areaTargets(state, position, enemy.deathMarkRadius)) damageEnemy(target.enemy, enemy.deathMarkDamage, false, state);
    effectBurst(state, position, enemy.deathMarkColor, enemy.deathMarkRadius);
  }
}
function fireTower(state, tower) {
  if (tower.type === 'validator') return;
  if (TOWER_DEFS[tower.type].effect) { fireEffectTower(state, tower, getTowerStats(state, tower)); return; }
  const stats = getTowerStats(state, tower); const targets = targetsInRange(state, tower, stats.range); if (!targets.length) return;
  const origin = state.padPositions[tower.pad]; const primary = targets[0];
  tower.angle = Math.atan2(primary.position.y - origin.y, primary.position.x - origin.x);
  if (tower.type === 'arc' || tower.type === 'prism') {
    let previous = origin; const limit = state.engineVersion>=UPGRADE_PATH_ENGINE_VERSION?3+stats.extraTargets:tower.type === 'prism' ? 3 + (tower.level === 3 ? 1 : 0) : 3;
    for (let index = 0; index < Math.min(limit, targets.length); index += 1) {
      const target = targets[index];
      const amount = stats.damage * (index === 0 ? 1 : stats.chainDamageRatio ?? .72);
      dealTowerHit(state, tower, target.enemy, amount, stats, tower.type === 'prism');
      state.beams.push({ from: previous, to: target.position, color: stats.color, ttl: 2, width: 3 - index * 0.35 }); previous = tower.type === 'prism' ? origin : target.position;
    }
  } else if (tower.type === 'firewall') {
    for (const target of targets) {
      if (Math.hypot(target.position.x - primary.position.x, target.position.y - primary.position.y) > (stats.legacySplash??65)) continue;
      dealTowerHit(state, tower, target.enemy, stats.damage * (target === primary ? 1 : .8), stats);
      target.enemy.burnUntil = state.tick + (stats.burnDuration ?? 18);
      target.enemy.burnDamage = Math.max(target.enemy.burnDamage, stats.damage * (stats.burnDamageRatio ?? .025));
    }
    state.beams.push({ from: origin, to: primary.position, color: stats.color, ttl: 3, width: 5 }); state.bursts.push({ ...primary.position, color: stats.color, ttl: 7, size: 32 });
  } else {
    for (const target of targets.slice(0, stats.hitTargets ?? 1)) {
      const amount = stats.damage * (target === primary ? 1 : stats.secondaryDamage ?? .65);
      dealTowerHit(state, tower, target.enemy, amount, stats, tower.type === 'block');
      if (tower.type === 'frost') target.enemy.slowUntil = Math.max(target.enemy.slowUntil, state.tick + (stats.frostDuration ?? 22 + tower.level * 3));
      if (tower.type === 'block') state.bursts.push({ ...target.position, color: stats.color, ttl: 6, size: 22 });
      state.beams.push({ from: origin, to: target.position, color: stats.color, ttl: 2, width: tower.type === 'pulse' ? 3 : 4 });
    }
  }
  tower.cooldown = stats.cooldown;
}
export function stepGame(state) {
  if (state.ended) return state;
  state.beams = state.beams.filter((beam) => --beam.ttl > 0); state.bursts = state.bursts.filter((burst) => --burst.ttl > 0);
  while (state.spawnCursor < state.spawnPlan.length && state.spawnPlan[state.spawnCursor].tick <= state.tick) {
    const spawn = state.spawnPlan[state.spawnCursor];
    if (spawn.wave > state.wave && spawn.wave > 1) { const bonus = 22 + Math.floor(state.level / 3); state.energy += bonus; state.orbIncome += bonus; }
    spawnEnemy(state, spawn); state.spawnCursor += 1;
  }
  advanceBosses(state,{positionAt:pointOnPath,spawnDrone:(parent,cast,index,progress,kind='runner',hpFraction=.045)=>{
    const hp=Math.max(16,Math.round(parent.maxHp*hpFraction));
    const variant=INVADER_DEFS[kind];
    state.enemies.push({id:`${parent.id}b${cast}-${index}`,kind,wave:parent.wave,hp,maxHp:hp,progress,
      slowUntil:0,hitFlash:0,burnUntil:0,burnDamage:0,speedScale:variant?state.levelDefinition.speedScale:parent.speedScale,reward:0,summonedBy:parent.id,
      ...(variant?{invaderBornAt:state.tick}:{})});
  }});
  resolveTraps(state);
  for (const tower of state.towers) { if(state.engineVersion>=4&&(tower.jammedUntil||0)>state.tick)continue;tower.cooldown -= 1; if (tower.cooldown <= 0) fireTower(state, tower); }
  for (const enemy of state.enemies) {
    if (enemy.hp <= 0) continue;
    const definition = ENEMY_DEFS[enemy.kind], behavior=definition.behavior;
    const heatMultiplier=behavior?.kind==='heatResist'?behavior.multiplier:1;
    if (enemy.burnUntil > state.tick) { const previousHp = enemy.hp; enemy.hp -= enemy.burnDamage*heatMultiplier; reportDamage(state, enemy, previousHp, 'burn'); } if (enemy.hp <= 0) continue;
    if (enemy.scorchUntil > state.tick) { const previousHp = enemy.hp; enemy.hp -= enemy.scorchDamage*heatMultiplier; reportDamage(state, enemy, previousHp, 'burn'); } if (enemy.hp <= 0) continue;
    if (enemy.poisonStacks) { enemy.poisonStacks = enemy.poisonStacks.filter(stack => stack.until > state.tick); for (const stack of enemy.poisonStacks) { const previousHp = enemy.hp; enemy.hp -= stack.damage; reportDamage(state, enemy, previousHp, 'poison'); } if (enemy.hp <= 0) continue; }
    let movement = enemy.slowUntil > state.tick ? .48 : 1;
    if (enemy.chillEffects) { enemy.chillEffects = enemy.chillEffects.filter(chill => chill.until > state.tick); for (const chill of enemy.chillEffects) movement = Math.min(movement, chill.factor); }
    if(behavior?.kind==='chillResist')movement=Math.max(movement,behavior.movementFloor);
    if (enemy.stunUntil > state.tick) movement = 0;
    const sprint=behavior?.kind==='sprint'&&invaderBehaviorActive(enemy,state.tick)?behavior.multiplier:1;
    enemy.progress += definition.speed * enemy.speedScale * movement * sprint * getBossMovementMultiplier(state,enemy); enemy.hitFlash = Math.max(0, enemy.hitFlash - 1);
    if (enemy.progress >= state.pathLength) { const reduction = enemy.weakenUntil > state.tick ? enemy.weakenReduction || 0 : 0;
      const coreDamage = reduction ? Math.max(1, Math.ceil(definition.damage * (1 - reduction))) : definition.damage;
      enemy.hp = -99999; state.lives = Math.max(0, state.lives - coreDamage); state.bursts.push({ ...pointOnPath(state.pathLength, state), color: '#ff3b66', ttl: 8, size: 26 }); }
  }
  resolveDeathMarks(state);
  const survivors = [];
  for (const enemy of state.enemies) {
    if (enemy.hp > 0) { survivors.push(enemy); continue; } if (enemy.hp === -99999) continue;
    state.energy += enemy.reward; state.orbIncome += enemy.reward; state.score += Math.round(90 + enemy.wave * 18 + enemy.reward * 2); state.kills += 1;
    state.bursts.push({ ...pointOnPath(enemy.progress, state), color: ENEMY_DEFS[enemy.kind].color, ttl: 7, size: ENEMY_DEFS[enemy.kind].radius + 8 });
    if (enemy.kind === 'splitter') {
      for (let child = 0; child < 2; child += 1) { const hp = Math.round(enemy.maxHp * 0.28); const offspring = { ...enemy, id: `${enemy.id}s${child}`, kind: 'runner', hp, maxHp: hp, progress: enemy.progress - child * 12, reward: 3, burnDamage: 0, burnUntil: 0, hitFlash: 0 };
        for (const field of ['poisonStacks','chillEffects','stunUntil','stunImmuneUntil','armorBreak','armorBrokenUntil','exposeBonus','exposeUntil','weakenReduction','weakenUntil','pullImmuneUntil','deathMarkDamage','deathMarkUntil','deathMarkRadius','deathMarkColor','deathMarkExploded','scorchUntil','scorchDamage','wardUntil','wardReduction']) delete offspring[field];
        survivors.push(offspring); }
    }
    const split=INVADER_DEFS[enemy.kind]?.behavior;
    if(split?.kind==='split'&&state.enemies.length<180){
      const hp=Math.max(1,Math.round(enemy.maxHp*split.hpFraction));
      survivors.push({id:`${enemy.id}s0`,kind:split.child,wave:enemy.wave,hp,maxHp:hp,progress:enemy.progress,
        slowUntil:0,hitFlash:0,burnUntil:0,burnDamage:0,speedScale:enemy.speedScale,reward:enemy.reward?2:0,invaderBornAt:state.tick});
    }
  }
  state.enemies = survivors;
  if (state.lives <= 0) { state.ended = true; state.victory = false; }
  else if (state.endless) {
    if (state.spawnCursor >= state.spawnPlan.length && state.enemies.length === 0) {
      state.wavesCleared = state.wave;
      queueEndlessWave(state, state.wave + 1, state.tick + 30);
    }
  } else {
    if (state.rulesVersion === MODE_RULES_VERSION) {
      const next = state.spawnPlan[state.spawnCursor];
      while (state.wavesCleared < state.wave) {
        const candidate = state.wavesCleared + 1;
        if (next?.wave <= candidate || state.enemies.some(enemy => enemy.wave <= candidate)) break;
        state.wavesCleared = candidate;
      }
    }
    if (state.spawnCursor >= state.spawnPlan.length && state.enemies.length === 0) { state.ended = true; state.victory = true; state.score += state.lives * 75; }
    else if (state.tick >= state.maxTicks) { state.ended = true; state.victory = false; }
  }
  state.tick += 1; return state;
}
export function currentWaveCountdown(state) { const next = state.spawnPlan[state.spawnCursor]; if (!next) return null; if (next.wave <= state.wave) return 0; return Math.max(0, next.tick - state.tick); }
export function simulateDefense(seed, actions, context = createStarterContext()) {
  if (context?.rulesVersion === MODE_RULES_VERSION && context.mode !== 'campaign') return { valid: false, reason: 'Endless runs require bounded replay checkpoints.' };
  if (!Array.isArray(actions) || actions.length > MAX_ACTIONS) return { valid: false, reason: 'Invalid action list.' };
  let state; try { state = createGame(seed, context); } catch { return { valid: false, reason: 'Invalid battle snapshot.' }; }
  const normalized = []; let previousTick = -1;
  for (const raw of actions) {
    if (!raw || !Number.isInteger(raw.tick) || raw.tick < 0 || raw.tick < previousTick || raw.tick > state.maxTicks) return { valid: false, reason: 'Actions are out of order.' };
    if (!['build', 'upgrade', 'sell', 'rush'].includes(raw.type)) return { valid: false, reason: 'Unknown action.' };
    const action = { type: raw.type, tick: raw.tick };
    if (raw.type === 'build' && state.mapLayoutVersion >= 4) { action.x = raw.x; action.y = raw.y; }
    else if (raw.type !== 'rush') action.pad = raw.pad;
    if(raw.type==='upgrade'&&state.engineVersion>=UPGRADE_PATH_ENGINE_VERSION)action.path=raw.path;
    if (raw.type === 'build') action.tower = String(raw.tower || ''); normalized.push(action); previousTick = raw.tick;
  }
  let cursor = 0;
  while (!state.ended && state.tick <= state.maxTicks) {
    while (cursor < normalized.length && normalized[cursor].tick === state.tick) { if (!applyAction(state, normalized[cursor])) return { valid: false, reason: `Invalid action at tick ${state.tick}.` }; cursor += 1; }
    stepGame(state);
  }
  if (cursor !== normalized.length || !state.ended) return { valid: false, reason: 'Run did not settle.' };
  return { valid: true, result: defenseResult(state) };
}
/** @returns {{victory:boolean,level:number,wave:number,lives:number,score:number,kills:number,ticks:number,calledWaves:number,mode?:string,ended?:boolean,wavesCleared?:number,retired?:boolean}} */
export function defenseResult(state) {
  const result = { victory: state.victory, level: state.level, wave: state.wave, lives: state.lives, score: state.score, kills: state.kills, ticks: state.tick, calledWaves: state.calledWaves };
  if (state.rulesVersion === MODE_RULES_VERSION) Object.assign(result, { mode: state.mode, ended: state.ended, wavesCleared: state.wavesCleared, retired: state.retired });
  return result;
}

/** Replay only a bounded segment. `state` must come from the server's persisted
 * checkpoint, never from a request body. The returned clone can be persisted as
 * JSON and includes its complete lazy-wave RNG and stable tower origins.
 *
 * Actions on endTick are applied without advancing another tick, matching the
 * live client's state immediately after a build click. Request sequences own
 * idempotency; callers must not resend acknowledged actions in a new sequence.
 * @param {number} seed
 * @param {Array<any>} actions
 * @param {any} context
 * @param {{state?:any,endTick?:number,maxTicks?:number}} [options]
 */
export function replayDefenseChunk(seed, actions, context, { state: checkpoint, endTick, maxTicks = MAX_REPLAY_CHUNK_TICKS } = {}) {
  if (context?.rulesVersion !== MODE_RULES_VERSION) return { valid: false, reason: 'Checkpoint rules version is required.' };
  if (!Array.isArray(actions) || actions.length > MAX_ACTIONS) return { valid: false, reason: 'Invalid action list.' };
  if (!Number.isInteger(maxTicks) || maxTicks < 1 || maxTicks > MAX_REPLAY_CHUNK_TICKS) return { valid: false, reason: 'Invalid replay chunk limit.' };
  let state;
  try {
    state = checkpoint ? structuredClone(checkpoint) : createGame(seed, context);
    const expectedMapLevel = context.mode === 'campaign' ? getCampaignLevel(context.level,context.mapLayoutVersion)?.map * 5 + 1 : context.mapLevel;
    const rosterMatches = Array.isArray(state.roster) && state.roster.length === context.towers?.length
      && state.roster.every((tower,index) => tower.type === context.towers[index].type && tower.level === context.towers[index].level && tower.rarity === context.towers[index].rarity);
    const challengeMatches = context.mode === 'campaign' || state.campaignBonusBps === (context.campaignBonusBps ?? 0)
      && state.periodStart === context.periodStart && state.periodEnd === context.periodEnd
      && JSON.stringify(state.theme) === JSON.stringify(context.theme);
    if (state.engineVersion !== (context.engineVersion??3) || state.rulesVersion !== MODE_RULES_VERSION || state.seed !== (Number(seed) >>> 0)
      || state.mode !== context.mode || state.level !== context.level || state.mapLayoutVersion !== context.mapLayoutVersion
      || state.mapLevel !== expectedMapLevel || !rosterMatches || !challengeMatches
      || state.engineVersion>=UPGRADE_PATH_ENGINE_VERSION&&(!Array.isArray(state.towers)||!state.towers.every(tower=>validUpgradeTiers(tower.upgradeTiers)))
      || !Number.isSafeInteger(state.tick) || state.tick < 0 || !Array.isArray(state.pathPoints)) throw new Error('Invalid checkpoint.');
    state.geometry = pathGeometry(state.pathPoints);
  } catch { return { valid: false, reason: 'Invalid battle checkpoint.' }; }
  if (!Number.isSafeInteger(endTick) || endTick < state.tick || endTick - state.tick > maxTicks) return { valid: false, reason: 'Replay segment is outside the checkpoint window.' };
  const normalized = []; let previousTick = state.tick;
  for (const raw of actions) {
    if (!raw || !Number.isSafeInteger(raw.tick) || raw.tick < previousTick || raw.tick > endTick) return { valid: false, reason: 'Actions are out of order.' };
    if (!['build', 'upgrade', 'sell', 'rush', 'retire'].includes(raw.type)) return { valid: false, reason: 'Unknown action.' };
    const action = { type: raw.type, tick: raw.tick };
    if (raw.type === 'build') { action.x = raw.x; action.y = raw.y; action.tower = String(raw.tower || ''); }
    else if (raw.type === 'upgrade' || raw.type === 'sell') action.pad = raw.pad;
    if(raw.type==='upgrade'&&state.engineVersion>=UPGRADE_PATH_ENGINE_VERSION)action.path=raw.path;
    normalized.push(action); previousTick = raw.tick;
  }
  let cursor = 0;
  while (true) {
    while (cursor < normalized.length && normalized[cursor].tick === state.tick) {
      if (!applyAction(state, normalized[cursor])) return { valid: false, reason: `Invalid action at tick ${state.tick}.` };
      cursor += 1;
    }
    if (state.ended || state.tick === endTick) break;
    stepGame(state);
  }
  if (cursor !== normalized.length) return { valid: false, reason: 'Actions continue after the defense ended.' };
  return { valid: true, state, result: defenseResult(state) };
}
