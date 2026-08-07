import streamlit as st
import pandas as pd
import itertools
import os
import re
import anthropic

# ==================================================
# CONSTANTS
# ==================================================
COPY_BOX_HEIGHT = 160
DEFAULT_SEPARATOR = ""
DEFAULT_EXTRAS_MODE = "Multiple"
EXTRAS_PER_PAGE = 8
MAX_SKU_HISTORY = 50

HISTORY_CATEGORY_ORDER = ["Blast Machine", "Air Receiver", "Hose"]

# Per-category suffix appended to every generated SKU. Used to encode
# manufacturer/source identity that doesn't vary across configurations
# (e.g. all Blastline hoses are JollyFlex → "JF").
CATEGORY_SUFFIXES = {
    "Hose": "JF",
}


def get_category_suffix(category):
    """Return the constant suffix for a category's SKU, or '' if none."""
    return CATEGORY_SUFFIXES.get(category, "")

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
    'FITTINGS RULE: A fitting was selected. Append " + F" at the end of the item name. '
    'For the item description, append " + " followed by the fitting\'s Description mapping '
    '(e.g. "+ A Fittings", "+ B Fittings").\n\n'
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
def _parse_meters(name):
    """Extract the leading meter value from a Roll Length name like '15mtr' or '1.5mtr'.
    Returns float or None if not parseable (e.g. 'Custom')."""
    m = re.match(r"\s*([\d.]+)\s*mtr", name or "", re.IGNORECASE)
    return float(m.group(1)) if m else None


def _apply_whip_paint_override(sel):
    """Hose rule: Application=HP (Paint) with Roll Length strictly under 5m is a 'Whip Paint Hose'.
    5m and Custom (unparseable) keep the default 'Paint Hose'."""
    app = sel.get("Application")
    roll = sel.get("Roll Length")
    if not app or app.get("code") != "HP" or not roll:
        return sel
    meters = _parse_meters(roll.get("name", ""))
    if meters is None or meters >= 5:
        return sel
    return {
        **sel,
        "Application": {**app, "tally_name": "Whip Paint Hose", "description": "Whip Paint Hose"},
    }


def generate_mapped_name_and_description(sel, ordered_field_names, chosen, fittings_selected, fields=None):
    """Build item name and description deterministically from tally_name/description mappings."""
    sel = _apply_whip_paint_override(sel)
    tally_parts = []
    desc_parts = []
    fittings_desc = ""
    for k in ordered_field_names:
        if fields and is_text_field(fields[k]):
            continue
        s = sel.get(k)
        if not s or not s.get("code"):
            continue
        is_fittings = k.lower() == "fittings"
        if not is_fittings:
            tn = s.get("tally_name", "").strip()
            if tn:
                tally_parts.append(tn)
            dd = s.get("description", "").strip()
            if dd:
                desc_parts.append(dd)
        else:
            fittings_desc = s.get("description", "").strip()

    item_name = " ".join(tally_parts)

    if chosen:
        extras_tally = [c.get("tally_name", "").strip() or c.get("name", "") for c in chosen]
        item_name += " + " + ",".join(extras_tally)

    if fittings_selected:
        item_name += " + F"

    item_desc = " ".join(desc_parts)

    if fittings_desc:
        item_desc += " + " + fittings_desc

    if chosen:
        extras_desc = [c.get("tally_name", "").strip() or c.get("name", "") for c in chosen]
        item_desc += " + Extras: " + ",".join(extras_desc)

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


def is_text_field(field_data):
    """Return True if the field is a free-text input (not part of SKU/name/description)."""
    opts = field_data.get("options", [])
    return bool(opts) and opts[0].get("type") == "text"


def get_machine_field(cat_data):
    """Return the name of the machine-selector field for a category."""
    return cat_data.get("settings", {}).get("machine_field", "Machine")


