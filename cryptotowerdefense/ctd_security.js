const widgetSource='https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
let widgetLibrary;
export const securityCode=error=>error?.code||error?.details?.code||error?.payload?.code||'';

export function loadTurnstile(){
  if(window.turnstile)return Promise.resolve(window.turnstile);
  if(widgetLibrary)return widgetLibrary;
  widgetLibrary=new Promise((resolve,reject)=>{
    const script=document.createElement('script');script.src=widgetSource;script.async=true;script.defer=true;
    const timeout=setTimeout(()=>{script.remove();widgetLibrary=null;reject(new Error('Verification could not load. Check your connection and try again.'));},15_000);
    script.addEventListener('load',()=>{clearTimeout(timeout);if(window.turnstile)resolve(window.turnstile);else{widgetLibrary=null;reject(new Error('Verification could not load. Please try again.'));}},{once:true});
    script.addEventListener('error',()=>{clearTimeout(timeout);script.remove();widgetLibrary=null;reject(new Error('Verification could not load. Allow challenges.cloudflare.com and try again.'));},{once:true});
    document.head.append(script);
  });return widgetLibrary;
}

/** Verification grants live only on the server. This UI never writes success cookies. */
export function createSecurityUI({request,onStatus=()=>{}}){
  const dialog=document.createElement('dialog');dialog.className='ctd-security-dialog';dialog.setAttribute('aria-labelledby','ctdSecurityTitle');
  dialog.innerHTML='<form method="dialog"><button class="ctd-security-close" aria-label="Cancel verification">×</button></form><span class="ctd-security-eyebrow">PROTECT YOUR DEFENSE</span><h2 id="ctdSecurityTitle">A quick security check.</h2><p id="ctdSecurityDescription"></p><div id="ctdSecurityWidget"></div><p id="ctdSecurityMessage" role="status" aria-live="polite"></p><div class="ctd-security-actions"><button id="ctdSecurityRetry" type="button">CHECK AGAIN</button><button id="ctdSecurityContinue" type="button" disabled>CONTINUE →</button></div>';
  document.body.append(dialog);
  const title=dialog.querySelector('h2'),description=dialog.querySelector('#ctdSecurityDescription'),widget=dialog.querySelector('#ctdSecurityWidget'),message=dialog.querySelector('#ctdSecurityMessage'),retry=dialog.querySelector('#ctdSecurityRetry'),proceed=dialog.querySelector('#ctdSecurityContinue');
  let active=null,widgetId=null,widgetApi=null,attemptSequence=0;
  const humanRequests=new Map();let cancellationSequence=0;
  function clearWidget(){if(widgetApi&&widgetId!==null)widgetApi.remove(widgetId);widgetId=null;widget.replaceChildren();}
  function show(label,detail){title.textContent=label;description.textContent=detail;message.textContent='';retry.hidden=true;proceed.hidden=false;proceed.disabled=true;dialog.showModal();}
  function finish(value,error){if(!active)return;const pending=active;active=null;attemptSequence++;clearWidget();dialog.close();onStatus('');error?pending.reject(error):pending.resolve(value);}
  dialog.addEventListener('cancel',()=>finish(null,new Error('Verification was cancelled.')));
  dialog.addEventListener('close',()=>{if(active)finish(null,new Error('Verification was cancelled.'));});

  async function humanAttempt(purpose){
    const attempt=++attemptSequence;
    clearWidget();message.textContent='Loading secure verification…';proceed.disabled=true;retry.hidden=true;let token='';
    try{
      const faucet=purpose==='faucet';
      const challenge=await request('/api/security/challenge?purpose='+encodeURIComponent(faucet?'play':purpose));
      if(!active||attempt!==attemptSequence)return;
      if(!challenge.siteKey||!challenge.challengeId)throw new Error('Security verification is temporarily unavailable. Please try again later.');
      widgetApi=await loadTurnstile();
      if(!active||attempt!==attemptSequence)return;
      widgetId=widgetApi.render(widget,{sitekey:challenge.siteKey,action:challenge.action||purpose,cData:challenge.cData||challenge.challengeId,theme:'dark',
        callback:value=>{token=value;proceed.disabled=false;message.textContent='Verification is ready. Continue when you are ready.';},
        'expired-callback':()=>{token='';proceed.disabled=true;retry.hidden=false;message.textContent='This verification expired. Please check again.';},
        'error-callback':()=>{token='';proceed.disabled=true;retry.hidden=false;message.textContent='Verification could not finish. Check your connection, then try again.';}});
      message.textContent='Complete the verification above.';
      proceed.onclick=async()=>{
        if(!token||proceed.disabled)return;proceed.disabled=true;retry.hidden=true;message.textContent='Confirming with the server…';
        if(faucet){const proof={challengeId:challenge.challengeId,turnstileToken:token};token='';finish(proof);return;}
        try{const verified=await request('/api/security/verify',{method:'POST',body:JSON.stringify({purpose,challengeId:challenge.challengeId,turnstileToken:token})});token='';finish(verified);}
        catch(error){token='';clearWidget();message.textContent=error.message;retry.hidden=false;}
      };
    }catch(error){if(!active||attempt!==attemptSequence)return;message.textContent=error.message;retry.hidden=false;}
    retry.onclick=()=>void humanAttempt(purpose);
  }
  function begin(purpose){
    if(active)return active.purpose===purpose?active.promise:active.promise.then(()=>begin(purpose));
    let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});active={promise,resolve,reject,purpose};
    const detail=purpose==='faucet'?'Verify this claim before collecting your Faucet Coins.'
      :purpose==='play'?'You’re still signed in. Complete this security check to continue playing.'
      :'Complete this security check to continue with your account change.';
    show('A quick security check.',detail);
    onStatus('Security verification required');void humanAttempt(purpose);
    return promise;
  }
  function ensureHuman(purpose='play'){
    if(humanRequests.has(purpose))return humanRequests.get(purpose).promise;
    const sequence=cancellationSequence;let cancel;
    const work=new Promise((resolve,reject)=>{
      cancel=reject;
      (async()=>{
        const status=await request('/api/security/status'),now=Date.now();
        if(sequence!==cancellationSequence)throw new Error('Verification was cancelled.');
        const valid=Number(status.verifiedUntil)>now+5000&&(purpose!=='account'||status.purpose==='account'&&Number(status.verifiedAt)>now-300_000);
        return valid?status:begin(purpose);
      })().then(resolve,reject);
    });
    const promise=work.finally(()=>humanRequests.delete(purpose));humanRequests.set(purpose,{promise,cancel});return promise;
  }
  return{
    ensureHuman,
    faucetProof:()=>begin('faucet'),
    async handleError(error,{retry:retryOperation}={}){
      const code=securityCode(error);
      if(code!=='HUMAN_VERIFICATION_REQUIRED'&&code!=='HUMAN_REQUIRED')throw error;
      const verified=await ensureHuman('play');
      return retryOperation?retryOperation():verified;
    },
    cancel:()=>{cancellationSequence++;const error=new Error('Verification was cancelled.');for(const entry of humanRequests.values())entry.cancel(error);finish(null,error);},
    isBusy:()=>Boolean(active)||humanRequests.size>0
  };
}
