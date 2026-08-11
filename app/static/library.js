(() => {
  const folderTree = document.getElementById("folderTree");
  const explorerBody = document.getElementById("explorerBody");
  const emptyHint = document.getElementById("emptyHint");
  const breadcrumb = document.getElementById("breadcrumb");
  const listMessage = document.getElementById("listMessage");
  const detailPanel = document.getElementById("detailPanel");
  const detailTitle = document.getElementById("detailTitle");
  const detailFile = document.getElementById("detailFile");
  const detailMessage = document.getElementById("detailMessage");
  const membership = document.getElementById("membership");
  const dCoverPreview = document.getElementById("dCoverPreview");
  const dCoverFrame = document.getElementById("dCoverFrame");
  const dCoverInput = document.getElementById("dCoverInput");
  const toggleFavBtn = document.getElementById("toggleFavBtn");
  const contextMenu = document.getElementById("contextMenu");
  const cutBtn = document.getElementById("cutBtn");
  const pasteBtn = document.getElementById("pasteBtn");
  const upBtn = document.getElementById("upBtn");

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
  let selectedRel = null;
  let clipboard = null; // { sources: string[] }
  let contextTarget = null;

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

  function showCover(name, hasCover) {
    if (!hasCover) {
      dCoverPreview.hidden = true;
      dCoverFrame.dataset.empty = "true";
      return;
    }
    dCoverPreview.hidden = false;
    dCoverPreview.src = `/library/cover/${name.split("/").map(encodeURIComponent).join("/")}?t=${Date.now()}`;
    dCoverFrame.dataset.empty = "false";
  }

  function bookUrl(name, suffix = "") {
    const parts = name.split("/").map(encodeURIComponent).join("/");
    return `/api/library/books/${parts}${suffix}`;
  }

  function updateClipboardUi() {
    cutBtn.disabled = !selectedRel;
    pasteBtn.disabled = !clipboard || !clipboard.sources.length;
  }

  function hideContext() {
    contextMenu.hidden = true;
    contextTarget = null;
  }

  function showContext(x, y, entry) {
    contextTarget = entry;
    contextMenu.hidden = false;
    contextMenu.style.left = `${Math.min(x, window.innerWidth - 180)}px`;
    contextMenu.style.top = `${Math.min(y, window.innerHeight - 220)}px`;
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
    btn.innerHTML = `<span class="tree-icon" aria-hidden="true"></span> <span>${node.name}</span>`;
    btn.draggable = false;
    btn.addEventListener("dragover", (e) => {
      e.preventDefault();
      btn.classList.add("drop-target");
    });
    btn.addEventListener("dragleave", () => btn.classList.remove("drop-target"));
    btn.addEventListener("drop", async (e) => {
      e.preventDefault();
      btn.classList.remove("drop-target");
      const src = e.dataTransfer.getData("text/plain");
      if (src) await moveTo(src, node.rel || "");
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
      if (entry.rel === selectedRel) tr.classList.add("is-selected");
      tr.dataset.rel = entry.rel;
      tr.dataset.type = entry.type;
      tr.draggable = true;
      const typeLabel = entry.type === "dir" ? "Pasta" : (entry.name.split(".").pop() || "arquivo").toUpperCase();
      const star = entry.favorite ? " ★" : "";
      tr.innerHTML = `
        <td class="col-name">
          <span class="entry-icon entry-icon-${entry.type}" aria-hidden="true"></span>
          <span class="entry-label">${entry.title || entry.name}${star}</span>
        </td>
        <td>${typeLabel}</td>
        <td>${entry.type === "dir" ? "—" : formatSize(entry.size)}</td>`;
      explorerBody.appendChild(tr);
    });
    updateClipboardUi();
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
    selectedRel = null;
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
    // refresh active tree highlight
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

  async function moveTo(sourceRel, destRel) {
    if (!sourceRel) return;
    if (sourceRel === destRel) return;
    // don't move into self
    if (destRel === sourceRel || destRel.startsWith(sourceRel + "/")) {
      setListMessage("Não é possível mover para dentro de si.", "error");
      return;
    }
    setListMessage("Movendo…");
    const r = await fetch("/api/library/move", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sources: [sourceRel], dest: destRel }),
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

  async function openBook(name) {
    setDetailMessage("Abrindo…");
    detailPanel.hidden = false;
    const res = await fetch(bookUrl(name));
    const data = await res.json();
    if (!res.ok || !data.ok) {
      setDetailMessage(data.error || "Falha.", "error");
      return;
    }
    current = data.book;
    detailTitle.textContent = current.metadata.title || current.name;
    detailFile.textContent = current.path;
    fillFields(current.metadata || {});
    showCover(current.name, current.has_cover);
    toggleFavBtn.textContent = current.favorite ? "Remover dos favoritos" : "Adicionar aos favoritos";

    membership.innerHTML = "<p class='field-label'>Coleções</p>";
    const wrap = document.createElement("div");
    wrap.className = "membership-toggles";
    collections.forEach((c) => {
      const id = `mem-${c.name}`;
      const checked = (current.collections || []).includes(c.name);
      const label = document.createElement("label");
      label.className = "check-row";
      label.innerHTML = `<input type="checkbox" id="${id}" data-coll="${c.name}" ${checked ? "checked" : ""}/> <span>${c.name === "favorites" ? "Favoritos" : c.name}</span>`;
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
        setDetailMessage("Coleção atualizada. Reinicie o KOReader para ver no aparelho.", "ok");
        if (coll === "favorites") {
          toggleFavBtn.textContent = input.checked ? "Remover dos favoritos" : "Adicionar aos favoritos";
        }
      });
    });
    setDetailMessage("");
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
    await refreshAll();
    setListMessage("Renomeado.", "ok");
  }

  async function deleteSelected(rel, type) {
    const label = rel.split("/").pop();
    const msg =
      type === "dir"
        ? `Apagar a pasta "${label}" e todo o conteúdo?`
        : `Excluir "${label}" e a pasta .sdr?`;
    if (!confirm(msg)) return;
    const r = await fetch(`/api/library/entry?path=${encodeURIComponent(rel)}`, {
      method: "DELETE",
    });
    const d = await r.json();
    if (!r.ok || !d.ok) {
      setListMessage(d.error || "Falha ao excluir.", "error");
      return;
    }
    if (current && current.name === rel) {
      current = null;
      detailPanel.hidden = true;
    }
    await refreshAll();
    setListMessage(d.message || "Excluído.", "ok");
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
  document.getElementById("refreshBtn").addEventListener("click", () => refreshAll().catch((err) => setListMessage(err.message, "error")));
  document.getElementById("newFolderBtn").addEventListener("click", createFolder);

  cutBtn.addEventListener("click", () => {
    if (!selectedRel) return;
    clipboard = { sources: [selectedRel] };
    updateClipboardUi();
    setListMessage(`Recortado: ${selectedRel}`, "ok");
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
    const row = e.target.closest(".explorer-row");
    if (!row) return;
    selectedRel = row.dataset.rel;
    renderEntries();
  });

  explorerBody.addEventListener("dblclick", (e) => {
    const row = e.target.closest(".explorer-row");
    if (!row) return;
    if (row.dataset.type === "dir") browse(row.dataset.rel);
    else openBook(row.dataset.rel);
  });

  explorerBody.addEventListener("contextmenu", (e) => {
    const row = e.target.closest(".explorer-row");
    e.preventDefault();
    if (row) {
      selectedRel = row.dataset.rel;
      renderEntries();
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
    e.dataTransfer.setData("text/plain", row.dataset.rel);
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
    const src = e.dataTransfer.getData("text/plain");
    if (src) await moveTo(src, row.dataset.rel);
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
    if (action === "cut" && target.rel && target.type !== "pane") {
      clipboard = { sources: [target.rel] };
      selectedRel = target.rel;
      updateClipboardUi();
      setListMessage(`Recortado: ${target.rel}`, "ok");
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
      await deleteSelected(target.rel, target.type);
      return;
    }
    if (action === "mkdir") {
      await createFolder();
    }
  });

  document.addEventListener("click", (e) => {
    if (!contextMenu.contains(e.target)) hideContext();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") hideContext();
    if (e.key === "Delete" && selectedRel && document.activeElement.tagName !== "INPUT" && document.activeElement.tagName !== "TEXTAREA") {
      const entry = entries.find((x) => x.rel === selectedRel);
      if (entry) deleteSelected(entry.rel, entry.type);
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "x" && selectedRel) {
      clipboard = { sources: [selectedRel] };
      updateClipboardUi();
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "v" && clipboard) {
      pasteBtn.click();
    }
  });

  document.getElementById("saveMetaBtn").addEventListener("click", async () => {
    if (!current) return;
    setDetailMessage("Salvando…");
    const r = await fetch(bookUrl(current.name, "/metadata"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(collectFields()),
    });
    const d = await r.json();
    if (!r.ok || !d.ok) {
      setDetailMessage(d.error || "Falha.", "error");
      return;
    }
    current = d.book;
    detailTitle.textContent = current.metadata.title || current.name;
    setDetailMessage(d.message || "Salvo.", "ok");
    await browse(currentPath);
  });

  document.getElementById("dCoverBtn").addEventListener("click", () => dCoverInput.click());
  dCoverInput.addEventListener("change", async () => {
    if (!current || !dCoverInput.files[0]) return;
    const body = new FormData();
    body.append("cover", dCoverInput.files[0]);
    setDetailMessage("Enviando capa…");
    const r = await fetch(bookUrl(current.name, "/cover"), { method: "POST", body });
    const d = await r.json();
    dCoverInput.value = "";
    if (!r.ok || !d.ok) {
      setDetailMessage(d.error || "Falha na capa.", "error");
      return;
    }
    current = d.book;
    showCover(current.name, true);
    setDetailMessage(d.message || "Capa ok.", "ok");
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
    setDetailMessage("Favoritos atualizados. Reinicie o KOReader.", "ok");
    await browse(currentPath);
  });

  document.getElementById("deleteBookBtn").addEventListener("click", async () => {
    if (!current) return;
    await deleteSelected(current.name, "file");
  });

  document.getElementById("closeDetailBtn").addEventListener("click", () => {
    detailPanel.hidden = true;
    current = null;
  });

  (async () => {
    try {
      await refreshAll();
    } catch (err) {
      setListMessage(err.message, "error");
    }
  })();
})();