def filter_for_machine(items, machine_code):
    """
    Return only items whose 'machines' tag includes machine_code.

    Convention:
      - 'machines' key absent → legacy unmigrated item, visible for all machines.
      - 'machines' key present (even if empty list) → visible only for the
        machine codes explicitly listed. An empty list means visible for none.

    This lets newly added fields/options/extras default to "no machines"
    (explicit opt-in) while keeping existing data that predates the feature
    visible everywhere until it is explicitly mapped.
    """
    if not machine_code:
        return items
    return [
        item for item in items
        if "machines" not in item or machine_code in item["machines"]
    ]


def merge_editor_records(old_items, edited_records):
    """
    Merge edited records from a st.data_editor back into the original list,
    preserving hidden keys (e.g. 'machines', 'type') that the editor strips.

    Matches old→new rows by `code` with occurrence tracking, so duplicate codes
    (e.g. two 'HP' rows in the same field) keep their independent mappings.
    Rows whose code doesn't match any old row keep only what the editor returned
    (correct for newly added rows; renames will lose their old mapping).
    """
    from collections import defaultdict

    buckets = defaultdict(list)
    for item in old_items:
        buckets[item.get("code")].append(item)

    merged = []
    for rec in edited_records:
        rec = dict(rec)
        bucket = buckets.get(rec.get("code"))
        if bucket:
            prev = bucket.pop(0)
            for k, v in prev.items():
                if k not in rec:
                    rec[k] = v
        elif rec.get("code"):
            # Truly new row added in the editor — default to "visible for no
            # machines" so it must be explicitly opted in via the Machine
            # Mapping tab.
            rec.setdefault("machines", [])
        merged.append(rec)
    return merged


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


def generate_full_matrix(cat_data, category_name=None):
    """Generate all possible SKU combinations for a category."""
    normalize_fields(cat_data)
    fields = cat_data["fields"]
    sep = cat_data.get("settings", {}).get("separator", DEFAULT_SEPARATOR)
    cat_suffix = get_category_suffix(category_name) if category_name else ""

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
        if sku and cat_suffix:
            sku += cat_suffix
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


def show_success(message):
    """Display success message."""
    st.success(message)


def show_error(message):
    """Display error message."""
    st.error(message)


def show_info(message):
    """Display info message."""
    st.info(message)


