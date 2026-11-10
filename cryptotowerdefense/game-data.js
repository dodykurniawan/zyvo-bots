// Shared by the collection, battle snapshot, and server validation.
import { MAP_LAYOUT_VERSION } from './map-layout.js';
import {CAMPAIGN_WORLDS} from './campaign-worlds.js';
export { MAP_LAYOUT_VERSION };
export const TOWER_FAMILIES = Object.freeze(['Assault', 'Artillery', 'Control', 'Energy', 'Support']);
export const NEW_CXL_EXCLUSIVE_TYPES = Object.freeze(['sunforge','phase_lancer','cryo_anchor','aurora_core']);
export const NEW_SHOP_EXCLUSIVE_TYPES = Object.freeze([
  'gilded_ballista', 'monsoon_battery', 'thorn_harvester', 'magnetar_array',
  'tidal_obelisk', 'circuit_weaver', 'bulwark_beacon', 'nova_siphon'
]);
export const RARITIES = Object.freeze([
  { id: 'common', name: 'Common', color: '#aebbd0', multiplier: 1 },
  { id: 'uncommon', name: 'Uncommon', color: '#63f0ad', multiplier: 1.22 },
  { id: 'rare', name: 'Rare', color: '#63a8ff', multiplier: 1.5 },
  { id: 'epic', name: 'Epic', color: '#b183ff', multiplier: 1.85 },
  { id: 'legendary', name: 'Legendary', color: '#ffbd5c', multiplier: 2.3 },
  { id: 'mythic', name: 'Mythic', color: '#ff6e9f', multiplier: 3 }
]);

