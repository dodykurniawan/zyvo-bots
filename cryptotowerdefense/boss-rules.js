// Boss timing is simulation time (100 ms per tick), never wall-clock time.
// All mutable fields are plain JSON so checkpoint replays retain every phase.
import {CAMPAIGN_BOSSES,CAMPAIGN_BOSS_IDS,getCampaignBoss} from './campaign-boss-data.js';
export {CAMPAIGN_BOSS_IDS,getCampaignBoss};

export const BOSS_DEFS = Object.freeze({
  bastion: Object.freeze({id:'bastion',name:'Aegis Bastion',shortName:'BASTION',color:'#71e5ff',
    mechanic:'A cycling shield absorbs direct fire, then opens a damage window.',
    counter:'Piercing weapons and damage over time bypass the shield. Use the exposed window.',
    cycleTicks:100,shieldTicks:60,shieldReduction:.6,exposedBonus:.15}),
  broodmother: Object.freeze({id:'broodmother',name:'Brood Carrier',shortName:'BROOD CARRIER',color:'#bbef7c',
    mechanic:'Releases three small drones after a visible hatch countdown. Up to three broods.',
    counter:'Focus the carrier before it hatches. Keep splash or chain damage for the drones.',
    firstCastTick:70,cycleTicks:90,telegraphTicks:20,broods:3,broodSize:3}),
  overlord: Object.freeze({id:'overlord',name:'Storm Overlord',shortName:'STORM OVERLORD',color:'#d7a3ff',
    mechanic:'Marks a tower cluster, then briefly jams up to three towers in the marked area.',
    counter:'Spread your towers and use long-range fire. Marked ground stays fixed during charging.',
    firstCastTick:75,cycleTicks:110,telegraphTicks:25,radius:112,jamTicks:12,immunityTicks:45,maxTargets:3}),
  ...Object.fromEntries(CAMPAIGN_BOSSES.map(definition=>[definition.id,definition]))
});
const BOSS_TYPES=Object.freeze(['bastion','broodmother','overlord']);
export const BOSS_ENGINE_VERSION=4;
export const CAMPAIGN_BOSS_ENGINE_VERSION=5;
export function getBossDefinitionForWave(wave,sector=0){
  const index=Math.max(0,Math.floor(((Number(wave)||1)-1)/5))+Math.max(0,Math.floor(Number(sector)||0));
  return BOSS_DEFS[BOSS_TYPES[index%BOSS_TYPES.length]];
}
export function initializeBoss(state,enemy,spawn){
  if(state.engineVersion<BOSS_ENGINE_VERSION || enemy.kind!=='boss')return;
  const requested=Object.hasOwn(BOSS_DEFS,spawn.bossType)?BOSS_DEFS[spawn.bossType]:null;
  const definition=requested&&(!requested.family||state.engineVersion>=CAMPAIGN_BOSS_ENGINE_VERSION)
    ?requested:getBossDefinitionForWave(spawn.wave,Math.floor(((state.mapLevel||state.level||1)-1)/5));
  const shielded=definition.id==='bastion'||definition.family==='shield';
  enemy.boss={type:definition.id,bornAt:state.tick,casts:0,nextCastAt:definition.firstCastTick===undefined?null:state.tick+definition.firstCastTick,
    phase:shielded?'shielded':'approaching',shieldActive:shielded,telegraph:null};
  if(definition.family){
    enemy.hp=enemy.maxHp=Math.max(1,Math.round(enemy.maxHp*definition.hpMultiplier));
    enemy.speedScale*=definition.speedMultiplier;
  }
}
export function getBossDamageMultiplier(state,enemy,penetration=0){
  if(state?.engineVersion<BOSS_ENGINE_VERSION)return 1;
  const protection=1-Math.max(0,Math.min(1,penetration));
  if(enemy?.boss?.type==='bastion'){
    const definition=BOSS_DEFS.bastion;
    return enemy.boss.shieldActive?1-definition.shieldReduction*protection:1+definition.exposedBonus;
  }
  if(!(state?.engineVersion>=CAMPAIGN_BOSS_ENGINE_VERSION))return 1;
  const boss=enemy?.boss,definition=BOSS_DEFS[boss?.type];
  let multiplier=enemy?.wardUntil>state.tick?1-enemy.wardReduction*protection:1;
  if(definition?.family==='shield')multiplier*=boss.shieldActive?1-definition.shieldReduction*protection:1+definition.exposedBonus;
  if(definition?.family==='mend'&&boss.telegraph)multiplier*=1+definition.exposedBonus;
  return multiplier;
}
export function getBossMovementMultiplier(state,enemy){
  if(!(state?.engineVersion>=CAMPAIGN_BOSS_ENGINE_VERSION)||!(enemy.boss?.activeUntil>state.tick))return 1;
  const definition=BOSS_DEFS[enemy.boss.type];
  return definition?.family==='dash'?definition.dashMultiplier:1;
}
export function getBossStatus(state,enemy){
  const boss=enemy?.boss,definition=BOSS_DEFS[boss?.type];if(!definition)return null;
  if(definition.family){
    const age=Math.max(0,state.tick-boss.bornAt),cycle=age%(definition.cycleTicks||1);
    let remaining=Math.max(0,(boss.nextCastAt??state.tick)-state.tick),label='APPROACHING';
    if(definition.family==='shield'){
      remaining=(boss.shieldActive?definition.shieldTicks:definition.cycleTicks)-cycle;
      label=boss.shieldActive?'SHIELD UP':'EXPOSED';
    }else if(boss.telegraph){
      label={jam:'EMP CHARGING',summon:'HATCHING',mend:'REPAIR CHARGING',dash:'DASH CHARGING',ward:'WARD CHARGING'}[definition.family];
    }else if(boss.activeUntil>state.tick){
      remaining=boss.activeUntil-state.tick;
      label=definition.family==='dash'?'SURGING':'WARD ACTIVE';
    }else if(boss.phase==='interrupted')label='REPAIR INTERRUPTED';
    else if(boss.nextCastAt===null)label='CASTS SPENT';
    else if(boss.casts)label='RECOVERING';
    return{...definition,label,phase:boss.phase,seconds:Math.ceil(Math.max(0,remaining)/10),
      health:Math.max(0,Math.min(1,enemy.hp/enemy.maxHp)),casts:boss.casts,telegraph:boss.telegraph,shieldActive:Boolean(boss.shieldActive)};
  }
  const ticks=Math.max(0,(boss.nextCastAt??state.tick)-state.tick);
  const age=Math.max(0,state.tick-boss.bornAt),cycle=age%BOSS_DEFS.bastion.cycleTicks;
  const shieldRemaining=boss.shieldActive?BOSS_DEFS.bastion.shieldTicks-cycle:BOSS_DEFS.bastion.cycleTicks-cycle;
  const label=boss.type==='bastion'?boss.shieldActive?'SHIELD UP':'EXPOSED':boss.telegraph?boss.type==='broodmother'?'HATCHING':'EMP CHARGING':boss.type==='broodmother'&&boss.casts>=definition.broods?'BROODS EXHAUSTED':'RECOVERING';
  return{...definition,label,phase:boss.phase,seconds:Math.ceil((boss.type==='bastion'?shieldRemaining:ticks)/10),
    health:Math.max(0,Math.min(1,enemy.hp/enemy.maxHp)),casts:boss.casts,telegraph:boss.telegraph,shieldActive:Boolean(boss.shieldActive)};
}

