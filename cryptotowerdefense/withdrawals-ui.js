const ENDPOINT = '/api/withdrawals';
const USD_SCALE = 1_000_000n;
const PROVIDER_SCALE = 100_000_000n;
const AUTO_REFRESH_MS = 60_000;
const STATUS_LABELS = {
  pending: 'Pending review',
  sending: 'Sending',
  uncertain: 'Payment under verification',
  paid: 'Paid',
  rejected: 'Rejected'
};

export function parseWithdrawalUsd(value) {
  const input = value.trim();
  if (input.length > 24 || !/^(?:\d+(?:\.\d{0,6})?|\.\d{1,6})$/.test(input)) return null;
  const [whole, fraction = ''] = input.split('.');
  const micros = BigInt(whole || '0') * USD_SCALE + BigInt(fraction.padEnd(6, '0'));
  return micros > 0n && micros <= BigInt(Number.MAX_SAFE_INTEGER) ? Number(micros) : null;
}

function units(value) {
  if (Number.isSafeInteger(value) && value >= 0) return BigInt(value);
  if (typeof value === 'string' && /^\d{1,24}$/.test(value)) return BigInt(value);
  return null;
}

function usd(value) {
  const micros = units(value);
  if (micros === null) return '—';
  const whole = (micros / USD_SCALE).toLocaleString('en-US');
  const fraction = (micros % USD_SCALE).toString().padStart(6, '0').replace(/0+$/, '').padEnd(2, '0');
  return '$' + whole + '.' + fraction;
}

function providerAmount(value, currency) {
  const amount = units(value);
  if (amount === null) return '';
  return (amount / PROVIDER_SCALE).toString() + '.' + (amount % PROVIDER_SCALE).toString().padStart(8, '0') + ' ' + currency;
}

function append(parent, tag, value, className) {
  const element = document.createElement(tag);
  element.textContent = value;
  if (className) element.className = className;
  parent.append(element);
  return element;
}

