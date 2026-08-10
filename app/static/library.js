(() => {
  const bookList = document.getElementById("bookList");
  const collectionList = document.getElementById("collectionList");
  const filterCollection = document.getElementById("filterCollection");
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

  const fields = {
    title: document.getElementById("dTitle"),
    authors: document.getElementById("dAuthors"),
    publisher: document.getElementById("dPublisher"),
    series: document.getElementById("dSeries"),
    tags: document.getElementById("dTags"),
    language: document.getElementById("dLanguage"),
    comments: document.getElementById("dComments"),
  };

  let books = [];
  let collections = [];
  let current = null;

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

  function showCover(name, hasCover) {
    if (!hasCover) {
      dCoverPreview.hidden = true;
      dCoverFrame.dataset.empty = "true";
      return;
    }
    dCoverPreview.hidden = false;
    dCoverPreview.src = `/library/cover/${encodeURIComponent(name)}?t=${Date.now()}`;
    dCoverFrame.dataset.empty = "false";
  }

  function renderCollections() {
    collectionList.innerHTML = "";
    const filterKeep = filterCollection.value;
    filterCollection.innerHTML = `<option value="">Todas</option>`;
    collections.forEach((c) => {
      const li = document.createElement("li");
      li.className = "collection-item";
      const label = c.name === "favorites" ? "Favoritos" : c.name;
      li.innerHTML = `<button type="button" class="collection-pick" data-name="${c.name}">${label} <span>(${c.count})</span></button>`;
      if (c.name !== "favorites") {
        const actions = document.createElement("div");
        actions.className = "collection-actions";
        actions.innerHTML = `
          <button type="button" class="linkish" data-rename="${c.name}">Renomear</button>
          <button type="button" class="linkish danger-text" data-del="${c.name}">Apagar</button>`;
        li.appendChild(actions);
      }
      collectionList.appendChild(li);

      const opt = document.createElement("option");
      opt.value = c.name;
      opt.textContent = label;
      filterCollection.appendChild(opt);
    });
    if ([...filterCollection.options].some((o) => o.value === filterKeep)) {
      filterCollection.value = filterKeep;
    }
  }

  function renderBooks() {
    const filter = filterCollection.value;
    bookList.innerHTML = "";
    const visible = books.filter((b) => {
      if (!filter) return true;
      return (b.collections || []).includes(filter);
    });
    if (!visible.length) {
      bookList.innerHTML = `<li class="book-empty">Nenhum livro nesta visão.</li>`;
      return;
    }
    visible.forEach((b) => {
      const li = document.createElement("li");
      li.className = "book-item";
      li.innerHTML = `
        <button type="button" class="book-open" data-name="${b.name}">
          <span class="book-item-title">${b.title || b.name}</span>
          <span class="book-item-meta">${b.name}${b.favorite ? " · ★" : ""}${b.has_cover ? " · capa" : ""}</span>
        </button>`;
      bookList.appendChild(li);
    });
  }

  async function loadCollections() {
    const res = await fetch("/api/library/collections");
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || "Falha ao ler coleções");
    collections = data.collections || [];
    renderCollections();
  }

  async function loadBooks() {
    setListMessage("Carregando biblioteca…");
    const res = await fetch("/api/library/books");
    const data = await res.json();
    if (!res.ok || !data.ok) {
      setListMessage(data.error || "Falha ao listar.", "error");
      books = [];
      renderBooks();
      return;
    }
    books = data.books || [];
    renderBooks();
    setListMessage(`${books.length} livro(s).`, "ok");
  }

  async function openBook(name) {
    setDetailMessage("Abrindo…");
    detailPanel.hidden = false;
    const res = await fetch(`/api/library/books/${encodeURIComponent(name)}`);
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
        renderCollections();
        await loadBooks();
        setDetailMessage("Coleção atualizada. Reinicie o KOReader para ver no aparelho.", "ok");
        if (coll === "favorites") {
          toggleFavBtn.textContent = input.checked ? "Remover dos favoritos" : "Adicionar aos favoritos";
        }
      });
    });
    setDetailMessage("");
  }

  document.getElementById("refreshBtn").addEventListener("click", async () => {
    try {
      await loadCollections();
      await loadBooks();
    } catch (err) {
      setListMessage(err.message, "error");
    }
  });

  filterCollection.addEventListener("change", renderBooks);

  bookList.addEventListener("click", (e) => {
    const btn = e.target.closest(".book-open");
    if (btn) openBook(btn.dataset.name);
  });

  collectionList.addEventListener("click", async (e) => {
    const pick = e.target.closest(".collection-pick");
    if (pick) {
      filterCollection.value = pick.dataset.name;
      renderBooks();
      return;
    }
    const ren = e.target.closest("[data-rename]");
    if (ren) {
      const oldName = ren.dataset.rename;
      const neu = prompt("Novo nome da coleção:", oldName);
      if (!neu || neu === oldName) return;
      const r = await fetch(`/api/library/collections/${encodeURIComponent(oldName)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: neu.trim() }),
      });
      const d = await r.json();
      if (!r.ok || !d.ok) {
        setListMessage(d.error || "Falha ao renomear.", "error");
        return;
      }
      collections = d.collections;
      renderCollections();
      setListMessage("Coleção renomeada. Reinicie o KOReader.", "ok");
      return;
    }
    const del = e.target.closest("[data-del]");
    if (del) {
      if (!confirm(`Apagar coleção "${del.dataset.del}"?`)) return;
      const r = await fetch(`/api/library/collections/${encodeURIComponent(del.dataset.del)}`, {
        method: "DELETE",
      });
      const d = await r.json();
      if (!r.ok || !d.ok) {
        setListMessage(d.error || "Falha ao apagar.", "error");
        return;
      }
      collections = d.collections;
      renderCollections();
      setListMessage("Coleção apagada.", "ok");
    }
  });

  document.getElementById("createCollectionBtn").addEventListener("click", async () => {
    const input = document.getElementById("newCollectionName");
    const name = input.value.trim();
    if (!name) return;
    const r = await fetch("/api/library/collections", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    const d = await r.json();
    if (!r.ok || !d.ok) {
      setListMessage(d.error || "Falha ao criar.", "error");
      return;
    }
    input.value = "";
    collections = d.collections;
    renderCollections();
    setListMessage(d.message || "Criada.", "ok");
  });

  document.getElementById("saveMetaBtn").addEventListener("click", async () => {
    if (!current) return;
    setDetailMessage("Salvando…");
    const r = await fetch(`/api/library/books/${encodeURIComponent(current.name)}/metadata`, {
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
    await loadBooks();
  });

  document.getElementById("dCoverBtn").addEventListener("click", () => dCoverInput.click());
  dCoverInput.addEventListener("change", async () => {
    if (!current || !dCoverInput.files[0]) return;
    const body = new FormData();
    body.append("cover", dCoverInput.files[0]);
    setDetailMessage("Enviando capa…");
    const r = await fetch(`/api/library/books/${encodeURIComponent(current.name)}/cover`, {
      method: "POST",
      body,
    });
    const d = await r.json();
    dCoverInput.value = "";
    if (!r.ok || !d.ok) {
      setDetailMessage(d.error || "Falha na capa.", "error");
      return;
    }
    current = d.book;
    showCover(current.name, true);
    setDetailMessage(d.message || "Capa ok.", "ok");
    await loadBooks();
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
    renderCollections();
    await loadBooks();
    setDetailMessage("Favoritos atualizados. Reinicie o KOReader.", "ok");
  });

  document.getElementById("deleteBookBtn").addEventListener("click", async () => {
    if (!current) return;
    if (!confirm(`Excluir "${current.name}" e a pasta .sdr?`)) return;
    const r = await fetch(`/api/library/books/${encodeURIComponent(current.name)}`, {
      method: "DELETE",
    });
    const d = await r.json();
    if (!r.ok || !d.ok) {
      setDetailMessage(d.error || "Falha ao excluir.", "error");
      return;
    }
    current = null;
    detailPanel.hidden = true;
    await loadBooks();
    await loadCollections();
    setListMessage(d.message || "Excluído.", "ok");
  });

  document.getElementById("closeDetailBtn").addEventListener("click", () => {
    detailPanel.hidden = true;
    current = null;
  });

  (async () => {
    try {
      await loadCollections();
      await loadBooks();
    } catch (err) {
      setListMessage(err.message, "error");
    }
  })();
})();
