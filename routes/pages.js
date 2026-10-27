const express = require("express");
const fs = require("fs");
const path = require("path");
const storage = require("../lib/storage");
const sku = require("../lib/sku");
const { historyWorkbook } = require("../lib/excel");

const router = express.Router();

function noticeFromQuery(query) {
  if (query.saved === "1" && query.reused) {
    return { type: "warn", text: `This configuration already has short code ${query.reused}. Reusing it — no new code was created.` };
  }
  if (query.saved === "1") {
    return { type: "ok", text: query.code ? `Saved ${query.code}` : "Saved to history." };
  }
  return null;
}

router.get("/", (req, res) => {
  const data = storage.load();
  const model = sku.resolveForm(data.inventory, req.query);
  if (model) model.existingShortCode = sku.lookupShortCode(model.signature, data.short_codes);
  res.render("home", { title: "SKU Generator", page: "home", model, notice: noticeFromQuery(req.query) });
});

router.post("/save", (req, res) => {
  const data = storage.load();
  const model = sku.resolveForm(data.inventory, req.body);
  if (!model || !model.sku) return res.redirect("/");
  const existing = sku.lookupShortCode(model.signature, data.short_codes);
  const machine = model.sel[model.mfName] || {};
  const result = sku.addToSkuHistory(storage, {
    sku: model.sku,
    description: model.mappedDesc || model.allBreakdown.map((item) => item.name).join(" - "),
    category: model.category,
    config: model.sel,
    extras: model.chosen,
    machineCode: model.selectedMachineCode,
    machineName: machine.name || null,
    mappedName: model.mappedName,
    mappedDesc: model.mappedDesc,
    breakdownItems: model.allBreakdown,
    signature: model.signature,
    prefix: model.prefix,
  });
  const params = new URLSearchParams();
  params.set("category", model.category);
  if (model.selectedMachineCode) params.set("machine", model.selectedMachineCode);
  for (const widget of model.widgets) {
    if (widget.kind === "text" || widget.kind === "textarea") params.set(`txt_${widget.name}`, widget.value || "");
    else if (widget.kind !== "machine") params.set(`opt_${widget.name}`, widget.value || "");
  }
  for (const extra of model.chosen) params.append("extra", extra.code);
  if (model.extrasMode === "Single") params.set("extra_single", model.singleExtra || "None");
  params.set("saved", "1");
  if (existing) params.set("reused", existing);
  else if (result && result.shortCode) params.set("code", result.shortCode);
  res.redirect(`/?${params.toString()}`);
});

router.get("/history", (req, res) => {
  const data = storage.load();
  const history = data.sku_history || [];
  const filterKey = req.query.filter || "all";
  const groupBy = req.query.group || "recent";
  const query = req.query.q || "";
  const filtered = sku.filterSkuHistory(history, data.inventory, query, filterKey);
  const cbmCount = history.filter((entry) => sku.isCustomBlastMachine(entry, data.inventory)).length;
  const sections = sku.groupHistoryForDisplay(filtered, data.inventory, groupBy).map(([title, entries]) => [
    title,
    entries.map((entry) => {
      const full = sku.enrichHistoryEntry(entry, data.inventory);
      full.label = sku.historyRowLabel(entry, data.inventory);
      return full;
    }),
  ]);
  res.render("history", {
    title: "SKU History",
    page: "history",
    history,
    filtered,
    sections,
    filters: sku.historyFilterOptions(history),
    filterKey,
    groupBy,
    query,
    cbmCount,
  });
});

router.get("/history/export.xlsx", async (req, res, next) => {
  try {
    const data = storage.load();
    const filtered = sku.filterSkuHistory(data.sku_history || [], data.inventory, req.query.q || "", req.query.filter || "all");
    const buffer = await historyWorkbook(filtered, data.short_codes);
    res.setHeader("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
    res.setHeader("Content-Disposition", "attachment; filename=blastline_sku_history.xlsx");
    res.send(Buffer.from(buffer));
  } catch (err) {
    next(err);
  }
});

router.post("/history/clear", (req, res) => {
  storage.saveHistory([]);
  req.session.flash = { type: "ok", text: "History cleared. Short codes were kept." };
  res.redirect("/history");
});

router.get("/decoder", (req, res) => {
  const q = (req.query.q || "").trim();
  const data = storage.load();
  const shortRec = q ? sku.findRegistryByCode(data.short_codes, q) : null;
  let best = null;
  let others = [];
  let itemName = "";
  let itemDesc = "";
  let matchedCode = null;
  if (q && !shortRec) {
    const results = sku.decodeSku(q, data.inventory);
    best = results[0] || null;
    others = results.slice(1);
    if (best && data.inventory[best.category]) {
      const built = sku.buildSelectionFromDecode(best, data.inventory[best.category]);
      [itemName, itemDesc] = sku.generateMappedNameAndDescription(
        built.sel,
        built.fieldOrder,
        built.chosen,
        built.fittingsSelected,
        data.inventory[best.category].fields
      );
      matchedCode = sku.findCodeForSku(data.short_codes, q);
    }
  }
  res.render("decoder", { title: "SKU Decoder", page: "decoder", q, shortRec, best, others, itemName, itemDesc, matchedCode });
});

router.get("/category-items", (req, res) => {
  const file = path.join(__dirname, "..", "category_items.json");
  let rows = [];
  if (fs.existsSync(file)) rows = JSON.parse(fs.readFileSync(file, "utf8"));
  const q = (req.query.q || "").trim().toLowerCase();
  if (q) rows = rows.filter((row) => `${row.category} ${row.group}`.toLowerCase().includes(q));
  const groups = [];
  const index = new Map();
  for (const row of rows) {
    if (!index.has(row.category)) {
      index.set(row.category, []);
      groups.push([row.category, index.get(row.category)]);
    }
    index.get(row.category).push(row.group);
  }
  res.render("categories", { title: "Category - Item Pairs", page: "categories", q: req.query.q || "", groups });
});

module.exports = router;
