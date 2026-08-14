const $ = selector => document.querySelector(selector);
const $$ = selector => document.querySelectorAll(selector);

let lastAnswerSpeech = '';
let speakNextAnswer = false;

async function api(path, options = {}) {
  const response = await fetch(path, options);
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error(`Resposta inválida (${response.status}).`);
  }
  if (!response.ok) {
    const detail = Array.isArray(data.detail)
      ? data.detail.map(item => item.msg).join('; ')
      : data.detail;
    throw new Error(data.erro || detail || `Erro ${response.status}`);
  }
  return data;
}

function showTab(id) {
  $$('.panel,.tabs button').forEach(element => element.classList.remove('active'));
  $(`#${id}`).classList.add('active');
  const tab = $(`[data-tab="${id}"]`);
  if (tab) tab.classList.add('active');
  if (id === 'acervo') loadDocuments();
}

$$('[data-tab]').forEach(button => {
  button.onclick = () => showTab(button.dataset.tab);
});

async function health() {
  try {
    const result = await api('/health');
    $('#status').textContent = `Online · ${result.documents} fonte(s)`;
    $('#status').classList.add('ok');
  } catch {
    $('#status').textContent = 'Offline';
  }
}

async function loadDocuments() {
  const box = $('#documents');
  box.innerHTML = '<p>Carregando…</p>';
  try {
    const documents = await api('/documents');
    box.innerHTML = documents.length ? documents.map(document => `
      <article class="document">
        ${imageMarkup(document.image_url, document.image_description || `Imagem da fonte ${document.title}`, 'document-image')}
        <span class="level">NÍVEL ${document.source_level}</span>
        <h3>${escapeHtml(document.title)}</h3>
        <p class="meta">${escapeHtml(document.author)}${document.year ? ` · ${document.year}` : ''} · Autenticidade: ${escapeHtml(document.authenticity_status)}</p>
        ${document.origin ? `<p class="meta"><b>Origem:</b> ${escapeHtml(document.origin)}</p>` : ''}
        ${document.provenance_note ? `<p class="provenance"><b>Observação de procedência:</b> ${escapeHtml(document.provenance_note)}</p>` : ''}
        <p>${escapeHtml(document.content.slice(0, 280))}${document.content.length > 280 ? '…' : ''}</p>
        <div class="document-actions"><button onclick="editDocument('${document.id}')">Editar metadados</button><button onclick="viewHistory('${document.id}')">Ver histórico</button></div>
      </article>`).join('') : '<div class="empty">O acervo ainda não possui documentos.</div>';
  } catch (error) {
    box.innerHTML = `<p>${escapeHtml(error.message)}</p>`;
  }
}

window.editDocument = async id => {
  try {
    const document = await api(`/documents/${id}`);
    const form = $('#edit-form');
    ['id', 'title', 'author', 'source_level', 'year', 'edition', 'origin',
      'provenance_note', 'authenticity_status', 'rights_status', 'image_url',
      'image_description'].forEach(key => {
      form.elements[key].value = document[key] ?? '';
    });
    form.elements.responsible.value = '';
    form.elements.justification.value = '';
    $('#edit-message').textContent = '';
    await loadHistory(id);
    showTab('editar');
  } catch (error) {
    alert(error.message);
  }
};

window.viewHistory = async id => editDocument(id);

async function loadHistory(id) {
  const box = $('#history');
  try {
    const rows = await api(`/documents/${id}/history`);
    box.innerHTML = rows.length ? rows.map(row => `
      <article class="history-item"><b>${label(row.field)}</b>: “${escapeHtml(value(row.old_value))}” → “${escapeHtml(value(row.new_value))}”
      <p class="meta">${escapeHtml(row.responsible)} · ${escapeHtml(row.changed_at)}</p><p>${escapeHtml(row.justification)}</p></article>`).join('') : '<div class="empty">Nenhuma alteração registrada.</div>';
  } catch (error) {
    box.innerHTML = `<p>${escapeHtml(error.message)}</p>`;
  }
}

