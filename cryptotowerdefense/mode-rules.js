// Public rules are shared with authoritative replay. Amounts here are game
// shares and percentages; they are never a funded crypto balance.
export const MODE_RULES_VERSION = 2;
export const DAY_MS = 86_400_000;
export const WEEK_MS = 7 * DAY_MS;
export const MODE_IDS = Object.freeze(['campaign', 'daily', 'weekly']);
export const STANDARD_ATTEMPTS = Object.freeze({ daily: 3, weekly: 10 });
export const PREMIUM_ATTEMPTS = Object.freeze({ daily: 5, weekly: 15 });
export const MAX_MODERN_TOWER_LEVEL = 100;
export const MAX_CAMPAIGN_BONUS_BPS = 2000;
export const CAMPAIGN_MILESTONE_STEP = 5;
const MONDAY_EPOCH = 4 * DAY_MS;
const themes = [
  ['rapid-response', 'Rapid Response', 'Assault'],
  ['arc-storm', 'Arc Storm', 'Energy'],
  ['frozen-frontier', 'Frozen Frontier', 'Control'],
  ['heavy-industry', 'Heavy Industry', 'Artillery'],
  ['network-synergy', 'Network Synergy', 'Support']
];
export const CHALLENGE_THEMES = Object.freeze(themes.map(([id, name, family]) => Object.freeze({
  id, name, favoredFamilies: Object.freeze([family]), damageBps: 2500, cooldownBps: 1000
})));
export const CAMPAIGN_TOWER_MILESTONES = Object.freeze([
  Object.freeze({ level: 5, type: 'frost', rarity: 'common' }),
  Object.freeze({ level: 15, type: 'venom', rarity: 'common' }),
  Object.freeze({ level: 30, type: 'scanner', rarity: 'common' }),
  Object.freeze({ level: 50, type: 'disruptor', rarity: 'common' })
]);
function challengeMode(mode) {
  if (mode !== 'daily' && mode !== 'weekly') throw new RangeError('Choose a daily or weekly challenge.');
}
export function getModePeriod(mode, now = Date.now()) {
  challengeMode(mode);
  if (!Number.isSafeInteger(now) || now < 0) throw new RangeError('Invalid challenge time.');
  const duration = mode === 'daily' ? DAY_MS : WEEK_MS;
  const offset = mode === 'daily' ? 0 : MONDAY_EPOCH;
  const periodStart = Math.floor((now - offset) / duration) * duration + offset;
  const periodEnd = periodStart + duration;
  return { mode, periodStart, periodEnd, periodKey: new Date(periodStart).toISOString().slice(0, 10) };
}
export function getModeChallenge(mode, now = Date.now()) {
  const period = getModePeriod(mode, now);
  const duration = mode === 'daily' ? DAY_MS : WEEK_MS;
  const ordinal = Math.floor(period.periodStart / duration);
  const positive = (value, modulus) => ((value % modulus) + modulus) % modulus;
  const theme = CHALLENGE_THEMES[positive(ordinal + (mode === 'weekly' ? 2 : 0), CHALLENGE_THEMES.length)];
  const mapLevel = [1, 6, 11, 16][positive(ordinal + (mode === 'weekly' ? 1 : 0), 4)];
  return { ...period, mapLevel, theme, startOrbs: mode === 'weekly' ? 300 : 260 };
}
export function getAttemptLimit(mode, premium = false) {
  challengeMode(mode);
  return (premium === true ? PREMIUM_ATTEMPTS : STANDARD_ATTEMPTS)[mode];
}
export function getCampaignBonus(clearedLevel) {
  if (!Number.isInteger(clearedLevel) || clearedLevel < 0 || clearedLevel > 100) throw new RangeError('Invalid campaign progress.');
  return Math.min(MAX_CAMPAIGN_BONUS_BPS, Math.floor(clearedLevel / CAMPAIGN_MILESTONE_STEP) * 100);
}
export function calculateWaveShares(wavesCleared) {
  if (!Number.isSafeInteger(wavesCleared) || wavesCleared < 0 || wavesCleared > Math.floor(Math.sqrt(Number.MAX_SAFE_INTEGER))) {
    throw new RangeError('Invalid cleared wave count.');
  }
  return wavesCleared * wavesCleared;
}
