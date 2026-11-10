// All map coordinates use a 960 x 540 board. Released layouts are immutable:
// a saved battle must replay against the original road and construction sites.
import {CAMPAIGN_WORLDS} from './campaign-worlds.js';
const freezePads = maps => Object.freeze(maps.map(pads => Object.freeze(pads.map(pad => Object.freeze(pad)))));
export const MAP_LAYOUT_VERSION = 6;
// The generated lower atlas quadrants did not retain the guide's Y positions.
// Trace their painted road centres explicitly; old snapshots keep MAPS below.
export const VERSION_THREE_PLACEMENT_PATHS = freezePads([
  [{x:-30,y:96},{x:180,y:96},{x:180,y:236},{x:402,y:236},{x:402,y:88},{x:650,y:88},{x:650,y:352},{x:846,y:352},{x:846,y:474},{x:1010,y:474}],
  [{x:-30,y:274},{x:150,y:274},{x:150,y:102},{x:382,y:102},{x:382,y:420},{x:620,y:420},{x:620,y:188},{x:830,y:188},{x:830,y:380},{x:1010,y:380}],
  [{x:-30,y:97},{x:250,y:97},{x:250,y:321},{x:458,y:321},{x:458,y:146},{x:726,y:146},{x:726,y:394},{x:897,y:394},{x:897,y:246},{x:1010,y:246}],
  [{x:-30,y:372},{x:171,y:372},{x:171,y:111},{x:418,y:111},{x:418,y:286},{x:648,y:286},{x:648,y:91},{x:845,y:91},{x:845,y:402},{x:1010,y:402}]
]);
export const PREVIOUS_PLACEMENT_PADS = freezePads([
  [
    {x:92,y:176},{x:274,y:126},{x:294,y:320},{x:482,y:164},
    {x:538,y:326},{x:724,y:180},{x:746,y:438},{x:888,y:286},
    {x:414,y:352},{x:777,y:282},{x:110,y:257},{x:548,y:412}
  ],
  [
    {x:70,y:188},{x:264,y:172},{x:282,y:300},{x:486,y:172},
    {x:514,y:322},{x:733,y:257},{x:767,y:425},{x:921,y:296},
    {x:528,y:76},{x:82,y:432},{x:233,y:391},{x:63,y:348}
  ],
  [
    {x:124,y:194},{x:350,y:202},{x:342,y:420},{x:565,y:248},
    {x:628,y:326},{x:812,y:300},{x:810,y:498},{x:928,y:179},
    {x:620,y:65},{x:156,y:360},{x:510,y:68},{x:525,y:445}
  ],
  [
    {x:230,y:288},{x:296,y:210},{x:305,y:350},{x:528,y:181},
    {x:445,y:402},{x:758,y:184},{x:725,y:370},{x:925,y:236},
    {x:376,y:50},{x:746,y:280},{x:535,y:477},{x:338,y:280}
  ]
]);

// Audited on the actual illustrated surfaces, rather than only testing road
// clearance. In particular, move off the forest shrub bank, the waterline, the
// Ember boulder and the cave's top edge. The island sites land on grass tops.
export const VERSION_THREE_PLACEMENT_PADS = freezePads([
  [
    {x:94,y:176},{x:286,y:163},{x:294,y:320},{x:498,y:168},
    {x:538,y:326},{x:730,y:181},{x:746,y:438},{x:866,y:254},
    {x:420,y:354},{x:777,y:282},{x:110,y:257},{x:548,y:412}
  ],
  [
    {x:70,y:188},{x:264,y:172},{x:282,y:300},{x:486,y:172},
    {x:514,y:322},{x:733,y:257},{x:767,y:425},{x:173,y:440},
    {x:528,y:82},{x:82,y:432},{x:233,y:391},{x:63,y:348}
  ],
  [
    {x:124,y:194},{x:350,y:202},{x:342,y:420},{x:565,y:248},
    {x:628,y:326},{x:812,y:300},{x:615,y:402},{x:838,y:219},
    {x:620,y:80},{x:156,y:360},{x:510,y:80},{x:525,y:445}
  ],
  [
    {x:242,y:288},{x:296,y:210},{x:305,y:350},{x:515,y:177},
    {x:445,y:402},{x:758,y:184},{x:725,y:370},{x:571,y:222},
    {x:621,y:414},{x:746,y:280},{x:535,y:450},{x:338,y:280}
  ]
]);

// Version four uses the separately painted maps and freeform construction.
// These road centres were measured on those images, not inherited from the
// legacy atlas. Land/shoreline/scenery collision lives in terrain-placement.js.
export const VERSION_FOUR_PLACEMENT_PATHS = freezePads([
  [{x:-30,y:94},{x:181,y:94},{x:181,y:234},{x:402,y:234},{x:402,y:94},{x:648,y:94},{x:648,y:354},{x:849,y:354},{x:849,y:472},{x:1010,y:472}],
  [{x:-30,y:260},{x:149,y:260},{x:149,y:95},{x:384,y:95},{x:384,y:410},{x:620,y:410},{x:620,y:181},{x:840,y:181},{x:840,y:367},{x:1010,y:367}],
  [{x:-30,y:94},{x:251,y:94},{x:251,y:315},{x:453,y:315},{x:453,y:142},{x:724,y:142},{x:724,y:390},{x:898,y:390},{x:898,y:250},{x:1010,y:250}],
  [{x:-30,y:351},{x:173,y:351},{x:173,y:111},{x:420,y:111},{x:420,y:270},{x:647,y:270},{x:647,y:97},{x:837,y:97},{x:837,y:391},{x:1010,y:391}]
]);
export const VERSION_FOUR_PLACEMENT_PADS = freezePads([[],[],[],[]]);

// The Lagoon repaint is a new layout contract; old attempts keep their exact
// v4 roads, terrain and illustration. Other biomes retain their v4 surfaces.
export const VERSION_FIVE_PLACEMENT_PATHS = freezePads(VERSION_FOUR_PLACEMENT_PATHS.map((path,index)=>index===1?[
  {x:-30,y:256},{x:123,y:256},{x:133,y:254},{x:141,y:249},{x:147,y:240},{x:149,y:230},
  {x:149,y:122},{x:151,y:112},{x:156,y:104},{x:164,y:99},{x:174,y:97},
  {x:362,y:97},{x:372,y:99},{x:380,y:104},{x:385,y:112},{x:387,y:122},
  {x:387,y:368},{x:389,y:378},{x:394,y:386},{x:402,y:391},{x:412,y:393},
  {x:595,y:393},{x:605,y:391},{x:613,y:386},{x:618,y:378},{x:620,y:368},
  {x:620,y:202},{x:622,y:192},{x:627,y:184},{x:635,y:179},{x:645,y:177},
  {x:815,y:177},{x:825,y:179},{x:833,y:184},{x:838,y:192},{x:840,y:202},
  {x:840,y:338},{x:842,y:348},{x:847,y:356},{x:855,y:361},{x:865,y:363},{x:1010,y:363}
]:path));
export const VERSION_FIVE_PLACEMENT_PADS = VERSION_FOUR_PLACEMENT_PADS;

// New campaign sectors are a separate contract. The first four retain the
// exact released v5 surfaces; the sixteen additional sectors begin at level21.
export const PLACEMENT_PATHS = freezePads([...VERSION_FIVE_PLACEMENT_PATHS,...CAMPAIGN_WORLDS.map(world=>world.path)]);
export const PLACEMENT_PADS = freezePads(Array.from({length:20},()=>[]));
