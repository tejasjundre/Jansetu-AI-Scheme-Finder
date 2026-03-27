document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("wizardForm");
  const speakButtons = Array.from(document.querySelectorAll(".speak-block"));

  function speak(text) {
    if (!window.speechSynthesis || !text) {
      return;
    }

    const lang = document.body.dataset.lang || "en";
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = lang === "hi" ? "hi-IN" : lang === "mr" ? "mr-IN" : "en-IN";
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  }

  speakButtons.forEach((button) => {
    button.addEventListener("click", () => speak(button.dataset.speak || ""));
  });

  if (!form) {
    return;
  }

  const steps = Array.from(form.querySelectorAll(".wizard-step"));
  const triggers = Array.from(form.querySelectorAll("[data-step-trigger]"));
  const backBtn = document.getElementById("wizardBack");
  const nextBtn = document.getElementById("wizardNext");
  const submitBtn = document.getElementById("wizardSubmit");
  const focusCards = Array.from(form.querySelectorAll("[data-focus-card]"));
  const focusRadios = Array.from(form.querySelectorAll("[data-focus-radio]"));
  const focusError = form.querySelector("[data-focus-error]");
  const progressFill = document.getElementById("wizardProgressFill");
  const currentStepLabel = document.getElementById("wizardCurrentStepLabel");

  if (!steps.length || !backBtn || !nextBtn || !submitBtn) {
    return;
  }

  form.classList.add("is-enhanced");

  const parsedInitialStep = Number.parseInt(form.dataset.initialStep || "1", 10);
  let currentStep = Number.isNaN(parsedInitialStep) ? 0 : Math.max(0, parsedInitialStep - 1);

  function renderFocusCards() {
    focusCards.forEach((card) => {
      const radio = card.querySelector("[data-focus-radio]");
      card.classList.toggle("is-selected", Boolean(radio && radio.checked));
    });
  }

  function validateFocusSelection(step) {
    const group = step.querySelector("[data-focus-group]");
    if (!group) {
      return true;
    }

    const selected = group.querySelector("[data-focus-radio]:checked");
    const isValid = Boolean(selected);

    if (focusError) {
      focusError.classList.toggle("d-none", isValid);
    }

    if (!isValid) {
      const firstRadio = group.querySelector("[data-focus-radio]");
      if (firstRadio) {
        firstRadio.focus();
      }
    }

    return isValid;
  }

  function renderStep() {
    steps.forEach((step, index) => {
      step.classList.toggle("active", index === currentStep);
    });

    triggers.forEach((trigger, index) => {
      trigger.classList.toggle("active", index === currentStep);
    });

    backBtn.disabled = currentStep === 0;
    nextBtn.classList.toggle("d-none", currentStep === steps.length - 1);
    submitBtn.classList.toggle("d-none", currentStep !== steps.length - 1);

    if (progressFill) {
      progressFill.style.width = `${((currentStep + 1) / steps.length) * 100}%`;
    }

    if (currentStepLabel) {
      currentStepLabel.textContent = triggers[currentStep]?.dataset.stepLabel || triggers[currentStep]?.textContent || "";
    }

    form.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  triggers.forEach((trigger, index) => {
    trigger.addEventListener("click", () => {
      currentStep = index;
      renderStep();
    });
  });

  backBtn.addEventListener("click", () => {
    if (currentStep > 0) {
      currentStep -= 1;
      renderStep();
    }
  });

  nextBtn.addEventListener("click", () => {
    const currentStepElement = steps[currentStep];
    if (!validateFocusSelection(currentStepElement)) {
      return;
    }

    const currentFields = Array.from(currentStepElement.querySelectorAll("input, select, textarea"))
      .filter((field) => field.type !== "hidden" && field.type !== "radio" && !field.disabled);

    const hasInvalidField = currentFields.some((field) => !field.checkValidity());
    if (hasInvalidField) {
      const firstInvalid = currentFields.find((field) => !field.checkValidity());
      if (firstInvalid) {
        firstInvalid.reportValidity();
        firstInvalid.focus();
      }
      return;
    }

    if (currentStep < steps.length - 1) {
      currentStep += 1;
      renderStep();
    }
  });

  focusRadios.forEach((radio) => {
    radio.addEventListener("change", () => {
      renderFocusCards();
      if (focusError) {
        focusError.classList.add("d-none");
      }
    });
  });

  form.addEventListener("submit", () => {
    submitBtn.disabled = true;
    submitBtn.classList.add("is-loading");
  });

  renderFocusCards();
  renderStep();
});
