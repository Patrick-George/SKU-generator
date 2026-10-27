# Blastline SKU Configurator — project notes for resume and LinkedIn

Internal notes. Copy the sections below onto a resume or LinkedIn. Do not publish the default admin password or session secret.

## One line

Built a Node.js web app that configures industrial blast-equipment products, generates SKUs and short codes, and decodes existing codes back into product specs.

## What it is

Blastline SKU Configurator is a Node.js rewrite of an earlier Streamlit tool. It keeps the same data file: product inventory, SKU history, a short-code registry, and sequence counters.

Operators pick a product category (blast machines, air receivers, hoses), then capacity, fittings, certification, extras, and similar options. The app builds a SKU, a readable item name and description, and a short code such as `BL-024`. The same configuration always reuses the same short code. A decoder turns a pasted SKU or short code back into the matching parts.

Admins maintain the catalog without a code deploy: categories, fields, options, extras, which options appear for which machine, full combination exports, and JSON backup and restore.

## Tech stack

| Layer | Choice |
| --- | --- |
| Runtime | Node.js 18+ |
| HTTP server | Express 4 |
| Views | EJS (server-rendered pages) |
| Auth | express-session, password-gated admin routes, httpOnly cookie |
| Uploads | Multer (in-memory, 20 MB cap) for JSON backup import |
| Spreadsheets | ExcelJS (`.xlsx` history export) |
| Data | JSON file (`data/sku_data.json`), atomic write via temp file and rename |
| Front end | HTML forms, custom CSS, a small vanilla JS file (copy-to-clipboard, dynamic table rows) |
| Hosting | Hostinger Node.js app (`PORT`, `ADMIN_PASSWORD`, `SESSION_SECRET`) |

No database, no frontend framework, no build step. `npm start` runs `node server.js`.

## Architecture

- `server.js` — Express app, session, login and logout, static files, route mounting, error handler.
- `routes/pages.js` — public pages: generator, save, history, Excel export, decoder, category lookup.
- `routes/admin.js` — session-protected catalog editor, CSV matrix export, backup download, upload with preview then confirm (replace or merge).
- `lib/sku.js` — SKU build and decode, short-code allocation, history grouping, name and description mapping.
- `lib/storage.js` — load and save the JSON store. Also accepts Python-style `NaN` and `Infinity` so old Streamlit exports still load.
- `lib/excel.js` — history workbook.
- `scripts/verify.js` — checks stored history against rebuilt SKUs, decoder results, and short-code lookups.
- `views/` and `public/` — EJS templates and CSS.

## Features worth mentioning

- Configurable SKU rules per category: field order, separators, single or multiple extras, machine-specific fields and options.
- Short codes from a prefix plus a counter (`BL-001`). A signature of the full configuration is the registry key, so duplicates are reused instead of minted again.
- Decoder uses longest-prefix matching across every category, including extras and a category suffix (hoses end in `JF`).
- History keeps the latest 50 SKUs, with search, filters, grouping, and Excel download. Clearing history does not drop the short-code registry.
- Admin matrix export writes every valid code combination for a category to CSV, with a size guard.
- Backup is a JSON download. Import is two-step: parse and preview in the session, then replace the database or merge new categories only.
- Timestamps are stored in IST. Writes are atomic so a crash mid-save does not truncate the data file.

## Resume bullets

Use two or three. Lead with the outcome, then the Node.js work.

- Built a Node.js and Express product configurator that generates SKUs and reusable short codes for blast machines, air receivers, and hoses, replacing a Streamlit app while keeping the existing JSON data format.
- Implemented SKU encoding and a longest-prefix decoder, plus a short-code registry that reuses an existing code when the same configuration is saved again.
- Shipped an admin console for catalog editing, machine-to-option mapping, combination-matrix CSV export, and JSON backup and restore, with session auth and in-memory file uploads.
- Added Excel history export with ExcelJS and a verification script that rebuilds stored SKUs and checks them against the decoder and short-code registry.
- Deployed the app as a Hostinger Node.js web app (Node 18+, environment-based port, admin password, and session secret).

## LinkedIn

**Project title:** Blastline SKU Configurator

**Skills to attach:** Node.js, Express.js, JavaScript, REST, server-side rendering, session authentication, file uploads, Excel export, JSON data stores

**About / Featured (short):**

I built the Node.js version of Blastline’s SKU configurator. Sales and operations staff configure blast machines, air receivers, and hoses in the browser. The app assembles a SKU from category rules, assigns a short code, and can decode a code back into the original parts.

The server is Express with EJS templates. Catalog, history, and short codes live in one JSON file, written atomically so a failed save cannot corrupt it. Admin routes are behind an express-session login. Admins edit fields and options, map which options belong to which machine, export the full combination matrix as CSV, and import or export JSON backups. History exports to Excel through ExcelJS. The same data shape as the earlier Streamlit app is supported, including Python `NaN` values in old exports.

**About / Featured (one paragraph, if the box is small):**

Built a Node.js/Express SKU configurator for industrial blast equipment. Users configure a product and get a generated SKU, item name, and a reusable short code. A decoder resolves existing codes with longest-prefix matching. Admin tools cover catalog editing, machine-specific option mapping, CSV matrix export, Excel history export, and JSON backup/restore. Data is a single JSON file with atomic writes. Session-based admin auth. Deployed on Hostinger (Node 18+).

## Keywords

Node.js, Express, EJS, JavaScript, express-session, Multer, ExcelJS, server-side rendering, file-based persistence, SKU generation, product configurator, CSV export, JSON backup and restore, session authentication
