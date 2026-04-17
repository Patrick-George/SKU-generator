import streamlit as st
import pandas as pd
import itertools
import base64
import qrcode
import os
import anthropic
from io import BytesIO

# ==================================================
# CONSTANTS
# ==================================================
COPY_BOX_HEIGHT = 160
DEFAULT_SEPARATOR = ""
DEFAULT_EXTRAS_MODE = "Multiple"
EXTRAS_PER_PAGE = 8
MAX_SKU_HISTORY = 15

# ==================================================
# AI DESCRIPTION
# ==================================================
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


def generate_product_description(breakdown_items, category_name, sku):
    """Generate a natural language product description from SKU breakdown using Claude."""
    if not ANTHROPIC_API_KEY:
        return None, "ANTHROPIC_API_KEY environment variable not set."

    parts = "\n".join([f"- {item['name']} (code: {item['code']})" for item in breakdown_items])
    prompt = (
        f"You are a product copywriter for Blastline India, an industrial equipment company. "
        f"Write a concise, professional 2-3 sentence product description based on these specifications.\n\n"
        f"Product Category: {category_name}\n"
        f"SKU: {sku}\n"
        f"Specifications:\n{parts}\n\n"
        f"Write a natural, readable description suitable for a product catalog. "
        f"Do not use bullet points. Do not repeat the SKU code. Do not use markdown headings. "
        f"Output plain text only, no formatting."
    )

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text, None
    except Exception as e:
        return None, str(e)


_FITTINGS_RULE = (
    'FITTINGS RULE: A fitting was selected. Append " + F" at the end of the item name, '
    'and " + Fittings" at the end of the item description. '
    'Do NOT include the specific fitting name or code.\n\n'
)


def generate_product_name_and_description(breakdown_items, category_name, sku, extras_items=None, fittings_selected=False):
    """Generate both an item name and item description from SKU breakdown using Claude."""
    if not ANTHROPIC_API_KEY:
        return None, None, "ANTHROPIC_API_KEY environment variable not set."

    display_items = [item for item in breakdown_items if item.get("field") != "Fittings"]
    parts = "\n".join([f"- {item['name']} (code: {item['code']})" for item in display_items])
    extras_str = ""
    if extras_items:
        extras_str = "\nExtras selected:\n" + "\n".join(
            [f"- {item['name']} (code: {item['code']})" for item in extras_items]
        )

    machine_code = breakdown_items[0]["code"] if breakdown_items else ""
    machine_name = breakdown_items[0]["name"] if breakdown_items else category_name

    prompt = (
        f"You are generating item names for Blastline India's inventory system.\n\n"
        f"Product Category: {category_name}\n"
        f"Machine: {machine_code} - {machine_name}\n"
        f"SKU: {sku}\n"
        f"Specifications:\n{parts}{extras_str}\n\n"
        f"{_FITTINGS_RULE if fittings_selected else ''}"
        f"Generate TWO things. Use ALL the specification fields above — do not skip any.\n\n"
        f"1. ITEM NAME (Tally Name): An abbreviation-only product name. NO full words allowed.\n"
        f"   Rules:\n"
        f"   - ONLY use abbreviations — no full words at all\n"
        f"   - Many field names already contain abbreviations in parentheses like 'Flat Sand Valve(FSV)' or 'Automatic(A)' or 'Moisture Separator(MS)'. Extract the abbreviation from inside the parentheses and use ONLY that.\n"
        f"   - If a field name has no parenthesized abbreviation, create a short one from the first letters\n"
        f"   - Start with the machine name abbreviation (extract from parentheses if present, otherwise use the code: {machine_code})\n"
        f"   - For capacity, just use the number (e.g. 200)\n"
        f"   - Separate fields with commas, no spaces\n"
        f"   - If extras selected, add ' + ' then extras abbreviations (from parentheses) comma-separated\n"
        f"   Example: BLBM200AT,SV,1 + MS,PG,RV\n\n"
        f"2. ITEM DESCRIPTION: A full, human-readable single-line description. Spell out everything EXCEPT extras.\n"
        f"   Rules:\n"
        f"   - Start with full machine name (without any parenthesized abbreviation): '{machine_name}'\n"
        f"   - Include the machine code after the name: '{machine_code}'\n"
        f"   - For capacity, use the number followed by 'Ltr' (e.g. '200Ltr')\n"
        f"   - Spell out every field in full (strip any parenthesized abbreviations from the names)\n"
        f"   - Certification in parentheses (e.g. '(Third Party Tested)')\n"
        f"   - Use 'w/' for 'with' (e.g. 'w/ Flat Sand Valve')\n"
        f"   - Include screen/cover status (e.g. 'w/ Screen + Cover')\n"
        f"   - If extras, add '+ Extras: ' then extras abbreviations (from parentheses) comma-separated — do NOT spell out extras\n"
        f"   Example: Blastline Blast Machine BL 24650 200Ltr Automatic (Third Party Tested) w/ Flat Sand Valve w/ Screen + Cover + Extras: MS,PG,RV\n\n"
        f"Output EXACTLY in this format (no extra text, no markdown):\n"
        f"NAME: <the item name>\n"
        f"DESCRIPTION: <the item description>"
    )

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        response_text = message.content[0].text.strip()

        item_name = ""
        description = ""
        for line in response_text.split("\n"):
            line = line.strip()
            if line.upper().startswith("NAME:"):
                item_name = line[5:].strip()
            elif line.upper().startswith("DESCRIPTION:"):
                description = line[12:].strip()

        if not item_name and not description:
            return None, None, "Could not parse AI response."

        return item_name, description, None
    except Exception as e:
        return None, None, str(e)


