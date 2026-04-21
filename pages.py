import streamlit as st
import pandas as pd
import json
import os

from storage import GithubStorage
from helpers import (
    DEFAULT_SEPARATOR,
    DEFAULT_EXTRAS_MODE,
    EXTRAS_PER_PAGE,
    normalize_fields,
    ordered_fields,
    get_machine_field,
    filter_for_machine,
    normalize_option_df,
    normalize_extras_df,
    generate_full_matrix,
    generate_mapped_name_and_description,
    add_to_sku_history,
    decode_sku,
    render_sidebar_nav,
    go,
    show_success,
    show_error,
    show_info,
    format_fitting_option,
    parse_fitting_parts,
)


# ==================================================
# HOME
# ==================================================
def home():
    """Main SKU configuration page."""

    with st.sidebar:
        render_sidebar_nav("home")

    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        .block-container { padding-top: 2rem; }

        .subheading {
            font-size: 11px;
            font-weight: 700;
            color: #aaa;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
            padding-bottom: 6px;
            border-bottom: 2px solid #f0f0f0;
        }

        .page-title {
            text-align: center;
            margin-bottom: 0;
            font-weight: 700;
            font-size: 26px;
            color: #1a1a1a;
            letter-spacing: -0.5px;
        }
        .page-subtitle {
            text-align: center;
            font-size: 13px;
            color: #aaa;
            margin-bottom: 8px;
            font-weight: 400;
        }

        .config-label {
            font-size: 11px;
            font-weight: 600;
            color: #999;
            margin-bottom: 3px;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }

        [data-testid="stSelectbox"] > div > div {
            border-radius: 8px !important;
        }

        [data-testid="stCheckbox"] label {
            font-size: 13px !important;
        }

        [data-testid="stHorizontalBlock"] > div:first-child {
            border-right: 1px solid #eee;
            padding-right: 2rem;
        }

        header[data-testid="stHeader"] {
            background: transparent;
        }

        .fitting-breakdown {
            background: #f8f9fb;
            border: 1px solid #e8eaed;
            border-radius: 8px;
            padding: 10px 14px;
            margin-top: 6px;
            margin-bottom: 4px;
            display: flex;
            gap: 16px;
            font-size: 12px;
            font-family: 'Inter', sans-serif;
        }
        .fitting-part {
            flex: 1;
        }
        .fitting-part-label {
            font-weight: 700;
            color: #888;
            text-transform: uppercase;
            font-size: 10px;
            letter-spacing: 0.5px;
            margin-bottom: 2px;
        }
        .fitting-part-value {
            color: #333;
            font-weight: 500;
        }
        .fitting-divider {
            width: 1px;
            background: #dde1e6;
            align-self: stretch;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("<h2 class='page-title'>Blastline SKU Configurator</h2>", unsafe_allow_html=True)
    st.markdown("<p class='page-subtitle'>Configure product specifications and generate SKU codes</p>", unsafe_allow_html=True)

    inv = st.session_state["sku_data"]["inventory"]
    if not inv:
        st.warning("No categories available. Please contact admin to set up product categories.")
        return

    cat_spacer1, cat_col, cat_spacer2 = st.columns([2.5, 1.5, 2.5])
    with cat_col:
        cat_list = list(inv.keys())
        stored = st.session_state.get("selected_category")
        idx = cat_list.index(stored) if stored in cat_list else 0
        cat = st.selectbox("Product Category", cat_list, index=idx, key="selected_category", label_visibility="collapsed")

    cat_data = inv[cat]
    normalize_fields(cat_data)

    fields = cat_data["fields"]
    extras = cat_data.get("extras", [])
    sep = cat_data.get("settings", {}).get("separator", DEFAULT_SEPARATOR)
    extras_mode = cat_data.get("settings", {}).get("extras_mode", DEFAULT_EXTRAS_MODE)

    sel = {}
    chosen = []

    mf_name = get_machine_field(cat_data)
    selected_machine_code = None

    st.markdown("<div style='margin-top: 16px;'></div>", unsafe_allow_html=True)

    left_col, right_col = st.columns([1, 1], gap="large")

    with left_col:
        st.markdown("<p class='subheading'>Configuration</p>", unsafe_allow_html=True)

        if mf_name in fields:
            mf_opts = fields[mf_name]["options"]
            if mf_opts and not mf_opts[0].get("type") == "text":
                st.markdown(f"<p class='config-label'>{mf_name}</p>", unsafe_allow_html=True)
                mf_selection = st.selectbox(
                    mf_name,
                    mf_opts,
                    format_func=lambda x: f"{x['code']} - {x['name']}",
                    help=f"Select {mf_name}",
                    label_visibility="collapsed"
                )
                sel[mf_name] = {"code": mf_selection["code"], "name": mf_selection["name"], "tally_name": mf_selection.get("tally_name", ""), "description": mf_selection.get("description", "")}
                selected_machine_code = mf_selection["code"]

        for f in ordered_fields(fields):
            if f == mf_name:
                continue
            field_machines = fields[f].get("machines", [])
            if field_machines and selected_machine_code and selected_machine_code not in field_machines:
                continue

            opts = fields[f]["options"]
            is_text = opts and opts[0].get("type") == "text"
            if is_text:
                st.markdown(f"<p class='config-label'>{f}</p>", unsafe_allow_html=True)
                text_val = st.text_input(f, help=f"Enter {f}", placeholder=f"Enter {f}", label_visibility="collapsed")
                sel[f] = {"code": text_val, "name": text_val, "tally_name": text_val, "description": text_val}
            else:
                filtered_opts = filter_for_machine(opts, selected_machine_code) if selected_machine_code else opts
                if filtered_opts:
                    is_fittings = f.lower() == "fittings"
                    st.markdown(f"<p class='config-label'>{f}</p>", unsafe_allow_html=True)
                    fmt = format_fitting_option if is_fittings else lambda x: f"{x['code']} - {x['name']}"
                    o = st.selectbox(
                        f,
                        filtered_opts,
                        format_func=fmt,
                        help=f"Select {f}",
                        label_visibility="collapsed"
                    )
                    sel[f] = {"code": o["code"], "name": o["name"], "tally_name": o.get("tally_name", ""), "description": o.get("description", "")}

                    if is_fittings and o.get("name", "").lower() != "none":
                        inlet, outlet = parse_fitting_parts(o["name"])
                        parts_html = ""
                        if inlet:
                            parts_html += (
                                '<div class="fitting-part">'
                                '<div class="fitting-part-label">Inlet</div>'
                                f'<div class="fitting-part-value">{inlet}</div>'
                                '</div>'
                                '<div class="fitting-divider"></div>'
                            )
                        if outlet:
                            parts_html += (
                                '<div class="fitting-part">'
                                '<div class="fitting-part-label">Outlet</div>'
                                f'<div class="fitting-part-value">{outlet}</div>'
                                '</div>'
                            )
                        if parts_html:
                            st.markdown(f'<div class="fitting-breakdown">{parts_html}</div>', unsafe_allow_html=True)

        st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
        st.markdown("<p class='subheading'>Extras</p>", unsafe_allow_html=True)

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
                            chosen.append({"code": e["code"], "name": e["name"], "tally_name": e.get("tally_name", ""), "description": e.get("description", "")})
                            break
            else:
                num_cols = 3
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
                                        chosen.append({"code": e["code"], "name": e["name"], "tally_name": e.get("tally_name", ""), "description": e.get("description", "")})
        else:
            if extras and selected_machine_code:
                st.info("No extras available for this machine")
            else:
                st.info("No extras configured")

    # Calculate SKU
    base = sep.join([sel[k]["code"] for k in ordered_fields(fields) if sel.get(k) and sel[k]["code"]])
    extras_codes = "".join([c["code"] for c in chosen])
    sku = base + (sep + "X" if base and extras_codes else "") + extras_codes

    breakdown_items = []
    fittings_selected = False
    for k in ordered_fields(fields):
        if sel.get(k) and sel[k].get("code") and sel[k].get("name"):
            breakdown_items.append({"code": str(sel[k]["code"]), "name": str(sel[k]["name"]), "field": k})
            if k.lower() == "fittings":
                fittings_selected = True
    extras_items = []
    for c in chosen:
        if c.get("code") and c.get("name"):
            extras_items.append({"code": str(c["code"]), "name": str(c["name"])})
    all_breakdown_items = breakdown_items + extras_items

    with right_col:
        with st.container():
            if sku:
                mapped_name, mapped_desc = generate_mapped_name_and_description(sel, ordered_fields(fields), chosen, fittings_selected)
                escaped_name = mapped_name.replace("'", "\\'").replace("`", "") if mapped_name else ""
                escaped_desc = mapped_desc.replace("'", "\\'").replace("`", "") if mapped_desc else ""

                sq = "\x27"  # single quote for use inside f-string expressions
                name_card_html = (
                    '<div class="copy-card name-card" onclick="copyText('
                    + sq + escaped_name + sq + ", " + sq + "name" + sq
                    + ')"><div class="text">' + mapped_name
                    + '</div><div class="copy-btn"><span id="name-icon" class="material-symbols-outlined">content_copy</span>'
                    + '<p id="name-label">Click to Copy</p></div></div>'
                ) if mapped_name else '<div style="color: #bbb; font-size: 13px; font-style: italic; padding: 8px 0;">Set Tally Name mappings in Settings</div>'

                desc_card_html = (
                    '<div class="copy-card desc-card" onclick="copyText('
                    + sq + escaped_desc + sq + ", " + sq + "desc" + sq
                    + ')"><div class="text">' + mapped_desc
                    + '</div><div class="copy-btn"><span id="desc-icon" class="material-symbols-outlined">content_copy</span>'
                    + '<p id="desc-label">Click to Copy</p></div></div>'
                ) if mapped_desc else '<div style="color: #bbb; font-size: 13px; font-style: italic; padding: 8px 0;">Set Description mappings in Settings</div>'

                breakdown_html = "".join(
                    '<div class="breakdown-row"><span class="breakdown-code">'
                    + item["code"] + "</span> " + item["name"] + "</div>"
                    for item in all_breakdown_items
                )

                output_html = f"""
                <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Material+Symbols+Outlined" rel="stylesheet" />
                <style>
                    * {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 0; box-sizing: border-box; }}
                    html, body {{ overflow: visible; }}
                    .section-label {{
                        font-size: 11px; font-weight: 600; color: #999; text-transform: uppercase;
                        letter-spacing: 0.8px; margin-bottom: 6px;
                    }}
                    .copy-card {{
                        border-radius: 10px; padding: 14px 16px;
                        display: flex; align-items: center; justify-content: space-between;
                        cursor: pointer; transition: box-shadow 0.15s ease;
                        gap: 12px;
                    }}
                    .copy-card:hover {{ box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
                    .copy-card .text {{ word-break: break-word; flex: 1; }}
                    .copy-card .copy-btn {{
                        flex-shrink: 0; display: flex; flex-direction: column;
                        align-items: center; gap: 1px; opacity: 0.6; transition: opacity 0.15s;
                    }}
                    .copy-card:hover .copy-btn {{ opacity: 1; }}
                    .copy-btn span {{ font-size: 18px; }}
                    .copy-btn p {{ font-size: 8px; font-weight: 500; margin: 0; }}
                    .sku-card {{ background: #f0f6ff; border: 1.5px solid #d0e3ff; }}
                    .sku-card .text {{ font-size: 18px; font-weight: 700; color: #1a5ed1; letter-spacing: 0.5px; }}
                    .sku-card .copy-btn {{ color: #1a5ed1; }}
                    .sku-card .copy-btn p {{ color: #7aabf0; }}
                    .name-card {{ background: #f0faf2; border: 1.5px solid #c8e6cc; }}
                    .name-card .text {{ font-size: 15px; font-weight: 600; color: #1b6e2a; }}
                    .name-card .copy-btn {{ color: #1b6e2a; }}
                    .name-card .copy-btn p {{ color: #6ebb7e; }}
                    .desc-card {{ background: #faf8f0; border: 1.5px solid #e6dfc8; }}
                    .desc-card .text {{ font-size: 14px; font-weight: 500; color: #5a4e2b; }}
                    .desc-card .copy-btn {{ color: #5a4e2b; }}
                    .desc-card .copy-btn p {{ color: #b3a67a; }}
                    .breakdown {{ margin-top: 4px; }}
                    .breakdown-row {{
                        display: flex; align-items: center; gap: 8px;
                        padding: 4px 0; font-size: 13px; color: #555;
                    }}
                    .breakdown-code {{
                        background: #eef2f7; color: #3366aa; padding: 2px 8px;
                        border-radius: 4px; font-size: 12px; font-weight: 600;
                        font-family: 'SF Mono', 'Fira Code', monospace; min-width: 28px; text-align: center;
                    }}
                </style>

                <div style="display: flex; flex-direction: column; gap: 16px;">
                    <!-- SKU -->
                    <div>
                        <div class="section-label">Generated SKU</div>
                        <div class="copy-card sku-card" onclick="copyText('{sku}', 'sku')">
                            <div class="text">{sku}</div>
                            <div class="copy-btn">
                                <span id="sku-icon" class="material-symbols-outlined">content_copy</span>
                                <p id="sku-label">Click to Copy</p>
                            </div>
                        </div>
                    </div>

                    {'<!-- Item Name --><div><div class="section-label">Item Name</div>' + name_card_html + '</div>' if cat != "Blast Machine" else ''}

                    <!-- Item Description -->
                    <div>
                        <div class="section-label">Item Description</div>
                        {desc_card_html}
                    </div>

                    <!-- SKU Breakdown -->
                    <div>
                        <div class="section-label">SKU Breakdown</div>
                        <div class="breakdown">
                            {breakdown_html}
                        </div>
                    </div>
                </div>

                <script>
                function copyText(text, id) {{
                    navigator.clipboard.writeText(text).then(function() {{
                        var icon = document.getElementById(id + '-icon');
                        var label = document.getElementById(id + '-label');
                        icon.innerText = 'check_circle';
                        label.innerText = 'Copied!';
                        setTimeout(function() {{
                            icon.innerText = 'content_copy';
                            label.innerText = 'Click to Copy';
                        }}, 2000);
                    }});
                }}
                </script>
                """

                total_items = len(all_breakdown_items)
                card_height = 280 + (total_items * 28)
                if cat == "Blast Machine":
                    card_height -= 80
                if mapped_desc and len(mapped_desc) > 80:
                    card_height += 30
                st.components.v1.html(output_html, height=card_height)

                sku_description = mapped_desc or " - ".join([item['name'] for item in all_breakdown_items])
                if st.button("💾 Save to History", key="save_history", use_container_width=False):
                    add_to_sku_history(sku, sku_description, cat)
                    st.toast(f"Saved: {sku}")
                    st.rerun()

            else:
                st.info("Select configuration to generate SKU")

    st.markdown("<div style='margin-top: 40px;'></div>", unsafe_allow_html=True)
    st.markdown(
        "<div style='text-align:center;color:#ccc;font-size:11px;font-family:Inter,sans-serif;letter-spacing:0.3px;'>"
        "Blastline India Pvt Ltd"
        "</div>",
        unsafe_allow_html=True
    )


# ==================================================
# LOGIN
# ==================================================
def login():
    """Admin login page."""

    if st.session_state.get("admin_authenticated"):
        go("admin")
        return

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown("<h3 style='text-align: center; font-family: Montserrat, Arial, sans-serif;'>Admin Login</h3>", unsafe_allow_html=True)
        st.markdown("")
        pw = st.text_input("Password", type="password")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Login", use_container_width=True):
                if pw == "admin123":
                    st.session_state["admin_authenticated"] = True
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

    col1, col2, col3 = st.columns([1, 3, 1])
    with col1:
        if st.button("← Back to Home"):
            go("home")
    with col3:
        if st.button("🔓 Logout"):
            st.session_state["admin_authenticated"] = False
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
            with st.expander("🔀 Field Order", expanded=False):
                df = pd.DataFrame([{"Field": k, "Order": v["order"]} for k, v in fields.items()])
                edited = st.data_editor(df, hide_index=True, use_container_width=True)

                if st.button("Apply Field Order"):
                    for _, r in edited.iterrows():
                        fields[r["Field"]]["order"] = int(r["Order"])
                    show_success("Field order updated successfully!")
                    st.rerun()

            with st.expander("✏️ Rename / Delete Field", expanded=False):
                field = st.selectbox("Select Field", ordered_fields(fields))
                new_name = st.text_input("Rename Field To", value=field)

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

            with st.expander("🛠️ Field Options", expanded=False):
                field_for_options = st.selectbox("Select Field to Edit Options", ordered_fields(fields), key="field_options_select")
                opts = fields[field_for_options]["options"]
                if opts and opts[0].get("type") == "text":
                    st.info("This is a text input field - users will enter values manually.")
                else:
                    x_codes = [o for o in opts if str(o.get("code", "")).upper() == "X"]
                    if x_codes:
                        st.warning(
                            "⚠️ An option in this field uses the code `X`, which the encoder reserves as the separator "
                            "between the base SKU and extras. The decoder now handles this correctly, but using a "
                            "different code (e.g. `NA`, `NF`) is recommended to avoid ambiguity."
                        )

                    df2 = normalize_option_df(opts)
                    edited_df = st.data_editor(
                        df2,
                        num_rows="dynamic",
                        hide_index=True,
                        use_container_width=True,
                        column_config={
                            "code": st.column_config.TextColumn("Code", help="SKU code segment"),
                            "name": st.column_config.TextColumn("Name", help="Display name"),
                            "tally_name": st.column_config.TextColumn("Tally Name", help="Abbreviation used in Item Name (e.g. FSV, A, ST)"),
                            "description": st.column_config.TextColumn("Description", help="Full text used in Item Description (e.g. Flat Sand Valve, Automatic)"),
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
                    "tally_name": st.column_config.TextColumn("Tally Name", help="Abbreviation used in Item Name (e.g. MS, PG, RV)"),
                    "description": st.column_config.TextColumn("Description", help="Full text used in Item Description (e.g. Moisture Separator)"),
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

            backup_data = json.dumps(st.session_state["sku_data"], indent=2)

            total_categories = len(st.session_state["sku_data"].get("inventory", {}))
            st.info(f"📁 **{total_categories}** categories in database")

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
                    import_data = json.load(uploaded_file)

                    if "inventory" in import_data:
                        num_categories = len(import_data["inventory"])
                        st.success(f"✅ Valid backup file detected: **{num_categories}** categories")

                        with st.expander("Preview categories"):
                            for cat_name in import_data["inventory"].keys():
                                cat_data = import_data["inventory"][cat_name]
                                num_fields = len(cat_data.get("fields", {}))
                                num_extras = len(cat_data.get("extras", []))
                                st.write(f"• **{cat_name}**: {num_fields} fields, {num_extras} extras")

                        import_mode = st.radio(
                            "Import mode:",
                            ["🔄 Replace all (overwrites existing data)", "➕ Merge (adds new, keeps existing)"],
                            key="import_mode"
                        )

                        st.warning("⚠️ **Warning:** This action cannot be undone. Make sure you have a backup!")

                        if st.button("🚀 Import Database", type="primary", use_container_width=True):
                            if "Replace" in import_mode:
                                st.session_state["sku_data"] = import_data
                                if GithubStorage().save(st.session_state["sku_data"]):
                                    show_success(f"✅ Database replaced successfully! Imported {num_categories} categories.")
                                    st.rerun()
                                else:
                                    show_error("Failed to save imported data to disk.")
                            else:
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
                    st.toast("✅ Saved to cloud!", icon="☁️")
                else:
                    show_error("Failed to save to cloud. Check your connection and credentials.")


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
        for idx, entry in enumerate(history):
            col1, col2, col3, col4 = st.columns([3, 2, 2, 1])

            with col1:
                st.markdown(f"### `{entry['sku']}`")
            with col2:
                st.markdown(f"**{entry['category']}**")
            with col3:
                st.caption(entry['timestamp'])
            with col4:
                copy_html = f"""
                <button onclick="navigator.clipboard.writeText('{entry['sku']}'); this.innerText='✓ Copied'"
                    style="background: #e8f4fd; border: 1px solid #1a73e8; border-radius: 6px;
                    padding: 5px 10px; cursor: pointer; color: #1a73e8; font-size: 12px;">
                    📋 Copy
                </button>
                """
                st.markdown(copy_html, unsafe_allow_html=True)

            if entry.get('description'):
                st.caption(f"↳ {entry['description']}")

            st.markdown("<hr style='margin: 10px 0; border: none; border-top: 1px solid #eee;'>", unsafe_allow_html=True)

        st.markdown("---")
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("🗑️ Clear All History", type="secondary"):
                GithubStorage().save_history([])
                st.session_state["sku_history"] = []
                if "sku_data" in st.session_state:
                    st.session_state["sku_data"]["sku_history"] = []
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

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("decoder_form", clear_on_submit=False):
            decode_input = st.text_input(
                "Enter SKU Code",
                placeholder="e.g., BL20MSF0",
                key="decoder_main_input",
                label_visibility="collapsed"
            )
            submitted = st.form_submit_button(
                "🔍 Decode", use_container_width=True, type="primary"
            )

        st.markdown("<p style='text-align: center; font-size: 12px; color: #888;'>Type or paste any SKU code, then press Enter or click Decode</p>", unsafe_allow_html=True)

    if decode_input:
        st.markdown("---")
        st.markdown(f"### Decoding: `{decode_input}`")

        inv = st.session_state["sku_data"]["inventory"]
        results = decode_sku(decode_input, inv)

        if results:
            best = results[0]
            st.success(f"✅ **Category Matched:** {best['category']}")

            st.markdown("#### Component Breakdown:")
            for part in best['parts']:
                col1, col2, col3 = st.columns([1, 1, 2])
                with col1:
                    st.markdown(f"**{part['field']}**")
                with col2:
                    st.code(part['code'])
                with col3:
                    st.markdown(part['name'])

            if best.get('extras'):
                st.markdown("#### Extras:")
                for extra in best['extras']:
                    col1, col2, col3 = st.columns([1, 1, 2])
                    with col1:
                        st.markdown("**Extra**")
                    with col2:
                        st.code(extra['code'])
                    with col3:
                        st.markdown(extra['name'])

            if best.get('remaining'):
                st.warning(f"⚠️ Unmatched portion: `{best['remaining']}`")

            if len(results) > 1:
                with st.expander(f"Other possible matches ({len(results) - 1})", expanded=False):
                    for other in results[1:]:
                        st.markdown(f"**{other['category']}** — {len(other['parts'])} fields matched, leftover `{other.get('remaining') or '—'}`")
        else:
            st.error("❌ Could not decode this SKU. It may not match any configured category.")
            st.info("💡 Make sure the SKU follows the correct format for one of your product categories.")


# ==================================================
# CATEGORY - ITEM PAIRS PAGE
# ==================================================
def category_items_page():
    """Category and Item pairs reference page."""
    with st.sidebar:
        render_sidebar_nav("category_items")

    st.markdown("<h2 style='text-align: center;'>📂 Category - Item Pairs</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #666;'>Reference table of product categories and their item groups</p>", unsafe_allow_html=True)

    st.markdown("---")

    json_path = os.path.join(os.path.dirname(__file__), "category_items.json")
    try:
        with open(json_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        st.error("category_items.json not found.")
        return

    df = pd.DataFrame(data)
    df.columns = ["Category", "Group / Under"]

    search = st.text_input("Search", placeholder="Filter by category or item...", label_visibility="collapsed")
    if search:
        mask = df.apply(lambda row: search.lower() in row.str.lower().str.cat(sep=" "), axis=1)
        df = df[mask]

    categories = df["Category"].unique().tolist()

    for cat in categories:
        cat_df = df[df["Category"] == cat]
        with st.expander(f"**{cat}** ({len(cat_df)} items)", expanded=True):
            for _, row in cat_df.iterrows():
                st.markdown(f"- {row['Group / Under']}")

    st.markdown("---")

    st.markdown(
        "<div style='text-align:center;color:#ccc;font-size:11px;font-family:Inter,sans-serif;letter-spacing:0.3px;'>"
        "Blastline India Pvt Ltd"
        "</div>",
        unsafe_allow_html=True
    )
