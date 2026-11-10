// Shared by the browser preview and authoritative battle replay. This module
// deliberately has no renderer, browser, database or image-decoder dependency.
import {PLACEMENT_PATHS,VERSION_FOUR_PLACEMENT_PATHS,VERSION_FIVE_PLACEMENT_PATHS,MAP_LAYOUT_VERSION} from './map-layout.js';
import {CAMPAIGN_WORLDS} from './campaign-worlds.js';

export const PLACEMENT_BOARD_WIDTH=960;
export const PLACEMENT_BOARD_HEIGHT=540;
export const TOWER_FOOTPRINT_RX=24;
export const TOWER_FOOTPRINT_RY=24*Math.sin(55*Math.PI/180);
export const PLACEMENT_MARGIN=3;
// The tallest tower's animated silhouette needs space above its ground origin.
// This guard is shared with replay so an accepted tower cannot be clipped by
// the top of the board even when the ground itself reaches the image edge.
export const MIN_TOWER_CENTRE_Y=80;
// Ember's stone borders are visibly wider than the garden/island lanes.
export const ROAD_HALF_WIDTHS=Object.freeze([32,32,38,35]);
export const ROAD_HALF_WIDTH=Math.max(...ROAD_HALF_WIDTHS);
const RX=TOWER_FOOTPRINT_RX+PLACEMENT_MARGIN,RY=TOWER_FOOTPRINT_RY+PLACEMENT_MARGIN;
const EPSILON=1e-8;
const BIOMES=['forest','lagoon','ember','cave'];

// Traced on the final 1672 x 941 painted maps. Polygons describe continuous
// walkable ground, including all the space between former construction sites.
// Lagoon polygons follow individual grass-topped islands, never their water.
const P=points=>points.map(([x,y])=>({x:x*960/1672,y:y*540/941}));
const LAND=[
  [P([[0,246],[55,223],[115,225],[187,219],[256,205],[365,205],[385,180],[413,125],[445,105],[535,112],[635,110],[770,100],[1110,100],[1190,160],[1260,208],[1365,220],[1435,255],[1510,330],[1605,414],[1660,476],[1640,515],[1580,565],[1595,642],[1575,715],[1545,745],[1575,790],[1672,800],[1672,915],[1445,902],[1290,862],[1200,820],[1105,790],[1020,786],[970,838],[884,872],[800,836],[725,792],[650,770],[560,745],[450,715],[350,650],[270,610],[215,545],[170,488],[145,435],[83,407],[0,390]])],
  [
    P([[0,246],[51,241],[92,225],[144,232],[177,254],[205,255],[210,402],[96,414],[0,401]]),
    P([[381,247],[422,224],[488,220],[550,230],[593,260],[598,325],[563,356],[472,369],[419,340],[392,298]]),
    P([[797,95],[852,56],[935,61],[1055,70],[1082,120],[1063,171],[1032,191],[967,218],[923,235],[930,308],[894,337],[833,359],[762,344],[731,310],[728,265],[750,223],[805,185],[795,144]]),
    P([[63,556],[117,522],[176,516],[235,530],[290,546],[349,572],[390,545],[414,493],[441,468],[498,452],[545,452],[573,483],[607,505],[613,552],[592,596],[558,618],[548,669],[519,708],[451,734],[419,786],[330,819],[247,811],[165,826],[99,804],[54,768],[44,681],[46,615]]),
    P([[779,536],[814,500],[890,477],[945,484],[1004,504],[1040,543],[1044,624],[1024,648],[938,663],[835,651],[792,624]]),
    P([[1185,371],[1245,360],[1322,366],[1392,382],[1411,434],[1398,478],[1370,503],[1309,503],[1238,482],[1200,449]]),
    P([[1535,355],[1581,373],[1590,421],[1602,468],[1672,487],[1672,593],[1535,584],[1527,515]]),
    P([[1276,687],[1344,672],[1412,677],[1465,733],[1480,794],[1447,825],[1375,825],[1328,803],[1263,799],[1230,766],[1240,723]])
  ],
  [P([[0,230],[112,229],[196,225],[306,235],[361,231],[377,138],[475,105],[514,88],[602,113],[658,110],[765,109],[793,65],[874,37],[956,65],[1030,61],[1128,76],[1166,99],[1265,118],[1316,169],[1375,250],[1461,289],[1534,345],[1600,340],[1649,364],[1672,363],[1672,720],[1580,785],[1490,753],[1415,736],[1300,757],[1197,781],[1158,823],[1080,857],[984,880],[872,867],[793,843],[730,805],[648,787],[562,803],[492,790],[439,760],[371,719],[315,695],[251,650],[205,635],[158,649],[112,627],[133,582],[136,546],[94,520],[69,462],[86,427],[52,384],[0,351]])],
  [P([[194,389],[207,328],[245,274],[254,218],[290,160],[371,159],[446,144],[560,147],[669,140],[746,183],[785,231],[825,248],[884,244],[987,247],[1033,264],[1051,255],[1088,172],[1138,139],[1262,123],[1377,129],[1447,181],[1497,256],[1523,367],[1517,478],[1561,582],[1601,620],[1672,625],[1672,745],[1547,756],[1437,748],[1395,707],[1373,689],[1335,718],[1300,757],[1238,768],[1190,788],[1133,796],[1077,834],[1016,839],[955,866],[884,843],[837,854],[764,841],[713,814],[663,758],[628,718],[594,701],[561,677],[518,668],[479,661],[420,651],[390,626],[350,636],[288,653],[230,650],[164,677],[60,685],[0,671],[0,557],[190,554]])]
];

