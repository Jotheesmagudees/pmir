/**
 * PMIR-Net-Lite: Frontend Application Controller
 * Handles speech recognition, multi-signal prediction display,
 * Confirm/Edit/Reject state machine, Web Speech TTS, and dictionary management.
 */

document.addEventListener("DOMContentLoaded", () => {
  // State
  let currentPrediction = null;
  let allIntents = [];
  let selectedEditIntentId = null;
  let isTTSAudioEnabled = true;
  let isRecording = false;
  let recognition = null;

  // DOM Elements
  const tabs = document.querySelectorAll(".nav-tab");
  const tabPanes = document.querySelectorAll(".tab-pane");
  const transcriptInput = document.getElementById("transcript-input");
  const processBtn = document.getElementById("process-btn");
  const micBtn = document.getElementById("mic-btn");
  const micStatusText = document.getElementById("mic-status-text");
  const presetChips = document.querySelectorAll(".preset-chip");
  const ttsToggleBtn = document.getElementById("tts-toggle-btn");
  const themeToggleBtn = document.getElementById("theme-toggle-btn");

  // Output Elements
  const emptyState = document.getElementById("empty-state");
  const activeResult = document.getElementById("active-result");
  const resCategory = document.getElementById("res-category");
  const resTitle = document.getElementById("res-title");
  const resId = document.getElementById("res-id");
  const urgencyBadge = document.getElementById("urgency-badge");
  const gaugeCircle = document.getElementById("gauge-circle");
  const gaugeValue = document.getElementById("gauge-value");
  const gaugeStatus = document.getElementById("gauge-status");
  const resTtsText = document.getElementById("res-tts-text");
  const audioWave = document.getElementById("audio-wave");
  const resPersonalBadge = document.getElementById("res-personal-badge");
  const abstentionBanner = document.getElementById("abstention-banner");
  const abstentionPrompt = document.getElementById("abstention-prompt");
  const alternativesWrapper = document.getElementById("alternatives-wrapper");
  const alternativesList = document.getElementById("alternatives-list");
  const inspectorNorm = document.getElementById("inspector-norm");
  const inspectorPhonetics = document.getElementById("inspector-phonetics");

  // Gate Buttons
  const btnConfirm = document.getElementById("btn-confirm");
  const btnEdit = document.getElementById("btn-edit");
  const btnReject = document.getElementById("btn-reject");

  // Modals
  const editModal = document.getElementById("edit-modal");
  const closeEditModal = document.getElementById("close-edit-modal");
  const btnCancelEdit = document.getElementById("btn-cancel-edit");
  const btnApplyEdit = document.getElementById("btn-apply-edit");
  const modalPhraseText = document.getElementById("modal-phrase-text");
  const modalIntentFilter = document.getElementById("modal-intent-filter");
  const modalIntentsList = document.getElementById("modal-intents-list");

  const addDictModal = document.getElementById("add-dict-modal");
  const btnOpenAddDict = document.getElementById("btn-open-add-dict");
  const closeAddModal = document.getElementById("close-add-modal");
  const btnCancelAdd = document.getElementById("btn-cancel-add");
  const btnSaveAdd = document.getElementById("btn-save-add");
  const newPhraseInput = document.getElementById("new-phrase-input");
  const newIntentSelect = document.getElementById("new-intent-select");
  const btnClearDict = document.getElementById("btn-clear-dict");
  const dictTableBody = document.getElementById("dict-table-body");
  const dictCountBadge = document.getElementById("dict-count-badge");

  // Initialize Speech Recognition if supported
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "en-US";

    recognition.onstart = () => {
      isRecording = true;
      micBtn.classList.add("recording");
      micStatusText.textContent = "Listening...";
    };

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      transcriptInput.value = transcript;
      showToast(`Heard: "${transcript}"`, "info");
      processTranscript(transcript);
    };

    recognition.onerror = (event) => {
      console.warn("Speech recognition error:", event.error);
      showToast(`Mic error: ${event.error}`, "error");
    };

    recognition.onend = () => {
      isRecording = false;
      micBtn.classList.remove("recording");
      micStatusText.textContent = "Listen";
    };
  }

  // Tab Navigation
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      const targetTab = tab.getAttribute("data-tab");
      tabs.forEach(t => {
        t.classList.remove("active");
        t.setAttribute("aria-selected", "false");
      });
      tabPanes.forEach(pane => pane.classList.remove("active"));

      tab.classList.add("active");
      tab.setAttribute("aria-selected", "true");
      document.getElementById(`tab-${targetTab}`).classList.add("active");

      if (targetTab === "dictionary") {
        fetchDictionary();
      } else if (targetTab === "analytics") {
        fetchBenchmarkData();
      }
    });
  });

  // Theme Toggle
  themeToggleBtn.addEventListener("click", () => {
    const isLight = document.body.getAttribute("data-theme") === "light";
    if (isLight) {
      document.body.removeAttribute("data-theme");
    } else {
      document.body.setAttribute("data-theme", "light");
    }
  });

  // TTS Toggle
  ttsToggleBtn.addEventListener("click", () => {
    isTTSAudioEnabled = !isTTSAudioEnabled;
    ttsToggleBtn.classList.toggle("active", isTTSAudioEnabled);
    showToast(isTTSAudioEnabled ? "Speech Audio Output Enabled" : "Speech Audio Muted", "info");
  });

  // Mic Button Click
  micBtn.addEventListener("click", () => {
    if (!recognition) {
      showToast("Web Speech API not supported on this browser.", "error");
      return;
    }
    if (isRecording) {
      recognition.stop();
    } else {
      try {
        recognition.start();
      } catch (e) {
        console.error(e);
      }
    }
  });

  // Preset Chips Click
  presetChips.forEach(chip => {
    chip.addEventListener("click", () => {
      const text = chip.getAttribute("data-text");
      transcriptInput.value = text;
      processTranscript(text);
    });
  });

  // Process Button Click
  processBtn.addEventListener("click", () => {
    const text = transcriptInput.value.trim();
    if (!text) {
      showToast("Please enter or speak a phrase first.", "error");
      return;
    }
    processTranscript(text);
  });

  transcriptInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      processBtn.click();
    }
  });

  // Global Keyboard Shortcuts (C, E, R)
  document.addEventListener("keydown", (e) => {
    const activeEl = document.activeElement;
    if (activeEl && (activeEl.tagName === "INPUT" || activeEl.tagName === "TEXTAREA" || activeEl.tagName === "SELECT")) {
      return;
    }
    if (!currentPrediction) return;

    if (e.key.toLowerCase() === "c") {
      btnConfirm.click();
    } else if (e.key.toLowerCase() === "e") {
      btnEdit.click();
    } else if (e.key.toLowerCase() === "r") {
      btnReject.click();
    }
  });

  // Load Initial Intents and Dictionary
  fetchIntents();
  fetchDictionary();

  // API Call: Fetch All Canonical Intents
  async function fetchIntents() {
    try {
      const res = await fetch("/api/intents");
      const data = await res.json();
      allIntents = data.intents || [];
      populateNewIntentSelect();
    } catch (e) {
      console.error("Failed to fetch intents:", e);
    }
  }

  function populateNewIntentSelect() {
    newIntentSelect.innerHTML = "";
    allIntents.forEach(item => {
      const opt = document.createElement("option");
      opt.value = item.id;
      opt.textContent = `[${item.id}] ${item.canonical_label} (${item.category})`;
      newIntentSelect.appendChild(opt);
    });
  }

  // API Call: Process Transcript Prediction
  async function processTranscript(text) {
    processBtn.disabled = true;
    try {
      const res = await fetch("/api/predict", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text })
      });

      if (!res.ok) {
        throw new Error("Prediction request failed");
      }

      const data = await res.json();
      currentPrediction = data;
      renderPrediction(data);
    } catch (e) {
      showToast(`Error resolving intent: ${e.message}`, "error");
    } finally {
      processBtn.disabled = false;
    }
  }

  // Render Prediction Result
  function renderPrediction(data) {
    emptyState.style.display = "none";
    activeResult.style.display = "block";

    resTitle.textContent = data.canonical_label;
    resId.textContent = `[${data.predicted_intent}]`;

    // Category lookup
    const foundIntent = allIntents.find(i => i.id === data.predicted_intent);
    resCategory.textContent = foundIntent ? foundIntent.category : "General Communication";

    // Urgency Badge
    urgencyBadge.className = `badge badge-${data.urgency || "medium"}`;
    urgencyBadge.textContent = (data.urgency || "medium").toUpperCase();

    // Confidence Gauge
    const confPercent = Math.round(data.confidence * 100);
    gaugeValue.textContent = `${confPercent}%`;
    gaugeCircle.className = "gauge-circle";

    if (data.is_abstain) {
      gaugeCircle.classList.add("low");
      gaugeStatus.textContent = "Abstain (< 52%)";
    } else if (confPercent >= 75) {
      gaugeCircle.classList.add("high");
      gaugeStatus.textContent = "High Confidence";
    } else {
      gaugeCircle.classList.add("moderate");
      gaugeStatus.textContent = "Moderate Confidence";
    }

    // TTS Display Text
    resTtsText.textContent = `"${data.tts_response}"`;
    resPersonalBadge.style.display = data.is_personal ? "block" : "none";

    // Abstention Banner
    if (data.is_abstain) {
      abstentionBanner.style.display = "flex";
      abstentionPrompt.textContent = data.clarification_prompt || "Confidence is below safe threshold. Please clarify below.";
    } else {
      abstentionBanner.style.display = "none";
    }

    // Alternative Candidates
    if (data.top_alternatives && data.top_alternatives.length > 0) {
      alternativesWrapper.style.display = "block";
      alternativesList.innerHTML = "";
      data.top_alternatives.forEach(alt => {
        const item = document.createElement("div");
        item.className = "alt-item";
        item.innerHTML = `
          <span><strong>[${alt.intent_id}]</strong> ${alt.canonical_label}</span>
          <span class="badge badge-info">${Math.round(alt.confidence * 100)}%</span>
        `;
        item.addEventListener("click", () => {
          openEditModalWithPreset(alt.intent_id);
        });
        alternativesList.appendChild(item);
      });
    } else {
      alternativesWrapper.style.display = "none";
    }

    // Normalizer Inspector
    inspectorNorm.textContent = data.normalized_text || "—";
    inspectorPhonetics.innerHTML = "";
    if (data.phonetic_tokens) {
      data.phonetic_tokens.forEach(tok => {
        const span = document.createElement("span");
        span.className = "token-badge";
        span.textContent = `${tok.token} [S:${tok.soundex} M:${tok.metaphone}]`;
        inspectorPhonetics.appendChild(span);
      });
    }
  }

  // Audio TTS Synthesis
  function speakTTS(text) {
    if (!isTTSAudioEnabled || !("speechSynthesis" in window)) return;

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.95;
    utterance.pitch = 1.0;

    audioWave.classList.add("playing");
    utterance.onend = () => audioWave.classList.remove("playing");
    utterance.onerror = () => audioWave.classList.remove("playing");

    window.speechSynthesis.speak(utterance);
  }

  // Confirmation Gate Actions
  btnConfirm.addEventListener("click", async () => {
    if (!currentPrediction) return;
    try {
      const res = await fetch("/api/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: currentPrediction.raw_text,
          action: "CONFIRM"
        })
      });

      const data = await res.json();
      speakTTS(data.final_tts_text);
      showToast(`Confirmed [${data.final_intent_id}]. Personal dictionary updated.`, "success");
      fetchDictionary();
    } catch (e) {
      showToast(`Error executing confirm: ${e.message}`, "error");
    }
  });

  btnReject.addEventListener("click", async () => {
    if (!currentPrediction) return;
    try {
      const res = await fetch("/api/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: currentPrediction.raw_text,
          action: "REJECT"
        })
      });

      showToast("Prediction rejected. Personal dictionary was NOT modified.", "info");
      currentPrediction = null;
      activeResult.style.display = "none";
      emptyState.style.display = "block";
    } catch (e) {
      showToast(`Error executing reject: ${e.message}`, "error");
    }
  });

  // Edit / Reassign Modal Flow
  btnEdit.addEventListener("click", () => {
    if (!currentPrediction) return;
    openEditModalWithPreset(currentPrediction.predicted_intent);
  });

  function openEditModalWithPreset(presetIntentId) {
    modalPhraseText.textContent = `"${currentPrediction.raw_text}"`;
    selectedEditIntentId = presetIntentId;
    renderEditModalIntents("");
    editModal.style.display = "flex";
    btnApplyEdit.disabled = !selectedEditIntentId;
  }

  function renderEditModalIntents(filterQuery) {
    modalIntentsList.innerHTML = "";
    const q = filterQuery.toLowerCase().trim();

    const filtered = allIntents.filter(item => {
      return (
        item.id.toLowerCase().includes(q) ||
        item.canonical_label.toLowerCase().includes(q) ||
        item.category.toLowerCase().includes(q)
      );
    });

    filtered.forEach(item => {
      const card = document.createElement("div");
      card.className = `intent-option-card ${selectedEditIntentId === item.id ? "selected" : ""}`;
      card.innerHTML = `
        <div class="intent-option-title">${item.canonical_label}</div>
        <div class="intent-option-id">[${item.id}] &bull; ${item.category}</div>
      `;
      card.addEventListener("click", () => {
        selectedEditIntentId = item.id;
        document.querySelectorAll(".intent-option-card").forEach(c => c.classList.remove("selected"));
        card.classList.add("selected");
        btnApplyEdit.disabled = false;
      });
      modalIntentsList.appendChild(card);
    });
  }

  modalIntentFilter.addEventListener("input", (e) => {
    renderEditModalIntents(e.target.value);
  });

  closeEditModal.addEventListener("click", () => editModal.style.display = "none");
  btnCancelEdit.addEventListener("click", () => editModal.style.display = "none");

  btnApplyEdit.addEventListener("click", async () => {
    if (!currentPrediction || !selectedEditIntentId) return;
    try {
      const res = await fetch("/api/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: currentPrediction.raw_text,
          action: "EDIT",
          corrected_intent_id: selectedEditIntentId
        })
      });

      const data = await res.json();
      editModal.style.display = "none";
      speakTTS(data.final_tts_text);
      showToast(`Assigned to [${data.final_intent_id}] and saved to dictionary!`, "success");
      fetchDictionary();

      // Refresh current prediction to reflect updated personal dictionary
      processTranscript(currentPrediction.raw_text);
    } catch (e) {
      showToast(`Error applying edit: ${e.message}`, "error");
    }
  });

  // Personal Dictionary API & Management
  async function fetchDictionary() {
    try {
      const res = await fetch("/api/dictionary");
      const data = await res.json();
      renderDictionaryTable(data.entries || []);
      dictCountBadge.textContent = data.count || 0;
    } catch (e) {
      console.error("Failed to fetch dictionary:", e);
    }
  }

  function renderDictionaryTable(entries) {
    dictTableBody.innerHTML = "";
    if (entries.length === 0) {
      dictTableBody.innerHTML = `
        <tr>
          <td colspan="5" class="empty-table-msg">
            No personalized phrases saved yet. Confirm or Edit any phrase in the Communicator to personalize mappings.
          </td>
        </tr>
      `;
      return;
    }

    entries.forEach(item => {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td><strong>"${item.phrase}"</strong></td>
        <td><span class="badge badge-info">[${item.intent_id}]</span></td>
        <td>${item.usage_count}x</td>
        <td><small class="subtitle">${item.timestamp || "—"}</small></td>
        <td>
          <button class="btn btn-danger btn-sm delete-entry-btn" data-phrase="${item.phrase}">Delete</button>
        </td>
      `;
      dictTableBody.appendChild(row);
    });

    document.querySelectorAll(".delete-entry-btn").forEach(btn => {
      btn.addEventListener("click", async () => {
        const phrase = btn.getAttribute("data-phrase");
        await deleteDictionaryEntry(phrase);
      });
    });
  }

  async function deleteDictionaryEntry(phrase) {
    try {
      const res = await fetch(`/api/dictionary?phrase=${encodeURIComponent(phrase)}`, {
        method: "DELETE"
      });
      const data = await res.json();
      if (data.success) {
        showToast(`Removed "${phrase}" from personal dictionary.`, "info");
        fetchDictionary();
      }
    } catch (e) {
      showToast(`Error deleting entry: ${e.message}`, "error");
    }
  }

  btnClearDict.addEventListener("click", async () => {
    if (!confirm("Are you sure you want to clear all personalized dictionary entries?")) return;
    try {
      const res = await fetch("/api/dictionary", { method: "DELETE" });
      const data = await res.json();
      if (data.success) {
        showToast("Personal dictionary cleared.", "info");
        fetchDictionary();
      }
    } catch (e) {
      showToast(`Error clearing dictionary: ${e.message}`, "error");
    }
  });

  // Manual Add Dictionary Modal
  btnOpenAddDict.addEventListener("click", () => {
    newPhraseInput.value = "";
    addDictModal.style.display = "flex";
  });

  closeAddModal.addEventListener("click", () => addDictModal.style.display = "none");
  btnCancelAdd.addEventListener("click", () => addDictModal.style.display = "none");

  btnSaveAdd.addEventListener("click", async () => {
    const phrase = newPhraseInput.value.trim();
    const intentId = newIntentSelect.value;
    if (!phrase || !intentId) {
      showToast("Phrase and Intent are required.", "error");
      return;
    }

    try {
      const res = await fetch("/api/dictionary/add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phrase, intent_id: intentId, note: "Added manually via web UI" })
      });

      const data = await res.json();
      if (data.success) {
        addDictModal.style.display = "none";
        showToast(`Saved "${phrase}" -> [${intentId}] to dictionary.`, "success");
        fetchDictionary();
      }
    } catch (e) {
      showToast(`Error saving phrase: ${e.message}`, "error");
    }
  });

  // Benchmark Live Stats
  async function fetchBenchmarkData() {
    try {
      const res = await fetch("/api/benchmark");
      if (!res.ok) return;
      const data = await res.json();
      const b = data.benchmark_evaluation;
      const p = data.personalization_experiment;

      if (b) {
        document.getElementById("kpi-accuracy").textContent = `${Math.round(b.overall_top1_accuracy * 1000) / 10}%`;
        document.getElementById("kpi-abstain").textContent = `${Math.round(b.overall_abstention_rate * 1000) / 10}%`;
        document.getElementById("kpi-accepted").textContent = `${Math.round(b.evaluated_accuracy_excluding_abstentions * 1000) / 10}%`;
      }
      if (p) {
        document.getElementById("kpi-delta").textContent = `+${Math.round(p.accuracy_delta * 1000) / 10}%`;
      }
    } catch (e) {
      console.warn("Could not load benchmark data:", e);
    }
  }

  // Toast System
  function showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(20px)";
      setTimeout(() => toast.remove(), 300);
    }, 3200);
  }
});

