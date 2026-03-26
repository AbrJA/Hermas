const state = {
  skills: [],
  selectedSkillIds: new Set(),
  availableModels: [],
  selectedModel: '',
  configBaseUrl: '',
  mcpServers: [],
  selectedMcpServerId: '',
  isSending: false,
  conversationSummaries: [],
  historyFilter: '',
  sessionToken: '',
  userId: 'anonymous',
  conversationId: '',
  requireAuth: false,
  activePanel: '',
  historyVisible: true,
  autoSkillRouting: true,
};

const el = {
  appShell: document.querySelector('.app-shell'),
  historyRail: document.getElementById('historyRail'),
  historyToggle: document.getElementById('historyToggle'),
  chatHeaderActions: document.querySelector('.chat-header-actions'),
  modelToggle: document.getElementById('modelToggle'),
  skillsToggle: document.getElementById('skillsToggle'),
  mcpToggle: document.getElementById('mcpToggle'),
  accessToggle: document.getElementById('accessToggle'),
  controlPopovers: document.querySelector('.control-popovers'),
  modelPanel: document.getElementById('modelPanel'),
  skillsPanel: document.getElementById('skillsPanel'),
  mcpPanel: document.getElementById('mcpPanel'),
  accessPanel: document.getElementById('accessPanel'),
  modelSummary: document.getElementById('modelSummary'),
  skillsSummary: document.getElementById('skillsSummary'),
  mcpSummary: document.getElementById('mcpSummary'),
  modelSelect: document.getElementById('modelSelect'),
  apiKey: document.getElementById('apiKey'),
  appToken: document.getElementById('appToken'),
  mcpSelect: document.getElementById('mcpSelect'),
  refreshMcpButton: document.getElementById('refreshMcpButton'),
  loadToolsButton: document.getElementById('loadToolsButton'),
  mcpToolsOutput: document.getElementById('mcpToolsOutput'),
  skillsContainer: document.getElementById('skillsContainer'),
  autoSkillRouting: document.getElementById('autoSkillRouting'),
  skillUpload: document.getElementById('skillUpload'),
  uploadSkillButton: document.getElementById('uploadSkillButton'),
  historySearch: document.getElementById('historySearch'),
  historyList: document.getElementById('historyList'),
  historyRefreshButton: document.getElementById('historyRefreshButton'),
  newChatButton: document.getElementById('newChatButton'),
  statusLine: document.getElementById('statusLine'),
  messages: document.getElementById('messages'),
  chatForm: document.getElementById('chatForm'),
  messageInput: document.getElementById('messageInput'),
  sendButton: document.getElementById('sendButton'),
  messageTemplate: document.getElementById('messageTemplate'),
  // MCP form elements
  mcpFormId: document.getElementById('mcpFormId'),
  mcpFormName: document.getElementById('mcpFormName'),
  mcpFormUrl: document.getElementById('mcpFormUrl'),
  mcpFormAuthName: document.getElementById('mcpFormAuthName'),
  mcpFormAuthValue: document.getElementById('mcpFormAuthValue'),
  saveMcpButton: document.getElementById('saveMcpButton'),
  deleteMcpButton: document.getElementById('deleteMcpButton'),
};

const conversation = [];
const DEFAULT_MODELS = ['gpt-4.1-mini', 'gpt-4.1', 'gpt-4o-mini', 'gpt-4o', 'o4-mini', 'o3'];

function setStatus(message) { el.statusLine.textContent = message; }

function formatTimestamp(raw) {
  if (!raw) return '';
  const normalized = `${raw}Z`;
  const d = new Date(normalized);
  if (Number.isNaN(d.getTime())) return raw;
  return d.toLocaleString();
}

function messageNode(role, content) {
  const fragment = el.messageTemplate.content.cloneNode(true);
  const row = fragment.querySelector('.message-row');
  const body = fragment.querySelector('.message-content');
  row.classList.add(role);
  body.textContent = content;
  return fragment;
}

function appendMessage(role, content) {
  const fragment = messageNode(role, content);
  const body = fragment.querySelector('.message-content');
  el.messages.appendChild(fragment);
  el.messages.scrollTop = el.messages.scrollHeight;
  return body;
}

function clearConversationView() {
  conversation.length = 0;
  el.messages.innerHTML = '';
}

