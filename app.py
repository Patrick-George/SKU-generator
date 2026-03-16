import streamlit as st
import pandas as pd
import json
import itertools
import requests
import base64
import qrcode
import os
import anthropic
from io import BytesIO
from PIL import Image

# ==================================================
# CONSTANTS
# ==================================================
COPY_BOX_HEIGHT = 160
DEFAULT_SEPARATOR = "-"
DEFAULT_EXTRAS_MODE = "Single"
EXTRAS_PER_PAGE = 8
MAX_SKU_HISTORY = 15  # Maximum number of SKUs to keep in history

# ==================================================
# SETUP
# ==================================================
st.set_page_config(
    page_title="Blastline SKU Configurator", 
    layout="wide",
    initial_sidebar_state="collapsed"  # Start with sidebar collapsed
)

# ==================================================
# GITHUB STORAGE
# ==================================================
# STORAGE (Disk-based for Render)
# ==================================================
DATA_FILE = "/data/sku_data.json"

class GithubStorage:
    """
    Disk-backed persistent storage.
    Class name preserved so the rest of the application remains unchanged.
    """

    def __init__(self):
        self.path = DATA_FILE
        self.can_connect = True  # Always true for disk storage

    def load(self):
        """
        Load configuration data from disk.
        If no data file exists yet, seed from bundled data.json (if present).
        """
        # If primary data file exists, load it
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {"inventory": {}}

        # Seed from repo data.json on first run (e.g. fresh Render deploy)
        seed_path = os.path.join(os.path.dirname(__file__), "data.json")
        if os.path.exists(seed_path):
            try:
                with open(seed_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Persist seeded data to primary storage path
                os.makedirs(os.path.dirname(self.path), exist_ok=True)
                with open(self.path, "w", encoding="utf-8") as out_f:
                    json.dump(data, out_f, indent=2)
                return data
            except Exception:
                return {"inventory": {}}

        # Fallback if nothing available
        return {"inventory": {}}

    def save(self, data):
        """Save configuration data to disk."""
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception:
            return False

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


def generate_product_name_and_description(breakdown_items, category_name, sku, extras_items=None):
    """Generate both a tally item name and item description from SKU breakdown using Claude."""
    if not ANTHROPIC_API_KEY:
        return None, None, "ANTHROPIC_API_KEY environment variable not set."

    parts = "\n".join([f"- {item['name']} (code: {item['code']})" for item in breakdown_items])
    extras_str = ""
    if extras_items:
        extras_str = "\nExtras selected:\n" + "\n".join(
            [f"- {item['name']} (code: {item['code']})" for item in extras_items]
        )

    machine_code = breakdown_items[0]["code"] if breakdown_items else ""
    machine_name = breakdown_items[0]["name"] if breakdown_items else category_name

    prompt = (
        f"You are generating item names for Blastline India's inventory/Tally system.\n\n"
        f"Product Category: {category_name}\n"
        f"Machine: {machine_code} - {machine_name}\n"
        f"SKU: {sku}\n"
        f"Specifications:\n{parts}{extras_str}\n\n"
        f"Generate TWO things based on these rules:\n\n"
        f"1. ITEM TALLY NAME: A short space-separated abbreviated name for Tally/inventory.\n"
        f"   Rules:\n"
        f"   - Start with the machine code exactly as given: {machine_code}\n"
        f"   - Then capacity + config code (e.g. 200A for 200ltr Automatic, 20M for 20ltr Manual)\n"
        f"   - Then certification abbreviation if any (e.g. T for Third-party Tested, ST for Standard)\n"
        f"   - Then valve abbreviation (e.g. SV=Sand Valve, MV=Micro Valve, GV=Grit Valve, TV=Thompson Valve, BV=Ball Valve, MS=Mini Sand Valve, MG=Mini Grit Valve)\n"
        f"   - Then inlet/outlet combo number if applicable\n"
        f"   - Separate each spec with a SPACE (not commas)\n"
        f"   - If extras selected, add ' + ' then extras codes space-separated\n"
        f"   - If screen/cover selected, add ' + Fittings'\n"
        f"   - Keep it SHORT - all abbreviations, no commas\n"
        f"   Example: {machine_code} 200A T SV 1 + MS PG RV + Fittings\n\n"
        f"2. ITEM DESCRIPTION: A single-line expanded but still concise description.\n"
        f"   Rules:\n"
        f"   - Start with full machine name (e.g. '{machine_name}')\n"
        f"   - Then capacity in litres + config name (e.g. '200ltr Automatic')\n"
        f"   - Certification in parentheses if any (e.g. '(Third Party Tested)')\n"
        f"   - Use 'w/' for 'with' (e.g. 'w/ Flat Sand Valve')\n"
        f"   - Screen/Cover status (e.g. 'w/ Screen + Cover' or 'w/ No Screen + No Cover')\n"
        f"   - If extras, add '+ Extras: ' then codes comma-space-separated (e.g. '+ Extras: MS, PG, RV')\n"
        f"   - Add '+ Fittings' at end if screen/cover present\n"
        f"   - Keep it to ONE line, use abbreviations where natural\n"
        f"   Example: {machine_name} 200ltr Automatic (Third Party Tested) w/ Flat Sand Valve w/ Screen + Cover + Extras: MS, PG, RV + Fittings\n\n"
        f"Output EXACTLY in this format (no extra text, no markdown):\n"
        f"NAME: <the tally name>\n"
        f"DESCRIPTION: <the item description>"
    )

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
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
def get_option_label(o):
    """Format option for display in selectbox."""
    return f"{o['code']} : {o['name']}"

def normalize_fields(cat):
    """
    Normalize category fields structure to ensure consistent format.
    Converts legacy field formats to new structure with 'order' and 'options'.
    
    Args:
        cat: Category dictionary (modified in place)
    """
    fields = {}
    for i, (k, v) in enumerate(cat.get("fields", {}).items(), start=1):
        if isinstance(v, dict):
            fields[k] = v
        else:
            fields[k] = {"order": i, "options": v}
    cat["fields"] = fields

def ordered_fields(fields):
    """
    Return field names sorted by their order value.
    
    Args:
        fields: Dictionary of field configurations
        
    Returns:
        List of field names in order
    """
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
    """
    Convert options list to normalized DataFrame for editing.
    
    Args:
        data: List of option dictionaries
        
    Returns:
        DataFrame with code, name, order columns
    """
    df = pd.DataFrame(data or [], columns=["code", "name", "order"])
    if df.empty:
        df = pd.DataFrame(columns=["code", "name", "order"])
    if df["order"].isnull().all():
        df["order"] = range(1, len(df) + 1)
    return df[["code", "name", "order"]]

def normalize_extras_df(data):
    """
    Convert extras list to normalized DataFrame for editing.
    
    Args:
        data: List of extra dictionaries
        
    Returns:
        DataFrame with code, name, and order columns
    """
    df = pd.DataFrame(data or [], columns=["code", "name", "order"])
    if df.empty:
        df = pd.DataFrame(columns=["code", "name", "order"])
    if "order" not in df.columns or df["order"].isnull().all():
        df["order"] = range(1, len(df) + 1)
    return df[["code", "name", "order"]]

def generate_full_matrix(cat_data):
    """
    Generate all possible SKU combinations for a category.
    
    Args:
        cat_data: Category configuration dictionary
        
    Returns:
        pandas DataFrame with all SKU combinations
    """
    normalize_fields(cat_data)
    fields = cat_data["fields"]
    sep = cat_data.get("settings", {}).get("separator", DEFAULT_SEPARATOR)
    
    # Get all field combinations (excluding text input fields)
    field_combos = []
    field_names = []
    
    for f in ordered_fields(fields):
        opts = fields[f]["options"]
        is_text = opts and opts[0].get("type") == "text"
        if not is_text and opts:
            field_names.append(f)
            field_combos.append([o["code"] for o in opts])
    
    # Generate all combinations
    if not field_combos:
        return pd.DataFrame(columns=["SKU"] + field_names)
    
    combinations = list(itertools.product(*field_combos))
    
    # Create DataFrame
    rows = []
    for combo in combinations:
        sku = sep.join(combo)
        row = {"SKU": sku}
        for i, fname in enumerate(field_names):
            row[fname] = combo[i]
        rows.append(row)
    
    return pd.DataFrame(rows)

def big_copy_box(text):
    """
    Generate HTML for large, clickable SKU display with copy functionality.
    Features responsive font sizing for mobile devices.
    
    Args:
        text: The SKU text to display and copy
        
    Returns:
        HTML string with embedded JavaScript and responsive CSS
    """
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
            /* Dynamic font sizing based on viewport and text length */
            font-size: clamp(16px, 5vw, 44px);
        }}
        .sku-msg {{
            margin-top: 8px;
            color: #aaa;
            font-size: 14px;
        }}
        /* Adjust for very long SKUs */
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
    """
    Generate a QR code image for the given text.
    
    Args:
        text: The text to encode in the QR code
        size: Size of the QR code image in pixels
        
    Returns:
        BytesIO object containing the PNG image
    """
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
    """
    Generate a QR code and return as base64 string for HTML embedding.
    
    Args:
        text: The text to encode in the QR code
        
    Returns:
        Base64 encoded string of the QR code PNG
    """
    buffer = generate_qr_code(text)
    return base64.b64encode(buffer.getvalue()).decode()


