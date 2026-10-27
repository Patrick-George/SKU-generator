const CATEGORY_SUFFIXES = { Hose: "JF" };
const DEFAULT_SEPARATOR = "";
const DEFAULT_EXTRAS_MODE = "Multiple";
const MAX_SKU_HISTORY = 50;
const HISTORY_CATEGORY_ORDER = ["Blast Machine", "Air Receiver", "Hose"];

function getCategorySuffix(category) {
  return CATEGORY_SUFFIXES[category] || "";
}

function nowIstString() {
  const now = new Date(Date.now() + 5.5 * 60 * 60 * 1000);
  const dd = String(now.getUTCDate()).padStart(2, "0");
  const mm = String(now.getUTCMonth() + 1).padStart(2, "0");
  const yyyy = now.getUTCFullYear();
  const hh = String(now.getUTCHours()).padStart(2, "0");
  const min = String(now.getUTCMinutes()).padStart(2, "0");
  return `${dd}/${mm}/${yyyy} ${hh}:${min}`;
}

function formatHistoryTimestamp(ts) {
  if (!ts) return ["", ""];
  const text = String(ts).trim();
  let day;
  let month;
  let year;
  let hour;
  let minute;
  let m = text.match(/^(\d{2})\/(\d{2})\/(\d{4}) (\d{2}):(\d{2})$/);
  if (m) {
    day = +m[1];
    month = +m[2];
    year = +m[3];
    hour = +m[4];
    minute = +m[5];
  } else {
    m = text.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?$/);
    if (m) {
      year = +m[1];
      month = +m[2];
      day = +m[3];
      hour = +m[4];
      minute = +m[5];
    }
  }
  if (day == null || month < 1 || month > 12 || day < 1 || day > 31) return [text, ""];
  const dateStr = `${String(day).padStart(2, "0")}/${String(month).padStart(2, "0")}/${year}`;
  const ampm = hour >= 12 ? "PM" : "AM";
  const h12 = hour % 12 || 12;
  const timeStr = `${String(h12).padStart(2, "0")}:${String(minute).padStart(2, "0")} ${ampm}`;
  return [dateStr, timeStr];
}

function parseMeters(name) {
  const m = /^\s*([\d.]+)\s*mtr/i.exec(name || "");
  return m ? parseFloat(m[1]) : null;
}

function applyWhipPaintOverride(sel) {
  const app = sel.Application;
  const roll = sel["Roll Length"];
  if (!app || app.code !== "HP" || !roll) return sel;
  const meters = parseMeters(roll.name || "");
  if (meters == null || meters >= 5) return sel;
  return {
    ...sel,
    Application: { ...app, tally_name: "Whip Paint Hose", description: "Whip Paint Hose" },
  };
}

function generateMappedNameAndDescription(sel, orderedFieldNames, chosen, fittingsSelected, fields) {
  sel = applyWhipPaintOverride(sel);
  const tallyParts = [];
  const descParts = [];
  let fittingsDesc = "";
  for (const k of orderedFieldNames) {
    if (fields && isTextField(fields[k])) continue;
    const s = sel[k];
    if (!s || !s.code) continue;
    const isFittings = k.toLowerCase() === "fittings";
    if (!isFittings) {
      const tn = (s.tally_name || "").trim();
      if (tn) tallyParts.push(tn);
      const dd = (s.description || "").trim();
      if (dd) descParts.push(dd);
    } else {
      fittingsDesc = (s.description || "").trim();
    }
  }
  let itemName = tallyParts.join(" ");
  if (chosen && chosen.length) {
    const extrasTally = chosen.map((c) => (c.tally_name || "").trim() || c.name || "");
    itemName += " + " + extrasTally.join(",");
  }
  if (fittingsSelected) itemName += " + F";
  let itemDesc = descParts.join(" ");
  if (fittingsDesc) itemDesc += " + " + fittingsDesc;
  if (chosen && chosen.length) {
    const extrasDesc = chosen.map((c) => (c.tally_name || "").trim() || c.name || "");
    itemDesc += " + Extras: " + extrasDesc.join(",");
  }
  return [itemName, itemDesc];
}

function formatFittingOption(opt) {
  const name = opt.name || "";
  const code = opt.code || "";
  if (name.includes(" + ")) {
    const [inlet, outlet] = name.split(" + ");
    return `${code}  —  Inlet: ${inlet}  |  Outlet: ${outlet}`;
  }
  if (name.toLowerCase() === "none") return `${code} - None`;
  return `${code}  —  Outlet: ${name}`;
}

function parseFittingParts(name) {
  if (name.includes(" + ")) {
    const [inlet, outlet] = name.split(" + ");
    return [inlet.trim(), outlet.trim()];
  }
  if ((name || "").toLowerCase() === "none") return [null, null];
  return [null, (name || "").trim()];
}

function normalizeFields(cat) {
  const fields = {};
  let i = 1;
  for (const [k, v] of Object.entries(cat.fields || {})) {
    if (v && typeof v === "object" && !Array.isArray(v)) fields[k] = v;
    else fields[k] = { order: i, options: v };
    i += 1;
  }
  cat.fields = fields;
  return cat;
}