$('#edit-form').onsubmit = async event => {
  event.preventDefault();
  const form = event.target;
  const id = form.elements.id.value;
  const keys = ['title', 'author', 'source_level', 'year', 'edition', 'origin',
    'provenance_note', 'authenticity_status', 'rights_status', 'image_url',
    'image_description'];
  const changes = {};
  keys.forEach(key => { changes[key] = form.elements[key].value || null; });
  if (changes.year) changes.year = Number(changes.year);
  const payload = {
    changes,
    responsible: form.elements.responsible.value,
    justification: form.elements.justification.value,
  };
  const message = $('#edit-message');
  message.textContent = 'Salvando…';
  try {
    await api(`/documents/${id}`, {
      method: 'PUT', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
    message.textContent = 'Alteração salva e registrada no histórico.';
    await loadHistory(id);
  } catch (error) {
    message.textContent = error.message;
  }
};

$('#cancel-edit').onclick = () => showTab('acervo');

$('#ask-form').onsubmit = async event => {
  event.preventDefault();
  const box = $('#answer');
  box.classList.remove('hidden');
  box.innerHTML = '<p>Pesquisando…</p>';
  try {
    const answer = await api('/ask', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({question: $('#question').value}),
    });
    const sourcesSpeech = answer.citations.map(citation =>
      `Fonte: ${citation.title}${citation.page ? `, página ${citation.page}` : ''}.`
    ).join(' ');
    lastAnswerSpeech = `${answer.answer} ${sourcesSpeech}`.trim();
    box.innerHTML = `
      <h3>${answer.grounded ? 'Resposta fundamentada' : 'Fontes insuficientes'}</h3>
      <button class="voice-button listen-answer" type="button" onclick="speakLastAnswer()" aria-label="Ouvir a resposta">🔊 Ouvir resposta</button>
      <p class="generated-answer">${escapeHtml(answer.answer)}</p>
      ${answer.citations.map(citation => `
        <blockquote>
          ${imageMarkup(citation.image_url, citation.image_description || `Imagem da fonte ${citation.title}`, 'citation-image')}
          <b>${escapeHtml(citation.title)}</b> · ${escapeHtml(citation.author)} · Nível ${citation.source_level}
          <p class="meta">${citation.section ? `Seção: ${escapeHtml(citation.section)} · ` : ''}${citation.page ? `Página ${citation.page}` : ''}</p>
          ${escapeHtml(citation.excerpt)}<br>
          <button class="source-link" onclick="openPassage('${citation.passage_id}')">Abrir trecho exato</button>
        </blockquote>`).join('')}
      <p class="meta">${escapeHtml(answer.observation || '')}${answer.interaction_id ? ` · Registro de auditoria #${answer.interaction_id}` : ''}</p>`;
    if (speakNextAnswer) {
      speakNextAnswer = false;
      speakText(lastAnswerSpeech);
    }
  } catch (error) {
    lastAnswerSpeech = `Não foi possível responder. ${error.message}`;
    box.innerHTML = `<p>${escapeHtml(error.message)}</p>`;
    if (speakNextAnswer) {
      speakNextAnswer = false;
      speakText(lastAnswerSpeech);
    }
  }
};

window.openPassage = async id => {
  try {
    const passage = await api(`/passages/${id}`);
    $('#source-title').textContent = passage.title;
    $('#source-location').textContent = `${passage.author} · Nível ${passage.source_level}${passage.section ? ` · Seção: ${passage.section}` : ''}${passage.page ? ` · Página ${passage.page}` : ''}`;
    $('#source-text').textContent = passage.text;
    const image = $('#source-image');
    const url = safeImageUrl(passage.image_url);
    if (url) {
      image.src = url;
      image.alt = passage.image_description || `Imagem da fonte ${passage.title}`;
      image.classList.remove('hidden');
    } else {
      image.removeAttribute('src');
      image.alt = '';
      image.classList.add('hidden');
    }
    $('#source-dialog').showModal();
  } catch (error) {
    alert(error.message);
  }
};

$('#document-form').onsubmit = async event => {
  event.preventDefault();
  const form = new FormData(event.target);
  const payload = Object.fromEntries(form.entries());
  if (payload.year) payload.year = Number(payload.year); else delete payload.year;
  if (!payload.image_url) delete payload.image_url;
  if (!payload.image_description) delete payload.image_description;
  const message = $('#document-message');
  message.textContent = 'Salvando…';
  try {
    await api('/documents', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
    message.textContent = 'Fonte salva permanentemente.';
    event.target.reset();
    health();
  } catch (error) {
    message.textContent = error.message;
  }
};

$$('[data-try]').forEach(button => {
  button.onclick = async () => {
    const path = button.dataset.try === 'health' ? '/health' : '/documents';
    try {
      $('#api-output').textContent = JSON.stringify(await api(path), null, 2);
    } catch (error) {
      $('#api-output').textContent = error.message;
    }
  };
});

function speakText(text) {
  if (!('speechSynthesis' in window)) {
    $('#voice-status').textContent = 'Este navegador não oferece leitura por voz.';
    return;
  }
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = 'pt-BR';
  utterance.rate = 0.95;
  utterance.onstart = () => { $('#voice-status').textContent = 'Falando…'; };
  utterance.onend = () => { $('#voice-status').textContent = ''; };
  utterance.onerror = () => { $('#voice-status').textContent = 'Não foi possível reproduzir a voz.'; };
  window.speechSynthesis.speak(utterance);
}

window.speakLastAnswer = () => {
  if (lastAnswerSpeech) speakText(lastAnswerSpeech);
};

$('#voice-help').onclick = () => speakText(
  'Para fazer uma pergunta, pressione o botão do microfone e fale depois do aviso. O Doutrinador pesquisará somente nas fontes cadastradas e lerá a resposta em voz alta.'
);

const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;

function submitVoiceTranscript(transcript) {
  const cleaned = transcript.trim();
  if (!cleaned) {
    reportVoiceError('Nenhuma fala foi reconhecida. Tente novamente.');
    return;
  }
  $('#question').value = cleaned;
  $('#voice-status').textContent = `Pergunta reconhecida: ${cleaned}`;
  speakNextAnswer = true;
  $('#ask-form').requestSubmit();
}

function reportVoiceError(message) {
  speakNextAnswer = false;
  $('#voice-status').textContent = message;
  speakText(message);
}

if (!window.isSecureContext) {
  $('#voice-question').disabled = true;
  $('#voice-question').title = 'O microfone exige acesso HTTPS.';
  $('#voice-status').textContent = 'Para usar o microfone, acesse pelo endereço HTTPS.';
} else if (Recognition) {
  const recognition = new Recognition();
  recognition.lang = 'pt-BR';
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;
  recognition.onstart = () => {
    $('#voice-question').classList.add('listening');
    $('#voice-status').textContent = 'Ouvindo. Faça sua pergunta agora.';
  };
  recognition.onresult = event => {
    submitVoiceTranscript(event.results[0][0].transcript);
  };
  recognition.onerror = event => {
    speakNextAnswer = false;
    const messages = {
      'not-allowed': 'Permissão para o microfone negada.',
      'no-speech': 'Nenhuma fala foi reconhecida. Tente novamente.',
      'audio-capture': 'Nenhum microfone foi encontrado.',
    };
    reportVoiceError(messages[event.error] || 'Não foi possível reconhecer a fala.');
  };
  recognition.onend = () => $('#voice-question').classList.remove('listening');
  $('#voice-question').onclick = () => {
    if ($('#voice-question').classList.contains('listening')) return;
    window.speechSynthesis?.cancel();
    try {
      recognition.start();
    } catch {
      $('#voice-status').textContent = 'O microfone já está sendo iniciado.';
    }
  };
} else if (navigator.mediaDevices?.getUserMedia && window.MediaRecorder) {
  let recorder = null;
  let recordingStream = null;
  let recordingChunks = [];
  let recordingTimeout = null;

  const resetRecordingButton = () => {
    $('#voice-question').classList.remove('listening');
    $('#voice-question').textContent = '🎙️ Fazer pergunta por voz';
  };

  const stopRecording = () => {
    if (recorder?.state === 'recording') recorder.stop();
  };

  const startRecording = async () => {
    try {
      window.speechSynthesis?.cancel();
      recordingStream = await navigator.mediaDevices.getUserMedia({audio: true});
      recordingChunks = [];
      recorder = new MediaRecorder(recordingStream);
      recorder.ondataavailable = event => {
        if (event.data.size) recordingChunks.push(event.data);
      };
      recorder.onerror = () => reportVoiceError('Não foi possível gravar o áudio.');
      recorder.onstop = async () => {
        clearTimeout(recordingTimeout);
        recordingStream?.getTracks().forEach(track => track.stop());
        resetRecordingButton();
        const audio = new Blob(recordingChunks, {type: recorder.mimeType || 'audio/webm'});
        $('#voice-status').textContent = 'Transcrevendo a pergunta…';
        try {
          const result = await api('/voice/transcribe', {
            method: 'POST',
            headers: {'Content-Type': audio.type || 'audio/webm'},
            body: audio,
          });
          submitVoiceTranscript(result.text);
        } catch (error) {
          reportVoiceError(error.message);
        }
      };
      recorder.start();
      $('#voice-question').classList.add('listening');
      $('#voice-question').textContent = '⏹️ Parar e enviar';
      $('#voice-status').textContent = 'Ouvindo. Fale e pressione novamente para enviar.';
      recordingTimeout = setTimeout(stopRecording, 15000);
    } catch (error) {
      recordingStream?.getTracks().forEach(track => track.stop());
      resetRecordingButton();
      const message = error.name === 'NotAllowedError'
        ? 'Permissão para o microfone negada.'
        : 'Nenhum microfone disponível.';
      reportVoiceError(message);
    }
  };

  $('#voice-question').onclick = () => {
    if (recorder?.state === 'recording') stopRecording(); else startRecording();
  };

  api('/voice/capabilities').then(capabilities => {
    if (!capabilities.server_transcription) {
      $('#voice-status').textContent = 'Este navegador usará a transcrição do servidor; configure a chave de transcrição.';
    }
  }).catch(() => {});
} else {
  $('#voice-question').disabled = true;
  $('#voice-question').title = 'Captura de áudio indisponível neste navegador.';
  $('#voice-status').textContent = 'O navegador não oferece captura de áudio.';
}

function safeImageUrl(value) {
  if (!value) return '';
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) ? url.href : '';
  } catch {
    return '';
  }
}

function imageMarkup(url, description, className) {
  const safeUrl = safeImageUrl(url);
  return safeUrl
    ? `<img class="${className}" src="${escapeHtml(safeUrl)}" alt="${escapeHtml(description)}" loading="lazy" referrerpolicy="no-referrer">`
    : '';
}

function label(key) {
  return ({
    title: 'Título', author: 'Autoria', source_level: 'Nível da fonte', year: 'Ano',
    edition: 'Edição', origin: 'Origem', provenance_note: 'Observação de procedência',
    authenticity_status: 'Autenticidade', rights_status: 'Direitos/autorização',
    image_url: 'Endereço da imagem', image_description: 'Descrição da imagem',
  })[key] || key;
}

function value(item) {
  return item === null ? 'não informado' : String(item);
}

function escapeHtml(value = '') {
  return String(value).replace(/[&<>'"]/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
  })[char]);
}

health();