def generate_qr_svg(text):
    """
    Generate a QR code as SVG string.
    
    Args:
        text: The text to encode in the QR code
        
    Returns:
        SVG string of the QR code
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(text)
    qr.make(fit=True)
    
    # Get the QR code matrix
    matrix = qr.get_matrix()
    size = len(matrix)
    scale = 10
    
    # Build SVG
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
# INIT
# ==================================================
if "sku_data" not in st.session_state:
    gh = GithubStorage()
    st.session_state["sku_data"] = gh.load() or {"inventory": {}}

if "page" not in st.session_state:
    st.session_state["page"] = "home"

if "extras_page" not in st.session_state:
    st.session_state["extras_page"] = 0

if "confirm_delete_cat" not in st.session_state:
    st.session_state["confirm_delete_cat"] = None

if "confirm_delete_field" not in st.session_state:
    st.session_state["confirm_delete_field"] = None

if "sku_history" not in st.session_state:
    st.session_state["sku_history"] = []

def go(p):
    """Navigate to a different page."""
    st.session_state["page"] = p
    st.rerun()

def render_sidebar_nav(current_page="home"):
    """Render the sidebar navigation with consistent styling."""
    
    # Add JavaScript to collapse sidebar on mobile after click
    st.markdown("""
        <style>
        /* Make sidebar collapse smoother on mobile */
        @media (max-width: 768px) {
            [data-testid="stSidebar"][aria-expanded="true"] {
                min-width: 100%;
            }
        }
        </style>
        <script>
        // Function to collapse sidebar
        function collapseSidebar() {
            const sidebar = window.parent.document.querySelector('[data-testid="stSidebarCollapsedControl"]');
            if (sidebar) {
                sidebar.click();
            }
        }
        </script>
    """, unsafe_allow_html=True)
    
    st.markdown("### 🧭 Navigation")
    
    pages = [
        ("home", "🏠 SKU Generator"),
        ("history", "📋 SKU History"),
        ("decoder", "🔍 SKU Decoder"),
        ("scanner", "📱 QR Scanner"),
    ]
    
    for page_id, page_name in pages:
        btn_type = "primary" if current_page == page_id else "secondary"
        if st.button(page_name, use_container_width=True, type=btn_type, key=f"nav_{page_id}_{current_page}"):
            if page_id != current_page:
                go(page_id)  # Use go() to trigger full rerun
    
    st.markdown("---")
    
    if st.button("⚙️ Settings", use_container_width=True, key=f"nav_settings_{current_page}"):
        go("login")

def add_to_sku_history(sku, description, category):
    """Add a SKU to history (avoid duplicates, limit size)."""
    if not sku:
        return
    
    history = st.session_state.get("sku_history", [])
    
    # Create history entry
    entry = {
        "sku": sku,
        "description": description,
        "category": category,
        "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
    }
    
    # Remove duplicate if exists
    history = [h for h in history if h["sku"] != sku]
    
    # Add to beginning
    history.insert(0, entry)
    
    # Limit size
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
        
        # Try to match this SKU against this category
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
                    # Remove separator if present
                    if remaining.startswith(sep):
                        remaining = remaining[len(sep):]
                    field_matched = True
                    break
            
            if not field_matched and opts and not (opts[0].get("type") == "text"):
                matched = False
                break
        
        # Check for extras
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

# ==================================================
# HOME
# ==================================================
def home():
    """Main SKU configuration page."""
    
    with st.sidebar:
        render_sidebar_nav("home")

    # Header styles
    st.markdown("""
        <style>
        .subheading {
            font-size: 18px;
            font-weight: 600;
            color: #333;
            margin-bottom: 12px;
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        }
        </style>
    """, unsafe_allow_html=True)

    # Centered Header
    st.markdown("<h2 style='text-align: center; margin-bottom: 5px; font-family: -apple-system, BlinkMacSystemFont, sans-serif;'>Blastline SKU Configurator</h2>", unsafe_allow_html=True)

    inv = st.session_state["sku_data"]["inventory"]
    if not inv:
        st.warning("No categories available. Please contact admin to set up product categories.")
        return

    # Centered Product Category dropdown - compact width
    cat_spacer1, cat_col, cat_spacer2 = st.columns([2, 1.5, 2])
    with cat_col:
        cat = st.selectbox("Product Category", list(inv.keys()), label_visibility="collapsed")
    
    cat_data = inv[cat]
    normalize_fields(cat_data)

    fields = cat_data["fields"]
    extras = cat_data.get("extras", [])
    sep = cat_data.get("settings", {}).get("separator", DEFAULT_SEPARATOR)
    extras_mode = cat_data.get("settings", {}).get("extras_mode", DEFAULT_EXTRAS_MODE)

    sel = {}
    chosen = []

    # Determine machine-selector field and get selected machine code
    mf_name = get_machine_field(cat_data)
    selected_machine_code = None
    
    st.markdown("<div style='margin-top: 30px;'></div>", unsafe_allow_html=True)

    # Main two-column layout (no divider column - use CSS border instead)
    left_col, right_col = st.columns([1, 1], gap="large")

    with left_col:
        # Configuration Section - larger subheading
        st.markdown("<p class='subheading'>Configuration</p>", unsafe_allow_html=True)
        
        # Create a narrower container for dropdowns
        config_inner, config_spacer = st.columns([3, 1])
        with config_inner:
            # Render machine-selector field first (always visible)
            if mf_name in fields:
                mf_opts = fields[mf_name]["options"]
                if mf_opts and not mf_opts[0].get("type") == "text":
                    st.markdown(f"<p style='font-size: 12px; color: #666; margin-bottom: 2px;'>{mf_name}</p>", unsafe_allow_html=True)
                    mf_selection = st.selectbox(
                        mf_name,
                        mf_opts,
                        format_func=lambda x: f"{x['code']} - {x['name']}",
                        help=f"Select {mf_name}",
                        label_visibility="collapsed"
                    )
                    sel[mf_name] = {"code": mf_selection["code"], "name": mf_selection["name"]}
                    selected_machine_code = mf_selection["code"]

            # Render remaining fields, filtered by selected machine
            for f in ordered_fields(fields):
                if f == mf_name:
                    continue
                field_machines = fields[f].get("machines", [])
                if field_machines and selected_machine_code and selected_machine_code not in field_machines:
                    continue

                opts = fields[f]["options"]
                is_text = opts and opts[0].get("type") == "text"
                if is_text:
                    text_val = st.text_input(f, help=f"Enter {f}", placeholder=f"Enter {f}", label_visibility="collapsed")
                    sel[f] = {"code": text_val, "name": text_val}
                else:
                    filtered_opts = filter_for_machine(opts, selected_machine_code) if selected_machine_code else opts
                    if filtered_opts:
                        st.markdown(f"<p style='font-size: 12px; color: #666; margin-bottom: 2px;'>{f}</p>", unsafe_allow_html=True)
                        o = st.selectbox(
                            f, 
                            filtered_opts, 
                            format_func=lambda x: f"{x['code']} - {x['name']}", 
                            help=f"Select {f}",
                            label_visibility="collapsed"
                        )
                        sel[f] = {"code": o["code"], "name": o["name"]}
        
        st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
        
        # Extras Section - larger subheading
        st.markdown("<p class='subheading'>Extras</p>", unsafe_allow_html=True)
        
        # Filter extras by selected machine
        visible_extras = filter_for_machine(extras, selected_machine_code) if selected_machine_code else extras
        
        if visible_extras:
            sorted_extras = sorted(visible_extras, key=lambda x: x.get("order", 999))
            
            if extras_mode == "Single":
                extra_options = ["None"] + [e["name"] for e in sorted_extras]
                
                selected_name = st.radio(
                    "Select extra:",
                    options=extra_options,
                    horizontal=True,
                    key="single_extra_radio",
                    label_visibility="collapsed"
                )
                
                if selected_name != "None":
                    for e in sorted_extras:
                        if e["name"] == selected_name and e.get("code"):
                            chosen.append({"code": e["code"], "name": e["name"]})
                            break
            else:
                num_cols = 5
                total_extras = len(sorted_extras)
                num_rows = (total_extras + num_cols - 1) // num_cols
                
                for row in range(num_rows):
                    cols = st.columns(num_cols)
                    for col_idx in range(num_cols):
                        extra_idx = row * num_cols + col_idx
                        if extra_idx < total_extras:
                            e = sorted_extras[extra_idx]
                            with cols[col_idx]:
                                if st.checkbox(e["name"], key=f"extra_{extra_idx}"):
                                    if e.get("code"):
                                        chosen.append({"code": e["code"], "name": e["name"]})
        else:
            if extras and selected_machine_code:
                st.info("No extras available for this machine")
            else:
                st.info("No extras configured")

    # Calculate SKU
    base = sep.join([sel[k]["code"] for k in ordered_fields(fields) if sel.get(k) and sel[k]["code"]])
    extras_codes = "".join([c["code"] for c in chosen])
    sku = base + (sep if base and extras_codes else "") + extras_codes
    
    # Build breakdown items (base fields only) and extras items separately
    breakdown_items = []
    for k in ordered_fields(fields):
        if sel.get(k) and sel[k].get("code") and sel[k].get("name"):
            breakdown_items.append({"code": str(sel[k]["code"]), "name": str(sel[k]["name"])})
    extras_items = []
    for c in chosen:
        if c.get("code") and c.get("name"):
            extras_items.append({"code": str(c["code"]), "name": str(c["name"])})
    all_breakdown_items = breakdown_items + extras_items

    with right_col:
        with st.container():
            # 1) Generated SKU
            st.markdown("<p class='subheading'>Generated SKU</p>", unsafe_allow_html=True)
            
            if sku:
                sku_html = f"""
                <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined" rel="stylesheet" />
                <style>
                    * {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
                    html, body {{ margin: 0; padding: 0; overflow: visible; }}
                    @keyframes pulse {{
                        0% {{ box-shadow: 0 0 0 0 rgba(76, 175, 80, 0.7); }}
                        70% {{ box-shadow: 0 0 0 8px rgba(76, 175, 80, 0); }}
                        100% {{ box-shadow: 0 0 0 0 rgba(76, 175, 80, 0); }}
                    }}
                    @keyframes fadeOut {{
                        0% {{ opacity: 1; }}
                        70% {{ opacity: 1; }}
                        100% {{ opacity: 0; }}
                    }}
                    .pulse-dot {{
                        width: 10px;
                        height: 10px;
                        background: #4CAF50;
                        border-radius: 50%;
                        animation: pulse 1s ease-out 3, fadeOut 3s ease-out forwards;
                        position: absolute;
                        top: 8px;
                        right: 8px;
                    }}
                </style>
                <div id="sku-container" onclick="copySKU()" style="
                    background: #e8f4fd;
                    border: 1px solid #c5dff0;
                    border-radius: 12px;
                    padding: 16px 20px;
                    display: inline-flex;
                    align-items: center;
                    gap: 20px;
                    cursor: pointer;
                    margin: 8px;
                    box-sizing: border-box;
                    min-width: 200px;
                    max-width: 100%;
                    position: relative;
                ">
                    <div class="pulse-dot"></div>
                    <span style="
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        font-size: 17px;
                        font-weight: 600;
                        color: #1a73e8;
                        word-break: break-all;
                    ">{sku}</span>
                    <div id="copy-area" style="text-align: center; color: #1a73e8; flex-shrink: 0;">
                        <span id="copy-icon" class="material-symbols-outlined" style="font-size: 20px;">content_copy</span>
                        <p id="copy-text" style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 9px; color: #5a9bd5; margin: 2px 0 0 0;">Click to Copy</p>
                    </div>
                </div>
                <script>
                function copySKU() {{
                    navigator.clipboard.writeText("{sku}").then(function() {{
                        document.getElementById('copy-icon').innerText = 'check_circle';
                        document.getElementById('copy-icon').style.color = '#34a853';
                        document.getElementById('copy-text').innerText = 'Copied!';
                        document.getElementById('copy-text').style.color = '#34a853';
                        setTimeout(function() {{
                            document.getElementById('copy-icon').innerText = 'content_copy';
                            document.getElementById('copy-icon').style.color = '#1a73e8';
                            document.getElementById('copy-text').innerText = 'Click to Copy';
                            document.getElementById('copy-text').style.color = '#5a9bd5';
                        }}, 2000);
                    }});
                }}
                </script>
                """
                st.components.v1.html(sku_html, height=95)
                
                # 2) Item Tally Name
                st.markdown("<p class='subheading'>Item Tally Name</p>", unsafe_allow_html=True)
                if st.session_state.get("ai_item_name"):
                    name_text = st.session_state["ai_item_name"]
                    name_html = f"""
                    <div style="
                        background: #f0faf0;
                        border: 1px solid #c8e6c9;
                        border-radius: 8px;
                        padding: 12px 16px;
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        font-size: 15px;
                        font-weight: 600;
                        color: #2e7d32;
                    ">{name_text}</div>
                    """
                    st.markdown(name_html, unsafe_allow_html=True)
                else:
                    st.markdown("<p style='color: #999; font-size: 13px; font-style: italic;'>Click 'Generate Name & Description' below</p>", unsafe_allow_html=True)

                st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)

                # 3) Item Description
                st.markdown("<p class='subheading'>Item Description</p>", unsafe_allow_html=True)
                if st.session_state.get("ai_description"):
                    desc_text = st.session_state["ai_description"]
                    st.info(desc_text)
                else:
                    st.markdown("<p style='color: #999; font-size: 13px; font-style: italic;'>Click 'Generate Name & Description' below</p>", unsafe_allow_html=True)

                st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)

                # 4) Generate Name & Description button
                if ANTHROPIC_API_KEY and breakdown_items:
                    if st.button("✨ Generate Name & Description", key="gen_name_desc", use_container_width=False):
                        with st.spinner("Generating..."):
                            name, desc, err = generate_product_name_and_description(breakdown_items, cat, sku, extras_items=extras_items)
                            if name or desc:
                                st.session_state["ai_item_name"] = name or ""
                                st.session_state["ai_description"] = desc or ""
                                st.rerun()
                            else:
                                st.error(f"Failed: {err}")

                    if st.session_state.get("ai_item_name") or st.session_state.get("ai_description"):
                        copy_all_text = f"{st.session_state.get('ai_item_name', '')}\\n{st.session_state.get('ai_description', '')}"
                        copy_btn_html = f"""
                        <button onclick="navigator.clipboard.writeText(`{st.session_state.get('ai_item_name', '')}\\n{st.session_state.get('ai_description', '').replace('`', '')}`); this.innerText='✓ Copied'" 
                            style="background: #e8f4fd; border: 1px solid #c5dff0; border-radius: 6px; 
                            padding: 5px 12px; cursor: pointer; color: #1a73e8; font-size: 11px; margin-top: 4px;">
                            📋 Copy Name & Description
                        </button>
                        """
                        st.components.v1.html(copy_btn_html, height=40)

                st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)

                # 5) SKU Breakdown
                st.markdown("<p class='subheading'>SKU Breakdown</p>", unsafe_allow_html=True)
                
                breakdown_html = "<div style='font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 13px; color: #555; line-height: 1.8;'>"
                for item in all_breakdown_items:
                    breakdown_html += f"<div><code style='background: #f0f0f0; padding: 2px 6px; border-radius: 4px; font-size: 12px;'>{item['code']}</code> - {item['name']}</div>"
                breakdown_html += "</div>"
                st.markdown(breakdown_html, unsafe_allow_html=True)

                st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
                
                # 6) Generated QR Code
                st.markdown("<p class='subheading'>Generated QR Code</p>", unsafe_allow_html=True)
                
                qr_base64 = get_qr_code_base64(sku)
                
                qr_buffer = generate_qr_code(sku, size=300)
                qr_download_base64 = base64.b64encode(qr_buffer.getvalue()).decode()
                
                qr_html = f"""
                <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined" rel="stylesheet" />
                <style>
                    * {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
                    html, body {{ margin: 0; padding: 0; overflow: visible; }}
                </style>
                <div style="
                    background: white;
                    border: 1px solid #e0e0e0;
                    border-radius: 12px;
                    padding: 16px;
                    display: inline-flex;
                    align-items: center;
                    gap: 16px;
                    margin: 8px;
                    box-sizing: border-box;
                ">
                    <img src="data:image/png;base64,{qr_base64}" style="width: 70px; height: 70px;">
                    <a href="data:image/png;base64,{qr_download_base64}" 
                       download="{sku}_QR.png" 
                       style="
                           display: inline-flex;
                           align-items: center;
                           gap: 5px;
                           background: #f8f9fa;
                           border: 1px solid #e0e0e0;
                           border-radius: 6px;
                           padding: 8px 12px;
                           text-decoration: none;
                           color: #333;
                           font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                           font-size: 12px;
                           font-weight: 500;
                           cursor: pointer;
                       ">
                        <span class="material-symbols-outlined" style="font-size: 16px; color: #1a73e8;">download</span>
                        Download PNG
                    </a>
                </div>
                """
                st.components.v1.html(qr_html, height=130)
                
                # 7) Save to History
                st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
                sku_description = st.session_state.get("ai_description", "") or " - ".join([item['name'] for item in all_breakdown_items])
                if st.button("💾 Save to History", key="save_history", use_container_width=False):
                    add_to_sku_history(sku, sku_description, cat)
                    st.toast(f"✅ Saved: {sku}")
                    st.rerun()
                
            else:
                st.info("Select configuration to generate SKU")
    
    # Footer
    st.markdown("<div style='margin-top: 50px;'></div>", unsafe_allow_html=True)
    st.markdown(
        "<div style='text-align:center;color:#aaa;font-size:0.8em;'>"
        "Developed by <strong>Blastline India Pvt Ltd</strong>"
        "</div>",
        unsafe_allow_html=True
    )

# ==================================================
# LOGIN
# ==================================================
def login():
    """Admin login page."""
    
    # Center the login form
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("<h3 style='text-align: center; font-family: Montserrat, Arial, sans-serif;'>Admin Login</h3>", unsafe_allow_html=True)
        st.markdown("")
        pw = st.text_input("Password", type="password")
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Login", use_container_width=True):
                if pw == "admin123":
                    go("admin")
                else:
                    show_error("Invalid password. Please try again.")
        with c2:
            if st.button("Cancel", use_container_width=True):
                go("home")

# ==================================================
# ADMIN
# ==================================================
def admin():
    """Admin configuration page."""
    st.title("⚙️ Admin Settings")
    
    # Back to home button - constrained width
    col1, col2, col3 = st.columns([1, 3, 1])
    with col1:
        if st.button("← Back to Home"):
            go("home")
    
    st.markdown("---")

    inv = st.session_state["sku_data"]["inventory"]

    c1, c2 = st.columns([3, 1])
    with c1:
        if inv:
            cat = st.selectbox("Product Category", list(inv.keys()))
        else:
            cat = None
            st.info("No categories yet. Create one below.")
            
    with c2:
        with st.form("add_cat"):
            n = st.text_input("New Category", label_visibility="collapsed", placeholder="Category name")
            if st.form_submit_button("➕ Add") and n:
                if n in inv:
                    show_error(f"Category '{n}' already exists!")
                else:
                    inv[n] = {
                        "fields": {}, 
                        "extras": [], 
                        "settings": {
                            "separator": DEFAULT_SEPARATOR, 
                            "extras_mode": DEFAULT_EXTRAS_MODE
                        }
                    }
                    show_success(f"Category '{n}' created successfully!")
                    st.rerun()

    if not cat:
        return

    # Delete Category with confirmation
    if st.session_state.get("confirm_delete_cat") == cat:
        st.warning(f"⚠️ Are you sure you want to delete category '{cat}'? This cannot be undone!")
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("✓ Yes, Delete", type="primary"):
                del inv[cat]
                st.session_state["confirm_delete_cat"] = None
                show_success(f"Category '{cat}' deleted successfully!")
                st.rerun()
        with col2:
            if st.button("✗ Cancel"):
                st.session_state["confirm_delete_cat"] = None
                st.rerun()
    else:
        col1, col2, col3 = st.columns([1, 3, 1])
        with col1:
            if st.button("🗑️ Delete Category", help="Permanently delete this category"):
                st.session_state["confirm_delete_cat"] = cat
                st.rerun()

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["🛠️ Fields Configuration", "🎁 Extras Management", "⚙️ Category Settings", "📊 Export Matrix", "💾 Backup & Restore", "🔗 Machine Mapping"])

    # ---------- FIELDS CONFIG ----------
    with tab1:
        cat_data = inv[cat]
        normalize_fields(cat_data)
        fields = cat_data["fields"]

        # Add Field - Collapsible
        with st.expander("➕ Add Field", expanded=False):
            with st.form("add_field"):
                a, b, c = st.columns([2, 1, 1])
                name = a.text_input("Field Name")
                ftype = c.selectbox("Type", ["Dropdown", "Text Input"])
                if b.form_submit_button("Add") and name:
                    if name in fields:
                        show_error(f"Field '{name}' already exists!")
                    else:
                        fields[name] = {
                            "order": len(fields) + 1,
                            "options": [{"type": "text", "code": "", "name": ""}] if ftype == "Text Input" else []
                        }
                        show_success(f"Field '{name}' added successfully!")
                        st.rerun()

        if fields:
            # Field Order - Collapsible
            with st.expander("🔀 Field Order", expanded=False):
                df = pd.DataFrame([{"Field": k, "Order": v["order"]} for k, v in fields.items()])
                edited = st.data_editor(df, hide_index=True, use_container_width=True)
                
                if st.button("Apply Field Order"):
                    for _, r in edited.iterrows():
                        fields[r["Field"]]["order"] = int(r["Order"])
                    show_success("Field order updated successfully!")
                    st.rerun()

            # Rename / Delete Field - Collapsible
            with st.expander("✏️ Rename / Delete Field", expanded=False):
                field = st.selectbox("Select Field", ordered_fields(fields))
                new_name = st.text_input("Rename Field To", value=field)
                
                # Delete Field with confirmation
                if st.session_state.get("confirm_delete_field") == field:
                    st.warning(f"⚠️ Are you sure you want to delete field '{field}'? This cannot be undone!")
                    col1, col2, col3 = st.columns([1, 1, 2])
                    with col1:
                        if st.button("✓ Yes, Delete", type="primary", key="confirm_delete_field_btn"):
                            del fields[field]
                            st.session_state["confirm_delete_field"] = None
                            show_success(f"Field '{field}' deleted successfully!")
                            st.rerun()
                    with col2:
                        if st.button("✗ Cancel", key="cancel_delete_field_btn"):
                            st.session_state["confirm_delete_field"] = None
                            st.rerun()
                else:
                    c1, c2 = st.columns(2)
                    if c1.button("Rename", use_container_width=True):
                        if new_name == field:
                            show_info("Field name unchanged.")
                        elif new_name and new_name not in fields:
                            fields[new_name] = fields.pop(field)
                            show_success(f"Field renamed from '{field}' to '{new_name}'")
                            st.rerun()
                        elif new_name in fields:
                            show_error(f"Field '{new_name}' already exists!")
                            
                    if c2.button("Delete", use_container_width=True):
                        st.session_state["confirm_delete_field"] = field
                        st.rerun()

            # Field Options - Collapsible
            with st.expander("🛠️ Field Options", expanded=False):
                field_for_options = st.selectbox("Select Field to Edit Options", ordered_fields(fields), key="field_options_select")
                opts = fields[field_for_options]["options"]
                if opts and opts[0].get("type") == "text":
                    st.info("This is a text input field - users will enter values manually.")
                else:
                    df2 = normalize_option_df(opts)
                    edited_df = st.data_editor(
                        df2, 
                        num_rows="dynamic", 
                        hide_index=True,
                        use_container_width=True,
                        column_config={
                            "code": st.column_config.TextColumn("Code", help="SKU code segment"),
                            "name": st.column_config.TextColumn("Name", help="Display name"),
                            "order": st.column_config.NumberColumn("Order", help="Display order")
                        }
                    )
                    if st.button("Update Options"):
                        fields[field_for_options]["options"] = edited_df.to_dict("records")
                        show_success(f"Options for '{field_for_options}' updated successfully!")
                        st.rerun()
        else:
            st.info("No fields configured yet. Add a field above to get started.")

    # ---------- EXTRAS MANAGEMENT ----------
    with tab2:
        cat_data = inv[cat]
        extras = cat_data.get("extras", [])
        
        with st.expander("🎁 Manage Extras / Add-ons", expanded=False):
            st.info(f"Extras will be displayed as a list (8 per page) in the configurator with pagination controls.")
            
            extras_df = normalize_extras_df(extras)
            edited_extras = st.data_editor(
                extras_df,
                num_rows="dynamic",
                hide_index=True,
                use_container_width=True,
                column_config={
                    "code": st.column_config.TextColumn("Code", help="SKU code for this extra (will be appended to SKU)"),
                    "name": st.column_config.TextColumn("Name", help="Display name shown to users"),
                    "order": st.column_config.NumberColumn("Order", help="Display order (lower numbers appear first)")
                }
            )
            
            if st.button("💾 Save Extras", type="primary"):
                cat_data["extras"] = edited_extras.to_dict("records")
                show_success(f"Extras updated successfully! Total: {len(edited_extras)}")
                st.rerun()
        
        if len(extras) > 0:
            with st.expander("📋 Preview", expanded=False):
                st.write(f"**Total Extras:** {len(extras)}")
                total_pages = (len(extras) - 1) // EXTRAS_PER_PAGE + 1 if len(extras) > 0 else 1
                st.write(f"**Pages in Configurator:** {total_pages}")
                st.write(f"**Layout:** 8 items per page")

    # ---------- CATEGORY SETTINGS ----------
    with tab3:
        cat_data = inv[cat]
        settings = cat_data.get("settings", {})
        
        with st.expander("🔧 SKU Format Options", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("##### SKU Separator")
                separator = st.text_input(
                    "Separator Character",
                    value=settings.get("separator", DEFAULT_SEPARATOR),
                    help="Character used to separate SKU components",
                    max_chars=5,
                    key="separator_input"
                )
            
            with col2:
                st.markdown("##### Extras Selection Mode")
                extras_mode_setting = st.radio(
                    "Allow users to select:",
                    options=["Single", "Multiple"],
                    index=0 if settings.get("extras_mode", DEFAULT_EXTRAS_MODE) == "Single" else 1,
                    help="Single: Users can select only one extra (radio buttons)\nMultiple: Users can select multiple extras (checkboxes)",
                    key="extras_mode_input"
                )
            
            st.markdown("---")
            
            if st.button("💾 Save Settings", type="primary"):
                settings["separator"] = separator
                settings["extras_mode"] = extras_mode_setting
                cat_data["settings"] = settings
                show_success("Category settings saved successfully!")
                st.rerun()
        
        with st.expander("📋 Current Settings Preview", expanded=False):
            st.write(f"**Separator:** `{settings.get('separator', DEFAULT_SEPARATOR)}`")
            st.write(f"**Extras Mode:** {settings.get('extras_mode', DEFAULT_EXTRAS_MODE)}")
            if settings.get('extras_mode', DEFAULT_EXTRAS_MODE) == "Single":
                st.info("ℹ️ Users will see radio buttons to select one extra at a time")
            else:
                st.info("ℹ️ Users will see checkboxes to select multiple extras")

    # ---------- EXPORT MATRIX ----------
    with tab4:
        cat_data = inv[cat]
        normalize_fields(cat_data)
        
        with st.expander("📊 Full Matrix SKU Export", expanded=False):
            st.write("Generate a CSV file containing all possible SKU combinations for this category.")
            
            if cat_data["fields"]:
                # Preview count
                field_combos = []
                for f in ordered_fields(cat_data["fields"]):
                    opts = cat_data["fields"][f]["options"]
                    is_text = opts and opts[0].get("type") == "text"
                    if not is_text and opts:
                        field_combos.append(len(opts))
                
                if field_combos:
                    total_combinations = 1
                    for count in field_combos:
                        total_combinations *= count
                    
                    st.info(f"This will generate **{total_combinations:,}** SKU combinations")
                    
                    if st.button("🔄 Generate Matrix"):
                        with st.spinner("Generating SKU matrix..."):
                            matrix_df = generate_full_matrix(cat_data)
                            st.session_state["matrix_preview"] = matrix_df
                            show_success(f"Generated {len(matrix_df):,} SKU combinations!")
                            st.rerun()
                    
                    if "matrix_preview" in st.session_state:
                        st.markdown("---")
                        st.write("**Preview:**")
                        st.dataframe(st.session_state["matrix_preview"].head(50), use_container_width=True)
                        if len(st.session_state["matrix_preview"]) > 50:
                            st.caption(f"Showing first 50 of {len(st.session_state['matrix_preview']):,} rows")
                        
                        csv = st.session_state["matrix_preview"].to_csv(index=False)
                        
                        st.download_button(
                            "📥 Download CSV",
                            csv,
                            f"{cat}_full_matrix.csv",
                            "text/csv",
                            type="primary"
                        )
                else:
                    st.warning("No dropdown fields configured. Text input fields are excluded from matrix generation.")
            else:
                st.warning("No fields configured yet. Add fields in the Fields Configuration tab.")

    # ---------- BACKUP & RESTORE ----------
    with tab5:
        st.markdown("### 💾 Database Backup & Restore")
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 📤 Export Database")
            st.write("Download a complete backup of all categories, fields, extras, and settings.")
            
            # Prepare JSON data
            backup_data = json.dumps(st.session_state["sku_data"], indent=2)
            
            # Show summary
            total_categories = len(st.session_state["sku_data"].get("inventory", {}))
            st.info(f"📁 **{total_categories}** categories in database")
            
            # Download button
            st.download_button(
                label="⬇️ Download Backup (JSON)",
                data=backup_data,
                file_name=f"blastline_sku_backup_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                type="primary",
                use_container_width=True
            )
            
            st.caption("💡 Tip: Keep regular backups before making major changes")
        
        with col2:
            st.markdown("#### 📥 Import Database")
            st.write("Restore from a previously exported backup file.")
            
            uploaded_file = st.file_uploader(
                "Choose backup file",
                type=["json"],
                help="Upload a JSON backup file previously exported from this app"
            )
            
            if uploaded_file is not None:
                try:
                    # Parse the uploaded JSON
                    import_data = json.load(uploaded_file)
                    
                    # Validate structure
                    if "inventory" in import_data:
                        num_categories = len(import_data["inventory"])
                        st.success(f"✅ Valid backup file detected: **{num_categories}** categories")
                        
                        # Show preview
                        with st.expander("Preview categories"):
                            for cat_name in import_data["inventory"].keys():
                                cat_data = import_data["inventory"][cat_name]
                                num_fields = len(cat_data.get("fields", {}))
                                num_extras = len(cat_data.get("extras", []))
                                st.write(f"• **{cat_name}**: {num_fields} fields, {num_extras} extras")
                        
                        # Import options
                        import_mode = st.radio(
                            "Import mode:",
                            ["🔄 Replace all (overwrites existing data)", "➕ Merge (adds new, keeps existing)"],
                            key="import_mode"
                        )
                        
                        st.warning("⚠️ **Warning:** This action cannot be undone. Make sure you have a backup!")
                        
                        if st.button("🚀 Import Database", type="primary", use_container_width=True):
                            if "Replace" in import_mode:
                                # Full replacement
                                st.session_state["sku_data"] = import_data
                                # Save to disk
                                if GithubStorage().save(st.session_state["sku_data"]):
                                    show_success(f"✅ Database replaced successfully! Imported {num_categories} categories.")
                                    st.rerun()
                                else:
                                    show_error("Failed to save imported data to disk.")
                            else:
                                # Merge mode
                                existing_inv = st.session_state["sku_data"].get("inventory", {})
                                imported_inv = import_data.get("inventory", {})
                                
                                added = 0
                                skipped = 0
                                for cat_name, cat_data in imported_inv.items():
                                    if cat_name not in existing_inv:
                                        existing_inv[cat_name] = cat_data
                                        added += 1
                                    else:
                                        skipped += 1
                                
                                st.session_state["sku_data"]["inventory"] = existing_inv
                                
                                # Save to disk
                                if GithubStorage().save(st.session_state["sku_data"]):
                                    show_success(f"✅ Merge complete! Added {added} new categories, skipped {skipped} existing.")
                                    st.rerun()
                                else:
                                    show_error("Failed to save merged data to disk.")
                    else:
                        show_error("❌ Invalid backup file format. Missing 'inventory' key.")
                        
                except json.JSONDecodeError:
                    show_error("❌ Invalid JSON file. Please upload a valid backup file.")
                except Exception as e:
                    show_error(f"❌ Error reading file: {str(e)}")

    # ---------- MACHINE MAPPING ----------
    with tab6:
        cat_data = inv[cat]
        normalize_fields(cat_data)
        fields = cat_data["fields"]
        extras = cat_data.get("extras", [])
        settings = cat_data.get("settings", {})

        st.markdown("### Machine-Based Field Visibility")
        st.caption("Configure which fields, options, and extras are available for each machine type.")

        field_names = ordered_fields(fields)
        if not field_names:
            st.warning("No fields configured. Add fields first in the Fields Configuration tab.")
        else:
            with st.expander("⚙️ Machine Selector Field", expanded=False):
                current_machine_field = settings.get("machine_field", "Machine")
                machine_field_name = st.selectbox(
                    "Which field acts as the Machine selector?",
                    field_names,
                    index=field_names.index(current_machine_field) if current_machine_field in field_names else 0,
                    key="machine_field_select"
                )
                if st.button("Set Machine Field"):
                    settings["machine_field"] = machine_field_name
                    cat_data["settings"] = settings
                    show_success(f"Machine selector field set to '{machine_field_name}'")
                    st.rerun()

            mf_name = settings.get("machine_field", "Machine")
            if mf_name not in fields:
                st.info(f"Machine field '{mf_name}' not found in this category. Set one above.")
            else:
                machine_opts = fields[mf_name].get("options", [])
                machine_opts = [o for o in machine_opts if o.get("code")]
                if not machine_opts:
                    st.info("No machine options configured yet. Add options to the machine field first.")
                else:
                    machine_labels = [f"{o['code']} - {o['name']}" for o in machine_opts]
                    selected_label = st.selectbox("Configure mapping for machine:", machine_labels, key="mapping_machine_select")
                    selected_machine_code = machine_opts[machine_labels.index(selected_label)]["code"]

                    other_fields = [f for f in field_names if f != mf_name]
                    non_text_fields = [f for f in other_fields if not (fields[f]["options"] and fields[f]["options"][0].get("type") == "text")]
                    text_fields = [f for f in other_fields if fields[f]["options"] and fields[f]["options"][0].get("type") == "text"]

                    st.markdown("---")

                    with st.expander("📋 Field Visibility", expanded=True):
                        st.caption("Check fields that should be **visible** when this machine is selected. Unchecked fields will be hidden.")
                        field_checks = {}
                        for f in other_fields:
                            current_machines = fields[f].get("machines", [])
                            default_on = not current_machines or selected_machine_code in current_machines
                            field_checks[f] = st.checkbox(f, value=default_on, key=f"fv_{cat}_{selected_machine_code}_{f}")

                    if non_text_fields:
                        visible_dropdown_fields = [f for f in non_text_fields if field_checks.get(f, True)]
                        if visible_dropdown_fields:
                            with st.expander("🔧 Option Visibility (per field)", expanded=False):
                                st.caption("For each visible dropdown field, check which options are available for this machine.")
                                option_checks = {}
                                for f in visible_dropdown_fields:
                                    st.markdown(f"**{f}**")
                                    opts = fields[f]["options"]
                                    option_checks[f] = {}
                                    for i, opt in enumerate(opts):
                                        if not opt.get("code"):
                                            continue
                                        opt_machines = opt.get("machines", [])
                                        default_on = not opt_machines or selected_machine_code in opt_machines
                                        label = f"{opt['code']} - {opt.get('name', '')}"
                                        option_checks[f][i] = st.checkbox(label, value=default_on, key=f"ov_{cat}_{selected_machine_code}_{f}_{i}")
                                    st.markdown("---")
                        else:
                            option_checks = {}
                    else:
                        option_checks = {}

                    if extras:
                        with st.expander("🎁 Extras Visibility", expanded=False):
                            st.caption("Check which extras are available when this machine is selected.")
                            extras_checks = {}
                            for i, e in enumerate(extras):
                                if not e.get("code"):
                                    continue
                                e_machines = e.get("machines", [])
                                default_on = not e_machines or selected_machine_code in e_machines
                                label = f"{e['code']} - {e.get('name', '')}"
                                extras_checks[i] = st.checkbox(label, value=default_on, key=f"ev_{cat}_{selected_machine_code}_{i}")
                    else:
                        extras_checks = {}

                    st.markdown("---")
                    if st.button("💾 Save Machine Mapping", type="primary"):
                        all_machine_codes = [o["code"] for o in machine_opts if o.get("code")]

                        for f in other_fields:
                            current_machines = fields[f].get("machines", [])
                            new_machines = set(current_machines) if current_machines else set(all_machine_codes)
                            if field_checks.get(f, True):
                                new_machines.add(selected_machine_code)
                            else:
                                new_machines.discard(selected_machine_code)
                            if new_machines >= set(all_machine_codes):
                                fields[f].pop("machines", None)
                            else:
                                fields[f]["machines"] = sorted(new_machines)

                        for f, opts_map in option_checks.items():
                            opts = fields[f]["options"]
                            for i, checked in opts_map.items():
                                opt = opts[i]
                                current_machines = opt.get("machines", [])
                                new_machines = set(current_machines) if current_machines else set(all_machine_codes)
                                if checked:
                                    new_machines.add(selected_machine_code)
                                else:
                                    new_machines.discard(selected_machine_code)
                                if new_machines >= set(all_machine_codes):
                                    opt.pop("machines", None)
                                else:
                                    opt["machines"] = sorted(new_machines)

                        for i, checked in extras_checks.items():
                            e = extras[i]
                            current_machines = e.get("machines", [])
                            new_machines = set(current_machines) if current_machines else set(all_machine_codes)
                            if checked:
                                new_machines.add(selected_machine_code)
                            else:
                                new_machines.discard(selected_machine_code)
                            if new_machines >= set(all_machine_codes):
                                e.pop("machines", None)
                            else:
                                e["machines"] = sorted(new_machines)

                        show_success(f"Machine mapping saved for '{selected_label}'!")
                        st.rerun()

    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 3, 1])
    with col1:
        if st.button("☁️ Save to Cloud", type="primary"):
            with st.spinner("Saving to cloud..."):
                if GithubStorage().save(st.session_state["sku_data"]):
                    show_success("Configuration saved to cloud successfully!")
                else:
                    show_error("Failed to save to cloud. Check your connection and credentials.")
            go("home")

# ==================================================
# HISTORY PAGE
# ==================================================
def history_page():
    """SKU History page."""
    with st.sidebar:
        render_sidebar_nav("history")
    
    st.markdown("<h2 style='text-align: center;'>📋 SKU History</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #666;'>Recently generated SKU codes</p>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    history = st.session_state.get("sku_history", [])
    
    if history:
        # Create a nice table view
        for idx, entry in enumerate(history):
            col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
            
            with col1:
                st.markdown(f"### `{entry['sku']}`")
            with col2:
                st.markdown(f"**{entry['category']}**")
            with col3:
                st.caption(entry['timestamp'])
            with col4:
                # Copy to clipboard using HTML/JS
                copy_html = f"""
                <button onclick="navigator.clipboard.writeText('{entry['sku']}'); this.innerText='✓ Copied'" 
                    style="background: #e8f4fd; border: 1px solid #1a73e8; border-radius: 6px; 
                    padding: 5px 10px; cursor: pointer; color: #1a73e8; font-size: 12px;">
                    📋 Copy
                </button>
                """
                st.markdown(copy_html, unsafe_allow_html=True)
            
            # Show description
            if entry.get('description'):
                st.caption(f"↳ {entry['description']}")
            
            st.markdown("<hr style='margin: 10px 0; border: none; border-top: 1px solid #eee;'>", unsafe_allow_html=True)
        
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("🗑️ Clear All History", type="secondary"):
                st.session_state["sku_history"] = []
                st.rerun()
    else:
        st.info("📭 No SKU history yet. Generate some SKUs to see them here!")
        if st.button("🏠 Go to SKU Generator"):
            go("home")

# ==================================================
# DECODER PAGE
# ==================================================
def decoder_page():
    """SKU Decoder page."""
    with st.sidebar:
        render_sidebar_nav("decoder")
    
    st.markdown("<h2 style='text-align: center;'>🔍 SKU Decoder</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #666;'>Enter a SKU code to see what each part means</p>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Center the input
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        decode_input = st.text_input(
            "Enter SKU Code",
            placeholder="e.g., BL20MSF0",
            key="decoder_main_input",
            label_visibility="collapsed"
        )
        
        st.markdown("<p style='text-align: center; font-size: 12px; color: #888;'>Type or paste any SKU code above</p>", unsafe_allow_html=True)
    
    if decode_input:
        st.markdown("---")
        st.markdown(f"### Decoding: `{decode_input}`")
        
        inv = st.session_state["sku_data"]["inventory"]
        results = decode_sku(decode_input, inv)
        
        if results:
            for result in results:
                st.success(f"✅ **Category Matched:** {result['category']}")
                
                st.markdown("#### Component Breakdown:")
                
                # Create a nice breakdown table
                for part in result['parts']:
                    col1, col2, col3 = st.columns([1, 1, 2])
                    with col1:
                        st.markdown(f"**{part['field']}**")
                    with col2:
                        st.code(part['code'])
                    with col3:
                        st.markdown(part['name'])
                
                if result.get('extras'):
                    st.markdown("#### Extras:")
                    for extra in result['extras']:
                        col1, col2, col3 = st.columns([1, 1, 2])
                        with col1:
                            st.markdown("**Extra**")
                        with col2:
                            st.code(extra['code'])
                        with col3:
                            st.markdown(extra['name'])
                
                if result.get('remaining'):
                    st.warning(f"⚠️ Unmatched portion: `{result['remaining']}`")
        else:
            st.error("❌ Could not decode this SKU. It may not match any configured category.")
            st.info("💡 Make sure the SKU follows the correct format for one of your product categories.")

# ==================================================
# SCANNER PAGE
# ==================================================
def scanner_page():
    """QR Scanner page with JavaScript-based scanning."""
    with st.sidebar:
        render_sidebar_nav("scanner")
    
    st.markdown("<h2 style='text-align: center;'>📱 QR Code Scanner</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #666;'>Scan a QR code to decode the SKU instantly</p>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    # JavaScript QR Scanner using html5-qrcode library
    qr_scanner_html = """
    <script src="https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js"></script>
    <style>
        #qr-reader {
            width: 100%;
            max-width: 500px;
            margin: 0 auto;
        }
        #qr-reader__scan_region {
            border-radius: 12px;
            overflow: hidden;
        }
        #result-container {
            margin-top: 20px;
            padding: 20px;
            border-radius: 12px;
            text-align: center;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }
        .success-result {
            background: #d4edda;
            border: 1px solid #c3e6cb;
        }
        .scanned-sku {
            font-size: 24px;
            font-weight: bold;
            color: #155724;
            margin: 10px 0;
            font-family: monospace;
        }
        .copy-btn {
            background: #28a745;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            margin: 5px;
        }
        .copy-btn:hover {
            background: #218838;
        }
        .decode-btn {
            background: #007bff;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            margin: 5px;
        }
        .decode-btn:hover {
            background: #0056b3;
        }
        #start-btn {
            padding: 16px 32px;
            font-size: 18px;
            border: none;
            border-radius: 12px;
            cursor: pointer;
            background: #1a73e8;
            color: white;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }
        #start-btn:hover {
            background: #1557b0;
        }
        #stop-btn {
            width: 60px;
            height: 60px;
            border-radius: 50%;
            border: 4px solid #fff;
            background: #dc3545;
            cursor: pointer;
            box-shadow: 0 4px 15px rgba(220, 53, 69, 0.4);
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        #stop-btn:hover {
            background: #c82333;
            transform: scale(1.05);
        }
        #stop-btn:active {
            transform: scale(0.95);
        }
        #stop-btn .stop-icon {
            width: 20px;
            height: 20px;
            background: white;
            border-radius: 3px;
        }
        .btn-container {
            text-align: center;
            margin: 15px 0;
        }
        .stop-container {
            text-align: center;
            margin: 20px 0;
            display: none;
        }
        .stop-container.active {
            display: block;
        }
    </style>
    
    <div class="btn-container" id="start-container">
        <button id="start-btn" onclick="startScanner()">📷 Start Camera</button>
    </div>
    
    <div id="qr-reader"></div>
    
    <div class="stop-container" id="stop-container">
        <button id="stop-btn" onclick="stopScanner()" title="Stop Camera">
            <div class="stop-icon"></div>
        </button>
        <p style="margin-top: 8px; color: #666; font-size: 12px;">Tap to stop</p>
    </div>
    
    <div id="result-container"></div>
    
    <script>
        let html5QrCode = null;
        let lastResult = '';
        
        function startScanner() {
            document.getElementById('start-container').style.display = 'none';
            document.getElementById('stop-container').classList.add('active');
            document.getElementById('result-container').innerHTML = '';
            
            html5QrCode = new Html5Qrcode("qr-reader");
            
            html5QrCode.start(
                { facingMode: "environment" },
                {
                    fps: 10,
                    qrbox: { width: 250, height: 250 }
                },
                (decodedText, decodedResult) => {
                    if (decodedText !== lastResult) {
                        lastResult = decodedText;
                        onScanSuccess(decodedText);
                    }
                },
                (errorMessage) => {
                    // Ignore scan errors
                }
            ).catch((err) => {
                document.getElementById('result-container').innerHTML = 
                    '<div style="color: #dc3545; padding: 20px;">❌ Camera access denied or not available.<br>Please allow camera access and try again.</div>';
                document.getElementById('start-container').style.display = 'block';
                document.getElementById('stop-container').classList.remove('active');
            });
        }
        
        function stopScanner() {
            if (html5QrCode) {
                html5QrCode.stop().then(() => {
                    document.getElementById('start-container').style.display = 'block';
                    document.getElementById('stop-container').classList.remove('active');
                });
            }
        }
        
        function onScanSuccess(decodedText) {
            // Play a beep sound
            try {
                const audioContext = new (window.AudioContext || window.webkitAudioContext)();
                const oscillator = audioContext.createOscillator();
                const gainNode = audioContext.createGain();
                oscillator.connect(gainNode);
                gainNode.connect(audioContext.destination);
                oscillator.frequency.value = 800;
                oscillator.type = 'sine';
                gainNode.gain.value = 0.3;
                oscillator.start();
                setTimeout(() => oscillator.stop(), 150);
            } catch(e) {}
            
            document.getElementById('result-container').innerHTML = `
                <div class="success-result">
                    <div style="color: #155724; font-size: 16px;">✅ QR Code Scanned!</div>
                    <div class="scanned-sku">${decodedText}</div>
                    <button class="copy-btn" onclick="copyToClipboard('${decodedText}')">📋 Copy SKU</button>
                    <button class="decode-btn" onclick="window.parent.postMessage({type:'qr_scanned', sku:'${decodedText}'}, '*')">🔍 Decode SKU</button>
                </div>
            `;
        }
        
        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => {
                const btn = event.target;
                btn.innerText = '✓ Copied!';
                setTimeout(() => btn.innerText = '📋 Copy SKU', 2000);
            });
        }
    </script>
    """
    
    # Display the QR scanner
    st.components.v1.html(qr_scanner_html, height=550)
    
    st.markdown("---")
    
    # Manual entry as fallback
    st.markdown("### ✍️ Or Enter SKU Manually")
    
    scanned_sku = st.text_input("Enter SKU code", placeholder="e.g., BL20MSF0", key="scanner_manual_input")
    
    if scanned_sku:
        st.markdown("---")
        st.markdown(f"### Decoding: `{scanned_sku}`")
        
        inv = st.session_state["sku_data"]["inventory"]
        results = decode_sku(scanned_sku, inv)
        
        if results:
            for result in results:
                st.success(f"✅ **{result['category']}**")
                
                for part in result['parts']:
                    col1, col2, col3 = st.columns([1, 1, 2])
                    with col1:
                        st.markdown(f"**{part['field']}**")
                    with col2:
                        st.code(part['code'])
                    with col3:
                        st.markdown(part['name'])
                
                for extra in result.get('extras', []):
                    col1, col2, col3 = st.columns([1, 1, 2])
                    with col1:
                        st.markdown("**Extra**")
                    with col2:
                        st.code(extra['code'])
                    with col3:
                        st.markdown(extra['name'])
        else:
            st.error("❌ Could not decode SKU")
    
    st.markdown("---")
    st.markdown("### 💡 Tips")
    st.markdown("""
    - Click **Start Camera** to activate the scanner
    - Point your camera at any QR code
    - The SKU will be detected automatically with a beep sound
    - Click **Copy SKU** or **Decode SKU** to see the breakdown
    """)

# ==================================================
# ROUTER
# ==================================================
if st.session_state["page"] == "home":
    home()
elif st.session_state["page"] == "login":
    login()
elif st.session_state["page"] == "admin":
    admin()
elif st.session_state["page"] == "history":
    history_page()
elif st.session_state["page"] == "decoder":
    decoder_page()
elif st.session_state["page"] == "scanner":
    scanner_page()