function orderedFields(fields) {
  return Object.keys(fields || {}).sort((a, b) => {
    const oa = fields[a].order ?? 999;
    const ob = fields[b].order ?? 999;
    if (oa !== ob) return oa - ob;
    if (a < b) return -1;
    if (a > b) return 1;
    return 0;
  });
}

function isTextField(fieldData) {
  const opts = (fieldData && fieldData.options) || [];
  return Boolean(opts.length) && opts[0].type === "text";
}

function getMachineField(catData) {
  return (catData.settings || {}).machine_field || "Machine";
}

function filterForMachine(items, machineCode) {
  if (!machineCode) return items || [];
  return (items || []).filter((item) => !("machines" in item) || item.machines.includes(machineCode));
}

function mergeEditorRecords(oldItems, editedRecords) {
  const buckets = new Map();
  for (const item of oldItems || []) {
    const key = item.code;
    if (!buckets.has(key)) buckets.set(key, []);
    buckets.get(key).push(item);
  }
  const merged = [];
  for (const rec of editedRecords) {
    const next = { ...rec };
    const bucket = buckets.get(next.code);
    if (bucket && bucket.length) {
      const prev = bucket.shift();
      for (const [k, v] of Object.entries(prev)) {
        if (!(k in next)) next[k] = v;
      }
    } else if (next.code) {
      if (!("machines" in next)) next.machines = [];
    }
    merged.push(next);
  }
  return merged;
}

function getCategorySuffixSafe(categoryName) {
  return categoryName ? getCategorySuffix(categoryName) : "";
}

function matrixFieldPlan(catData) {
  normalizeFields(catData);
  const fields = catData.fields || {};
  const names = [];
  const lists = [];
  for (const f of orderedFields(fields)) {
    const opts = fields[f].options || [];
    if (isTextField(fields[f]) || !opts.length) continue;
    names.push(f);
    lists.push(opts.map((o) => o.code));
  }
  let total = lists.length ? 1 : 0;
  for (const list of lists) total *= list.length;
  return { names, lists, total };
}

function iterateMatrix(catData, categoryName, limit) {
  const { names, lists, total } = matrixFieldPlan(catData);
  const sep = (catData.settings || {}).separator ?? DEFAULT_SEPARATOR;
  const suffix = getCategorySuffixSafe(categoryName);
  const rows = [];
  if (!lists.length) return { total: 0, rows, names };
  const idx = lists.map(() => 0);
  const cap = limit == null ? total : Math.min(limit, total);
  for (let n = 0; n < cap; n += 1) {
    const combo = idx.map((i, fi) => lists[fi][i]);
    let sku = combo.join(sep);
    if (sku && suffix) sku += suffix;
    const row = { SKU: sku };
    names.forEach((name, i) => {
      row[name] = combo[i];
    });
    rows.push(row);
    let carry = lists.length - 1;
    while (carry >= 0) {
      idx[carry] += 1;
      if (idx[carry] < lists[carry].length) break;
      idx[carry] = 0;
      carry -= 1;
    }
  }
  return { total, rows, names };
}

function toCsv(rows) {
  if (!rows.length) return "";
  const headers = Object.keys(rows[0]);
  const esc = (v) => {
    const s = v == null ? "" : String(v);
    if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
    return s;
  };
  return [headers.join(","), ...rows.map((r) => headers.map((h) => esc(r[h])).join(","))].join("\n");
}

function padShortCodesInPlace(data) {
  let changed = false;
  const shortCodes = data.short_codes || {};
  const history = data.sku_history || [];
  const oldToNew = {};
  for (const rec of Object.values(shortCodes)) {
    if (!rec || typeof rec !== "object") continue;
    let prefix = rec.prefix;
    let seq = rec.seq;
    if (prefix == null || seq == null) {
      const code = String(rec.code || "");
      const cut = code.lastIndexOf("-");
      if (cut !== -1) {
        const num = code.slice(cut + 1);
        if (/^\d+$/.test(num)) {
          prefix = code.slice(0, cut);
          seq = parseInt(num, 10);
          if (rec.prefix == null) rec.prefix = prefix;
          if (rec.seq == null) rec.seq = seq;
        }
      }
    }
    if (prefix == null || seq == null) continue;
    let newCode;
    try {
      newCode = `${String(prefix).toUpperCase()}-${String(parseInt(seq, 10)).padStart(3, "0")}`;
    } catch {
      continue;
    }
    const oldCode = rec.code;
    if (oldCode !== newCode) {
      if (oldCode) oldToNew[String(oldCode)] = newCode;
      rec.code = newCode;
      rec.prefix = String(prefix).toUpperCase();
      changed = true;
    }
  }
  if (Object.keys(oldToNew).length) {
    for (const entry of history) {
      if (!entry || typeof entry !== "object") continue;
      if (entry.short_code in oldToNew) {
        entry.short_code = oldToNew[entry.short_code];
        changed = true;
      }
    }
  }
  return changed;
}

