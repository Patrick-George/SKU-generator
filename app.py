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