// Individual scenery silhouettes have their own exclusion boundaries. Small
// flat pebbles/grass texture remain buildable; raised rocks, plants, ruins and
// crystals do not. The foundation clearance is applied by geometry below.
const OBSTACLES=[
  [
    ['western flowers',P([[0,204],[60,205],[111,227],[112,263],[72,274],[61,319],[0,328]])],
    ['western tree',P([[0,342],[82,349],[113,381],[120,423],[95,455],[0,455]])],
    ['western rock garden',P([[117,430],[192,436],[226,472],[237,540],[274,575],[279,630],[227,634],[180,567],[156,517]])],
    ['northern plants',P([[348,124],[404,126],[444,159],[449,189],[418,203],[390,252],[369,248]])],
    ['inner road flowers',P([[731,371],[776,375],[814,410],[799,454],[764,487],[725,469],[718,441]])],
    ['inner eastern stones',P([[1038,249],[1074,251],[1088,287],[1075,307],[1046,301]])],
    ['eastern ruins',P([[1450,218],[1562,232],[1632,272],[1672,339],[1672,447],[1625,452],[1569,403],[1517,389],[1480,337],[1422,328]])],
    ['eastern fern bank',P([[1600,508],[1672,504],[1672,701],[1614,752],[1570,734],[1546,694],[1571,637],[1563,578]])],
    ['southwestern garden',P([[234,580],[300,603],[342,650],[415,635],[476,659],[526,669],[577,679],[625,704],[665,700],[704,713],[756,732],[794,775],[835,818],[856,869],[800,920],[560,900],[426,817],[357,773],[309,728],[269,682]])],
    ['southern ruins',P([[988,798],[1038,781],[1128,787],[1207,817],[1272,855],[1263,917],[1174,941],[1004,906],[956,859]])]
  ],
  [
    ['northwest palms',P([[0,263],[55,264],[88,295],[104,350],[87,389],[0,402]])],
    ['northwest palm',P([[143,222],[201,224],[218,258],[204,294],[169,300],[152,271]])],
    ['inner island palm',P([[546,233],[590,235],[613,273],[604,325],[567,341],[541,313]])],
    ['upper island palm',P([[803,45],[857,43],[889,75],[869,112],[832,120],[800,102]])],
    ['upper island crystals',P([[990,46],[1049,58],[1087,87],[1081,120],[1058,141],[1004,118],[985,92]])],
    ['middle island palms',P([[765,139],[830,133],[858,173],[845,214],[805,239],[770,209],[756,178]])],
    ['middle island fern',P([[875,205],[928,210],[958,240],[954,280],[927,297],[883,269]])],
    ['middle island palms south',P([[744,299],[784,286],[832,308],[841,352],[799,366],[760,349]])],
    ['southwest palm',P([[183,523],[242,515],[275,554],[269,602],[238,638],[196,606]])],
    ['southwest flower bed',P([[203,627],[251,626],[287,654],[281,689],[246,708],[202,689],[183,658]])],
    ['southwest western shore',P([[46,657],[84,660],[106,718],[97,771],[73,788],[43,752]])],
    ['southwest middle palm',P([[469,588],[516,573],[552,602],[551,644],[524,679],[488,664]])],
    ['southwest north palm',P([[542,428],[599,430],[621,469],[613,508],[579,528],[542,495]])],
    ['southern inner palm',P([[791,492],[841,490],[868,519],[859,559],[828,580],[796,559]])],
    ['southern inner ruin',P([[894,442],[968,437],[1005,468],[1005,510],[973,527],[930,505],[895,478]])],
    ['southern inner crystals',P([[748,567],[807,567],[830,596],[813,643],[773,652],[752,623]])],
    ['southern inner flowers',P([[952,570],[996,573],[1037,603],[1039,641],[1006,654],[974,637]])],
    ['eastern inner palm',P([[1342,365],[1396,364],[1421,400],[1405,449],[1365,470],[1338,434]])],
    ['eastern inner flowers',P([[1187,352],[1242,351],[1276,373],[1267,406],[1226,419],[1198,399]])],
    ['far eastern crystals',P([[1514,438],[1565,436],[1598,469],[1596,520],[1558,540],[1525,514]])],
    ['far eastern palm',P([[1582,496],[1640,486],[1672,513],[1672,556],[1615,570],[1579,541]])],
    ['southeast upper palm',P([[1357,638],[1422,634],[1450,666],[1440,711],[1406,735],[1366,709]])],
    ['southeast eastern palm',P([[1437,716],[1489,709],[1522,743],[1507,796],[1471,812],[1443,772]])],
    ['southeast western flowers',P([[1229,717],[1282,714],[1313,753],[1291,785],[1255,787],[1224,760]])]
  ],
  [
    ['western cactus',P([[0,348],[74,345],[105,378],[106,430],[72,461],[0,437]])],
    ['western ruin and cactus',P([[297,224],[353,215],[374,255],[376,323],[353,347],[304,328],[295,289]])],
    ['western rock bank',P([[303,421],[350,414],[374,455],[370,494],[337,519],[303,488]])],
    ['western lava cactus',P([[125,544],[167,541],[197,565],[197,612],[166,637],[127,608]])],
    ['upper middle cactus',P([[647,111],[702,93],[747,106],[776,136],[769,171],[731,185],[681,168],[641,152]])],
    ['middle cactus',P([[499,395],[552,390],[592,421],[609,455],[594,478],[544,477],[505,448]])],
    ['middle western cliff stones',P([[506,185],[540,186],[561,219],[551,259],[522,276],[498,245]])],
    ['inner raised corner post',P([[830,485],[870,477],[887,502],[888,562],[864,584],[826,568],[817,537]])],
    ['western raised corner post',P([[395,581],[440,575],[466,604],[464,644],[434,668],[398,650],[385,615]])],
    ['inner northern rock bank',P([[858,297],[1168,300],[1193,362],[1190,449],[1150,457],[1103,408],[1117,371],[1035,355],[982,359],[952,347],[872,350]])],
    ['floor boulder',P([[754,674],[803,672],[822,704],[802,721],[765,717]])],
    ['southern cactus',P([[1020,793],[1086,784],[1130,813],[1143,855],[1111,879],[1055,860],[1019,835]])],
    ['southeastern cactus',P([[1138,714],[1194,709],[1228,743],[1225,784],[1188,809],[1149,778]])],
    ['eastern inner rocks',P([[1318,279],[1360,282],[1389,319],[1385,353],[1344,361],[1315,329]])],
    ['eastern inner thorn',P([[1335,561],[1364,552],[1384,578],[1387,615],[1359,627],[1336,599]])],
    ['eastern crystals',P([[1535,284],[1596,281],[1624,314],[1618,349],[1580,374],[1540,347]])],
    ['southwestern ruins',P([[161,667],[246,659],[292,687],[323,738],[395,743],[463,790],[478,850],[378,898],[287,851],[244,787],[204,772],[163,720]])]
  ],
  [
    ['inner western crystals',P([[377,251],[463,249],[479,271],[456,305],[423,314],[413,362],[387,387],[371,359],[366,302]])],
    ['inner northern crystals',P([[583,245],[650,246],[673,291],[665,338],[644,330],[640,295],[601,287]])],
    ['western lower crystals',P([[351,548],[401,558],[420,600],[411,636],[368,630]])],
    ['middle road boulders',P([[642,491],[693,525],[717,528],[735,542],[789,534],[818,545],[857,532],[904,535],[957,535],[994,532],[1034,542],[1072,528],[1123,540],[1142,557],[1111,574],[1015,568],[943,581],[876,574],[810,572],[754,567],[714,583],[686,563],[658,559],[640,536]])],
    ['upper middle crystal bank',P([[789,334],[823,340],[841,375],[888,390],[922,397],[946,422],[927,437],[843,427],[806,409],[784,381]])],
    ['inner eastern crystals',P([[1193,220],[1274,227],[1284,246],[1240,258],[1224,282],[1194,275]])],
    ['eastern inner crystal',P([[1346,378],[1384,376],[1413,413],[1400,446],[1361,438]])],
    ['inner western lower crystal',P([[629,399],[669,398],[687,433],[684,475],[658,487],[638,457]])],
    ['southern western stones',P([[448,635],[490,637],[517,674],[523,706],[490,727],[451,706]])]
  ]
];

