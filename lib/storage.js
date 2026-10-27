const fs = require("fs");
const path = require("path");
const { padShortCodesInPlace } = require("./sku");

const DATA_FILE = process.env.DATA_FILE || path.join(__dirname, "..", "data", "sku_data.json");

function blank() {
  return { inventory: {}, sku_history: [], short_codes: {}, code_counters: {} };
}

function ensureShape(data) {
  data.inventory = data.inventory || {};
  data.sku_history = data.sku_history || [];
  data.short_codes = data.short_codes || {};
  data.code_counters = data.code_counters || {};
  return data;
}

function parseDataFile(raw) {
  // Python's json.dumps writes NaN for empty spreadsheet cells. That is not valid JSON.
  const cleaned = raw.replace(/^\uFEFF/, "").replace(/\bNaN\b|-?\bInfinity\b/g, "null");
  return { data: JSON.parse(cleaned), cleaned: cleaned !== raw.replace(/^\uFEFF/, "") };
}

function load() {
  let data = null;
  let sanitized = false;
  if (fs.existsSync(DATA_FILE)) {
    try {
      const parsed = parseDataFile(fs.readFileSync(DATA_FILE, "utf8"));
      data = parsed.data;
      sanitized = parsed.cleaned;
    } catch {
      data = null;
    }
  }
  if (!data || typeof data !== "object" || Array.isArray(data)) data = blank();
  ensureShape(data);
  if (sanitized || padShortCodesInPlace(data)) save(data);
  return data;
}

function save(data) {
  ensureShape(data);
  fs.mkdirSync(path.dirname(DATA_FILE), { recursive: true });
  const tmp = `${DATA_FILE}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(data, null, 2));
  fs.renameSync(tmp, DATA_FILE);
  return true;
}

function saveHistory(history) {
  const current = load();
  current.sku_history = history;
  return save(current);
}

function saveRegistry(shortCodes, codeCounters) {
  const current = load();
  current.short_codes = shortCodes;
  current.code_counters = codeCounters;
  return save(current);
}

module.exports = { DATA_FILE, load, save, saveHistory, saveRegistry };
