import {themedPathChoice,themedTowerModifiers} from './themed-tower-upgrades.js';

export const UPGRADE_PATH_ENGINE_VERSION = 6;
export const THEMED_UPGRADE_ENGINE_VERSION = 7;
export const UPGRADE_PATHS = Object.freeze(['power','tempo','reach']);
export const EMPTY_UPGRADE_TIERS = Object.freeze({power:0,tempo:0,reach:0});

const NAMES = {
  pulse:['Pulse Amplifier','Rapid Capacitor','Wideband Pulse'],
  arc:['High Voltage','Oscillator','Chain Network'],
  frost:['Absolute Chill','Cryo Cycle','Glacier Spread'],
  firewall:['Plasma Fuel','Fast Ignition','Burn Radius'],
  block:['Dense Payload','Breech Loader','Long Barrel'],
  validator:['Authority','Fast Consensus','Wide Broadcast'],
  prism:['Prism Focus','Optical Clock','Spectral Fan'],
  repeater:['Critical Bolts','Burst Governor','Longburst'],
  sniper:['Armor Punch','Smooth Bolt','Long Glass'],
  scatter:['Heavy Pellets','Auto Chamber','Wide Choke'],
  shredder:['Corrosive Teeth','Twin Rotors','Stripper Array'],
  executioner:['Final Judgment','Quick Draw','Far Verdict'],
  howitzer:['Siege Charge','Auto Loader','High Elevation'],
  minefield:['Shaped Charges','Fast Fuse','Mine Network'],
  seismic:['Deep Tremor','Pulse Driver','Fault Line'],
  meteor:['Dense Core','Rapid Descent','Crater Field'],
  venom:['Potent Toxin','Fast Infusion','Dispersal Nozzles'],
  glacier:['Deep Freeze','Cold Cycle','Chill Chain'],
  disruptor:['Signal Crush','Fast Interference','Long Signal'],
  storm:['Thunderhead','Flash Cycle','Lightning Mesh'],
  stasis:['Time Lock','Field Cycling','Extended Stasis'],
  laser:['Beam Convergence','Rapid Refocus','Long Focus'],
  railgun:['Bossbreaker','Rail Charge','Extreme Calibration'],
  singularity:['Mass Driver','Fast Collapse','Event Horizon'],
  plasma:['Volatile Mark','Crucible Feed','Cascade Radius'],
  mint:['Dense Minting','Fast Stamps','Orb Vault'],
  scanner:['Weakpoint Insight','Scan Cycle','Wide Spectrum'],
  accelerator:['Drive Reinforcement','Clock Boost','Grid Coverage'],
  sunforge:['Solar Payload','Quick Furnace','Solar Corona'],
  phase_lancer:['Phase Fracture','Lance Reset','Phase Corridor'],
  cryo_anchor:['Deep Lock','Anchor Cycle','Long Intercept'],
  aurora_core:['Recovery Surge','Pulse Recovery','Aurora Field'],
  gilded_ballista:['Gilded Bolt','Torsion Reset','Long Bow'],
  monsoon_battery:['Cyclone Charge','Rapid Salvo','Storm Coverage'],
  thorn_harvester:['Razor Bloom','Scythe Speed','Thorn Reach'],
  magnetar_array:['Magnetic Crush','Field Reset','Magnetic Halo'],
  tidal_obelisk:['Deep Undertow','Tidal Cycle','Flood Radius'],
  circuit_weaver:['High Current','Switching Speed','Woven Grid'],
  bulwark_beacon:['Ward Strength','Fast Intercept','Outer Perimeter'],
  nova_siphon:['Dense Compression','Fast Intake','Nova Reservoir']
};
const POWER = [1,1.65,2.38,3.4,4.7,6.3];
const SPEED = [1,.75,.58,.46,.34,.24];
const TEMPO_DAMAGE = [1,1.02,1.05,1.12,1.23,1.37];
const RANGE = [1,1.14,1.28,1.47,1.68,1.93];
const AREA = [1,1.12,1.24,1.39,1.57,1.78];
const SUPPORT = [1,1.23,1.47,1.78,2.14,2.6];
const TARGETS = [0,0,1,1,2,3];
const INCOME = [0,3,7,12,19,28];
const CAPACITY = [0,24,48,80,120,170];
const COST = [.84,1.16,1.72,3.2,5.1];
const PATH_PRICE = {power:1,tempo:.92,reach:.8};