def inject_app_theme():
    """Apply global dark theme overrides for Streamlit chrome and custom widgets."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        html, body, [class*="css"], .stApp {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            color: #f3f4f6;
        }

        .stApp {
            background: #2a2e38;
        }

        header[data-testid="stHeader"] {
            background: rgba(42, 46, 56, 0.92);
        }

        [data-testid="stSidebar"] {
            background: #252933 !important;
            border-right: 1px solid #5c6475;
        }

        [data-testid="stSidebar"] .block-container {
            padding-top: 1.5rem;
        }

        [data-testid="stExpander"] {
            background: #353a46;
            border: 1px solid #5c6475;
            border-radius: 8px;
        }

        div[data-testid="stExpander"] details summary p {
            color: #f3f4f6 !important;
        }

        /* Clearer field boundaries */
        [data-testid="stSelectbox"] > div > div,
        [data-testid="stTextInput"] input,
        [data-testid="stTextArea"] textarea,
        [data-baseweb="input"],
        [data-baseweb="select"] > div {
            background-color: #353a46 !important;
            border-color: #6b7385 !important;
        }

        div[data-testid="stButton"] button[kind="secondary"],
        div[data-testid="stButton"] button[data-testid="baseButton-secondary"] {
            background-color: #3d4352 !important;
            border: 1px solid #7a8499 !important;
            color: #f3f4f6 !important;
        }

        div[data-testid="stCheckbox"] label p {
            color: #e8eaed !important;
        }

        hr {
            border-color: #5c6475 !important;
        }

        .block-container {
            padding-top: 2rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


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

    st.markdown("<p style='font-size:13px;font-weight:700;color:#c0c6d0;text-transform:uppercase;letter-spacing:1px;font-family:Inter,sans-serif;'>Navigation</p>", unsafe_allow_html=True)

    pages = [
        ("home", "SKU Generator"),
        ("history", "SKU History"),
        ("decoder", "SKU Decoder"),
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


def get_history_machine_key(entry, inventory):
    """Return (machine_code, machine_name) for grouping a history entry."""
    machine_code = entry.get("machine_code")
    machine_name = entry.get("machine_name")
    if machine_code:
        return machine_code, machine_name or machine_code

    cat = entry.get("category")
    config = entry.get("config") or {}
    if cat and cat in inventory:
        mf_name = get_machine_field(inventory[cat])
        machine_info = config.get(mf_name, {})
        if machine_info.get("code"):
            return machine_info["code"], machine_info.get("name") or machine_info["code"]

        sku = entry.get("sku")
        if sku:
            decode_results = decode_sku(sku, inventory)
            cat_match = next((r for r in decode_results if r.get("category") == cat), None)
            if cat_match:
                for part in cat_match.get("parts", []):
                    if part.get("field") == mf_name:
                        return part["code"], part.get("name", part["code"])

    return "—", "Unknown"


def now_ist():
    """Return the current time in Indian Standard Time (UTC+5:30) as a naive timestamp."""
    return (pd.Timestamp.now(tz="UTC") + pd.Timedelta(hours=5, minutes=30)).tz_localize(None)


def format_history_timestamp(ts):
    """Parse a stored timestamp and return (date_str dd/mm/yyyy, time_str hh:mm AM/PM)."""
    if not ts:
        return "", ""
    dt = None
    for fmt in ("%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = pd.to_datetime(ts, format=fmt)
            break
        except (ValueError, TypeError):
            continue
    if dt is None:
        try:
            dt = pd.to_datetime(ts)
        except (ValueError, TypeError):
            return str(ts), ""
    return dt.strftime("%d/%m/%Y"), dt.strftime("%I:%M %p")


def group_sku_history(history, inventory):
    """Group history entries by category, then by machine field."""
    grouped = {}
    for entry in history:
        cat = entry.get("category", "Other")
        mcode, mname = get_history_machine_key(entry, inventory)
        grouped.setdefault(cat, {}).setdefault((mcode, mname), []).append(entry)
    return grouped


def _config_field_text(config, *name_parts, exclude=()):
    """Return the display text for the first config field whose name matches all parts."""
    if not config:
        return ""
    lowered_parts = [p.lower() for p in name_parts]
    exclude_l = [e.lower() for e in exclude]
    for key, val in config.items():
        key_l = str(key).lower()
        if exclude_l and any(e in key_l for e in exclude_l):
            continue
        if all(p in key_l for p in lowered_parts):
            return (val.get("name") or val.get("code") or "").strip()
    return ""


def get_history_client_info(entry):
    """Return (client_name, client_abbr) from a history entry's config when present."""
    config = entry.get("config") or {}
    name = _config_field_text(config, "client", "name", exclude=("abbrev",))
    if not name:
        # Free-text client field without "name" in the label
        name = _config_field_text(config, "client", exclude=("abbrev",))

    abbr = ""
    for key, val in (config or {}).items():
        key_l = str(key).lower()
        if "abbrev" not in key_l:
            continue
        # Abbreviation is usually the code token (NB); name may repeat the client.
        abbr = (val.get("code") or val.get("name") or "").strip()
        if abbr:
            break
    return name, abbr


def is_custom_blast_machine(entry, inventory=None):
    """True when the entry is a Customized Blast Machine (CBM)."""
    mcode = (entry.get("machine_code") or "").upper()
    if mcode == "CBM":
        return True
    mname = (entry.get("machine_name") or "").lower()
    if "custom" in mname and "blast" in mname:
        return True
    if inventory is not None:
        code, name = get_history_machine_key(entry, inventory)
        if str(code).upper() == "CBM":
            return True
        name_l = str(name).lower()
        if "custom" in name_l and "blast" in name_l:
            return True
    return False


