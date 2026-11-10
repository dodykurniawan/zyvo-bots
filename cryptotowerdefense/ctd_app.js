import { TOWER_DEFS, ENEMY_DEFS, TICK_MS, createGame, replayDefenseChunk, stepGame, applyAction, pointOnPath, currentWaveCountdown, getUpgradeCost, getUpgradeChoices, getSellRefund, UPGRADE_PATH_ENGINE_VERSION, getTowerStats, getMap } from './game-engine.js';
import { RARITIES, TOWER_CATALOG, CAMPAIGN_LEVELS, CAMPAIGN_LEVELS_V2, getLevel, getMapLevel, getCampaignLevel, getCampaignLevels } from './game-data.js';
import { createChestsUI } from './chests-ui.js';
import { getModeChallenge, calculateWaveShares } from './mode-rules.js';
import { createModesUI, isEndlessMode, periodEndNumber } from './modes-ui.js';
import { BattleSession } from './battle-session.js';
import { BattleFX } from './battle-fx.js';
import { ModelMotion } from './model-motion.js';
import { drawMapArtwork, loadMapArtwork, getMapExitAnchor } from './map-art.js';
import { MAP_LAYOUT_VERSION } from './map-layout.js';
import { getPlacementValidity } from './terrain-placement.js';
import { createArsenalUI } from './arsenal-ui.js';
import { mountBattleLayout } from './battle-layout.js';
import { mountPageNavigation } from './page-navigation.js';
import { createAccountUI } from './accounts-ui.js';
import { createPremiumUI } from './premium-ui.js';
import { createSquadsUI } from './squads-ui.js';
import { drawBossGround,drawBossOverlay } from './boss-fx.js';
import { BOSS_DEFS, getBossDefinitionForWave, getCampaignBoss } from './boss-rules.js';
import { createSecurityUI, securityCode } from './security-ui.js';
import { confirmSignedOut, createProtectedRequest, isSignInRequired, sessionIdentityPath } from './security-request.js';
import { createWithdrawalsUI } from './withdrawals-ui.js';
import { createEarningUI } from './earning-ui.js';
import { loadReferralCard } from './referrals-ui.js';
import { createShortlinksUI } from './shortlinks-ui.js';
import { createShopUI } from './shop-ui.js';
import { createUpgradePathsUI } from './upgrade-paths-ui.js';
import { getInitialCampaignSelection } from './campaign-selection.js';
import { createBattleUnitLayer,traceRoundedRect } from './battle-unit-layer.js';
import { bindBoardPointer,drawPlacementSlots,getCanvasBoardPoint } from './placement-slots.js';

mountBattleLayout();

const $ = (selector) => document.querySelector(selector);
const canvas = $('#gameCanvas');
const ctx = canvas?.getContext('2d');
const faucetClaims = [
  {button:$('#claimQuickFaucet'),amount:$('#quickFaucetAmount'),timer:$('#quickFaucetTimer'),path:'/api/faucet/quick',coinsKey:'quickFaucetCoins',nextKey:'quickNextClaimAt'},
  {button:$('#claimFaucet'),amount:$('#faucetAmount'),timer:$('#faucetTimer'),path:'/api/faucet/claim',coinsKey:'faucetCoins',nextKey:'nextClaimAt'}
].filter(claim=>claim.button);
const ui = {
  alias: $('#playerAlias'), coins: $('#coinBalance'), wave: $('#waveValue'), lives: $('#livesValue'),
  energy: $('#energyValue'), nextWave: $('#nextWaveValue'), startOverlay: $('#startOverlay'),
  resultOverlay: $('#resultOverlay'), startButton: $('#startRun'), startHint: $('#startHint'),
  resultKicker: $('#resultKicker'), resultTitle: $('#resultTitle'), resultScore: $('#resultScore'),
  resultCoins: $('#resultCoins'), resultMessage: $('#resultMessage'), playAgain: $('#playAgain'),
  upgrade: $('#upgradeTower'), sell: $('#sellTower'), callWave: $('#callWave'), speed: $('#speedToggle'), toast: $('#toast')
};
let towerPortraits = {}, enemyPortraits = {}, upcomingPreviewKey = '';
const unitRenderer=ctx&&createBattleUnitLayer({ctx,quality:matchMedia('(max-width: 760px), (pointer: coarse)').matches?'low':'high'});
const battleFX = new BattleFX({reducedMotion:matchMedia('(prefers-reduced-motion: reduce)').matches,
  muzzleResolver:(tower)=>unitRenderer?.muzzle(tower)});
const modelMotion = new ModelMotion({reducedMotion:matchMedia('(prefers-reduced-motion: reduce)').matches});
matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change',(event)=>{
  modelMotion.reducedMotion=event.matches; battleFX.reducedMotion=event.matches;
});
let bootstrapData = null, game = null, runId = null, actions = [], selectedType = 'pulse', selectedPad = null, hoveredPad = null;
let selectedLevel = 1, speed = 1, paused = false, submitting = false, settled = false, view = 'campaign';
let selectedMode='campaign',campaignChapter=0,starting=false,syncIssue=null,nextSyncRetry=0,periodRefreshing=false,settlementAttempted=false;
let campaignDefaultPending=true, campaignChapterChosen=false;
let placementPoint=null, buildMode=false, touchPlacement=false;
let lastFrame = performance.now(), accumulator = 0, toastTimer, soundEnabled = false, audioContext, chestOpening=false, claimingFaucet=false;
let pageNavigation,accountUI,squadsUI,withdrawalsUI,activeEconomyRequests=0,bootstrapSequence=0;
let securityBlocked=false,restrictionMessage='';
let verificationHold=false,securityWasPaused=true,securityRetryRequired=false;
let battleProfileId=null,sessionInterrupted=false,sessionWasPaused=false,checkingBattleSession=false,battleSessionGeneration=0;
const bootstrapRequests=new Set();
const pendingOperations = new Map();
const battleSession=new BattleSession((path,payload)=>api(path,{method:'POST',body:JSON.stringify(payload)}));
const securityUI=createSecurityUI({request:rawApi,onStatus:message=>{if(message&&game&&!game.ended)setPaused(true);}});
const upgradePathsUI=canvas&&createUpgradePathsUI({element:$('#battleUpgradePaths'),getChoices:getUpgradeChoices,onChoose:upgradeBattlePath});
const protectedRequest=createProtectedRequest({request:rawApi,security:securityUI});
const earningUI=$('#earningDialog')&&createEarningUI({request:rawApi,requestPaidVisits:protectedRequest,getData:()=>bootstrapData,isRestricted:()=>securityBlocked,showError:showToast});
if($('#referralCard'))void loadReferralCard(rawApi);
const shortlinksUI=$('#shortlinkGrid')&&createShortlinksUI({request:rawApi,startRequest:protectedRequest,isRestricted:()=>securityBlocked,
  onCoins:coins=>{if(bootstrapData&&Number.isSafeInteger(coins)){bootstrapData.player.coins=coins;ui.coins.textContent=formatNumber(coins);}}});
const shopUI=$('#shopOrderDialog')&&createShopUI({isAvailable:()=>Boolean(bootstrapData?.shop?.enabled&&!securityBlocked)});
const arsenalUI=createArsenalUI({
  getData:()=>bootstrapData,getPortraits:()=>towerPortraits,
  onChange:()=>{renderCampaign();squadsUI?.render();},onToast:showToast,onCampaign:()=>switchView(game?.mode || selectedMode),
  onUpgrade:async(type)=>{
    try{
      const result=await mutate('/api/towers/upgrade',{towerType:type});
      const copies=bootstrapData?.collection.filter(tower=>tower.type===type);
      if(copies?.length&&copies.every(tower=>tower.level===result.level-1)&&
        Number.isSafeInteger(result.coins)&&bootstrapData.player.coins-result.coinsSpent===result.coins&&
        (result.upgradeCost===null||Number.isSafeInteger(result.upgradeCost))){
        for(const tower of copies){tower.level=result.level;tower.upgradeCost=result.upgradeCost;}
        bootstrapData.player.coins=result.coins;
        ui.coins.textContent=formatNumber(result.coins);
      }else await loadBootstrap();
      showToast(TOWER_CATALOG[type].name+' permanently upgraded to level '+result.level+'.');
    }
    catch(error){showToast(error.message);await loadBootstrap();}
  },
  onFuse:async(ids)=>{
    try{const result=await mutate('/api/towers/fuse',{towerIds:ids.sort()});await loadBootstrap();revealTower(result.tower,true);}
    catch(error){showToast(error.message);await loadBootstrap();}
  }
});
const chestsUI=shopUI&&createChestsUI({getData:()=>bootstrapData,getPortraits:()=>towerPortraits,isOpening:()=>chestOpening,onOpen:openChest,onShop:shopUI.open});
const modesUI=canvas&&createModesUI({getData:()=>bootstrapData,getMode:()=>selectedMode});
const canChangeIdentity=()=>!starting&&(securityBlocked||!game||game.ended&&settled)&&!submitting&&!activeEconomyRequests&&!chestOpening&&!claimingFaucet&&!accountUI?.isBusy()&&!securityUI.isBusy()&&!withdrawalsUI?.isBusy();
accountUI=$('#accountView')&&createAccountUI({getData:()=>bootstrapData,request:async(path,options)=>{
  // Let earlier profile responses finish before changing account metadata.
  while(bootstrapRequests.size)await Promise.allSettled([...bootstrapRequests]);
  return api(path,options);
},canChangeIdentity,onToast:showToast,onCxlStatus:result=>premiumUI.accept(result),verifyAccount:()=>securityUI.ensureHuman('account'),refresh:async()=>{
  bootstrapData=null;ui.alias.textContent='CONNECTING…';ui.coins.textContent='—';renderCollection();accountUI.render();premiumUI.render();
  if(!await loadBootstrap({allowDuringAccount:true}))throw new Error('Your account was updated. Reconnect to load your saved profile.');
}});
squadsUI=$('#saveSquadForm')&&createSquadsUI({getData:()=>bootstrapData,getLoadout:()=>arsenalUI.getLoadout(),setLoadout:types=>arsenalUI.setLoadout(types),mutate,refresh:loadBootstrap,onToast:showToast});
withdrawalsUI=$('#walletView')&&createWithdrawalsUI({
  getAccountId:()=>bootstrapData ? (bootstrapData.account?.authenticated ? bootstrapData.player?.id || null : null) : undefined,
  isRestricted:()=>securityBlocked,
  isAccountBusy:()=>Boolean(accountUI?.isBusy() || securityUI.isBusy()),
  request:rawApi,
  verify:()=>securityUI.ensureHuman('account')
});
const premiumUI=(canvas || accountUI || $('#premiumView') || faucetClaims.length) ? createPremiumUI({
  getData:()=>bootstrapData,
  request:rawApi,
  canRefresh:()=>!bootstrapRequests.size && !accountUI?.isBusy() && !starting && !submitting && !claimingFaucet,
  onChange:()=>{
    if(game&&!game.ended)modesUI?.render();
    else renderCampaign();
    if(game?.ended&&settled&&isEndless())ui.playAgain.disabled=securityBlocked||selectedChallenge()?.attempts?.remaining===0;
    updateFaucet();
    accountUI?.render();
  }
}) : null;