# ==================================================
# HELPERS
# ==================================================
def generate_mapped_name_and_description(sel, ordered_field_names, chosen, fittings_selected):
    """Build item name and description deterministically from tally_name/description mappings."""
    tally_parts = []
    desc_parts = []
    for k in ordered_field_names:
        s = sel.get(k)
        if not s or not s.get("code"):
            continue
        if k.lower() == "fittings":
            continue
        tn = s.get("tally_name", "").strip()
        if tn:
            tally_parts.append(tn)
        dd = s.get("description", "").strip()
        if dd:
            desc_parts.append(dd)

    item_name = " ".join(tally_parts)

    if chosen:
        extras_tally = [c.get("tally_name", "").strip() or c.get("name", "") for c in chosen]
        item_name += " + " + ",".join(extras_tally)

    if fittings_selected:
        item_name += " + F"

    item_desc = " ".join(desc_parts)

    if chosen:
        extras_desc = [c.get("tally_name", "").strip() or c.get("name", "") for c in chosen]
        item_desc += " + Extras: " + ",".join(extras_desc)

    if fittings_selected:
        item_desc += " + Fittings"

    return item_name, item_desc


def get_option_label(o):
    """Format option for display in selectbox."""
    return f"{o['code']} : {o['name']}"


def format_fitting_option(opt):
    """Format a fitting option to visually separate inlet and outlet."""
    name = opt.get("name", "")
    code = opt.get("code", "")
    if " + " in name:
        inlet, outlet = name.split(" + ", 1)
        return f"{code}  —  Inlet: {inlet}  |  Outlet: {outlet}"
    if name.lower() == "none":
        return f"{code} - None"
    return f"{code}  —  Outlet: {name}"


def parse_fitting_parts(name):
    """Split a fitting option name into (inlet, outlet) strings."""
    if " + " in name:
        inlet, outlet = name.split(" + ", 1)
        return inlet.strip(), outlet.strip()
    if name.lower() == "none":
        return None, None
    return None, name.strip()


def normalize_fields(cat):
    """
    Normalize category fields structure to ensure consistent format.
    Converts legacy field formats to new structure with 'order' and 'options'.
    """
    fields = {}
    for i, (k, v) in enumerate(cat.get("fields", {}).items(), start=1):
        if isinstance(v, dict):
            fields[k] = v
        else:
            fields[k] = {"order": i, "options": v}
    cat["fields"] = fields


def ordered_fields(fields):
    """Return field names sorted by their order value."""
    return sorted(fields.keys(), key=lambda k: fields[k].get("order", 999))


def get_machine_field(cat_data):
    """Return the name of the machine-selector field for a category."""
    return cat_data.get("settings", {}).get("machine_field", "Machine")


def filter_for_machine(items, machine_code):
    """
    Return only items whose 'machines' tag includes machine_code.
    Items with no 'machines' key or an empty list pass through (shown for all machines).
    """
    if not machine_code:
        return items
    return [
        item for item in items
        if not item.get("machines") or machine_code in item["machines"]
    ]