function configFieldText(config, nameParts, exclude) {
  if (!config) return "";
  const lowered = nameParts.map((p) => p.toLowerCase());
  const excludeL = (exclude || []).map((e) => e.toLowerCase());
  for (const [key, val] of Object.entries(config)) {
    const keyL = String(key).toLowerCase();
    if (excludeL.length && excludeL.some((e) => keyL.includes(e))) continue;
    if (lowered.every((p) => keyL.includes(p))) return ((val && (val.name || val.code)) || "").trim();
  }
  return "";
}

function getHistoryClientInfo(entry) {
  const config = entry.config || {};
  let name = configFieldText(config, ["client", "name"], ["abbrev"]);
  if (!name) name = configFieldText(config, ["client"], ["abbrev"]);
  let abbr = "";
  for (const [key, val] of Object.entries(config)) {
    if (!String(key).toLowerCase().includes("abbrev")) continue;
    abbr = ((val && (val.code || val.name)) || "").trim();
    if (abbr) break;
  }
  return [name, abbr];
}

function getHistoryMachineKey(entry, inventory) {
  const machineCode = entry.machine_code;
  const machineName = entry.machine_name;
  if (machineCode) return [machineCode, machineName || machineCode];
  const cat = entry.category;
  const config = entry.config || {};
  if (cat && inventory[cat]) {
    const mfName = getMachineField(inventory[cat]);
    const machineInfo = config[mfName] || {};
    if (machineInfo.code) return [machineInfo.code, machineInfo.name || machineInfo.code];
    const sku = entry.sku;
    if (sku) {
      const decodeResults = decodeSku(sku, inventory);
      const catMatch = decodeResults.find((r) => r.category === cat);
      if (catMatch) {
        for (const part of catMatch.parts || []) {
          if (part.field === mfName) return [part.code, part.name || part.code];
        }
      }
    }
  }
  return ["—", "Unknown"];
}

function isCustomBlastMachine(entry, inventory) {
  const mcode = (entry.machine_code || "").toUpperCase();
  if (mcode === "CBM") return true;
  const mname = (entry.machine_name || "").toLowerCase();
  if (mname.includes("custom") && mname.includes("blast")) return true;
  if (inventory) {
    const [code, name] = getHistoryMachineKey(entry, inventory);
    if (String(code).toUpperCase() === "CBM") return true;
    const nameL = String(name).toLowerCase();
    if (nameL.includes("custom") && nameL.includes("blast")) return true;
  }
  return false;
}

function getHistoryIdentity(entry, inventory) {
  const [clientName, clientAbbr] = getHistoryClientInfo(entry);
  if (isCustomBlastMachine(entry, inventory) && (clientName || clientAbbr)) {
    if (clientName && clientAbbr) return `${clientName} (${clientAbbr})`;
    return clientName || clientAbbr;
  }
  const [mcode, mname] = getHistoryMachineKey(entry, inventory);
  if (mcode && mname && mcode !== mname && mcode !== "—") return `${mcode} — ${mname}`;
  return mname || mcode || "Unknown";
}

function getHistorySpecsSummary(entry, maxParts = 3) {
  const config = entry.config || {};
  if (!Object.keys(config).length) {
    const desc = (entry.description || entry.mapped_name || "").trim();
    return desc.length > 60 ? `${desc.slice(0, 57)}…` : desc;
  }
  const preferred = ["capacity", "configuration", "certification", "valve", "screen", "fittings"];
  const skip = ["machine", "client", "version", "customization", "other"];
  const parts = [];
  const used = new Set();
  for (const pref of preferred) {
    for (const [key, val] of Object.entries(config)) {
      const keyL = String(key).toLowerCase();
      if (used.has(key) || !keyL.includes(pref)) continue;
      if (keyL.includes("client") || keyL.includes("machine")) continue;
      const label = ((val && (val.name || val.code)) || "").trim();
      if (label) {
        parts.push(label);
        used.add(key);
        break;
      }
    }
    if (parts.length >= maxParts) break;
  }
  if (parts.length < maxParts) {
    for (const [key, val] of Object.entries(config)) {
      if (used.has(key)) continue;
      const keyL = String(key).toLowerCase();
      if (skip.some((s) => keyL.includes(s))) continue;
      if (val && val.is_text) continue;
      const label = ((val && (val.name || val.code)) || "").trim();
      if (label) {
        parts.push(label);
        used.add(key);
      }
      if (parts.length >= maxParts) break;
    }
  }
  return parts.join(" · ");
}

function historyEntryMatchesQuery(entry, inventory, query) {
  const q = (query || "").trim().toLowerCase();
  if (!q) return true;
  const [clientName, clientAbbr] = getHistoryClientInfo(entry);
  const [mcode, mname] = getHistoryMachineKey(entry, inventory);
  const haystacks = [
    entry.sku,
    entry.short_code,
    entry.category,
    entry.description,
    entry.mapped_name,
    clientName,
    clientAbbr,
    mcode,
    mname,
    getHistoryIdentity(entry, inventory),
    getHistorySpecsSummary(entry),
  ];
  return haystacks.some((h) => h && String(h).toLowerCase().includes(q));
}

