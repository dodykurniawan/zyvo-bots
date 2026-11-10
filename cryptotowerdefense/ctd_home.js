if (window.self !== window.top) {
  const referral = new URL(location.href).searchParams.get('ref');
  for (const link of document.querySelectorAll('a[href^="/"]')) {
    const destination = new URL(link.href);
    if (destination.origin !== location.origin || destination.pathname === '/') continue;
    link.target = '_blank';
    link.relList.add('noopener');
    // A third-party frame may not be able to set the referral cookie. The
    // first-party signup page verifies the original signed code itself.
    if (destination.pathname === '/signup' && /^[a-f0-9]{64}$/.test(referral ?? '')) {
      destination.searchParams.set('ref', referral);
      link.href = destination.href;
    }
  }
}

const preview = document.querySelector('#homeDefense');
const toggle = document.querySelector('#previewToggle');
const status = document.querySelector('#previewStatus');
let previewModule, mounted = false;
const loadPreview = () => previewModule ||= import('./home-preview.js');
const heroImage=preview.querySelector('.preview-fallback');
const heroReady=heroImage?.decode?.().catch(()=>{});

function afterHeroPaint(work) {
  void Promise.resolve(heroReady).then(()=>requestAnimationFrame(()=>{
    if ('requestIdleCallback' in window) window.requestIdleCallback(work,{timeout:1500});
    else setTimeout(work,0);
  }));
}

const startPreview = async () => {
  if (mounted) return;
  mounted = true;
  try {
    const module = await loadPreview();
    await module.mountHomePreview(preview);
  } catch {
    preview.dataset.preview = 'fallback';
    status.textContent = 'GAME MAP PREVIEW';
    toggle.hidden = true;
  }
};

// The page is useful before graphics load, and data-saver visitors opt in.
if (navigator.connection?.saveData || matchMedia('(prefers-reduced-motion: reduce)').matches) {
  status.textContent = 'GAME MAP PREVIEW';
  toggle.disabled = false;
  toggle.textContent = '▷ PLAY PREVIEW';
  toggle.setAttribute('aria-label', 'Play game preview');
  toggle.addEventListener('click', () => void startPreview(), {once:true});
} else if ('IntersectionObserver' in window) {
  const observer = new IntersectionObserver(entries => {
    if (entries.some(entry => entry.isIntersecting)) {
      observer.disconnect();
      afterHeroPaint(()=>void startPreview());
    }
  }, {rootMargin:'180px'});
  observer.observe(preview);
} else {
  afterHeroPaint(()=>void startPreview());
}

const loadPortraits = async () => {
  try {
    const module = await loadPreview();
    await module.renderHomePortraits((type, source) => {
      const card = document.querySelector('[data-home-model="' + type + '"]');
      const slot = card?.querySelector('.showcase-model, .boss-model');
      if (!slot) return;
      const image = new Image(320, 320);
      image.alt = '';
      image.decoding = 'async';
      image.src = source;
      slot.replaceChildren(image);
      card.dataset.modelReady = 'true';
    });
  } catch {
    // Card names and descriptions are complete without WebGL portraits.
    document.querySelectorAll('[data-home-model]').forEach(card => {
      card.dataset.modelReady = 'unavailable';
    });
  }
};
const showcases = document.querySelectorAll('#homeTowerShowcase, #homeBossShowcase');
if ('IntersectionObserver' in window) {
  const observer = new IntersectionObserver(entries => {
    if (entries.some(entry => entry.isIntersecting)) {
      observer.disconnect();
      afterHeroPaint(()=>void loadPortraits());
    }
  }, {rootMargin:'250px'});
  showcases.forEach(showcase => observer.observe(showcase));
} else {
  afterHeroPaint(()=>void loadPortraits());
}
