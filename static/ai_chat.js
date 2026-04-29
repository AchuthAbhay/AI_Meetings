(function () {
  const root = document.getElementById('ai-chat-root');
  if (!root) return;

  const config = {
    endpoint: '/api/chat/query',
    transcriptEndpoints: [
      '/api/transcripts/list',
      '/api/transcripts',
      '/api/recent-transcripts?limit=20'
    ],
    maxChars: 500,
    topK: 5,
    prompts: [
      'Show action items',
      'What decisions were made?',
      'Speaker-level summary',
      'What risks or blockers came up?'
    ]
  };

  const state = {
    selectedTranscriptId: null,
    messages: [
      {
        role: 'assistant',
        text: 'Ask about recent meetings, action items, decisions, or sentiment patterns across your transcript history.'
      }
    ],
    isTyping: false,
    transcripts: []
  };

  root.innerHTML = `
    <div class="ai-chat-shell">
      <aside class="ai-sidebar">
        <div class="ai-surface ai-sidebar-panel">
          <div class="ai-section-label">SEARCH:</div>
          <div class="ai-select-wrap">
            <select class="ai-scope-select" id="ai-scope-select">
              <option value="all">All transcripts</option>
            </select>
            <i class="fas fa-chevron-down ai-select-icon" aria-hidden="true"></i>
          </div>
          <div class="ai-sidebar-copy">
            Choose a single transcript for focused answers, or stay on all transcripts for broader retrieval.
          </div>
        </div>

        <div class="ai-surface ai-transcript-panel">
          <div class="ai-sidebar-header">
            <div>
              <div class="ai-sidebar-title">Recent transcripts</div>
              <div class="ai-sidebar-subtitle" id="ai-transcript-count">Loading history...</div>
            </div>
          </div>
          <div class="ai-transcript-list" id="ai-transcript-list"></div>
        </div>
      </aside>

      <section class="ai-chat-stage">
        <div class="ai-surface ai-chat-card">
          <div class="ai-chat-topbar">
            <div class="ai-chat-header-left">
              <div class="ai-chat-avatar">AI</div>
              <div>
                <div class="ai-chat-title">AI Analyst</div>
                <div class="ai-chat-subtitle">
                  <span class="ai-status-dot"></span>
                  Transcript Q&A with retrieval context
                </div>
              </div>
            </div>
            <div class="ai-active-scope" id="ai-active-scope">All transcripts</div>
          </div>

          <div class="ai-messages" id="ai-messages"></div>

          <div class="ai-prompts" id="ai-prompts">
            ${config.prompts.map(prompt => `<button class="ai-prompt-chip" type="button">${escapeHtml(prompt)}</button>`).join('')}
          </div>

          <div class="ai-input-area">
            <div class="ai-input-row">
              <textarea
                id="ai-input"
                class="ai-textarea"
                placeholder="Ask about your transcripts..."
                rows="1"
              ></textarea>
              <button class="ai-send-btn" id="ai-send" type="button" aria-label="Send">
                <i class="fas fa-paper-plane" aria-hidden="true"></i>
              </button>
            </div>
            <div class="ai-input-footer">
              <span class="ai-powered-by">Groq / Qdrant / LangChain</span>
              <span class="ai-char-count" id="ai-char-count">0/${config.maxChars}</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  `;

  const elements = {
    select: document.getElementById('ai-scope-select'),
    transcriptList: document.getElementById('ai-transcript-list'),
    transcriptCount: document.getElementById('ai-transcript-count'),
    activeScope: document.getElementById('ai-active-scope'),
    messages: document.getElementById('ai-messages'),
    prompts: document.getElementById('ai-prompts'),
    input: document.getElementById('ai-input'),
    send: document.getElementById('ai-send'),
    charCount: document.getElementById('ai-char-count')
  };

  elements.select.addEventListener('change', () => {
    const value = elements.select.value;
    syncTranscriptId(value === 'all' ? null : Number(value));
  });

  elements.input.addEventListener('input', () => autoResize(elements.input));
  elements.input.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      aiSendMessage();
    }
  });

  elements.send.addEventListener('click', () => aiSendMessage());

  elements.prompts.querySelectorAll('.ai-prompt-chip').forEach(button => {
    button.addEventListener('click', () => aiSendMessage(button.textContent.trim()));
  });

  window.aiChat = {
    syncTranscriptId
  };

  initialize();

  async function initialize() {
    renderMessages();
    autoResize(elements.input);

    const preferredId = getPreferredTranscriptId();
    if (preferredId !== null) {
      state.selectedTranscriptId = preferredId;
    }

    await loadTranscripts();
    renderTranscriptList();
    updateScopeLabel();
  }

  async function loadTranscripts() {
    for (const endpoint of config.transcriptEndpoints) {
      try {
        const response = await fetch(endpoint);
        if (!response.ok) continue;

        const payload = await response.json();
        const transcripts = normalizeTranscriptPayload(payload);
        if (!transcripts.length) continue;

        state.transcripts = transcripts;
        populateSelect(transcripts);

        if (state.selectedTranscriptId !== null) {
          syncTranscriptId(state.selectedTranscriptId, { persist: false });
        } else {
          elements.select.value = 'all';
        }

        elements.transcriptCount.textContent = `${transcripts.length} transcript${transcripts.length === 1 ? '' : 's'}`;
        return;
      } catch (error) {
        continue;
      }
    }

    state.transcripts = [];
    elements.transcriptCount.textContent = 'No transcripts found';
    populateSelect([]);
  }

  function normalizeTranscriptPayload(payload) {
    let items = [];

    if (Array.isArray(payload)) {
      items = payload;
    } else if (Array.isArray(payload?.transcripts)) {
      items = payload.transcripts;
    } else if (Array.isArray(payload?.data)) {
      items = payload.data;
    }

    return items
      .map(item => ({
        id: Number(item.id),
        title: item.title || item.name || item.filename || `Transcript ${item.id}`,
        subtitle: item.created_at_formatted || item.language_name || item.created_at || '',
        preview: item.text || item.summary || ''
      }))
      .filter(item => Number.isFinite(item.id));
  }

  function populateSelect(transcripts) {
    elements.select.innerHTML = '<option value="all">All transcripts</option>';

    transcripts.forEach(transcript => {
      const option = document.createElement('option');
      option.value = String(transcript.id);
      option.textContent = transcript.title;
      elements.select.appendChild(option);
    });
  }

  function renderTranscriptList() {
    if (!state.transcripts.length) {
      elements.transcriptList.innerHTML = `
        <div class="ai-empty-state">
          <i class="fas fa-file-audio"></i>
          <p>No transcripts are available yet.</p>
        </div>
      `;
      return;
    }

    elements.transcriptList.innerHTML = state.transcripts.map(transcript => {
      const activeClass = transcript.id === state.selectedTranscriptId ? ' active' : '';
      const preview = transcript.preview ? escapeHtml(trimText(transcript.preview, 120)) : 'Use this transcript as the active retrieval scope.';
      return `
        <button class="ai-transcript-item${activeClass}" type="button" data-id="${transcript.id}">
          <div class="ai-transcript-item-top">
            <span class="ai-transcript-title">${escapeHtml(transcript.title)}</span>
            <span class="ai-transcript-badge">${transcript.id === state.selectedTranscriptId ? 'Active' : 'Scope'}</span>
          </div>
          <div class="ai-transcript-meta">${escapeHtml(transcript.subtitle || `Transcript #${transcript.id}`)}</div>
          <div class="ai-transcript-preview">${preview}</div>
        </button>
      `;
    }).join('');

    elements.transcriptList.querySelectorAll('.ai-transcript-item').forEach(button => {
      button.addEventListener('click', () => {
        syncTranscriptId(Number(button.dataset.id));
      });
    });
  }

  function renderMessages() {
    const html = state.messages.map(message => {
      const roleClass = message.role === 'user' ? 'user' : 'assistant';
      return `
        <div class="ai-msg ${roleClass}">
          <div class="ai-msg-avatar">${message.role === 'user' ? '<i class="fas fa-user"></i>' : '<i class="fas fa-brain"></i>'}</div>
          <div class="ai-msg-body">
            <div class="ai-msg-bubble">${escapeHtml(message.text)}</div>
            ${renderSources(message.sources)}
          </div>
        </div>
      `;
    }).join('');

    const typingHtml = state.isTyping ? `
      <div class="ai-msg assistant">
        <div class="ai-msg-avatar"><i class="fas fa-brain"></i></div>
        <div class="ai-msg-body">
          <div class="ai-msg-bubble">
            <div class="ai-typing-dots"><span></span><span></span><span></span></div>
          </div>
        </div>
      </div>
    ` : '';

    elements.messages.innerHTML = html + typingHtml;
    elements.messages.scrollTop = elements.messages.scrollHeight;
  }

  function renderSources(sources) {
    if (!Array.isArray(sources) || !sources.length) return '';

    const chips = sources.map(source => {
      const label = typeof source === 'string' ? source : formatSourceLabel(source);
      return `<span class="ai-source-chip">${escapeHtml(label)}</span>`;
    }).join('');

    return `<div class="ai-source-chips">${chips}</div>`;
  }

  function formatSourceLabel(source) {
    const parts = [];

    if (source.title) parts.push(source.title);
    if (source.source_kind === 'summary') parts.push('Summary');
    if (source.speaker) parts.push(source.speaker);
    if (source.transcript_id && !source.title) parts.push(`Transcript ${source.transcript_id}`);

    return parts.join(' • ') || 'Transcript source';
  }

  async function aiSendMessage(textFromPromptOptional) {
    if (state.isTyping) return;

    const text = (textFromPromptOptional || elements.input.value).trim();
    if (!text) return;

    state.messages.push({ role: 'user', text });
    state.isTyping = true;
    renderMessages();

    elements.input.value = '';
    autoResize(elements.input);
    elements.send.disabled = true;

    const transcriptId = state.selectedTranscriptId;

    try {
      const response = await fetch(config.endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: text,
          transcript_id: transcriptId,
          scope: transcriptId === null ? 'all' : 'current',
          top_k: config.topK
        })
      });

      const data = await response.json();
      const answer = data?.answer || 'I could not find enough relevant transcript context to answer that yet.';
      state.messages.push({
        role: 'assistant',
        text: answer,
        sources: Array.isArray(data?.sources) ? data.sources : []
      });
    } catch (error) {
      state.messages.push({
        role: 'assistant',
        text: 'I could not reach the transcript chat service just now. Please try again.'
      });
    } finally {
      state.isTyping = false;
      elements.send.disabled = false;
      renderMessages();
      elements.input.focus();
    }
  }

  function syncTranscriptId(id, options = {}) {
    const { persist = true } = options;
    const normalizedId = id === null || id === undefined || Number.isNaN(Number(id)) ? null : Number(id);

    state.selectedTranscriptId = normalizedId;
    elements.select.value = normalizedId === null ? 'all' : String(normalizedId);

    if (persist) {
      if (normalizedId === null) {
        window.currentTranscriptId = null;
        localStorage.removeItem('currentTranscriptId');
      } else {
        window.currentTranscriptId = normalizedId;
        localStorage.setItem('currentTranscriptId', String(normalizedId));
      }
    }

    renderTranscriptList();
    updateScopeLabel();
  }

  function updateScopeLabel() {
    if (state.selectedTranscriptId === null) {
      elements.activeScope.textContent = 'All transcripts';
      return;
    }

    const selectedTranscript = state.transcripts.find(item => item.id === state.selectedTranscriptId);
    elements.activeScope.textContent = selectedTranscript ? selectedTranscript.title : `Transcript ${state.selectedTranscriptId}`;
  }

  function getPreferredTranscriptId() {
    const rawValue = window.currentTranscriptId ?? localStorage.getItem('currentTranscriptId');
    if (rawValue === null || rawValue === undefined || rawValue === '') return null;

    const parsed = Number(rawValue);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function autoResize(textarea) {
    const nextValue = textarea.value.slice(0, config.maxChars);
    if (nextValue !== textarea.value) {
      textarea.value = nextValue;
    }

    textarea.style.height = 'auto';
    const maxHeight = 144;
    const nextHeight = Math.min(textarea.scrollHeight, maxHeight);
    textarea.style.height = `${nextHeight}px`;
    textarea.style.overflowY = textarea.scrollHeight > maxHeight ? 'auto' : 'hidden';
    elements.charCount.textContent = `${textarea.value.length}/${config.maxChars}`;
  }

  function trimText(text, maxLength) {
    return text.length > maxLength ? `${text.slice(0, maxLength - 1)}…` : text;
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }
})();