function filterSkuHistory(history, inventory, query = "", filterKey = "all") {
  const results = [];
  for (const entry of history) {
    const cat = entry.category || "Other";
    if (filterKey === "cbm") {
      if (!isCustomBlastMachine(entry, inventory)) continue;
    } else if (filterKey && filterKey !== "all") {
      if (cat !== filterKey) continue;
    }
    if (!historyEntryMatchesQuery(entry, inventory, query)) continue;
    results.push(entry);
  }
  return results;
}

function historyFilterOptions(history) {
  const options = [
    ["All", "all"],
    ["Custom (CBM)", "cbm"],
  ];
  const present = new Set(history.map((e) => e.category || "Other"));
  for (const cat of HISTORY_CATEGORY_ORDER) {
    if (present.has(cat)) options.push([cat, cat]);
  }
  for (const cat of [...present].sort()) {
    if (!HISTORY_CATEGORY_ORDER.includes(cat)) options.push([cat, cat]);
  }
  return options;
}

function groupHistoryForDisplay(entries, inventory, groupBy = "recent") {
  if (!entries.length) return [];
  if (groupBy === "recent") return [["Recent", entries.slice()]];
  const buckets = new Map();
  const order = [];
  for (const entry of entries) {
    let key;
    if (groupBy === "client") {
      const [clientName, clientAbbr] = getHistoryClientInfo(entry);
      if (isCustomBlastMachine(entry, inventory) && (clientName || clientAbbr)) {
        key = clientName && clientAbbr ? `${clientName} (${clientAbbr})` : clientName || clientAbbr;
      } else if (isCustomBlastMachine(entry, inventory)) {
        key = "Custom (no client)";
      } else {
        const [mcode, mname] = getHistoryMachineKey(entry, inventory);
        key = mcode !== "—" ? `${mcode} — ${mname}` : mname || "Other";
      }
    } else {
      const [mcode, mname] = getHistoryMachineKey(entry, inventory);
      key = mcode && mcode !== "—" ? `${mcode} — ${mname}` : mname || "Unknown";
    }
    if (!buckets.has(key)) {
      buckets.set(key, []);
      order.push(key);
    }
    buckets.get(key).push(entry);
  }
  let titles = order;
  if (groupBy === "client") {
    titles = order.slice().sort((a, b) => {
      const rank = (title) => {
        const sample = buckets.get(title)[0] || {};
        if (isCustomBlastMachine(sample, inventory)) return title === "Custom (no client)" ? [1, title.toLowerCase()] : [0, title.toLowerCase()];
        return [2, title.toLowerCase()];
      };
      const ra = rank(a);
      const rb = rank(b);
      if (ra[0] !== rb[0]) return ra[0] - rb[0];
      return ra[1] < rb[1] ? -1 : ra[1] > rb[1] ? 1 : 0;
    });
  } else {
    titles = order.slice().sort((a, b) => {
      const as = a.startsWith("—") ? 1 : 0;
      const bs = b.startsWith("—") ? 1 : 0;
      if (as !== bs) return as - bs;
      return a.toLowerCase() < b.toLowerCase() ? -1 : a.toLowerCase() > b.toLowerCase() ? 1 : 0;
    });
  }
  return titles.map((title) => [title, buckets.get(title)]);
}

function historyRowLabel(entry, inventory) {
  const identity = getHistoryIdentity(entry, inventory);
  const shortCode = entry.short_code || "—";
  const sku = entry.sku || "";
  const skuShort = sku.length <= 28 ? sku : `${sku.slice(0, 25)}…`;
  const specs = getHistorySpecsSummary(entry);
  const [dateStr] = formatHistoryTimestamp(entry.timestamp);
  const parts = [identity, String(shortCode), skuShort];
  if (specs) parts.push(specs);
  if (dateStr) parts.push(dateStr);
  return parts.join("   ·   ");
}

function computeConfigSignature(category, sel, orderedFieldNames, chosen) {
  const parts = [category || ""];
  for (const k of orderedFieldNames) {
    const s = sel[k];
    if (!s) continue;
    if (s.is_text) {
      const val = (s.name || "").trim();
      if (val) parts.push(`${k}=T:${val}`);
    } else if (s.code) {
      parts.push(`${k}=${s.code}`);
    }
  }
  const extraCodes = (chosen || []).map((c) => c.code || "").filter(Boolean).sort();
  if (extraCodes.length) parts.push(`X=${extraCodes.join(",")}`);
  return parts.join("|");
}

function getShortCodePrefix(category, sel, machineFieldName) {
  const s = machineFieldName ? sel[machineFieldName] : null;
  if (s && s.code) return String(s.code).toUpperCase();
  const letters = [...(category || "")].filter((ch) => /[a-z0-9]/i.test(ch)).join("");
  return (letters.slice(0, 3) || "SKU").toUpperCase();
}

function formatShortCode(prefix, seq) {
  return `${String(prefix).toUpperCase()}-${String(parseInt(seq, 10)).padStart(3, "0")}`;
}

function lookupShortCode(signature, shortCodes) {
  if (!signature || !shortCodes) return null;
  const rec = shortCodes[signature];
  return rec && rec.code ? rec.code : null;
}

