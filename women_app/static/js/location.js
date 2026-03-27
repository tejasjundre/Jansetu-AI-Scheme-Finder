document.addEventListener("DOMContentLoaded", () => {
  const districtDataNode = document.getElementById("districtData");
  if (!districtDataNode) {
    return;
  }

  const districtMap = JSON.parse(districtDataNode.textContent || "{}");
  const districtLookup = {};
  Object.entries(districtMap).forEach(([stateName, districts]) => {
    districtLookup[normalizeKey(stateName)] = districts;
  });
  const stateSelects = Array.from(document.querySelectorAll("[data-state-select='true']"));

  function normalizeKey(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/&/g, "and")
      .replace(/[^a-z0-9]+/g, "");
  }

  function resolveDistricts(stateValue, stateLabel) {
    const exact = districtMap[stateValue];
    if (exact && Array.isArray(exact)) {
      return exact;
    }

    const normalized = districtLookup[normalizeKey(stateValue)];
    if (normalized && Array.isArray(normalized)) {
      return normalized;
    }

    const normalizedLabel = districtLookup[normalizeKey(stateLabel)];
    if (normalizedLabel && Array.isArray(normalizedLabel)) {
      return normalizedLabel;
    }

    return [];
  }

  function populateDistricts(stateSelect, districtSelect) {
    const placeholder = districtSelect.dataset.placeholder || districtSelect.options[0]?.textContent || "Select district";
    const stateValue = (stateSelect.value || "").trim();
    const selectedOption = stateSelect.options[stateSelect.selectedIndex];
    const stateLabel = (selectedOption?.textContent || "").trim();
    const districts = resolveDistricts(stateValue, stateLabel);
    const selectedValue = districtSelect.dataset.selectedValue || districtSelect.value;

    districtSelect.innerHTML = "";

    const placeholderOption = document.createElement("option");
    placeholderOption.value = "";
    placeholderOption.textContent = placeholder;
    districtSelect.appendChild(placeholderOption);

    districts.forEach((district) => {
      const option = document.createElement("option");
      option.value = district;
      option.textContent = district;
      if (district === selectedValue) {
        option.selected = true;
      }
      districtSelect.appendChild(option);
    });

    districtSelect.disabled = !districts.length;
    if (!districts.length) {
      districtSelect.value = "";
    }
  }

  stateSelects.forEach((stateSelect) => {
    const form = stateSelect.form || document;
    const districtSelect = form.querySelector("[data-district-select='true']");
    if (!districtSelect) {
      return;
    }

    districtSelect.dataset.placeholder = districtSelect.options[0]?.textContent || "Select district";
    districtSelect.dataset.selectedValue = districtSelect.value || "";
    populateDistricts(stateSelect, districtSelect);

    stateSelect.addEventListener("change", () => {
      districtSelect.dataset.selectedValue = "";
      populateDistricts(stateSelect, districtSelect);
    });
  });
});
