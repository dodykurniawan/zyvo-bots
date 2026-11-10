import {getChestCatalog} from './chest-data.js';
import {TOWER_CATALOG, RARITIES} from './game-data.js';
import {getShopProduct} from './shop-products.js';
import {formatShopPrice} from './shop-ui.js';
import {TICK_MS} from './game-engine.js';

const escape = value => String(value).replace(/[&<>"']/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));
const coins = value => new Intl.NumberFormat('en-US').format(value);
const cxlTowers = Object.entries(TOWER_CATALOG).filter(([,tower])=>tower.shopExclusive);

function renderOdds(odds) {
  return odds.map(odd=>'<span style="--drop-color:'+escape(RARITIES.find(rarity=>rarity.id===odd.rarity)?.color||'#ccd7e8')+'"><b>'+coins(odd.percent)+'%</b> '+escape(odd.rarity)+'</span>').join('');
}

function renderPool(pool,portraits) {
  return pool.map(entry=>{
    const tower=TOWER_CATALOG[entry.type],portrait=portraits[entry.type];
    return '<li class="'+(entry.eligible?'':'pool-locked')+'">'+(portrait?'<img src="'+escape(portrait)+'" width="40" height="40" alt="">':'<span class="chest-pool-marker" aria-hidden="true" style="--pool-color:'+escape(tower.color)+'"></span>')+'<span><b>'+escape(tower.name)+'</b><small>'+escape(tower.family)+(entry.eligible?'':' · Level '+entry.unlockLevel)+'</small></span></li>';
  }).join('');
}

function cxlTowerCard(type,tower,portrait,shopEnabled) {
  const image = portrait
    ? `<img src="${escape(portrait)}" width="72" height="72" alt="" loading="lazy">`
    : '<span class="cxl-tower-placeholder" aria-hidden="true">◇</span>';
  const seconds = tower.cooldown * TICK_MS / 1000;
  const generatesOrbs = tower.effect?.kind === 'income';
  const rateLabel = tower.damage ? 'Fire rate' : generatesOrbs ? 'Production' : 'Pulse interval';
  const rate = tower.damage ? (1 / seconds).toFixed(1) + '/s'
    : generatesOrbs ? tower.effect.amount + ' Orbs / ' + seconds + 's' : seconds + 's';
  return `<article class="cxl-tower-card" data-cxl-tower="${escape(type)}" style="--tower-accent:${escape(tower.color)}">
    <div class="cxl-tower-portrait">${image}</div>
    <div class="cxl-tower-copy">
      <small>${escape(tower.family)} · ${escape(tower.role)}</small>
      <h4>${escape(tower.name)}</h4>
    </div>
    <p class="cxl-tower-description">${escape(tower.description)}</p>
    <dl class="cxl-tower-stats" aria-label="Base battle stats">
      <div><dt>Placement</dt><dd>${tower.cost} Orbs</dd></div>
      <div><dt>Damage</dt><dd>${tower.damage || '—'}</dd></div>
      <div><dt>Range</dt><dd>${tower.range || '—'}</dd></div>
      <div><dt>${rateLabel}</dt><dd>${rate}</dd></div>
    </dl>
    <div class="cxl-tower-actions">
      <a class="secondary-button" href="/sandbox?try=${encodeURIComponent(type)}" aria-label="Try ${escape(tower.name)} in Sandbox">Try it <span aria-hidden="true">↗</span></a>
      <button type="button" class="secondary-button cxl-copy-buy" data-shop-sku="ctd:tower:${escape(type)}" ${shopEnabled?'':'disabled'}>Common copy · ${formatShopPrice(getShopProduct('ctd:tower:'+type).unitPriceCents)}</button>
    </div>
  </article>`;
}

export function createChestsUI({getData,getPortraits,isOpening,onOpen,onShop}) {
  const coinGrid=document.querySelector('#coinChestGrid'),shopGrid=document.querySelector('#cxlChestGrid');
  const towerGrid=document.querySelector('#cxlTowerGrid');
  coinGrid.addEventListener('click',event=>{
    const button=event.target.closest('[data-open-chest]');
    if(button&&!button.disabled&&!isOpening())void onOpen(button.dataset.openChest);
  });
  for(const grid of [shopGrid,towerGrid,document.querySelector('#cxlCoinPack')])grid?.addEventListener('click',event=>{
    const button=event.target.closest('[data-shop-sku]');
    if(button&&!button.disabled&&getData()?.shop?.enabled)onShop?.(button.dataset.shopSku);
  });

  function card(chest,data,openPools) {
    const shop=chest.channel==='cxl-shop',locked=chest.locked,opening=isOpening();
    const enough=Boolean(data&&data.player.coins>=chest.cost),portraits=getPortraits();
    const product=shop?getShopProduct('ctd:chest:'+chest.id):null;
    const disabled=shop?!chest.purchaseAvailable||!data?.shop?.enabled:locked||!data||opening||!enough||!chest.purchaseAvailable;
    const action=shop?(disabled?'CHECKOUT UNAVAILABLE':'CHOOSE QUANTITY'):locked?'REACH LEVEL '+chest.unlockLevel:!data?'CONNECTING…':opening?'OPENING…':!enough?'NEED '+coins(chest.cost-data.player.coins)+' MORE COINS':'OPEN CHEST';
    const rarityOdds=renderOdds(chest.odds);
    const chance=chest.towerTypeChance?'<b>1 / '+chest.towerTypeChance.denominator+'</b> chance for each available tower type.':'Tower types become available as you progress.';
    const poolDetails=chest.dropGroups
      ? '<p>The rates below are chances per opening. Eligible towers within each group are equally likely.</p>'+
        chest.dropGroups.map(group=>'<section class="chest-pool-group"><h4>'+escape(group.name)+' towers</h4>'+
          '<div class="chest-drop-odds">'+renderOdds(group.odds)+'</div><ul>'+renderPool(group.towerPool,portraits)+'</ul></section>').join('')
      : '<ul>'+renderPool(chest.towerPool,portraits)+'</ul><p>'+chance+' Rarity is rolled separately.</p>';
    return '<article class="chest-card'+(shop?' chest-card-shop':'')+(locked?' chest-card-locked':'')+'" style="--chest-accent:'+escape(chest.color)+'" data-chest-id="'+escape(chest.id)+'">'+
      '<div class="chest-card-top"><span>'+ (shop?'CXL SHOP EXCLUSIVE':'TIER '+String(chest.tier).padStart(2,'0'))+'</span><span class="chest-availability">'+(shop?'CXL SHOP':locked?'LEVEL '+chest.unlockLevel:'AVAILABLE')+'</span></div>'+
      '<div class="chest-illustration"><img src="'+escape(chest.art)+'" alt="'+escape(chest.name)+'" width="256" height="220" loading="lazy"></div>'+
      '<div class="chest-card-copy"><h3>'+escape(chest.name)+'</h3><p>'+escape(chest.description)+'</p></div>'+
      '<div class="chest-drop-odds" aria-label="Rarity drop rates">'+rarityOdds+'</div>'+
      '<div class="chest-price">'+(product?'<b>'+formatShopPrice(product.unitPriceCents)+' USD</b><small>Per chest · one tower</small>':'<b><span class="resource-art resource-coin" aria-hidden="true"></span> '+coins(chest.cost)+' <small>COINS</small></b><small>'+(locked?'Unlocks at campaign level '+chest.unlockLevel+'.':'One tower. Permanent collection.')+'</small>')+'</div>'+
      '<button class="'+(shop?'secondary-button':'primary-button')+'" type="button" '+(product?'data-shop-sku="'+escape(product.sku)+'"':'data-open-chest="'+escape(chest.id)+'"')+' '+(disabled?'disabled':'')+' aria-label="'+escape(product?action+' · '+chest.name:locked?'Reach campaign level '+chest.unlockLevel+' to unlock '+chest.name:action+' · '+chest.name+' · '+coins(chest.cost)+' Coins')+'">'+escape(action)+(disabled?'':' <span aria-hidden="true">→</span>')+'</button>'+
      '<details class="chest-pool" data-chest-pool="'+escape(chest.id)+'"'+(openPools.has(chest.id)?' open':'')+'><summary>VIEW TOWER POOL <span>'+chest.eligibleTowerTypes.length+' / '+chest.towerPool.length+'</span></summary>'+poolDetails+'</details></article>';
  }
  function render() {
    const data=getData(),catalog=data?.chests||getChestCatalog(1);
    const openPools=new Set([...document.querySelectorAll('[data-chest-pool][open]')].map(element=>element.dataset.chestPool));
    coinGrid.innerHTML=catalog.filter(chest=>chest.channel==='coins').map(chest=>card(chest,data,openPools)).join('');
    shopGrid.innerHTML=catalog.filter(chest=>chest.channel==='cxl-shop').map(chest=>card(chest,data,openPools)).join('');
    if(towerGrid){
      const portraits=getPortraits();
      towerGrid.innerHTML=cxlTowers.map(([type,tower])=>cxlTowerCard(type,tower,portraits[type],Boolean(data?.shop?.enabled))).join('');
    }
    const coinPack=document.querySelector('#shopCoinPackButton');
    if(coinPack)coinPack.disabled=!data?.shop?.enabled;
  }
  return {render};
}