function normalizeShortCodeText(text) {
  const t = String(text).trim().toUpperCase();
  const cut = t.lastIndexOf("-");
  if (cut === -1) return t;
  const prefix = t.slice(0, cut);
  const num = t.slice(cut + 1);
  if (/^\d+$/.test(num)) return `${prefix}-${String(parseInt(num, 10)).padStart(3, "0")}`;
  return t;
}

function findRegistryByCode(registry, text) {
  if (!registry || !text) return null;
  const t = String(text).trim().toUpperCase();
  const padded = normalizeShortCodeText(t);
  for (const rec of Object.values(registry)) {
    const code = String(rec.code || "").trim().toUpperCase();
    if (code === t || code === padded || normalizeShortCodeText(code) === padded) return rec;
  }
  return null;
}

function findCodeForSku(registry, sku) {
  if (!registry || !sku) return null;
  const s = String(sku).trim().toUpperCase();
  for (const rec of Object.values(registry)) {
    if (String(rec.sku || "").trim().toUpperCase() === s) return rec.code;
  }
  return null;
}

function stripSep(s, sep) {
  if (sep && s.startsWith(sep)) return s.slice(sep.length);
  return s;
}

function reverseString(s) {
  return [...s].reverse().join("");
}

function stripChars(s, chars) {
  if (!chars) return s;
  const set = new Set(chars);
  let i = 0;
  let j = s.length;
  while (i < j && set.has(s[i])) i += 1;
  while (j > i && set.has(s[j - 1])) j -= 1;
  return s.slice(i, j);
}

function validOptions(opts) {
  const out = [];
  for (const o of opts || []) {
    if (o.type === "text") continue;
    if (!o.code) continue;
    out.push(o);
  }
  return out;
}

function matchLongestPrefix(remaining, opts) {
  let best = null;
  let bestLen = 0;
  for (const opt of opts) {
    const code = opt.code || "";
    if (code && remaining.startsWith(code) && code.length > bestLen) {
      best = opt;
      bestLen = code.length;
    }
  }
  return [best, bestLen];
}

function splitBaseAndExtras(skuCode, sep, extras) {
  const extrasPool = validOptions(extras);
  if (!extrasPool.length) return [skuCode, ""];
  const marker = sep ? sep + "X" : "X";
  const idx = skuCode.lastIndexOf(marker);
  if (idx === -1) return [skuCode, ""];
  const tail = skuCode.slice(idx + marker.length);
  if (!tail) return [skuCode, ""];
  let t = tail;
  while (t) {
    const [opt, codeLen] = matchLongestPrefix(t, extrasPool);
    if (!opt) return [skuCode, ""];
    t = stripSep(t.slice(codeLen), sep);
  }
  return [skuCode.slice(0, idx), tail];
}

function decodeForCategory(skuCode, catName, catData) {
  normalizeFields(catData);
  const fields = catData.fields || {};
  const extras = catData.extras || [];
  const sep = (catData.settings || {}).separator ?? DEFAULT_SEPARATOR;
  const mfName = getMachineField(catData);
  let suffixPart = null;
  const catSuffix = getCategorySuffix(catName);
  if (catSuffix) {
    if (!skuCode.endsWith(catSuffix)) return null;
    skuCode = skuCode.slice(0, -catSuffix.length);
    skuCode = sep ? reverseString(stripSep(reverseString(skuCode), sep)) : skuCode;
    suffixPart = {
      field: "Manufacturer",
      code: catSuffix,
      name: catSuffix === "JF" ? "JollyFlex" : catSuffix,
    };
  }
  const mfOpts = mfName in fields ? validOptions(fields[mfName].options || []) : [];
  if (mfOpts.length) {
    const [mfHit] = matchLongestPrefix(skuCode, mfOpts);
    if (!mfHit) return null;
  }
  const [base, extrasStr] = splitBaseAndExtras(skuCode, sep, extras);
  let remaining = base;
  const matchedParts = [];
  let concreteMatches = 0;
  let machineMatched = false;
  let selectedMachineCode = null;
  const fieldOrder = orderedFields(fields);
  const fieldVisible = (fname) => {
    const fieldMachines = fields[fname].machines || [];
    if (!fieldMachines.length || !selectedMachineCode) return true;
    return fieldMachines.includes(selectedMachineCode);
  };
  for (let i = 0; i < fieldOrder.length; i += 1) {
    const fname = fieldOrder[i];
    if (!fieldVisible(fname)) continue;
    const rawOpts = fields[fname].options || [];
    const textField = Boolean(rawOpts.length) && rawOpts[0].type === "text";
    if (textField) {
      let nextOpts = [];
      for (let j = i + 1; j < fieldOrder.length; j += 1) {
        const nxt = fieldOrder[j];
        if (!fieldVisible(nxt)) continue;
        let no = validOptions(fields[nxt].options || []);
        if (selectedMachineCode) no = filterForMachine(no, selectedMachineCode);
        if (no.length) {
          nextOpts = no;
          break;
        }
      }
      if (nextOpts.length && remaining) {
        let bestIdx = -1;
        for (let k = 0; k <= remaining.length; k += 1) {
          const slice = remaining.slice(k);
          if (!slice) continue;
          const [matched] = matchLongestPrefix(slice, nextOpts);
          if (matched) {
            bestIdx = k;
            break;
          }
        }
        if (bestIdx > 0) {
          matchedParts.push({ field: fname, code: remaining.slice(0, bestIdx), name: remaining.slice(0, bestIdx) });
          remaining = stripSep(remaining.slice(bestIdx), sep);
        }
      }
      continue;
    }
    let opts = validOptions(rawOpts);
    if (selectedMachineCode) opts = filterForMachine(opts, selectedMachineCode);
    if (!opts.length) continue;
    const [opt, codeLen] = matchLongestPrefix(remaining, opts);
    if (!opt) continue;
    matchedParts.push({ field: fname, code: opt.code, name: opt.name || "" });
    concreteMatches += 1;
    remaining = stripSep(remaining.slice(codeLen), sep);
    if (fname === mfName) {
      selectedMachineCode = opt.code;
      machineMatched = true;
    }
  }
  const matchedExtras = [];
  let extrasPool = validOptions(extras);
  if (selectedMachineCode) extrasPool = filterForMachine(extrasPool, selectedMachineCode);
  let extrasRemaining = extrasStr;
  while (extrasRemaining) {
    const [opt, codeLen] = matchLongestPrefix(extrasRemaining, extrasPool);
    if (!opt) break;
    matchedExtras.push({ field: "Extra", code: opt.code, name: opt.name || "" });
    extrasRemaining = stripSep(extrasRemaining.slice(codeLen), sep);
  }
  let leftover = remaining;
  if (extrasRemaining) {
    if (leftover && sep) leftover += sep;
    leftover += extrasRemaining;
  }
  if (sep) leftover = stripChars(leftover, sep);
  if (!machineMatched && concreteMatches < 2) return null;
  if (suffixPart) {
    matchedParts.push(suffixPart);
    concreteMatches += 1;
  }
  return {
    category: catName,
    parts: matchedParts,
    extras: matchedExtras,
    remaining: leftover,
    score: [machineMatched ? 1 : 0, concreteMatches, -leftover.length],
  };
}