export const TOWER_CATALOG = Object.freeze({
  pulse: { name: 'Pulse Cannon', short: 'PULSE', role: 'Assault', family: 'Assault', specialty: 'Reliable fire', cost: 80, range: 128, damage: 24, cooldown: 7, color: '#60f5ff', description: 'Fast, reliable single-target fire.', unlockLevel: 1, shopExclusive: false },
  arc: { name: 'Arc Node', short: 'ARC', role: 'Chain', family: 'Energy', specialty: 'Chain lightning', cost: 125, range: 124, damage: 20, cooldown: 12, color: '#a77bff', description: 'Chains lightning through up to three threats.', unlockLevel: 1, shopExclusive: false },
  frost: { name: 'Cold Wallet', short: 'FROST', role: 'Control', family: 'Control', specialty: 'Single-target slow', cost: 105, range: 126, damage: 13, cooldown: 12, color: '#89b8ff', description: 'Slows threats so the rest of your grid can fire.', unlockLevel: 3, shopExclusive: false },
  firewall: { name: 'Firewall', short: 'BURN', role: 'Splash', family: 'Artillery', specialty: 'Splash and burn', cost: 140, range: 118, damage: 28, cooldown: 14, color: '#ff7a52', description: 'Splash damage and a lingering burn.', unlockLevel: 5, shopExclusive: false },
  block: { name: 'Block Launcher', short: 'BLOCK', role: 'Artillery', family: 'Artillery', specialty: 'Full armor piercing', cost: 165, range: 170, damage: 104, cooldown: 24, color: '#ffbd5c', description: 'Long-range impact that pierces armor.', unlockLevel: 8, shopExclusive: false },
  validator: { name: 'Validator', short: 'BOOST', role: 'Support', family: 'Support', specialty: 'Damage aura', targeting: 'support', cost: 130, range: 198, damage: 0, cooldown: 10, color: '#63f0ad', description: 'Boosts nearby damage towers. Stronger with rarity and levels.', unlockLevel: 10, shopExclusive: false },
  prism: { name: 'Prism Spire', short: 'PRISM', role: 'Beam', family: 'Energy', specialty: 'Piercing beams', cost: 180, range: 152, damage: 37, cooldown: 13, color: '#ff8fe1', description: 'A piercing beam that strikes several advancing targets.', unlockLevel: 1, shopExclusive: true },
  repeater: { name: 'Burst Repeater', short: 'BURST', role: 'Rapid fire', family: 'Assault', specialty: 'Critical rhythm', cost: 95, range: 118, damage: 9, cooldown: 3, color: '#4edbd1', description: 'Rapid fire. Every sixth shot is a guaranteed critical hit.', unlockLevel: 2, shopExclusive: false, effect: { kind: 'rapid', criticalEvery: 6, criticalMultiplier: 2.4 } },
  sniper: { name: 'Sentinel Sniper', short: 'SNIPE', role: 'Precision', family: 'Assault', specialty: 'Armor piercing', targeting: 'strongest', cost: 160, range: 235, damage: 145, cooldown: 31, color: '#a2d6ff', description: 'Prioritizes the strongest enemy and ignores most of its armor.', unlockLevel: 4, shopExclusive: false, effect: { kind: 'sniper', armorPierce: .85 } },
  scatter: { name: 'Scattershot', short: 'SCATTER', role: 'Volley', family: 'Assault', specialty: 'Cone volley', cost: 135, range: 112, damage: 24, cooldown: 11, color: '#ffb477', description: 'Sweeps a forward cone with a volley that can hit five enemies.', unlockLevel: 6, shopExclusive: false, effect: { kind: 'scatter', angle: .65, targets: 5 } },
  shredder: { name: 'Armor Shredder', short: 'SHRED', role: 'Armor break', family: 'Assault', specialty: 'Stacking armor shred', cost: 155, range: 132, damage: 18, cooldown: 7, color: '#ed777b', description: 'Repeated hits strip armor so your whole defense deals more damage.', unlockLevel: 9, shopExclusive: false, effect: { kind: 'shred', armorBreak: .075, maxArmorBreak: .3, duration: 45 } },
  executioner: { name: 'Executioner', short: 'FINISH', role: 'Finisher', family: 'Assault', specialty: 'Low-health execution', cost: 210, range: 145, damage: 48, cooldown: 16, color: '#b18af1', description: 'Executes ordinary enemies below 20% health; wounded bosses take bonus damage.', unlockLevel: 14, shopExclusive: false, effect: { kind: 'execute', threshold: .2, bossMultiplier: 2.5 } },
  howitzer: { name: 'Siege Howitzer', short: 'SIEGE', role: 'Siege', family: 'Artillery', specialty: 'Minimum range', cost: 190, range: 220, damage: 125, cooldown: 29, color: '#c2c382', description: 'Long-range explosive shells. Cannot fire at enemies inside its inner dead zone.', unlockLevel: 6, shopExclusive: false, effect: { kind: 'artillery', minRange: 70, splash: 52 } },
  minefield: { name: 'Mine Foundry', short: 'MINES', role: 'Traps', family: 'Artillery', specialty: 'Proximity mines', cost: 165, range: 155, damage: 102, cooldown: 24, color: '#efb154', description: 'Lays mines that arm, wait for a nearby threat, then explode.', unlockLevel: 10, shopExclusive: false, effect: { kind: 'mine', armTicks: 4, triggerRadius: 28, splash: 49, lifetime: 180, limit: 3 } },
  seismic: { name: 'Seismic Driver', short: 'QUAKE', role: 'Shockwave', family: 'Artillery', specialty: 'Stun pulses', cost: 205, range: 145, damage: 72, cooldown: 26, color: '#d89c79', description: 'A shockwave damages and briefly stuns a cluster of enemies.', unlockLevel: 13, shopExclusive: false, effect: { kind: 'shockwave', splash: 55, stunTicks: 6 } },
  meteor: { name: 'Meteor Battery', short: 'METEOR', role: 'Bombardment', family: 'Artillery', specialty: 'Wide blast', cost: 245, range: 180, damage: 182, cooldown: 39, color: '#f4cc83', description: 'Huge blasts hit an entire crowd, with the strongest impact at the center.', unlockLevel: 16, shopExclusive: false, effect: { kind: 'meteor', splash: 88, edgeDamage: .35 } },
  venom: { name: 'Venom Vat', short: 'VENOM', role: 'Poison', family: 'Control', specialty: 'Stacking poison', cost: 115, range: 132, damage: 9, cooldown: 12, color: '#a7e06d', description: 'Poisons enemies over time. Up to three doses can stack.', unlockLevel: 3, shopExclusive: false, effect: { kind: 'poison', duration: 35, tickDamage: .12, stacks: 3 } },
  glacier: { name: 'Glacier Array', short: 'GLACIER', role: 'Chain chill', family: 'Control', specialty: 'Chained chill', cost: 160, range: 134, damage: 11, cooldown: 17, color: '#b5e8ff', description: 'Chills up to three enemies in a chain, slowing them more than Cold Wallet.', unlockLevel: 7, shopExclusive: false, effect: { kind: 'chainSlow', targets: 3, factor: .32, duration: 24 } },
  disruptor: { name: 'Signal Disruptor', short: 'DISRUPT', role: 'Weakening', family: 'Control', specialty: 'Core protection', cost: 150, range: 150, damage: 22, cooldown: 15, color: '#71c9b7', description: 'Weakens dangerous enemies so they deal less damage if they reach the core.', unlockLevel: 8, shopExclusive: false, effect: { kind: 'weaken', reduction: .4, duration: 55 } },
  storm: { name: 'Storm Relay', short: 'STORM', role: 'Chain stun', family: 'Control', specialty: 'Chain stun', cost: 185, range: 142, damage: 28, cooldown: 19, color: '#a3a3fa', description: 'Electric arcs briefly stun two enemies. Bosses recover faster.', unlockLevel: 11, shopExclusive: false, effect: { kind: 'chainStun', targets: 2, stunTicks: 5 } },
  stasis: { name: 'Stasis Chamber', short: 'STASIS', role: 'Slow field', family: 'Control', specialty: 'Deep slow field', cost: 195, range: 150, damage: 10, cooldown: 21, color: '#8adfdc', description: 'Creates a deep slowing field around its target. Bosses resist the strongest chill.', unlockLevel: 15, shopExclusive: false, effect: { kind: 'fieldSlow', splash: 53, factor: .18, duration: 16 } },
  laser: { name: 'Focus Laser', short: 'FOCUS', role: 'Focused beam', family: 'Energy', specialty: 'Sustained damage ramp', cost: 175, range: 155, damage: 21, cooldown: 7, color: '#ff8b9e', description: 'Deals increasing damage while it keeps firing at the same target.', unlockLevel: 7, shopExclusive: false, effect: { kind: 'ramp', step: .22, stacks: 6 } },
  railgun: { name: 'Titan Railgun', short: 'TITAN', role: 'Boss hunter', family: 'Energy', specialty: 'Boss priority', targeting: 'boss', cost: 225, range: 208, damage: 102, cooldown: 23, color: '#e8d296', description: 'Prioritizes bosses, deals bonus boss damage and pierces armor.', unlockLevel: 1, shopExclusive: true, effect: { kind: 'boss', bossMultiplier: 2.4, armorPierce: .75 } },
  singularity: { name: 'Singularity Well', short: 'GRAVITY', role: 'Gravity', family: 'Energy', specialty: 'Gravity pull', cost: 240, range: 162, damage: 44, cooldown: 25, color: '#ac8de8', description: 'Pulls a cluster backward along the road. Brief immunity prevents permanent trapping.', unlockLevel: 17, shopExclusive: false, effect: { kind: 'gravity', splash: 47, pull: 28, immunity: 36 } },
  plasma: { name: 'Plasma Crucible', short: 'PLASMA', role: 'Death bursts', family: 'Energy', specialty: 'Explosive death marks', cost: 220, range: 155, damage: 64, cooldown: 22, color: '#ee92d5', description: 'Marks enemies to explode when defeated, damaging nearby threats.', unlockLevel: 18, shopExclusive: false, effect: { kind: 'deathMark', duration: 45, explosionDamage: .8, splash: 45 } },
  mint: { name: 'Orb Mint', short: 'MINT', role: 'Economy', family: 'Support', specialty: 'Capped Orb income', targeting: 'support', cost: 150, range: 0, damage: 0, cooldown: 30, color: '#7ae9b6', description: 'Produces battle Orbs. Each slot has a production limit; the whole level is capped at 300 Orbs.', unlockLevel: 5, shopExclusive: false, effect: { kind: 'income', amount: 8, perSlotCap: 120, teamCap: 300 } },
  scanner: { name: 'Weakpoint Scanner', short: 'SCAN', role: 'Vulnerability', family: 'Support', specialty: 'Weakpoint marks', cost: 145, range: 180, damage: 0, cooldown: 16, color: '#a1e8ef', description: 'Marks an enemy so every tower deals more direct damage to it.', unlockLevel: 9, shopExclusive: false, effect: { kind: 'expose', bonus: .24, duration: 30 } },
  accelerator: { name: 'Overdrive Beacon', short: 'HASTE', role: 'Attack speed', family: 'Support', specialty: 'Attack speed aura', targeting: 'support', cost: 155, range: 174, damage: 0, cooldown: 10, color: '#69ded9', description: 'Accelerates nearby weapons. Multiple beacons use the strongest aura rather than stacking.', unlockLevel: 12, shopExclusive: false, effect: { kind: 'haste', bonus: .14, cap: .5 } },
  sunforge: { name: 'Sunforge Mortar', short: 'SUNFORGE', role: 'Airburst', family: 'Artillery', specialty: 'Scorching splash', cost: 225, range: 194, damage: 82, cooldown: 32, color: '#ffad58', description: 'A wide solar airburst scorches clustered enemies. Cannot fire inside its inner dead zone.', unlockLevel: 1, shopExclusive: true, effect: { kind: 'scorch', minRange: 64, splash: 70, duration: 24, tickDamage: .025 } },
  phase_lancer: { name: 'Phase Lancer', short: 'PHASE', role: 'Precision', family: 'Assault', specialty: 'Line piercing', targeting: 'strongest', cost: 205, range: 205, damage: 108, cooldown: 25, color: '#72beff', description: 'Targets the toughest enemy. Its armor-piercing lance hits up to two more enemies lined up behind it.', unlockLevel: 1, shopExclusive: true, effect: { kind: 'linePierce', targets: 3, lineWidth: 15, secondaryDamage: .62, armorPierce: .82 } },
  cryo_anchor: { name: 'Cryo Anchor', short: 'CRYO', role: 'Interception', family: 'Control', specialty: 'Fastest target lock', targeting: 'fastest', cost: 175, range: 145, damage: 12, cooldown: 16, color: '#afc7ff', description: 'Finds the fastest threat in range and locks it in a deep chill. Bosses resist its strongest slow.', unlockLevel: 1, shopExclusive: true, effect: { kind: 'anchorSlow', factor: .18, duration: 24 } },
  aurora_core: { name: 'Aurora Core', short: 'AURORA', role: 'Recovery', family: 'Support', specialty: 'Anti-jam recovery pulse', targeting: 'support', cost: 180, range: 180, damage: 0, cooldown: 33, color: '#7ef1d1', description: 'Pulses to help up to two nearby weapons fire sooner, prioritizing and clearing jammed weapons. Assistance cannot stack.', unlockLevel: 1, shopExclusive: true, effect: { kind: 'cleanse', targets: 2, advance: 5, assistCooldown: 24 } },
  gilded_ballista: { name: 'Gilded Ballista', short: 'BALLISTA', role: 'Precision', family: 'Assault', specialty: 'Torsion bolt', targeting: 'strongest', cost: 218, range: 211, damage: 135, cooldown: 26, color: '#f5cc7b', description: 'A torsion bow drives a heavy bolt through almost all of the toughest enemy’s armor.', unlockLevel: 1, shopExclusive: true, effect: { kind: 'sniper', armorPierce: .94 } },
  monsoon_battery: { name: 'Monsoon Battery', short: 'MONSOON', role: 'Rocket salvo', family: 'Artillery', specialty: 'Cluster rockets', cost: 215, range: 191, damage: 114, cooldown: 30, color: '#80d7c7', description: 'A cluster salvo bursts over a wide area, with damage tapering toward the edge. Cannot launch at enemies in its inner dead zone.', unlockLevel: 1, shopExclusive: true, effect: { kind: 'meteor', minRange: 54, splash: 59, edgeDamage: .65 } },
  thorn_harvester: { name: 'Thorn Harvester', short: 'THORN', role: 'Armor break', family: 'Assault', specialty: 'Rotary scythes', cost: 177, range: 127, damage: 20, cooldown: 9, color: '#b9db79', description: 'Twin scythes strip armor in heavy cuts. Follow-up hits from any tower exploit the weakened plating.', unlockLevel: 1, shopExclusive: true, effect: { kind: 'shred', armorBreak: .102, maxArmorBreak: .34, duration: 35 } },
  magnetar_array: { name: 'Magnetar Array', short: 'MAGNETAR', role: 'Gravity', family: 'Energy', specialty: 'Magnetic recoil', cost: 226, range: 169, damage: 46, cooldown: 23, color: '#e3a4f7', description: 'A magnetic pulse pulls a wide cluster backward. Targets gain a brief resistance to further pulls.', unlockLevel: 1, shopExclusive: true, effect: { kind: 'gravity', splash: 52, pull: 20, immunity: 30 } },
  tidal_obelisk: { name: 'Tidal Obelisk', short: 'TIDAL', role: 'Slow field', family: 'Control', specialty: 'Undertow field', cost: 190, range: 161, damage: 14, cooldown: 19, color: '#83def7', description: 'An undertow sweeps clustered enemies into a lingering slow field. Bosses resist its strongest drag.', unlockLevel: 1, shopExclusive: true, effect: { kind: 'fieldSlow', splash: 49, factor: .28, duration: 20 } },
  circuit_weaver: { name: 'Circuit Weaver', short: 'WEAVER', role: 'Chain stun', family: 'Energy', specialty: 'Three-way arc', cost: 208, range: 153, damage: 26, cooldown: 21, color: '#a7ffb3', description: 'A loom threads electricity through up to three enemies and briefly stuns each. Bosses recover faster.', unlockLevel: 1, shopExclusive: true, effect: { kind: 'chainStun', targets: 3, stunTicks: 4 } },
  bulwark_beacon: { name: 'Bulwark Beacon', short: 'BULWARK', role: 'Core protection', family: 'Support', specialty: 'Interceptor signal', cost: 165, range: 178, damage: 9, cooldown: 16, color: '#ffad9e', description: 'Long-range interference weakens a target so it deals less damage if it reaches the core.', unlockLevel: 1, shopExclusive: true, effect: { kind: 'weaken', reduction: .44, duration: 46 } },
  nova_siphon: { name: 'Nova Siphon', short: 'SIPHON', role: 'Economy', family: 'Support', specialty: 'Quick Orb production', targeting: 'support', cost: 135, range: 0, damage: 0, cooldown: 28, color: '#ffc974', description: 'Compresses energy into battle Orbs. It fills its smaller production allowance quickly and shares the 300-Orb level cap.', unlockLevel: 1, shopExclusive: true, effect: { kind: 'income', amount: 10, perSlotCap: 98, teamCap: 300 } }
});