const freeze=value=>{if(value&&typeof value==='object'&&!Object.isFrozen(value)){Object.values(value).forEach(freeze);Object.freeze(value);}return value;};
function cross(a,b,c){return(b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x);}
function hull(points){
  const sorted=points.sort((a,b)=>a.x-b.x||a.y-b.y),lower=[],upper=[];
  for(const point of sorted){while(lower.length>1&&cross(lower.at(-2),lower.at(-1),point)<=0)lower.pop();lower.push(point);}
  for(const point of [...sorted].reverse()){while(upper.length>1&&cross(upper.at(-2),upper.at(-1),point)<=0)upper.pop();upper.push(point);}
  lower.pop();upper.pop();return lower.concat(upper);
}
function roadCapsule(a,b,halfWidth){
  // Circumscribed rather than inscribed circles: no gaps between vertices can
  // accidentally admit a foundation onto the painted curb.
  const points=[],steps=32,radius=halfWidth/Math.cos(Math.PI/steps);
  for(const centre of [a,b])for(let n=0;n<steps;n++){
    const angle=(n+.5)*2*Math.PI/steps;
    points.push({x:centre.x+radius*Math.cos(angle),y:centre.y+radius*Math.sin(angle)});
  }
  return hull(points);
}
export const VERSION_FOUR_TERRAIN_MASKS=freeze(BIOMES.map((biome,index)=>({
  biome,width:PLACEMENT_BOARD_WIDTH,height:PLACEMENT_BOARD_HEIGHT,
  footprint:{rx:TOWER_FOOTPRINT_RX,ry:TOWER_FOOTPRINT_RY,margin:PLACEMENT_MARGIN,minCentreY:MIN_TOWER_CENTRE_Y},
  landPolygons:LAND[index],
  obstacles:OBSTACLES[index].map(([name,polygon])=>({name,polygon})),
  obstaclePolygons:OBSTACLES[index].map(([,polygon])=>polygon),
  roadPath:VERSION_FOUR_PLACEMENT_PATHS[index],roadHalfWidth:ROAD_HALF_WIDTHS[index],
  roadPolygons:VERSION_FOUR_PLACEMENT_PATHS[index].slice(1).map((point,n)=>roadCapsule(VERSION_FOUR_PLACEMENT_PATHS[index][n],point,ROAD_HALF_WIDTHS[index]))
})));