function decodeSku(skuCode, inventory) {
  if (!skuCode) return [];
  const candidates = [];
  for (const [catName, catData] of Object.entries(inventory || {})) {
    const result = decodeForCategory(skuCode, catName, catData);
    if (result) candidates.push(result);
  }
  candidates.sort((a, b) => {
    for (let i = 0; i < 3; i += 1) {
      if (a.score[i] !== b.score[i]) return b.score[i] - a.score[i];
    }
    return 0;
  });
  for (const r of candidates) delete r.score;
  return candidates;
}

function findOptionByCode(options, code) {
  const codeStr = String(code);
  for (const opt of options || []) {
    if (String(opt.code ?? "") === codeStr) return opt;
  }
  return null;
}

function buildSelectionFromDecode(decodeResult, catData) {
  normalizeFields(catData);
  const fields = catData.fields;
  const extrasList = catData.extras || [];
  const fieldOrder = orderedFields(fields);
  const sel = {};
  let fittingsSelected = false;
  for (const part of decodeResult.parts || []) {
    const fname = part.field;
    if (fname === "Manufacturer") continue;
    const code = part.code;
    if (!(fname in fields)) continue;
    const opts = fields[fname].options || [];
    const text = Boolean(opts.length) && opts[0].type === "text";
    if (text) {
      const name = part.name || code;
      sel[fname] = { code, name, tally_name: code, description: name };
    } else {
      const opt = findOptionByCode(opts, code);
      if (opt) {
        sel[fname] = {
          code: opt.code,
          name: opt.name || "",
          tally_name: opt.tally_name || "",
          description: opt.description || "",
        };
      } else {
        sel[fname] = { code, name: part.name || "", tally_name: "", description: "" };
      }
    }
    if (fname.toLowerCase() === "fittings" && code && String(part.name || "").toLowerCase() !== "none") {
      fittingsSelected = true;
    }
  }
  const chosen = [];
  for (const extra of decodeResult.extras || []) {
    const opt = findOptionByCode(extrasList, extra.code);
    if (opt) {
      chosen.push({
        code: opt.code,
        name: opt.name || "",
        tally_name: opt.tally_name || "",
        description: opt.description || "",
      });
    } else {
      chosen.push({ code: extra.code, name: extra.name || "", tally_name: "", description: "" });
    }
  }
  return { sel, fieldOrder, chosen, fittingsSelected };
}

function optionSelection(opt) {
  return {
    code: opt.code,
    name: opt.name,
    tally_name: opt.tally_name || "",
    description: opt.description || "",
  };
}

function buildSku(category, catData, sel, chosen) {
  const fields = catData.fields || {};
  const sep = (catData.settings || {}).separator ?? DEFAULT_SEPARATOR;
  const base = orderedFields(fields)
    .filter((k) => sel[k] && sel[k].code && !isTextField(fields[k]))
    .map((k) => sel[k].code)
    .join(sep);
  const extrasCodes = (chosen || []).map((c) => c.code).join("");
  let sku = base + (base && extrasCodes ? `${sep}X` : "") + extrasCodes;
  const suffix = getCategorySuffix(category);
  if (sku && suffix) sku += suffix;
  return sku;
}