def get_history_identity(entry, inventory):
    """
    Human identity label for list rows.
    CBM: client name (+ abbr). Others: machine code — machine name.
    """
    client_name, client_abbr = get_history_client_info(entry)
    if is_custom_blast_machine(entry, inventory) and (client_name or client_abbr):
        if client_name and client_abbr:
            return f"{client_name} ({client_abbr})"
        return client_name or client_abbr

    mcode, mname = get_history_machine_key(entry, inventory)
    if mcode and mname and mcode != mname and mcode != "—":
        return f"{mcode} — {mname}"
    return mname or mcode or "Unknown"


def get_history_specs_summary(entry, max_parts=3):
    """Short scannable specs line from config (capacity, config, cert, etc.)."""
    config = entry.get("config") or {}
    if not config:
        desc = (entry.get("description") or entry.get("mapped_name") or "").strip()
        if len(desc) > 60:
            return desc[:57] + "…"
        return desc

    preferred = (
        "capacity",
        "configuration",
        "certification",
        "valve",
        "screen",
        "fittings",
    )
    skip = ("machine", "client", "version", "customization", "other")
    parts = []
    used_keys = set()

    for pref in preferred:
        for key, val in config.items():
            key_l = str(key).lower()
            if key in used_keys:
                continue
            if pref not in key_l:
                continue
            if any(s in key_l for s in ("client", "machine")):
                continue
            label = (val.get("name") or val.get("code") or "").strip()
            if label:
                parts.append(label)
                used_keys.add(key)
                break
        if len(parts) >= max_parts:
            break

    if len(parts) < max_parts:
        for key, val in config.items():
            if key in used_keys:
                continue
            key_l = str(key).lower()
            if any(s in key_l for s in skip):
                continue
            if val.get("is_text"):
                continue
            label = (val.get("name") or val.get("code") or "").strip()
            if label:
                parts.append(label)
                used_keys.add(key)
            if len(parts) >= max_parts:
                break

    return " · ".join(parts)


def history_entry_matches_query(entry, inventory, query):
    """True if query matches SKU, short code, client, machine, category, or description."""
    q = (query or "").strip().lower()
    if not q:
        return True

    client_name, client_abbr = get_history_client_info(entry)
    mcode, mname = get_history_machine_key(entry, inventory)
    haystacks = [
        entry.get("sku") or "",
        entry.get("short_code") or "",
        entry.get("category") or "",
        entry.get("description") or "",
        entry.get("mapped_name") or "",
        client_name,
        client_abbr,
        mcode,
        mname,
        get_history_identity(entry, inventory),
        get_history_specs_summary(entry),
    ]
    return any(q in str(h).lower() for h in haystacks if h)


def filter_sku_history(history, inventory, query="", filter_key="all"):
    """
    Filter history for the searchable list view.
    filter_key: 'all' | 'cbm' | category name
    """
    results = []
    for entry in history:
        cat = entry.get("category") or "Other"
        if filter_key == "cbm":
            if not is_custom_blast_machine(entry, inventory):
                continue
        elif filter_key not in ("", "all", None):
            if cat != filter_key:
                continue
        if not history_entry_matches_query(entry, inventory, query):
            continue
        results.append(entry)
    return results


def group_history_for_display(entries, inventory, group_by="recent"):
    """
    Return ordered list of (section_title, [entries]) for the history UI.
    group_by: 'recent' | 'client' | 'machine'
    """
    if not entries:
        return []

    if group_by == "recent":
        return [("Recent", list(entries))]

    buckets = {}
    order = []

    for entry in entries:
        if group_by == "client":
            client_name, client_abbr = get_history_client_info(entry)
            if is_custom_blast_machine(entry, inventory) and (client_name or client_abbr):
                if client_name and client_abbr:
                    key = f"{client_name} ({client_abbr})"
                else:
                    key = client_name or client_abbr
            elif is_custom_blast_machine(entry, inventory):
                key = "Custom (no client)"
            else:
                mcode, mname = get_history_machine_key(entry, inventory)
                key = f"{mcode} — {mname}" if mcode != "—" else (mname or "Other")
        else:  # machine
            mcode, mname = get_history_machine_key(entry, inventory)
            key = f"{mcode} — {mname}" if mcode and mcode != "—" else (mname or "Unknown")

        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(entry)

    if group_by == "client":
        def sort_key(title):
            sample = buckets[title][0] if buckets[title] else {}
            if is_custom_blast_machine(sample, inventory):
                if title == "Custom (no client)":
                    return (1, title.lower())
                return (0, title.lower())
            return (2, title.lower())

        order = sorted(order, key=sort_key)
    else:
        order = sorted(order, key=lambda t: (t.startswith("—"), t.lower()))

    return [(title, buckets[title]) for title in order]