const SECTORS = ['Genesis Gardens', 'Neon Crossing', 'Ember Circuit', 'Obsidian Vault'];
const SUBLEVELS = ['Outer Gate', 'Uplink', 'Pressure Point', 'Siege Line', 'Core Assault'];
export const CAMPAIGN_LEVELS = Object.freeze(Array.from({ length: 20 }, (_, index) => {
  const id = index + 1;
  return Object.freeze({ id, name: `${SECTORS[Math.floor(index / 5)]} · ${SUBLEVELS[index % 5]}`,
    sector: SECTORS[Math.floor(index / 5)], map: Math.floor(index / 5), waves: 4 + id,
    hpScale: Number((1.2 ** index).toFixed(4)), speedScale: Number((1 + index * 0.018).toFixed(3)),
    startOrbs: 220 + Math.floor(index / 5) * 20, firstClearCoins: 55 + id * 15,
    boss: id % 5 === 0 ? 'Citadel Colossus' : '51% Attacker' });
}));
export function getLevel(id = 1) {
  return CAMPAIGN_LEVELS.find((level) => level.id === Number(id)) || null;
}
export function getUpgradePrice(currentLevel) {
  if (!Number.isInteger(currentLevel) || currentLevel < 1 || currentLevel >= 30) return null;
  return Math.ceil(35 * 1.28 ** (currentLevel - 1));
}
// Rules version 2 extends progression without changing any historical level or
// upgrade-price snapshot. New challenges explicitly choose these definitions.
export const CAMPAIGN_LEVELS_V2 = Object.freeze(Array.from({ length: 100 }, (_, index) => {
  const id = index + 1, sectorIndex = Math.floor(index / 5) % SECTORS.length;
  return Object.freeze({ id, name: `${SECTORS[sectorIndex]} · ${SUBLEVELS[index % 5]}`,
    sector: SECTORS[sectorIndex], map: sectorIndex,
    waves: id <= 20 ? 4 + id : 24 + Math.ceil((id - 20) / 8),
    hpScale: Number((index < 20 ? 1.2 ** index : 1.2 ** 19 * 1.11 ** (id - 20)).toFixed(4)), speedScale: Number((1 + index * 0.018).toFixed(3)),
    startOrbs: 220 + Math.min(80, Math.floor(index / 5) * 20), firstClearCoins: 10 + Math.floor(id / 10) * 5,
    boss: id % 5 === 0 ? 'Citadel Colossus' : '51% Attacker' });
}));
// Layout six gives every five-level sector its own world. Keep the complete
// released V2 definitions above untouched for historical battles and clients.
export const CAMPAIGN_LEVELS_V3 = Object.freeze(CAMPAIGN_LEVELS_V2.map((level,index)=>{
  if(index<20)return level;
  const map=Math.floor(index/5),world=CAMPAIGN_WORLDS[map-4];
  if(!world)throw new Error('Campaign world metadata is incomplete.');
  return Object.freeze({...level,map,sector:world.name,name:`${world.name} · ${SUBLEVELS[index%5]}`});
}));
export function getCampaignLevels(mapLayoutVersion=MAP_LAYOUT_VERSION){
  if(![1,2,3,4,5,6].includes(mapLayoutVersion))throw new RangeError('Unknown campaign layout.');
  return mapLayoutVersion>=6?CAMPAIGN_LEVELS_V3:CAMPAIGN_LEVELS_V2;
}
export function getCampaignLevel(id = 1,mapLayoutVersion=MAP_LAYOUT_VERSION) {
  return getCampaignLevels(mapLayoutVersion).find(level => level.id === Number(id)) || null;
}
// A map key is the first level in its five-level sector. Unlike combat level
// lookup, this helper can describe all twenty physical maps for layout six.
export function getMapLevel(id=1,mapLayoutVersion=MAP_LAYOUT_VERSION){
  if(mapLayoutVersion>=6)return getCampaignLevel(id,mapLayoutVersion);
  return getLevel(id);
}
export function getModernUpgradePrice(currentLevel) {
  if (!Number.isInteger(currentLevel) || currentLevel < 1 || currentLevel >= 100) return null;
  return Math.ceil(35 * 1.12 ** (currentLevel - 1));
}
export const MODERN_TOWER_UNLOCK_LEVELS = Object.freeze({
  pulse: 1, arc: 1, repeater: 1, frost: 1, firewall: 1, validator: 1,
  venom: 15, scanner: 30, disruptor: 50, scatter: 5, sniper: 5,
  glacier: 10, shredder: 10, howitzer: 10, mint: 10,
  block: 15, minefield: 15, laser: 15, storm: 20, accelerator: 20,
  seismic: 25, stasis: 30, meteor: 40, executioner: 45,
  singularity: 60, plasma: 75,
  prism: 1, railgun: 1, sunforge: 1, phase_lancer: 1, cryo_anchor: 1, aurora_core: 1,
  gilded_ballista: 1, monsoon_battery: 1, thorn_harvester: 1, magnetar_array: 1,
  tidal_obelisk: 1, circuit_weaver: 1, bulwark_beacon: 1, nova_siphon: 1
});
// Historical pre-0.13 definition, retained for old receipt fixtures. The active
// store, prices, tower pools and new draws are defined in chest-data.js.
export const CHEST = Object.freeze({
  id: 'supply', name: 'Supply Chest', cost: 120,
  description: 'One unlocked, non-exclusive tower. Duplicate copies can be fused.',
  odds: Object.freeze([
    { rarity: 'common', weight: 7000 }, { rarity: 'uncommon', weight: 2200 },
    { rarity: 'rare', weight: 650 }, { rarity: 'epic', weight: 130 },
    { rarity: 'legendary', weight: 19 }, { rarity: 'mythic', weight: 1 }
  ])
});
export function createStarterContext() {
  return { level: 1, mapLayoutVersion: MAP_LAYOUT_VERSION, towers: [{ type: 'pulse', level: 1, rarity: 'common' }, { type: 'arc', level: 1, rarity: 'common' }] };
}
