import {loadTurnstile} from './security-ui.js';

async function loginRequest(path, options = {}) {
  const response = await fetch(path, {
    credentials: 'same-origin',
    cache: 'no-store',
    ...options,
    headers: {'content-type': 'application/json', 'x-ctd-client-version': '0.16.0', ...(options.headers || {})}
  });
  const result = await response.json().catch(() => ({error: 'The server could not complete this request.'}));
  if (!response.ok) {
    const error = new Error(result.error || result.message || 'Sign-in could not finish. Please try again.');
    error.code = result.code;
    error.status = response.status;
    throw error;
  }
  return result;
}

export function createLogin({root = document, browser = window, request = loginRequest, getWidget = loadTurnstile} = {}) {
  const byId = id => root.getElementById(id);
  const form = byId('secureLoginForm');
  const message = byId('loginMessage');
  const submit = byId('submitSecureLogin');
  const retry = byId('retryLoginChallenge');
  const restart = byId('restartLogin');
  const existingLogin = byId('existingLogin');
  const container = byId('loginCaptcha');
  const {identifier, password, authenticatorCode, enrollmentInvite} = form.elements;
  const adminMode = new URLSearchParams(browser.location.search).get('next') === 'admin';
  let step = 'credentials';
  let enrollment = null;
  let enrollmentTimer;
  let challenge = null;
  let token = '';
  let widget;
  let widgetId = null;
  let busy = false;
  let challengeGeneration = 0;
  let pageGeneration = 0;

  function render() {
    const showCode = step === 'otp' || step === 'enrollment';
    const showInvite = step === 'invite';
    byId('loginAuthenticatorField').hidden = !showCode;
    byId('loginInviteField').hidden = !showInvite;
    byId('loginEnrollmentSetup').hidden = step !== 'enrollment';
    authenticatorCode.disabled = busy || !showCode;
    authenticatorCode.required = showCode;
    enrollmentInvite.disabled = busy || !showInvite;
    enrollmentInvite.required = showInvite;
    identifier.disabled = busy;
    password.disabled = busy;
    submit.disabled = busy || !token;
    submit.textContent = step === 'invite' ? 'SET UP AUTHENTICATOR →'
      : step === 'enrollment' ? 'CONFIRM AND SIGN IN →' : 'SIGN IN →';
    restart.hidden = step === 'credentials';
    restart.disabled = busy;
  }

  function clearChallenge() {
    challengeGeneration++;
    token = '';
    challenge = null;
    if (widget && widgetId !== null) widget.remove(widgetId);
    widgetId = null;
    container.replaceChildren();
    render();
  }

  function clearEnrollment() {
    clearTimeout(enrollmentTimer);
    enrollment = null;
    byId('loginEnrollmentSecret').textContent = '';
    byId('loginEnrollmentExpiry').textContent = '';
  }

  function changeStep(next) {
    if (next !== 'enrollment') clearEnrollment();
    step = next;
    authenticatorCode.value = '';
    enrollmentInvite.value = '';
    render();
  }

  function resetSignIn() {
    form.reset();
    password.value = '';
    changeStep('credentials');
    clearChallenge();
  }

  async function prepare(notice = '') {
    if (busy) return;
    clearChallenge();
    const version = challengeGeneration;
    const preparedStep = step;
    const announce = text => { message.textContent = notice && step === preparedStep ? notice + ' ' + text : text; };
    retry.hidden = true;
    announce('Loading secure verification…');
    try {
      const current = await request('/api/security/challenge?purpose=login');
      if (version !== challengeGeneration) return;
      if (!current.siteKey || !current.challengeId) throw new Error('Sign-in verification is temporarily unavailable. Please try again later.');
      widget = await getWidget();
      if (version !== challengeGeneration) return;
      challenge = current;
      announce('Complete the security verification to sign in.');
      widgetId = widget.render(container, {
        sitekey: current.siteKey,
        action: current.action || 'login',
        cData: current.cData || current.challengeId,
        theme: 'dark',
        callback: value => {
          if (version !== challengeGeneration) return;
          token = value;
          render();
          announce('Ready to continue.');
        },
        'expired-callback': () => {
          if (version !== challengeGeneration) return;
          token = '';
          render();
          retry.hidden = false;
          announce('Verification expired. Reload it before continuing.');
        },
        'error-callback': () => {
          if (version !== challengeGeneration) return;
          token = '';
          render();
          retry.hidden = false;
          announce('Verification could not load. Check your connection and try again.');
        }
      });
    } catch (error) {
      if (version !== challengeGeneration) return;
      announce(error.message);
      retry.hidden = false;
    }
  }

  function showEnrollment(setup) {
    const expiresAt = Number(setup.expiresAt);
    if (!setup.setupId || !setup.enrollmentToken || !setup.secret || !Number.isSafeInteger(expiresAt) || expiresAt <= Date.now()) {
      throw new Error('Could not start authenticator setup. Try signing in again.');
    }
    clearEnrollment();
    enrollment = {id: setup.setupId, token: setup.enrollmentToken};
    byId('loginEnrollmentSecret').textContent = setup.secret;
    byId('loginEnrollmentExpiry').textContent = 'Setup expires at ' + new Date(expiresAt).toLocaleTimeString() + '.';
    changeStep('enrollment');
    enrollmentTimer = setTimeout(() => {
      if (busy) return;
      changeStep('invite');
      enrollmentInvite.focus();
      void prepare('Authenticator setup expired. Enter the private setup invite again.');
    }, Math.min(expiresAt - Date.now(), 2_147_483_647));
  }

  retry.addEventListener('click', () => void prepare());
  restart.addEventListener('click', () => {
    if (busy) return;
    resetSignIn();
    identifier.focus();
    void prepare();
  });
  for (const field of [identifier, password]) {
    field.addEventListener('input', () => {
      if (step === 'credentials') return;
      changeStep('credentials');
      message.textContent = token ? 'Ready to sign in.' : 'Complete the security verification to sign in.';
    });
  }

  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (busy || !token || !challenge) return;
    const code = authenticatorCode.disabled ? '' : authenticatorCode.value.trim();
    if (authenticatorCode.required && !/^\d{6}$/.test(code)) {
      message.textContent = 'Enter a six-digit authenticator code.';
      authenticatorCode.focus();
      return;
    }
    const payload = {
      identifier: identifier.value.trim(),
      password: password.value,
      challengeId: challenge.challengeId,
      turnstileToken: token
    };
    if (code) payload.authenticatorCode = code;
    if (step === 'invite') payload.enrollmentInvite = enrollmentInvite.value;
    if (step === 'enrollment' && enrollment) {
      payload.enrollmentId = enrollment.id;
      payload.enrollmentToken = enrollment.token;
    }
    const version = pageGeneration;
    busy = true;
    retry.hidden = true;
    clearChallenge();
    message.textContent = 'Signing in securely…';
    let nextNotice = '';
    let nextFocus;
    try {
      const result = await request('/api/account/login', {method: 'POST', body: JSON.stringify(payload)});
      if (version !== pageGeneration) return;
      if (result.adminEnrollment) {
        showEnrollment(result.adminEnrollment);
        nextNotice = 'Add the secret to your authenticator, then enter the code.';
        nextFocus = authenticatorCode;
      } else if (result.account?.authenticated) {
        resetSignIn();
        browser.location.assign(adminMode ? '/admin' : '/campaign');
      } else {
        throw new Error('Sign-in could not be confirmed. Reload verification to try again.');
      }
    } catch (error) {
      if (version !== pageGeneration) return;
      if (error.code === 'ADMIN_LOGIN_MFA_REQUIRED') {
        changeStep(enrollment ? 'enrollment' : 'otp');
        nextNotice = error.message;
        nextFocus = authenticatorCode;
      } else if (error.code === 'ADMIN_LOGIN_ENROLL_REQUIRED') {
        changeStep('invite');
        nextNotice = error.message;
        nextFocus = enrollmentInvite;
      } else {
        password.value = '';
        changeStep('credentials');
        message.textContent = error.message;
        retry.hidden = false;
      }
    } finally {
      if (version === pageGeneration) {
        busy = false;
        render();
      }
    }
    if (version === pageGeneration && nextFocus) {
      nextFocus.focus();
      await prepare(nextNotice);
    }
  });

  async function checkExistingSession() {
    if (adminMode) return false;
    existingLogin.hidden = true;
    form.hidden = false;
    const version = pageGeneration;
    try {
      const session = await request('/api/session/identity', {signal: AbortSignal.timeout(2000)});
      if (version !== pageGeneration) return true;
      if (session.profileId && !identifier.value && !password.value) {
        existingLogin.hidden = false;
        form.hidden = true;
        return true;
      }
    } catch { /* Keep the sign-in form available when no session is confirmed. */ }
    return version !== pageGeneration;
  }

  async function start() {
    if (!await checkExistingSession()) await prepare();
  }

  byId('switchLogin').addEventListener('click', () => {
    existingLogin.hidden = true;
    form.hidden = false;
    identifier.focus();
    void prepare();
  });
  browser.addEventListener('pagehide', () => {
    pageGeneration++;
    busy = false;
    resetSignIn();
  });
  browser.addEventListener('pageshow', event => { if (event.persisted) void start(); });
  render();
  return {prepare, start};
}

if (typeof window !== 'undefined') void createLogin().start();