def normalize_option_df(data):
    """Convert options list to normalized DataFrame for editing."""
    cols = ["code", "name", "tally_name", "description", "order"]
    df = pd.DataFrame(data or [], columns=cols)
    if df.empty:
        df = pd.DataFrame(columns=cols)
    for c in ["tally_name", "description"]:
        if c not in df.columns:
            df[c] = ""
    df["tally_name"] = df["tally_name"].fillna("")
    df["description"] = df["description"].fillna("")
    if df["order"].isnull().all():
        df["order"] = range(1, len(df) + 1)
    return df[cols]


def normalize_extras_df(data):
    """Convert extras list to normalized DataFrame for editing."""
    cols = ["code", "name", "tally_name", "description", "order"]
    df = pd.DataFrame(data or [], columns=cols)
    if df.empty:
        df = pd.DataFrame(columns=cols)
    for c in ["tally_name", "description"]:
        if c not in df.columns:
            df[c] = ""
    df["tally_name"] = df["tally_name"].fillna("")
    df["description"] = df["description"].fillna("")
    if "order" not in df.columns or df["order"].isnull().all():
        df["order"] = range(1, len(df) + 1)
    return df[cols]


def generate_full_matrix(cat_data):
    """Generate all possible SKU combinations for a category."""
    normalize_fields(cat_data)
    fields = cat_data["fields"]
    sep = cat_data.get("settings", {}).get("separator", DEFAULT_SEPARATOR)

    field_combos = []
    field_names = []

    for f in ordered_fields(fields):
        opts = fields[f]["options"]
        is_text = opts and opts[0].get("type") == "text"
        if not is_text and opts:
            field_names.append(f)
            field_combos.append([o["code"] for o in opts])

    if not field_combos:
        return pd.DataFrame(columns=["SKU"] + field_names)

    combinations = list(itertools.product(*field_combos))

    rows = []
    for combo in combinations:
        sku = sep.join(combo)
        row = {"SKU": sku}
        for i, fname in enumerate(field_names):
            row[fname] = combo[i]
        rows.append(row)

    return pd.DataFrame(rows)


def big_copy_box(text):
    """Generate HTML for large, clickable SKU display with copy functionality."""
    return f"""
    <style>
        .sku-container {{
            cursor: pointer;
            background: #111;
            border: 2px solid #4CAF50;
            border-radius: 14px;
            padding: 26px 15px;
            text-align: center;
            overflow: hidden;
        }}
        .sku-text {{
            font-family: monospace;
            color: #4CAF50;
            font-weight: 700;
            word-break: break-all;
            overflow-wrap: break-word;
            font-size: clamp(16px, 5vw, 44px);
        }}
        .sku-msg {{
            margin-top: 8px;
            color: #aaa;
            font-size: 14px;
        }}
        @media (max-width: 768px) {{
            .sku-container {{
                padding: 20px 10px;
            }}
            .sku-text {{
                font-size: clamp(14px, 4vw, 28px);
            }}
        }}
        @media (max-width: 480px) {{
            .sku-text {{
                font-size: clamp(12px, 3.5vw, 22px);
            }}
        }}
    </style>
    <div class="sku-container" onclick="copySKU()">
        <div class="sku-text">{text}</div>
        <div id="msg" class="sku-msg">📋 Click to copy</div>
    </div>
    <script>
    function copySKU(){{
        navigator.clipboard.writeText("{text}");
        let m=document.getElementById("msg");
        m.innerText="✅ Copied to clipboard";
        m.style.color="#4CAF50";
        setTimeout(()=>{{m.innerText="📋 Click to copy";m.style.color="#aaa";}},2000);
    }}
    </script>
    """


def generate_qr_code(text, size=200):
    """Generate a QR code image for the given text."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(text)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return buffer


def get_qr_code_base64(text):
    """Generate a QR code and return as base64 string for HTML embedding."""
    buffer = generate_qr_code(text)
    return base64.b64encode(buffer.getvalue()).decode()


def generate_qr_svg(text):
    """Generate a QR code as SVG string."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(text)
    qr.make(fit=True)

    matrix = qr.get_matrix()
    size = len(matrix)
    scale = 10

    svg_size = size * scale
    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_size}" height="{svg_size}" viewBox="0 0 {svg_size} {svg_size}">',
        f'<rect width="100%" height="100%" fill="white"/>',
    ]

    for y, row in enumerate(matrix):
        for x, cell in enumerate(row):
            if cell:
                svg_parts.append(
                    f'<rect x="{x * scale}" y="{y * scale}" width="{scale}" height="{scale}" fill="black"/>'
                )

    svg_parts.append('</svg>')
    return '\n'.join(svg_parts)