// Version five is one connected dry island. Trace the painted sand/water edge,
// not the old grass clearings: flat beach and every open interior lawn are
// buildable. Only raised coastal scenery needs a separate exclusion polygon.
const LAGOON_FIVE_LAND=[P([
  [0,365],[23,331],[62,310],[40,253],[60,188],[39,151],[54,120],[90,91],[143,57],
  [213,52],[266,21],[329,16],[375,49],[459,63],[511,79],[569,62],[631,41],[700,36],
  [769,56],[819,80],[880,87],[955,62],[1011,38],[1118,39],[1182,61],[1239,86],
  [1309,65],[1384,62],[1468,48],[1530,61],[1569,102],[1574,150],[1595,199],
  [1570,227],[1592,252],[1631,284],[1632,338],[1598,368],[1642,394],[1640,435],
  [1672,477],[1672,712],[1648,745],[1635,783],[1595,835],[1545,860],[1475,866],
  [1414,865],[1361,847],[1311,839],[1248,844],[1207,851],[1141,849],[1056,854],
  [1007,880],[951,878],[899,859],[836,840],[786,847],[730,858],[671,865],
  [616,853],[565,828],[520,824],[466,839],[424,840],[394,830],[332,823],
  [298,827],[254,821],[215,806],[173,795],[153,769],[125,730],[93,713],
  [71,672],[65,638],[40,590],[0,566]
])];
const LAGOON_FIVE_OBSTACLES=[
  ['northwest ruin and palms',P([[35,55],[133,16],[204,28],[260,4],[371,0],[420,47],[411,108],[355,121],[302,100],[253,106],[214,100],[185,126],[135,133],[109,163],[66,179],[40,143]])],
  ['western beach palm',P([[53,180],[104,176],[147,209],[161,253],[148,289],[104,305],[60,281],[27,272],[25,233]])],
  ['western shore flowers',P([[0,303],[43,310],[66,343],[48,373],[15,384],[0,371]])],
  ['western lower palm',P([[0,500],[35,494],[65,532],[60,572],[28,587],[0,574]])],
  ['southwestern beach garden',P([[70,576],[113,587],[141,611],[172,618],[191,642],[162,680],[119,669],[95,643],[61,638],[68,611]])],
  ['southwestern rock and palm grove',P([[111,689],[165,691],[192,706],[217,717],[226,699],[255,690],[291,705],[307,742],[307,771],[335,790],[332,817],[292,818],[276,795],[241,808],[215,796],[211,764],[170,780],[132,771],[113,739]])],
  ['southern small shore stones',P([[341,781],[375,779],[389,794],[375,809],[348,807]])],
  ['southern beach fern',P([[387,756],[422,746],[452,765],[443,785],[409,793],[385,780]])],
  ['southern shore rock',P([[422,806],[445,801],[463,818],[454,837],[430,835]])],
  ['southern beach palm',P([[449,773],[473,768],[492,785],[508,804],[505,826],[473,830],[455,810]])],
  ['southern western coastal rocks',P([[539,825],[557,814],[578,821],[586,805],[605,811],[622,838],[629,863],[647,861],[655,887],[625,894],[601,878],[569,885],[553,862]])],
  ['southern middle coastal rock',P([[773,841],[795,838],[814,853],[826,872],[812,891],[785,885],[772,867]])],
  ['southern eastern coastal rock',P([[973,848],[985,834],[1012,831],[1029,851],[1029,873],[1009,888],[980,886],[967,866]])],
  ['southeastern coastal rock',P([[1173,836],[1199,822],[1223,837],[1237,864],[1224,883],[1194,878],[1172,858]])],
  ['southeastern ruin and grove',P([[1275,799],[1294,777],[1326,777],[1348,749],[1386,740],[1409,764],[1456,760],[1492,778],[1506,755],[1530,744],[1541,720],[1574,708],[1603,723],[1624,747],[1620,789],[1641,809],[1619,850],[1579,867],[1519,851],[1488,872],[1457,861],[1422,865],[1371,854],[1348,827],[1305,850],[1277,833]])],
  ['eastern coastal palms',P([[1544,377],[1577,368],[1604,392],[1601,424],[1638,415],[1669,430],[1672,462],[1653,487],[1672,505],[1672,554],[1638,561],[1615,530],[1587,521],[1574,482],[1538,465],[1525,435]])],
  ['eastern upper beach palm',P([[1555,280],[1596,279],[1620,302],[1626,332],[1613,363],[1587,374],[1559,352],[1545,323]])],
  ['northeastern ruin and palms',P([[1232,39],[1297,31],[1331,53],[1391,50],[1443,42],[1490,40],[1526,53],[1546,82],[1556,114],[1541,146],[1556,171],[1537,202],[1497,197],[1487,174],[1459,164],[1426,142],[1395,127],[1371,115],[1324,129],[1286,115],[1246,109],[1226,82]])],
  ['northern central coastal rocks and palms',P([[937,20],[978,12],[1000,33],[1021,18],[1069,30],[1093,14],[1139,14],[1169,39],[1166,67],[1137,84],[1107,80],[1085,103],[1048,99],[1015,83],[992,91],[965,78],[947,58]])],
  ['northern western coastal rocks',P([[632,3],[691,0],[729,20],[770,20],[799,43],[807,74],[783,98],[747,90],[734,72],[697,79],[670,61],[646,59]])]
];
export const VERSION_FIVE_TERRAIN_MASKS=freeze(VERSION_FOUR_TERRAIN_MASKS.map((mask,index)=>index===1?{
  ...mask,landPolygons:LAGOON_FIVE_LAND,
  obstacles:LAGOON_FIVE_OBSTACLES.map(([name,polygon])=>({name,polygon})),
  obstaclePolygons:LAGOON_FIVE_OBSTACLES.map(([,polygon])=>polygon),
  roadPath:VERSION_FIVE_PLACEMENT_PATHS[index],
  roadPolygons:VERSION_FIVE_PLACEMENT_PATHS[index].slice(1).map((point,n)=>roadCapsule(VERSION_FIVE_PLACEMENT_PATHS[index][n],point,ROAD_HALF_WIDTHS[index]))
}:mask));
const MASKS=freeze([...VERSION_FIVE_TERRAIN_MASKS,...CAMPAIGN_WORLDS.map(world=>({
  biome:world.slug,width:PLACEMENT_BOARD_WIDTH,height:PLACEMENT_BOARD_HEIGHT,
  footprint:{rx:TOWER_FOOTPRINT_RX,ry:TOWER_FOOTPRINT_RY,margin:PLACEMENT_MARGIN,minCentreY:MIN_TOWER_CENTRE_Y},
  landPolygons:world.landPolygons,obstacles:world.obstacles,
  obstaclePolygons:world.obstacles.map(obstacle=>obstacle.polygon),
  roadPath:world.path,roadHalfWidth:world.roadHalfWidth,
  roadPolygons:world.path.slice(1).map((point,n)=>roadCapsule(world.path[n],point,world.roadHalfWidth))
}))]);
function maskFor(level,mapLayoutVersion){
  const masks=mapLayoutVersion===4?VERSION_FOUR_TERRAIN_MASKS:mapLayoutVersion===5?VERSION_FIVE_TERRAIN_MASKS:mapLayoutVersion===6?MASKS:null;
  return masks&&Number.isInteger(level)&&level>=1&&level<=masks.length*5?masks[Math.floor((level-1)/5)]:null;
}
export function getTerrainPlacementMask(level,mapLayoutVersion=MAP_LAYOUT_VERSION){
  const mask=maskFor(level,mapLayoutVersion);if(!mask)throw new RangeError('Unknown campaign level or terrain version.');return mask;
}
function pointInPolygon(x,y,polygon){
  let inside=false;
  for(let n=0,j=polygon.length-1;n<polygon.length;j=n++){
    const a=polygon[n],b=polygon[j];
    if(((a.y>y)!==(b.y>y))&&x<(b.x-a.x)*(y-a.y)/(b.y-a.y)+a.x)inside=!inside;
  }
  return inside;
}
function boundaryDistanceSquared(x,y,polygon){
  // In this space the entire expanded foundation is a unit circle. Testing
  // every edge catches narrow notches AND tiny enclosed obstacles; rim-only
  // samples would miss both. It also checks the foundation interior exactly.
  let distance=Infinity;
  for(let n=0;n<polygon.length;n++){
    const a=polygon[n],b=polygon[(n+1)%polygon.length],ax=(a.x-x)/RX,ay=(a.y-y)/RY,bx=(b.x-x)/RX,by=(b.y-y)/RY;
    const dx=bx-ax,dy=by-ay,length=dx*dx+dy*dy,t=length?Math.max(0,Math.min(1,-(ax*dx+ay*dy)/length)):0;
    const px=ax+t*dx,py=ay+t*dy;distance=Math.min(distance,px*px+py*py);
  }
  return distance;
}
function fitsLand(x,y,polygon){return pointInPolygon(x,y,polygon)&&boundaryDistanceSquared(x,y,polygon)>1+EPSILON;}
const polygonBounds=new WeakMap();
function intersects(x,y,polygon){
  let bounds=polygonBounds.get(polygon);
  if(!bounds){bounds={left:Math.min(...polygon.map(p=>p.x)),right:Math.max(...polygon.map(p=>p.x)),top:Math.min(...polygon.map(p=>p.y)),bottom:Math.max(...polygon.map(p=>p.y))};polygonBounds.set(polygon,bounds);}
  if(x+RX<bounds.left||x-RX>bounds.right||y+RY<bounds.top||y-RY>bounds.bottom)return false;
  return pointInPolygon(x,y,polygon)||boundaryDistanceSquared(x,y,polygon)<=1+EPSILON;
}
const rejected=reason=>({valid:false,reason});

