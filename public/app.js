document.querySelectorAll("[data-copy]").forEach((el) => {
  el.addEventListener("click", async () => {
    const text = el.getAttribute("data-copy") || "";
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      return;
    }
    const note = el.querySelector("small");
    if (!note) return;
    const old = note.textContent;
    note.textContent = "Copied";
    setTimeout(() => {
      note.textContent = old;
    }, 1600);
  });
});

document.querySelectorAll("[data-add-row]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const table = document.querySelector(btn.getAttribute("data-add-row"));
    const body = table && table.querySelector("tbody");
    if (!body) return;
    const row = body.querySelector("tr");
    const next = row ? row.cloneNode(true) : null;
    if (!next) return;
    next.querySelectorAll("input").forEach((input) => {
      input.value = input.name === "order" ? String(body.querySelectorAll("tr").length + 1) : "";
    });
    body.appendChild(next);
  });
});

document.querySelectorAll("[data-remove-row]").forEach((table) => {
  table.addEventListener("click", (event) => {
    const btn = event.target.closest("[data-remove]");
    if (!btn) return;
    const row = btn.closest("tr");
    const body = table.querySelector("tbody");
    if (row && body && body.querySelectorAll("tr").length > 1) row.remove();
    else if (row) row.querySelectorAll("input").forEach((input) => { input.value = ""; });
  });
});
