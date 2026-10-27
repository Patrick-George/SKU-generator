# Blastline SKU Configurator

Node.js version of the SKU generator. It uses the same data file shape as the Streamlit app: inventory, history, short codes, and counters.

## Run locally

```bash
npm install
npm start
```

Open http://localhost:3000. Admin password defaults to `admin123`. Override it with `ADMIN_PASSWORD`.

The live database is `data/sku_data.json`.

## Hostinger

Use a plan that includes Node.js web apps.

1. In hPanel, create a Node.js app. Node 18 or newer. Startup file: `server.js`. The start command is `npm start`.
2. Upload this folder, including `data/sku_data.json`.
3. Set `PORT` from the panel if Hostinger injects one. The app already reads `process.env.PORT`.
4. Set `ADMIN_PASSWORD` and `SESSION_SECRET`.
5. Attach the domain. Hostinger provides SSL.

Replace `data/sku_data.json` with a fresh admin backup from the current site before pointing the domain here. History keeps the latest 50 SKUs. The short-code registry is not trimmed.