export function createWithdrawalsUI({getAccountId, isRestricted, isAccountBusy, request, verify,
  documentObject = document, windowObject = globalThis.window}) {
  const byId = id => documentObject.getElementById(id);
  const form = byId('withdrawalForm');
  const amount = byId('withdrawalAmount');
  const currency = byId('withdrawalCurrency');
  const recipient = byId('withdrawalRecipient');
  const submitButton = byId('reviewWithdrawal');
  const refreshButton = byId('refreshWithdrawals');
  const message = byId('withdrawalMessage');
  const history = byId('withdrawalHistory');
  const confirm = byId('withdrawalConfirm');
  const confirmButton = byId('confirmWithdrawal');
  let accountId = null;
  let generation = 0;
  let summary = null;
  let loading = false;
  let submitting = false;
  let loadFailed = false;
  let pending = null;
  let draft = null;
  let autoTimer = null;
  let refreshController = null;
  let refreshSequence = 0;
  let lastRefreshStartedAt = 0;
  let destroyed = false;
  let pageActive = true;
  const lifecycleListeners = [];

  function walletVisible() {
    if (!pageActive || documentObject.hidden || documentObject.visibilityState === 'hidden') return false;
    const view = byId('walletView');
    if (!view || view.hidden || view.classList?.contains('hidden')) return false;
    if (view.getClientRects && view.getClientRects().length === 0) return false;
    const style = windowObject?.getComputedStyle?.(view);
    return !style || (style.display !== 'none' && style.visibility !== 'hidden');
  }

  function cancelTimer() {
    if (autoTimer !== null) windowObject?.clearTimeout(autoTimer);
    autoTimer = null;
  }

  function cancelRefresh() {
    refreshSequence++;
    refreshController?.abort();
    refreshController = null;
    loading = false;
  }

  function scheduleAutoRefresh() {
    if (destroyed || !windowObject?.setTimeout) return;
    if (!walletVisible() || !getAccountId()) {
      cancelTimer();
      if (refreshController) cancelRefresh();
      return;
    }
    if (autoTimer !== null) return;
    autoTimer = windowObject.setTimeout(async () => {
      autoTimer = null;
      await refresh({automatic: true});
      scheduleAutoRefresh();
    }, AUTO_REFRESH_MS);
  }

  function syncAccount() {
    const active = getAccountId();
    if (active === accountId) return;
    accountId = active;
    generation++;
    cancelRefresh();
    summary = null;
    loading = false;
    submitting = false;
    loadFailed = false;
    pending = null;
    draft = null;
    if (confirm.open) confirm.close();
    form.reset();
    message.textContent = '';
    history.replaceChildren();
  }

  function setSummary(result) {
    const amountKeys = ['minUsdMicros', 'maxUsdMicros', 'availableUsdMicros', 'reservedUsdMicros', 'paidUsdMicros'];
    if (typeof result?.enabled !== 'boolean' || !Array.isArray(result.currencies) || !Array.isArray(result.withdrawals) ||
        !amountKeys.every(key => Number.isSafeInteger(result[key]) && result[key] >= 0)) {
      throw new Error('Unable to read withdrawal status.');
    }
    summary = result;
    loadFailed = false;
    const selected = currency.value;
    currency.replaceChildren(new Option('Choose an asset', ''));
    for (const code of result.currencies) {
      if (typeof code === 'string' && /^[A-Z0-9]{2,8}$/.test(code)) currency.add(new Option(code, code));
    }
    currency.value = result.currencies.includes(selected) ? selected : '';
    history.replaceChildren();
    for (const row of result.withdrawals) {
      const item = append(history, 'li', '');
      const main = append(item, 'div', '', 'withdrawal-record-main');
      const asset = typeof row.currency === 'string' ? row.currency : '';
      append(main, 'b', usd(row.amountUsdMicros) + (asset ? ' · ' + asset : ''));
      const status = Object.hasOwn(STATUS_LABELS, row.status) ? row.status : '';
      const badge = append(main, 'span', STATUS_LABELS[status] || 'Status unavailable', 'withdrawal-record-status');
      badge.dataset.status = status;
      append(item, 'span', row.recipient || '', 'withdrawal-record-recipient');
      const amountPaid = providerAmount(row.amountUnits, asset);
      if (amountPaid) append(item, 'span', amountPaid, 'withdrawal-record-amount');
      const created = new Date(row.createdAt);
      if (row.createdAt != null && !Number.isNaN(created.getTime())) {
        const time = append(item, 'time', created.toLocaleString());
        time.dateTime = created.toISOString();
      }
      if (row.payoutId != null && row.payoutId !== '') append(item, 'small', 'FaucetPay reference ' + row.payoutId);
    }
    if (pending && result.withdrawals.some(row => row.id === pending.id)) {
      pending = null;
      form.reset();
      message.textContent = 'Your request appears in the withdrawal history below.';
    }
  }

  function canRequest() {
    return accountId && summary?.enabled === true && (pending || !hasOpenRequest()) &&
      !loadFailed && !loading && !submitting && !isRestricted() && !isAccountBusy();
  }

  function hasOpenRequest() {
    return summary?.withdrawals.some(row => ['pending', 'sending', 'uncertain'].includes(row.status));
  }

  function render() {
    syncAccount();
    const signedIn = Boolean(accountId);
    const connecting = accountId === undefined;
    const restricted = isRestricted();
    const enough = summary?.availableUsdMicros >= summary?.minUsdMicros;
    const requestAvailable = canRequest() && (enough || pending);
    byId('withdrawalSignIn').hidden = signedIn || connecting;
    form.hidden = !signedIn;
    byId('withdrawalBalances').hidden = !signedIn;
    byId('withdrawalHistorySection').hidden = !signedIn;
    refreshButton.hidden = !signedIn;
    refreshButton.disabled = loading || submitting;
    refreshButton.textContent = loading ? 'Checking…' : 'Refresh status';
    byId('withdrawalAvailable').textContent = usd(summary?.availableUsdMicros);
    byId('withdrawalReserved').textContent = usd(summary?.reservedUsdMicros);
    byId('withdrawalPaid').textContent = usd(summary?.paidUsdMicros);
    const limits = byId('withdrawalLimits');
    if (!summary) limits.textContent = 'Limits appear when withdrawal status loads.';
    else if (summary.minUsdMicros <= 1) limits.textContent = 'Up to ' + usd(summary.maxUsdMicros) + ' USD per request. Amounts must cover one FaucetPay unit at the current rate.';
    else limits.textContent = 'Request range ' + usd(summary.minUsdMicros) + ' to ' + usd(summary.maxUsdMicros) + ' USD. Amounts must cover one FaucetPay unit at the current rate.';
    byId('withdrawalEmpty').hidden = Boolean(summary?.withdrawals.length);
    byId('withdrawalEmpty').textContent = summary ? 'No withdrawal requests yet.' : loading ? 'Loading withdrawal history…' : 'Withdrawal history is unavailable.';
    const status = byId('withdrawalStatus');
    if (connecting) status.textContent = 'Connecting to your account…';
    else if (!signedIn) status.textContent = 'Sign in to see your settled rewards and withdrawal history.';
    else if (restricted) {
      const held = summary?.heldUsdMicros > 0 ? usd(summary.heldUsdMicros) + ' USD is on hold. ' : '';
      status.textContent = held + 'Your account cannot request withdrawals at the moment. You can still check your history.';
    }
    else if (loadFailed) status.textContent = 'Could not check withdrawal status. Refresh status to try again.';
    else if (!summary) status.textContent = 'Checking withdrawal status…';
    else if (!summary.enabled) status.textContent = 'New withdrawal requests are paused. You can still check your history.';
    else if (hasOpenRequest() && !pending) status.textContent = 'You have a withdrawal in progress. Check its status in your history.';
    else if (summary.availableUsdMicros === 0 && !pending) status.textContent = 'You have no settled rewards available to withdraw.';
    else if (!enough && !pending) status.textContent = 'Your available reward balance is below the withdrawal minimum.';
    else status.textContent = 'Requests are reviewed before payment.';
    for (const field of [amount, currency, recipient]) field.disabled = !requestAvailable || Boolean(pending);
    submitButton.disabled = !requestAvailable;
    submitButton.textContent = submitting ? 'Submitting…' : pending ? 'Review same request' : 'Review request';
    confirmButton.disabled = !requestAvailable;
    scheduleAutoRefresh();
  }

  async function refresh({automatic = false} = {}) {
    syncAccount();
    if (destroyed || !accountId || !walletVisible() || loading || submitting || isAccountBusy()) return;
    // Visibility and focus often arrive together. Reuse a just-started read.
    if (automatic && Date.now() - lastRefreshStartedAt < 1_000) return;
    const version = generation;
    const sequence = ++refreshSequence;
    const controller = new AbortController();
    refreshController = controller;
    lastRefreshStartedAt = Date.now();
    const current = () => !destroyed && version === generation && sequence === refreshSequence &&
      accountId === getAccountId() && !controller.signal.aborted;
    loading = true;
    render();
    try {
      const result = await request(ENDPOINT, {signal: controller.signal});
      if (current()) setSummary(result);
    } catch {
      if (current()) loadFailed = true;
    } finally {
      if (version === generation && sequence === refreshSequence) {
        loading = false;
        refreshController = null;
      }
      if (!destroyed) render();
    }
  }

  function review(event) {
    event.preventDefault();
    if (!canRequest()) return;
    const amountUsdMicros = pending?.amountUsdMicros ?? parseWithdrawalUsd(amount.value);
    const asset = pending?.currency ?? currency.value;
    const email = pending?.recipient ?? recipient.value.trim().toLowerCase();
    if (!pending) {
      if (!amountUsdMicros) {
        message.textContent = 'Enter a positive USD amount with up to six decimal places.';
        return;
      }
      if (amountUsdMicros < summary.minUsdMicros || amountUsdMicros > summary.maxUsdMicros) {
        message.textContent = 'Enter an amount within the request limits shown above.';
        return;
      }
      if (amountUsdMicros > summary.availableUsdMicros) {
        message.textContent = 'That amount exceeds your available reward balance.';
        return;
      }
      if (!summary.currencies.includes(asset) || !email || !recipient.checkValidity()) {
        message.textContent = 'Choose an asset and enter your FaucetPay email.';
        return;
      }
    }
    draft = pending || {id: crypto.randomUUID(), amountUsdMicros, currency: asset, recipient: email};
    byId('withdrawalConfirmAmount').textContent = usd(amountUsdMicros) + ' USD';
    byId('withdrawalConfirmCurrency').textContent = asset;
    byId('withdrawalConfirmRecipient').textContent = email;
    message.textContent = '';
    confirm.showModal();
  }

  async function submit(payload) {
    if (!canRequest()) return;
    const version = generation;
    let sent = false;
    let refreshAfter = false;
    submitting = true;
    message.textContent = 'Checking account security…';
    render();
    try {
      await verify();
      if (version !== generation || accountId !== getAccountId()) return;
      if (isRestricted()) throw new Error('Your account cannot request withdrawals at the moment.');
      sent = true;
      message.textContent = 'Submitting your request…';
      const result = await request(ENDPOINT, {method: 'POST', body: JSON.stringify(payload)});
      if (version !== generation || accountId !== getAccountId()) return;
      setSummary(result);
      pending = null;
      form.reset();
      message.textContent = 'Request recorded. Check your withdrawal history for its status.';
    } catch (error) {
      if (version !== generation || accountId !== getAccountId()) return;
      // A typed quote rejection is returned before the reservation is created.
      // Transport failures and unclassified server errors can still have committed.
      const status = Number.isInteger(error?.status) ? error.status : null;
      const quoteRejected = error?.code === 'WITHDRAWAL_QUOTE_UNAVAILABLE' && [422, 503].includes(status);
      const knownFailure = quoteRejected || error?.code === 'WITHDRAWALS_PAUSED' || (status >= 400 && status < 500);
      const unknownResult = sent && !knownFailure && (status === null || status >= 500);
      if (pending || unknownResult) {
        pending = payload;
        message.textContent = knownFailure
          ? error.message + ' Refresh status or retry this same request.'
          : 'The request could not be confirmed. Refresh status or retry this same request.';
      } else {
        message.textContent = error.message;
      }
      refreshAfter = sent;
    } finally {
      if (version === generation) submitting = false;
      render();
    }
    if (refreshAfter) await refresh();
  }

  form.addEventListener('submit', review);
  refreshButton.addEventListener('click', () => void refresh());
  byId('cancelWithdrawal').addEventListener('click', () => confirm.close());
  confirm.addEventListener('close', () => {
    draft = null;
    byId('withdrawalConfirmRecipient').textContent = '';
  });
  confirmButton.addEventListener('click', () => {
    const payload = draft;
    confirm.close();
    if (payload) void submit(payload);
  });
  function resumeFreshness() {
    if (destroyed) return;
    if (!walletVisible()) {
      cancelTimer();
      cancelRefresh();
      return;
    }
    void refresh({automatic: true});
    scheduleAutoRefresh();
  }
  function listen(target, event, handler) {
    if (!target?.addEventListener) return;
    target.addEventListener(event, handler);
    lifecycleListeners.push(() => target.removeEventListener?.(event, handler));
  }
  listen(windowObject, 'focus', resumeFreshness);
  listen(documentObject, 'visibilitychange', resumeFreshness);
  listen(windowObject, 'pageshow', () => { pageActive = true; resumeFreshness(); });
  listen(windowObject, 'pagehide', () => { pageActive = false; cancelTimer(); cancelRefresh(); });
  render();
  return {render, refresh, isBusy: () => submitting, destroy() {
    destroyed = true;
    cancelTimer();
    cancelRefresh();
    for (const remove of lifecycleListeners) remove();
  }};
}