function strengthWeight(type,definition,path) {
  const effect=definition.effect,kind=effect?.kind;
  const aura=type==='validator'||kind==='haste',wide=aura||effect?.splash||effect?.targets||['arc','prism','firewall'].includes(type);
  if(path==='power')return wide?1.13:kind==='income'?1.05:1;
  if(path==='tempo')return aura||kind==='cleanse'?1.18:definition.cooldown<=6?.9:1;
  return wide||kind==='income'?1.12:.85;
}

export function validUpgradeTiers(tiers) {
  return tiers&&typeof tiers==='object'&&Object.keys(tiers).length===3&&
    UPGRADE_PATHS.every(path=>Number.isInteger(tiers[path])&&tiers[path]>=0&&tiers[path]<=5)&&
    UPGRADE_PATHS.filter(path=>tiers[path]>0).length<=2&&UPGRADE_PATHS.filter(path=>tiers[path]>2).length<=1;
}

function detail(type,definition,path,tier) {
  const kind=definition.effect?.kind;
  if(kind==='income') {
    return {
      power:['Increase the Orbs produced in each batch.',`+${INCOME[tier]} Orbs per batch before permanent bonuses`],
      tempo:['Produce Orb batches more often.',`Production interval ×${SPEED[tier]}`],
      reach:['Increase this generator’s capacity. The level cap stays at 300 Orbs.',`+${CAPACITY[tier]} Orbs of base capacity`]
    }[path];
  }
  if(type==='validator') {
    return {
      power:['Boost the damage granted to nearby weapons.',`Damage aura strength ×${SUPPORT[tier]}`],
      tempo:['Add attack-speed support for nearby weapons.',`+${tier*6}% base attack-speed aura`],
      reach:['Extend the radius of both support effects.',`Aura radius ×${RANGE[tier]}`]
    }[path];
  }
  if(kind==='haste') {
    return {
      power:['Grant nearby weapons extra damage.',`+${tier*5}% base damage aura`],
      tempo:['Strengthen the attack-speed aura.',`Attack-speed aura strength ×${SUPPORT[tier]}`],
      reach:['Extend the radius of both support effects.',`Aura radius ×${RANGE[tier]}`]
    }[path];
  }
  const support=['expose','cleanse'].includes(kind);
  if(path==='power')return [
    support?'Strengthen this tower’s support effect.':kind||['frost','firewall'].includes(type)?'Increase hit damage and strengthen the tower’s specialty.':'Increase direct hit damage.',
    support?`Support power ×${SUPPORT[tier]}`:`Hit damage ×${POWER[tier]} before other boosts`
  ];
  if(path==='tempo')return [
    support?'Trigger support effects more frequently.':'Shorten the time between attacks and add a small damage bonus.',
    `Base interval ×${SPEED[tier]}`
  ];
  return [
    definition.effect?.splash||type==='firewall'?'Extend attack range and enlarge the affected area.':definition.effect?.targets||['arc','prism'].includes(type)?'Extend range and gain extra targets at higher tiers.':'Extend effective targeting range.',
    `Range ×${RANGE[tier]}`
  ];
}

