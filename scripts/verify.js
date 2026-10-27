const storage = require("../lib/storage");
const sku = require("../lib/sku");

const data = storage.load();
const inventory = data.inventory;
const history = data.sku_history || [];
let skuOk = 0;
let skuBad = 0;
let decodeOk = 0;
let decodeBad = 0;
let codeOk = 0;
let codeBad = 0;
const problems = [];

for (const entry of history) {
  if (entry.config && Object.keys(entry.config).length && inventory[entry.category]) {
    const catData = inventory[entry.category];
    sku.normalizeFields(catData);
    const built = sku.buildSku(entry.category, catData, entry.config, entry.extras || []);
    if (built === entry.sku) skuOk += 1;
    else {
      skuBad += 1;
      if (problems.length < 8) problems.push(`SKU mismatch ${entry.short_code || ""} stored=${entry.sku} built=${built}`);
    }
    const order = sku.orderedFields(catData.fields);
    const signature = sku.computeConfigSignature(entry.category, entry.config, order, entry.extras || []);
    const found = sku.lookupShortCode(signature, data.short_codes);
    if (!entry.short_code || found === entry.short_code) codeOk += 1;
    else {
      codeBad += 1;
      if (problems.length < 8) problems.push(`code mismatch ${entry.short_code} lookup=${found} sig=${signature}`);
    }
  }
  const decoded = sku.decodeSku(entry.sku, inventory);
  const hit = decoded.find((r) => r.category === entry.category) || decoded[0];
  if (hit && hit.category === entry.category && !hit.remaining) decodeOk += 1;
  else {
    decodeBad += 1;
    if (problems.length < 8) {
      problems.push(`decode ${entry.sku} -> ${hit ? `${hit.category} left=${hit.remaining}` : "none"}`);
    }
  }
}

const categories = Object.keys(inventory).length;
const codes = Object.keys(data.short_codes || {}).length;
console.log(JSON.stringify({ categories, history: history.length, codes, skuOk, skuBad, decodeOk, decodeBad, codeOk, codeBad, problems }, null, 2));
if (skuBad || decodeBad) process.exitCode = 1;
