(() => {
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("fileInput");
  const pickBtn = document.getElementById("pickBtn");
  const pushBtn = document.getElementById("pushBtn");
  const formatSelect = document.getElementById("formatSelect");
  const bookReady = document.getElementById("bookReady");
  const bookName = document.getElementById("bookName");
  const messageEl = document.getElementById("message");
  const statusList = document.getElementById("statusList");
  const metaPanel = document.getElementById("metaPanel");
  const applyMetaBtn = document.getElementById("applyMetaBtn");
  const coverBtn = document.getElementById("coverBtn");
  const coverInput = document.getElementById("coverInput");
  const coverPreview = document.getElementById("coverPreview");
  const coverFrame = document.querySelector(".cover-frame");
  const metaWarn = document.getElementById("metaWarn");

  const fields = {
    title: document.getElementById("metaTitle"),
    authors: document.getElementById("metaAuthors"),
    publisher: document.getElementById("metaPublisher"),
    series: document.getElementById("metaSeries"),
    tags: document.getElementById("metaTags"),
    language: document.getElementById("metaLanguage"),
    comments: document.getElementById("metaComments"),
  };

  let pendingFile = null;
  let metaDirty = false;

  function setMessage(text, type = "") {
    messageEl.textContent = text || "";
    messageEl.className = `message${type ? ` ${type}` : ""}`;
  }

  function setStatus(status = {}) {
    for (const li of statusList.querySelectorAll("li")) {
      const key = li.dataset.key;
      li.classList.remove("done", "fail");
      if (status[key] === true) li.classList.add("done");
      if (status[key] === "fail") li.classList.add("fail");
    }
  }

  function showReady(name) {
    bookName.textContent = name || "";
    bookReady.hidden = !name;
    pushBtn.disabled = !name;
    metaPanel.hidden = !name;
  }

  function fillMetadata(data = {}) {
    for (const [key, el] of Object.entries(fields)) {
      if (!el) continue;
      el.value = data[key] || "";
    }
    metaDirty = false;
  }

  function collectMetadata() {
    const out = {};
    for (const [key, el] of Object.entries(fields)) {
      out[key] = el ? el.value.trim() : "";
    }
    return out;
  }

  function showCover(url) {
    if (!url) {
      coverPreview.hidden = true;
      coverPreview.removeAttribute("src");
      if (coverFrame) coverFrame.dataset.empty = "true";
      return;
    }
    coverPreview.hidden = false;
    coverPreview.src = `${url}?t=${Date.now()}`;
    if (coverFrame) coverFrame.dataset.empty = "false";
  }

  async function convertFile(file) {
    if (!file) return;
    pendingFile = file;
    setMessage("Convertendo livro…");
    setStatus({ converted: false, transferred: false, ready: false });
    pushBtn.disabled = true;
    showCover("");

    const body = new FormData();
    body.append("book", file);
    body.append("format", formatSelect.value);

    try {
      const res = await fetch("/books/upload", { method: "POST", body });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        setStatus({ converted: "fail" });
        setMessage(data.error || "Falha na conversão.", "error");
        showReady("");
        return;
      }
      setStatus(data.status || { converted: true });
      showReady(data.book_name || "");
      fillMetadata(data.metadata || {});
      if (metaWarn && data.meta_available === false) {
        metaWarn.hidden = false;
        metaWarn.textContent =
          "ebook-meta indisponível — capa ainda vai no .sdr; título no arquivo pode não atualizar.";
      }
      setMessage(data.message || "Convertido.", "ok");
    } catch (err) {
      setStatus({ converted: "fail" });
      setMessage(`Erro de rede: ${err.message}`, "error");
      showReady("");
    }
  }

  async function uploadCover(file) {
    if (!file) return;
    setMessage("Processando capa…");
    const body = new FormData();
    body.append("cover", file);
    try {
      const res = await fetch("/books/cover", { method: "POST", body });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        setMessage(data.error || "Falha na capa.", "error");
        return;
      }
      showCover(data.preview_url || "/books/cover-preview");
      metaDirty = true;
      setMessage(data.message || "Capa pronta.", "ok");
    } catch (err) {
      setMessage(`Erro de rede: ${err.message}`, "error");
    }
  }

  async function applyMetadata() {
    setMessage("Aplicando metadados…");
    applyMetaBtn.disabled = true;
    try {
      const res = await fetch("/books/metadata", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(collectMetadata()),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        setMessage(data.error || "Falha ao aplicar metadados.", "error");
        return false;
      }
      if (data.book_name) {
        bookName.textContent = data.book_name;
      }
      if (data.metadata) fillMetadata(data.metadata);
      metaDirty = false;
      setMessage(data.message || "Metadados aplicados.", "ok");
      return true;
    } catch (err) {
      setMessage(`Erro de rede: ${err.message}`, "error");
      return false;
    } finally {
      applyMetaBtn.disabled = false;
    }
  }

  async function pushToKindle() {
    if (metaDirty) {
      const ok = await applyMetadata();
      if (!ok) return;
    }

    setMessage("Enviando livro para o Kindle…");
    setStatus({ converted: true, transferred: false, ready: false });
    pushBtn.disabled = true;

    try {
      const res = await fetch("/books/push", { method: "POST" });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        setStatus({
          converted: true,
          transferred: "fail",
          ready: "fail",
        });
        setMessage(data.error || "Falha ao enviar.", "error");
        pushBtn.disabled = false;
        return;
      }
      setStatus(data.status || { converted: true, transferred: true, ready: true });
      setMessage(data.message || "Enviado.", "ok");
    } catch (err) {
      setStatus({ converted: true, transferred: "fail", ready: "fail" });
      setMessage(`Erro de rede: ${err.message}`, "error");
    } finally {
      pushBtn.disabled = false;
    }
  }

  Object.values(fields).forEach((el) => {
    if (!el) return;
    el.addEventListener("input", () => {
      metaDirty = true;
    });
  });

  pickBtn.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", () => {
    const file = fileInput.files && fileInput.files[0];
    convertFile(file);
    fileInput.value = "";
  });

  formatSelect.addEventListener("change", () => {
    if (pendingFile) convertFile(pendingFile);
  });

  coverBtn.addEventListener("click", () => coverInput.click());
  coverInput.addEventListener("change", () => {
    const file = coverInput.files && coverInput.files[0];
    uploadCover(file);
    coverInput.value = "";
  });

  applyMetaBtn.addEventListener("click", () => applyMetadata());

  ["dragenter", "dragover"].forEach((evt) => {
    dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach((evt) => {
    dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
    });
  });

  dropzone.addEventListener("drop", (e) => {
    const file = e.dataTransfer.files && e.dataTransfer.files[0];
    convertFile(file);
  });

  pushBtn.addEventListener("click", pushToKindle);
})();
