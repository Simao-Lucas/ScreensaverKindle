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

  let pendingFile = null;

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
  }

  async function convertFile(file) {
    if (!file) return;
    pendingFile = file;
    setMessage("Convertendo livro…");
    setStatus({ converted: false, transferred: false, ready: false });
    pushBtn.disabled = true;

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
      setMessage(data.message || "Convertido.", "ok");
    } catch (err) {
      setStatus({ converted: "fail" });
      setMessage(`Erro de rede: ${err.message}`, "error");
      showReady("");
    }
  }

  async function pushToKindle() {
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

  pickBtn.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", () => {
    const file = fileInput.files && fileInput.files[0];
    convertFile(file);
    fileInput.value = "";
  });

  formatSelect.addEventListener("change", () => {
    if (pendingFile) convertFile(pendingFile);
  });

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
