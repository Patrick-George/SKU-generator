import streamlit as st
from storage import GithubStorage
from pages import home, login, admin, history_page, decoder_page, scanner_page, category_items_page

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
elif st.session_state["page"] == "scanner":
    scanner_page()
elif st.session_state["page"] == "category_items":
    category_items_page()
