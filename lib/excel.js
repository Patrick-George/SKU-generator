const ExcelJS = require("exceljs");
const { formatHistoryTimestamp } = require("./sku");

async function historyWorkbook(entries, registry) {
  const skuToCode = {};
  for (const rec of Object.values(registry || {})) {
    if (rec.sku && rec.code && !(rec.sku in skuToCode)) skuToCode[rec.sku] = rec.code;
  }
  const rows = entries.map((entry) => {
    const sku = entry.sku || "";
    const shortCode = entry.short_code || skuToCode[sku] || "";
    const [dateStr, timeStr] = formatHistoryTimestamp(entry.timestamp);
    const created = dateStr && timeStr ? `${dateStr} ${timeStr}` : dateStr || timeStr || entry.timestamp || "";
    return {
      "Short Code": shortCode,
      SKU: sku,
      Name: (entry.mapped_name || "").trim(),
      Description: (entry.description || "").trim(),
      "Date Created": created,
    };
  });
  rows.sort((a, b) => {
    const split = (code) => {
      const text = String(code || "");
      const cut = text.lastIndexOf("-");
      if (cut === -1) return [text, Number.POSITIVE_INFINITY];
      const num = text.slice(cut + 1);
      return [text.slice(0, cut), /^\d+$/.test(num) ? parseInt(num, 10) : Number.POSITIVE_INFINITY];
    };
    const [ap, as] = split(a["Short Code"]);
    const [bp, bs] = split(b["Short Code"]);
    if (ap !== bp) return ap < bp ? -1 : 1;
    return as - bs;
  });

  const workbook = new ExcelJS.Workbook();
  const sheet = workbook.addWorksheet("SKU History");
  sheet.columns = [
    { header: "Short Code", key: "Short Code", width: 16 },
    { header: "SKU", key: "SKU", width: 36 },
    { header: "Name", key: "Name", width: 42 },
    { header: "Description", key: "Description", width: 64 },
    { header: "Date Created", key: "Date Created", width: 22 },
  ];
  for (const row of rows) sheet.addRow(row);
  sheet.getRow(1).font = { bold: true };
  return workbook.xlsx.writeBuffer();
}

module.exports = { historyWorkbook };