def compute_config_signature(category, sel, ordered_field_names, chosen):
    """
    Build a canonical, stable signature string for a configuration so that
    identical configurations always resolve to the same short code.

    Includes every selected field (dropdown codes and free-text values) in
    field order, plus the sorted set of extra codes. Text values are included
    because two otherwise-identical machines with different client/version text
    are genuinely different products and deserve distinct short codes.
    """
    parts = [category or ""]
    for k in ordered_field_names:
        s = sel.get(k)
        if not s:
            continue
        if s.get("is_text"):
            val = (s.get("name") or "").strip()
            if val:
                parts.append(f"{k}=T:{val}")
        elif s.get("code"):
            parts.append(f"{k}={s['code']}")
    extra_codes = sorted([c.get("code", "") for c in (chosen or []) if c.get("code")])
    if extra_codes:
        parts.append("X=" + ",".join(extra_codes))
    return "|".join(parts)


def get_short_code_prefix(category, sel, machine_field_name):
    """
    Determine the readable prefix for a short code.

    Uses the selected machine option's code (e.g. 'BL', 'CBM', 'AR', 'HP').
    Falls back to the category's initials when no machine code is available.
    """
    s = sel.get(machine_field_name) if machine_field_name else None
    if s and s.get("code"):
        return str(s["code"]).upper()
    letters = "".join(ch for ch in (category or "") if ch.isalnum())
    return (letters[:3] or "SKU").upper()


def format_short_code(prefix, seq):
    """
    Build a short code like BL-003.

    Sequence is zero-padded to at least 3 digits; values >= 1000 keep their
    natural width (BL-1000) so we can grow past 999 without a format break.
    """
    return f"{str(prefix).upper()}-{int(seq):03d}"


def lookup_short_code(signature, short_codes):
    """Return the existing short code for a signature, or None. Read-only."""
    if not signature or not short_codes:
        return None
    rec = short_codes.get(signature)
    return rec.get("code") if rec else None


def allocate_short_code(signature, prefix, meta):
    """
    Return the short code for `signature`, allocating a new one if needed.

    Idempotent: an already-registered signature returns its existing code and
    does not consume a new number. New signatures get `PREFIX-NNN` (3-digit
    padded sequence). Persists the registry to disk and returns
    (code, short_codes, code_counters).
    """
    from storage import GithubStorage

    storage = GithubStorage()
    data = storage.load()
    short_codes = data.get("short_codes", {})
    counters = data.get("code_counters", {})

    existing = short_codes.get(signature)
    if existing and existing.get("code"):
        return existing["code"], short_codes, counters

    seq = int(counters.get(prefix, 0)) + 1
    counters[prefix] = seq
    code = format_short_code(prefix, seq)

    record = {
        "code": code,
        "prefix": prefix,
        "seq": seq,
        "signature": signature,
        "created_at": now_ist().strftime("%d/%m/%Y %H:%M"),
    }
    record.update(meta or {})
    record["code"] = code  # meta must never override the allocated code
    short_codes[signature] = record

    storage.save_registry(short_codes, counters)
    return code, short_codes, counters


