// Each tier adds these deltas on top of the previous tiers in its path.
export const CORE_TOWER_PATHS = {
  pulse: {
    power: ['Impact Driver', 'Condense each pulse into an armor-piercing impact.', [
      ['Packed Cell', {damage:.38}],
      ['Hardlight Tip', {damage:.42, armorPierce:.20}],
      ['Core Compression', {damage:.55, armorPierce:.15}],
      ['Breaker Pulse', {damage:.75, armorPierce:.25}, 1.17],
      ['Bastion Buster', {damage:.90, armorPierce:.40, bossDamageMultiplier:.2}, 1.36]
    ]],
    tempo: ['Capacitor Cascade', 'Cycle the capacitors faster and keep a constant stream of pulses.', [
      ['Faster Discharge', {fireRate:.23}],
      ['Parallel Cells', {fireRate:.30, damage:.08}],
      ['Recirculating Charge', {fireRate:.35, damage:.10}],
      ['Ion Clock', {fireRate:.43, damage:.14}, 1.12],
      ['Pulse Torrent', {fireRate:.55, damage:.18}, 1.31]
    ]],
    reach: ['Echo Optics', 'Extend your firing lanes and split pulses between targets.', [
      ['Longglass Lens', {range:.14}],
      ['Echo Splitter', {range:.10, hitTargets:1}, 1.16],
      ['Echo Coherence', {range:.14, secondaryDamage:.12}],
      ['Triad Lenses', {range:.17, hitTargets:1}, 1.22],
      ['Farfield Array', {range:.21, secondaryDamage:.20, hitTargets:1}, 1.36]
    ]]
  },
  arc: {
    power: ['Overvolt Coil', 'Strike with higher voltage and carry more damage through each jump.', [
      ['Copper Windings', {damage:.38}],
      ['Overvolt Core', {damage:.42, chainDamageRatio:.04}],
      ['Ion Channel', {damage:.55, armorPierce:.20}],
      ['Blackout Spike', {damage:.70, chainDamageRatio:.09}, 1.20],
      ['Gridbreaker', {damage:.85, chainDamageRatio:.12, armorPierce:.35}, 1.39]
    ]],
    tempo: ['Alternating Current', 'Cycle bursts rapidly and briefly stun invaders at high tiers.', [
      ['Closed Circuit', {fireRate:.23}],
      ['Dual Oscillator', {fireRate:.27, damage:.08}],
      ['Phase Sync', {fireRate:.31, hitStunTicks:3}, 1.13],
      ['Live Line', {fireRate:.39, damage:.16, hitStunTicks:2}, 1.22],
      ['Brownout Loop', {fireRate:.45, damage:.16, hitStunTicks:3}, 1.37]
    ]],
    reach: ['Transmission Grid', 'Reach across lanes and jump the arc to more enemies.', [
      ['Extended Electrode', {range:.15}],
      ['Bridge Contact', {range:.10, extraTargets:1}, 1.12],
      ['Auxiliary Pylon', {range:.14, extraTargets:1}, 1.12],
      ['Longspan Bus', {range:.15, extraTargets:1}, 1.20],
      ['Lightning Network', {range:.18, extraTargets:2, chainDamageRatio:.10}, 1.38]
    ]]
  },
  frost: {
    power: ['Cryogenic Core', 'Hit harder with shots that leave behind colder, longer chill.', [
      ['Cryo Cartridge', {damage:.42, frostDuration:3}],
      ['Flash Freeze', {damage:.48, hitSlowFactor:-.64, hitSlowDuration:15}, 1.12],
      ['Ice Compression', {damage:.55, hitSlowFactor:-.06, hitSlowDuration:7}],
      ['Bitter Zero', {damage:.70, hitSlowFactor:-.06, hitSlowDuration:7}, 1.20],
      ['Absolute Winter', {damage:.85, hitSlowFactor:-.08, hitSlowDuration:10}, 1.38]
    ]],
    tempo: ['Snowfall Pump', 'Cycle refrigerant faster and interrupt targets with deep bursts.', [
      ['Cold Feed', {fireRate:.25}],
      ['Pressure Loop', {fireRate:.29, frostDuration:5}],
      ['Frozen Valve', {fireRate:.33, hitStunTicks:3}, 1.13],
      ['Permafrost Pump', {fireRate:.38, frostDuration:8, damage:.15}, 1.16],
      ['Whiteout Flow', {fireRate:.45, hitStunTicks:5, damage:.20}, 1.33]
    ]],
    reach: ['Cryo Fork', 'Route chill through additional barrels to keep a lane covered.', [
      ['Polar Sight', {range:.16}],
      ['Twin Frost Nozzle', {range:.09, hitTargets:1}, 1.16],
      ['Drift Lens', {range:.15, frostDuration:7}],
      ['Blizzard Manifold', {range:.16, hitTargets:1}, 1.23],
      ['Tundra Battery', {range:.19, hitTargets:2, frostDuration:10}, 1.38]
    ]]
  },
  firewall: {
    power: ['Thermite Furnace', 'Deliver hotter shells and leave a more damaging burn.', [
      ['Thermite Blend', {damage:.37, burnDamageRatio:.004}],
      ['White Flame', {damage:.40, burnDamageRatio:.005}],
      ['Refractory Core', {damage:.52, burnDuration:5, burnDamageRatio:.007}],
      ['Flashpoint Shells', {damage:.73, burnDamageRatio:.010}, 1.23],
      ['Star Furnace', {damage:.88, burnDuration:9, burnDamageRatio:.013}, 1.40]
    ]],
    tempo: ['Pilot Flame', 'Maintain bombardment with faster ignition and longer-lived fire.', [
      ['Hot Primer', {fireRate:.24}],
      ['Fuel Rail', {fireRate:.29, burnDuration:5}],
      ['Dual Igniters', {fireRate:.33, damage:.10}],
      ['Continuous Feed', {fireRate:.40, burnDuration:7, damage:.14}, 1.18],
      ['Refinery Flare', {fireRate:.45, burnDuration:10, damage:.20}, 1.32]
    ]],
    reach: ['Firebreak', 'Broaden each blast and cover enemies farther from the turret.', [
      ['Long Throw', {range:.14, legacySplash:7}],
      ['Oil Burst', {range:.09, legacySplash:10}],
      ['Flare Canister', {range:.13, legacySplash:12}, 1.12],
      ['Wildfire Lanes', {range:.14, legacySplash:15}, 1.22],
      ['Containment Breach', {range:.17, legacySplash:20, burnDuration:8}, 1.36]
    ]]
  },
  block: {
    power: ['Tungsten Mass', 'Send heavier armor-piercing blocks through high-value targets.', [
      ['Solid Slug', {damage:.37}],
      ['Tungsten Infill', {damage:.45}],
      ['Press Forged', {damage:.58, bossDamageMultiplier:.12}],
      ['Siegebreaker Block', {damage:.72, bossDamageMultiplier:.14}, 1.20],
      ['Fortress Wedge', {damage:.90, bossDamageMultiplier:.22}, 1.41]
    ]],
    tempo: ['Magnetic Breech', 'Reload faster and stagger enemies with repeated block impacts.', [
      ['Balanced Counterweight', {fireRate:.24}],
      ['Twin Breech', {fireRate:.29, damage:.08}],
      ['Magnetic Rams', {fireRate:.32, hitStunTicks:3}],
      ['Indexed Magazine', {fireRate:.39, damage:.17, hitStunTicks:2}, 1.20],
      ['Rail Loader', {fireRate:.47, damage:.21, hitStunTicks:4}, 1.36]
    ]],
    reach: ['Block Battery', 'Reach farther down the track and fire at several enemies.', [
      ['Elevated Cradle', {range:.13}],
      ['Duplex Barrel', {range:.10, hitTargets:1}, 1.15],
      ['Gimbal Sights', {range:.13, secondaryDamage:.12}],
      ['Salvo Mount', {range:.14, hitTargets:1}, 1.20],
      ['Broadside Blocks', {range:.18, secondaryDamage:.17, hitTargets:1}, 1.37]
    ]]
  },
  validator: {
    power: ['Consensus Authority', 'Increase the damage aura granted to nearby weapons.', [
      ['Trusted Node', {damageAura:.040}],
      ['Signed Rounds', {damageAura:.046}],
      ['Quorum Seal', {damageAura:.056}],
      ['Authority Key', {damageAura:.076}, 1.22],
      ['Unanimous Mandate', {damageAura:.105}, 1.39]
    ]],
    tempo: ['Clock Consensus', 'Grant nearby weapons attack speed and increase the aura’s haste limit.', [
      ['Timing Signal', {hasteAura:.06}],
      ['Synchronized Clocks', {hasteAura:.07}],
      ['Fast Quorum', {hasteAura:.08, hasteCap:.07}],
      ['Rapid Finality', {hasteAura:.09, hasteCap:.07}, 1.20],
      ['Instant Accord', {hasteAura:.11, hasteCap:.08}, 1.39]
    ]],
    reach: ['Broadcast Domain', 'Extend the aura to more towers and reinforce signal strength at high tiers.', [
      ['Broadcast Antenna', {range:.13}],
      ['Field Repeater', {range:.13}],
      ['Open Mesh', {range:.15, damageAura:.025}],
      ['Distant Quorum', {range:.17, damageAura:.035}, 1.16],
      ['Sector Authority', {range:.21, damageAura:.055}, 1.33]
    ]]
  },
  prism: {
    power: ['Hardlight Focus', 'Concentrate piercing beams and preserve damage across the beam fan.', [
      ['Brilliant Aperture', {damage:.39}],
      ['Optical Polish', {damage:.42, chainDamageRatio:.04}],
      ['Beam Pinch', {damage:.56, chainDamageRatio:.05}],
      ['Hardlight Convergence', {damage:.71, chainDamageRatio:.07}, 1.21],
      ['White Spectrum', {damage:.84, chainDamageRatio:.11}, 1.37]
    ]],
    tempo: ['Optical Clock', 'Refocus the beam faster and disrupt enemies with flickering light.', [
      ['Quick Iris', {fireRate:.23}],
      ['Fast Refraction', {fireRate:.28, damage:.08}],
      ['Liquid Shutter', {fireRate:.32, hitStunTicks:3}],
      ['Strobe Focus', {fireRate:.39, damage:.15, hitStunTicks:2}, 1.18],
      ['Photon Flash', {fireRate:.45, damage:.18, hitStunTicks:4}, 1.34]
    ]],
    reach: ['Spectral Fan', 'Spread beams farther and refract them toward extra enemies.', [
      ['Wideband Lens', {range:.15}],
      ['Twin Spectrum', {range:.10, extraTargets:1}, 1.14],
      ['Folding Mirrors', {range:.14, extraTargets:1}],
      ['Facet Assembly', {range:.16, extraTargets:1}, 1.23],
      ['Crown of Glass', {range:.19, extraTargets:2, chainDamageRatio:.10}, 1.39]
    ]]
  },
  repeater: {
    power: ['Critical Bolts', 'Turn timed critical hits into concentrated bursts of damage.', [
      ['Heavy Bolt', {damage:.31, effect:{criticalMultiplier:.15}}],
      ['Marked Chambers', {damage:.31, effect:{criticalEvery:-1}}],
      ['Double Charge', {damage:.40, effect:{criticalMultiplier:.35}}],
      ['Critical Timing', {damage:.57, effect:{criticalEvery:-1,criticalMultiplier:.30}}, 1.21],
      ['Redline Bolts', {damage:.73, effect:{criticalEvery:-1,criticalMultiplier:.45}}, 1.42]
    ]],
    tempo: ['Burst Governor', 'Keep short gaps between shots and build toward sustained rapid fire.', [
      ['Spring Indexer', {fireRate:.30}],
      ['Buffered Trigger', {fireRate:.30, damage:.15}],
      ['Dual Feed Belt', {fireRate:.34, damage:.15}],
      ['Zero Drag', {fireRate:.42, damage:.20}, 1.17],
      ['Continuous Burst', {fireRate:.69, damage:.30}, 1.39]
    ]],
    reach: ['Longburst Array', 'Reach beyond the front line and thread bursts into extra enemies.', [
      ['Steady Stock', {range:.15}],
      ['Split Barrel', {range:.09, hitTargets:1}, 1.14],
      ['Tight Grouping', {range:.15, secondaryDamage:.14}],
      ['Scatter Bolts', {range:.16, hitTargets:1}, 1.21],
      ['Firing Line', {range:.18, hitTargets:1, secondaryDamage:.18}, 1.36]
    ]]
  },
  sniper: {
    power: ['Armor Punch', 'Turn precision shots into a dedicated counter to armor and bosses.', [
      ['Dense Jacket', {damage:.37, effect:{armorPierce:.05}}],
      ['Tungsten Needle', {damage:.43, effect:{armorPierce:.10}}],
      ['Boss Optics', {damage:.52, bossDamageMultiplier:.12}],
      ['Breaker Rifle', {damage:.70, bossDamageMultiplier:.15}, 1.21],
      ['Dreadnought Killer', {damage:.87, bossDamageMultiplier:.23}, 1.42]
    ]],
    tempo: ['Smooth Bolt', 'Chamber shots rapidly and briefly interrupt heavy enemies.', [
      ['Oiled Action', {fireRate:.24}],
      ['Spring Assist', {fireRate:.28, damage:.08}],
      ['Counter Recoil', {fireRate:.34, hitStunTicks:3}],
      ['Tracking Bolt', {fireRate:.39, damage:.15, hitStunTicks:3}, 1.16],
      ['Snaplock', {fireRate:.47, damage:.22, hitStunTicks:4}, 1.34]
    ]],
    reach: ['Recon Optics', 'Cover long lanes and hit additional targets with spotter-assisted shots.', [
      ['Survey Lens', {range:.13}],
      ['Spotter Drone', {range:.09, hitTargets:1}, 1.13],
      ['Stabilized Optics', {range:.12, secondaryDamage:.12}],
      ['Remote Targeter', {range:.15, hitTargets:1}, 1.22],
      ['Cross-Sector Scope', {range:.18, secondaryDamage:.18, hitTargets:1}, 1.36]
    ]]
  },
  scatter: {
    power: ['Heavy Pellets', 'Hit enemies in the cone with dense, armor-piercing pellets.', [
      ['Packed Shot', {damage:.40}],
      ['Steel Pellets', {damage:.42, armorPierce:.16}],
      ['Dense Canister', {damage:.55, armorPierce:.14}],
      ['Ceramic Shards', {damage:.70, armorPierce:.21}, 1.21],
      ['Siege Flechettes', {damage:.88, armorPierce:.24}, 1.38]
    ]],
    tempo: ['Auto Chamber', 'Send volleys downrange faster and sustain damage over the whole cone.', [
      ['Split Loading Tray', {fireRate:.25}],
      ['Recoil Spring', {fireRate:.28, damage:.09}],
      ['Drum Chamber', {fireRate:.33, damage:.12}],
      ['Volley Drive', {fireRate:.40, damage:.16}, 1.19],
      ['Pellet Storm', {fireRate:.47, damage:.23}, 1.38]
    ]],
    reach: ['Wide Choke', 'Widen the cone and fill it with more targets per volley.', [
      ['Bored Choke', {range:.14, effect:{angle:.10}}],
      ['Wide Pattern', {range:.08, effect:{angle:.09,targets:1}}],
      ['Sleeved Barrel', {range:.12, effect:{angle:.13,targets:1}}],
      ['Fan Choke', {range:.14, effect:{angle:.16,targets:2}}, 1.21],
      ['Full Arc Volley', {range:.16, effect:{angle:.20,targets:2}}, 1.37]
    ]]
  },
  shredder: {
    power: ['Corrosive Teeth', 'Strip tougher armor faster while grinding through targets.', [
      ['Biting Edges', {damage:.36, effect:{armorBreak:.012}}],
      ['Corrosive Teeth', {damage:.41, effect:{maxArmorBreak:.06}}],
      ['Chrome Grinder', {damage:.53, effect:{armorBreak:.018,maxArmorBreak:.06}}],
      ['Armor Mill', {damage:.71, effect:{armorBreak:.025,maxArmorBreak:.07}}, 1.20],
      ['Metal Dissolver', {damage:.86, effect:{armorBreak:.040,maxArmorBreak:.10}}, 1.38]
    ]],
    tempo: ['Twin Rotors', 'Land more hits and keep armor stripped for longer.', [
      ['Low Friction Bearings', {fireRate:.24}],
      ['Dual Rotors', {fireRate:.29, effect:{duration:7}}],
      ['Serrated Belt', {fireRate:.32, damage:.10, effect:{duration:7}}],
      ['Rotor Governor', {fireRate:.39, damage:.14, effect:{duration:9}}, 1.16],
      ['Continuous Grind', {fireRate:.46, damage:.20, effect:{duration:12}}, 1.35]
    ]],
    reach: ['Stripping Array', 'Apply armor break to more enemies across the lane.', [
      ['Long Arm', {range:.14}],
      ['Forked Teeth', {range:.09, hitTargets:1}, 1.13],
      ['Widened Shaft', {range:.13, secondaryDamage:.11}],
      ['Three Jaw Rack', {range:.16, hitTargets:1}, 1.20],
      ['Dismantling Line', {range:.19, hitTargets:1, secondaryDamage:.16}, 1.37]
    ]]
  },
  executioner: {
    power: ['Final Judgment', 'Execute enemies at higher health and punish wounded bosses.', [
      ['Weighted Blade', {damage:.39, effect:{threshold:.02}}],
      ['Merciless Edge', {damage:.44, effect:{threshold:.03}}],
      ['Reaper Seal', {damage:.53, effect:{threshold:.03,bossMultiplier:.15}}],
      ['Death Sentence', {damage:.68, effect:{threshold:.04,bossMultiplier:.25}}, 1.22],
      ['Final Decree', {damage:.83, effect:{threshold:.05,bossMultiplier:.45}}, 1.42]
    ]],
    tempo: ['Quick Verdict', 'Speed up executions and stagger targets that survive the hit.', [
      ['Short Draw', {fireRate:.24}],
      ['Fast Counter', {fireRate:.28, damage:.08}],
      ['Stagger Strike', {fireRate:.34, hitStunTicks:3}],
      ['Passing Sentence', {fireRate:.39, damage:.15, hitStunTicks:3}, 1.20],
      ['No Reprieve', {fireRate:.47, damage:.22, hitStunTicks:4}, 1.37]
    ]],
    reach: ['Long Arm of Judgment', 'Enforce judgments from farther away and cut through armor.', [
      ['Far Mark', {range:.14}],
      ['Honed Verdict', {range:.10, armorPierce:.18}],
      ['Unflinching Reach', {range:.14, armorPierce:.22, damage:.11}],
      ['Judgment Beacon', {range:.17, armorPierce:.27, damage:.16}, 1.17],
      ['Verdict Across the Void', {range:.20, armorPierce:.33, damage:.22}, 1.35]
    ]]
  },
  howitzer: {
    power: ['Siege Charge', 'Break armored groups with heavier explosive shells.', [
      ['Packed Explosive', {damage:.37}],
      ['Shaped Warhead', {damage:.42, armorPierce:.16}],
      ['Bursting Jacket', {damage:.54, armorPierce:.14}],
      ['Siege Hammer', {damage:.72, armorPierce:.20}, 1.21],
      ['Citadel Breaker', {damage:.88, armorPierce:.24, bossDamageMultiplier:.14}, 1.42]
    ]],
    tempo: ['Mechanical Loader', 'Accelerate the reload and add suppressive shell bursts.', [
      ['Spring Magazine', {fireRate:.24}],
      ['Ram Assist', {fireRate:.29, damage:.08}],
      ['Alternating Trays', {fireRate:.33, hitStunTicks:3}],
      ['Suppression Fire', {fireRate:.39, damage:.14, hitStunTicks:2}, 1.20],
      ['Rolling Barrage', {fireRate:.48, damage:.20, hitStunTicks:4}, 1.39]
    ]],
    reach: ['High Elevation', 'Cover a wider area and reduce the dead zone around the gun.', [
      ['High Angle Carriage', {range:.13, effect:{minRange:-8}}],
      ['Steep Trajectory', {range:.09, effect:{minRange:-9,splash:7}}],
      ['Airburst Shell', {range:.13, effect:{minRange:-10,splash:10}}],
      ['Overhead Strike', {range:.15, effect:{minRange:-13,splash:13}}, 1.20],
      ['All-Angle Bombardment', {range:.19, effect:{minRange:-20,splash:18}}, 1.38]
    ]]
  },
  minefield: {
    power: ['Shaped Charges', 'Blast through armor and stun enemies caught in high-tier detonations.', [
      ['Dense Charge', {damage:.40}],
      ['Hull Spike', {damage:.42, armorPierce:.16}],
      ['Blasting Core', {damage:.54, armorPierce:.19}],
      ['Concussion Mine', {damage:.70, armorPierce:.20, hitStunTicks:4}, 1.21],
      ['Deep-Seam Charge', {damage:.87, armorPierce:.24, hitStunTicks:5}, 1.40]
    ]],
    tempo: ['Snap Fuse', 'Plant mines more often, arm them sooner and stock more active traps.', [
      ['Quick Cradle', {fireRate:.24}],
      ['Fast Fuse', {fireRate:.29, effect:{armTicks:-1}}],
      ['Cartridge Rack', {fireRate:.32, effect:{limit:1}}],
      ['Dual Armature', {fireRate:.40, effect:{armTicks:-1,limit:1}}, 1.17],
      ['Instant Detonator', {fireRate:.48, effect:{armTicks:-1,limit:2}}, 1.38]
    ]],
    reach: ['Mine Network', 'Lay mines farther out and widen both their sensor and blast radius.', [
      ['Long Placement Arm', {range:.14, effect:{triggerRadius:3}}],
      ['Seismic Sensor', {range:.08, effect:{triggerRadius:4,splash:6}}],
      ['Buried Relay', {range:.12, effect:{triggerRadius:5,splash:8,lifetime:25}}],
      ['Interlinked Traps', {range:.16, effect:{triggerRadius:6,splash:11,lifetime:35}}, 1.20],
      ['No Entry Zone', {range:.18, effect:{triggerRadius:8,splash:16,lifetime:55}}, 1.39]
    ]]
  },
  seismic: {
    power: ['Deep Tremor', 'Drive stronger shockwaves and stun clusters for longer.', [
      ['Weighted Piston', {damage:.38, effect:{stunTicks:1}}],
      ['Bedrock Strike', {damage:.42, effect:{stunTicks:1}}],
      ['Shear Plate', {damage:.53, effect:{stunTicks:2}}],
      ['Continental Shift', {damage:.70, effect:{stunTicks:2}}, 1.21],
      ['Mantle Fracture', {damage:.86, effect:{stunTicks:3}}, 1.40]
    ]],
    tempo: ['Resonance Driver', 'Cycle the piston rapidly and weaken armor through vibration.', [
      ['Resonant Spring', {fireRate:.24}],
      ['Rebound Plate', {fireRate:.28, damage:.08}],
      ['Harmonic Driver', {fireRate:.33, armorPierce:.15}],
      ['Echoing Tremor', {fireRate:.39, damage:.15, armorPierce:.18}, 1.18],
      ['Resonance Cascade', {fireRate:.48, damage:.21, armorPierce:.25}, 1.38]
    ]],
    reach: ['Fault Line', 'Project shockwaves farther and expand the area of each tremor.', [
      ['Long Fault', {range:.14, effect:{splash:6}}],
      ['Branching Fault', {range:.08, effect:{splash:9}}],
      ['Seismic Echo', {range:.12, effect:{splash:11}}],
      ['Fracture Belt', {range:.16, effect:{splash:15}}, 1.21],
      ['Rupture Zone', {range:.19, effect:{splash:20,stunTicks:3}}, 1.39]
    ]]
  },
  meteor: {
    power: ['Dense Core', 'Drop heavier impacts and carry more damage toward the blast edge.', [
      ['Iron Meteor', {damage:.39}],
      ['Nickel-Iron Core', {damage:.42, effect:{edgeDamage:.04}}],
      ['Deep Impact', {damage:.54, effect:{edgeDamage:.07}}],
      ['Crust Breaker', {damage:.71, effect:{edgeDamage:.10}}, 1.20],
      ['Extinction Impact', {damage:.89, effect:{edgeDamage:.16}}, 1.43]
    ]],
    tempo: ['Orbital Descent', 'Call impacts in rapid succession and suppress enemies at the strike site.', [
      ['Rapid Plotting', {fireRate:.24}],
      ['Guided Reentry', {fireRate:.29, damage:.08}],
      ['Descent Window', {fireRate:.33, hitStunTicks:3}],
      ['Orbital Battery', {fireRate:.41, damage:.14, hitStunTicks:2}, 1.20],
      ['Meteor Shower', {fireRate:.49, damage:.19, hitStunTicks:4}, 1.41]
    ]],
    reach: ['Crater Field', 'Reach distant bends and expand the full impact zone.', [
      ['Downrange Relay', {range:.13, effect:{splash:7}}],
      ['Fragmentation Core', {range:.09, effect:{splash:10}}],
      ['Crater Ring', {range:.12, effect:{splash:13}}],
      ['Crater Chain', {range:.16, effect:{splash:16}}, 1.21],
      ['Crater Continent', {range:.19, effect:{splash:22,edgeDamage:.08}}, 1.40]
    ]]
  },
  venom: {
    power: ['Potent Toxin', 'Brew concentrated poison that deals more damage with each dose.', [
      ['Concentrated Venom', {damage:.23, effect:{tickDamage:.012}}],
      ['Caustic Blend', {damage:.20, effect:{tickDamage:.019}}],
      ['Toxin Reactor', {damage:.25, effect:{tickDamage:.024}}],
      ['Biohazard Compound', {damage:.30, effect:{tickDamage:.032}}, 1.22],
      ['Lethal Distillate', {damage:.36, effect:{tickDamage:.047}}, 1.42]
    ]],
    tempo: ['Long Exposure', 'Apply poison more often and keep more doses active on each target.', [
      ['Dosing Valve', {fireRate:.24}],
      ['Persistent Toxin', {fireRate:.24, effect:{duration:12}}],
      ['Infusion Cycle', {fireRate:.28, effect:{stacks:1,duration:8}}, 1.12],
      ['Deep Infusion', {fireRate:.34, effect:{stacks:1,duration:10}}, 1.22],
      ['Sustained Exposure', {fireRate:.41, effect:{stacks:1,duration:15}}, 1.42]
    ]],
    reach: ['Virulent Mist', 'Poison at longer range and spread weaker doses to nearby enemies.', [
      ['Caustic Jet', {damage:.18, range:.12}],
      ['Spreading Venom', {range:.07, effect:{poisonSpreadTargets:1,poisonSpreadRadius:55,poisonSpreadDamage:.55}}, 1.16],
      ['Mist Expansion', {range:.11, effect:{poisonSpreadTargets:1,poisonSpreadRadius:13}}, 1.15],
      ['Vapor Catalyst', {range:.13, effect:{poisonSpreadTargets:1,poisonSpreadRadius:17,poisonSpreadDamage:.10}}, 1.26],
      ['Virulent Fog', {range:.17, effect:{poisonSpreadTargets:2,poisonSpreadRadius:22,poisonSpreadDamage:.15}}, 1.45]
    ]]
  },
  glacier: {
    power: ['Deep Freeze', 'Amplify damage and make the chain’s chill more severe.', [
      ['Ice Crystal', {damage:.40, effect:{factor:-.025}}],
      ['Dense Frost', {damage:.43, effect:{factor:-.030}}],
      ['Subzero Crystal', {damage:.55, effect:{factor:-.035,duration:4}}],
      ['Polar Vortex', {damage:.70, effect:{factor:-.040,duration:6}}, 1.22],
      ['Glacial Lock', {damage:.87, effect:{factor:-.050,duration:8}}, 1.40]
    ]],
    tempo: ['Cold Cycle', 'Keep enemies chilled with shorter intervals and longer-lasting pulses.', [
      ['Coolant Pump', {fireRate:.23}],
      ['Staged Cooling', {fireRate:.28, effect:{duration:5}}],
      ['Thaw Inhibitor', {fireRate:.33, effect:{duration:6}, damage:.10}],
      ['Cryo Circulator', {fireRate:.39, effect:{duration:8}, damage:.14}, 1.16],
      ['Ice-Lock Cycle', {fireRate:.46, effect:{duration:11}, damage:.20}, 1.36]
    ]],
    reach: ['Glacier Chain', 'Extend the chill chain across a larger part of the track.', [
      ['Glacier Lens', {range:.15}],
      ['Fourth Link', {range:.09, effect:{targets:1}}, 1.14],
      ['Ice Bridge', {range:.13, effect:{targets:1}}],
      ['Permafrost Links', {range:.16, effect:{targets:1}}, 1.21],
      ['Ice Shelf Array', {range:.19, effect:{targets:2,duration:7}}, 1.40]
    ]]
  },
  disruptor: {
    power: ['Signal Crush', 'Hit harder and weaken more of the damage enemies can deal to the core.', [
      ['Signal Amplifier', {damage:.39, effect:{reduction:.025}}],
      ['Tuned Interference', {damage:.42, effect:{reduction:.035}}],
      ['Defense Spoof', {damage:.55, effect:{reduction:.050}}],
      ['Command Override', {damage:.70, effect:{reduction:.090}}, 1.20],
      ['Hostile Shutdown', {damage:.87, bossDamageMultiplier:.18, effect:{duration:16}}, 1.39]
    ]],
    tempo: ['Burst Interference', 'Refresh interference rapidly and make weakened signals linger.', [
      ['Fast Oscillation', {fireRate:.24}],
      ['Carrier Sweep', {fireRate:.28, effect:{duration:7}}],
      ['Signal Persistence', {fireRate:.33, effect:{duration:9}, damage:.09}],
      ['Constant Jammer', {fireRate:.39, effect:{duration:12}, damage:.14}, 1.16],
      ['Permanent Static', {fireRate:.46, effect:{duration:18}, damage:.22}, 1.35]
    ]],
    reach: ['Signal Flood', 'Hit and weaken extra enemies from across a wider sector.', [
      ['Directional Transmitter', {range:.14}],
      ['Dual Carrier', {range:.09, hitTargets:1}, 1.13],
      ['Broad Antenna', {range:.13, secondaryDamage:.10}],
      ['Command Net', {range:.16, hitTargets:1}, 1.22],
      ['Sector Flood', {range:.19, hitTargets:1, secondaryDamage:.14}, 1.39]
    ]]
  },
  storm: {
    power: ['Thunderhead', 'Raise the voltage and stun targets for longer with each arc.', [
      ['Charge Bank', {damage:.40, effect:{stunTicks:1}}],
      ['Thunder Coil', {damage:.43, effect:{stunTicks:1}}],
      ['Cloud Charge', {damage:.53, effect:{stunTicks:2}}],
      ['Ground Flash', {damage:.71, effect:{stunTicks:2}}, 1.21],
      ['Supercell Strike', {damage:.86, effect:{stunTicks:4}}, 1.43]
    ]],
    tempo: ['Flash Cycle', 'Cycle repeated strikes and add extra armor penetration.', [
      ['Spark Return', {fireRate:.24}],
      ['Charge Recovery', {fireRate:.29, damage:.08}],
      ['Flash Converter', {fireRate:.33, armorPierce:.14}],
      ['Strobe Arc', {fireRate:.40, damage:.15, armorPierce:.17}, 1.18],
      ['Endless Thunder', {fireRate:.48, damage:.21, armorPierce:.23}, 1.38]
    ]],
    reach: ['Lightning Mesh', 'Extend the relay’s range and stun more enemies in the chain.', [
      ['Air Terminal', {range:.14}],
      ['Mesh Contact', {range:.10, effect:{targets:1}}, 1.15],
      ['Triangulated Relay', {range:.12, effect:{targets:1}}, 1.12],
      ['Wideband Discharge', {range:.16, effect:{targets:1}}, 1.22],
      ['Thunder Grid', {range:.20, effect:{targets:2,stunTicks:2}}, 1.42]
    ]]
  }
};
