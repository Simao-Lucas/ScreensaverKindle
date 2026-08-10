(() => {
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("fileInput");
  const pickBtn = document.getElementById("pickBtn");
  const pushBtn = document.getElementById("pushBtn");
  const preview = document.getElementById("preview");
  const previewFrame = document.querySelector(".preview-frame");
  const previewCaption = document.getElementById("previewCaption");
  const messageEl = document.getElementById("message");
  const statusList = document.getElementById("statusList");

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

  function showPreview(url) {
    preview.hidden = false;
    preview.src = `${url}?t=${Date.now()}`;
    previewFrame.dataset.empty = "false";
    previewCaption.textContent = "Preview convertido";
    pushBtn.disabled = false;
  }

  async function uploadFile(file) {
    if (!file) return;
    setMessage("Convertendo imagem…");
    setStatus({ converted: false, transferred: false, ready: false });
    pushBtn.disabled = true;

    const body = new FormData();
    body.append("image", file);

    try {
      const res = await fetch("/upload", { method: "POST", body });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        setStatus({ converted: "fail" });
        setMessage(data.error || "Falha no upload.", "error");
        return;
      }
      setStatus(data.status || { converted: true });
      showPreview(data.preview_url || "/preview");
      setMessage(data.message || "Convertida.", "ok");
    } catch (err) {
      setStatus({ converted: "fail" });
      setMessage(`Erro de rede: ${err.message}`, "error");
    }
  }

  async function pushToKindle() {
    setMessage("Enviando para o Kindle…");
    setStatus({ converted: true, transferred: false, ready: false });
    pushBtn.disabled = true;

    try {
      const res = await fetch("/push", { method: "POST" });
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
    uploadFile(file);
    fileInput.value = "";
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
    uploadFile(file);
  });

  pushBtn.addEventListener("click", pushToKindle);
})();