export function getPlacementValidity(level,x,y,activePositions=[],mapLayoutVersion=MAP_LAYOUT_VERSION){
  const mask=maskFor(level,mapLayoutVersion);
  if(!mask||!Number.isFinite(x)||!Number.isFinite(y)||!Number.isInteger(x)||!Number.isInteger(y))return rejected('invalid-coordinate');
  if(x-RX<0||x+RX>mask.width||y-RY<0||y+RY>mask.height||y<MIN_TOWER_CENTRE_Y)return rejected('outside-map');
  if(mask.roadPolygons.some(polygon=>intersects(x,y,polygon)))return rejected('path');
  if(!mask.landPolygons.some(polygon=>fitsLand(x,y,polygon))||mask.obstaclePolygons.some(polygon=>intersects(x,y,polygon)))return rejected('terrain');
  if(!Array.isArray(activePositions))return rejected('occupied');
  for(const position of activePositions){
    if(!position||!Number.isFinite(position.x)||!Number.isFinite(position.y))return rejected('occupied');
    // Equal, aligned ellipses have an exact elliptical Minkowski sum. Keep a
    // three-pixel visible gap between physical foundations, not two margins.
    const dx=(x-position.x)/(2*TOWER_FOOTPRINT_RX+PLACEMENT_MARGIN),dy=(y-position.y)/(2*TOWER_FOOTPRINT_RY+PLACEMENT_MARGIN);
    if(dx*dx+dy*dy<=1+EPSILON)return rejected('occupied');
  }
  return{valid:true,reason:null};
}
