(() => {
  const STATE_LABELS = {
    "standby": ["STANDBY", 'Say "Jarvis" to begin'],
    "listening": ["LISTENING", "Speak now"],
    "thinking": ["THINKING", "Processing"],
    "speaking": ["SPEAKING", "Responding"],
    "error": ["ERROR", "Something went wrong"],
    "needs-setup": ["OFFLINE", "Initial setup required"],
  };

  const el = {
    reactor: document.getElementById("reactor"),
    statusText: document.getElementById("status-text"),
    statusHint: document.getElementById("status-hint"),
    log: document.getElementById("log"),
    wsDot: document.getElementById("ws-dot"),
    userChip: document.getElementById("user-chip"),
    providerChip: document.getElementById("provider-chip"),
    btnSettings: document.getElementById("btn-settings"),
    modal: document.getElementById("setup-modal"),
    modalTitle: document.getElementById("modal-title"),
    fName: document.getElementById("f-name"),
    fProvider: document.getElementById("f-provider"),
    fKey: document.getElementById("f-key"),
    fKeyLabel: document.getElementById("f-key-label"),
    fModel: document.getElementById("f-model"),
    rowKey: document.getElementById("row-key"),
    rowOllamaHost: document.getElementById("row-ollama-host"),
    fOllamaHost: document.getElementById("f-ollama-host"),
    submit: document.getElementById("setup-submit"),
    cancel: document.getElementById("setup-cancel"),
    setupError: document.getElementById("setup-error"),
  };

  const MODEL_DEFAULTS = {
    anthropic: "claude-opus-4-7",
    openai: "gpt-4o",
    ollama: "llama3.1",
  };

  // 마지막으로 받아온 /api/state — 모달 열 때 prefill 에 씀
  let currentState = null;
  // "initial" | "edit"
  let modalMode = "initial";

  function setState(value) {
    el.reactor.dataset.state = value;
    const [label, hint] = STATE_LABELS[value] || [value.toUpperCase(), ""];
    el.statusText.textContent = label;
    el.statusHint.textContent = hint;
  }

  function appendTranscript(role, text, lang) {
    const entry = document.createElement("div");
    entry.className = `entry ${role}`;
    const roleEl = document.createElement("div");
    roleEl.className = "role";
    const roleLabel =
      role === "user" ? `YOU${lang ? " · " + lang.toUpperCase() : ""}`
        : role === "assistant" ? "JARVIS"
        : "SYSTEM";
    roleEl.textContent = roleLabel;
    const textEl = document.createElement("div");
    textEl.className = "text";
    textEl.textContent = text;
    entry.appendChild(roleEl);
    entry.appendChild(textEl);
    el.log.appendChild(entry);
    el.log.scrollTop = el.log.scrollHeight;
  }

  // === 셋업 / 설정 모달 ===

  function updateSetupFields() {
    const p = el.fProvider.value;
    el.fModel.placeholder = MODEL_DEFAULTS[p] || "";

    if (p === "ollama") {
      el.rowKey.classList.add("hidden");
      el.rowOllamaHost.classList.remove("hidden");
    } else {
      el.rowKey.classList.remove("hidden");
      el.rowOllamaHost.classList.add("hidden");
      el.fKeyLabel.textContent = p === "anthropic" ? "ANTHROPIC API KEY" : "OPENAI API KEY";
      // 편집 모드 + 해당 provider 에 이미 키가 저장돼 있으면 빈칸 = 유지
      const haveKey = currentState && currentState.have_keys && currentState.have_keys[p];
      if (modalMode === "edit" && haveKey) {
        el.fKey.placeholder = "(현재 키 유지 — 변경하려면 새 키 입력)";
      } else {
        el.fKey.placeholder = p === "anthropic" ? "sk-ant-..." : "sk-...";
      }
    }
  }

  function openModal(mode) {
    modalMode = mode;
    el.setupError.classList.add("hidden");
    el.fKey.value = "";  // 절대 prefill 안 함 (보안)

    if (mode === "edit" && currentState) {
      el.modalTitle.textContent = "SETTINGS";
      el.submit.textContent = "SAVE";
      el.cancel.classList.remove("hidden");
      el.fName.value = currentState.user_name || "";
      el.fProvider.value = currentState.provider || "anthropic";
      const p = el.fProvider.value;
      const modelFromState = currentState.models ? currentState.models[p] : "";
      el.fModel.value = modelFromState || "";
      el.fOllamaHost.value = currentState.ollama_host || "http://localhost:11434";
    } else {
      el.modalTitle.textContent = "INITIAL SETUP";
      el.submit.textContent = "INITIALIZE";
      el.cancel.classList.add("hidden");
      el.fName.value = "";
      el.fProvider.value = (currentState && currentState.provider) || "anthropic";
      el.fModel.value = "";
      el.fOllamaHost.value = "http://localhost:11434";
    }
    updateSetupFields();
    el.modal.classList.remove("hidden");
    setTimeout(() => el.fName.focus(), 50);
  }

  function closeModal() {
    el.modal.classList.add("hidden");
  }

  async function submitSetup() {
    el.setupError.classList.add("hidden");
    const provider = el.fProvider.value;
    const apiKey = el.fKey.value.trim();
    const haveKey =
      currentState && currentState.have_keys && currentState.have_keys[provider];

    const payload = {
      user_name: el.fName.value.trim(),
      provider,
      api_key: apiKey,
      model: el.fModel.value.trim() || null,
      ollama_host: el.fOllamaHost.value.trim() || null,
    };
    if (!payload.user_name) {
      showSetupError("이름을 입력해주세요.");
      return;
    }
    // 키 검증: provider 가 ollama 아닌데 키가 없고 + 기존 키도 없으면 막음
    if (provider !== "ollama" && !apiKey && !haveKey) {
      showSetupError("API 키를 입력해주세요.");
      return;
    }

    el.submit.disabled = true;
    try {
      const r = await fetch("/api/setup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await r.json();
      if (!r.ok || !data.ok) {
        showSetupError(data.error || "설정 실패");
        return;
      }
      el.userChip.textContent = payload.user_name;
      el.providerChip.textContent = payload.provider.toUpperCase();
      closeModal();
      // state 다시 갖고오기 (have_keys 등 갱신)
      await refreshState();
    } catch (e) {
      showSetupError(String(e));
    } finally {
      el.submit.disabled = false;
    }
  }

  function showSetupError(msg) {
    el.setupError.textContent = msg;
    el.setupError.classList.remove("hidden");
  }

  async function refreshState() {
    try {
      const r = await fetch("/api/state");
      currentState = await r.json();
      if (currentState.user_name) el.userChip.textContent = currentState.user_name;
      if (currentState.provider) el.providerChip.textContent = currentState.provider.toUpperCase();
      return currentState;
    } catch (e) {
      appendTranscript("system", "/api/state 실패: " + e);
      return null;
    }
  }

  async function bootstrap() {
    const state = await refreshState();
    if (!state) return;
    if (!state.setup_complete) {
      openModal("initial");
      setState("needs-setup");
    } else {
      setState(state.runtime_state || "standby");
    }
  }

  // === WS ===

  function connectWS() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${proto}//${location.host}/ws`);

    ws.addEventListener("open", () => {
      el.wsDot.classList.add("live");
    });
    ws.addEventListener("close", () => {
      el.wsDot.classList.remove("live");
      setTimeout(connectWS, 1500);
    });
    ws.addEventListener("message", (ev) => {
      let msg;
      try { msg = JSON.parse(ev.data); } catch { return; }
      if (msg.type === "state") {
        setState(msg.value);
      } else if (msg.type === "transcript") {
        appendTranscript(msg.role, msg.text, msg.lang);
      } else if (msg.type === "log") {
        appendTranscript("system", msg.text);
      } else if (msg.type === "user") {
        if (msg.name) el.userChip.textContent = msg.name;
        if (msg.provider) el.providerChip.textContent = msg.provider.toUpperCase();
      }
    });

    setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "ping" }));
    }, 20000);
  }

  // === 부팅 ===

  el.fProvider.addEventListener("change", updateSetupFields);
  el.submit.addEventListener("click", submitSetup);
  el.cancel.addEventListener("click", closeModal);
  el.btnSettings.addEventListener("click", async () => {
    await refreshState();
    openModal(currentState && currentState.setup_complete ? "edit" : "initial");
  });
  el.fKey.addEventListener("keydown", (e) => { if (e.key === "Enter") submitSetup(); });
  el.fName.addEventListener("keydown", (e) => { if (e.key === "Enter") submitSetup(); });
  // Esc 로 모달 닫기 (편집 모드 한정)
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modalMode === "edit" && !el.modal.classList.contains("hidden")) {
      closeModal();
    }
  });

  updateSetupFields();
  bootstrap();
  connectWS();
})();