function asList(value) {
  if (value == null || value === "") return [];
  return Array.isArray(value) ? value : [value];
}

function resolveForm(inventory, query) {
  const categories = Object.keys(inventory || {});
  if (!categories.length) return null;
  const category = categories.includes(query.category) ? query.category : categories[0];
  const catData = inventory[category];
  normalizeFields(catData);
  const fields = catData.fields;
  const fieldOrder = orderedFields(fields);
  const mfName = getMachineField(catData);
  const extrasMode = (catData.settings || {}).extras_mode || DEFAULT_EXTRAS_MODE;
  const sel = {};
  let selectedMachineCode = null;
  const widgets = [];

  if (fields[mfName] && !isTextField(fields[mfName])) {
    const mfOpts = (fields[mfName].options || []).filter((o) => o.code != null && o.code !== "");
    const picked = mfOpts.find((o) => o.code === query.machine) || mfOpts[0];
    if (picked) {
      sel[mfName] = optionSelection(picked);
      selectedMachineCode = picked.code;
      widgets.push({
        name: mfName,
        kind: "machine",
        options: mfOpts.map((o) => ({ code: o.code, label: `${o.code} - ${o.name}` })),
        value: picked.code,
      });
    }
  }

  for (const f of fieldOrder) {
    if (f === mfName) continue;
    const fieldMachines = fields[f].machines || [];
    if (fieldMachines.length && selectedMachineCode && !fieldMachines.includes(selectedMachineCode)) continue;
    const opts = fields[f].options || [];
    if (isTextField(fields[f])) {
      const txt = String(query[`txt_${f}`] || "");
      const clean = txt.trim();
      if (clean) {
        sel[f] = { code: "", name: clean, tally_name: "", description: clean, is_text: true };
      }
      widgets.push({
        name: f,
        kind: opts[0] && opts[0].multiline ? "textarea" : "text",
        value: txt,
      });
    } else {
      const filtered = (selectedMachineCode ? filterForMachine(opts, selectedMachineCode) : opts.slice()).filter((o) => o.code != null && o.code !== "");
      if (!filtered.length) continue;
      const picked = filtered.find((o) => o.code === query[`opt_${f}`]) || filtered[0];
      sel[f] = optionSelection(picked);
      const isFittings = f.toLowerCase() === "fittings";
      let inlet = null;
      let outlet = null;
      if (isFittings && String(picked.name || "").toLowerCase() !== "none") {
        [inlet, outlet] = parseFittingParts(picked.name || "");
      }
      widgets.push({
        name: f,
        kind: isFittings ? "fittings" : "select",
        options: filtered.map((o) => ({
          code: o.code,
          label: isFittings ? formatFittingOption(o) : `${o.code} - ${o.name}`,
        })),
        value: picked.code,
        inlet,
        outlet,
      });
    }
  }

  const extras = catData.extras || [];
  const visibleExtras = (selectedMachineCode ? filterForMachine(extras, selectedMachineCode) : extras.slice())
    .filter((e) => e.code != null && e.code !== "")
    .slice()
    .sort((a, b) => (a.order ?? 999) - (b.order ?? 999) || 0);
  const chosen = [];
  if (extrasMode === "Single") {
    const selectedName = query.extra_single || "None";
    if (selectedName !== "None") {
      const found = visibleExtras.find((e) => e.name === selectedName && e.code);
      if (found) chosen.push(optionSelection(found));
    }
  } else {
    const wanted = new Set(asList(query.extra));
    for (const extra of visibleExtras) {
      if (wanted.has(extra.code) && extra.code) chosen.push(optionSelection(extra));
    }
  }

  const sku = buildSku(category, catData, sel, chosen);
  const breakdown = [];
  let fittingsSelected = false;
  for (const k of fieldOrder) {
    if (isTextField(fields[k])) continue;
    if (sel[k] && sel[k].code && sel[k].name) {
      breakdown.push({ code: String(sel[k].code), name: String(sel[k].name), field: k });
      if (k.toLowerCase() === "fittings") fittingsSelected = true;
    }
  }
  const extrasItems = chosen.filter((c) => c.code && c.name).map((c) => ({ code: String(c.code), name: String(c.name) }));
  const allBreakdown = breakdown.concat(extrasItems);
  const [mappedName, mappedDesc] = sku
    ? generateMappedNameAndDescription(sel, fieldOrder, chosen, fittingsSelected, fields)
    : ["", ""];
  const signature = computeConfigSignature(category, sel, fieldOrder, chosen);
  const prefix = getShortCodePrefix(category, sel, mfName);
  return {
    categories,
    category,
    widgets,
    visibleExtras,
    extrasMode,
    chosenCodes: new Set(chosen.map((c) => c.code)),
    singleExtra: chosen[0] ? chosen[0].name : "None",
    sku,
    mappedName,
    mappedDesc,
    allBreakdown,
    signature,
    prefix,
    sel,
    chosen,
    mfName,
    selectedMachineCode,
    showItemName: category !== "Blast Machine",
  };
}

