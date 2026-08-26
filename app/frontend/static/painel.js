(function () {
  const listEl = document.getElementById("alert-list");
  const detailEl = document.getElementById("detail-panel");
  const filterButtons = document.querySelectorAll(".filters button");

  let currentFilter = "aberto";
  let selectedAlertId = null;
  let selectedAlertStatus = null;
  let listPollTimer = null;
  let detailPollTimer = null;
  const transcriptIds = new Set();

  const REASON_ICON = { gatilho_imediato: "🔴", pontuacao_cumulativa: "🟠" };
  const ROLE_LABEL = { user: "Paciente", assistant: "IA", professional: "Você", system: "Sistema" };

  const RESOLUTION_LABEL = {
    falso_positivo: "Falso positivo",
    atendimento_remoto: "Atendimento remoto",
    encaminhado: "Encaminhado para acompanhamento",
    samu_acionado: "Risco iminente confirmado (SAMU)",
  };

  function formatTime(iso) {
    try {
      return new Date(iso).toLocaleString("pt-BR");
    } catch (e) {
      return iso;
    }
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function statusLabel(status) {
    return { aberto: "Aberto", em_atendimento: "Em atendimento", resolvido: "Resolvido" }[status] || status;
  }

  // ---------------- Lista de alertas ----------------

  async function fetchAlerts() {
    const res = await fetch(`/api/alerts?status=${currentFilter}`);
    const alerts = await res.json();
    renderList(alerts);
  }

  function renderList(alerts) {
    if (!alerts.length) {
      listEl.innerHTML = '<div class="empty-state">Nenhum alerta nesta categoria.</div>';
      return;
    }
    listEl.innerHTML = "";
    alerts.forEach((a) => {
      const card = document.createElement("div");
      card.className = `alert-card ${a.reason} ${a.status === "resolvido" ? "resolvido" : ""} ${a.id === selectedAlertId ? "selected" : ""}`;
      card.innerHTML = `
        <div class="reason">${REASON_ICON[a.reason] || "⚪"} ${a.reason_label}</div>
        <div class="meta">Sessão ${a.session_id.slice(0, 8)} · pontuação atual: ${a.session_score}</div>
        <div class="meta">${formatTime(a.created_at)}</div>
        <span class="status-tag ${a.status}">${statusLabel(a.status)}</span>
      `;
      card.addEventListener("click", () => selectAlert(a.id));
      listEl.appendChild(card);
    });
  }

  // ---------------- Detalhe / atendimento ----------------

  async function selectAlert(id) {
    selectedAlertId = id;
    transcriptIds.clear();
    if (detailPollTimer) clearInterval(detailPollTimer);

    const alert = await fetchAlertDetail(id);
    if (!alert) return;
    selectedAlertStatus = alert.status;
    renderDetailShell(alert);
    fetchAlerts();

    detailPollTimer = setInterval(async () => {
      const fresh = await fetchAlertDetail(id);
      if (!fresh) return;
      if (fresh.status !== selectedAlertStatus) {
        selectedAlertStatus = fresh.status;
        transcriptIds.clear();
        renderDetailShell(fresh);
        fetchAlerts();
      } else {
        appendNewMessages(fresh.messages);
      }
    }, 3000);
  }

  async function fetchAlertDetail(id) {
    try {
      const res = await fetch(`/api/alerts/${id}`);
      if (!res.ok) return null;
      return await res.json();
    } catch (e) {
      return null;
    }
  }

  function messageHtml(m) {
    const roleClass = m.role === "user" ? "user" : m.role;
    if (m.role === "system") {
      return `<div class="msg system">${escapeHtml(m.content)}</div>`;
    }
    return `
      <div class="msg-row ${m.role === "user" ? "user" : "assistant"}">
        ${m.role === "user" ? "" : `<div class="avatar ${m.role === "assistant" ? "ai" : "professional"}">${ROLE_LABEL[m.role]?.slice(0, 3) || "?"}</div>`}
        <div class="msg ${roleClass}">${escapeHtml(m.content)}</div>
        ${m.role === "user" ? '<div class="avatar user">Pac</div>' : ""}
      </div>
    `;
  }

  function appendNewMessages(messages) {
    const box = document.getElementById("transcript-box");
    if (!box) return;
    let appended = false;
    messages.forEach((m) => {
      if (!transcriptIds.has(m.id)) {
        transcriptIds.add(m.id);
        box.insertAdjacentHTML("beforeend", messageHtml(m));
        appended = true;
      }
    });
    if (appended) box.scrollTop = box.scrollHeight;
  }

  function renderDetailShell(alert) {
    const isResolved = alert.status === "resolvido";
    const isAssumed = alert.status === "em_atendimento";
    const isOpen = alert.status === "aberto";

    transcriptIds.clear();
    const transcriptHtml = alert.messages.map((m) => {
      transcriptIds.add(m.id);
      return messageHtml(m);
    }).join("");

    detailEl.innerHTML = `
      <div class="detail-header">
        <div>
          <div class="reason" style="font-size:15px;">
            ${REASON_ICON[alert.reason] || "⚪"} ${alert.reason_label}
          </div>
          <div class="meta">Sessão ${alert.session_id.slice(0, 8)} · criado em ${formatTime(alert.created_at)}</div>
          <div class="meta">Detalhe: ${escapeHtml(alert.detail || "")}</div>
        </div>
        <span class="status-tag ${alert.status}">${statusLabel(alert.status)}</span>
      </div>

      ${isResolved ? `
        <div class="resolution-box">
          <strong>Resolvido como:</strong> ${RESOLUTION_LABEL[alert.resolution] || alert.resolution}
          ${alert.note ? `<div class="meta" style="margin-top:4px;">Observações: ${escapeHtml(alert.note)}</div>` : ""}
        </div>
      ` : ""}

      <div class="transcript" id="transcript-box">${transcriptHtml || '<div class="empty-state">Sem mensagens.</div>'}</div>

      ${isOpen ? `
        <button id="assume-btn" class="send-primary-btn" style="width:100%; margin-bottom: 10px;">Assumir conversa</button>
      ` : ""}

      ${isAssumed ? `
        <div class="professional-composer">
          <input id="professional-input" type="text" placeholder="Responder como psicólogo de plantão..." autocomplete="off" />
          <button id="professional-send-btn" class="send-primary-btn">Enviar</button>
        </div>
      ` : ""}

      ${!isResolved ? `
        <details class="resolve-details" ${isOpen ? "" : "open"}>
          <summary>${isAssumed ? "Encerrar atendimento" : "Resolver sem assumir a conversa"}</summary>
          <textarea class="note-input" id="note-input" placeholder="Observações do atendimento (opcional)..."></textarea>
          <div class="action-row">
            <button class="btn-falso" data-resolution="falso_positivo">Marcar falso positivo</button>
            <button class="btn-remoto" data-resolution="atendimento_remoto">Atendimento remoto concluído</button>
            <button class="btn-encaminhado" data-resolution="encaminhado">Encaminhar para acompanhamento</button>
            <button class="btn-samu" data-resolution="samu_acionado">Confirmar risco iminente (SAMU) *</button>
          </div>
          <div class="meta" style="margin-top:8px;">* Neste protótipo, esta ação apenas registra a decisão humana — nenhum contato real é feito com o SAMU ou com localização.</div>
        </details>
      ` : ""}
    `;

    const box = document.getElementById("transcript-box");
    if (box) box.scrollTop = box.scrollHeight;

    const assumeBtn = document.getElementById("assume-btn");
    if (assumeBtn) assumeBtn.addEventListener("click", () => assumeAlert(alert.id));

    const sendBtn = document.getElementById("professional-send-btn");
    const input = document.getElementById("professional-input");
    if (sendBtn && input) {
      const send = () => sendProfessionalMessage(alert.id, input);
      sendBtn.addEventListener("click", send);
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") send();
      });
    }

    detailEl.querySelectorAll(".action-row button").forEach((btn) => {
      btn.addEventListener("click", () => resolveAlert(alert.id, btn.dataset.resolution));
    });
  }

  async function assumeAlert(id) {
    await fetch(`/api/alerts/${id}/assume`, { method: "POST" });
    const fresh = await fetchAlertDetail(id);
    if (fresh) {
      selectedAlertStatus = fresh.status;
      renderDetailShell(fresh);
      fetchAlerts();
    }
  }

  async function sendProfessionalMessage(alertId, inputEl) {
    const text = inputEl.value.trim();
    if (!text) return;
    inputEl.value = "";
    const res = await fetch("/api/professional-message", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ alert_id: alertId, message: text }),
    });
    const data = await res.json();
    const box = document.getElementById("transcript-box");
    if (box && data.id != null && !transcriptIds.has(data.id)) {
      transcriptIds.add(data.id);
      box.insertAdjacentHTML("beforeend", messageHtml({ role: "professional", content: text }));
      box.scrollTop = box.scrollHeight;
    }
    inputEl.focus();
  }

  async function resolveAlert(id, resolution) {
    const note = document.getElementById("note-input")?.value || "";
    await fetch(`/api/alerts/${id}/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resolution, note }),
    });
    if (detailPollTimer) clearInterval(detailPollTimer);
    selectAlert(id);
    fetchAlerts();
  }

  filterButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      filterButtons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentFilter = btn.dataset.filter;
      fetchAlerts();
    });
  });

  fetchAlerts();
  listPollTimer = setInterval(fetchAlerts, 5000);
})();
