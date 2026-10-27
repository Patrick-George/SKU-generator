const express = require("express");
const multer = require("multer");
const storage = require("../lib/storage");
const sku = require("../lib/sku");

const router = express.Router();
const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 20 * 1024 * 1024 } });
const SECTIONS = [
  ["fields", "Fields"],
  ["extras", "Extras"],
  ["settings", "Settings"],
  ["matrix", "Export Matrix"],
  ["backup", "Backup"],
  ["mapping", "Machine Mapping"],
];

router.use((req, res, next) => {
  if (!req.session.admin) return res.redirect("/login");
  next();
});

function list(value) {
  if (value == null || value === "") return [];
  return Array.isArray(value) ? value : [value];
}

function back(cat, section, extra) {
  const params = new URLSearchParams({ cat: cat || "", section: section || "fields" });
  if (extra) {
    for (const [key, value] of Object.entries(extra)) {
      if (value != null && value !== "") params.set(key, value);
    }
  }
  return `/admin?${params.toString()}`;
}

function recordsFromBody(body) {
  const codes = list(body.code);
  const names = list(body.name);
  const tallies = list(body.tally_name);
  const descriptions = list(body.description);
  const orders = list(body.order);
  const count = Math.max(codes.length, names.length, tallies.length, descriptions.length, orders.length);
  const records = [];
  for (let i = 0; i < count; i += 1) {
    const code = codes[i] == null ? "" : String(codes[i]).trim();
    const name = names[i] == null ? "" : String(names[i]).trim();
    const tally = tallies[i] == null ? "" : String(tallies[i]);
    const description = descriptions[i] == null ? "" : String(descriptions[i]);
    const orderRaw = orders[i];
    if (!code && !name && !String(tally).trim() && !String(description).trim()) continue;
    const order = orderRaw === "" || orderRaw == null || Number.isNaN(Number(orderRaw)) ? records.length + 1 : Number(orderRaw);
    records.push({ code, name, tally_name: tally, description, order });
  }
  return records;
}

function categoryOrRedirect(req, res) {
  const data = storage.load();
  const cat = req.body.cat || req.query.cat;
  if (!cat || !data.inventory[cat]) {
    req.session.flash = { type: "err", text: "Category not found." };
    res.redirect("/admin");
    return null;
  }
  return { data, cat, catData: data.inventory[cat] };
}

router.get("/", (req, res) => {
  const data = storage.load();
  const categories = Object.keys(data.inventory);
  const cat = categories.includes(req.query.cat) ? req.query.cat : categories[0] || "";
  const section = SECTIONS.some(([id]) => id === req.query.section) ? req.query.section : "fields";
  const vm = {
    title: "Admin",
    page: "admin",
    categories,
    cat,
    section,
    sections: SECTIONS,
    categoryCount: categories.length,
    fieldOrder: [],
    tool: req.query.tool || "options",
    field: req.query.field || "",
    options: [],
    extras: [],
    settings: {},
    matrix: { total: 0, headers: [], preview: [] },
    machines: [],
    machine: req.query.machine || "",
    machineField: "Machine",
    detail: req.query.detail || "fields",
    otherFields: [],
    optionGroups: [],
    extraMaps: [],
    hasX: false,
    fieldData: null,
    importPreview: req.session.pendingImport
      ? {
          fileName: req.session.pendingImport.fileName,
          count: req.session.pendingImport.categories.length,
          categories: req.session.pendingImport.categories,
        }
      : null,
  };
  if (cat) {
    const catData = data.inventory[cat];
    sku.normalizeFields(catData);
    const fields = catData.fields;
    vm.fieldOrder = sku.orderedFields(fields);
    vm.field = vm.fieldOrder.includes(vm.field) ? vm.field : vm.fieldOrder[0] || "";
    vm.extras = catData.extras || [];
    vm.settings = catData.settings || {};
    if (vm.field && fields[vm.field]) {
      const opts = fields[vm.field].options || [];
      vm.fieldData = { text: sku.isTextField(fields[vm.field]), multiline: Boolean(opts[0] && opts[0].multiline) };
      vm.options = opts.filter((opt) => opt.type !== "text");
      vm.hasX = vm.options.some((opt) => String(opt.code || "").toUpperCase() === "X");
    }
    const plan = sku.matrixFieldPlan(catData);
    const preview = sku.iterateMatrix(catData, cat, 20);
    vm.matrix = { total: plan.total, headers: ["SKU", ...plan.names], preview: preview.rows };
    vm.machineField = sku.getMachineField(catData);
    const machineOpts = ((fields[vm.machineField] || {}).options || []).filter((opt) => opt.code);
    vm.machines = machineOpts;
    vm.machine = machineOpts.some((opt) => opt.code === vm.machine) ? vm.machine : (machineOpts[0] && machineOpts[0].code) || "";
    const allCodes = machineOpts.map((opt) => opt.code);
    vm.otherFields = vm.fieldOrder.filter((name) => name !== vm.machineField).map((name) => {
      const hasKey = Object.prototype.hasOwnProperty.call(fields[name], "machines");
      const current = fields[name].machines || [];
      return { name, on: !hasKey || current.includes(vm.machine) };
    });
    const visibleNames = new Set(vm.otherFields.filter((f) => f.on).map((f) => f.name));
    vm.optionGroups = vm.fieldOrder
      .filter((name) => name !== vm.machineField && !sku.isTextField(fields[name]) && visibleNames.has(name))
      .map((name) => ({
        name,
        options: (fields[name].options || []).flatMap((opt, index) => {
          if (!opt.code) return [];
          const hasKey = Object.prototype.hasOwnProperty.call(opt, "machines");
          return [{
            key: `${encodeURIComponent(name)}|${index}`,
            code: opt.code,
            name: opt.name || "",
            on: !hasKey || (opt.machines || []).includes(vm.machine),
          }];
        }),
      }));
    vm.extraMaps = (catData.extras || []).flatMap((extra, index) => {
      if (!extra.code) return [];
      const hasKey = Object.prototype.hasOwnProperty.call(extra, "machines");
      return [{ index, code: extra.code, name: extra.name || "", on: !hasKey || (extra.machines || []).includes(vm.machine) }];
    });
  }
  res.render("admin", vm);
});

