document.addEventListener("DOMContentLoaded", () => {
  const chatPanel = document.querySelector(".chat-panel");
  const sendBtn = document.getElementById("sendBtn");
  const userInput = document.getElementById("userInput");
  const chatBox = document.getElementById("chatBox");
  const recommendationBox = document.getElementById("chatRecommendations");
  const micBtn = document.getElementById("micBtn");
  const voiceToggle = document.getElementById("voiceToggle");
  const speechLangSelect = document.getElementById("speechLang");
  const promptButtons = Array.from(document.querySelectorAll("[data-prompt]"));
  const uiStringsElement = document.getElementById("uiStrings");

  if (!chatPanel || !sendBtn || !userInput || !chatBox || !recommendationBox) {
    return;
  }

  const uiStrings = uiStringsElement ? JSON.parse(uiStringsElement.textContent) : {};
  const chatUrl = chatPanel.dataset.chatUrl;
  const sttUrl = chatPanel.dataset.sttUrl || "";
  const ttsUrl = chatPanel.dataset.ttsUrl || "";
  const currentLang = chatPanel.dataset.currentLang || "en";
  let isSending = false;
  let autoSpeak = false;
  let recognition;
  let recognitionRunning = false;
  let activeSpeechLocales = [];
  let activeSpeechLocaleIndex = 0;
  let mediaRecorder;
  let mediaStream;
  let recordedChunks = [];
  let serverRecording = false;

  function getCookie(name) {
    const cookieValue = document.cookie
      .split(";")
      .map((item) => item.trim())
      .find((item) => item.startsWith(`${name}=`));
    return cookieValue ? decodeURIComponent(cookieValue.split("=")[1]) : "";
  }

  function activeUiLang() {
    return (speechLangSelect && speechLangSelect.value) || currentLang || "en";
  }

  function speechLocalesFor(lang) {
    if (lang === "hi") return ["hi-IN", "hi", "en-IN"];
    if (lang === "mr") return ["mr-IN", "mr", "hi-IN", "en-IN"];
    return ["en-IN", "en-US", "en"];
  }

  function primaryLocale() {
    const locales = speechLocalesFor(activeUiLang());
    return locales[0];
  }

  function setMicState(active) {
    if (!micBtn) {
      return;
    }
    micBtn.classList.toggle("is-active", active);
  }

  async function speakByServer(text) {
    if (!ttsUrl || !text) {
      return false;
    }
    try {
      const response = await fetch(ttsUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify({ text, lang: activeUiLang() }),
      });
      if (!response.ok) {
        return false;
      }
      const audioBlob = await response.blob();
      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);
      audio.addEventListener("ended", () => URL.revokeObjectURL(audioUrl), { once: true });
      await audio.play();
      return true;
    } catch (error) {
      console.error(error);
      return false;
    }
  }

  function speakText(text) {
    if (!text) {
      return;
    }

    if (window.speechSynthesis) {
      try {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = primaryLocale();
        window.speechSynthesis.speak(utterance);
        return;
      } catch (error) {
        console.error(error);
      }
    }
    speakByServer(text);
  }

  function appendMessage(text, sender) {
    const row = document.createElement("div");
    row.className = `message-row ${sender}-row`;

    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    avatar.textContent = sender === "bot" ? "AI" : "You";

    const bubble = document.createElement("div");
    bubble.className = `message ${sender}-message`;
    bubble.textContent = text;

    row.appendChild(avatar);
    row.appendChild(bubble);
    chatBox.appendChild(row);
    chatBox.scrollTop = chatBox.scrollHeight;

    if (sender === "bot" && autoSpeak) {
      speakText(text);
    }
  }

  function renderRecommendations(items) {
    recommendationBox.innerHTML = "";
    if (!items || !items.length) {
      return;
    }

    items.forEach((item) => {
      const card = document.createElement("article");
      card.className = "chat-recommendation-card";
      const detailLink = item.slug
        ? `<a href="/scheme/${item.slug}/?lang=${activeUiLang()}" class="text-link">${uiStrings.chat_open_details || "Open details"}</a>`
        : "";
      const officialLink = item.url
        ? `<a href="${item.url}" target="_blank" rel="noopener noreferrer" class="text-link">${uiStrings.chat_official_source || "Official source"}</a>`
        : "";

      card.innerHTML = `
        <strong>${item.name}</strong>
        <div class="small-muted">${item.category_label}</div>
        <div class="small-muted">${item.where_to_apply || ""}</div>
        <div class="small-muted">${item.helpline || ""}</div>
        ${detailLink}
        ${officialLink}
      `;
      recommendationBox.appendChild(card);
    });
  }

  function showTyping() {
    const row = document.createElement("div");
    row.className = "message-row bot-row";
    row.id = "typingIndicator";
    row.innerHTML = `
      <div class="message-avatar">AI</div>
      <div class="message bot-message">
        <div class="typing-shell">
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
        </div>
      </div>
    `;
    chatBox.appendChild(row);
    chatBox.scrollTop = chatBox.scrollHeight;
  }

  function removeTyping() {
    const indicator = document.getElementById("typingIndicator");
    if (indicator) {
      indicator.remove();
    }
  }

  async function sendMessage() {
    const text = userInput.value.trim();
    if (!text || isSending) {
      return;
    }

    isSending = true;
    sendBtn.disabled = true;
    sendBtn.classList.add("is-loading");
    renderRecommendations([]);
    appendMessage(text, "user");
    userInput.value = "";
    showTyping();

    try {
      const response = await fetch(chatUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify({ message: text, lang: activeUiLang() }),
      });

      const data = await response.json();
      removeTyping();

      if (!response.ok) {
        appendMessage(data.message || uiStrings.chat_error || "Something went wrong while checking the scheme list.", "bot");
      } else {
        appendMessage(data.reply || uiStrings.chat_retry || "I could not generate a reply just now. Please try again.", "bot");
        renderRecommendations(data.recommended_schemes || []);
        if (data.needs_human_review) {
          const note = document.createElement("article");
          note.className = "chat-recommendation-card";
          note.innerHTML = `<strong>${uiStrings.chat_human_title || "Need human help?"}</strong><div class="small-muted">${uiStrings.chat_human_text || "Open the Human Help page to request callback support."}</div><a href="/support/?lang=${activeUiLang()}" class="text-link">${uiStrings.support_request_link || "Request support"}</a>`;
          recommendationBox.appendChild(note);
        }
      }
    } catch (error) {
      removeTyping();
      appendMessage(uiStrings.chat_connection_failed || "The connection failed. Please retry in a moment.", "bot");
      console.error(error);
    } finally {
      isSending = false;
      sendBtn.disabled = false;
      sendBtn.classList.remove("is-loading");
      userInput.focus();
    }
  }

  async function transcribeBlob(blob) {
    if (!sttUrl || !blob) {
      return;
    }
    try {
      const formData = new FormData();
      formData.append("audio", blob, "voice.webm");
      formData.append("lang", activeUiLang());
      const response = await fetch(sttUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: formData,
      });
      const payload = await response.json();
      if (!response.ok) {
        appendMessage(uiStrings.chat_connection_failed || "Voice transcription failed. Please try again or type your message.", "bot");
        return;
      }
      const transcript = (payload.transcript || "").trim();
      if (transcript) {
        userInput.value = transcript;
        userInput.focus();
      }
    } catch (error) {
      console.error(error);
      appendMessage(uiStrings.chat_connection_failed || "Voice transcription failed. Please type your message.", "bot");
    }
  }

  async function ensureMediaRecorder() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !window.MediaRecorder) {
      return false;
    }
    if (!mediaStream) {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    }
    return true;
  }

  async function startServerRecording() {
    const available = await ensureMediaRecorder();
    if (!available || !sttUrl) {
      appendMessage("Voice input is not available on this browser. Please type your message.", "bot");
      return;
    }

    recordedChunks = [];
    mediaRecorder = new MediaRecorder(mediaStream);
    mediaRecorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) {
        recordedChunks.push(event.data);
      }
    };
    mediaRecorder.onstop = async () => {
      serverRecording = false;
      setMicState(false);
      if (micBtn) {
        micBtn.textContent = micBtn.dataset.defaultLabel || micBtn.textContent;
      }
      if (!recordedChunks.length) {
        return;
      }
      const audioBlob = new Blob(recordedChunks, { type: recordedChunks[0].type || "audio/webm" });
      await transcribeBlob(audioBlob);
    };

    serverRecording = true;
    mediaRecorder.start();
    setMicState(true);
    if (micBtn) {
      micBtn.textContent = uiStrings.voice_stop || "Stop";
    }

    setTimeout(() => {
      if (mediaRecorder && mediaRecorder.state === "recording") {
        mediaRecorder.stop();
      }
    }, 8000);
  }

  function stopServerRecording() {
    if (mediaRecorder && mediaRecorder.state === "recording") {
      mediaRecorder.stop();
    }
  }

  function initSpeechRecognition() {
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) {
      return;
    }

    recognition = new Recognition();
    activeSpeechLocales = speechLocalesFor(activeUiLang());
    activeSpeechLocaleIndex = 0;
    recognition.lang = activeSpeechLocales[activeSpeechLocaleIndex];
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.continuous = false;

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      userInput.value = transcript;
      userInput.focus();
      recognitionRunning = false;
      setMicState(false);
      if (micBtn) {
        micBtn.textContent = micBtn.dataset.defaultLabel || micBtn.textContent;
      }
    };

    recognition.onerror = (event) => {
      const retryable = new Set(["language-not-supported", "no-speech"]);
      if (retryable.has(event.error) && activeSpeechLocaleIndex < activeSpeechLocales.length - 1) {
        activeSpeechLocaleIndex += 1;
        recognition.lang = activeSpeechLocales[activeSpeechLocaleIndex];
        try {
          recognition.start();
          return;
        } catch (error) {
          console.error(error);
        }
      }
      recognitionRunning = false;
      setMicState(false);
      if (micBtn) {
        micBtn.textContent = micBtn.dataset.defaultLabel || micBtn.textContent;
      }
    };

    recognition.onend = () => {
      recognitionRunning = false;
      setMicState(false);
      if (micBtn) {
        micBtn.textContent = micBtn.dataset.defaultLabel || micBtn.textContent;
      }
    };
  }

  sendBtn.addEventListener("click", sendMessage);
  userInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  });

  if (voiceToggle) {
    voiceToggle.addEventListener("click", () => {
      autoSpeak = !autoSpeak;
      voiceToggle.classList.toggle("active-ghost", autoSpeak);
    });
  }

  if (micBtn) {
    micBtn.dataset.defaultLabel = micBtn.textContent;
  }

  initSpeechRecognition();

  if (micBtn) {
    micBtn.addEventListener("click", async () => {
      if (recognition) {
        if (recognitionRunning) {
          recognition.stop();
          recognitionRunning = false;
          setMicState(false);
          micBtn.textContent = micBtn.dataset.defaultLabel || micBtn.textContent;
          return;
        }
        activeSpeechLocales = speechLocalesFor(activeUiLang());
        activeSpeechLocaleIndex = 0;
        recognition.lang = activeSpeechLocales[activeSpeechLocaleIndex];
        micBtn.textContent = uiStrings.voice_listening || "Listening...";
        recognitionRunning = true;
        setMicState(true);
        try {
          recognition.start();
          return;
        } catch (error) {
          recognitionRunning = false;
          setMicState(false);
          micBtn.textContent = micBtn.dataset.defaultLabel || micBtn.textContent;
          console.error(error);
        }
      }

      if (serverRecording) {
        stopServerRecording();
        return;
      }
      await startServerRecording();
    });
  }

  if (speechLangSelect) {
    speechLangSelect.addEventListener("change", () => {
      if (recognition && recognitionRunning) {
        recognition.stop();
      }
      if (serverRecording) {
        stopServerRecording();
      }
      setMicState(false);
    });
  }

  promptButtons.forEach((button) => {
    button.addEventListener("click", () => {
      userInput.value = button.dataset.prompt || "";
      userInput.focus();
    });
  });

  appendMessage(uiStrings.chat_intro || "Share your age, income, state, and need. I will look for the most relevant schemes first.", "bot");
});