function nearbyTowerPositions(state,center,radius){
  return state.towers.map(tower=>({tower,point:state.padPositions[tower.pad]}))
    .map(entry=>({...entry,distance:Math.hypot(entry.point.x-center.x,entry.point.y-center.y)}))
    .filter(entry=>entry.distance<=radius).sort((a,b)=>a.distance-b.distance||a.tower.pad-b.tower.pad);
}

function advanceCampaignBoss(state,enemy,definition,positionAt,spawnDrone){
  const boss=enemy.boss;
  if(definition.family==='shield'){
    boss.shieldActive=(state.tick-boss.bornAt)%definition.cycleTicks<definition.shieldTicks;
    boss.phase=boss.shieldActive?'shielded':'exposed';return;
  }
  if((boss.phase==='dashing'||boss.phase==='warded')&&boss.activeUntil<=state.tick){
    boss.phase='recovering';boss.shieldActive=false;
  }
  if(boss.nextCastAt===null)return;
  if(!boss.telegraph&&state.tick>=boss.nextCastAt-definition.telegraphTicks){
    const center=positionAt(enemy.progress,state);
    const target=definition.family==='jam'?(nearbyTowerPositions(state,center,230)[0]?.point||center):center;
    boss.telegraph={x:target.x,y:target.y,radius:definition.radius??42,startsAt:state.tick,endsAt:boss.nextCastAt};
    if(definition.family==='mend')boss.hpAtCharge=enemy.hp;
    boss.phase='charging';
  }
  if(state.tick<boss.nextCastAt)return;
  const center=positionAt(enemy.progress,state),target=boss.telegraph||center;
  boss.phase='recovering';
  switch(definition.family){
    case 'summon':
      for(let index=0;index<definition.broodSize&&state.enemies.length<180;index++){
        spawnDrone(enemy,boss.casts,index,Math.max(0,enemy.progress-14-index*13),definition.broodKind,definition.broodHp);
      }
      break;
    case 'jam': {
      const candidates=nearbyTowerPositions(state,target,definition.radius)
        .filter(({tower})=>(tower.jamImmuneUntil||0)<=state.tick).slice(0,definition.maxTargets);
      for(const {tower}of candidates){tower.jammedUntil=state.tick+definition.jamTicks;tower.jamImmuneUntil=state.tick+definition.immunityTicks;}
      break;
    }
    case 'dash':
      boss.activeUntil=state.tick+definition.dashTicks;boss.phase='dashing';break;
    case 'mend':
      if(boss.hpAtCharge-enemy.hp>=enemy.maxHp*definition.interruptFraction)boss.phase='interrupted';
      else enemy.hp=Math.min(enemy.maxHp,enemy.hp+Math.round(enemy.maxHp*definition.healFraction));
      delete boss.hpAtCharge;
      break;
    case 'ward': {
      const escorts=state.enemies.filter(other=>other!==enemy&&other.hp>0&&!other.boss)
        .map(other=>{const position=positionAt(other.progress,state);return{other,distance:Math.hypot(position.x-target.x,position.y-target.y)};})
        .filter(escort=>escort.distance<=definition.radius)
        .sort((a,b)=>a.distance-b.distance||a.other.id.localeCompare(b.other.id)).slice(0,definition.maxTargets);
      const until=state.tick+definition.wardTicks;
      for(const targetEnemy of [enemy,...escorts.map(escort=>escort.other)]){
        if(!(targetEnemy.wardUntil>state.tick)||targetEnemy.wardReduction<=definition.wardReduction){
          targetEnemy.wardUntil=until;targetEnemy.wardReduction=definition.wardReduction;
        }
      }
      boss.activeUntil=until;boss.phase='warded';boss.shieldActive=true;
      break;
    }
  }
  const burstCenter=definition.family==='jam'||definition.family==='ward'?target:center;
  state.bursts.push({x:burstCenter.x,y:burstCenter.y,color:definition.color,ttl:12,size:definition.radius??48});
  boss.casts+=1;
  boss.nextCastAt=boss.casts>=definition.maxCasts?null:boss.nextCastAt+definition.cycleTicks;
  boss.telegraph=null;
}