function renderConversationMessages(messages) {
  clearConversationView();
  for (const item of messages) {
    if (!item || typeof item !== 'object') continue;
    const role = item.role === 'assistant' ? 'assistant' : 'user';
    const content = String(item.content || '');
    if (!content.trim()) continue;
    conversation.push({ role, content });
    appendMessage(role, content);
  }
}

function selectedSkillIds() { return Array.from(state.selectedSkillIds); }

function selectedMcpServer() {
  if (!state.selectedMcpServerId) return null;
  return state.mcpServers.find((s) => s.id === state.selectedMcpServerId) || null;
}

function selectedMcpServers() {
  const server = selectedMcpServer();
  return server ? [server] : [];
}

function updateSkillsSummary() {
  const count = state.selectedSkillIds.size;
  el.skillsSummary.textContent = state.autoSkillRouting ? 'Skills: LLM pick' : `Skills: ${count}`;
}

function updateModelSummary() { el.modelSummary.textContent = `Model: ${state.selectedModel || '-'}`; }

function updateMcpSummary() {
  const server = selectedMcpServer();
  el.mcpSummary.textContent = `MCP: ${server ? server.name || server.url : 'none'}`;
}

function setHistoryVisible(isVisible) {
  state.historyVisible = isVisible;
  el.appShell.classList.toggle('history-collapsed', !isVisible);
  el.historyToggle.setAttribute('aria-expanded', String(isVisible));
  el.historyToggle.textContent = isVisible ? 'Hide history' : 'Show';
}

function sortConversations(conversations) {
  return [...conversations].sort((a, b) => {
    const aTime = Date.parse(`${a.updatedAt || ''}Z`) || 0;
    const bTime = Date.parse(`${b.updatedAt || ''}Z`) || 0;
    return bTime - aTime;
  });
}

function filteredConversations() {
  const needle = state.historyFilter.trim().toLowerCase();
  if (!needle) return state.conversationSummaries;
  return state.conversationSummaries.filter((item) => {
    const title = String(item.title || '').toLowerCase();
    const model = String(item.model || '').toLowerCase();
    return title.includes(needle) || model.includes(needle);
  });
}

function renderConversationHistory() {
  const items = filteredConversations();
  el.historyList.innerHTML = '';
  if (!items.length) {
    el.historyList.innerHTML = '<p class="history-empty">No conversations yet.</p>';
    return;
  }
  for (const conv of items) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `history-item${conv.id === state.conversationId ? ' active' : ''}`;
    button.dataset.conversationId = conv.id;
    button.innerHTML = `<span class="history-title">${conv.title || 'Conversation'}</span><span class="history-meta">${conv.model || ''} ${formatTimestamp(conv.updatedAt)}</span>`;
    button.addEventListener('click', () => loadConversationById(conv.id));
    el.historyList.appendChild(button);
  }
}

function togglePanel(panelName) {
  const entries = [
    { name: 'model', toggle: el.modelToggle, panel: el.modelPanel },
    { name: 'skills', toggle: el.skillsToggle, panel: el.skillsPanel },
    { name: 'mcp', toggle: el.mcpToggle, panel: el.mcpPanel },
    { name: 'access', toggle: el.accessToggle, panel: el.accessPanel },
  ];
  const next = state.activePanel === panelName ? '' : panelName;
  state.activePanel = next;
  for (const entry of entries) {
    const shouldOpen = entry.name === next;
    entry.panel.hidden = !shouldOpen;
    entry.toggle.setAttribute('aria-expanded', String(shouldOpen));
  }
}

function closePanels() {
  state.activePanel = '';
  for (const entry of [
    { toggle: el.modelToggle, panel: el.modelPanel },
    { toggle: el.skillsToggle, panel: el.skillsPanel },
    { toggle: el.mcpToggle, panel: el.mcpPanel },
    { toggle: el.accessToggle, panel: el.accessPanel },
  ]) {
    entry.panel.hidden = true;
    entry.toggle.setAttribute('aria-expanded', 'false');
  }
}