def show_success(message):
    """Display success message."""
    st.success(message)


def show_error(message):
    """Display error message."""
    st.error(message)


def show_info(message):
    """Display info message."""
    st.info(message)


# ==================================================
# NAVIGATION
# ==================================================
def go(p):
    """Navigate to a different page."""
    st.session_state["page"] = p
    st.rerun()


def render_sidebar_nav(current_page="home"):
    """Render the sidebar navigation with consistent styling."""

    st.markdown("""
        <style>
        @media (max-width: 768px) {
            [data-testid="stSidebar"][aria-expanded="true"] {
                min-width: 100%;
            }
        }
        </style>
        <script>
        function collapseSidebar() {
            const sidebar = window.parent.document.querySelector('[data-testid="stSidebarCollapsedControl"]');
            if (sidebar) {
                sidebar.click();
            }
        }
        </script>
    """, unsafe_allow_html=True)

    st.markdown("""
        <style>
        [data-testid="stSidebar"] {
            background: #fafbfc;
        }
        [data-testid="stSidebar"] .block-container {
            padding-top: 1.5rem;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("<p style='font-size:13px;font-weight:700;color:#aaa;text-transform:uppercase;letter-spacing:1px;font-family:Inter,sans-serif;'>Navigation</p>", unsafe_allow_html=True)

    pages = [
        ("home", "SKU Generator"),
        ("history", "SKU History"),
        ("decoder", "SKU Decoder"),
        ("scanner", "QR Scanner"),
        ("category_items", "Category - Item Pairs"),
    ]

    for page_id, page_name in pages:
        btn_type = "primary" if current_page == page_id else "secondary"
        if st.button(page_name, use_container_width=True, type=btn_type, key=f"nav_{page_id}_{current_page}"):
            if page_id != current_page:
                go(page_id)

    st.markdown("---")

    if st.button("⚙️ Settings", use_container_width=True, key=f"nav_settings_{current_page}"):
        go("login")


def add_to_sku_history(sku, description, category):
    """Add a SKU to history (avoid duplicates, limit size)."""
    if not sku:
        return

    history = st.session_state.get("sku_history", [])

    entry = {
        "sku": sku,
        "description": description,
        "category": category,
        "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
    }

    history = [h for h in history if h["sku"] != sku]
    history.insert(0, entry)

    if len(history) > MAX_SKU_HISTORY:
        history = history[:MAX_SKU_HISTORY]

    st.session_state["sku_history"] = history


def decode_sku(sku_code, inventory):
    """Decode a SKU code and return breakdown."""
    results = []

    for cat_name, cat_data in inventory.items():
        normalize_fields(cat_data)
        fields = cat_data.get("fields", {})
        extras = cat_data.get("extras", [])
        sep = cat_data.get("settings", {}).get("separator", DEFAULT_SEPARATOR)

        remaining = sku_code
        matched_parts = []
        matched = True

        for field_name in ordered_fields(fields):
            opts = fields[field_name].get("options", [])
            field_matched = False

            for opt in opts:
                if opt.get("type") == "text":
                    continue
                code = opt.get("code", "")
                if code and remaining.startswith(code):
                    matched_parts.append({
                        "field": field_name,
                        "code": code,
                        "name": opt.get("name", "")
                    })
                    remaining = remaining[len(code):]
                    if remaining.startswith(sep):
                        remaining = remaining[len(sep):]
                    field_matched = True
                    break

            if not field_matched and opts and not (opts[0].get("type") == "text"):
                matched = False
                break

        if remaining.startswith("X"):
            remaining = remaining[1:]
        elif remaining.startswith(sep + "X"):
            remaining = remaining[len(sep) + 1:]
        matched_extras = []
        for extra in extras:
            code = extra.get("code", "")
            if code and code in remaining:
                matched_extras.append({
                    "field": "Extra",
                    "code": code,
                    "name": extra.get("name", "")
                })
                remaining = remaining.replace(code, "", 1)

        if matched and matched_parts:
            results.append({
                "category": cat_name,
                "parts": matched_parts,
                "extras": matched_extras,
                "remaining": remaining.strip(sep)
            })

    return results
