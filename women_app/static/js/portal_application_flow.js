document.addEventListener("DOMContentLoaded", () => {
  const shell = document.querySelector("[data-application-flow]");
  if (!shell) {
    return;
  }

  const form = document.getElementById("applicationForm");
  const panes = Array.from(shell.querySelectorAll("[data-app-step]"));
  const triggers = Array.from(shell.querySelectorAll("[data-app-trigger]"));
  const backBtn = document.getElementById("appBack");
  const nextBtn = document.getElementById("appNext");
  const submitBtn = document.getElementById("appSubmit");
  const schemeInput = form ? form.querySelector("#id_scheme_name") : null;
  const schemeChoices = Array.from(shell.querySelectorAll("[data-scheme-choice]"));
  const docsInput = document.getElementById("documentsInput");
  const docsPreview = document.getElementById("documentPreview");

  if (!form || !panes.length || !backBtn || !nextBtn || !submitBtn) {
    return;
  }

  const parsedInitial = Number.parseInt(shell.dataset.initialStep || "1", 10);
  let currentStep = Number.isNaN(parsedInitial) ? 0 : Math.max(0, parsedInitial - 1);

  function renderStep() {
    panes.forEach((pane, index) => {
      pane.classList.toggle("is-active", index === currentStep);
    });

    triggers.forEach((trigger, index) => {
      trigger.classList.toggle("is-active", index === currentStep);
    });

    backBtn.disabled = currentStep === 0;
    const isLast = currentStep === panes.length - 1;
    nextBtn.classList.toggle("d-none", isLast);
    submitBtn.classList.toggle("d-none", !isLast);
  }

  function validateCurrentStep() {
    const pane = panes[currentStep];
    if (!pane) {
      return true;
    }
    const fields = Array.from(pane.querySelectorAll("input, select, textarea")).filter((field) => {
      if (field.disabled || field.type === "hidden" || field.type === "button") {
        return false;
      }
      if (field.type === "file") {
        return false;
      }
      return true;
    });

    for (const field of fields) {
      if (!field.checkValidity()) {
        field.reportValidity();
        field.focus();
        return false;
      }
    }
    return true;
  }

  function renderDocumentPreview(files) {
    if (!docsPreview) {
      return;
    }
    docsPreview.innerHTML = "";
    if (!files || !files.length) {
      return;
    }
    Array.from(files).forEach((file) => {
      const item = document.createElement("div");
      item.className = "upload-preview-item";
      const sizeKb = Math.max(1, Math.round(file.size / 1024));
      item.textContent = `${file.name} (${sizeKb} KB)`;
      docsPreview.appendChild(item);
    });
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
    if (!validateCurrentStep()) {
      return;
    }
    if (currentStep < panes.length - 1) {
      currentStep += 1;
      renderStep();
    }
  });

  schemeChoices.forEach((button) => {
    button.addEventListener("click", () => {
      const value = button.dataset.schemeChoice || "";
      if (schemeInput && value) {
        schemeInput.value = value;
        schemeInput.focus();
      }
    });
  });

  if (docsInput) {
    docsInput.addEventListener("change", () => {
      renderDocumentPreview(docsInput.files);
    });
  }

  form.addEventListener("submit", () => {
    submitBtn.disabled = true;
    submitBtn.classList.add("is-loading");
  });

  renderStep();
});