router.post("/category", (req, res) => {
  const name = (req.body.newCategory || "").trim();
  const data = storage.load();
  if (!name) {
    req.session.flash = { type: "err", text: "Enter a category name." };
  } else if (data.inventory[name]) {
    req.session.flash = { type: "err", text: `Category '${name}' already exists.` };
  } else {
    data.inventory[name] = { fields: {}, extras: [], settings: { separator: "", extras_mode: "Multiple" } };
    storage.save(data);
    req.session.flash = { type: "ok", text: `Category '${name}' created.` };
    return res.redirect(back(name, "fields"));
  }
  res.redirect("/admin");
});

router.post("/category/delete", (req, res) => {
  const found = categoryOrRedirect(req, res);
  if (!found) return;
  delete found.data.inventory[found.cat];
  storage.save(found.data);
  req.session.flash = { type: "ok", text: `Category '${found.cat}' deleted.` };
  res.redirect("/admin");
});

router.post("/field", (req, res) => {
  const found = categoryOrRedirect(req, res);
  if (!found) return;
  const name = (req.body.name || "").trim();
  const type = req.body.type;
  sku.normalizeFields(found.catData);
  const fields = found.catData.fields;
  if (!name) {
    req.session.flash = { type: "err", text: "Enter a field name." };
  } else if (fields[name]) {
    req.session.flash = { type: "err", text: `Field '${name}' already exists.` };
  } else {
    let options = [];
    if (type === "Text Input") options = [{ type: "text", code: "", name: "" }];
    else if (type === "Multi-line Text") options = [{ type: "text", multiline: true, code: "", name: "" }];
    fields[name] = { order: Object.keys(fields).length + 1, options, machines: [] };
    storage.save(found.data);
    req.session.flash = { type: "ok", text: `Field '${name}' added.` };
  }
  res.redirect(back(found.cat, "fields"));
});

router.post("/field/move", (req, res) => {
  const found = categoryOrRedirect(req, res);
  if (!found) return;
  sku.normalizeFields(found.catData);
  const fields = found.catData.fields;
  const order = sku.orderedFields(fields);
  const index = order.indexOf(req.body.field);
  const swapWith = req.body.dir === "up" ? index - 1 : index + 1;
  if (index >= 0 && swapWith >= 0 && swapWith < order.length) {
    const a = order[index];
    const b = order[swapWith];
    const orderA = fields[a].order;
    fields[a].order = fields[b].order;
    fields[b].order = orderA;
    sku.orderedFields(fields).forEach((name, i) => {
      fields[name].order = i + 1;
    });
    storage.save(found.data);
  }
  res.redirect(back(found.cat, "fields", { tool: "reorder" }));
});

