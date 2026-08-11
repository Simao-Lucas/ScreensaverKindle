(() => {
  const folderTree = document.getElementById("folderTree");
  const explorerBody = document.getElementById("explorerBody");
  const emptyHint = document.getElementById("emptyHint");
  const breadcrumb = document.getElementById("breadcrumb");
  const listMessage = document.getElementById("listMessage");
  const detailPanel = document.getElementById("detailPanel");
  const detailFile = document.getElementById("detailFile");
  const detailMessage = document.getElementById("detailMessage");
  const membership = document.getElementById("membership");
  const dCoverPreview = document.getElementById("dCoverPreview");
  const dCoverFrame = document.getElementById("dCoverFrame");
  const dCoverInput = document.getElementById("dCoverInput");
  const dFilename = document.getElementById("dFilename");
  const toggleFavBtn = document.getElementById("toggleFavBtn");
  const contextMenu = document.getElementById("contextMenu");
  const cutBtn = document.getElementById("cutBtn");
  const pasteBtn = document.getElementById("pasteBtn");
  const editBtn = document.getElementById("editBtn");
  const renameBtn = document.getElementById("renameBtn");
  const deleteBtn = document.getElementById("deleteBtn");
  const upBtn = document.getElementById("upBtn");
  const selectAll = document.getElementById("selectAll");

  const fields = {
    title: document.getElementById("dTitle"),
    authors: document.getElementById("dAuthors"),
    publisher: document.getElementById("dPublisher"),
    series: document.getElementById("dSeries"),
    tags: document.getElementById("dTags"),
    language: document.getElementById("dLanguage"),
    comments: document.getElementById("dComments"),
  };

  let currentPath = "";
  let entries = [];
  let collections = [];
  let current = null;
  let selectedRels = new Set();
  let lastClickedRel = null;
  let clipboard = null;
  let contextTarget = null;
  let pendingCoverFile = null;
  let pendingCoverUrl = null;

  function setListMessage(text, type = "") {
    listMessage.textContent = text || "";
    listMessage.className = `message${type ? ` ${type}` : ""}`;
  }

  function setDetailMessage(text, type = "") {
    detailMessage.textContent = text || "";
    detailMessage.className = `message${type ? ` ${type}` : ""}`;
  }

  function collectFields() {
    const out = {};
    for (const [k, el] of Object.entries(fields)) out[k] = el.value.trim();
    return out;
  }

  function fillFields(meta = {}) {
    for (const [k, el] of Object.entries(fields)) el.value = meta[k] || "";
  }

  function formatSize(bytes) {
    if (!bytes) return "—";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function parentPath(path) {
    if (!path) return "";
    const parts = path.split("/").filter(Boolean);
    parts.pop();
    return parts.join("/");
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function showCover(name, hasCover) {
    if (pendingCoverUrl) {
      dCoverPreview.hidden = false;
      dCoverPreview.src = pendingCoverUrl;
      dCoverFrame.dataset.empty = "false";
      return;
    }
    if (!hasCover) {
      dCoverPreview.hidden = true;
      dCoverPreview.removeAttribute("src");
      dCoverFrame.dataset.empty = "true";
      return;
    }
    dCoverPreview.hidden = false;
    dCoverPreview.src = `/library/cover/${name.split("/").map(encodeURIComponent).join("/")}?t=${Date.now()}`;
    dCoverFrame.dataset.empty = "false";
  }

  function clearPendingCover() {
    if (pendingCoverUrl) URL.revokeObjectURL(pendingCoverUrl);
    pendingCoverFile = null;
    pendingCoverUrl = null;
  }

  function bookUrl(name, suffix = "") {
    const parts = name.split("/").map(encodeURIComponent).join("/");
    return `/api/library/books/${parts}${suffix}`;
  }

  function selectedEntries() {
    return entries.filter((e) => selectedRels.has(e.rel));
  }

  function primarySelected() {
    const list = selectedEntries();
    if (!list.length) return null;
    if (lastClickedRel) {
      const hit = list.find((e) => e.rel === lastClickedRel);
      if (hit) return hit;
    }
    return list[0];
  }

  function setSelection(rels, { anchor } = {}) {
    selectedRels = new Set(rels);
    if (anchor !== undefined) lastClickedRel = anchor;
    renderEntries();
  }

  function updateActionUi() {
    const selected = selectedEntries();
    const count = selected.length;
    const one = count === 1 ? selected[0] : null;
    cutBtn.disabled = count === 0;
    pasteBtn.disabled = !clipboard || !clipboard.sources.length;
    renameBtn.disabled = count !== 1;
    deleteBtn.disabled = count === 0;
    editBtn.disabled = !(one && one.type === "file");
    if (selectAll) {
      selectAll.checked = entries.length > 0 && count === entries.length;
      selectAll.indeterminate = count > 0 && count < entries.length;
    }
  }

  function hideContext() {
    contextMenu.hidden = true;
    contextTarget = null;
  }

  function showContext(x, y, entry) {
    contextTarget = entry;
    const editItem = contextMenu.querySelector('[data-action="edit"]');
    if (editItem) editItem.hidden = !(entry && entry.type === "file");
    contextMenu.hidden = false;
    contextMenu.style.left = `${Math.min(x, window.innerWidth - 180)}px`;
    contextMenu.style.top = `${Math.min(y, window.innerHeight - 240)}px`;
  }

  function renderBreadcrumb(crumbs) {
    breadcrumb.innerHTML = "";
    const root = document.createElement("button");
    root.type = "button";
    root.className = "crumb";
    root.dataset.rel = "";
    root.textContent = "documents";
    breadcrumb.appendChild(root);
    crumbs.forEach((c) => {
      const sep = document.createElement("span");
      sep.className = "crumb-sep";
      sep.textContent = "/";
      breadcrumb.appendChild(sep);
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "crumb";
      btn.dataset.rel = c.rel;
      btn.textContent = c.name;
      breadcrumb.appendChild(btn);
    });
    upBtn.disabled = !currentPath;
  }

  function renderTreeNode(node, depth = 0) {
    const wrap = document.createElement("div");
    wrap.className = "tree-node";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "tree-item";
    if ((node.rel || "") === currentPath) btn.classList.add("is-active");
    btn.dataset.rel = node.rel || "";
    btn.style.paddingLeft = `${0.5 + depth * 0.85}rem`;
    btn.innerHTML = `<span class="tree-icon" aria-hidden="true"></span> <span>${escapeHtml(node.name)}</span>`;
    btn.addEventListener("dragover", (e) => {
      e.preventDefault();
      btn.classList.add("drop-target");
    });
    btn.addEventListener("dragleave", () => btn.classList.remove("drop-target"));
    btn.addEventListener("drop", async (e) => {
      e.preventDefault();
      btn.classList.remove("drop-target");
      const raw = e.dataTransfer.getData("text/plain");
      const sources = raw.split("\n").map((s) => s.trim()).filter(Boolean);
      if (sources.length) await moveTo(sources, node.rel || "");
    });
    wrap.appendChild(btn);
    (node.children || []).forEach((child) => {
      wrap.appendChild(renderTreeNode(child, depth + 1));
    });
    return wrap;
  }

  function renderTree(tree) {
    folderTree.innerHTML = "";
    if (!tree) {
      folderTree.innerHTML = `<p class="field-hint">Sem pastas.</p>`;
      return;
    }
    folderTree.appendChild(renderTreeNode(tree, 0));
  }

  function renderEntries() {
    explorerBody.innerHTML = "";
    emptyHint.hidden = entries.length > 0;
    entries.forEach((entry) => {
      const tr = document.createElement("tr");
      tr.className = "explorer-row";
      if (selectedRels.has(entry.rel)) tr.classList.add("is-selected");
      tr.dataset.rel = entry.rel;
      tr.dataset.type = entry.type;
      tr.draggable = true;
      const typeLabel =
        entry.type === "dir" ? "Pasta" : (entry.name.split(".").pop() || "arquivo").toUpperCase();
      const star = entry.favorite ? " ★" : "";
      const title = escapeHtml((entry.title || entry.name) + star);
      const fileName = escapeHtml(entry.name);
      const showFile = entry.type === "file" && entry.title && entry.title !== entry.name;
      const editBtnHtml =
        entry.type === "file"
          ? `<button type="button" class="btn ghost row-action" data-row-edit="${escapeHtml(entry.rel)}">Editar</button>`
          : "";
      tr.innerHTML = `
        <td class="col-check">
          <input type="checkbox" class="row-check" data-rel="${escapeHtml(entry.rel)}" ${selectedRels.has(entry.rel) ? "checked" : ""} aria-label="Selecionar ${fileName}" />
        </td>
        <td class="col-name">
          <div class="name-cell">
            <span class="entry-icon entry-icon-${entry.type}" aria-hidden="true"></span>
            <span class="entry-text">
              <span class="entry-label">${title}</span>
              ${showFile ? `<span class="entry-file">${fileName}</span>` : ""}
            </span>
          </div>
        </td>
        <td>${typeLabel}</td>
        <td>${entry.type === "dir" ? "—" : formatSize(entry.size)}</td>
        <td class="col-actions">
          <div class="actions-cell">
            ${editBtnHtml}
            <button type="button" class="btn ghost danger-text row-action" data-row-del="${escapeHtml(entry.rel)}" data-row-type="${entry.type}">Excluir</button>
          </div>
        </td>`;
      explorerBody.appendChild(tr);
    });
    updateActionUi();
  }

  async function loadCollections() {
    const res = await fetch("/api/library/collections");
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || "Falha ao ler coleções");
    collections = data.collections || [];
  }

  async function loadTree() {
    const res = await fetch("/api/library/tree");
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || "Falha na árvore");
    renderTree(data.tree);
  }

  async function browse(path = "") {
    setListMessage("Carregando…");
    currentPath = path || "";
    selectedRels = new Set();
    lastClickedRel = null;
    const res = await fetch(`/api/library/browse?path=${encodeURIComponent(currentPath)}`);
    const data = await res.json();
    if (!res.ok || !data.ok) {
      setListMessage(data.error || "Falha ao listar.", "error");
      entries = [];
      renderEntries();
      return;
    }
    entries = data.entries || [];
    renderBreadcrumb(data.crumbs || []);
    renderEntries();
    folderTree.querySelectorAll(".tree-item").forEach((el) => {
      el.classList.toggle("is-active", (el.dataset.rel || "") === currentPath);
    });
    const dirs = entries.filter((e) => e.type === "dir").length;
    const files = entries.filter((e) => e.type === "file").length;
    setListMessage(`${dirs} pasta(s), ${files} livro(s).`, "ok");
  }

  async function refreshAll() {
    await loadCollections();
    await loadTree();
    await browse(currentPath);
  }

  async function moveTo(sources, destRel) {
    const list = Array.isArray(sources) ? sources.filter(Boolean) : [sources].filter(Boolean);
    if (!list.length) return;
    for (const sourceRel of list) {
      if (sourceRel === destRel || destRel.startsWith(sourceRel + "/")) {
        setListMessage("Não é possível mover para dentro de si.", "error");
        return;
      }
    }
    setListMessage("Movendo…");
    const r = await fetch("/api/library/move", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sources: list, dest: destRel }),
    });
    const d = await r.json();
    if (!r.ok || !d.ok) {
      setListMessage(d.error || "Falha ao mover.", "error");
      return;
    }
    clipboard = null;
    await refreshAll();
    setListMessage(d.message || "Movido.", "ok");
  }

  function renderMembership() {
    membership.innerHTML = "<p class='field-label'>Coleções</p>";
    const wrap = document.createElement("div");
    wrap.className = "membership-toggles";
    collections.forEach((c) => {
      const id = `mem-${c.name}`;
      const checked = (current.collections || []).includes(c.name);
      const label = document.createElement("label");
      label.className = "check-row";
      label.innerHTML = `<input type="checkbox" id="${id}" data-coll="${escapeHtml(c.name)}" ${checked ? "checked" : ""}/> <span>${c.name === "favorites" ? "Favoritos" : escapeHtml(c.name)}</span>`;
      wrap.appendChild(label);
    });
    membership.appendChild(wrap);
    wrap.querySelectorAll("input[type=checkbox]").forEach((input) => {
      input.addEventListener("change", async () => {
        const coll = input.dataset.coll;
        const action = input.checked ? "add" : "remove";
        const r = await fetch(`/api/library/collections/${encodeURIComponent(coll)}/books`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: current.path, action }),
        });
        const d = await r.json();
        if (!r.ok || !d.ok) {
          input.checked = !input.checked;
          setDetailMessage(d.error || "Falha na coleção.", "error");
          return;
        }
        collections = d.collections || collections;
        current.collections = collections
          .filter((c) => (c.files || []).includes(current.path))
          .map((c) => c.name);
        current.favorite = current.collections.includes("favorites");
        setDetailMessage("Coleção atualizada. Reinicie o KOReader para ver no aparelho.", "ok");
        if (coll === "favorites") {
          toggleFavBtn.textContent = input.checked ? "Remover dos favoritos" : "Adicionar aos favoritos";
        }
      });
    });
  }

  async function openBook(name) {
    clearPendingCover();
    setDetailMessage("Abrindo…");
    detailPanel.hidden = false;
    detailPanel.scrollIntoView({ behavior: "smooth", block: "start" });
    const res = await fetch(bookUrl(name));
    const data = await res.json();
    if (!res.ok || !data.ok) {
      setDetailMessage(data.error || "Falha.", "error");
      return;
    }
    current = data.book;
    detailFile.textContent = current.path;
    dFilename.value = current.name.split("/").pop();
    fillFields(current.metadata || {});
    showCover(current.name, current.has_cover);
    toggleFavBtn.textContent = current.favorite ? "Remover dos favoritos" : "Adicionar aos favoritos";
    renderMembership();
    setDetailMessage("");
  }

  async function applyMetadataOnly() {
    if (!current) return false;
    const r = await fetch(bookUrl(current.name, "/metadata"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(collectFields()),
    });
    const d = await r.json();
    if (!r.ok || !d.ok) {
      setDetailMessage(d.error || "Falha ao salvar metadados.", "error");
      return false;
    }
    current = d.book;
    return true;
  }

  async function applyPendingCover() {
    if (!current || !pendingCoverFile) return true;
    const body = new FormData();
    body.append("cover", pendingCoverFile);
    const r = await fetch(bookUrl(current.name, "/cover"), { method: "POST", body });
    const d = await r.json();
    if (!r.ok || !d.ok) {
      setDetailMessage(d.error || "Falha na capa.", "error");
      return false;
    }
    current = d.book;
    clearPendingCover();
    showCover(current.name, true);
    return true;
  }

  async function applyRenameIfNeeded() {
    if (!current) return false;
    const newName = (dFilename.value || "").trim();
    const oldName = current.name.split("/").pop();
    if (!newName || newName === oldName) return true;
    const r = await fetch("/api/library/rename", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: current.name, new_name: newName }),
    });
    const d = await r.json();
    if (!r.ok || !d.ok) {
      setDetailMessage(d.error || "Falha ao renomear arquivo.", "error");
      return false;
    }
    current = await (async () => {
      const res = await fetch(bookUrl(d.rel));
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || "Falha ao recarregar livro");
      return data.book;
    })();
    detailFile.textContent = current.path;
    dFilename.value = current.name.split("/").pop();
    return true;
  }

  async function saveAllToKindle() {
    if (!current) return;
    setDetailMessage("Salvando no Kindle…");
    try {
      if (!(await applyRenameIfNeeded())) return;
      if (!(await applyMetadataOnly())) return;
      if (!(await applyPendingCover())) return;
      showCover(current.name, current.has_cover);
      toggleFavBtn.textContent = current.favorite ? "Remover dos favoritos" : "Adicionar aos favoritos";
      renderMembership();
      setDetailMessage("Salvo no Kindle (nome, metadados e capa).", "ok");
      await refreshAll();
      setSelection([current.name], { anchor: current.name });
    } catch (err) {
      setDetailMessage(err.message || "Falha ao salvar.", "error");
    }
  }

  async function createFolder() {
    const name = prompt("Nome da nova pasta:");
    if (!name || !name.trim()) return;
    const r = await fetch("/api/library/folders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ parent: currentPath, name: name.trim() }),
    });
    const d = await r.json();
    if (!r.ok || !d.ok) {
      setListMessage(d.error || "Falha ao criar pasta.", "error");
      return;
    }
    await refreshAll();
    setListMessage(d.message || "Pasta criada.", "ok");
  }

  async function renameSelected(rel) {
    const entry = entries.find((e) => e.rel === rel) || { name: rel.split("/").pop(), rel };
    const neu = prompt("Novo nome:", entry.name);
    if (!neu || neu === entry.name) return;
    const r = await fetch("/api/library/rename", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: rel, new_name: neu.trim() }),
    });
    const d = await r.json();
    if (!r.ok || !d.ok) {
      setListMessage(d.error || "Falha ao renomear.", "error");
      return;
    }
    if (current && current.name === rel) {
      await openBook(d.rel);
    }
    await refreshAll();
    setListMessage("Renomeado.", "ok");
  }

  async function deleteEntries(items) {
    if (!items.length) return;
    const label =
      items.length === 1
        ? items[0].type === "dir"
          ? `Apagar a pasta "${items[0].name}" e todo o conteúdo?`
          : `Excluir "${items[0].name}" e a pasta .sdr?`
        : `Excluir ${items.length} itens selecionados?`;
    if (!confirm(label)) return;

    let failed = null;
    for (const item of items) {
      const r = await fetch(`/api/library/entry?path=${encodeURIComponent(item.rel)}`, {
        method: "DELETE",
      });
      const d = await r.json();
      if (!r.ok || !d.ok) {
        failed = d.error || `Falha ao excluir ${item.name}`;
        break;
      }
      if (current && (current.name === item.rel || current.name.startsWith(item.rel + "/"))) {
        current = null;
        clearPendingCover();
        detailPanel.hidden = true;
      }
    }
    selectedRels = new Set();
    lastClickedRel = null;
    await refreshAll();
    if (failed) setListMessage(failed, "error");
    else setListMessage(items.length === 1 ? "Excluído." : `${items.length} itens excluídos.`, "ok");
  }

  function deleteCurrentSelection() {
    return deleteEntries(selectedEntries());
  }

  function selectRange(fromRel, toRel) {
    const i0 = entries.findIndex((e) => e.rel === fromRel);
    const i1 = entries.findIndex((e) => e.rel === toRel);
    if (i0 < 0 || i1 < 0) return [toRel];
    const a = Math.min(i0, i1);
    const b = Math.max(i0, i1);
    return entries.slice(a, b + 1).map((e) => e.rel);
  }

  function applyRowClick(rel, { ctrl, shift, fromCheckbox } = {}) {
    if (shift && lastClickedRel) {
      setSelection(selectRange(lastClickedRel, rel), { anchor: lastClickedRel });
      return;
    }
    if (ctrl || fromCheckbox) {
      const next = new Set(selectedRels);
      if (next.has(rel)) next.delete(rel);
      else next.add(rel);
      setSelection([...next], { anchor: rel });
      return;
    }
    setSelection([rel], { anchor: rel });
  }

  // --- events ---

  breadcrumb.addEventListener("click", (e) => {
    const crumb = e.target.closest(".crumb");
    if (crumb) browse(crumb.dataset.rel || "");
  });

  folderTree.addEventListener("click", (e) => {
    const item = e.target.closest(".tree-item");
    if (item) browse(item.dataset.rel || "");
  });

  upBtn.addEventListener("click", () => browse(parentPath(currentPath)));
  document.getElementById("refreshBtn").addEventListener("click", () =>
    refreshAll().catch((err) => setListMessage(err.message, "error"))
  );
  document.getElementById("newFolderBtn").addEventListener("click", createFolder);

  if (selectAll) {
    selectAll.addEventListener("change", () => {
      if (selectAll.checked) setSelection(entries.map((e) => e.rel));
      else setSelection([]);
    });
  }

  editBtn.addEventListener("click", () => {
    const entry = primarySelected();
    if (entry && entry.type === "file") openBook(entry.rel);
  });
  renameBtn.addEventListener("click", () => {
    const entry = primarySelected();
    if (entry) renameSelected(entry.rel);
  });
  deleteBtn.addEventListener("click", () => deleteCurrentSelection());

  cutBtn.addEventListener("click", () => {
    const selected = selectedEntries();
    if (!selected.length) return;
    clipboard = { sources: selected.map((e) => e.rel) };
    updateActionUi();
    setListMessage(
      selected.length === 1 ? `Recortado: ${selected[0].rel}` : `Recortados: ${selected.length} itens`,
      "ok"
    );
  });

  pasteBtn.addEventListener("click", async () => {
    if (!clipboard || !clipboard.sources.length) return;
    setListMessage("Colando…");
    const r = await fetch("/api/library/move", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sources: clipboard.sources, dest: currentPath }),
    });
    const d = await r.json();
    if (!r.ok || !d.ok) {
      setListMessage(d.error || "Falha ao colar.", "error");
      return;
    }
    clipboard = null;
    await refreshAll();
    setListMessage("Colado.", "ok");
  });

  explorerBody.addEventListener("click", (e) => {
    const edit = e.target.closest("[data-row-edit]");
    if (edit) {
      e.stopPropagation();
      setSelection([edit.dataset.rowEdit], { anchor: edit.dataset.rowEdit });
      openBook(edit.dataset.rowEdit);
      return;
    }
    const del = e.target.closest("[data-row-del]");
    if (del) {
      e.stopPropagation();
      const entry = entries.find((x) => x.rel === del.dataset.rowDel);
      if (entry) deleteEntries([entry]);
      return;
    }
    const check = e.target.closest(".row-check");
    if (check) {
      e.stopPropagation();
      applyRowClick(check.dataset.rel, {
        ctrl: e.ctrlKey || e.metaKey,
        shift: e.shiftKey,
        fromCheckbox: true,
      });
      return;
    }
    const row = e.target.closest(".explorer-row");
    if (!row) return;
    applyRowClick(row.dataset.rel, { ctrl: e.ctrlKey || e.metaKey, shift: e.shiftKey });
  });

  explorerBody.addEventListener("dblclick", (e) => {
    if (e.target.closest(".row-action") || e.target.closest(".row-check")) return;
    const row = e.target.closest(".explorer-row");
    if (!row) return;
    if (row.dataset.type === "dir") browse(row.dataset.rel);
    else openBook(row.dataset.rel);
  });

  explorerBody.addEventListener("contextmenu", (e) => {
    const row = e.target.closest(".explorer-row");
    e.preventDefault();
    if (row) {
      if (!selectedRels.has(row.dataset.rel)) {
        setSelection([row.dataset.rel], { anchor: row.dataset.rel });
      } else {
        renderEntries();
      }
      const entry = entries.find((x) => x.rel === row.dataset.rel);
      showContext(e.clientX, e.clientY, entry);
    } else {
      showContext(e.clientX, e.clientY, { type: "pane", rel: currentPath });
    }
  });

  document.querySelector(".explorer-table-wrap").addEventListener("contextmenu", (e) => {
    if (e.target.closest(".explorer-row")) return;
    e.preventDefault();
    showContext(e.clientX, e.clientY, { type: "pane", rel: currentPath });
  });

  explorerBody.addEventListener("dragstart", (e) => {
    const row = e.target.closest(".explorer-row");
    if (!row) return;
    if (!selectedRels.has(row.dataset.rel)) {
      setSelection([row.dataset.rel], { anchor: row.dataset.rel });
    }
    const sources = selectedRels.has(row.dataset.rel)
      ? [...selectedRels]
      : [row.dataset.rel];
    e.dataTransfer.setData("text/plain", sources.join("\n"));
    e.dataTransfer.effectAllowed = "move";
    row.classList.add("is-dragging");
  });

  explorerBody.addEventListener("dragend", (e) => {
    const row = e.target.closest(".explorer-row");
    if (row) row.classList.remove("is-dragging");
  });

  explorerBody.addEventListener("dragover", (e) => {
    const row = e.target.closest(".explorer-row");
    if (row && row.dataset.type === "dir") {
      e.preventDefault();
      row.classList.add("drop-target");
    }
  });

  explorerBody.addEventListener("dragleave", (e) => {
    const row = e.target.closest(".explorer-row");
    if (row) row.classList.remove("drop-target");
  });

  explorerBody.addEventListener("drop", async (e) => {
    const row = e.target.closest(".explorer-row");
    if (!row || row.dataset.type !== "dir") return;
    e.preventDefault();
    row.classList.remove("drop-target");
    const raw = e.dataTransfer.getData("text/plain");
    const sources = raw.split("\n").map((s) => s.trim()).filter(Boolean);
    if (sources.length) await moveTo(sources, row.dataset.rel);
  });

  contextMenu.addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-action]");
    if (!btn) return;
    const action = btn.dataset.action;
    const target = contextTarget;
    hideContext();
    if (!target) return;

    if (action === "open") {
      if (target.type === "dir") browse(target.rel);
      else if (target.type === "file") openBook(target.rel);
      return;
    }
    if (action === "edit" && target.type === "file") {
      openBook(target.rel);
      return;
    }
    if (action === "cut" && target.rel && target.type !== "pane") {
      const sources = selectedRels.has(target.rel)
        ? [...selectedRels]
        : [target.rel];
      clipboard = { sources };
      updateActionUi();
      setListMessage(
        sources.length === 1 ? `Recortado: ${sources[0]}` : `Recortados: ${sources.length} itens`,
        "ok"
      );
      return;
    }
    if (action === "paste") {
      if (!clipboard || !clipboard.sources.length) return;
      const dest = target.type === "dir" ? target.rel : currentPath;
      const r = await fetch("/api/library/move", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sources: clipboard.sources, dest }),
      });
      const d = await r.json();
      if (!r.ok || !d.ok) {
        setListMessage(d.error || "Falha ao colar.", "error");
        return;
      }
      clipboard = null;
      await refreshAll();
      setListMessage("Colado.", "ok");
      return;
    }
    if (action === "rename" && target.type !== "pane") {
      await renameSelected(target.rel);
      return;
    }
    if (action === "delete" && target.type !== "pane") {
      const items = selectedRels.has(target.rel)
        ? selectedEntries()
        : [entries.find((x) => x.rel === target.rel)].filter(Boolean);
      await deleteEntries(items);
      return;
    }
    if (action === "mkdir") await createFolder();
  });

  document.addEventListener("click", (e) => {
    if (!contextMenu.contains(e.target)) hideContext();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") hideContext();
    const tag = document.activeElement && document.activeElement.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA") return;
    if (e.key === "Delete" && selectedRels.size) {
      deleteCurrentSelection();
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "a") {
      e.preventDefault();
      setSelection(entries.map((x) => x.rel));
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "x" && selectedRels.size) {
      clipboard = { sources: [...selectedRels] };
      updateActionUi();
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "v" && clipboard) {
      pasteBtn.click();
    }
  });

  document.getElementById("saveMetaBtn").addEventListener("click", saveAllToKindle);
  document.getElementById("applyMetaBtn").addEventListener("click", async () => {
    if (!current) return;
    setDetailMessage("Aplicando metadados…");
    if (await applyMetadataOnly()) {
      setDetailMessage("Metadados aplicados no Kindle.", "ok");
      await browse(currentPath);
    }
  });

  document.getElementById("dCoverBtn").addEventListener("click", () => dCoverInput.click());
  dCoverInput.addEventListener("change", () => {
    if (!current || !dCoverInput.files[0]) return;
    clearPendingCover();
    pendingCoverFile = dCoverInput.files[0];
    pendingCoverUrl = URL.createObjectURL(pendingCoverFile);
    dCoverInput.value = "";
    showCover(current.name, true);
    setDetailMessage("Capa selecionada — use “Salvar no Kindle” para enviar.", "ok");
  });

  toggleFavBtn.addEventListener("click", async () => {
    if (!current) return;
    const add = !current.favorite;
    const r = await fetch("/api/library/collections/favorites/books", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: current.path, action: add ? "add" : "remove" }),
    });
    const d = await r.json();
    if (!r.ok || !d.ok) {
      setDetailMessage(d.error || "Falha.", "error");
      return;
    }
    collections = d.collections;
    current.favorite = add;
    toggleFavBtn.textContent = add ? "Remover dos favoritos" : "Adicionar aos favoritos";
    renderMembership();
    setDetailMessage("Favoritos atualizados. Reinicie o KOReader.", "ok");
    await browse(currentPath);
  });

  document.getElementById("deleteBookBtn").addEventListener("click", async () => {
    if (!current) return;
    const entry = { rel: current.name, name: current.name.split("/").pop(), type: "file" };
    await deleteEntries([entry]);
  });

  document.getElementById("closeDetailBtn").addEventListener("click", () => {
    detailPanel.hidden = true;
    current = null;
    clearPendingCover();
  });

  (async () => {
    try {
      await refreshAll();
    } catch (err) {
      setListMessage(err.message, "error");
    }
  })();
})();
