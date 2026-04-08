# Blastline SKU Configurator

A Streamlit web app for generating, decoding, and managing product SKU codes for Blastline India Pvt Ltd.

## Features

- **SKU Generator** — Select a product category and configure fields to build a structured SKU with optional extras.
- **SKU Decoder** — Paste an existing SKU to reverse-lookup its component fields and values.
- **QR Code** — Generate and download QR codes for any SKU; scan QR codes using the device camera.
- **History** — View the last 15 generated SKUs in the current session.
- **Category - Item Pairs** — Reference table of product categories and their item groups, with search filtering.
- **Admin Panel** — Manage categories, fields, options, extras, machine-based visibility, combination matrix export, and data backup/restore.

## Tech Stack

- **Python / Streamlit** — UI and application logic
- **pandas** — Data tables and CSV export
- **qrcode + Pillow** — QR code generation
- **JSON** — Local file-based data storage

## Project Structure

| File | Purpose |
|------|---------|
| `app.py` | Entry point — Streamlit config, session state init, page routing |
| `pages.py` | All page functions: home, login, admin, history, decoder, scanner |
| `helpers.py` | SKU building/decoding, QR generation, name/description mapping, navigation |
| `storage.py` | JSON-based persistence (load/save to `/data/sku_data.json`) |
| `data.json` | Seed data copied on first run |
| `category_items.json` | Category and item group reference data |

## Running Locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

The app runs on port **8501** by default.

## Dev Container

A `.devcontainer` config is included for Python 3.11. It installs dependencies and starts Streamlit automatically on attach.