router.post("/field/rename", (req, res) => {
  const found = categoryOrRedirect(req, res);
  if (!found) return;
  sku.normalizeFields(found.catData);
  const fields = found.catData.fields;
  const field = req.body.field;
  const newName = (req.body.newName || "").trim();
  if (!fields[field]) {
    req.session.flash = { type: "err", text: "Field not found." };
  } else if (!newName || newName === field) {
    req.session.flash = { type: "info", text: "Field name unchanged." };
  } else if (fields[newName]) {
    req.session.flash = { type: "err", text: `Field '${newName}' already exists.` };
  } else {
    const next = {};
    for (const [key, value] of Object.entries(fields)) next[key === field ? newName : key] = value;
    found.catData.fields = next;
    storage.save(found.data);
    req.session.flash = { type: "ok", text: `Field renamed to '${newName}'.` };
    return res.redirect(back(found.cat, "fields", { tool: "rename", field: newName }));
  }
  res.redirect(back(found.cat, "fields", { tool: "rename", field }));
});

router.post("/field/delete", (req, res) => {
  const found = categoryOrRedirect(req, res);
  if (!found) return;
  sku.normalizeFields(found.catData);
  if (found.catData.fields[req.body.field]) {
    delete found.catData.fields[req.body.field];
    storage.save(found.data);
    req.session.flash = { type: "ok", text: `Field '${req.body.field}' deleted.` };
  }
  res.redirect(back(found.cat, "fields", { tool: "rename" }));
});

router.post("/field/multiline", (req, res) => {
  const found = categoryOrRedirect(req, res);
  if (!found) return;
  sku.normalizeFields(found.catData);
  const field = found.catData.fields[req.body.field];
  if (field && sku.isTextField(field)) {
    if (req.body.multiline) field.options[0].multiline = true;
    else delete field.options[0].multiline;
    storage.save(found.data);
    req.session.flash = { type: "ok", text: "Field updated." };
  }
  res.redirect(back(found.cat, "fields", { tool: "options", field: req.body.field }));
});

router.post("/options", (req, res) => {
  const found = categoryOrRedirect(req, res);
  if (!found) return;
  sku.normalizeFields(found.catData);
  const field = found.catData.fields[req.body.field];
  if (!field || sku.isTextField(field)) return res.redirect(back(found.cat, "fields"));
  field.options = sku.mergeEditorRecords(field.options || [], recordsFromBody(req.body));
  storage.save(found.data);
  req.session.flash = { type: "ok", text: "Options saved." };
  res.redirect(back(found.cat, "fields", { tool: "options", field: req.body.field }));
});

router.post("/extras", (req, res) => {
  const found = categoryOrRedirect(req, res);
  if (!found) return;
  found.catData.extras = sku.mergeEditorRecords(found.catData.extras || [], recordsFromBody(req.body));
  storage.save(found.data);
  req.session.flash = { type: "ok", text: "Extras saved." };
  res.redirect(back(found.cat, "extras"));
});

router.post("/settings", (req, res) => {
  const found = categoryOrRedirect(req, res);
  if (!found) return;
  const settings = found.catData.settings || {};
  settings.separator = req.body.separator == null ? "" : String(req.body.separator).slice(0, 5);
  settings.extras_mode = req.body.extras_mode === "Single" ? "Single" : "Multiple";
  found.catData.settings = settings;
  storage.save(found.data);
  req.session.flash = { type: "ok", text: "Settings saved." };
  res.redirect(back(found.cat, "settings"));
});

router.post("/machine-field", (req, res) => {
  const found = categoryOrRedirect(req, res);
  if (!found) return;
  sku.normalizeFields(found.catData);
  const name = req.body.machineField;
  if (found.catData.fields[name]) {
    found.catData.settings = found.catData.settings || {};
    found.catData.settings.machine_field = name;
    storage.save(found.data);
    req.session.flash = { type: "ok", text: "Machine field saved." };
  }
  res.redirect(back(found.cat, "mapping"));
});

