import {CORE_TOWER_PATHS} from './tower-paths-core.js';
import {SPECIALIST_TOWER_PATHS} from './tower-paths-specialists.js';

export const THEMED_TOWER_PATHS = Object.freeze({...CORE_TOWER_PATHS,...SPECIALIST_TOWER_PATHS});
const cache = new WeakMap();
const statDefaults = {
  damage:1, fireRate:1, range:1, support:1,
  hitTargets:1, secondaryDamage:.65, armorPierce:0, hitStunTicks:0,
  hitSlowFactor:1, hitSlowDuration:0, bossDamageMultiplier:1,
  burnDamageRatio:.025, chainDamageRatio:.72, legacySplash:65,
  burnDuration:18, frostDuration:25, extraTargets:0
};
const effectBounds = {
  armorPierce:[0,1], factor:[.08,1], angle:[0,1.5], threshold:[0,.36],
  edgeDamage:[0,1], minRange:[0,Infinity], armTicks:[1,Infinity],
  immunity:[1,Infinity], assistCooldown:[1,Infinity], criticalEvery:[2,Infinity],
  reduction:[0,.6], maxArmorBreak:[0,.55], poisonSpreadDamage:[0,1],
  secondaryDamage:[0,1]
};
const clamp = (n,min,max) => Math.max(min,Math.min(max,n));
const number = new Intl.NumberFormat('en-US',{maximumFractionDigits:2});
const pct = value => number.format(value*100)+'%';
const seconds = value => number.format(value/10)+'s';
const units = value => number.format(value);

export function themedTowerModifiers(type,definition,tiers) {
  let tiersByDefinition = cache.get(definition);
  if (!tiersByDefinition) cache.set(definition,tiersByDefinition=new Map());
  const key = type+':'+[tiers.power,tiers.tempo,tiers.reach].join(',');
  const saved = tiersByDefinition.get(key);
  if (saved) return saved;

  const original = definition.effect;
  const haste = original?.kind==='haste';
  const stats = {...statDefaults,damageAura:type==='validator'?.18:0,hasteAura:haste?original.bonus:0,
    hasteCap:type==='validator'?.3:haste?original.cap:0};
  const effect = original ? {...original} : undefined;
  const paths = THEMED_TOWER_PATHS[type];
  for (const [path,tier] of Object.entries(tiers)) {
    for (const [,deltas] of paths[path][2].slice(0,tier)) {
      for (const [stat,value] of Object.entries(deltas)) {
        if (stat==='effect') {
          for (const [key,delta] of Object.entries(value)) effect[key]=(effect[key]??0)+delta;
        } else stats[stat]+=value;
      }
    }
  }
  if (effect) {
    for (const [stat,bounds] of Object.entries(effectBounds)) {
      if (stat in effect) effect[stat]=clamp(effect[stat],...bounds);
    }
    Object.freeze(effect);
  }
  const {damage,fireRate,range,support,...special} = stats;
  const result = Object.freeze({
    ...special,effect,range:definition.range*range,cooldown:Math.max(1,Math.round(definition.cooldown/fireRate)),
    damageMultiplier:damage,supportMultiplier:support,armorPierce:clamp(stats.armorPierce,0,1),
    hitSlowFactor:clamp(stats.hitSlowFactor,.08,1),hasteCap:clamp(stats.hasteCap,0,.65),
    secondaryDamage:clamp(stats.secondaryDamage,0,1),chainDamageRatio:clamp(stats.chainDamageRatio,0,1)
  });
  tiersByDefinition.set(key,result);
  return result;
}