function selectedChallenge(){return bootstrapData?.modes?.[selectedMode] || (isEndlessMode(selectedMode)?getModeChallenge(selectedMode,Date.now()):null);}
function campaignLevelCount(){return bootstrapData?.campaign?.levels?.length || CAMPAIGN_LEVELS_V2.length;}
function selectDefaultCampaignLevel() {
  if (!canvas || selectedMode !== 'campaign' || !campaignDefaultPending || game || starting || submitting) return;
  const selection = getInitialCampaignSelection(bootstrapData?.campaign);
  if (!selection) return;
  selectedLevel = selection.level;
  if (!campaignChapterChosen) campaignChapter = selection.chapter;
  campaignDefaultPending = false;
}
function campaignLevel(id=selectedLevel){return (game?.level===id?game.levelDefinition:null)||bootstrapData?.campaign?.levels.find(level=>level.id===id)||getCampaignLevel(id,game?.mapLayoutVersion || bootstrapData?.campaign?.mapLayoutVersion || MAP_LAYOUT_VERSION)||getLevel(id)||getLevel(1);}
function mapLevel(){return game?.mapLevel || (game?game.level:isEndlessMode(selectedMode)?selectedChallenge()?.mapLevel || 1:campaignLevel().map*5+1);}
function isEndless(){return isEndlessMode(game?.mode || selectedMode);}
function battleMoved(){return syncIssue?.code==='RUN_RESUMED_ELSEWHERE';}
function syncBlocked(){return Boolean(battleSession.modern&&game&&!game.ended&&(battleMoved()||game.tick-battleSession.verifiedTick>=900));}
function chooseMode(mode){
  if(!['campaign','daily','weekly'].includes(mode))return;
  if(starting || game&&!game.ended){showToast('Finish this defense before choosing another mode.');return;}
  if(game?.ended&&!settled){showToast('Save this defense before changing modes.');return;}
  selectedMode=mode;game=null;selectedPad=null;placementPoint=null;hoveredPad=null;paused=false;
  document.body.classList.remove('is-playing');ui.resultOverlay.classList.add('hidden');$('#pauseOverlay').classList.add('hidden');ui.startOverlay.classList.remove('hidden');
  $('#liveEndlessLine').classList.add('hidden');$('#battleSyncLine').classList.add('hidden');$('#endAttempt').classList.add('hidden');
  renderCampaign();
}