def add_to_sku_history(
    sku,
    description,
    category,
    *,
    config=None,
    extras=None,
    machine_code=None,
    machine_name=None,
    mapped_name=None,
    mapped_desc=None,
    breakdown_items=None,
    signature=None,
    prefix=None,
):
    """Add a SKU to history (avoid duplicates, limit size). Persists to disk.

    When `signature` and `prefix` are provided, also allocates (or reuses) a
    short code for the configuration and stores it on the history entry.
    """
    if not sku:
        return

    from storage import GithubStorage

    storage = GithubStorage()

    short_code = None
    if signature and prefix:
        short_code, short_codes, counters = allocate_short_code(
            signature,
            prefix,
            {
                "category": category,
                "sku": sku,
                "config": config or {},
                "extras": extras or [],
                "machine_code": machine_code,
                "machine_name": machine_name,
                "mapped_name": mapped_name,
                "mapped_desc": mapped_desc if mapped_desc is not None else description,
                "breakdown_items": breakdown_items or [],
            },
        )
        if "sku_data" in st.session_state:
            st.session_state["sku_data"]["short_codes"] = short_codes
            st.session_state["sku_data"]["code_counters"] = counters

    data = storage.load()
    history = data.get("sku_history", [])

    entry = {
        "sku": sku,
        "short_code": short_code,
        "description": description,
        "category": category,
        "timestamp": now_ist().strftime("%d/%m/%Y %H:%M"),
        "config": config or {},
        "extras": extras or [],
        "machine_code": machine_code,
        "machine_name": machine_name,
        "mapped_name": mapped_name,
        "breakdown_items": breakdown_items or [],
    }

    history = [h for h in history if h["sku"] != sku]
    history.insert(0, entry)

    if len(history) > MAX_SKU_HISTORY:
        history = history[:MAX_SKU_HISTORY]

    storage.save_history(history)
    st.session_state["sku_history"] = history
    if "sku_data" in st.session_state:
        st.session_state["sku_data"]["sku_history"] = history


def _strip_sep(s, sep):
    """Strip a single leading separator if present (no-op when sep is empty)."""
    if sep and s.startswith(sep):
        return s[len(sep):]
    return s


def _split_base_and_extras(sku_code, sep, extras):
    """
    Split an SKU into (base, extras_str) around the 'X' marker.
    The encoder inserts sep+'X' between the base and concatenated extras when both exist.

    Only splits if the category has extras configured AND the tail after the marker
    actually parses as a sequence of extras codes. Otherwise the whole SKU is the base,
    which avoids collisions with fields whose options include 'X' as a code.
    """
    extras_pool = _valid_options(extras)
    if not extras_pool:
        return sku_code, ""

    marker = (sep + "X") if sep else "X"
    idx = sku_code.rfind(marker)
    if idx == -1:
        return sku_code, ""

    tail = sku_code[idx + len(marker):]
    if not tail:
        return sku_code, ""

    # Verify the tail is fully consumable as a chain of extras codes; if not,
    # the 'X' is probably part of a field code, not an extras marker.
    t = tail
    while t:
        opt, code_len = _match_longest_prefix(t, extras_pool)
        if opt is None:
            return sku_code, ""
        t = t[code_len:]
        t = _strip_sep(t, sep)

    return sku_code[:idx], tail


def _valid_options(opts):
    """Filter out null/empty and text-type options, leaving only concrete matchable codes."""
    out = []
    for o in opts or []:
        if o.get("type") == "text":
            continue
        code = o.get("code")
        if not code:
            continue
        out.append(o)
    return out


def _match_longest_prefix(remaining, opts):
    """Return (opt, code_len) for the longest-code option that is a prefix of `remaining`, else (None, 0)."""
    best = None
    best_len = 0
    for opt in opts:
        code = opt.get("code", "")
        if code and remaining.startswith(code) and len(code) > best_len:
            best = opt
            best_len = len(code)
    return best, best_len