function registerToggleHandlers() {
  el.historyToggle.addEventListener('click', () => setHistoryVisible(!state.historyVisible));
  el.modelToggle.addEventListener('click', () => togglePanel('model'));
  el.skillsToggle.addEventListener('click', () => togglePanel('skills'));
  el.mcpToggle.addEventListener('click', () => togglePanel('mcp'));
  el.accessToggle.addEventListener('click', () => togglePanel('access'));

  document.addEventListener('click', (event) => {
    const target = event.target;
    if (!(target instanceof Node)) return;
    if (el.chatHeaderActions?.contains(target)) return;
    if (el.controlPopovers?.contains(target)) return;
    if (el.chatForm?.contains(target)) return;
    closePanels();
  });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape') closePanels(); });
}

function setSending(isSending) { state.isSending = isSending; el.sendButton.disabled = isSending; }

function renderSkills(skills) {
  state.skills = skills;
  state.selectedSkillIds = new Set(skills.map((s) => s.id));
  el.skillsContainer.innerHTML = '';
  if (!skills.length) {
    el.skillsContainer.innerHTML = '<p class="hint">No skills available</p>';
    updateSkillsSummary();
    return;
  }
  skills.forEach((skill) => {
    const item = document.createElement('div');
    item.className = 'skill-item';

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.checked = true;
    checkbox.id = `skill-${String(skill.id).replace(/[^a-z0-9_-]/gi, '-')}`;
    checkbox.addEventListener('change', () => {
      if (checkbox.checked) state.selectedSkillIds.add(skill.id);
      else state.selectedSkillIds.delete(skill.id);
      updateSkillsSummary();
    });

    const label = document.createElement('label');
    label.htmlFor = checkbox.id;
    label.innerHTML = `<span class="skill-name">${skill.name}</span><span class="skill-description">${skill.description}</span>`;

    const deleteBtn = document.createElement('button');
    deleteBtn.type = 'button';
    deleteBtn.className = 'secondary-btn danger-btn skill-delete-btn';
    deleteBtn.textContent = 'Del';
    deleteBtn.addEventListener('click', async () => {
      if (!confirm(`Delete skill "${skill.name}"?`)) return;
      try {
        const resp = await fetch(`/api/skills/${encodeURIComponent(skill.id)}`, {
          method: 'DELETE',
          headers: { 'X-Session-Token': state.sessionToken, 'X-User-Id': state.userId },
        });
        if (resp.ok) { await loadSkills(); setStatus('Skill deleted.'); }
        else { const d = await resp.json(); setStatus(`Delete failed: ${d.detail || d.error}`); }
      } catch (e) { setStatus(`Delete error: ${e.message}`); }
    });

    item.append(checkbox, label, deleteBtn);
    el.skillsContainer.appendChild(item);
  });
  updateSkillsSummary();
}

function renderModelSelect(defaultModel) {
  const uniqueModels = new Set(DEFAULT_MODELS);
  if (defaultModel) uniqueModels.add(defaultModel);
  state.availableModels = Array.from(uniqueModels);
  el.modelSelect.innerHTML = '';
  state.availableModels.forEach((modelName) => {
    const option = document.createElement('option');
    option.value = modelName;
    option.textContent = modelName;
    el.modelSelect.appendChild(option);
  });
  state.selectedModel = defaultModel || state.availableModels[0] || '';
  el.modelSelect.value = state.selectedModel;
  updateModelSummary();
}

function renderMcpServers(servers) {
  state.mcpServers = servers.filter((s) => s && s.enabled !== false && s.url);
  el.mcpSelect.innerHTML = '';
  const noneOption = document.createElement('option');
  noneOption.value = '';
  noneOption.textContent = 'None';
  el.mcpSelect.appendChild(noneOption);
  for (const server of state.mcpServers) {
    const option = document.createElement('option');
    option.value = server.id || '';
    option.textContent = server.name || server.url;
    el.mcpSelect.appendChild(option);
  }
  if (state.selectedMcpServerId && state.mcpServers.some((s) => s.id === state.selectedMcpServerId)) {
    el.mcpSelect.value = state.selectedMcpServerId;
  } else {
    state.selectedMcpServerId = state.mcpServers[0]?.id || '';
    el.mcpSelect.value = state.selectedMcpServerId;
  }
  updateMcpSummary();
}

/* --- API calls --- */

async function loadConfig() {
  const response = await fetch('/api/config');
  if (!response.ok) throw new Error('Could not load config');
  const data = await response.json();
  state.configBaseUrl = data.baseUrl || 'https://api.openai.com';
  renderModelSelect(data.defaultModel || 'gpt-4.1-mini');
  if (data.hasBackendApiKey) el.apiKey.placeholder = 'Backend key available (optional override)';
  state.requireAuth = !!data.requireAuth;
}

