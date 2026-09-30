(function () {
  const messagesEl = document.getElementById("messages");
  const inputEl = document.getElementById("input");
  const sendBtn = document.getElementById("send-btn");
  const statusPill = document.getElementById("status-pill");
  const endSessionBtn = document.getElementById("end-session-btn");
  const endModal = document.getElementById("end-modal");
  const endModalCancel = document.getElementById("end-modal-cancel");
  const endModalConfirm = document.getElementById("end-modal-confirm");
  const endScreen = document.getElementById("end-screen");
  const newConversationBtn = document.getElementById("new-conversation-btn");

  const STORAGE_KEY = "triagem_session_id";
  let sessionId = localStorage.getItem(STORAGE_KEY) || null;
  let currentStatus = "normal";
  let pollTimer = null;

  const renderedIds = new Set();

  const ROLE_LABEL = { assistant: "IA", user: "Eu", professional: "Psi" };

  function formatTime(date) {
    return date.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  }

  function addMessage(role, content, id) {
    if (id != null) {
      if (renderedIds.has(id)) return null;
      renderedIds.add(id);
    }

    if (role === "system") {
      const div = document.createElement("div");
      div.className = "msg system";
      div.textContent = content;
      messagesEl.appendChild(div);
      messagesEl.scrollTop = messagesEl.scrollHeight;
      return div;
    }

    const row = document.createElement("div");
    row.className = "msg-row " + role;

    const bubble = document.createElement("div");
    bubble.className = "msg " + role;
    bubble.textContent = content;

    const avatarClass = role === "assistant" ? "ai" : role === "professional" ? "professional" : "user";
    const avatar = document.createElement("div");
    avatar.className = "avatar " + avatarClass;
    avatar.textContent = ROLE_LABEL[role] || "?";

    if (role === "user") {
      row.appendChild(bubble);
      row.appendChild(avatar);
    } else {
      row.appendChild(avatar);
      row.appendChild(bubble);
    }

    messagesEl.appendChild(row);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return row;
  }

  function addEscalationBanner() {
    const div = document.createElement("div");
    div.className = "msg escalated-banner";
    div.textContent = "⚠ Um psicólogo de plantão foi notificado e vai acompanhar esta conversa.";
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function addWaitingForHuman() {
    const div = document.createElement("div");
    div.className = "waiting-human";
    div.id = "waiting-human";
    div.textContent = "Aguardando resposta do psicólogo de plantão...";
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function removeWaitingForHuman() {
    const el = document.getElementById("waiting-human");
    if (el) el.remove();
  }

  function showTyping() {
    const row = document.createElement("div");
    row.className = "typing-row";
    row.id = "typing-indicator";

    const avatar = document.createElement("div");
    avatar.className = "avatar ai";
    avatar.textContent = "IA";

    const dots = document.createElement("div");
    dots.className = "typing-dots";
    dots.innerHTML = "<span></span><span></span><span></span>";

    row.appendChild(avatar);
    row.appendChild(dots);
    messagesEl.appendChild(row);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function hideTyping() {
    const el = document.getElementById("typing-indicator");
    if (el) el.remove();
  }

  function setStatus(status) {
    currentStatus = status;
    statusPill.classList.remove("normal", "escalated");
    if (status === "em_atendimento") {
      statusPill.classList.add("escalated");
      statusPill.textContent = "Psicólogo na conversa";
    } else if (status === "escalated") {
      statusPill.classList.add("escalated");
      statusPill.textContent = "Encaminhado a psicólogo";
    } else {
      statusPill.classList.add("normal");
      statusPill.textContent = "Conversa normal";
    }
    managePolling();
  }

  function managePolling() {
    // Poll sempre que a sessão estiver escalonada (aguardando ou já em
    // atendimento humano) — senão o paciente só descobriria que o
    // psicólogo entrou na conversa ao mandar uma mensagem nova.
    const needsPolling = (currentStatus === "escalated" || currentStatus === "em_atendimento") && sessionId;
    if (needsPolling) {
      if (!pollTimer) pollTimer = setInterval(pollForUpdates, 3000);
    } else if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  async function pollForUpdates() {
    if (!sessionId) return;
    try {
      const res = await fetch(`/api/session/${sessionId}`);
      const data = await res.json();
      let gotProfessionalReply = false;
      (data.messages || []).forEach((m) => {
        if (!renderedIds.has(m.id)) {
          if (m.role === "professional") gotProfessionalReply = true;
          addMessage(m.role, m.content, m.id);
        }
      });
      if (gotProfessionalReply) removeWaitingForHuman();
      if (data.status !== currentStatus) setStatus(data.status);
    } catch (e) {
      // silencioso — tenta de novo no próximo ciclo
    }
  }

  async function loadHistory() {
    if (!sessionId) {
      addMessage("assistant", "Oi, que bom que você está aqui. Como você está se sentindo hoje?");
      return;
    }
    try {
      const res = await fetch(`/api/session/${sessionId}`);
      const data = await res.json();
      if (data.messages && data.messages.length) {
        data.messages.forEach((m) => addMessage(m.role, m.content, m.id));
        setStatus(data.status);
      } else {
        addMessage("assistant", "Oi, que bom que você está aqui. Como você está se sentindo hoje?");
      }
    } catch (e) {
      addMessage("assistant", "Oi, que bom que você está aqui. Como você está se sentindo hoje?");
    }
  }

  let sending = false;

  async function sendMessage() {
    if (sending) return; // evita envio duplicado (ex.: Enter disparando 2x)
    const text = inputEl.value.trim();
    if (!text) return;
    sending = true;
    inputEl.value = "";
    sendBtn.disabled = true;
    addMessage("user", text);

    const isHumanAttendance = currentStatus === "em_atendimento";
    if (!isHumanAttendance) showTyping();

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: text }),
      });
      const data = await res.json();

      if (data.session_id) {
        sessionId = data.session_id;
        localStorage.setItem(STORAGE_KEY, sessionId);
      }
      if (data.user_message_id != null) renderedIds.add(data.user_message_id);

      if (isHumanAttendance) {
        addWaitingForHuman();
        setStatus(data.status);
        return;
      }

      const delay = 500 + Math.random() * 700;
      await new Promise((r) => setTimeout(r, delay));
      hideTyping();

      if (data.alert_created) addEscalationBanner();

      if (data.reply) {
        addMessage("assistant", data.reply, data.assistant_message_id);
      }
      setStatus(data.status);
    } catch (e) {
      hideTyping();
      addMessage("assistant", "Estou com uma instabilidade agora. Se você precisar de ajuda urgente, ligue para o CVV (188) ou SAMU (192).");
    } finally {
      sending = false;
      sendBtn.disabled = false;
      inputEl.focus();
    }
  }

  sendBtn.addEventListener("click", sendMessage);
  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendMessage();
  });

  // ---------- Encerrar conversa / iniciar nova ----------

  endSessionBtn.addEventListener("click", () => {
    endModal.classList.remove("hidden");
  });
  endModalCancel.addEventListener("click", () => {
    endModal.classList.add("hidden");
  });
  endModalConfirm.addEventListener("click", async () => {
    endModal.classList.add("hidden");
    if (pollTimer) clearInterval(pollTimer);
    try {
      if (sessionId) {
        await fetch(`/api/session/${sessionId}/end`, { method: "POST" });
      }
    } catch (e) {
      // segue mesmo se a chamada falhar — o importante é liberar o navegador
    }
    localStorage.removeItem(STORAGE_KEY);
    endScreen.classList.remove("hidden");
  });
  newConversationBtn.addEventListener("click", () => {
    window.location.reload();
  });

  loadHistory();
})();