def _decode_for_category(sku_code, cat_name, cat_data):
    """
    Attempt to decode `sku_code` against a single category.
    Returns a dict with category, parts, extras, remaining, score — or None on no match.
    Score = (machine_matched, concrete_parts_matched, -len(leftover)); higher is better.

    Hard rules:
    - If the category's machine-selector field has non-text options, at least one of
      those options must be a prefix of the SKU. Otherwise the category is rejected.
    - A text field only consumes characters when a following field's code is found
      downstream in the remaining string. Otherwise it contributes nothing.
    - If the category has a fixed SKU suffix (see CATEGORY_SUFFIXES), require the
      SKU to end with it and strip it before parsing.
    """
    normalize_fields(cat_data)
    fields = cat_data.get("fields", {})
    extras = cat_data.get("extras", [])
    sep = cat_data.get("settings", {}).get("separator", DEFAULT_SEPARATOR)
    mf_name = get_machine_field(cat_data)

    cat_suffix = get_category_suffix(cat_name)
    suffix_part = None
    if cat_suffix:
        if not sku_code.endswith(cat_suffix):
            return None
        sku_code = sku_code[: -len(cat_suffix)]
        sku_code = _strip_sep(sku_code[::-1], sep)[::-1] if sep else sku_code
        suffix_part = {
            "field": "Manufacturer",
            "code": cat_suffix,
            "name": "JollyFlex" if cat_suffix == "JF" else cat_suffix,
        }

    # Hard-require the machine field if it has concrete options.
    mf_opts = _valid_options(fields.get(mf_name, {}).get("options", [])) if mf_name in fields else []
    if mf_opts:
        mf_hit, _ = _match_longest_prefix(sku_code, mf_opts)
        if mf_hit is None:
            return None

    base, extras_str = _split_base_and_extras(sku_code, sep, extras)

    remaining = base
    matched_parts = []
    concrete_matches = 0
    machine_matched = False
    selected_machine_code = None
    field_order = ordered_fields(fields)

    def field_visible(fname):
        field_machines = fields[fname].get("machines", [])
        if not field_machines or not selected_machine_code:
            return True
        return selected_machine_code in field_machines

    i = 0
    while i < len(field_order):
        fname = field_order[i]
        if not field_visible(fname):
            i += 1
            continue

        raw_opts = fields[fname].get("options", [])
        is_text_field = bool(raw_opts) and raw_opts[0].get("type") == "text"

        if is_text_field:
            # Read text until we can match the next visible field's option.
            # If no downstream field can match anywhere in `remaining`, the text
            # field contributes nothing — it does NOT swallow the whole SKU.
            next_opts = []
            for j in range(i + 1, len(field_order)):
                nxt = field_order[j]
                if not field_visible(nxt):
                    continue
                no = _valid_options(fields[nxt].get("options", []))
                if selected_machine_code:
                    no = filter_for_machine(no, selected_machine_code)
                if no:
                    next_opts = no
                    break

            if next_opts and remaining:
                best_idx = -1
                for k in range(len(remaining) + 1):
                    slice_ = remaining[k:]
                    if not slice_:
                        continue
                    matched_opt, _ = _match_longest_prefix(slice_, next_opts)
                    if matched_opt is not None:
                        best_idx = k
                        break
                if best_idx > 0:
                    matched_parts.append({
                        "field": fname,
                        "code": remaining[:best_idx],
                        "name": remaining[:best_idx],
                    })
                    remaining = _strip_sep(remaining[best_idx:], sep)
            i += 1
            continue

        opts = _valid_options(raw_opts)
        if selected_machine_code:
            opts = filter_for_machine(opts, selected_machine_code)

        if not opts:
            i += 1
            continue

        opt, code_len = _match_longest_prefix(remaining, opts)
        if opt is None:
            i += 1
            continue

        matched_parts.append({
            "field": fname,
            "code": opt["code"],
            "name": opt.get("name", ""),
        })
        concrete_matches += 1
        remaining = remaining[code_len:]
        remaining = _strip_sep(remaining, sep)

        if fname == mf_name:
            selected_machine_code = opt["code"]
            machine_matched = True

        i += 1

    # Decode extras by repeatedly consuming the longest matching extra code.
    matched_extras = []
    extras_pool = _valid_options(extras)
    if selected_machine_code:
        extras_pool = filter_for_machine(extras_pool, selected_machine_code)
    extras_remaining = extras_str
    while extras_remaining:
        opt, code_len = _match_longest_prefix(extras_remaining, extras_pool)
        if opt is None:
            break
        matched_extras.append({
            "field": "Extra",
            "code": opt["code"],
            "name": opt.get("name", ""),
        })
        extras_remaining = extras_remaining[code_len:]
        extras_remaining = _strip_sep(extras_remaining, sep)

    leftover = remaining
    if extras_remaining:
        if leftover and sep:
            leftover += sep
        leftover += extras_remaining
    if sep:
        leftover = leftover.strip(sep)

    # A category needs either a machine match or at least 2 concrete field matches
    # to be a credible candidate. This kills spurious single-letter collisions.
    if not machine_matched and concrete_matches < 2:
        return None

    if suffix_part is not None:
        matched_parts.append(suffix_part)
        concrete_matches += 1

    score = (1 if machine_matched else 0, concrete_matches, -len(leftover))

    return {
        "category": cat_name,
        "parts": matched_parts,
        "extras": matched_extras,
        "remaining": leftover,
        "score": score,
    }