const specialLabels = {
  armorPierce:['Armor bypass',pct], bossDamageMultiplier:['Boss damage',pct],
  hitTargets:['Targets per shot',units], secondaryDamage:['Extra shot damage',pct],
  hitStunTicks:['Hit stun',seconds], hitSlowFactor:['Movement speed while slowed',pct],
  hitSlowDuration:['Hit slow duration',seconds], burnDamageRatio:['Burn damage per tick',pct],
  chainDamageRatio:['Damage on each jump',pct], legacySplash:['Blast radius',units],
  burnDuration:['Burn duration',seconds], frostDuration:['Chill duration',seconds],
  extraTargets:['Extra chain targets',units], damageAura:['Base allied damage bonus',pct],
  hasteAura:['Base allied haste',pct], hasteCap:['Allied haste cap',pct]
};
const effectLabels = {
  duration:['Effect duration',seconds], tickDamage:['Damage per tick',pct], stacks:['Stack limit',units],
  armorPierce:['Armor bypass',pct], armorBreak:['Armor stripped per hit',pct],
  maxArmorBreak:['Maximum armor stripped',pct], factor:['Movement speed while slowed',pct],
  splash:['Effect radius',units], minRange:['Minimum range',units], targets:['Targets',units],
  angle:['Spread angle',radians=>units(radians*180/Math.PI)+'°'],
  criticalEvery:['Shots per critical hit',units], criticalMultiplier:['Critical hit damage',pct],
  threshold:['Execute threshold',pct], bossMultiplier:['Boss hit multiplier',pct],
  armTicks:['Mine arming time',seconds], limit:['Active mines',units],
  triggerRadius:['Mine trigger radius',units], lifetime:['Mine lifetime',seconds],
  stunTicks:['Stun duration',seconds], edgeDamage:['Blast damage at edge',pct],
  reduction:['Leak damage reduction',pct], step:['Damage bonus per focus stack',pct],
  pull:['Pull distance',units], immunity:['Time before next pull',seconds],
  explosionDamage:['Death burst damage',pct], amount:['Orbs per batch',units],
  perSlotCap:['Orbs per tower',units], bonus:['Base damage taken bonus',pct],
  lineWidth:['Piercing line width',units], secondaryDamage:['Piercing damage',pct],
  advance:['Cooldown reduction on assist',seconds], assistCooldown:['Time between assists on each tower',seconds]
};

function describeTier(type,definition,tiers,path,tier) {
  const before = themedTowerModifiers(type,definition,{...tiers,[path]:tier-1});
  const after = themedTowerModifiers(type,definition,{...tiers,[path]:tier});
  const changes = [];
  if (before.damageMultiplier!==after.damageMultiplier) changes.push('+'+pct(after.damageMultiplier-before.damageMultiplier)+' base hit damage');
  if (before.cooldown!==after.cooldown) {
    const interval = definition.effect?.kind==='income'?'Orb batch interval':definition.damage?'Attack interval':'Support interval';
    changes.push(interval+' '+seconds(before.cooldown)+' → '+seconds(after.cooldown));
  }
  if (before.range!==after.range) changes.push('Range '+units(before.range)+' → '+units(after.range));
  if (before.supportMultiplier!==after.supportMultiplier) changes.push('+'+pct(after.supportMultiplier-before.supportMultiplier)+' base effect strength');

  for (const [stat,[label,format]] of Object.entries(specialLabels)) {
    if (before[stat]!==after[stat]) changes.push(label+' '+format(before[stat])+' → '+format(after[stat]));
  }
  const a = before.effect, b = after.effect;
  if (a && b) {
    if (a.poisonSpreadTargets!==b.poisonSpreadTargets || a.poisonSpreadRadius!==b.poisonSpreadRadius || a.poisonSpreadDamage!==b.poisonSpreadDamage) {
      const targetText = b.poisonSpreadTargets===1?'enemy':'enemies';
      changes.push('Poison spreads to '+b.poisonSpreadTargets+' nearby '+targetText+' within '+units(b.poisonSpreadRadius)+' range at '+pct(b.poisonSpreadDamage)+' strength');
    }
    for (const [stat,[label,format]] of Object.entries(effectLabels)) {
      if (a[stat]!==b[stat]) changes.push(label+' '+format(a[stat]??0)+' → '+format(b[stat]??0));
    }
  }
  return changes.join(' · ');
}

export function themedPathChoice(type,definition,tiers,path,energy,cap,reason,baseCosts,priceScale) {
  const [name,description,steps] = THEMED_TOWER_PATHS[type][path];
  const tier = tiers[path];
  const nextTier = reason ? null : tier+1;
  const cost = nextTier===null ? null : Math.ceil(definition.cost*baseCosts[tier]*priceScale*(steps[tier][2]??1));
  return {
    path,name,description,tier,nextTier,cap,cost,reason,themed:true,affordable:cost!==null&&energy>=cost,
    nextName:nextTier===null?null:steps[tier][0],
    nextDetail:nextTier===null?null:describeTier(type,definition,tiers,path,nextTier)
  };
}
