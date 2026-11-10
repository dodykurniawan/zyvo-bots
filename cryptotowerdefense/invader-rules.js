const define=entry=>Object.freeze({...entry,...(entry.behavior?{behavior:Object.freeze(entry.behavior)}:{})});

export const INVADER_DEFS=Object.freeze({
  seed_mite:define({name:'Seed Mite',role:'Swarmer',hp:43,speed:4.3,reward:10,damage:1,radius:9,color:'#aae96d',armor:0,description:'A light garden swarmer that travels in packs.'}),
  neon_skater:define({name:'Neon Skater',role:'Sprint',hp:50,speed:5.2,reward:11,damage:1,radius:10,color:'#ff77d1',armor:0,description:'Neon wheels flare during short speed bursts.',behavior:{kind:'sprint',cycleTicks:36,activeTicks:9,multiplier:1.25}}),
  ember_tick:define({name:'Ember Tick',role:'Heat resistant',hp:75,speed:3.7,reward:13,damage:1,radius:11,color:'#ff955a',armor:.06,description:'Its shell resists burns. Direct shots remain effective.',behavior:{kind:'heatResist',multiplier:.65}}),
  vault_guard:define({name:'Vault Guard',role:'Armored',hp:155,speed:2.75,reward:19,damage:2,radius:15,color:'#a7a8e8',armor:.27,description:'A slower guard with dense armor; piercing fire cuts through it.'}),
  dune_burrower:define({name:'Dune Burrower',role:'Burrowing armor',hp:80,speed:3.8,reward:14,damage:1,radius:11,color:'#dfbe77',armor:.08,description:'Burrows briefly for extra armor. Piercing fire bypasses the protection.',behavior:{kind:'burrow',cycleTicks:40,activeTicks:13,armorBonus:.15}}),
  delta_leech:define({name:'Delta Leech',role:'Durable',hp:106,speed:3.2,reward:15,damage:1,radius:13,color:'#70dfbf',armor:.06,description:'A slippery, durable invader that keeps coming under pressure.'}),
  rime_shard:define({name:'Rime Shard',role:'Chill resistant',hp:86,speed:3.65,reward:14,damage:1,radius:11,color:'#a0eaff',armor:.08,description:'Resists slows from cold weapons. Stuns still stop it.',behavior:{kind:'chillResist',movementFloor:.68}}),
  copper_ram:define({name:'Copper Ram',role:'Heavy breach',hp:176,speed:2.63,reward:21,damage:3,radius:16,color:'#f2aa77',armor:.24,description:'A slow armored battering ram. Keep it away from the Core.'}),
  spore_scout:define({name:'Spore Scout',role:'Splitting',hp:79,speed:3.92,reward:13,damage:1,radius:11,color:'#d4d37d',armor:0,description:'Drops a tiny Seed Mite when defeated.',behavior:{kind:'split',child:'seed_mite',hpFraction:.3}}),
  storm_ray:define({name:'Storm Ray',role:'Sprint',hp:64,speed:4.65,reward:12,damage:1,radius:11,color:'#75cfff',armor:0,description:'Rides a brief burst of lightning every few seconds.',behavior:{kind:'sprint',cycleTicks:42,activeTicks:12,multiplier:1.27}}),
  void_mote:define({name:'Void Mote',role:'Evasive',hp:61,speed:4.75,reward:12,damage:1,radius:10,color:'#b9a0ff',armor:.13,description:'A quick mote with a thin phase shell that softens direct fire.'}),
  apex_drone:define({name:'Apex Drone',role:'Assault',hp:102,speed:4.64,reward:16,damage:2,radius:13,color:'#f6d27f',armor:.12,description:'A fast assault drone with light armor and a harder Core hit.'})
});

export const CAMPAIGN_INVADER_IDS=Object.freeze(Object.keys(INVADER_DEFS));
const MAP_MIXES=Object.freeze([
  ['seed_mite','spore_scout'],['neon_skater','seed_mite'],['ember_tick','dune_burrower'],['vault_guard','ember_tick'],
  ['dune_burrower','copper_ram'],['delta_leech','seed_mite'],['rime_shard','delta_leech'],['copper_ram','vault_guard'],
  ['spore_scout','seed_mite'],['storm_ray','neon_skater'],['spore_scout','void_mote'],['ember_tick','copper_ram'],
  ['storm_ray','spore_scout'],['vault_guard','seed_mite'],['rime_shard','storm_ray'],['ember_tick','void_mote'],
  ['copper_ram','apex_drone'],['void_mote','vault_guard'],['void_mote','apex_drone'],['apex_drone','copper_ram']
]);

/** The caller supplies the roll; this helper never consumes random state. */
export function pickCampaignInvader(mapIndex,wave,roll,{spawnIndex,spawnCount}={}){
  const index=Number.isInteger(mapIndex)&&mapIndex>=0&&mapIndex<MAP_MIXES.length?mapIndex:0;
  const [primary,secondary]=MAP_MIXES[index];
  const value=Number.isFinite(roll)?Math.max(0,Math.min(99,Math.floor(roll))):0;
  // Heavy armor arrives after players have had time to earn build Orbs.
  const signature=wave<3&&INVADER_DEFS[primary].hp>=140
    ?(INVADER_DEFS[secondary].hp<140?secondary:index%2?'dune_burrower':'ember_tick'):primary;
  // The last three worlds need a short Orb ramp before their fast armored
  // mobs mix freely. Preview one signature invader at each opening wave's end.
  if(index>=17&&wave<=2){
    if(Number.isInteger(spawnCount)&&spawnCount>0&&spawnIndex===spawnCount-1)return signature;
    return value<15?'runner':wave>=2&&value>=62?'wraith':'bot';
  }
  if(wave===1&&spawnIndex===0)return signature;
  const signatureWeight=INVADER_DEFS[signature].hp>=140?24:42;
  if(value<signatureWeight)return signature;
  if(value<signatureWeight+14&&wave>=2&&secondary!==signature&&(wave>=4||INVADER_DEFS[secondary].hp<140))return secondary;
  if(wave>=5&&value>=96)return 'whale';
  if(wave>=4&&value>=89)return 'splitter';
  if(wave>=2&&value>=74)return 'wraith';
  if(index>=1&&wave>=2&&value>=67)return 'runner';
  return 'bot';
}

export function invaderBehaviorActive(enemy,tick){
  const behavior=INVADER_DEFS[enemy.kind]?.behavior;
  return Boolean(behavior?.cycleTicks&&Math.max(0,tick-(enemy.invaderBornAt??0))%behavior.cycleTicks<behavior.activeTicks);
}
