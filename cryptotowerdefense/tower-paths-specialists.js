export const SPECIALIST_TOWER_PATHS = {
  stasis: {
    power: ['Time Lock', 'Deepen the chill and turn the chamber into a damaging freeze zone.', [
      ['Cold Pressure', {damage:.38,effect:{factor:-.02}}],
      ['Crystal Compression', {damage:.46,effect:{duration:3}}],
      ['Zero-Point Cells', {damage:.62,effect:{factor:-.025,duration:3}}],
      ['Frozen Moment', {damage:.78,effect:{factor:-.025,duration:4}},1.14],
      ['Absolute Stasis', {damage:.92,bossDamageMultiplier:.22,effect:{factor:-.03,duration:5}},1.26]
    ]],
    tempo: ['Field Cycling', 'Refresh the field sooner to cover successive groups.', [
      ['Rapid Condenser', {fireRate:.23}],
      ['Twin Chill Chambers', {fireRate:.27,damage:.12}],
      ['Oscillating Lattice', {fireRate:.32,effect:{duration:3}}],
      ['Rolling Freeze', {fireRate:.43,damage:.22,effect:{duration:3}},1.12],
      ['Permafrost Cycle', {fireRate:.56,damage:.32,effect:{duration:4}},1.2]
    ]],
    reach: ['Extended Stasis', 'Cover more of the road with a larger, longer-ranged freeze field.', [
      ['Outer Cryostat', {range:.13,effect:{splash:7}}],
      ['Wide Cooling Fins', {range:.14,effect:{splash:9}}],
      ['Radial Freeze', {range:.16,effect:{splash:11}}],
      ['Ice Shelf', {range:.18,damage:.18,effect:{splash:13}},1.12],
      ['Whiteout Zone', {range:.2,damage:.3,effect:{splash:17,duration:5}},1.22]
    ]]
  },
  laser: {
    power: ['Beam Convergence', 'Build a stronger focused beam against enemies that survive sustained fire.', [
      ['Coherent Beam', {damage:.28,effect:{step:.025}}],
      ['Focusing Crystal', {damage:.34,effect:{step:.035}}],
      ['Locked Resonance', {damage:.45,effect:{stacks:1}}],
      ['Thermal Runaway', {damage:.54,effect:{step:.055,stacks:1}},1.16],
      ['Star Lance', {damage:.7,effect:{step:.065,stacks:1}},1.28]
    ]],
    tempo: ['Rapid Refocus', 'Cycle the emitter faster to build focus stacks sooner.', [
      ['Fast Trigger Diode', {fireRate:.25}],
      ['Liquid-Cooled Optics', {fireRate:.28,damage:.08}],
      ['Overclocked Emitter', {fireRate:.37,damage:.13}],
      ['Continuous Excitation', {fireRate:.48,damage:.2},1.1],
      ['Pulse Furnace', {fireRate:.62,damage:.26},1.22]
    ]],
    reach: ['Long Focus', 'Keep targets in view longer and split the beam across nearby enemies.', [
      ['Long-Focus Lens', {range:.14}],
      ['Stabilized Telescope', {range:.15,damage:.12}],
      ['Beam Splitter', {range:.13,hitTargets:1},1.13],
      ['Twin Resonators', {range:.15,secondaryDamage:.16,damage:.19},1.16],
      ['Solar Array', {range:.16,hitTargets:1,secondaryDamage:.14,damage:.25},1.3]
    ]]
  },
  railgun: {
    power: ['Bossbreaker', 'Concentrate immense armor-piercing damage on bosses.', [
      ['Tungsten Sabot', {damage:.3,effect:{armorPierce:.05}}],
      ['Siege Capacitors', {damage:.33,effect:{bossMultiplier:.25}}],
      ['Dreadnought Slug', {damage:.42,effect:{bossMultiplier:.33,armorPierce:.08}},1.1],
      ['Titan Breaker', {damage:.52,effect:{bossMultiplier:.45,armorPierce:.12}},1.2],
      ['Orbital Impactor', {damage:.66,effect:{bossMultiplier:.65}},1.38]
    ]],
    tempo: ['Rail Charge', 'Recharge the magnetic rails faster and strengthen each shot.', [
      ['Rapid Induction', {fireRate:.2}],
      ['Split Capacitor Bank', {fireRate:.26,damage:.09}],
      ['Rail Quench', {fireRate:.34,damage:.14}],
      ['Autoloaded Sabots', {fireRate:.48,damage:.2},1.12],
      ['Salvo Accelerator', {fireRate:.66,damage:.26},1.22]
    ]],
    reach: ['Extreme Calibration', 'Reach distant targets and fire follow-up shots at other threats.', [
      ['Extended Rails', {range:.14}],
      ['Rangefinding Mast', {range:.15,damage:.1}],
      ['Predictive Targeting', {range:.17,fireRate:.12}],
      ['Coaxial Rail', {range:.15,hitTargets:1},1.15],
      ['Dual Horizon', {range:.18,secondaryDamage:.25,damage:.36},1.21]
    ]]
  },
  singularity: {
    power: ['Mass Driver', 'Increase the impact and throw clusters farther back along the track.', [
      ['Dense Gravity Core', {damage:.38,effect:{pull:3}}],
      ['Heavy Mass Injection', {damage:.48,effect:{pull:4}}],
      ['Compressed Orbit', {damage:.58,effect:{pull:5}}],
      ['Stellar Mass Driver', {damage:.75,effect:{pull:6}},1.15],
      ['Collapsed Star', {damage:.94,effect:{pull:9},bossDamageMultiplier:.15},1.31]
    ]],
    tempo: ['Fast Collapse', 'Trigger gravity pulses more often and shorten recovery from each pull.', [
      ['Fast Recombination', {fireRate:.21}],
      ['Isolated Containment', {fireRate:.24,effect:{immunity:-2}}],
      ['Dual Event Coils', {fireRate:.33,damage:.16,effect:{immunity:-3}}],
      ['Quick Collapse', {fireRate:.44,damage:.22,effect:{immunity:-3}},1.16],
      ['Recurring Singularity', {fireRate:.58,damage:.3,effect:{immunity:-4}},1.28]
    ]],
    reach: ['Event Horizon', 'Widen each pulse and exert gravity over more of the lane.', [
      ['Outer Gravity Rings', {range:.12,effect:{splash:7}}],
      ['Broad Mass Field', {range:.13,effect:{splash:8}}],
      ['Dark Matter Halo', {range:.15,effect:{splash:10}}],
      ['Warped Space', {range:.17,effect:{splash:12},hitSlowFactor:-.15,hitSlowDuration:8},1.16],
      ['Event Horizon Engine', {range:.18,effect:{splash:15},hitSlowFactor:-.15,hitSlowDuration:4},1.28]
    ]]
  },
  plasma: {
    power: ['Volatile Mark', 'Turn marked enemies into stronger bombs when they fall.', [
      ['Reactive Plasma', {damage:.34,effect:{explosionDamage:.09}}],
      ['Volatile Isotope', {damage:.44,effect:{explosionDamage:.1}}],
      ['Ignition Chain', {damage:.58,effect:{explosionDamage:.12,duration:5}}],
      ['Plasma Detonation', {damage:.72,effect:{explosionDamage:.15,duration:6}},1.15],
      ['Annihilation Mark', {damage:.98,effect:{explosionDamage:.2,duration:8}},1.31]
    ]],
    tempo: ['Crucible Feed', 'Mark fresh enemies faster and keep the marks active longer.', [
      ['Automatic Plasma Feed', {fireRate:.23}],
      ['Quick Ion Tap', {fireRate:.25,effect:{duration:5}}],
      ['Rapid Tagging', {fireRate:.34,damage:.16,effect:{duration:5}}],
      ['Parallel Igniters', {fireRate:.43,damage:.21,hitTargets:1},1.17],
      ['Cascade Reactor', {fireRate:.53,damage:.26,effect:{duration:10}},1.26]
    ]],
    reach: ['Cascade Radius', 'Reach more enemies with wider death bursts and extra mark targets.', [
      ['Wide Plasma Lens', {range:.13,effect:{splash:7}}],
      ['Expanding Hot Zone', {range:.13,effect:{splash:8}}],
      ['Dual Mark Projector', {range:.15,hitTargets:1,effect:{splash:7}},1.12],
      ['Linked Detonators', {range:.16,secondaryDamage:.15,effect:{splash:10}},1.16],
      ['Chain Reaction Grid', {range:.17,hitTargets:1,effect:{splash:13}},1.32]
    ]]
  },
  mint: {
    power: ['Dense Minting', 'Stamp larger Orb batches without raising the shared production cap.', [
      ['Weighted Dies', {effect:{amount:3}}],
      ['Twin Stamps', {effect:{amount:4}}],
      ['Dense Alloy', {effect:{amount:5,perSlotCap:12}}],
      ['Industrial Mint', {effect:{amount:6,perSlotCap:15}},1.13],
      ['Orb Foundry', {effect:{amount:9,perSlotCap:18}},1.22]
    ]],
    tempo: ['Fast Stamps', 'Deliver Orb batches at shorter intervals.', [
      ['Lubricated Press', {fireRate:.23}],
      ['Rapid Hopper', {fireRate:.27}],
      ['Pneumatic Dies', {fireRate:.33,effect:{amount:1}}],
      ['Continuous Press', {fireRate:.47,effect:{amount:2}},1.11],
      ['Assembly Line', {fireRate:.59,effect:{amount:3}},1.22]
    ]],
    reach: ['Orb Vault', 'Raise this mint’s production allowance while preserving the 300-Orb team cap.', [
      ['Side Reservoir', {effect:{perSlotCap:20}}],
      ['Reinforced Vault', {effect:{perSlotCap:24}}],
      ['Deep Storage', {effect:{perSlotCap:30}}],
      ['Vault Complex', {fireRate:.15,effect:{perSlotCap:42}},1.12],
      ['Central Reserve', {fireRate:.2,effect:{perSlotCap:56}},1.23]
    ]]
  },
  scanner: {
    power: ['Weakpoint Insight', 'Make exposed enemies take more direct damage from the squad.', [
      ['Fracture Finder', {effect:{bonus:.055}}],
      ['Defect Analysis', {effect:{bonus:.045,duration:3}}],
      ['Target Profile', {support:.12,effect:{bonus:.06,duration:4}}],
      ['Critical Fault Map', {support:.13,effect:{bonus:.065,duration:5}},1.15],
      ['Total Exposure', {support:.15,effect:{bonus:.075,duration:7}},1.28]
    ]],
    tempo: ['Scan Cycle', 'Refresh vulnerabilities more frequently and keep them visible longer.', [
      ['Quick Sweep', {fireRate:.23}],
      ['Live Pattern Buffer', {fireRate:.27,effect:{duration:4}}],
      ['Fast Reacquisition', {fireRate:.31,effect:{duration:5}}],
      ['Predictive Scan', {fireRate:.44,effect:{duration:7}},1.1],
      ['Persistent Tracking', {fireRate:.56,effect:{duration:10,bonus:.045}},1.2]
    ]],
    reach: ['Wide Spectrum', 'Expose multiple enemies from farther away.', [
      ['Wide-Angle Optics', {range:.13}],
      ['Paired Sensors', {range:.12,hitTargets:1},1.12],
      ['Multi-Track Processor', {range:.14,hitTargets:1}],
      ['Spectrum Sweep', {range:.16,hitTargets:1,effect:{duration:4}},1.16],
      ['All-Band Reconnaissance', {range:.17,hitTargets:2,effect:{duration:5}},1.33]
    ]]
  },
  accelerator: {
    power: ['Drive Reinforcement', 'Give nearby weapons a growing damage bonus alongside haste.', [
      ['Power Injection', {damageAura:.045}],
      ['Reinforced Bus', {damageAura:.055}],
      ['Kinetic Feedback', {damageAura:.06,range:.05}],
      ['Voltage Cascade', {damageAura:.07,range:.06},1.17],
      ['Drive Supremacy', {damageAura:.09,range:.07},1.32]
    ]],
    tempo: ['Clock Boost', 'Increase the strength of the attack-speed aura.', [
      ['Synchronized Clock', {hasteAura:.035}],
      ['Fast Bus', {hasteAura:.045}],
      ['Dual Clock Domains', {hasteAura:.055}],
      ['Overspeed Governor', {hasteAura:.065,hasteCap:.035},1.16],
      ['Limit Breaker', {hasteAura:.075,hasteCap:.045},1.32]
    ]],
    reach: ['Grid Coverage', 'Extend the beacon’s influence across a wider tower formation.', [
      ['Auxiliary Antenna', {range:.14}],
      ['Extended Transmitter', {range:.16}],
      ['Mesh Relay', {range:.18,hasteAura:.02}],
      ['Distributed Clock', {range:.2,hasteAura:.025},1.13],
      ['Sector-Wide Drive', {range:.23,hasteAura:.03,damageAura:.035},1.24]
    ]]
  },
  sunforge: {
    power: ['Solar Payload', 'Turn stronger mortar hits into hotter, longer-lasting scorch damage.', [
      ['Solar Charge', {damage:.32,effect:{tickDamage:.004}}],
      ['Fused Plasma Shell', {damage:.41,effect:{tickDamage:.004}}],
      ['Superheated Casing', {damage:.52,effect:{tickDamage:.006,duration:3}}],
      ['Prominence Burst', {damage:.72,effect:{tickDamage:.007,duration:4}},1.17],
      ['Miniature Sun', {damage:.97,effect:{tickDamage:.009,duration:5}},1.34]
    ]],
    tempo: ['Quick Furnace', 'Cycle the mortar faster and keep advancing enemies scorched.', [
      ['Rapid Furnace Draft', {fireRate:.2}],
      ['Hot Breech', {fireRate:.25,damage:.1}],
      ['Dual Furnace Feed', {fireRate:.31,effect:{duration:4}}],
      ['Sustained Flare', {fireRate:.43,damage:.21,effect:{duration:4}},1.1],
      ['Flarestorm Battery', {fireRate:.57,damage:.31,effect:{duration:5}},1.23]
    ]],
    reach: ['Solar Corona', 'Expand airbursts and shrink the mortar’s minimum range.', [
      ['Adjustable Elevation', {range:.11,effect:{splash:7,minRange:-5}}],
      ['Flare Dispersal', {range:.12,effect:{splash:8,minRange:-6}}],
      ['High Corona', {range:.14,effect:{splash:11,minRange:-7}}],
      ['Sunspot Mortar', {range:.16,effect:{splash:13,minRange:-8}},1.14],
      ['Crown of Fire', {range:.17,damage:.32,effect:{splash:17,minRange:-10}},1.27]
    ]]
  },
  phase_lancer: {
    power: ['Phase Fracture', 'Strengthen the lance and carry more of its damage through every target in line.', [
      ['Hardened Phase Tip', {damage:.33,effect:{armorPierce:.045}}],
      ['Lance Compression', {damage:.4,effect:{secondaryDamage:.055,armorPierce:.045}}],
      ['Phase Rupture', {damage:.57,effect:{secondaryDamage:.07,armorPierce:.045}}],
      ['Piercing Resonance', {damage:.72,effect:{secondaryDamage:.08,armorPierce:.045}},1.17],
      ['Reality Fracture', {damage:1,effect:{secondaryDamage:.11}},1.3]
    ]],
    tempo: ['Lance Reset', 'Rephase the weapon quickly so repeated shots cut down the same lane.', [
      ['Quick Reset Coil', {fireRate:.23}],
      ['Rephasing Optics', {fireRate:.28,damage:.09}],
      ['Rapid Pattern Lock', {fireRate:.35,damage:.14}],
      ['Parallel Rephasers', {fireRate:.46,damage:.22},1.12],
      ['Continuous Phase Drive', {fireRate:.59,damage:.29},1.23]
    ]],
    reach: ['Phase Corridor', 'Widen the lance’s line and pierce deeper groups.', [
      ['Longwave Optics', {range:.12,effect:{lineWidth:2}}],
      ['Wide Lance Aperture', {range:.12,effect:{lineWidth:3}}],
      ['Expanded Phase Corridor', {range:.14,effect:{lineWidth:3,targets:1}},1.11],
      ['Layered Penetration', {range:.16,effect:{lineWidth:4,targets:1}},1.17],
      ['Dimensional Thoroughfare', {range:.17,effect:{lineWidth:5,targets:2}},1.33]
    ]]
  },
  cryo_anchor: {
    power: ['Glacial Anchor', 'Hold tough targets in place while reinforced shots wear them down.', [
      ['Anchor Head',{damage:.38,effect:{duration:3}}],
      ['Subzero Clamp',{damage:.48,effect:{factor:-.035}}],
      ['Deep Ice Tether',{damage:.64,effect:{duration:6}}],
      ['Permafrost Bolt',{damage:.79,effect:{factor:-.05,duration:6}},1.16],
      ['Icebound Core',{damage:.90,bossDamageMultiplier:.25,effect:{duration:12}},1.32]
    ]],
    tempo: ['Cold Intercept', 'Reapply the anchor faster and interrupt priority invaders.', [
      ['Short Reset',{fireRate:.25}],
      ['Piston Brake',{fireRate:.28,hitStunTicks:1}],
      ['Flash Clamp',{fireRate:.36,damage:.13}],
      ['Triple Valve',{fireRate:.45,damage:.22,hitStunTicks:1},1.16],
      ['Snap Freeze',{fireRate:.56,damage:.32,hitStunTicks:1},1.3]
    ]],
    reach: ['Anchor Network', 'Intercept enemies across a broader lane and tether several at once.', [
      ['Extended Tether',{range:.15}],
      ['Twin Anchor',{hitTargets:1,range:.09},1.13],
      ['Insulated Line',{range:.12,effect:{duration:5}}],
      ['Three-Point Lock',{hitTargets:1,range:.15},1.24],
      ['Ice Fleet',{hitTargets:1,range:.16,secondaryDamage:.24},1.38]
    ]]
  },
  aurora_core: {
    power: ['Emergency Recovery', 'Advance nearby weapon cooldowns by more whenever the Aurora pulses.', [
      ['Recovery Cell',{effect:{advance:1}}],
      ['Surge Charge',{effect:{advance:1},support:.16}],
      ['Rapid Repair',{effect:{advance:2}}],
      ['Emergency Relay',{effect:{advance:2,assistCooldown:-2},support:.16},1.18],
      ['Full Recovery',{effect:{advance:3,assistCooldown:-3},support:.24},1.38]
    ]],
    tempo: ['Rhythm of Light', 'Pulse more often so the same allies can receive more assists.', [
      ['Soft Start',{fireRate:.22}],
      ['Timing Lens',{fireRate:.28,effect:{assistCooldown:-2}}],
      ['Parallel Pulsers',{fireRate:.35,effect:{assistCooldown:-3}}],
      ['Rapid Recovery',{fireRate:.46,effect:{assistCooldown:-4}},1.19],
      ['Continuous Aurora',{fireRate:.62,effect:{assistCooldown:-5}},1.39]
    ]],
    reach: ['Aurora Canopy', 'Cover a larger formation and assist more towers per pulse.', [
      ['Dawn Lens',{range:.14}],
      ['Twin Light',{range:.09,effect:{targets:1}},1.10],
      ['High Canopy',{range:.16,effect:{advance:1}}],
      ['Ribbon Network',{range:.15,effect:{targets:1}},1.19],
      ['Northern Crown',{range:.18,effect:{targets:2}},1.37]
    ]]
  },
  gilded_ballista: {
    power: ['Siege Torsion', 'Use heavy bolts to break armor and punish bosses.', [
      ['Tempered Bolt',{damage:.42,effect:{armorPierce:.03}}],
      ['Gilded Tip',{damage:.49,effect:{armorPierce:.03}}],
      ['Siege Limbs',{damage:.65,bossDamageMultiplier:.15}],
      ['Bastion Bolt',{damage:.82,bossDamageMultiplier:.22},1.18],
      ['Citadel Breaker',{damage:.99,bossDamageMultiplier:.35},1.42]
    ]],
    tempo: ['Clockwork Draw', 'Automate the draw and fire a steady volley of increasingly heavy bolts.', [
      ['Quick Ratchet',{fireRate:.25}],
      ['Clockwork Winch',{fireRate:.30,damage:.10}],
      ['Twin Draw Springs',{fireRate:.35,damage:.16}],
      ['Ratchet Array',{fireRate:.46,damage:.24},1.14],
      ['Golden Volley',{fireRate:.58,damage:.32},1.28]
    ]],
    reach: ['Longbow Battery', 'Trade a single target for long-range shots into clustered lanes.', [
      ['Flight Fletching',{range:.16}],
      ['Forked Bowstring',{range:.1,hitTargets:1},1.16],
      ['Weighted Fletching',{range:.14,secondaryDamage:.13}],
      ['Split Carriage',{range:.16,hitTargets:1},1.24],
      ['Crown Battery',{range:.18,secondaryDamage:.22,damage:.4},1.38]
    ]]
  },
  monsoon_battery: {
    power: ['Storm Payload', 'Pack each rocket with more force and preserve more damage at the blast edge.', [
      ['Charged Warhead',{damage:.4}],
      ['Shaped Casing',{damage:.43,effect:{edgeDamage:.07}}],
      ['Squall Charge',{damage:.62,effect:{edgeDamage:.08}}],
      ['Cyclone Yield',{damage:.8,effect:{edgeDamage:.09}},1.18],
      ['Typhoon Warhead',{damage:1.02,effect:{edgeDamage:.11}},1.42]
    ]],
    tempo: ['Rolling Salvo', 'Feed the six barrels quickly to keep incoming groups under fire.', [
      ['Quick Feeder',{fireRate:.23}],
      ['Ejector Pistons',{fireRate:.29,damage:.10}],
      ['Sequenced Launch',{fireRate:.36,damage:.14}],
      ['Constant Salvo',{fireRate:.47,damage:.25},1.16],
      ['Monsoon Barrage',{fireRate:.60,damage:.36},1.33]
    ]],
    reach: ['Storm Footprint', 'Spread blasts over more road and cover closer targets.', [
      ['Gyro Fins',{range:.13,effect:{minRange:-4}}],
      ['Shower Rockets',{effect:{splash:9,minRange:-5}}],
      ['Front Extension',{range:.14,effect:{splash:11}}],
      ['Sheet of Rain',{range:.16,effect:{splash:13,minRange:-6}},1.2],
      ['Storm Front',{range:.18,effect:{splash:17,minRange:-10}},1.36]
    ]]
  },
  thorn_harvester: {
    power: ['Armor Harvest', 'Strip more armor with each scythe and cut deep into durable targets.', [
      ['Honed Thorn',{damage:.39,effect:{armorBreak:.012}}],
      ['Paired Serration',{damage:.44,effect:{maxArmorBreak:.045}}],
      ['Tungsten Sickle',{damage:.59,effect:{armorBreak:.017}}],
      ['Deep Harvest',{damage:.79,effect:{maxArmorBreak:.065}},1.16],
      ['Bastion Reaper',{damage:.97,effect:{maxArmorBreak:.1,armorBreak:.025}},1.35]
    ]],
    tempo: ['Scythe Rhythm', 'Accelerate each swing and make the stripped armor take longer to recover.', [
      ['Greased Hinge',{fireRate:.22}],
      ['Bristle Timing',{fireRate:.30,effect:{duration:5}}],
      ['Return Spring',{fireRate:.38,damage:.16}],
      ['Chain Reaper',{fireRate:.46,damage:.23,effect:{duration:6}},1.16],
      ['Harvest Frenzy',{fireRate:.60,damage:.32,effect:{duration:9}},1.32]
    ]],
    reach: ['Bramble Sweep', 'Cut armor from multiple enemies across a wide lane.', [
      ['Spined Handle',{range:.14}],
      ['Second Scythe',{hitTargets:1,range:.09},1.15],
      ['Bramble Graft',{range:.14,effect:{duration:6}}],
      ['Forked Sweep',{hitTargets:1,range:.15},1.22],
      ['Bramble Reaping',{hitTargets:1,range:.18,secondaryDamage:.23},1.37]
    ]]
  },
  magnetar_array: {
    power: ['Mass Capture', 'Pull invaders farther backward and crush those caught in the field.', [
      ['Dense Core',{damage:.40,effect:{pull:3}}],
      ['Tidal Magnet',{damage:.45,effect:{pull:5}}],
      ['Iron Singularity',{damage:.60,effect:{pull:7}}],
      ['Magnetic Crush',{damage:.78,effect:{pull:10}},1.19],
      ['Gravitic Breaker',{damage:.96,effect:{pull:13}},1.42]
    ]],
    tempo: ['Recapture Cycle', 'Reset the field sooner and shorten how long enemies resist a new pull.', [
      ['Flux Reset',{fireRate:.22}],
      ['Field Collapse',{fireRate:.28,effect:{immunity:-2}}],
      ['Fast Reversal',{fireRate:.35,effect:{immunity:-3}}],
      ['Pulsed Core',{fireRate:.46,damage:.23,effect:{immunity:-4}},1.17],
      ['Repeated Capture',{fireRate:.59,damage:.36,effect:{immunity:-5}},1.35]
    ]],
    reach: ['Magnetic Halo', 'Catch whole groups from farther away in a wider pull radius.', [
      ['Flux Wings',{range:.13,effect:{splash:5}}],
      ['Halo Coils',{range:.11,effect:{splash:7}}],
      ['Broad Flux',{range:.14,effect:{splash:9}}],
      ['Polar Field',{range:.16,effect:{splash:11}},1.17],
      ['Magnetar Halo',{range:.18,effect:{splash:15,pull:5}},1.34]
    ]]
  },
  tidal_obelisk: {
    power: ['Deep Undertow', 'Make the tide hit harder and leave invaders moving more slowly.', [
      ['Pressure Channel',{damage:.40,effect:{factor:-.025}}],
      ['Water Weight',{damage:.45,effect:{duration:3}}],
      ['Riptide Core',{damage:.62,effect:{factor:-.04}}],
      ['Deep Channel',{damage:.80,effect:{factor:-.05,duration:4}},1.16],
      ['Abyssal Undertow',{damage:.96,effect:{factor:-.065,duration:7}},1.34]
    ]],
    tempo: ['Rising Tides', 'Refresh the slowing water rapidly as new groups arrive.', [
      ['Fast Intake',{fireRate:.22}],
      ['Twin Sluice',{fireRate:.29,effect:{duration:3}}],
      ['Return Flow',{fireRate:.36,damage:.17}],
      ['Riptide Rhythm',{fireRate:.46,damage:.24,effect:{duration:4}},1.16],
      ['Endless Tide',{fireRate:.60,damage:.34,effect:{duration:6}},1.33]
    ]],
    reach: ['Flood Plain', 'Flood a wider stretch of road with longer-range strikes.', [
      ['Outer Sluice',{range:.13,effect:{splash:4}}],
      ['Bank Overflow',{range:.11,effect:{splash:7}}],
      ['Floodgate',{range:.14,effect:{splash:9}}],
      ['Flood Basin',{range:.16,effect:{splash:12}},1.17],
      ['High-Water Mark',{range:.18,effect:{splash:15,duration:4}},1.34]
    ]]
  },
  circuit_weaver: {
    power: ['Power Surge', 'Send heavier pulses through the circuit and interrupt enemies for longer.', [
      ['Surge Cell',{damage:.40}],
      ['Tripped Breaker',{damage:.45,effect:{stunTicks:1}}],
      ['Overvoltage',{damage:.61,effect:{stunTicks:1}}],
      ['Circuit Break',{damage:.79,effect:{stunTicks:1}},1.18],
      ['Grid Blackout',{damage:.96,effect:{stunTicks:2}},1.39]
    ]],
    tempo: ['Switching Clock', 'Close the next circuit faster and interrupt threats more often.', [
      ['Fast Switch',{fireRate:.22}],
      ['Double Clock',{fireRate:.29,damage:.11}],
      ['Polarity Flip',{fireRate:.35,damage:.16}],
      ['Clock Divider',{fireRate:.47,damage:.24},1.15],
      ['Switching Storm',{fireRate:.61,damage:.33},1.31]
    ]],
    reach: ['Woven Grid', 'Reach across the map and add more enemies to each linked strike.', [
      ['Copper Mesh',{range:.14}],
      ['Branch Circuit',{effect:{targets:1},range:.09},1.13],
      ['Extended Traces',{range:.14}],
      ['Parallel Branches',{effect:{targets:1},range:.15},1.22],
      ['City Grid',{effect:{targets:2},range:.17},1.40]
    ]]
  },
  bulwark_beacon: {
    power: ['Sentinel Ward', 'Weaken the enemies that get through and add weight to each beacon strike.', [
      ['Reinforced Signal',{damage:.39,effect:{reduction:.035}}],
      ['Sustained Ward',{damage:.45,effect:{duration:7}}],
      ['Interception Pulse',{damage:.61,effect:{reduction:.05}}],
      ['Fortified Beacon',{damage:.79,effect:{duration:8}},1.16],
      ['Aegis Signal',{damage:.99,effect:{reduction:.065,duration:10}},1.35]
    ]],
    tempo: ['Rapid Intercept', 'Tag incoming threats sooner and keep the weakening signal active.', [
      ['Ready Antenna',{fireRate:.23}],
      ['Quick Intercept',{fireRate:.29,effect:{duration:4}}],
      ['Cycle Counter',{fireRate:.36,damage:.17}],
      ['Rapid Shielding',{fireRate:.47,damage:.23,effect:{duration:5}},1.14],
      ['Round-the-Clock Guard',{fireRate:.60,damage:.32,effect:{duration:7}},1.32]
    ]],
    reach: ['Perimeter Screen', 'Tag more enemies and cover a larger portion of the approach.', [
      ['Rangefinder',{range:.14}],
      ['Twin Beacon',{hitTargets:1,range:.09},1.14],
      ['Early Warning',{range:.14,effect:{duration:7}}],
      ['Three-Point Screen',{hitTargets:1,range:.15},1.24],
      ['Outer Perimeter',{hitTargets:1,range:.18,secondaryDamage:.22},1.4]
    ]]
  },
  nova_siphon: {
    power: ['Nova Compression', 'Condense larger batches of Orbs while the shared battle cap still applies.', [
      ['Dense Intake',{effect:{amount:2}}],
      ['Compression Ring',{effect:{amount:3}}],
      ['Star Chamber',{effect:{amount:4,perSlotCap:12}}],
      ['Nova Press',{effect:{amount:6,perSlotCap:16}},1.15],
      ['Singularity Press',{effect:{amount:8,perSlotCap:23}},1.28]
    ]],
    tempo: ['Fast Intake', 'Bring future Orb batches forward to the waves where you need them.', [
      ['Open Valve',{fireRate:.21}],
      ['Pulse Feed',{fireRate:.27,effect:{amount:1}}],
      ['Accelerated Intake',{fireRate:.35}],
      ['Two-Stage Feed',{fireRate:.44,effect:{amount:2}},1.13],
      ['Nova Intake',{fireRate:.57,effect:{amount:3}},1.25]
    ]],
    reach: ['Nova Reservoir', 'Keep this siphon producing longer before it reaches its individual cap.', [
      ['Spare Vessel',{effect:{perSlotCap:19}}],
      ['Pressure Tank',{effect:{perSlotCap:25}}],
      ['Cold Storage',{effect:{perSlotCap:29,amount:1}}],
      ['Reservoir Wing',{effect:{perSlotCap:35,amount:2}},1.12],
      ['Nova Reserve',{effect:{perSlotCap:46,amount:3}},1.23]
    ]]
  }
};