export function advanceBosses(state,{positionAt,spawnDrone}){
  if(state.engineVersion<BOSS_ENGINE_VERSION)return;
  // Work from a snapshot: a summoned drone never becomes another boss cast.
  for(const enemy of [...state.enemies]){
    if(enemy.hp<=0 || !enemy.boss)continue;
    const boss=enemy.boss,definition=BOSS_DEFS[boss.type];
    if(!definition)continue;
    if(definition.family){if(state.engineVersion>=CAMPAIGN_BOSS_ENGINE_VERSION)advanceCampaignBoss(state,enemy,definition,positionAt,spawnDrone);continue;}
    if(boss.type==='bastion'){
      boss.shieldActive=(state.tick-boss.bornAt)%definition.cycleTicks<definition.shieldTicks;
      boss.phase=boss.shieldActive?'shielded':'exposed';continue;
    }
    if(boss.nextCastAt===null)continue;
    if(boss.type==='broodmother'&&boss.casts>=definition.broods){boss.nextCastAt=null;boss.phase='spent';boss.telegraph=null;continue;}
    if(!boss.telegraph&&state.tick>=boss.nextCastAt-definition.telegraphTicks){
      const center=positionAt(enemy.progress,state);
      if(boss.type==='overlord'){
        // Snapshot a nearby cluster now. Selling the target or the boss moving
        // cannot drag an already announced pulse across the battlefield.
        const candidates=state.towers.map(tower=>({tower,point:state.padPositions[tower.pad]}))
          .map(entry=>({...entry,distance:Math.hypot(entry.point.x-center.x,entry.point.y-center.y)}))
          .filter(entry=>entry.distance<=230).sort((a,b)=>a.distance-b.distance||a.tower.pad-b.tower.pad);
        const target=candidates[0]?.point||center;
        boss.telegraph={x:target.x,y:target.y,radius:definition.radius,startsAt:state.tick,endsAt:boss.nextCastAt};
      }else boss.telegraph={x:center.x,y:center.y,radius:42,startsAt:state.tick,endsAt:boss.nextCastAt};
      boss.phase='charging';
    }
    if(state.tick<boss.nextCastAt)continue;
    const center=positionAt(enemy.progress,state),cast=boss.casts;
    if(boss.type==='broodmother'){
      for(let index=0;index<definition.broodSize;index++){
        if(state.enemies.length>=180)break;
        spawnDrone(enemy,cast,index,Math.max(0,enemy.progress-14-index*13));
      }
      state.bursts.push({...center,color:definition.color,ttl:10,size:48});
    }else{
      const target=boss.telegraph||{...center,radius:definition.radius};
      const targets=state.towers.filter(tower=>(tower.jamImmuneUntil||0)<=state.tick)
        .map(tower=>({tower,point:state.padPositions[tower.pad]}))
        .map(entry=>({...entry,distance:Math.hypot(entry.point.x-target.x,entry.point.y-target.y)}))
        .filter(entry=>entry.distance<=definition.radius).sort((a,b)=>a.distance-b.distance||a.tower.pad-b.tower.pad).slice(0,definition.maxTargets);
      for(const {tower}of targets){tower.jammedUntil=state.tick+definition.jamTicks;tower.jamImmuneUntil=state.tick+definition.immunityTicks;}
      state.bursts.push({x:target.x,y:target.y,color:definition.color,ttl:12,size:definition.radius});
    }
    boss.casts+=1;boss.nextCastAt+=definition.cycleTicks;boss.telegraph=null;boss.phase='recovering';
  }
}