async function createSession() {
  const headers = { 'Content-Type': 'application/json' };
  const appToken = (el.appToken?.value || '').trim();
  if (appToken) headers['X-App-Token'] = appToken;
  const response = await fetch('/api/session', { method: 'POST', headers, body: JSON.stringify({ userId: state.userId }) });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || data.error || 'Failed to create session');
  state.sessionToken = data.sessionToken || '';
  state.userId = data.userId || state.userId;
}

async function loadSkills() {
  const response = await fetch('/api/skills');
  if (!response.ok) throw new Error('Could not load skills');
  const data = await response.json();
  renderSkills(data.skills || []);
}

async function loadMcpServers() {
  const response = await fetch('/api/mcp/servers', { headers: { 'X-Session-Token': state.sessionToken, 'X-User-Id': state.userId } });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || data.error || 'Could not load MCP servers');
  renderMcpServers(data.servers || []);
}

async function loadConversationHistory() {
  const response = await fetch('/api/conversations/list', { headers: { 'X-Session-Token': state.sessionToken, 'X-User-Id': state.userId } });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || data.error || 'Could not load conversation history');
  state.conversationSummaries = sortConversations(data.conversations || []);
  renderConversationHistory();
}

async function loadConversationById(conversationId) {
  if (!conversationId) return;
  setStatus('Loading conversation...');
  const response = await fetch(`/api/conversations/load?id=${encodeURIComponent(conversationId)}`, { headers: { 'X-Session-Token': state.sessionToken, 'X-User-Id': state.userId } });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || data.error || 'Could not load conversation');
  const conv = data.conversation || {};
  state.conversationId = conv.id || conversationId;
  renderConversationMessages(Array.isArray(conv.messages) ? conv.messages : []);
  renderConversationHistory();
  setStatus('Conversation loaded.');
}

function startNewConversation() {
  state.conversationId = '';
  clearConversationView();
  renderConversationHistory();
  setStatus('New conversation started.');
  el.messageInput.focus();
}