def decode_sku(sku_code, inventory):
    """
    Decode a SKU code and return a ranked list of category matches.

    Uses longest-prefix matching per field, respects machine-based visibility,
    handles text fields, and splits base/extras on the 'X' marker.
    """
    if not sku_code:
        return []

    candidates = []
    for cat_name, cat_data in inventory.items():
        result = _decode_for_category(sku_code, cat_name, cat_data)
        if result is not None:
            candidates.append(result)

    candidates.sort(key=lambda r: r["score"], reverse=True)

    for r in candidates:
        r.pop("score", None)

    return candidates


def _find_option_by_code(options, code):
    """Return the first option whose code matches `code`, or None."""
    code_str = str(code)
    for opt in options or []:
        if str(opt.get("code", "")) == code_str:
            return opt
    return None


def build_selection_from_decode(decode_result, cat_data):
    """
    Rebuild sel/chosen structures from a decode result so that
    generate_mapped_name_and_description can produce item name and description.
    """
    normalize_fields(cat_data)
    fields = cat_data["fields"]
    extras_list = cat_data.get("extras", [])
    field_order = ordered_fields(fields)

    sel = {}
    fittings_selected = False

    for part in decode_result.get("parts", []):
        fname = part["field"]
        if fname == "Manufacturer":
            continue

        code = part["code"]
        if fname not in fields:
            continue

        opts = fields[fname].get("options", [])
        is_text = opts and opts[0].get("type") == "text"

        if is_text:
            name = part.get("name", code)
            sel[fname] = {
                "code": code,
                "name": name,
                "tally_name": code,
                "description": name,
            }
        else:
            opt = _find_option_by_code(opts, code)
            if opt:
                sel[fname] = {
                    "code": opt["code"],
                    "name": opt.get("name", ""),
                    "tally_name": opt.get("tally_name", ""),
                    "description": opt.get("description", ""),
                }
            else:
                sel[fname] = {
                    "code": code,
                    "name": part.get("name", ""),
                    "tally_name": "",
                    "description": "",
                }

        if fname.lower() == "fittings" and code and str(part.get("name", "")).lower() != "none":
            fittings_selected = True

    chosen = []
    for extra in decode_result.get("extras", []):
        opt = _find_option_by_code(extras_list, extra["code"])
        if opt:
            chosen.append({
                "code": opt["code"],
                "name": opt.get("name", ""),
                "tally_name": opt.get("tally_name", ""),
                "description": opt.get("description", ""),
            })
        else:
            chosen.append({
                "code": extra["code"],
                "name": extra.get("name", ""),
                "tally_name": "",
                "description": "",
            })

    return sel, field_order, chosen, fittings_selected
