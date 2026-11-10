import {loadTurnstile} from './security-ui.js';

async function signupRequest(path, options) {
  const response=await fetch(path,{
    credentials:'same-origin',cache:'no-store',...options,
    headers:{'content-type':'application/json','x-ctd-client-version':'0.19.0'}
  });
  const result=await response.json().catch(()=>null);
  if(!response.ok||!result){
    const error=new Error(result?.error||'Could not complete this request. Please try again.');
    error.code=result?.code;
    throw error;
  }
  return result;
}

export function createSignup({root=document,browser=window,request=signupRequest,getWidget=loadTurnstile}={}){
  const get=id=>root.getElementById(id);
  const form=get('secureSignupForm'),submit=get('submitSecureSignup'),retry=get('retrySignupChallenge');
  const captcha=get('signupCaptcha'),message=get('signupMessage');
  const {username,email,password}=form.elements;
  const operationId=crypto.randomUUID();
  let challenge,token='',widget,widgetId=null,busy=false,challengeVersion=0,pageVersion=0;

  function render(){
    submit.disabled=busy||!token;
    username.disabled=email.disabled=password.disabled=busy;
  }

  function clearChallenge(){
    challengeVersion++;
    challenge=null;
    token='';
    if(widgetId!==null)widget.remove(widgetId);
    widgetId=null;
    captcha.replaceChildren();
    render();
  }

  async function prepare(notice=''){
    if(busy)return;
    clearChallenge();
    const version=challengeVersion;
    const announce=text=>{message.textContent=notice?notice+' '+text:text;};
    retry.hidden=true;
    announce('Loading secure verification…');
    try{
      const current=await request('/api/security/challenge?purpose=login');
      if(version!==challengeVersion)return;
      if(!current.siteKey||!current.challengeId)throw new Error('Signup verification is temporarily unavailable.');
      widget=await getWidget();
      if(version!==challengeVersion)return;
      challenge=current;
      announce('Complete the security verification to sign up.');
      const reset=text=>{
        if(version!==challengeVersion)return;
        token='';
        render();
        retry.hidden=false;
        announce(text);
      };
      widgetId=widget.render(captcha,{
        sitekey:current.siteKey,action:current.action||'login',cData:current.cData||current.challengeId,theme:'dark',
        callback:value=>{
          if(version!==challengeVersion)return;
          token=value;
          retry.hidden=true;
          render();
          announce('Ready to create your account.');
        },
        'expired-callback':()=>reset('Verification expired. Reload it to continue.'),
        'error-callback':()=>reset('Verification could not load. Please try again.')
      });
    }catch(error){
      if(version!==challengeVersion)return;
      announce(error.message);
      retry.hidden=false;
    }
  }

  retry.addEventListener('click',()=>void prepare());
  form.addEventListener('submit',async event=>{
    event.preventDefault();
    if(busy||!challenge||!token||!form.reportValidity())return;
    const body={username:username.value.trim(),email:email.value.trim(),password:password.value,operationId,challengeId:challenge.challengeId,turnstileToken:token};
    const version=pageVersion;
    busy=true;
    clearChallenge();
    message.textContent='Creating your account…';
    let errorText;
    try{
      const result=await request('/api/account/signup',{method:'POST',body:JSON.stringify(body)});
      if(version!==pageVersion)return;
      if(!result.account?.authenticated)throw new Error('Could not verify that signup finished. Try signing in.');
      form.reset();
      browser.location.assign('/campaign');
    }catch(error){
      if(version!==pageVersion)return;
      password.value='';
      errorText=error.message;
    }finally{
      if(version===pageVersion){busy=false;render();}
    }
    if(errorText)await prepare(errorText);
  });
  browser.addEventListener('pagehide',()=>{
    pageVersion++;
    busy=false;
    form.reset();
    clearChallenge();
  });
  browser.addEventListener('pageshow',event=>{if(event.persisted)void prepare();});
  render();
  return {prepare};
}

if(typeof window!=='undefined')void createSignup().prepare();