async function handleLoadTools() {
  const server = selectedMcpServer();
  if (!server) { el.mcpToolsOutput.textContent = 'Select an MCP server first.'; return; }
  setStatus('Loading MCP tools...');
  el.mcpToolsOutput.textContent = '';
  try {
    const response = await fetch('/api/mcp/tools', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Session-Token': state.sessionToken, 'X-User-Id': state.userId },
      body: JSON.stringify({ server }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || data.error || 'Failed to load tools');
    el.mcpToolsOutput.textContent = JSON.stringify(data.tools, null, 2);
    setStatus('MCP tools loaded.');
  } catch (error) {
    el.mcpToolsOutput.textContent = String(error.message || error);
    setStatus('Failed to load MCP tools.');
  }
}

async function handleUploadSkill() {
  const file = el.skillUpload?.files?.[0];
  if (!file) { setStatus('Select a .md file first.'); return; }
  const formData = new FormData();
  formData.append('file', file);
  try {
    setStatus('Uploading skill...');
    const response = await fetch('/api/skills/upload', {
      method: 'POST',
      headers: { 'X-Session-Token': state.sessionToken, 'X-User-Id': state.userId },
      body: formData,
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || data.error || 'Upload failed');
    await loadSkills();
    el.skillUpload.value = '';
    setStatus(`Skill "${data.skill?.name || 'uploaded'}" added.`);
  } catch (error) {
    setStatus(`Upload error: ${error.message}`);
  }
}

async function handleSaveMcpServer() {
  const payload = {
    id: el.mcpFormId.value.trim(),
    name: el.mcpFormName.value.trim() || 'MCP Server',
    url: el.mcpFormUrl.value.trim(),
    authHeaderName: el.mcpFormAuthName.value.trim(),
    authHeaderValue: el.mcpFormAuthValue.value.trim(),
    enabled: true,
  };
  if (!payload.url) { setStatus('MCP server URL is required.'); return; }
  try {
    setStatus('Saving MCP server...');
    const response = await fetch('/api/mcp/servers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Session-Token': state.sessionToken, 'X-User-Id': state.userId },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || data.error || 'Save failed');
    await loadMcpServers();
    el.mcpFormId.value = '';
    el.mcpFormName.value = '';
    el.mcpFormUrl.value = '';
    el.mcpFormAuthName.value = '';
    el.mcpFormAuthValue.value = '';
    setStatus(`MCP server "${data.server?.name}" saved.`);
  } catch (error) {
    setStatus(`Save error: ${error.message}`);
  }
}

async function handleDeleteMcpServer() {
  const server = selectedMcpServer();
  if (!server) { setStatus('Select an MCP server to delete.'); return; }
  if (!confirm(`Delete MCP server "${server.name}"?`)) return;
  try {
    setStatus('Deleting MCP server...');
    const response = await fetch(`/api/mcp/servers/${encodeURIComponent(server.id)}`, {
      method: 'DELETE',
      headers: { 'X-Session-Token': state.sessionToken, 'X-User-Id': state.userId },
    });
    if (!response.ok) { const d = await response.json(); throw new Error(d.detail || d.error || 'Delete failed'); }
    await loadMcpServers();
    setStatus('MCP server deleted.');
  } catch (error) {
    setStatus(`Delete error: ${error.message}`);
  }
}

async function handleSend(event) {
  event.preventDefault();
  const text = el.messageInput.value.trim();
  if (!text || state.isSending) return;

  appendMessage('user', text);
  conversation.push({ role: 'user', content: text });
  el.messageInput.value = '';
  setSending(true);
  setStatus('Generating response...');

  try {
    const assistantBody = appendMessage('assistant', '');
    let appliedSkillIds = [];
    const payload = {
      messages: conversation,
      conversationId: state.conversationId,
      model: state.selectedModel,
      baseUrl: state.configBaseUrl,
      apiKey: el.apiKey.value.trim(),
      selectedSkillIds: selectedSkillIds(),
      autoSkillRouting: state.autoSkillRouting,
      maxAutoSkills: 1,
      mcpServers: selectedMcpServers(),
    };

    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Session-Token': state.sessionToken, 'X-User-Id': state.userId },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.detail || data.error || 'Chat request failed');
    }

    const streamText = await response.text();
    const lines = streamText.split('\n');
    let latestEvent = '';
    let answer = '';
    const toolSteps = [];

    for (const line of lines) {
      if (line.startsWith('event: ')) { latestEvent = line.slice(7).trim(); continue; }
      if (!line.startsWith('data: ')) continue;
      const dataLine = line.slice(6).trim();
      if (!dataLine) continue;
      let parsed;
      try { parsed = JSON.parse(dataLine); } catch { continue; }

      if (latestEvent === 'start') {
        state.conversationId = parsed.conversationId || state.conversationId;
        appliedSkillIds = Array.isArray(parsed.appliedSkillIds) ? parsed.appliedSkillIds : appliedSkillIds;
        continue;
      }
      if (latestEvent === 'tool_start') {
        const step = `Calling tool: ${parsed.tool}`;
        toolSteps.push(step);
        assistantBody.innerHTML = '';
        const indicator = document.createElement('div');
        indicator.className = 'tool-progress';
        for (const s of toolSteps) {
          const ln = document.createElement('div');
          ln.className = 'tool-progress-step';
          ln.textContent = s === step ? `\u23F3 ${s}...` : `\u2713 ${s}`;
          indicator.appendChild(ln);
        }
        assistantBody.appendChild(indicator);
        el.messages.scrollTop = el.messages.scrollHeight;
        setStatus(`Running tool: ${parsed.tool}...`);
        continue;
      }
      if (latestEvent === 'tool_done') {
        const last = toolSteps.length - 1;
        if (last >= 0) toolSteps[last] = `${parsed.tool} completed`;
        assistantBody.innerHTML = '';
        const indicator = document.createElement('div');
        indicator.className = 'tool-progress';
        for (const s of toolSteps) {
          const ln = document.createElement('div');
          ln.className = 'tool-progress-step completed';
          ln.textContent = `\u2713 ${s}`;
          indicator.appendChild(ln);
        }
        assistantBody.appendChild(indicator);
        el.messages.scrollTop = el.messages.scrollHeight;
        setStatus('Analyzing results...');
        continue;
      }
      if (latestEvent === 'token') {
        answer += parsed.delta || '';
        assistantBody.textContent = answer;
        el.messages.scrollTop = el.messages.scrollHeight;
        continue;
      }
      if (latestEvent === 'done') {
        state.conversationId = parsed.conversationId || state.conversationId;
        appliedSkillIds = Array.isArray(parsed.appliedSkillIds) ? parsed.appliedSkillIds : appliedSkillIds;
        if (!answer) { answer = parsed.content || answer; assistantBody.textContent = answer; }
      }
    }

    const finalAnswer = answer || assistantBody.textContent || '(Empty response)';
    assistantBody.textContent = finalAnswer;
    conversation.push({ role: 'assistant', content: finalAnswer });
    await loadConversationHistory();
    const skillSuffix = appliedSkillIds.length ? ` Skills used: ${appliedSkillIds.join(', ')}` : state.autoSkillRouting ? ' No skill matched' : '';
    setStatus(`Response ready.${skillSuffix}`);
  } catch (error) {
    const message = `Error: ${String(error.message || error)}`;
    appendMessage('assistant', message);
    setStatus('Request failed.');
  } finally {
    setSending(false);
  }
}

