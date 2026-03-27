document.addEventListener("DOMContentLoaded", () => {
  const forms = Array.from(document.querySelectorAll("[data-help-center-form]"));
  if (!forms.length) {
    return;
  }

  function text(value, fallback = "") {
    const cleaned = String(value || "").trim();
    return cleaned || fallback;
  }

  function renderPreview(preview, center) {
    if (!preview || !center) {
      return;
    }
    const stateLabel = text(center.state, "Selected state");
    const districtLabel = text(center.district, "All districts");
    const officeName = text(center.office_name, "District Help Center");
    const address = text(center.address, "District administration office");
    const phone = text(center.phone, "Helpline not available");
    const hours = text(center.hours, "Office hours not available");
    const source = text(center.source_name, "Directory source");
    const mapUrl = text(center.map_url);
    const mapLink = mapUrl
      ? `<a href="${mapUrl}" target="_blank" rel="noopener noreferrer" class="text-link">Open on map</a>`
      : "";

    preview.innerHTML = `
      <h3>${officeName}</h3>
      <p class="small-muted">${stateLabel}${districtLabel ? `, ${districtLabel}` : ""}</p>
      <p>${address}</p>
      <p><strong>Phone:</strong> ${phone}</p>
      <p><strong>Hours:</strong> ${hours}</p>
      <p class="small-muted">Source: ${source}</p>
      ${mapLink}
    `;
  }

  async function fetchPreview(form, preview, stateValue, districtValue) {
    const apiUrl = form.dataset.helpApiUrl;
    if (!apiUrl) {
      return;
    }

    const params = new URLSearchParams();
    if (stateValue) {
      params.set("state", stateValue);
    }
    if (districtValue) {
      params.set("district", districtValue);
    }

    try {
      const response = await fetch(`${apiUrl}?${params.toString()}`, {
        method: "GET",
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      });
      if (!response.ok) {
        return;
      }
      const payload = await response.json();
      const firstCenter = (payload.centers || [])[0];
      if (firstCenter) {
        renderPreview(preview, firstCenter);
      }
    } catch (error) {
      console.error(error);
    }
  }

  forms.forEach((form) => {
    const preview = form.querySelector("[data-help-center-preview]");
    const stateSelect = form.querySelector("[data-state-select='true']");
    const districtSelect = form.querySelector("[data-district-select='true']");
    if (!preview || !stateSelect) {
      return;
    }

    const refresh = () => fetchPreview(form, preview, stateSelect.value, districtSelect ? districtSelect.value : "");

    stateSelect.addEventListener("change", refresh);
    if (districtSelect) {
      districtSelect.addEventListener("change", refresh);
    }
    refresh();
  });
});