router.post("/mapping", (req, res) => {
  const found = categoryOrRedirect(req, res);
  if (!found) return;
  sku.normalizeFields(found.catData);
  const fields = found.catData.fields;
  const machine = req.body.machine;
  const mfName = sku.getMachineField(found.catData);
  const machineOpts = ((fields[mfName] || {}).options || []).filter((opt) => opt.code);
  const allCodes = machineOpts.map((opt) => opt.code);
  if (!allCodes.includes(machine)) return res.redirect(back(found.cat, "mapping"));
  const checkedFields = new Set(list(req.body.visibleField));
  for (const name of sku.orderedFields(fields)) {
    if (name === mfName) continue;
    const current = Object.prototype.hasOwnProperty.call(fields[name], "machines") ? new Set(fields[name].machines) : new Set(allCodes);
    if (checkedFields.has(name)) current.add(machine);
    else current.delete(machine);
    fields[name].machines = [...current].sort();
  }
  if (req.body.detail === "options") {
    const checked = new Set(list(req.body.visibleOpt));
    for (const name of sku.orderedFields(fields)) {
      if (name === mfName || sku.isTextField(fields[name])) continue;
      if (!checkedFields.has(name)) continue;
      (fields[name].options || []).forEach((opt, index) => {
        if (!opt.code) return;
        const key = `${encodeURIComponent(name)}|${index}`;
        const current = Object.prototype.hasOwnProperty.call(opt, "machines") ? new Set(opt.machines) : new Set(allCodes);
        if (checked.has(key)) current.add(machine);
        else current.delete(machine);
        opt.machines = [...current].sort();
      });
    }
  }
  if (req.body.detail === "extras") {
    const checked = new Set(list(req.body.visibleExtra).map(String));
    (found.catData.extras || []).forEach((extra, index) => {
      if (!extra.code) return;
      const current = Object.prototype.hasOwnProperty.call(extra, "machines") ? new Set(extra.machines) : new Set(allCodes);
      if (checked.has(String(index))) current.add(machine);
      else current.delete(machine);
      extra.machines = [...current].sort();
    });
  }
  storage.save(found.data);
  req.session.flash = { type: "ok", text: "Machine mapping saved." };
  res.redirect(back(found.cat, "mapping", { machine, detail: req.body.detail || "fields" }));
});

router.get("/matrix.csv", (req, res) => {
  const data = storage.load();
  const cat = req.query.cat;
  const catData = data.inventory[cat];
  if (!catData) return res.status(404).send("Category not found");
  const plan = sku.matrixFieldPlan(catData);
  if (!plan.total || plan.total > 100000) return res.status(400).send("This matrix is too large to export.");
  const { rows } = sku.iterateMatrix(catData, cat, plan.total);
  res.setHeader("Content-Type", "text/csv; charset=utf-8");
  res.setHeader("Content-Disposition", `attachment; filename="${cat}_full_matrix.csv"`);
  res.send(sku.toCsv(rows));
});

router.get("/backup.json", (req, res) => {
  const data = storage.load();
  const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\..+/, "").replace("T", "_");
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Content-Disposition", `attachment; filename="blastline_sku_backup_${stamp}.json"`);
  res.send(JSON.stringify(data, null, 2));
});

function categoryPreview(inventory) {
  return Object.entries(inventory || {}).map(([name, cat]) => ({
    name,
    fields: Object.keys((cat && cat.fields) || {}).length,
    extras: Array.isArray(cat && cat.extras) ? cat.extras.length : 0,
  }));
}

router.post("/import", upload.single("backup"), (req, res) => {
  if (!req.file) {
    req.session.flash = { type: "err", text: "Choose a backup file." };
    return res.redirect("/admin?section=backup");
  }
  let imported;
  try {
    const raw = req.file.buffer.toString("utf8").replace(/^\uFEFF/, "").replace(/\bNaN\b|-?\bInfinity\b/g, "null");
    imported = JSON.parse(raw);
  } catch {
    delete req.session.pendingImport;
    req.session.flash = { type: "err", text: "That file is not valid JSON." };
    return res.redirect("/admin?section=backup");
  }
  if (!imported || !imported.inventory || typeof imported.inventory !== "object" || Array.isArray(imported.inventory)) {
    delete req.session.pendingImport;
    req.session.flash = { type: "err", text: "Backup is missing an inventory." };
    return res.redirect("/admin?section=backup");
  }
  const categories = categoryPreview(imported.inventory);
  req.session.pendingImport = {
    fileName: req.file.originalname || "",
    categories,
    data: imported,
  };
  res.redirect("/admin?section=backup");
});

router.post("/import/cancel", (req, res) => {
  delete req.session.pendingImport;
  res.redirect("/admin?section=backup");
});

router.post("/import/confirm", (req, res) => {
  const pending = req.session.pendingImport;
  if (!pending || !pending.data || !pending.data.inventory) {
    req.session.flash = { type: "err", text: "Choose a backup file and preview it first." };
    return res.redirect("/admin?section=backup");
  }
  const imported = pending.data;
  const data = storage.load();
  if (req.body.mode === "merge") {
    let added = 0;
    let skipped = 0;
    for (const [name, catData] of Object.entries(imported.inventory)) {
      if (data.inventory[name]) skipped += 1;
      else {
        data.inventory[name] = catData;
        added += 1;
      }
    }
    storage.save(data);
    req.session.flash = { type: "ok", text: `Merge complete. Added ${added} categories, skipped ${skipped}.` };
  } else {
    storage.save(imported);
    req.session.flash = { type: "ok", text: `Database replaced. Imported ${pending.categories.length} categories.` };
  }
  delete req.session.pendingImport;
  res.redirect("/admin?section=backup");
});

module.exports = router;