export function getPathChoice(type,definition,tiers,path,energy,engineVersion=UPGRADE_PATH_ENGINE_VERSION) {
  if(!definition||!UPGRADE_PATHS.includes(path))return null;
  const tier=tiers[path];
  const chosen=UPGRADE_PATHS.filter(key=>tiers[key]>0);
  const primary=UPGRADE_PATHS.find(key=>tiers[key]>2);
  const cap=primary&&primary!==path?2:5;
  const reason=chosen.length===2&&tier===0?'Only two paths can be used on one tower.':
    tier>=cap?(cap===2?'The secondary path stops at Tier 2.':'Maximum tier reached.'):null;
  if(engineVersion>=THEMED_UPGRADE_ENGINE_VERSION) {
    return themedPathChoice(type,definition,tiers,path,energy,cap,reason,COST,PATH_PRICE[path]*strengthWeight(type,definition,path));
  }
  const cost=reason?null:Math.ceil(definition.cost*COST[tier]*PATH_PRICE[path]*strengthWeight(type,definition,path));
  const [description,nextDetail]=detail(type,definition,path,Math.min(5,tier+1));
  return {
    path,name:(NAMES[type]||['Power','Tempo','Reach'])[UPGRADE_PATHS.indexOf(path)],description,
    tier,nextTier:reason?null:tier+1,cap,cost,reason,nextDetail:reason?null:nextDetail,affordable:cost!==null&&energy>=cost
  };
}

export function pathTowerModifiers(type,definition,tiers,engineVersion=UPGRADE_PATH_ENGINE_VERSION) {
  if(engineVersion>=THEMED_UPGRADE_ENGINE_VERSION) return themedTowerModifiers(type,definition,tiers);
  const {power,tempo,reach}=tiers;
  const original=definition.effect;
  const kind=original?.kind;
  const effect=original&&power+tempo+reach>0?{...original}:original;
  if(effect&&effect!==original) {
    if(effect.splash)effect.splash*=AREA[reach];
    if(effect.minRange)effect.minRange*=1-reach*.13;
    if(effect.targets)effect.targets+=TARGETS[reach];
    if(effect.angle)effect.angle=Math.min(1.5,effect.angle+reach*.105);
    if(effect.lineWidth)effect.lineWidth*=AREA[reach];
    if(effect.duration)effect.duration+=power*3;
    if(effect.factor)effect.factor=Math.max(.08,effect.factor-power*.025);
    if(effect.stunTicks)effect.stunTicks+=power*2;
    if(effect.tickDamage)effect.tickDamage*=1+power*.12;
    if(effect.armorPierce)effect.armorPierce=Math.min(1,effect.armorPierce+power*.035);
    if(effect.maxArmorBreak)effect.maxArmorBreak=Math.min(.55,effect.maxArmorBreak+power*.04);
    if(effect.edgeDamage)effect.edgeDamage=Math.min(.92,effect.edgeDamage+power*.055);
    if(effect.pull)effect.pull+=power*5;
    if(effect.threshold)effect.threshold=Math.min(.36,effect.threshold+power*.03);
    if(effect.step)effect.step*=1+power*.14;
    if(effect.explosionDamage)effect.explosionDamage*=1+power*.12;
    if(effect.criticalEvery)effect.criticalEvery=Math.max(2,effect.criticalEvery-tempo);
    if(effect.armTicks)effect.armTicks=Math.max(1,effect.armTicks-tempo);
    if(effect.triggerRadius)effect.triggerRadius*=AREA[reach];
    if(effect.limit)effect.limit+=TARGETS[reach];
    if(kind==='poison')effect.stacks+=TARGETS[reach];
    if(kind==='income') {
      effect.amount+=INCOME[power];
      effect.perSlotCap+=CAPACITY[reach];
    }
  }
  return {
    effect,range:definition.range*RANGE[reach],cooldown:Math.max(1,Math.round(definition.cooldown*SPEED[tempo])),
    damageMultiplier:POWER[power]*TEMPO_DAMAGE[tempo],supportMultiplier:kind==='income'?1:SUPPORT[power],
    damageAura:type==='validator'?.18*SUPPORT[power]:kind==='haste'?.05*power:0,
    hasteAura:type==='validator'?.06*tempo:kind==='haste'?original.bonus*SUPPORT[tempo]:0,
    hasteCap:type==='validator'?.3:kind==='haste'?original.cap:0,
    extraTargets:TARGETS[reach],legacySplash:65*AREA[reach],burnDuration:18+power*4,frostDuration:25+power*5
  };
}
