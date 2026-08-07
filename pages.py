import streamlit as st
import pandas as pd
import json
import os
import io
import html
from streamlit_sortables import sort_items

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
    merge_editor_records,
    generate_full_matrix,
    generate_mapped_name_and_description,
    add_to_sku_history,
    compute_config_signature,
    get_short_code_prefix,
    lookup_short_code,
    HISTORY_CATEGORY_ORDER,
    format_history_timestamp,
    get_history_client_info,
    get_history_identity,
    get_history_specs_summary,
    is_custom_blast_machine,
    filter_sku_history,
    group_history_for_display,
    decode_sku,
    build_selection_from_decode,
    render_sidebar_nav,
    go,
    show_success,
    show_error,
    show_info,
    format_fitting_option,
    parse_fitting_parts,
    get_category_suffix,
    is_text_field,
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
                is_multiline = bool(opts[0].get("multiline"))
                st.markdown(f"<p class='config-label'>{f}</p>", unsafe_allow_html=True)
                if is_multiline:
                    txt_val = st.text_area(
                        f,
                        key=f"textfield_{cat}_{f}",
                        help=f"Enter {f}",
                        placeholder=f"Enter {f}",
                        label_visibility="collapsed",
                        height=120,
                    )
                else:
                    txt_val = st.text_input(
                        f,
                        key=f"textfield_{cat}_{f}",
                        help=f"Enter {f}",
                        placeholder=f"Enter {f}",
                        label_visibility="collapsed",
                    )
                if txt_val and txt_val.strip():
                    clean = txt_val.strip()
                    sel[f] = {"code": "", "name": clean, "tally_name": "", "description": clean, "is_text": True}
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
    base = sep.join([
        sel[k]["code"] for k in ordered_fields(fields)
        if sel.get(k) and sel[k]["code"] and not is_text_field(fields[k])
    ])
    extras_codes = "".join([c["code"] for c in chosen])
    sku = base + (sep + "X" if base and extras_codes else "") + extras_codes
    cat_suffix = get_category_suffix(cat)
    if sku and cat_suffix:
        sku += cat_suffix

    breakdown_items = []
    fittings_selected = False
    for k in ordered_fields(fields):
        if is_text_field(fields[k]):
            continue
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
                mapped_name, mapped_desc = generate_mapped_name_and_description(
                    sel, ordered_fields(fields), chosen, fittings_selected, fields=fields
                )
                escaped_name = mapped_name.replace("'", "\\'").replace("`", "") if mapped_name else ""
                escaped_desc = mapped_desc.replace("'", "\\'").replace("`", "") if mapped_desc else ""

                # Short code: read-only lookup against the saved registry. A code
                # is only *allocated* on Save; here we just show the existing one
                # (if this exact configuration was saved before) or a hint.
                config_signature = compute_config_signature(cat, sel, ordered_fields(fields), chosen)
                short_code_prefix = get_short_code_prefix(cat, sel, mf_name)
                existing_short_code = lookup_short_code(
                    config_signature, st.session_state.get("sku_data", {}).get("short_codes", {})
                )

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

                if existing_short_code:
                    short_code_html = (
                        '<div class="copy-card code-card" onclick="copyText('
                        + sq + existing_short_code + sq + ", " + sq + "code" + sq
                        + ')"><div class="text">' + existing_short_code
                        + '</div><div class="copy-btn"><span id="code-icon" class="material-symbols-outlined">content_copy</span>'
                        + '<p id="code-label">Click to Copy</p></div></div>'
                    )
                else:
                    short_code_html = (
                        '<div style="background:#fbf6ff;border:1.5px dashed #d9c7ee;border-radius:10px;'
                        'padding:12px 16px;color:#7a5aa6;font-size:13px;font-style:italic;">'
                        'Assigned when you Save to History'
                        '</div>'
                    )

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
                    .code-card {{ background: #fbf6ff; border: 1.5px solid #e2d3f5; }}
                    .code-card .text {{ font-size: 17px; font-weight: 700; color: #7a3ecb; letter-spacing: 0.5px; }}
                    .code-card .copy-btn {{ color: #7a3ecb; }}
                    .code-card .copy-btn p {{ color: #b08fe0; }}
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

                    <!-- Short Code -->
                    <div>
                        <div class="section-label">Short Code</div>
                        {short_code_html}
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
                card_height = 320 + (total_items * 30) + 90
                if cat == "Blast Machine":
                    card_height -= 88
                if mapped_desc and len(mapped_desc) > 80:
                    card_height += 30
                if mapped_name and len(mapped_name) > 80:
                    card_height += 30
                st.components.v1.html(output_html, height=card_height)

                sku_description = mapped_desc or " - ".join([item['name'] for item in all_breakdown_items])
                if st.button("💾 Save to History", key="save_history", use_container_width=False):
                    # Captured before saving: if set, this exact configuration
                    # was already saved and already owns a short code.
                    already_had_code = existing_short_code
                    machine_name = sel.get(mf_name, {}).get("name") if mf_name and sel.get(mf_name) else None
                    add_to_sku_history(
                        sku,
                        sku_description,
                        cat,
                        config=sel,
                        extras=chosen,
                        machine_code=selected_machine_code,
                        machine_name=machine_name,
                        mapped_name=mapped_name,
                        mapped_desc=mapped_desc,
                        breakdown_items=all_breakdown_items,
                        signature=config_signature,
                        prefix=short_code_prefix,
                    )
                    saved_code = lookup_short_code(
                        config_signature,
                        st.session_state.get("sku_data", {}).get("short_codes", {}),
                    )
                    if already_had_code:
                        # Idempotent: no new code was minted. Tell the user which
                        # existing code this combination already maps to.
                        st.warning(
                            f"⚠️ This exact configuration already has a short code: "
                            f"**{already_had_code}**. Reusing it — no new code was created."
                        )
                    else:
                        st.toast(f"Saved: {sku}" + (f"  •  {saved_code}" if saved_code else ""))
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
                ftype = c.selectbox("Type", ["Dropdown", "Text Input", "Multi-line Text"])
                if b.form_submit_button("Add") and name:
                    if name in fields:
                        show_error(f"Field '{name}' already exists!")
                    else:
                        if ftype == "Text Input":
                            new_options = [{"type": "text", "code": "", "name": ""}]
                        elif ftype == "Multi-line Text":
                            new_options = [{"type": "text", "multiline": True, "code": "", "name": ""}]
                        else:
                            new_options = []
                        fields[name] = {
                            "order": len(fields) + 1,
                            "options": new_options,
                            "machines": []
                        }
                        show_success(f"Field '{name}' added successfully!")
                        st.rerun()

        if fields:
            with st.expander("🔀 Field Order", expanded=False):
                st.caption("Drag fields to reorder them. The order from top to bottom is the order used in SKUs.")
                current_order = ordered_fields(fields)
                sorted_fields = sort_items(
                    current_order,
                    direction="vertical",
                    key=f"field_order_sort_{cat}",
                )
                if sorted_fields and sorted_fields != current_order:
                    for idx, fname in enumerate(sorted_fields, start=1):
                        if fname in fields:
                            fields[fname]["order"] = idx
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
                    is_multiline = bool(opts[0].get("multiline"))
                    new_multiline = st.toggle(
                        "Multi-line input (large text box)",
                        value=is_multiline,
                        key=f"multiline_toggle_{cat}_{field_for_options}",
                        help="Enable for long, multi-line text such as customization notes.",
                    )
                    if new_multiline != is_multiline:
                        if new_multiline:
                            opts[0]["multiline"] = True
                        else:
                            opts[0].pop("multiline", None)
                        show_success("Field updated. Remember to save changes.")
                        st.rerun()
                else:
                    x_codes = [o for o in opts if str(o.get("code", "")).upper() == "X"]
                    if x_codes:
                        st.warning(
                            "⚠️ An option in this field uses the code `X`, which the encoder reserves as the separator "
                            "between the base SKU and extras. The decoder now handles this correctly, but using a "
                            "different code (e.g. `NA`, `NF`) is recommended to avoid ambiguity."
                        )

                    # Snapshot the dataframe once per (cat, field) and reuse the
                    # SAME object on every rerun. st.data_editor resets its pending
                    # edits whenever the `data` arg's hash changes between reruns,
                    # so rebuilding df2 from the just-saved opts each run silently
                    # drops in-flight keystrokes. Holding a stable snapshot here is
                    # what makes typed input persist on the first try.
                    df_key = f"options_df_{cat}_{field_for_options}"
                    if df_key not in st.session_state:
                        st.session_state[df_key] = normalize_option_df(opts)
                    edited_df = st.data_editor(
                        st.session_state[df_key],
                        num_rows="dynamic",
                        hide_index=True,
                        use_container_width=True,
                        key=f"options_editor_{cat}_{field_for_options}",
                        column_config={
                            "code": st.column_config.TextColumn("Code", help="SKU code segment"),
                            "name": st.column_config.TextColumn("Name", help="Display name"),
                            "tally_name": st.column_config.TextColumn("Tally Name", help="Abbreviation used in Item Name (e.g. FSV, A, ST)"),
                            "description": st.column_config.TextColumn("Description", help="Full text used in Item Description (e.g. Flat Sand Valve, Automatic)"),
                            "order": st.column_config.NumberColumn("Order", help="Display order")
                        }
                    )
                    fields[field_for_options]["options"] = merge_editor_records(opts, edited_df.to_dict("records"))
        else:
            st.info("No fields configured yet. Add a field above to get started.")

    # ---------- EXTRAS MANAGEMENT ----------
    with tab2:
        cat_data = inv[cat]
        extras = cat_data.get("extras", [])

        with st.expander("🎁 Manage Extras / Add-ons", expanded=False):
            st.info(f"Extras will be displayed as a list (8 per page) in the configurator with pagination controls.")

            # Snapshot once per category for the same reason as Field Options
            # above — feeding a freshly-built DataFrame on every rerun makes
            # st.data_editor drop pending keystrokes when its `data` hash flips.
            extras_df_key = f"extras_df_{cat}"
            if extras_df_key not in st.session_state:
                st.session_state[extras_df_key] = normalize_extras_df(extras)
            edited_extras = st.data_editor(
                st.session_state[extras_df_key],
                num_rows="dynamic",
                hide_index=True,
                use_container_width=True,
                key=f"extras_editor_{cat}",
                column_config={
                    "code": st.column_config.TextColumn("Code", help="SKU code for this extra (will be appended to SKU)"),
                    "name": st.column_config.TextColumn("Name", help="Display name shown to users"),
                    "tally_name": st.column_config.TextColumn("Tally Name", help="Abbreviation used in Item Name (e.g. MS, PG, RV)"),
                    "description": st.column_config.TextColumn("Description", help="Full text used in Item Description (e.g. Moisture Separator)"),
                    "order": st.column_config.NumberColumn("Order", help="Display order (lower numbers appear first)")
                }
            )
            cat_data["extras"] = merge_editor_records(extras, edited_extras.to_dict("records"))

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
                    key=f"separator_input_{cat}"
                )

            with col2:
                st.markdown("##### Extras Selection Mode")
                extras_mode_setting = st.radio(
                    "Allow users to select:",
                    options=["Single", "Multiple"],
                    index=0 if settings.get("extras_mode", DEFAULT_EXTRAS_MODE) == "Single" else 1,
                    help="Single: Users can select only one extra (radio buttons)\nMultiple: Users can select multiple extras (checkboxes)",
                    key=f"extras_mode_input_{cat}"
                )

            settings["separator"] = separator
            settings["extras_mode"] = extras_mode_setting
            cat_data["settings"] = settings

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
                            matrix_df = generate_full_matrix(cat_data, cat)
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
                                # Drop cached editor dataframes so they re-init from the new inventory.
                                for k in [k for k in st.session_state.keys() if k.startswith("options_df_") or k.startswith("extras_df_")]:
                                    del st.session_state[k]
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

                                # Drop cached editor dataframes for any newly-added categories
                                # so they pick up imported options/extras on the next render.
                                for k in [k for k in st.session_state.keys() if k.startswith("options_df_") or k.startswith("extras_df_")]:
                                    del st.session_state[k]

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
                    key=f"machine_field_select_{cat}"
                )
                settings["machine_field"] = machine_field_name
                cat_data["settings"] = settings

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
                            has_machines_key = "machines" in fields[f]
                            current_machines = fields[f].get("machines", [])
                            default_on = (not has_machines_key) or selected_machine_code in current_machines
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
                                        has_machines_key = "machines" in opt
                                        opt_machines = opt.get("machines", [])
                                        default_on = (not has_machines_key) or selected_machine_code in opt_machines
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
                                has_machines_key = "machines" in e
                                e_machines = e.get("machines", [])
                                default_on = (not has_machines_key) or selected_machine_code in e_machines
                                label = f"{e['code']} - {e.get('name', '')}"
                                extras_checks[i] = st.checkbox(label, value=default_on, key=f"ev_{cat}_{selected_machine_code}_{i}")
                    else:
                        extras_checks = {}

                    all_machine_codes = [o["code"] for o in machine_opts if o.get("code")]

                    # Save logic: always store an explicit `machines` list so that
                    # "missing key" cleanly means "legacy / visible to all" and an
                    # empty list cleanly means "visible to no machine". Items that
                    # had no key (legacy data) get soft-migrated to the full code
                    # list on first interaction with this tab.
                    for f in other_fields:
                        if "machines" in fields[f]:
                            new_machines = set(fields[f]["machines"])
                        else:
                            new_machines = set(all_machine_codes)
                        if field_checks.get(f, True):
                            new_machines.add(selected_machine_code)
                        else:
                            new_machines.discard(selected_machine_code)
                        fields[f]["machines"] = sorted(new_machines)

                    for f, opts_map in option_checks.items():
                        opts = fields[f]["options"]
                        for i, checked in opts_map.items():
                            opt = opts[i]
                            if "machines" in opt:
                                new_machines = set(opt["machines"])
                            else:
                                new_machines = set(all_machine_codes)
                            if checked:
                                new_machines.add(selected_machine_code)
                            else:
                                new_machines.discard(selected_machine_code)
                            opt["machines"] = sorted(new_machines)

                    for i, checked in extras_checks.items():
                        e = extras[i]
                        if "machines" in e:
                            new_machines = set(e["machines"])
                        else:
                            new_machines = set(all_machine_codes)
                        if checked:
                            new_machines.add(selected_machine_code)
                        else:
                            new_machines.discard(selected_machine_code)
                        e["machines"] = sorted(new_machines)

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
def _render_history_entry_detail(entry, inventory):
    """Show the full configuration saved with a history entry."""
    cat = entry.get("category")
    config = entry.get("config") or {}
    extras = entry.get("extras") or []
    breakdown = entry.get("breakdown_items") or []
    mapped_name = entry.get("mapped_name")
    mapped_desc = entry.get("description")

    if not config and cat in inventory:
        decode_results = decode_sku(entry.get("sku", ""), inventory)
        cat_match = next((r for r in decode_results if r.get("category") == cat), None)
        if not cat_match and decode_results:
            cat_match = decode_results[0]
        if cat_match:
            cat_data = inventory.get(cat_match["category"], inventory.get(cat, {}))
            if cat_data:
                config, field_order, extras, fittings_selected = build_selection_from_decode(
                    cat_match, cat_data
                )
                if not breakdown:
                    breakdown = [
                        {"code": p["code"], "name": p.get("name", ""), "field": p["field"]}
                        for p in cat_match.get("parts", [])
                    ]
                    breakdown += [
                        {"code": e["code"], "name": e.get("name", "")}
                        for e in cat_match.get("extras", [])
                    ]
                if not mapped_name or not mapped_desc:
                    mapped_name, mapped_desc = generate_mapped_name_and_description(
                        config, field_order, extras, fittings_selected, fields=cat_data.get("fields")
                    )

    sku_escaped = html.escape(entry.get("sku", ""))
    copy_html = f"""
    <button onclick="navigator.clipboard.writeText('{sku_escaped}'); this.innerText='✓ Copied'"
        style="background: #e8f4fd; border: 1px solid #1a73e8; border-radius: 6px;
        padding: 7px 14px; cursor: pointer; color: #1a73e8; font-size: 15px; margin-bottom: 12px;">
        📋 Copy SKU
    </button>
    """
    st.markdown(copy_html, unsafe_allow_html=True)

    short_code = entry.get("short_code")
    if short_code:
        sc_escaped = html.escape(str(short_code))
        st.markdown(
            f"<div style='display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:12px;'>"
            f"<div style='display:inline-block;background:#fbf6ff;border:1.5px solid #e2d3f5;"
            f"border-radius:8px;padding:8px 14px;'>"
            f"<span style='color:#888;font-weight:600;font-size:13px;'>Short Code</span> "
            f"<span style='color:#7a3ecb;font-weight:700;font-size:16px;'>{sc_escaped}</span>"
            f"</div>"
            f"<button onclick=\"navigator.clipboard.writeText('{sc_escaped}'); this.innerText='✓ Copied'\""
            f" style='background:#fbf6ff;border:1px solid #c4a8e8;border-radius:6px;"
            f"padding:7px 12px;cursor:pointer;color:#7a3ecb;font-size:14px;'>"
            f"Copy Short Code</button>"
            f"</div>",
            unsafe_allow_html=True,
        )

    client_name, client_abbr = get_history_client_info(entry)
    if client_name or client_abbr:
        client_label = client_name or ""
        if client_name and client_abbr:
            client_label = f"{client_name} ({client_abbr})"
        elif client_abbr:
            client_label = client_abbr
        st.markdown(
            f"<div style='background:#eef6ff;border:1px solid #c5daf5;border-radius:8px;"
            f"padding:10px 14px;margin-bottom:12px;'>"
            f"<span style='color:#5a7aa0;font-weight:600;font-size:13px;'>Client</span>"
            f"<div style='color:#1a4a7a;font-weight:700;font-size:17px;'>{html.escape(client_label)}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    date_str, time_str = format_history_timestamp(entry.get("timestamp"))
    if date_str or time_str:
        st.markdown(
            f"<div style='display:flex;gap:24px;margin-bottom:14px;font-size:15px;'>"
            f"<div><span style='color:#888;font-weight:600;'>Date</span>"
            f"<div style='color:#222;font-weight:600;'>{html.escape(date_str)}</div></div>"
            f"<div><span style='color:#888;font-weight:600;'>Time</span>"
            f"<div style='color:#222;font-weight:600;'>{html.escape(time_str)} IST</div></div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    if mapped_name and cat != "Blast Machine":
        st.markdown("**Item Name**")
        st.markdown(f"<div style='background:#f0faf2;border:1px solid #c8e6cc;border-radius:8px;padding:10px 14px;font-weight:600;font-size:16px;color:#1b6e2a;'>{html.escape(mapped_name)}</div>", unsafe_allow_html=True)

    if mapped_desc:
        st.markdown("**Item Description**")
        st.markdown(f"<div style='background:#faf8f0;border:1px solid #e6dfc8;border-radius:8px;padding:10px 14px;font-size:15px;color:#5a4e2b;'>{html.escape(mapped_desc)}</div>", unsafe_allow_html=True)

    if config:
        st.markdown("**Configuration**")
        for field_name, field_val in config.items():
            code = field_val.get("code", "")
            name = field_val.get("name", "")
            is_text = field_val.get("is_text") or (not code and name)
            if is_text:
                st.markdown(
                    f"<div style='padding:5px 0;font-size:15px;'>"
                    f"<span style='color:#888;font-weight:600;'>{html.escape(field_name)}</span>"
                    f"<div style='margin-top:3px;color:#444;white-space:pre-wrap;background:#f8f9fb;"
                    f"border:1px solid #e8eaed;border-radius:6px;padding:8px 12px;'>{html.escape(name)}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<div style='display:flex;gap:10px;align-items:center;padding:5px 0;font-size:15px;'>"
                    f"<span style='min-width:130px;color:#888;font-weight:600;'>{html.escape(field_name)}</span>"
                    f"<span style='background:#eef2f7;color:#3366aa;padding:2px 8px;border-radius:4px;font-family:monospace;font-size:14px;'>{html.escape(str(code))}</span>"
                    f"<span style='color:#444;'>{html.escape(name)}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    if extras:
        st.markdown("**Extras**")
        for extra in extras:
            st.markdown(
                f"<div style='display:flex;gap:10px;align-items:center;padding:5px 0;font-size:15px;'>"
                f"<span style='background:#eef2f7;color:#3366aa;padding:2px 8px;border-radius:4px;font-family:monospace;font-size:14px;'>{html.escape(str(extra.get('code', '')))}</span>"
                f"<span style='color:#444;'>{html.escape(extra.get('name', ''))}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

    if breakdown:
        st.markdown("**SKU Breakdown**")
        for item in breakdown:
            field_label = item.get("field")
            prefix = f"{html.escape(field_label)}: " if field_label else ""
            st.markdown(
                f"<div style='display:flex;gap:8px;align-items:center;padding:4px 0;font-size:15px;color:#555;'>"
                f"<span style='background:#eef2f7;color:#3366aa;padding:2px 8px;border-radius:4px;font-family:monospace;font-size:14px;'>{html.escape(str(item.get('code', '')))}</span>"
                f"<span>{prefix}{html.escape(item.get('name', ''))}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

    if not config and not breakdown:
        st.caption("Configuration snapshot not available for this entry.")


def _history_row_label(entry, inventory):
    """Dense one-line expander label: identity · short · sku · specs · date."""
    identity = get_history_identity(entry, inventory)
    short_code = entry.get("short_code") or "—"
    sku = entry.get("sku") or ""
    sku_short = sku if len(sku) <= 28 else sku[:25] + "…"
    specs = get_history_specs_summary(entry)
    date_str, _time_str = format_history_timestamp(entry.get("timestamp"))

    parts = [identity, str(short_code), sku_short]
    if specs:
        parts.append(specs)
    if date_str:
        parts.append(date_str)
    return "   ·   ".join(parts)


def _history_filter_options(history):
    """Build (label, key) filter options present in history."""
    options = [("All", "all"), ("Custom (CBM)", "cbm")]
    cats_present = {e.get("category") or "Other" for e in history}
    for cat in HISTORY_CATEGORY_ORDER:
        if cat in cats_present:
            options.append((cat, cat))
    for cat in sorted(cats_present):
        if cat not in HISTORY_CATEGORY_ORDER:
            options.append((cat, cat))
    return options


def _render_history_list(entries, inventory, group_by):
    """Render filtered history as dense expandable rows, optionally grouped."""
    sections = group_history_for_display(entries, inventory, group_by=group_by)
    if not sections:
        st.info("No SKUs match your search or filter.")
        return

    for section_title, section_entries in sections:
        if group_by != "recent":
            st.markdown(
                f"<div style='margin:14px 0 6px 0;font-size:15px;font-weight:700;color:#444;'>"
                f"{html.escape(section_title)}"
                f"<span style='color:#888;font-weight:600;font-size:13px;'>"
                f"  ·  {len(section_entries)} SKU{'s' if len(section_entries) != 1 else ''}"
                f"</span></div>",
                unsafe_allow_html=True,
            )
        for i, entry in enumerate(section_entries):
            sku_key = entry.get("sku") or f"row_{i}"
            label = _history_row_label(entry, inventory)
            with st.expander(label, expanded=False):
                _render_history_entry_detail(entry, inventory)


def _build_codes_excel(registry):
    """Build an .xlsx (bytes) of all saved short codes from the registry."""
    rows = []
    for rec in registry.values():
        rows.append({
            "Short Code": rec.get("code", ""),
            "SKU": rec.get("sku", ""),
            "Category": rec.get("category", ""),
            "Item Name": rec.get("mapped_name", "") or "",
            "Description": rec.get("mapped_desc", "") or rec.get("description", "") or "",
            "Created At": rec.get("created_at", ""),
        })

    df = pd.DataFrame(rows, columns=[
        "Short Code", "SKU", "Category", "Item Name", "Description", "Created At",
    ])
    # Sort by prefix then numeric sequence so codes read naturally (BL-1, BL-2, ...).
    if not df.empty:
        parts = df["Short Code"].astype(str).str.rsplit("-", n=1, expand=True)
        df["_prefix"] = parts[0]
        df["_seq"] = pd.to_numeric(parts[1], errors="coerce") if parts.shape[1] > 1 else 0
        df = df.sort_values(["_prefix", "_seq"]).drop(columns=["_prefix", "_seq"])

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Saved Codes")
    return buffer.getvalue()


def history_page():
    """SKU History: searchable list with client-first identity for custom machines."""
    with st.sidebar:
        render_sidebar_nav("history")

    st.markdown("""
        <style>
        div[data-testid="stExpander"] details summary p {
            font-weight: 600;
            font-size: 14px !important;
            line-height: 1.35;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("<h2 style='text-align: center;'>📋 SKU History</h2>", unsafe_allow_html=True)

    history = st.session_state.get("sku_history", [])
    inventory = st.session_state.get("sku_data", {}).get("inventory", {})
    registry = st.session_state.get("sku_data", {}).get("short_codes", {})

    # Toolbar: download + clear
    tool_l, tool_r = st.columns([3, 1])
    with tool_l:
        if registry:
            excel_bytes = _build_codes_excel(registry)
            st.download_button(
                f"⬇️ Download Saved Codes ({len(registry)}) as Excel",
                data=excel_bytes,
                file_name="blastline_saved_codes.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
    with tool_r:
        if history and st.button("🗑️ Clear All", type="secondary", use_container_width=True):
            GithubStorage().save_history([])
            st.session_state["sku_history"] = []
            if "sku_data" in st.session_state:
                st.session_state["sku_data"]["sku_history"] = []
            st.session_state.pop("history_cat", None)
            st.session_state.pop("history_machine", None)
            st.rerun()

    if not history:
        st.markdown("---")
        st.info("📭 No SKU history yet. Generate some SKUs and click **Save to History** to see them here!")
        if st.button("🏠 Go to SKU Generator"):
            go("home")
        return

    st.markdown("---")

    filter_options = _history_filter_options(history)
    filter_labels = [label for label, _key in filter_options]
    label_to_key = {label: key for label, key in filter_options}

    search_col, filter_col, group_col = st.columns([3, 2, 2])
    with search_col:
        query = st.text_input(
            "Search",
            placeholder="Client, abbr, short code, SKU, machine…",
            label_visibility="collapsed",
            key="history_search",
        )
    with filter_col:
        filter_label = st.selectbox(
            "Filter",
            filter_labels,
            index=0,
            key="history_filter_label",
        )
    with group_col:
        group_label = st.selectbox(
            "Group by",
            ["Recent", "Client", "Machine"],
            index=0,
            key="history_group_by",
        )

    filter_key = label_to_key.get(filter_label, "all")
    group_by = {"Recent": "recent", "Client": "client", "Machine": "machine"}[group_label]

    filtered = filter_sku_history(history, inventory, query=query, filter_key=filter_key)

    cbm_count = sum(1 for e in history if is_custom_blast_machine(e, inventory))
    st.caption(
        f"Showing **{len(filtered)}** of **{len(history)}** saved SKUs"
        + (f"  ·  {cbm_count} custom (CBM)" if cbm_count else "")
    )

    _render_history_list(filtered, inventory, group_by)

# ==================================================
# DECODER PAGE
# ==================================================
def _normalize_short_code_text(text):
    """Uppercase and pad numeric suffix to at least 3 digits (BL-3 -> BL-003)."""
    t = str(text).strip().upper()
    if "-" not in t:
        return t
    prefix, _, num = t.rpartition("-")
    if num.isdigit():
        return f"{prefix}-{int(num):03d}"
    return t


def _find_registry_by_code(registry, text):
    """Return the saved short-code record matching `text` (case-insensitive), or None."""
    if not registry or not text:
        return None
    t = str(text).strip().upper()
    t_padded = _normalize_short_code_text(t)
    for rec in registry.values():
        code = str(rec.get("code", "")).strip().upper()
        if code == t or code == t_padded or _normalize_short_code_text(code) == t_padded:
            return rec
    return None


def _find_code_for_sku(registry, sku):
    """Return the short code assigned to a full SKU string, or None."""
    if not registry or not sku:
        return None
    s = str(sku).strip().upper()
    for rec in registry.values():
        if str(rec.get("sku", "")).strip().upper() == s:
            return rec.get("code")
    return None


def _render_short_code_result(rec):
    """Render a decoded short-code record using its stored snapshot."""
    st.success(f"✅ **Short Code:** {rec.get('code', '')}  —  {rec.get('category', '')}")

    full_sku = rec.get("sku", "")
    if full_sku:
        st.markdown("**Full SKU**")
        st.markdown(
            f'<div style="background:#f0f6ff;border:1.5px solid #d0e3ff;border-radius:8px;'
            f'padding:12px 16px;font-weight:700;color:#1a5ed1;">{html.escape(full_sku)}</div>',
            unsafe_allow_html=True,
        )

    item_name = rec.get("mapped_name")
    item_desc = rec.get("mapped_desc") or rec.get("description")
    if item_name:
        st.markdown("**Item Name**")
        st.markdown(
            f'<div style="background:#f0faf2;border:1.5px solid #c8e6cc;border-radius:8px;'
            f'padding:12px 16px;font-weight:600;color:#1b6e2a;">{html.escape(item_name)}</div>',
            unsafe_allow_html=True,
        )
    if item_desc:
        st.markdown("**Item Description**")
        st.markdown(
            f'<div style="background:#faf8f0;border:1.5px solid #e6dfc8;border-radius:8px;'
            f'padding:12px 16px;color:#5a4e2b;">{html.escape(item_desc)}</div>',
            unsafe_allow_html=True,
        )

    breakdown = rec.get("breakdown_items") or []
    if breakdown:
        st.markdown("#### Component Breakdown:")
        for part in breakdown:
            c1, c2, c3 = st.columns([1, 1, 2])
            with c1:
                st.markdown(f"**{part.get('field', '')}**")
            with c2:
                st.code(part.get("code", ""))
            with c3:
                st.markdown(part.get("name", ""))


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
        registry = st.session_state.get("sku_data", {}).get("short_codes", {})

        # A short code (e.g. "CBM-12") is resolved by a direct registry lookup,
        # not by the character-parsing decoder.
        code_rec = _find_registry_by_code(registry, decode_input)
        if code_rec:
            _render_short_code_result(code_rec)
            return

        results = decode_sku(decode_input, inv)

        if results:
            best = results[0]
            st.success(f"✅ **Category Matched:** {best['category']}")

            matched_code = _find_code_for_sku(registry, decode_input)
            if matched_code:
                st.info(f"🔖 Short Code: **{matched_code}**")

            cat_data = inv[best["category"]]
            sel, field_order, chosen, fittings_selected = build_selection_from_decode(best, cat_data)
            item_name, item_desc = generate_mapped_name_and_description(
                sel, field_order, chosen, fittings_selected, fields=cat_data["fields"]
            )

            if item_name or item_desc:
                st.markdown("#### Product Output")
                if item_name:
                    st.markdown("**Item Name**")
                    st.markdown(
                        f'<div style="background:#f0faf2;border:1.5px solid #c8e6cc;border-radius:8px;'
                        f'padding:12px 16px;font-weight:600;color:#1b6e2a;">{html.escape(item_name)}</div>',
                        unsafe_allow_html=True,
                    )
                if item_desc:
                    st.markdown("**Item Description**")
                    st.markdown(
                        f'<div style="background:#faf8f0;border:1.5px solid #e6dfc8;border-radius:8px;'
                        f'padding:12px 16px;color:#5a4e2b;">{html.escape(item_desc)}</div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.info(
                    "Item name and description could not be built — check that Tally Name and "
                    "Description mappings are configured in Settings for this category."
                )

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
