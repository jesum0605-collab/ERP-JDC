(function () {
  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;").replaceAll("'", "&#039;");

  function itemMeta(item) {
    return [item.code, item.position, item.location, item.client_name, item.status]
      .filter(Boolean).join(" · ");
  }

  function renderContext(target, payload) {
    if (!target || !payload || !payload.record) return;
    const record = payload.record;
    const blocks = [];
    if (record.client_name || record.location || record.manager_name) {
      blocks.push(`<div><strong>${escapeHtml(record.client_name || "Sin cliente")}</strong> · ${escapeHtml(record.location || "Sin ubicación")}<br><span class="text-muted">Responsable: ${escapeHtml(record.manager_name || "Sin asignar")}</span></div>`);
    } else if (record.position || record.email || record.phone) {
      blocks.push(`<div><strong>${escapeHtml(record.position || "Sin cargo")}</strong><br><span class="text-muted">${escapeHtml(record.email || "Sin correo")} · ${escapeHtml(record.phone || "Sin teléfono")}</span></div>`);
    }
    if (payload.phases?.length) blocks.push(`<div><span class="fw-semibold">Fases:</span> ${payload.phases.map((x) => escapeHtml(x.name) + " (" + Number(x.progress_percent || 0).toFixed(0) + "%)").join(" · ")}</div>`);
    if (payload.resources?.length) blocks.push(`<div><span class="fw-semibold">Recursos:</span> ${payload.resources.map((x) => escapeHtml(x.name)).join(" · ")}</div>`);
    if (payload.projects?.length) blocks.push(`<div><span class="fw-semibold">Proyectos:</span> ${payload.projects.map((x) => escapeHtml(x.code + " · " + x.name)).join(" · ")}</div>`);
    if (payload.incidents?.length) blocks.push(`<div><span class="fw-semibold">Incidentes relacionados:</span> ${payload.incidents.length}</div>`);
    target.innerHTML = blocks.length ? `<div class="linked-context small">${blocks.join("<hr class=\"my-2\">")}</div>` : "";
    target.hidden = !blocks.length;
  }

  function initLookup(control) {
    const input = control.querySelector("[data-lookup-input]");
    const hidden = control.querySelector("input[type=hidden]");
    const results = control.querySelector(".lookup-results");
    if (!input || !hidden || !results) return;
    let timer;
    let requestId = 0;
    const contextTarget = document.querySelector(control.dataset.contextTarget || "");

    const loadContext = (item) => {
      const template = control.dataset.contextUrl;
      if (!template || !contextTarget || !item?.id) return;
      const url = template.replace(/\/0\/context$/, `/${item.id}/context`);
      fetch(url, {headers: {"Accept": "application/json"}})
        .then((response) => response.ok ? response.json() : null)
        .then((payload) => renderContext(contextTarget, payload))
        .catch(() => {});
    };

    const search = () => {
      const term = input.value.trim();
      if (term.length < 1) { results.innerHTML = ""; results.hidden = true; return; }
      const current = ++requestId;
      fetch(`${control.dataset.lookupUrl}?q=${encodeURIComponent(term)}`, {headers: {"Accept": "application/json"}})
        .then((response) => response.ok ? response.json() : {items: []})
        .then((payload) => {
          if (current !== requestId) return;
          results.innerHTML = (payload.items || []).map((item) => `<button type="button" class="lookup-result" data-id="${escapeHtml(item.id)}"><span>${escapeHtml(item.label)}</span><small>${escapeHtml(itemMeta(item))}</small></button>`).join("");
          results.hidden = !(payload.items || []).length;
          results.querySelectorAll("[data-id]").forEach((button, index) => {
            button.addEventListener("click", () => {
              const item = payload.items[index];
              hidden.value = item.id;
              input.value = item.label;
              results.innerHTML = "";
              results.hidden = true;
              input.dispatchEvent(new CustomEvent("record:selected", {detail: item}));
              loadContext(item);
            });
          });
        }).catch(() => { results.innerHTML = ""; results.hidden = true; });
    };
    input.addEventListener("input", () => { hidden.value = ""; clearTimeout(timer); timer = setTimeout(search, 180); });
    input.addEventListener("focus", search);
    document.addEventListener("click", (event) => { if (!control.contains(event.target)) results.hidden = true; });
  }

  function initSelectFilters() {
    document.querySelectorAll("select").forEach((select) => {
      if (select.dataset.noFilter !== undefined || select.options.length < 8 || select.previousElementSibling?.matches("[data-select-filter]")) return;
      const input = document.createElement("input");
      input.className = "form-control form-control-sm mb-2";
      input.placeholder = "Buscar en la lista";
      input.dataset.selectFilter = `#${select.id || ""}`;
      if (!select.id) {
        select.id = `lookup-select-${Math.random().toString(36).slice(2)}`;
        input.dataset.selectFilter = `#${select.id}`;
      }
      select.parentNode.insertBefore(input, select);
    });
    document.querySelectorAll("[data-select-filter]").forEach((input) => {
      const select = document.querySelector(input.dataset.selectFilter);
      if (!select) return;
      input.addEventListener("input", () => {
        const term = input.value.trim().toLowerCase();
        select.querySelectorAll("option").forEach((option) => {
          option.hidden = Boolean(term) && !option.textContent.toLowerCase().includes(term);
        });
      });
    });
  }

  function initReferenceInputs() {
    document.querySelectorAll("[data-reference-catalog]").forEach((input) => {
      const catalog = input.dataset.referenceCatalog;
      const listId = `reference-list-${catalog}-${Math.random().toString(36).slice(2)}`;
      const datalist = document.createElement("datalist");
      datalist.id = listId;
      input.setAttribute("list", listId);
      input.parentNode.appendChild(datalist);
      let timer;
      const load = () => {
        clearTimeout(timer);
        timer = setTimeout(() => fetch(`/api/lookups/references/${encodeURIComponent(catalog)}?q=${encodeURIComponent(input.value.trim())}`)
          .then((response) => response.ok ? response.json() : {items: []})
          .then((payload) => {
            datalist.innerHTML = (payload.items || []).map((item) => `<option value="${escapeHtml(item.name)}" label="${escapeHtml(item.code)}"></option>`).join("");
          }).catch(() => {}), 120);
      };
      input.addEventListener("focus", load);
      input.addEventListener("input", load);
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".record-lookup").forEach(initLookup);
    initSelectFilters();
    initReferenceInputs();
  });
})();