function formatNumber(value) { return Number(value || 0).toLocaleString('en-US'); }
function escapeText(value) { return String(value ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function rarityInfo(id) { return RARITIES.find((r) => r.id === id) || RARITIES[0]; }
function glyph(type) { return '<span class="tower-portrait '+(towerPortraits[type]?'has-image':'')+' art-'+type+'" style="--tower-color:'+TOWER_CATALOG[type].color+';background-image:url('+ (towerPortraits[type] || '') +');background-size:contain;background-position:center;background-repeat:no-repeat" aria-hidden="true"></span>'; }
function showToast(message) { ui.toast.textContent = message; ui.toast.classList.remove('hidden'); clearTimeout(toastTimer); toastTimer = setTimeout(() => ui.toast.classList.add('hidden'), 4000); }
function tone(frequency, duration=.06, volume=.035) {
  if (!soundEnabled) return;
  try { audioContext ||= new AudioContext(); const oscillator = audioContext.createOscillator(), gain = audioContext.createGain();
    oscillator.type='triangle'; oscillator.frequency.value=frequency; gain.gain.setValueAtTime(volume,audioContext.currentTime);
    gain.gain.exponentialRampToValueAtTime(.0001,audioContext.currentTime+duration); oscillator.connect(gain).connect(audioContext.destination);
    oscillator.start(); oscillator.stop(audioContext.currentTime+duration);
  } catch { /* Audio is optional. */ }
}
async function rawApi(path, options={}, retrySession=true) {
  const generation=battleSessionGeneration;
  const replayRequest=path==='/api/run/checkpoint'||path==='/api/run/finish';
  const inBattleSecurity=game&&!settled&&path.startsWith('/api/security/');
  // Bound each network request separately so players can take their time
  // completing an interactive security check between requests.
  const {timeoutMs=replayRequest||inBattleSecurity||path==='/api/run/resume'?20_000:0,...requestOptions}=options;
  const controller=timeoutMs&&!requestOptions.signal?new AbortController():null;
  const timeout=controller&&setTimeout(()=>controller.abort(),timeoutMs);
  const signal=requestOptions.signal??controller?.signal;
  const headers = new Headers(options.headers || {});
  headers.set('x-ctd-client-version','0.19.0');
  if (options.body) headers.set('content-type','application/json');
  if (bootstrapData?.csrfToken && options.method === 'POST') headers.set('x-csrf-token', bootstrapData.csrfToken);
  let response,data;
  try {
    response=await fetch(path,{credentials:'same-origin',cache:'no-store',...requestOptions,headers,signal});
    data=await response.json().catch(()=>{
      if(signal?.aborted)throw signal.reason;
      return {};
    });
  }catch(error){
    if(controller?.signal.aborted||signal?.reason?.name==='TimeoutError')throw new Error('The server took too long to respond.');
    throw error;
  }finally{if(timeout)clearTimeout(timeout);}
  if (!response.ok) { const error = new Error(data.error || 'Request failed ('+response.status+').'); error.status=response.status;error.code=data.code;error.details=data;
    if(response.status===429){
      const retryAfter=Number(response.headers.get('retry-after'));
      if(Number.isFinite(retryAfter)&&retryAfter>0)error.retryAfterSeconds=retryAfter;
    }
    if(path!==sessionIdentityPath&&generation===battleSessionGeneration){
      const loginRequired=isSignInRequired(response.status,data.code);
      const sessionChanged=response.status===403&&data.code==='CSRF_MISMATCH';
      if(game&&!settled&&(loginRequired||sessionChanged)){
        const activeGame=game;
        if(retrySession&&(options.method!=='POST'||replayRequest)){
          const identity=await rawApi(sessionIdentityPath,{timeoutMs:5000}).catch(()=>null);
          if(game===activeGame&&!settled&&generation===battleSessionGeneration&&matchesBattleIdentity(identity)){
            if(bootstrapData.csrfToken!==identity.csrfToken){
              bootstrapSequence++;
              bootstrapData.csrfToken=identity.csrfToken;
            }
            return rawApi(path,options,false);
          }
        }
        if(game===activeGame&&!settled&&generation===battleSessionGeneration)holdBattleForSignIn();
      }
      else if(loginRequired&&await confirmSignedOut(rawApi)&&generation===battleSessionGeneration){
        if(game&&!settled)holdBattleForSignIn();
        else location.replace('/account');
      }
    }
    if(data.code==='HUMAN_VERIFICATION_REQUIRED'&&replayRequest&&game&&!game.ended){if(!verificationHold)securityWasPaused=paused;verificationHold=true;setPaused(true);updateHud();updateBattleSync();}
    if(data.code==='ACCOUNT_RESTRICTED'){securityBlocked=true;restrictionMessage=error.message;if(game&&!game.ended)setPaused(true);applyAccountRestriction();}
    throw error; }
  return data;
}
async function api(path,options={}){
  try{
    const result=await protectedRequest(path,options);
    if(path!=='/api/bootstrap'&&result.security&&result.security.status!=='active'){securityBlocked=true;restrictionMessage=result.security.message;}
    if(verificationHold&&['/api/run/checkpoint','/api/run/finish'].includes(path)){
      verificationHold=false;securityRetryRequired=false;if(game&&!game.ended&&!securityWasPaused&&!securityBlocked&&view==='campaign')setPaused(false);if(game)updateHud();
    }
    return result;
  }catch(error){if(verificationHold&&['/api/run/checkpoint','/api/run/finish'].includes(path))securityRetryRequired=true;throw error;}
}
function applyAccountRestriction(){
  const notice=$('#accountRestriction');if(notice){notice.classList.toggle('hidden',!securityBlocked);$('#accountRestrictionMessage').textContent=restrictionMessage;}
  if(!securityBlocked)return;
  withdrawalsUI?.render();
  if(canvas)renderBattleUpgradeControls(game?.towers.find(tower=>tower.pad===selectedPad));
  for(const button of document.querySelectorAll('#startRun,#playAgain,#nextLevel,[data-faucet-claim],#coinChestGrid button,[data-upgrade],[data-fuse-type],#saveSquadForm button,#savedSquadsList button,#pauseRun,#upgradeTower,#sellTower,#callWave,#endAttempt'))button.disabled=true;
}
async function mutate(path, body={},authority={}) {
  if(securityBlocked)throw new Error(restrictionMessage||'Gameplay and rewards are paused while this account is reviewed.');
  if(accountUI?.isBusy())throw new Error('Your account is updating. Please wait.');
  const key = path+JSON.stringify(body), storageKey = 'ctd-operation:'+key;
  const legacyChestKey=path==='/api/chests/open'&&body.chestId==='supply'?'ctd-operation:/api/chests/open{}':null;
  let id = pendingOperations.get(key) || sessionStorage.getItem(storageKey) || (legacyChestKey&&sessionStorage.getItem(legacyChestKey));
  if (!id) { id=crypto.randomUUID(); pendingOperations.set(key,id); sessionStorage.setItem(storageKey,id); }
  activeEconomyRequests++;
  try {
    const request = path.startsWith('/api/faucet/')?rawApi:api;
    const data = await request(path,{method:'POST',body:JSON.stringify({...body,...authority,operationId:id})});
    pendingOperations.delete(key); sessionStorage.removeItem(storageKey);if(legacyChestKey)sessionStorage.removeItem(legacyChestKey);
    return data;
  } catch (error) {
    if (error.status && error.status < 500) { pendingOperations.delete(key); sessionStorage.removeItem(storageKey);if(legacyChestKey)sessionStorage.removeItem(legacyChestKey); }
    throw error;
  }finally{activeEconomyRequests--;}
}
function bestRoster() {
  const roster = new Map();
  for (const tower of bootstrapData?.collection || []) {
    const old=roster.get(tower.type);
    if (!old || rarityInfo(tower.rarity).multiplier > rarityInfo(old.rarity).multiplier) roster.set(tower.type,tower);
  }
  return [...roster.values()];
}
function renderCampaign() {
  if(!canvas)return;
  const levels=bootstrapData?.campaign?.levels || getCampaignLevels().map(level=>({...level,unlocked:level.id===1}));
  const maxLevel=levels.length,unlocked=bootstrapData?.campaign?.unlockedLevel || 1;
  $('#campaignProgress').textContent=String(unlocked).padStart(2,'0')+' / '+maxLevel;
  const chapters=Math.ceil(maxLevel/20);campaignChapter=Math.max(0,Math.min(chapters-1,campaignChapter));
  $('#campaignChapter').innerHTML=Array.from({length:chapters},(_,i)=>'<option value="'+i+'" '+(i===campaignChapter?'selected':'')+'>LEVELS '+(i*20+1)+'–'+Math.min(maxLevel,(i+1)*20)+'</option>').join('');
  const chapter=levels.slice(campaignChapter*20,campaignChapter*20+20);
  $('#levelGrid').innerHTML=Array.from({length:Math.ceil(chapter.length/5)},(_,sector)=>{
    const group=chapter.slice(sector*5,sector*5+5);
    return '<div class="sector-group '+(group.some(l=>l.id===selectedLevel)?'current':'')+'"><div class="sector-group-title"><i>'+String(campaignChapter*4+sector+1).padStart(2,'0')+'</i> '+escapeText(group[0].sector)+'</div><div class="sector-levels">'+group.map(level=>'<button class="level-button '+(level.id===selectedLevel?'current ':'')+(level.cleared?'cleared':'')+'" data-level="'+level.id+'" aria-label="Level '+level.id+': '+escapeText(level.name)+(level.cleared?', cleared':'')+'" '+(!level.unlocked?'disabled':'')+'>'+String(level.id).padStart(2,'0')+'</button>').join('')+'</div></div>';
  }).join('');
  const endless=isEndlessMode(selectedMode),challenge=selectedChallenge(),level=campaignLevel();
  const saved=endless?challenge?.resumableRun:null;
  const baseMap=getMap(mapLevel(),game?.mapLayoutVersion || MAP_LAYOUT_VERSION);
  $('#levelName').textContent=endless?challenge?.theme?.name || 'Endless defense':level.name.split(' · ')[1] || level.name;
  $('#sectorLabel').textContent=(endless?baseMap.name:level.sector).toUpperCase();
  $('#levelDifficulty').textContent=endless?selectedMode.toUpperCase()+' · ENDLESS':'LEVEL '+String(selectedLevel).padStart(2,'0');
  $('#startKicker').textContent=endless?selectedMode.toUpperCase()+' DEFENSE // ENDLESS':'LEVEL '+String(selectedLevel).padStart(2,'0')+' // READY';
  $('#startTitle').textContent=saved?'Your battle is saved.':endless?'How far can you hold?':selectedLevel===1?'The first line.':'Build. Improve. Advance.';
  const mapBoss=level.boss || getCampaignBoss(level.map)?.name;
  if(!unitRenderer)ui.startHint.textContent='Canvas graphics could not start. Reload this page to try again.';
  else ui.startHint.innerHTML=saved?'Return to your last verified checkpoint without using another attempt.':endless?'Every cleared wave builds your pool share.<br>Deploying uses one attempt.':
    (mapBoss?'<strong>Final wave: '+escapeText(mapBoss)+'</strong><br>':'')+'First clears earn Coins. Campaign milestones strengthen your endless defenses.';
  $('#previewWaves').textContent=saved?formatNumber(saved.wavesCleared):endless?'∞':String(level.waves).padStart(2,'0');
  $('#previewWavesLabel').textContent=saved?'VERIFIED WAVES':'WAVES';
  $('#previewOrbs').textContent=saved?formatNumber(Math.floor(saved.verifiedTick*TICK_MS/1000))+'s':formatNumber(endless?challenge?.startOrbs || (selectedMode==='weekly'?300:260):level.startOrbs);
  $('#previewOrbsLabel').textContent=saved?'TIME SAVED':'STARTING ORBS';
  const isCleared=levels.find(entry=>entry.id===selectedLevel)?.cleared;
  $('#previewReward').textContent=endless?String(challenge?.attempts?.remaining ?? '—'):isCleared?'CLAIMED':formatNumber(level.firstClearCoins);
  $('#previewRewardLabel').textContent=endless?'ATTEMPTS LEFT':'FIRST CLEAR COINS';
  const exhausted=endless&&challenge?.attempts?.remaining===0;
  const canStart=Boolean(arsenalUI.getLoadout().length)&&!exhausted;
  ui.startButton.disabled=securityBlocked||starting||!bootstrapData||!unitRenderer||(!saved&&!canStart);
  ui.startButton.innerHTML=saved?'RESUME BATTLE <span>▶</span>':exhausted?'NO ATTEMPTS LEFT':endless?'USE 1 ATTEMPT <span>▶</span>':'DEPLOY SQUAD <span>▶</span>';
  const replaceAttempt=$('#replaceAttempt');
  replaceAttempt.classList.toggle('hidden',!saved||!canStart);
  replaceAttempt.disabled=ui.startButton.disabled;
  const milestones=bootstrapData?.campaign?.milestones || [],next=milestones.find(item=>item.level>(unlocked-1)&&(item.towerType||item.tower||item.type));
  const tower=next&&TOWER_CATALOG[next.towerType||next.tower||next.type];
  $('#nextUnlockName').textContent=tower?tower.name:'Campaign mastery';
  $('#nextUnlockText').textContent=tower?'Clear level '+next.level+' for a Common '+tower.name+'. Every five cleared levels also boosts daily and weekly power.':'Each new sector gets harder. Use faucet Coins and earning partners to permanently improve a varied collection.';
  modesUI.render();renderDeck();
  if(!game){ui.wave.textContent=endless?'0 · ENDLESS':'0 / '+level.waves;ui.energy.textContent=endless?challenge?.startOrbs || (selectedMode==='weekly'?300:260):level.startOrbs;ui.lives.textContent='20';}
}
function renderDeck() {
  if(!canvas)return;
  const roster=game && !game.ended ? game.roster : arsenalUI.getLoadout().map(type=>bestRoster().find(tower=>tower.type===type)).filter(Boolean);
  if (!roster.some((t)=>t.type===selectedType)) selectedType=roster[0]?.type || 'pulse';
  $('#towerDeck').innerHTML=Array.from({length:6},(_,index)=>{
    const owned=roster[index];if(!owned)return '<button class="tower-card empty-deck" data-manage-loadout aria-label="Choose another tower for the loadout">＋ EMPTY SLOT</button>';
    const type=owned.type,def=TOWER_CATALOG[type],label=rarityInfo(owned.rarity).name.toUpperCase()+' · LV '+owned.level;
    const selected=buildMode && selectedType===type;
    return '<button class="tower-card '+(selected?'selected':'')+'" data-tower="'+type+'" aria-pressed="'+selected+'"><span class="dock-index" aria-hidden="true">'+String(index+1).padStart(2,'0')+'</span>'+glyph(type)+'<span class="tower-meta"><strong>'+def.name+'</strong><small>'+label+'</small></span><b><span class="resource-art resource-orb" aria-hidden="true"></span>'+def.cost+'<span class="visually-hidden"> Orbs</span></b></button>';
  }).join('');
  $('#selectedTowerInfo').textContent=roster.length?(buildMode?TOWER_DEFS[selectedType].name.toUpperCase()+' · '+TOWER_DEFS[selectedType].cost+' ORBS → PLACE ON OPEN GROUND':'CHOOSE A TOWER BELOW TO BUILD · CLICK A PLACED TOWER TO INSPECT'):'ADD TOWERS TO YOUR LOADOUT IN THE ARSENAL';
  $('#deployLoadoutCount').textContent=roster.length+' TOWERS EQUIPPED';
  renderBattleInspector();
}
function setBattleText(id, text) {
  const element=$('#'+id);if(element && element.textContent!==String(text))element.textContent=String(text);
}
function renderBattleInspector() {
  const portrait=$('#battleTowerPortrait');if(!portrait)return;
  const placed=game?.towers.find(tower=>tower.pad===selectedPad);
  const owned=(!game?.ended && game?.roster.find(tower=>tower.type===selectedType)) || bestRoster().find(tower=>tower.type===selectedType);
  const tower=placed || {type:selectedType,pad:0,level:1,permanentLevel:owned?.level || 1,rarity:owned?.rarity || 'common'};
  const definition=TOWER_DEFS[tower.type],rarity=rarityInfo(tower.rarity);
  const stats=getTowerStats(placed?game:{rulesVersion:2,mode:selectedMode,endless:isEndlessMode(selectedMode),campaignBonusBps:Number(bootstrapData?.campaign?.bonus?.damageBps||0),theme:selectedChallenge()?.theme,towers:[],padPositions:[{x:0,y:0}]},tower);
  const image=towerPortraits[tower.type] || '';
  if(portrait.dataset.portrait!==tower.type+image){
    portrait.dataset.portrait=tower.type+image;
    portrait.innerHTML=image?'<img src="'+image+'" alt="" width="320" height="320">':'<span class="battle-model-loading">PREPARING MODEL…</span>';
  }
  portrait.style.setProperty('--tower-color',definition.color);
  setBattleText('battlePortraitName',definition.name.toUpperCase());
  const legacyBoost=placed&&game.engineVersion<UPGRADE_PATH_ENGINE_VERSION?' · BOOST '+tower.level+'/3':'';
  setBattleText('battleRarityValue',rarity.name.toUpperCase()+' · LV '+tower.permanentLevel+legacyBoost);
  $('#battleRarityValue')?.style.setProperty('--rarity-color',rarity.color);
  setBattleText('battleDamageValue',stats.damage?formatNumber(Math.round(stats.damage)):'SUPPORT');
  setBattleText('battleRangeValue',stats.range?formatNumber(Math.round(stats.range)):'—');
  const rateLabel=$('#battleRateValue')?.previousElementSibling;
  if(rateLabel)rateLabel.textContent=definition.damage?'FIRE RATE':'OPERATION';
  const aura=tower.type==='validator'||definition.effect?.kind==='haste';
  setBattleText('battleRateValue',definition.damage?(1000/(stats.cooldown*TICK_MS)).toFixed(1)+'/s':aura?'CONTINUOUS':(stats.cooldown*TICK_MS/1000).toFixed(1)+'s CYCLE');
  if(!placed){
    setBattleText('selectedTowerName',definition.specialty.toUpperCase());
    setBattleText('selectedTowerDetail',definition.description+' Place on open ground for '+definition.cost+' Orbs.');
  }
  renderBattleUpgradeControls(placed);
  renderUpcomingWave();
}

function renderBattleUpgradeControls(tower) {
  const pathBattle=game?.engineVersion>=UPGRADE_PATH_ENGINE_VERSION;
  const restricted=sessionInterrupted||verificationHold||securityBlocked||battleMoved()||securityUI.isBusy();
  const canEdit=tower&&!game.ended&&!restricted;
  const note=sessionInterrupted?'Restore your sign-in to buy upgrades.':verificationHold?'Complete verification to buy upgrades.':securityBlocked?'Account access is paused.':game?.ended?'This defense has ended.':paused?'Resume the defense to buy upgrades.':'';
  upgradePathsUI.render(game,tower,{disabled:!canEdit||paused,note});
  ui.upgrade.hidden=!tower||pathBattle;
  ui.sell.hidden=!tower;
  ui.sell.disabled=!canEdit;
  if(!tower){ui.upgrade.disabled=true;return;}
  setBattleText('sellTower','SELL +'+formatNumber(getSellRefund(game,tower))+' ◉');

  if(pathBattle){
    setBattleText('selectedTowerName','TEMPORARY UPGRADES');
    setBattleText('selectedTowerDetail','Choose up to two paths. One can reach Tier 5 and the other Tier 2.');
    return;
  }

  const cost=getUpgradeCost(tower);
  ui.upgrade.disabled=!canEdit||cost===null||game.energy<cost;
  setBattleText('upgradeTower',cost===null?'MAX BOOST':'OVERCHARGE '+cost+' ◉');
  setBattleText('selectedTowerName',TOWER_DEFS[tower.type].name.toUpperCase()+' · BOOST '+tower.level+'/3');
  const effect=TOWER_DEFS[tower.type].effect;
  const nextStats=getTowerStats(game,{...tower,level:Math.min(3,tower.level+1)});
  let nextBoost='Next: '+Math.round(nextStats.damage)+' damage · '+nextStats.range+' range.';
  if(tower.type==='validator')nextBoost='Next: +'+Math.round((.18+tower.level*.12)*(1+(tower.permanentLevel-1)*.025)*rarityInfo(tower.rarity).multiplier*100)+'% nearby damage.';
  if(effect?.kind==='income')nextBoost='Next: '+Math.floor(effect.amount*Math.min(2,nextStats.supportPower))+' Orbs per cycle. The level cap stays '+effect.teamCap+'.';
  if(effect?.kind==='haste')nextBoost='Next: '+Math.round(Math.min(effect.cap,effect.bonus*nextStats.supportPower)*100)+'% shorter nearby attack cooldowns.';
  if(effect?.kind==='expose')nextBoost='Next: +'+Math.round(Math.min(.65,effect.bonus*nextStats.supportPower)*100)+'% direct damage to marked enemies.';
  setBattleText('selectedTowerDetail','Permanent LV '+tower.permanentLevel+' · '+rarityInfo(tower.rarity).name+' · '+(tower.level===3?'Max boost this level.':nextBoost));
}
function renderUpcomingWave() {
  if(!canvas)return;
  const container=$('#upcomingWavePreview');if(!container)return;
  const next=game?.spawnPlan.slice(game.spawnCursor).find(spawn=>spawn.wave>game.wave);
  const wave=next?.wave;
  const entries=wave?game.spawnPlan.filter(spawn=>spawn.wave===wave):[];
  const kinds=[...new Set(entries.map(spawn=>spawn.kind))];
  const bossEntry=entries.find(spawn=>spawn.kind==='boss');
  const mapIndex=Math.floor((mapLevel()-1)/5);
  const boss=bossEntry&&game?.engineVersion>=4
    ? (BOSS_DEFS[bossEntry.bossType] || getBossDefinitionForWave(wave,mapIndex))
    : !game&&!isEndlessMode(selectedMode)?getCampaignBoss(mapIndex):null;
  const allSpawned=game && game.spawnCursor===game.spawnPlan.length;
  const key=(runId || 'preview-'+selectedMode+'-'+selectedLevel)+':'+(wave || 0)+':'+Boolean(game?.ended)+':'+Boolean(allSpawned)+':'+(boss?.id||'')+':'+kinds.map(kind=>kind+Boolean(enemyPortraits[kind])).join(',');
  if(key===upcomingPreviewKey)return;upcomingPreviewKey=key;
  setBattleText('upcomingWaveLabel',wave?'WAVE '+String(wave).padStart(2,'0')+' · '+entries.length+' ENEMIES':game?.ended?'DEFENSE COMPLETE':game?(isEndless()?'ENDLESS WAVES':'FINAL WAVE'):'DEPLOY TO SCOUT');
  container.innerHTML=kinds.length?kinds.map(kind=>{
    const definition=kind==='boss'&&boss?boss:ENEMY_DEFS[kind];
    const portrait=kind==='boss'&&boss?null:enemyPortraits[kind];
    return '<div class="wave-enemy" title="'+escapeText(definition.description||definition.name)+'"><span class="wave-enemy-art" style="--enemy-color:'+definition.color+'">'+(portrait?'<img src="'+portrait+'" width="96" height="96" alt="">':'<i aria-hidden="true"></i>')+'</span><span>'+escapeText(definition.name)+'</span><b>×'+entries.filter(spawn=>spawn.kind===kind).length+'</b></div>';
  }).join(''):'<p>'+(game?.ended?'Choose your next defense when you are ready.':game?(isEndless()?'Clear every enemy to advance. The next wave will be stronger.':allSpawned?'All enemies deployed. Protect the core.':'Final wave underway. Protect the core.'):'Deploy your squad to reveal the next wave.')+'</p>';
  if(boss)container.insertAdjacentHTML('beforeend','<div class="boss-scout"><strong>'+escapeText(boss.name)+'</strong><p>'+escapeText(boss.mechanic)+'</p><small>'+escapeText(boss.counter)+'</small></div>');
}
function renderHistory() {
  if(!canvas)return;
  const runs=bootstrapData?.recentRuns || [];
  $('#runHistory').innerHTML=runs.length?runs.map(run=>{
    const endless=isEndlessMode(run.mode),label=endless?run.mode.toUpperCase():'CAMPAIGN';
    return '<div class="history-row"><span class="history-state '+(run.victory||endless?'victory':'')+'">'+(endless?'BANKED':run.victory?'CLEARED':'BREACHED')+'</span><span>'+label+' · '+(endless?'W'+formatNumber(run.waves_cleared ?? run.wavesCleared ?? 0):'LV '+run.campaign_level)+' · '+formatNumber(run.score)+' PTS</span><span class="history-reward">+'+formatNumber(endless?run.reward_shares:run.coins_awarded)+(endless?' SHARES':' ●')+'</span></div>';
  }).join(''):'<p class="muted">Your first defense is waiting.</p>';
}
function renderCollection() {
  chestsUI?.render();
  const ladder=$('#rarityLadder');
  if(ladder)ladder.innerHTML=RARITIES.map((r)=>'<span style="--rarity-color:'+r.color+'">'+r.name.toUpperCase()+'</span>').join('');
  arsenalUI.render();
  applyAccountRestriction();
}
function renderEarning() {
  withdrawalsUI?.render();
  if(withdrawalsUI)void withdrawalsUI.refresh();
  earningUI?.render();
  if(shortlinksUI)void shortlinksUI.initialize();
  updateFaucet();
}
function updateFaucet() {
  const earning=bootstrapData?.earning;
  for(const {button,amount,timer,coinsKey,nextKey} of faucetClaims) {
    const available=typeof earning?.[coinsKey]==='number';
    const wait=Math.max(0,(earning?.[nextKey]||0)-Date.now());
    button.disabled=securityBlocked||claimingFaucet||!available||wait>0;
    button.textContent=wait?'RECHARGING':'CLAIM COINS →';
    if(available)amount.textContent=earning[coinsKey];
    if(!available){timer.textContent='CONNECTING…';continue;}
    const remaining=Math.ceil(wait/1000),hours=Math.floor(remaining/3600),minutes=Math.floor(remaining%3600/60),seconds=remaining%60;
    timer.textContent=wait?'READY IN '+[hours,minutes,seconds].map(n=>String(n).padStart(2,'0')).join(':'):'READY TO CLAIM';
  }
}
async function loadBootstrap({allowDuringAccount=false,timeoutMs,quiet=false}={}) {
  if(accountUI?.isBusy()&&!allowDuringAccount)return false;
  const sequence=++bootstrapSequence,request=api('/api/bootstrap',{timeoutMs});bootstrapRequests.add(request);
  try {
    const data=await request;if(sequence!==bootstrapSequence)return true;
    if(game&&!settled&&battleProfileId!==data.player.id){holdBattleForSignIn();return false;}
    bootstrapData=data;
    selectDefaultCampaignLevel();
    premiumUI?.receiveBootstrap();
    securityBlocked=Boolean(data.security&&data.security.status!=='active');restrictionMessage=data.security?.message||'';
    if(securityBlocked&&game&&!game.ended)setPaused(true);
    ui.alias.textContent=bootstrapData.account?.username||bootstrapData.player.alias; ui.coins.textContent=formatNumber(bootstrapData.player.coins);
    $('#accountAccess').textContent=bootstrapData.account?.authenticated?'MY ACCOUNT ↗':'SIGN IN ↗';
    const levels=bootstrapData.campaign?.levels;
    if(levels?.length){
      const cleared=levels.filter(level=>level.cleared).length;
      $('#campaignMeter').style.width=cleared/levels.length*100+'%';
      $('#railProgress').textContent=cleared+' / '+levels.length+' LEVELS CLEARED';
    }
    $('#saveStatus').textContent=securityBlocked?'ACCOUNT RESTRICTED':game&&!game.ended?'DEFENSE IN PROGRESS':'PROGRESS SAVED'; renderCampaign(); renderCollection(); renderEarning(); renderHistory();accountUI?.render();squadsUI?.render();applyAccountRestriction();if(accountUI)void accountUI.checkAdminAccess();
    return true;
  } catch (error) {
    if(sequence!==bootstrapSequence||quiet)return false;
    $('#saveStatus').textContent='CONNECTION UNAVAILABLE'; if(ui.startButton)ui.startButton.disabled=true;
    if(!bootstrapData&&accountUI){$('#accountConnectionMessage').textContent='Unable to load your profile. Reconnect to continue.';$('#retryAccountLoad').classList.remove('hidden');}
    showToast('Unable to load saved progress. Refresh to reconnect.'); console.warn(error); return false;
  }finally{bootstrapRequests.delete(request);}
}
function switchView(next) {
  return pageNavigation?.navigate(next);
}
function showPage(page) {
  view=page.view;
  if(page.mode)chooseMode(page.mode);
}
function setPaused(value) {
  if (!game || game.ended) return;
  if((verificationHold||sessionInterrupted||battleMoved())&&!value)return;
  paused=value; $('#pauseOverlay').classList.toggle('hidden',!paused);updatePlacementControls();
  renderBattleUpgradeControls(game.towers.find(tower=>tower.pad===selectedPad));
  $('#pauseRun').textContent=paused?'▶ RESUME':'Ⅱ PAUSE'; accumulator=0; lastFrame=performance.now();
}
function updateHud() {
  if (!game) return;
  ui.wave.textContent=isEndless()?game.wave+' · ENDLESS':game.wave+' / '+game.totalWaves; ui.lives.textContent=game.lives; ui.energy.textContent=Math.floor(game.energy);
  const countdown=currentWaveCountdown(game);
  ui.nextWave.textContent=countdown===null?(isEndless()?'CLEAR THIS WAVE':'FINAL CONTACT'):countdown===0?'WAVE ACTIVE':'NEXT WAVE '+(countdown*TICK_MS/1000).toFixed(1)+'S';
  renderBattleInspector();
  updatePlacementControls();
  const controlsLocked=sessionInterrupted||verificationHold||securityBlocked||battleMoved();
  const canCall=countdown!==null && countdown>=10 && !game.ended;
  ui.callWave.disabled=controlsLocked||!canCall; ui.callWave.textContent=canCall?'CALL WAVE +'+Math.min(32,Math.floor(countdown/2))+' ◉':'CALL WAVE';
  $('#pauseRun').disabled=controlsLocked||game.ended;
  $('#liveEndlessLine').classList.toggle('hidden',!isEndless());
  $('#clearedWaveCount').textContent=formatNumber(game.wavesCleared || 0);
  $('#attemptShareCount').textContent=formatNumber(calculateWaveShares(game.wavesCleared || 0));
  $('#endAttempt').classList.toggle('hidden',!isEndless());$('#endAttempt').disabled=controlsLocked||game.ended||submitting;
  document.querySelectorAll('#towerDeck .tower-card').forEach((button)=>{const owned=game.roster.some((t)=>t.type===button.dataset.tower);button.disabled=controlsLocked||!owned;button.classList.toggle('unaffordable',owned && game.energy<TOWER_DEFS[button.dataset.tower].cost);});
}
function roundedRect(context,x,y,width,height,radius) {context.beginPath();traceRoundedRect(context,x,y,width,height,radius);}
function drawBackground(time) {
  const biome=getMapLevel(mapLevel(),game?.mapLayoutVersion || MAP_LAYOUT_VERSION).map;
  if(!drawMapArtwork(ctx,biome,game?.mapLayoutVersion || MAP_LAYOUT_VERSION)){
    ctx.fillStyle=['#619c72','#548e95','#b86f56','#695483'][biome%4];ctx.fillRect(0,0,960,540);
    for(let i=0;i<95;i++){const x=(i*173+29)%960,y=(i*97+35)%540;ctx.beginPath();ctx.ellipse(x,y,4+i%7,2+i%3,0,0,Math.PI*2);ctx.fillStyle=i%2?'#ffffff0c':'#13293610';ctx.fill();}
  }
  const vignette=ctx.createRadialGradient(480,270,200,480,270,590);vignette.addColorStop(0,'#102f2800');vignette.addColorStop(1,'#10223859');ctx.fillStyle=vignette;ctx.fillRect(0,0,960,540);
  // Small drifting pollen makes the illustrated terrain feel alive.
  ctx.save();for(let i=0;i<14;i++){const x=(i*137+time*.006)%990,y=(i*83+Math.sin(time*.0006+i)*12)%540;ctx.fillStyle=i%3?'#fff8b665':'#affff084';ctx.beginPath();ctx.arc(x,y,1.2+i%2*.6,0,Math.PI*2);ctx.fill();}ctx.restore();
}
function drawPath() {
  const points=game?.pathPoints || getMap(mapLevel()).path;
  // Roads are painted into the terrain atlas using the engine's exact route guide.
  ctx.save();
  const exitY=points.at(-1).y;
  const modernExit=(game?.mapLayoutVersion || MAP_LAYOUT_VERSION)>=6;
  const core=modernExit?getMapExitAnchor(points):{x:925,y:exitY};
  ctx.fillStyle='#172a3a55';ctx.beginPath();ctx.ellipse(core.x,core.y+19,35,18,0,0,Math.PI*2);ctx.fill();
  roundedRect(ctx,core.x-30,core.y-32,61,56,11);ctx.fillStyle='#263f57';ctx.fill();ctx.lineWidth=4;ctx.strokeStyle='#9aaac1';ctx.stroke();
  roundedRect(ctx,core.x-21,core.y-23,43,37,7);ctx.fillStyle='#4bc2a5';ctx.fill();ctx.strokeStyle='#b5ffda';ctx.lineWidth=2;ctx.stroke();
  ctx.fillStyle='#eaffdf';ctx.font='bold 23px Segoe UI';ctx.textAlign='center';ctx.fillText('◈',core.x,core.y+3);
  // Spawn gate and traveling route arrows.
  const from=points[0],to=points[1],ratio=Math.min(1,40/Math.hypot(to.x-from.x,to.y-from.y));
  const entry=game?pointOnPath(40,game):{x:from.x+(to.x-from.x)*ratio,y:from.y+(to.y-from.y)*ratio};
  ctx.fillStyle='#fff3ce88';ctx.beginPath();
  if(modernExit){ctx.translate(entry.x,entry.y);ctx.rotate(Math.atan2(to.y-from.y,to.x-from.x));ctx.moveTo(-4,-6);ctx.lineTo(5,0);ctx.lineTo(-4,6);}
  else{ctx.moveTo(entry.x-4,entry.y-6);ctx.lineTo(entry.x+5,entry.y);ctx.lineTo(entry.x-4,entry.y+6);}
  ctx.fill();
  ctx.restore();
}
function drawPads(time) {
  if((game?.mapLayoutVersion || MAP_LAYOUT_VERSION)>=4)return;
  const pads=game?.padPositions || getMap(mapLevel()).pads;
  drawPlacementSlots(ctx,pads,{occupiedPads:new Set(game?.towers.map(t=>t.pad) || []),selectedPad,hoveredPad,affordable:!game || game.energy>=TOWER_DEFS[selectedType].cost,labelPositions:unitRenderer?.padLabels() || null});
}
function drawTower(tower,time) {
  const pad=game.padPositions[tower.pad],rarity=rarityInfo(tower.rarity);
  for(let i=0;i<tower.level;i++){ctx.beginPath();ctx.arc(pad.x+(i-(tower.level-1)/2)*8,pad.y+23,2.4,0,Math.PI*2);ctx.fillStyle=i?'#ffdf80':'#def9e8';ctx.fill();ctx.strokeStyle='#294035';ctx.lineWidth=1;ctx.stroke();}
  if(tower.rarity!=='common'){ctx.beginPath();ctx.arc(pad.x+23,pad.y-26,4,0,Math.PI*2);ctx.fillStyle=rarity.color;ctx.fill();ctx.lineWidth=1.5;ctx.strokeStyle='#f8f1d7';ctx.stroke();}
}
function drawEnemy(enemy,time) {
  const pose=modelMotion.enemy(enemy),pos=pose.position;
  const sizes={bot:49,runner:48,wraith:58,whale:74,splitter:62,boss:108},size=sizes[enemy.kind]||50;
  ctx.save();
  if(enemy.burnUntil>game.tick){ctx.fillStyle='#ffc277aa';ctx.beginPath();ctx.arc(pos.x+Math.sin(pose.phase*14)*8,pos.y-10-size*.22,3+Math.sin(pose.phase*20)*1.5,0,Math.PI*2);ctx.fill();}
  if(enemy.hp<enemy.maxHp || enemy.kind==='boss'){
    const w=enemy.kind==='boss'?48:26,y=pos.y-size*.39-9;
    roundedRect(ctx,pos.x-w/2-1,y-1,w+2,5,2);ctx.fillStyle='#1c293bbb';ctx.fill();
    roundedRect(ctx,pos.x-w/2,y,w*Math.max(0,enemy.hp/enemy.maxHp),3,2);ctx.fillStyle=enemy.kind==='boss'?'#ffb38d':'#c2f29d';ctx.fill();
  }
  ctx.restore();
}
function render(time,deltaMs=16) {
  drawBackground(time);drawPath();
  const placementPreview=currentPlacementPreview();
  if(placementPreview){
    const {x,y,valid}=placementPreview,range=TOWER_DEFS[selectedType].range;
    ctx.save();ctx.beginPath();ctx.arc(x,y,range,0,Math.PI*2);ctx.fillStyle=valid?'#70f4c31a':'#ff6c6c12';ctx.fill();ctx.strokeStyle=valid?'#b1ffdb8c':'#ff77778c';ctx.lineWidth=1.5;ctx.setLineDash([5,5]);ctx.stroke();ctx.setLineDash([]);
    ctx.beginPath();ctx.ellipse(x,y,27,22,0,0,Math.PI*2);ctx.fillStyle=valid?'#5af4d147':'#ff57775c';ctx.fill();ctx.strokeStyle=valid?'#b8ffe0':'#ff899f';ctx.lineWidth=2;ctx.stroke();ctx.restore();
  }
  if(game){
    modelMotion.update(game,deltaMs,{paused:paused || syncBlocked() || view!=='campaign',speed,alpha:game.ended?1:accumulator/TICK_MS});
    const selected=game.towers.find((t)=>t.pad===selectedPad);
    if(selected){const pad=game.padPositions[selected.pad],range=getTowerStats(game,selected).range;ctx.save();ctx.beginPath();ctx.arc(pad.x,pad.y,range,0,Math.PI*2);ctx.fillStyle='#e5ffd11b';ctx.fill();ctx.strokeStyle='#e7ffc77a';ctx.lineWidth=2;ctx.setLineDash([5,6]);ctx.stroke();ctx.restore();}
    battleFX.update(game,deltaMs,{paused:paused || syncBlocked() || view!=='campaign',speed});battleFX.drawGround(ctx,time);
    drawBossGround(ctx,game,{reducedMotion:modelMotion.reducedMotion});
    unitRenderer.draw(game,modelMotion,{deltaSeconds:deltaMs/1000,paused:paused || syncBlocked() || view!=='campaign',placementPreview});
    if(unitRenderer.frameCount%60===0){
      canvas.dataset.towers=game.towers.length;
      canvas.dataset.enemies=game.enemies.length;
      canvas.dataset.drawCalls=unitRenderer.drawCalls;
    }
    game.towers.forEach(t=>drawTower(t,time));game.enemies.forEach(e=>drawEnemy(e,time));battleFX.draw(ctx,time);drawBossOverlay(ctx,game);
  } else {
    unitRenderer.draw(null,modelMotion,{deltaSeconds:0,paused:true});
  }
  drawPads(time);
}


function clearResumedStart(operationId) {
  if(!operationId)return;
  for(const [key,id] of pendingOperations)if(key.startsWith('/api/run/start{')&&id===operationId)pendingOperations.delete(key);
  for(let index=sessionStorage.length-1;index>=0;index--){
    const key=sessionStorage.key(index);
    if(key?.startsWith('ctd-operation:/api/run/start{')&&sessionStorage.getItem(key)===operationId)sessionStorage.removeItem(key);
  }
}

async function startGame({replace=false}={}) {
  if(securityBlocked){showToast(restrictionMessage);return;}
  if(accountUI?.isBusy()){showToast('Your account is updating. Please wait.');return;}
  if(starting || !unitRenderer || !bootstrapData || game&&!game.ended || game?.ended&&!settled)return;
  const mode=selectedMode,challenge=selectedChallenge(),endless=isEndlessMode(mode);
  const saved=endless&&!replace?challenge?.resumableRun:null;
  const activeMode=['daily','weekly'].find(name=>bootstrapData.modes?.[name]?.resumableRun);
  const replaceRunId=activeMode?bootstrapData.modes[activeMode].resumableRun.runId:null;
  if(!saved&&endless&&challenge?.attempts?.remaining===0){showToast('No attempts remain in this rotation.');return;}
  if(!saved&&activeMode&&!window.confirm('Start a new battle and end your saved '+activeMode+' attempt? Only its verified progress will count.'))return;
  if(!endless)campaignDefaultPending=false;
  starting=true;ui.startButton.disabled=true;ui.playAgain.disabled=true;$('#nextLevel').disabled=true;
  $('#replaceAttempt').disabled=true;
  try{
    const playerId=bootstrapData.player.id;
    const towerTypes=saved?null:arsenalUI.getLoadout();
    if(!saved&&!towerTypes.length)throw new Error('Add at least one tower to your loadout in the Arsenal.');
    await Promise.all([securityUI.ensureHuman('play'),saved?null:loadMapArtwork(getMapLevel(mapLevel(),MAP_LAYOUT_VERSION).map,MAP_LAYOUT_VERSION)]);
    if(bootstrapData?.player.id!==playerId||selectedMode!==mode)throw new Error('Your account or defense selection changed. Try again.');
    const started=saved
      ?await mutate('/api/run/resume',{runId:saved.runId,resumeRevision:saved.resumeRevision})
      :await mutate('/api/run/start',{mode,level:endless?1:selectedLevel,towerTypes,supportsResume:true,...(replaceRunId?{replaceRunId}:{})});
    let nextGame;
    if(saved){
      if(!started.state||started.runId!==saved.runId||started.context?.mode!==mode||started.state.tick!==started.verifiedTick||!started.resumeToken){
        throw new Error('The verified checkpoint could not be loaded.');
      }
      const restored=replayDefenseChunk(started.seed,[],started.context,{state:started.state,endTick:started.verifiedTick});
      if(!restored.valid)throw new Error('The verified checkpoint could not be loaded.');
      nextGame=restored.state;
    }else nextGame=createGame(started.seed,started.context);
    if(bootstrapData?.player.id!==playerId||selectedMode!==mode)throw new Error('Your account or defense selection changed. Try again.');
    if(saved)clearResumedStart(started.startOperationId);
    runId=started.runId;game=nextGame;selectedMode=isEndlessMode(started.context.mode)?started.context.mode:'campaign';
    battleSessionGeneration++;
    battleSession.begin(started);actions=battleSession.actions;syncIssue=null;nextSyncRetry=0;battleProfileId=playerId;
    sessionInterrupted=false;verificationHold=false;securityRetryRequired=false;
    battleFX.reset(game);modelMotion.reset(game);unitRenderer.reset();selectedPad=null;hoveredPad=null;placementPoint=null;buildMode=false;touchPlacement=false;
    document.body.classList.add('is-playing');submitting=false;settled=false;settlementAttempted=false;paused=false;accumulator=0;speed=1;lastFrame=performance.now();
    ui.speed.textContent='1× SPEED';$('#pauseRun').textContent='Ⅱ PAUSE';ui.startOverlay.classList.add('hidden');ui.resultOverlay.classList.add('hidden');$('#pauseOverlay').classList.add('hidden');
    $('#retryVerification').classList.add('hidden');$('#saveStatus').textContent='DEFENSE IN PROGRESS';$('#battleSyncLine').classList.add('hidden');
    renderDeck();updateHud();updatePlacementControls();tone(420,.12,.05);canvas.focus({preventScroll:true});window.scrollTo({top:0,left:0,behavior:'instant'});
    showToast(saved?'Resumed your last verified checkpoint.':isEndless()?'Attempt used. Clear waves to build your verified share.':'Build your defense. Orbs reset each level.');
    void loadBootstrap();
  }catch(error){
    showToast(error.message);
    if(error.status===409)await loadBootstrap({timeoutMs:5000,quiet:true});
  }
  finally{starting=false;renderCampaign();ui.playAgain.disabled=false;}
}
function updateBattleSync(){
  const blocked=syncBlocked();
  $('#battleSyncLine').classList.toggle('hidden',!sessionInterrupted&&!verificationHold&&!syncIssue&&!blocked);
  const status=$('#battleSyncMessage');
  let message='';
  if(battleMoved())message='This battle resumed in another tab. Reload to open the latest verified checkpoint here.';
  else if(sessionInterrupted)message='Your battle is paused. Recheck your session or sign in as the same player.';
  else if(verificationHold)message=securityRetryRequired?'Retry the security check to resume this battle.':'Complete the security check to resume this battle.';
  else if(syncIssue)message=syncIssue.message+' Your battle is kept in this tab.';
  else if(blocked)message='Waiting for the server to verify your progress…';
  if(status.textContent!==message)status.textContent=message;
  const signIn=$('#battleSignIn');if(signIn)signIn.hidden=!sessionInterrupted;
  $('#retryBattleSync').disabled=battleSession.busy||checkingBattleSession;
  $('#retryBattleSync').textContent=battleSession.busy||checkingBattleSession?'CONNECTING…':battleMoved()?'RELOAD CHECKPOINT':sessionInterrupted?'RECHECK SIGN-IN':securityRetryRequired?'VERIFY & RETRY':'RETRY CONNECTION';
}
function holdBattleForSignIn(){
  if(!sessionInterrupted){sessionWasPaused=paused;sessionInterrupted=true;}
  setPaused(true);updateHud();updateBattleSync();
}
function matchesBattleIdentity(session){
  return Boolean(battleProfileId&&session?.profileId===battleProfileId&&typeof session.csrfToken==='string'&&session.csrfToken);
}
async function retryBattleConnection(){
  if(checkingBattleSession||battleSession.busy)return;
  if(battleMoved()){location.reload();return;}
  if(sessionInterrupted){
    checkingBattleSession=true;updateBattleSync();
    try{
      const session=await rawApi(sessionIdentityPath,{timeoutMs:5000});
      if(!matchesBattleIdentity(session)){showToast('Sign in as the player who started this defense.');return;}
      battleSessionGeneration++;bootstrapSequence++;
      bootstrapData.csrfToken=session.csrfToken;
      sessionInterrupted=false;
      if(!sessionWasPaused&&!securityBlocked)setPaused(false);
      updateHud();
    }catch(error){showToast(error.message);return;}
    finally{checkingBattleSession=false;updateBattleSync();}
  }
  securityRetryRequired=false;nextSyncRetry=0;
  if(game?.ended)void settleRun();
  else void checkpointBattle();
}
async function checkpointBattle(){
  if(!game || game.ended || sessionInterrupted || securityBlocked || securityRetryRequired || !battleSession.modern || battleSession.busy || submitting || Date.now()<nextSyncRetry)return;
  try{
    const save=battleSession.flush(game.tick);updateBattleSync();
    const response=await save;syncIssue=null;nextSyncRetry=0;
    if(!response)return;
    if(response.security&&response.security.status!=='active'){securityBlocked=true;restrictionMessage=response.security.message||response.message;setPaused(true);applyAccountRestriction();}
    if(response.poolClosed===true){game.ended=true;game.victory=false;}
    if(!game.ended)$('#saveStatus').textContent='DEFENSE IN PROGRESS';
  }catch(error){
    syncIssue=error;
    const needsAttention=[400,404,409,422].includes(error.status);
    nextSyncRetry=needsAttention?Infinity:Date.now()+Math.max(2500,(error.retryAfterSeconds||0)*1000);
    $('#saveStatus').textContent=needsAttention?'CHECKPOINT NEEDS ATTENTION':'BATTLE WAITING FOR CONNECTION';
    if(battleMoved()){clearBuildSelection();updateHud();}
  }
  finally{updateBattleSync();}
}
async function settleRun() {
  if(submitting || !game || !game.ended || settled || sessionInterrupted)return;
  submitting=true;settlementAttempted=true;$('#retryVerification').disabled=true;
  let result=game,coins=0,shares=0,message,verified=false;
  try{
    const previousTypes=new Set((bootstrapData?.collection||[]).map(tower=>tower.type));
    const settlement=battleSession.modern?await battleSession.flush(game.tick,{finish:true}):await api('/api/run/finish',{method:'POST',body:JSON.stringify({runId,actions})});
    result=settlement.result;coins=settlement.reward?.coins||0;shares=settlement.reward?.shares||0;message=settlement.message;verified=true;settled=true;syncIssue=null;
    await loadBootstrap({timeoutMs:5000,quiet:true});$('#saveStatus').textContent=securityBlocked?'ACCOUNT RESTRICTED':'PROGRESS SAVED';$('#battleSyncLine').classList.add('hidden');
    const newTypes=[...new Set((bootstrapData?.collection||[]).map(tower=>tower.type))].filter(type=>!previousTypes.has(type));
    if(newTypes.length)message+=' New reinforcement'+(newTypes.length===1?'':'s')+': '+newTypes.map(type=>TOWER_CATALOG[type].name).join(', ')+'. Equip in the Arsenal.';
  }catch(error){
    syncIssue=error;
    message=battleMoved()?'This battle resumed in another tab. Reload to open the latest verified checkpoint here.':'Progress has not saved: '+error.message+' Your battle is kept here. Use Retry Save.';
    $('#saveStatus').textContent='SAVE NEEDS RETRY';settled=false;
  }
  const endless=isEndless();
  ui.resultKicker.textContent=verified?'DEFENSE VERIFIED':'SAVE PENDING';
  ui.resultTitle.textContent=endless?(verified?'ATTEMPT BANKED.':'VERIFY YOUR ATTEMPT.'):(result.victory?'CORE SECURED.':'CORE BREACHED.');
  ui.resultScore.textContent=endless?formatNumber(result.wavesCleared ?? game.wavesCleared ?? 0):formatNumber(result.score);
  $('#resultScore').previousElementSibling.textContent=endless?'WAVES CLEARED':'SCORE';
  $('#resultKills').textContent=formatNumber(result.kills);$('#resultRewardLabel').textContent=endless?'VERIFIED SHARES':'COINS';
  ui.resultCoins.textContent='+'+formatNumber(endless?shares:coins);ui.resultMessage.textContent=message || (endless?'Your verified shares have been added to this rotation.':'Defense verified.');
  $('#nextLevel').classList.toggle('hidden',endless);$('#nextLevel').disabled=endless||!verified||!result.victory||selectedLevel>=campaignLevelCount();
  $('#backToModes').disabled=!verified;ui.playAgain.textContent=endless?'USE 1 MORE ATTEMPT':'RETRY LEVEL';
  ui.playAgain.disabled=endless&&selectedChallenge()?.attempts?.remaining===0;
  $('#retryVerification').classList.toggle('hidden',verified);$('#retryVerification').disabled=false;
  $('#retryVerification').textContent=battleMoved()?'RELOAD CHECKPOINT':'RETRY SAVE';
  ui.resultOverlay.classList.remove('hidden');submitting=false;tone(verified?740:180,.25,.05);
}
function recordAction(action) {
  if (!game || game.ended || sessionInterrupted || verificationHold || securityBlocked || battleMoved() || securityUI.isBusy()) return false;
  const full={...action,tick:game.tick}; if(!applyAction(game,full)) return false;
  actions.push(full); updateHud(); tone(action.type==='upgrade'?680:action.type==='rush'?780:440); return true;
}
function upgradeBattlePath(path) {
  if(paused||selectedPad===null||game?.engineVersion<UPGRADE_PATH_ENGINE_VERSION)return;
  if(!recordAction({type:'upgrade',pad:selectedPad,path}))showToast('That upgrade is unavailable. Check the path and your Orbs.');
}
function interactPad(pad) {
  if(!game || game.ended || pad<0 || pad>=game.padPositions.length) return;
  const existing=game.towers.find((t)=>t.pad===pad);
  if(existing) {selectedPad=pad;selectedType=existing.type;clearBuildSelection();updateHud();return;}
  if(!buildMode){selectedPad=null;updateHud();return;}
  if(recordAction({type:'build',tower:selectedType,pad})) {selectedPad=null;clearBuildSelection();updateHud();}
  else showToast('You need '+TOWER_DEFS[selectedType].cost+' Orbs to place this tower.');
}
const placementReasons={
  'invalid-coordinate':'Choose a point on the map.',
  'outside-map':'Keep the entire tower inside the map.',
  terrain:'Find clear, level ground away from scenery and water.',
  path:'Keep the tower and its base off the track.',
  occupied:'Leave room between towers.',
  orbs:'You need more Orbs for this tower.',
  limit:'The field holds up to 40 towers.',
  actions:'This defense has reached its build and upgrade limit.'
};
function currentPlacementPreview(){
  if(!game || game.ended || game.mapLayoutVersion<4 || !placementPoint || !buildMode || (Number.isInteger(hoveredPad) && hoveredPad>=0) || paused || view!=='campaign')return null;
  const positions=game.towers.map(tower=>game.padPositions[tower.pad]);
  let check=getPlacementValidity(game.mapLevel || game.level,placementPoint.x,placementPoint.y,positions,game.mapLayoutVersion);
  if(check.valid && game.actionCount>=400)check={valid:false,reason:'actions'};
  if(check.valid && game.towers.length>=40)check={valid:false,reason:'limit'};
  if(check.valid && game.energy<TOWER_DEFS[selectedType].cost)check={valid:false,reason:'orbs'};
  return {...placementPoint,type:selectedType,...check};
}
function updatePlacementControls(){
  const preview=currentPlacementPreview(),status=$('#placementStatus'),controls=$('#placementActions');
  if(!status || !controls)return;
  status.classList.toggle('hidden',!preview);
  controls.classList.toggle('hidden',!preview || !touchPlacement);
  if(!preview)return;
  status.dataset.valid=String(preview.valid);
  const text=preview.valid?'CLEAR TO BUILD · '+TOWER_DEFS[selectedType].cost+' ORBS':placementReasons[preview.reason] || 'Choose another spot.';
  if(status.textContent!==text)status.textContent=text;
  const confirm=$('#confirmPlacement');confirm.disabled=!preview.valid;
  confirm.textContent='PLACE '+TOWER_DEFS[selectedType].cost+' ◉';
}
function clearBuildSelection(){
  buildMode=false;placementPoint=null;touchPlacement=false;hoveredPad=null;canvas.style.cursor='default';
  renderDeck();updatePlacementControls();
}
function chooseBattleTower(type){
  selectedType=type;selectedPad=null;buildMode=true;placementPoint=null;hoveredPad=null;touchPlacement=false;
  canvas.style.cursor='crosshair';
  renderDeck();if(game)updateHud();updatePlacementControls();
}
function placeAtPreview(){
  const preview=currentPlacementPreview();if(!preview)return;
  if(!preview.valid){showToast(placementReasons[preview.reason] || 'Choose another spot.');return;}
  if(recordAction({type:'build',tower:selectedType,x:preview.x,y:preview.y})){
    selectedPad=null;clearBuildSelection();updateHud();
  }
}
if(canvas){
bindBoardPointer(canvas,event=>{
  if(!game || game.ended || paused || view!=='campaign' || event.button>0) return;
  const {x,y}=getCanvasBoardPoint(canvas,event);
  const pad=unitRenderer?.pick(game,x,y) ?? -1;
  if(game.mapLayoutVersion<4){if(pad>=0)interactPad(pad);return;}
  touchPlacement=event.pointerType==='touch';hoveredPad=pad;
  if(pad>=0){
    const existing=game.towers.find(tower=>tower.pad===pad);
    if(existing){selectedPad=pad;selectedType=existing.type;clearBuildSelection();updateHud();return;}
    hoveredPad=-1;
  }
  selectedPad=null;
  if(!buildMode){placementPoint=null;touchPlacement=false;updateHud();updatePlacementControls();return;}
  placementPoint={x:Math.round(x),y:Math.round(y)};updateHud();updatePlacementControls();
  if(!touchPlacement)placeAtPreview();
});
canvas.addEventListener('pointermove',event=>{
  // Touch/keyboard previews are explicitly confirmed. Moving a mouse toward
  // their confirm button must not move the planned tower underneath it.
  if(event.pointerType==='touch'||touchPlacement)return;
  const {x,y}=getCanvasBoardPoint(canvas,event);hoveredPad=unitRenderer?.pick(game,x,y) ?? -1;
  if(buildMode){placementPoint={x:Math.round(x),y:Math.round(y)};touchPlacement=false;}
  canvas.style.cursor=hoveredPad>=0?'pointer':buildMode?'crosshair':'default';updatePlacementControls();
});
canvas.addEventListener('pointerleave',()=>{if(!touchPlacement)placementPoint=null;hoveredPad=null;canvas.style.cursor=buildMode?'crosshair':'default';updatePlacementControls();});
canvas.addEventListener('keydown',(event)=>{
  if(event.key==='Escape'){event.preventDefault();selectedPad=null;clearBuildSelection();updateHud();return;}
  if(!game || game.ended || paused || view!=='campaign' || game.mapLayoutVersion<4)return;
  const moves={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]};
  if(moves[event.key]){
    if(!buildMode)return;
    event.preventDefault();hoveredPad=null;selectedPad=null;touchPlacement=true;
    const point=placementPoint || {x:480,y:270},step=event.shiftKey?1:5,[dx,dy]=moves[event.key];
    placementPoint={x:Math.max(0,Math.min(960,point.x+dx*step)),y:Math.max(0,Math.min(540,point.y+dy*step))};updatePlacementControls();
  }else if(event.key==='Enter' || event.key===' '){event.preventDefault();placeAtPreview();}
});
$('#confirmPlacement').addEventListener('click',placeAtPreview);
$('#cancelPlacement').addEventListener('click',()=>{selectedPad=null;clearBuildSelection();canvas.focus();});
$('#towerDeck').addEventListener('click',(event)=>{
  if(event.target.closest('[data-manage-loadout]')){switchView('arsenal');return;}
  const button=event.target.closest('[data-tower]'); if(!button || button.disabled)return;
  chooseBattleTower(button.dataset.tower);tone(330,.04);
});
document.addEventListener('pointerdown',event=>{
  if(event.button>0 || event.target.closest('#gameCanvas, #towerDeck [data-tower], #placementActions, .battle-inspector, .mobile-battle-link'))return;
  if(buildMode || selectedPad!==null){selectedPad=null;clearBuildSelection();updateHud();}
});
ui.upgrade.addEventListener('click',()=>{if(selectedPad!==null && !recordAction({type:'upgrade',pad:selectedPad}))showToast('Not enough Orbs to overcharge.');});
ui.sell.addEventListener('click',()=>{if(selectedPad!==null && recordAction({type:'sell',pad:selectedPad})){selectedPad=null;updateHud();}});
ui.callWave.addEventListener('click',()=>{if(recordAction({type:'rush'}))showToast('Wave called early. Bonus Orbs secured.');});
ui.speed.addEventListener('click',()=>{speed=speed===1?2:1;ui.speed.textContent=speed+'× SPEED';});
$('#pauseRun').addEventListener('click',()=>setPaused(!paused)); $('#resumeRun').addEventListener('click',()=>setPaused(false));
ui.startButton.addEventListener('click',()=>void startGame()); ui.playAgain.addEventListener('click',()=>{if(submitting)return;void startGame();});
$('#replaceAttempt').addEventListener('click',()=>void startGame({replace:true}));
$('#nextLevel').addEventListener('click',()=>{if(!settled || submitting || isEndlessMode(selectedMode))return;campaignDefaultPending=false;selectedLevel=Math.min(campaignLevelCount(),selectedLevel+1);campaignChapter=Math.floor((selectedLevel-1)/20);game=null;document.body.classList.remove('is-playing');ui.resultOverlay.classList.add('hidden');ui.startOverlay.classList.remove('hidden');renderCampaign();});
$('#retryVerification').addEventListener('click',()=>void retryBattleConnection());
$('#backToModes').addEventListener('click',()=>{if(settled&&!submitting)chooseMode(selectedMode);});
$('#retryBattleSync').addEventListener('click',()=>void retryBattleConnection());
$('#endAttempt').addEventListener('click',()=>{if(isEndless()&&recordAction({type:'retire'})){$('#pauseOverlay').classList.add('hidden');void settleRun();}});
$('#campaignChapter').addEventListener('change',event=>{campaignChapterChosen=true;campaignChapter=Number(event.target.value);renderCampaign();});
$('#levelGrid').addEventListener('click',(event)=>{
  const button=event.target.closest('[data-level]');if(!button || button.disabled)return;
  if(starting){showToast('Your defense is deploying. Please wait.');return;}
  if(game && !game.ended){showToast('Finish this defense before changing levels.');return;}
  if(game?.ended&&!settled){showToast('Save this defense before changing levels.');return;}
  if(submitting){showToast('Saving this defense. Please wait.');return;}
  campaignDefaultPending=false;
  selectedLevel=Number(button.dataset.level);selectedMode='campaign';game=null;selectedPad=null;placementPoint=null;paused=false;document.body.classList.remove('is-playing');
  ui.resultOverlay.classList.add('hidden');$('#pauseOverlay').classList.add('hidden');ui.startOverlay.classList.remove('hidden');renderCampaign();
});
}
document.querySelectorAll('[data-switch]').forEach((button)=>button.addEventListener('click',()=>switchView(button.dataset.switch)));
$('#quickFaucet').addEventListener('click',()=>switchView('faucet'));
window.addEventListener('beforeunload',event=>{
  const unfinishedLocalBattle=game&&!settled&&!(isEndless()&&battleSession.modern);
  if(accountUI?.isBusy() || withdrawalsUI?.isBusy() || activeEconomyRequests || starting || unfinishedLocalBattle){event.preventDefault();event.returnValue='';}
});
const manual=$('#manualDialog');
$('#howButton')?.addEventListener('click',()=>{if(game && !game.ended)setPaused(true);manual.showModal();});
$('#closeManual')?.addEventListener('click',()=>manual.close());
$('#soundToggle').addEventListener('click',(event)=>{soundEnabled=!soundEnabled;event.currentTarget.innerHTML='♪ <span>'+(soundEnabled?'SOUND ON':'SOUND OFF')+'</span>';event.currentTarget.setAttribute('aria-pressed',String(soundEnabled));if(soundEnabled)tone(520);});
function revealTower(tower, fused=false) {
  const rarity=rarityInfo(tower.rarity), def=TOWER_CATALOG[tower.type];
  $('#lootDialog').style.setProperty('--rarity-color',rarity.color);$('#lootKicker').textContent=fused?'FUSION COMPLETE':'SUPPLY DROP OPENED';
  $('#lootIcon').innerHTML=glyph(tower.type);$('#lootName').textContent=def.name.toUpperCase();$('#lootRarity').textContent=rarity.name.toUpperCase()+' · '+rarity.multiplier+'× RARITY POWER';
  $('#lootDetail').textContent=fused?'Two matching copies became one stronger tower. Your permanent coin upgrades are retained.':'Added to your collection. Its strongest rarity is automatically used in your next defense.';
  $('#lootDialog').showModal();tone(760,.17,.04);
}
for(const id of ['closeLoot','acceptLoot'])$('#'+id)?.addEventListener('click',()=>$('#lootDialog').close());
async function openChest(chestId){
  if(chestOpening||accountUI?.isBusy())return;chestOpening=true;chestsUI.render();
  try{const result=await mutate('/api/chests/open',{chestId});await loadBootstrap();revealTower(result.tower);}
  catch(error){showToast(error.message);}
  finally{chestOpening=false;renderCollection();}
}
for(const claim of faucetClaims)claim.button.addEventListener('click',async()=>{
  if(claimingFaucet)return;
  claimingFaucet=true;
  updateFaucet();
  const status=$('#faucetClaimStatus');
  status.textContent='';
  try{
    const proof=await securityUI.faucetProof();
    const result=await mutate(claim.path,{},proof);
    bootstrapData.earning[claim.nextKey]=result.nextClaimAt;
    status.textContent='Claimed '+result.coinsAwarded+' Coins. Returning to Earn Coins in 5 seconds.';
    setTimeout(()=>{if(pageNavigation?.current?.id==='faucet')location.replace('/earn');},5000);
    void loadBootstrap();
  }
  catch(error){status.textContent=error.message;}
  finally{claimingFaucet=false;updateFaucet();}
});
document.addEventListener('visibilitychange',()=>{if(document.hidden && game && !game.ended)setPaused(true);});
function frame(now) {
  const delta=Math.min(250,now-lastFrame);lastFrame=now;
  if(game&&!game.ended&&isEndless()&&battleSession.modern){
    const end=periodEndNumber(battleSession.context?.periodEnd);
    if(end&&Date.now()>=end)recordAction({type:'retire'});
  }
  if(game && !game.ended && !paused && !verificationHold && !securityBlocked && !syncBlocked() && view==='campaign'){
    accumulator+=delta*speed;
    while(accumulator>=TICK_MS && !game.ended && !syncBlocked()){modelMotion.beforeStep(game);stepGame(game);accumulator-=TICK_MS;}
    updateHud();
  }
  if(!securityBlocked&&game&&!game.ended&&battleSession.modern&&!battleSession.busy&&!submitting&&(game.tick-battleSession.verifiedTick>=300||battleSession.pending)&&Date.now()>=nextSyncRetry)void checkpointBattle();
  if(!securityBlocked&&game?.ended && !submitting && !settled && !settlementAttempted)void settleRun();
  if(syncBlocked()){accumulator=0;updateBattleSync();}
  if(view==='campaign')render(now,delta);requestAnimationFrame(frame);
}
async function updateModeClock(){
  modesUI.updateTimer();
  const challenge=selectedChallenge();
  if(!document.hidden&&!periodRefreshing&&!accountUI?.isBusy()&&isEndlessMode(selectedMode)&&!game&&bootstrapData&&periodEndNumber(challenge?.periodEnd)<=Date.now()){
    periodRefreshing=true;try{await loadBootstrap();}finally{periodRefreshing=false;}
  }
}
pageNavigation=mountPageNavigation({onNavigate:showPage,onLeavePage:page=>{
  if(withdrawalsUI?.isBusy()){showToast('Wait for the withdrawal request to finish.');return false;}
  if(canChangeIdentity())return true;showToast('Finish and save your defense before opening '+page.label+'.');return false;
}});
if(pageNavigation.current){
  renderCollection();accountUI?.render();squadsUI?.render();
  void loadBootstrap();
  if(unitRenderer){
    void unitRenderer.initialize();
    setInterval(updateModeClock,1000);
    requestAnimationFrame(frame);
  }
  if(canvas||chestsUI||$('#arsenalView'))void import('./models3d/portraits.js').then(({getTowerPortraits,getEnemyPortraits})=>{
    const showTowers=portraits=>{towerPortraits={...towerPortraits,...portraits};renderDeck();renderCollection();};
    void getTowerPortraits({onProgress:showTowers}).then(showTowers).catch(error=>console.warn('Tower portraits unavailable',error));
    if(canvas){
      const showEnemies=portraits=>{enemyPortraits={...enemyPortraits,...portraits};renderUpcomingWave();};
      void getEnemyPortraits({onProgress:showEnemies}).then(showEnemies).catch(error=>console.warn('Enemy portraits unavailable',error));
    }
  }).catch(error=>console.warn('Portraits unavailable',error));
  if(faucetClaims.length)setInterval(updateFaucet,1000);
}