async function bootstrap() {
  setStatus('Loading...');
  registerToggleHandlers();
  setHistoryVisible(true);
  closePanels();

  el.modelSelect.addEventListener('change', () => { state.selectedModel = el.modelSelect.value; updateModelSummary(); });
  el.mcpSelect.addEventListener('change', () => {
    state.selectedMcpServerId = el.mcpSelect.value;
    updateMcpSummary();
    // Populate form with selected server
    const server = selectedMcpServer();
    if (server) {
      el.mcpFormId.value = server.id || '';
      el.mcpFormName.value = server.name || '';
      el.mcpFormUrl.value = server.url || '';
      el.mcpFormAuthName.value = server.authHeaderName || '';
      el.mcpFormAuthValue.value = server.authHeaderValue || '';
    }
  });

  el.autoSkillRouting?.addEventListener('change', () => { state.autoSkillRouting = !!el.autoSkillRouting.checked; updateSkillsSummary(); });
  if (el.autoSkillRouting) { el.autoSkillRouting.checked = true; state.autoSkillRouting = true; }

  try {
    await Promise.all([loadConfig(), loadSkills()]);
    await createSession();
    const startupResults = await Promise.allSettled([loadConversationHistory(), loadMcpServers()]);
    if (startupResults[0].status === 'rejected') throw startupResults[0].reason;
    if (startupResults[1].status === 'rejected') {
      appendMessage('assistant', `MCP startup warning: ${String(startupResults[1].reason?.message || startupResults[1].reason)}`);
      setStatus('Ready (MCP unavailable)');
    } else {
      setStatus('Ready');
    }
  } catch (error) {
    setStatus('Initialization failed');
    appendMessage('assistant', `Startup error: ${String(error.message || error)}`);
  }

  el.refreshMcpButton.addEventListener('click', async () => { try { setStatus('Refreshing MCP list...'); await loadMcpServers(); setStatus('MCP list updated.'); } catch (e) { setStatus('Failed to refresh MCP list.'); } });
  el.historyRefreshButton.addEventListener('click', async () => { try { setStatus('Refreshing conversations...'); await loadConversationHistory(); setStatus('History updated.'); } catch (e) { setStatus('Failed to refresh history.'); } });
  el.newChatButton.addEventListener('click', startNewConversation);
  el.historySearch.addEventListener('input', () => { state.historyFilter = el.historySearch.value || ''; renderConversationHistory(); });

  el.messageInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); if (!state.isSending) el.chatForm.requestSubmit(); }
  });
  el.messageInput.addEventListener('input', () => { el.messageInput.style.height = 'auto'; el.messageInput.style.height = Math.min(el.messageInput.scrollHeight, 160) + 'px'; });
  el.messageInput.style.height = 'auto';
  el.messageInput.style.height = Math.min(el.messageInput.scrollHeight, 160) + 'px';

  el.loadToolsButton.addEventListener('click', handleLoadTools);
  el.uploadSkillButton?.addEventListener('click', handleUploadSkill);
  el.saveMcpButton?.addEventListener('click', handleSaveMcpServer);
  el.deleteMcpButton?.addEventListener('click', handleDeleteMcpServer);
  el.chatForm.addEventListener('submit', handleSend);
}

bootstrap();
