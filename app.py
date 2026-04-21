import os

import streamlit as st
from storage import GithubStorage
from pages import home, login, admin, history_page, decoder_page, category_items_page

# ==================================================
# SETUP
# ==================================================
st.set_page_config(
    page_title="Blastline SKU Configurator",
    layout="wide",
    initial_sidebar_state="collapsed"
)

_logo_path = os.path.join(os.path.dirname(__file__), "assets", "blastline_logo.png")
if os.path.exists(_logo_path):
    st.logo(_logo_path, size="large")

# Replace the subtle ">>" sidebar expand control with a prominent hamburger-menu button
st.markdown("""
    <style>
    [data-testid="stSidebarCollapsedControl"] {
        top: 0.9rem !important;
    }
    [data-testid="stSidebarCollapsedControl"] button {
        background: #1a5ed1 !important;
        border: none !important;
        border-radius: 10px !important;
        width: 44px !important;
        height: 40px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        box-shadow: 0 2px 8px rgba(26, 94, 209, 0.35) !important;
        transition: all 0.15s ease !important;
        padding: 0 !important;
    }
    [data-testid="stSidebarCollapsedControl"] button:hover {
        background: #1449a3 !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(26, 94, 209, 0.45) !important;
    }
    [data-testid="stSidebarCollapsedControl"] button svg,
    [data-testid="stSidebarCollapsedControl"] button [data-testid="stIconMaterial"],
    [data-testid="stSidebarCollapsedControl"] button span {
        display: none !important;
    }
    [data-testid="stSidebarCollapsedControl"] button::before {
        content: "";
        width: 20px;
        height: 14px;
        background-image: linear-gradient(#fff, #fff), linear-gradient(#fff, #fff), linear-gradient(#fff, #fff);
        background-size: 100% 2.5px;
        background-position: top left, center left, bottom left;
        background-repeat: no-repeat;
        border-radius: 2px;
    }
    </style>
""", unsafe_allow_html=True)

# ==================================================
# INIT
# ==================================================
if "page" not in st.session_state:
    st.session_state["page"] = "home"

# Reload the inventory from disk on every rerun so the app always reflects the
# latest admin edits from any device. Skip reload while on the admin page so
# unsaved edits in session_state aren't clobbered before the admin hits Save.
if st.session_state["page"] != "admin":
    st.session_state["sku_data"] = GithubStorage().load() or {"inventory": {}}
elif "sku_data" not in st.session_state:
    st.session_state["sku_data"] = GithubStorage().load() or {"inventory": {}}

if "extras_page" not in st.session_state:
    st.session_state["extras_page"] = 0

if "confirm_delete_cat" not in st.session_state:
    st.session_state["confirm_delete_cat"] = None

if "confirm_delete_field" not in st.session_state:
    st.session_state["confirm_delete_field"] = None

if st.session_state["page"] != "admin":
    st.session_state["sku_history"] = list(st.session_state["sku_data"].get("sku_history", []))
elif "sku_history" not in st.session_state:
    st.session_state["sku_history"] = list(st.session_state["sku_data"].get("sku_history", []))

if "admin_authenticated" not in st.session_state:
    st.session_state["admin_authenticated"] = False

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
elif st.session_state["page"] == "category_items":
    category_items_page()
