(function () {
  const $ = id => document.getElementById(id);
  const panel = $('diagnostics');
  let running = false;

  $('diagJs').textContent = 'SIM';
  function appendFlow(message) {
    const log = $('diagFlowLog');
    if (!log) return;
    if (log.children.length === 1 && log.children[0].textContent === 'Aguardando execução do app.js') log.replaceChildren();
    const item = document.createElement('li');
    item.textContent = `${new Date().toLocaleTimeString()} · ${message}`;
    log.appendChild(item);
    while (log.children.length > 40) log.firstElementChild.remove();
  }
  window.offtecDiagnosticStage = stage => {
    $('diagLast').textContent = stage;
    appendFlow(stage);
    console.info(`[OFFTEC HUB][FLOW] ${stage}`);
  };
  window.offtecDiagnosticModules = (received, rendered) => {
    $('diagModules').textContent = `${received} recebidos · ${rendered} renderizados`;
    appendFlow(`Módulos: ${received} recebidos · ${rendered} renderizados no DOM`);
  };
  window.offtecDiagnosticLoading = loading => {
    $('diagLoading').textContent = loading ? 'ATIVO' : 'ENCERRADO';
    appendFlow(`loading=${loading ? 'true' : 'false'}${loading ? '' : ' (carregamento encerrado)'}`);
  };
  $('diagnosticToggle').addEventListener('click', () => {
    panel.hidden = !panel.hidden;
    if (!panel.hidden && !$('diagHealth').dataset.done) run();
  });
  $('diagnosticRun').addEventListener('click', run);
  $('diagUrl').textContent = location.href;
  window.offtecDiagnosticError = error => {
    const detail = error && (error.stack || error.message) ? String(error.stack || error.message) : String(error);
    $('diagError').textContent = detail;
    $('diagLast').textContent = 'Falha: ' + (error && error.message ? error.message : detail);
    appendFlow(`ERRO: ${detail}`);
  };
  $('diagWebView').textContent = window.Offtec && typeof window.Offtec.isWebViewInitialized === 'function'
    ? (window.Offtec.isWebViewInitialized() ? 'SIM' : 'NÃO') : 'NÃO confirmado (bridge indisponível)';
  document.addEventListener('DOMContentLoaded', () => {
    $('diagLast').textContent = 'DOMContentLoaded';
  }, { once: true });

  window.addEventListener('error', event => {
    if (event.target && (event.target.src || event.target.href)) return;
    window.offtecDiagnosticError(event.error || `${event.message} (${event.filename}:${event.lineno}:${event.colno})`);
  });
  window.addEventListener('unhandledrejection', event => {
    const reason = event.reason;
    window.offtecDiagnosticError(reason);
  });

  async function timedFetch(label, url, outputId, options = {}, timeout = 5000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    const begin = performance.now();
    $(outputId).textContent = 'Em andamento…';
    try {
      const response = await fetch(url, { ...options, signal: controller.signal });
      const body = await response.text();
      const result = { response, body, ms: Math.round(performance.now() - begin) };
      $(outputId).textContent = `HTTP ${response.status} · ${result.ms} ms`;
      return result;
    } catch (error) {
      const detail = error.name === 'AbortError'
        ? `${label}: timeout após ${timeout} ms`
        : `${label}: ${error.name}: ${error.message}\nOrigem: ${location.origin}\nDestino: ${url}`;
      $(outputId).textContent = detail;
      throw Error(detail);
    } finally { clearTimeout(timer); }
  }

  async function run() {
    if (running) return;
    running = true;
    $('diagnosticRun').disabled = true;
    $('diagHealth').dataset.done = '';
    $('diagBootstrap').textContent = 'Aguardando teste';
    $('diagDashboard').textContent = 'Aguardando teste';
    $('diagBootstrapData').textContent = 'Aguardando resposta';
    $('diagDashboardData').textContent = 'Aguardando resposta';
    $('diagModules').textContent = 'Aguardando dashboard';
    $('diagToken').textContent = 'NÃO confirmado';
    $('diagError').textContent = 'Nenhuma';
    $('diagLast').textContent = 'Teste iniciado';
    const base = location.hostname === 'appassets.androidplatform.net' ? 'http://127.0.0.1:8765' : location.origin;
    try {
      const health = await timedFetch('Health', `${base}/api/v1/health`, 'diagHealth');
      $('diagLast').textContent = 'Health respondeu';
      if (!health.response.ok) throw Error(`Health respondeu HTTP ${health.response.status}.`);
      const boot = await timedFetch('Bootstrap', `${base}/api/v1/bootstrap`, 'diagBootstrap', { headers: { Accept: 'application/json' } });
      $('diagLast').textContent = 'Bootstrap respondeu';
      if (!boot.response.ok) throw Error(`Bootstrap respondeu HTTP ${boot.response.status}.`);
      let data;
      try { data = JSON.parse(boot.body); } catch (e) { throw Error(`Bootstrap retornou JSON inválido: ${e.message}`); }
      $('diagBootstrapData').textContent = `JSON válido · chaves: ${Object.keys(data).join(', ') || '(nenhuma)'}`;
      appendFlow(`Bootstrap JSON recebido e analisado · chaves: ${Object.keys(data).join(', ') || '(nenhuma)'}`);
      const token = data.token || '';
      if (token) sessionStorage.setItem('hub-token', token);
      $('diagToken').textContent = token ? 'SIM (valor oculto)' : 'NÃO';
      if (!token) throw Error('Bootstrap concluído sem campo token.');
      const dashboard = await timedFetch('Dashboard', `${base}/api/v1/dashboard`, 'diagDashboard', { headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' } }, 8000);
      $('diagLast').textContent = 'Dashboard respondeu';
      if (!dashboard.response.ok) throw Error(`Dashboard respondeu HTTP ${dashboard.response.status}.`);
      let dashboardData;
      try { dashboardData = JSON.parse(dashboard.body); } catch (e) { throw Error(`Dashboard retornou JSON inválido: ${e.message}`); }
      const modules = Array.isArray(dashboardData.modules) ? dashboardData.modules : [];
      $('diagDashboardData').textContent = `JSON válido · chaves: ${Object.keys(dashboardData).join(', ') || '(nenhuma)'} · módulos=${modules.length} · module_count=${dashboardData.module_count ?? 'ausente'} · system=${dashboardData.system && typeof dashboardData.system === 'object' ? 'objeto' : typeof dashboardData.system} · history=${Array.isArray(dashboardData.history) ? dashboardData.history.length : 'formato inválido'}`;
      appendFlow(`Dashboard JSON recebido e analisado · ${modules.length} módulos`);
      $('diagModules').textContent = `${modules.length} recebidos pelo teste; renderização do app ainda não confirmada`;
      $('diagLast').textContent = `Dashboard JSON analisado · ${modules.length} módulos`;
    } catch (error) {
      $('diagError').textContent = error && (error.stack || error.message) ? String(error.stack || error.message) : String(error);
      $('diagLast').textContent = 'Falha: ' + (error.message || error);
      if ($('diagBootstrap').textContent === 'Aguardando teste') $('diagBootstrap').textContent = 'Não executado';
      if ($('diagDashboard').textContent === 'Aguardando teste') $('diagDashboard').textContent = 'Não executado';
    } finally {
      $('diagHealth').dataset.done = 'true';
      $('diagnosticRun').disabled = false;
      running = false;
    }
  }
})();