function allocateShortCode(storage, signature, prefix, meta) {
  const data = storage.load();
  const shortCodes = data.short_codes || {};
  const counters = data.code_counters || {};
  const existing = shortCodes[signature];
  if (existing && existing.code) return { code: existing.code, reused: true };
  const seq = parseInt(counters[prefix] || 0, 10) + 1;
  counters[prefix] = seq;
  const code = formatShortCode(prefix, seq);
  const record = {
    code,
    prefix,
    seq,
    signature,
    created_at: nowIstString(),
    ...(meta || {}),
  };
  record.code = code;
  shortCodes[signature] = record;
  storage.saveRegistry(shortCodes, counters);
  return { code, reused: false };
}

function addToSkuHistory(storage, payload) {
  const { sku, description, category, config, extras, machineCode, machineName, mappedName, mappedDesc, breakdownItems, signature, prefix } = payload;
  if (!sku) return null;
  let shortCode = null;
  let reused = false;
  if (signature && prefix) {
    const allocated = allocateShortCode(storage, signature, prefix, {
      category,
      sku,
      config: config || {},
      extras: extras || [],
      machine_code: machineCode,
      machine_name: machineName,
      mapped_name: mappedName,
      mapped_desc: mappedDesc != null ? mappedDesc : description,
      breakdown_items: breakdownItems || [],
    });
    shortCode = allocated.code;
    reused = allocated.reused;
  }
  const data = storage.load();
  let history = data.sku_history || [];
  const entry = {
    sku,
    short_code: shortCode,
    description,
    category,
    timestamp: nowIstString(),
    config: config || {},
    extras: extras || [],
    machine_code: machineCode,
    machine_name: machineName,
    mapped_name: mappedName,
    breakdown_items: breakdownItems || [],
  };
  history = history.filter((h) => h.sku !== sku);
  history.unshift(entry);
  if (history.length > MAX_SKU_HISTORY) history = history.slice(0, MAX_SKU_HISTORY);
  storage.saveHistory(history);
  return { entry, reused, shortCode };
}

function enrichHistoryEntry(entry, inventory) {
  let config = entry.config || {};
  let extras = entry.extras || [];
  let breakdown = entry.breakdown_items || [];
  let mappedName = entry.mapped_name;
  let mappedDesc = entry.description;
  const cat = entry.category;
  if (!Object.keys(config).length && inventory[cat]) {
    const decodeResults = decodeSku(entry.sku || "", inventory);
    const catMatch = decodeResults.find((r) => r.category === cat) || decodeResults[0];
    if (catMatch) {
      const catData = inventory[catMatch.category] || inventory[cat] || {};
      if (catData.fields) {
        const built = buildSelectionFromDecode(catMatch, catData);
        config = built.sel;
        extras = built.chosen;
        if (!breakdown.length) {
          breakdown = (catMatch.parts || []).map((p) => ({ code: p.code, name: p.name || "", field: p.field }));
          breakdown = breakdown.concat((catMatch.extras || []).map((e) => ({ code: e.code, name: e.name || "" })));
        }
        if (!mappedName || !mappedDesc) {
          const [name, desc] = generateMappedNameAndDescription(config, built.fieldOrder, extras, built.fittingsSelected, catData.fields);
          mappedName = mappedName || name;
          mappedDesc = mappedDesc || desc;
        }
      }
    }
  }
  const [clientName, clientAbbr] = getHistoryClientInfo({ ...entry, config });
  let clientLabel = "";
  if (clientName && clientAbbr) clientLabel = `${clientName} (${clientAbbr})`;
  else clientLabel = clientName || clientAbbr || "";
  const [dateStr, timeStr] = formatHistoryTimestamp(entry.timestamp);
  return { ...entry, config, extras, breakdown, mappedName, mappedDesc, clientLabel, dateStr, timeStr };
}

module.exports = {
  CATEGORY_SUFFIXES,
  DEFAULT_SEPARATOR,
  DEFAULT_EXTRAS_MODE,
  MAX_SKU_HISTORY,
  HISTORY_CATEGORY_ORDER,
  getCategorySuffix,
  nowIstString,
  formatHistoryTimestamp,
  generateMappedNameAndDescription,
  formatFittingOption,
  parseFittingParts,
  normalizeFields,
  orderedFields,
  isTextField,
  getMachineField,
  filterForMachine,
  mergeEditorRecords,
  matrixFieldPlan,
  iterateMatrix,
  toCsv,
  padShortCodesInPlace,
  getHistoryClientInfo,
  getHistoryIdentity,
  getHistorySpecsSummary,
  filterSkuHistory,
  historyFilterOptions,
  groupHistoryForDisplay,
  historyRowLabel,
  computeConfigSignature,
  lookupShortCode,
  findRegistryByCode,
  findCodeForSku,
  decodeSku,
  buildSelectionFromDecode,
  buildSku,
  resolveForm,
  addToSkuHistory,
  enrichHistoryEntry,
  isCustomBlastMachine,
};
