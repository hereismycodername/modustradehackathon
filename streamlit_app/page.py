"""Streamlit page that frames the Django site served at ./django/."""
import html
import os

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Модус Трейд — обратная связь сотрудников", page_icon="💬",
                   layout="wide", initial_sidebar_state="collapsed")

password = html.escape(os.getenv("DEMO_PASSWORD", "ModusDemo2026!"))

# The bar and the site are pinned to the window, so Streamlit's own spacing
# around elements cannot cut or shift them.
st.markdown(
    f"""
    <style>
      :root {{ --modus-bar: 40px; }}
      @media (max-width: 760px) {{ :root {{ --modus-bar: 60px; }} }}
      header[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"], footer {{
        display: none !important;
      }}
      [data-testid="stMain"] {{ overflow: hidden !important; }}
      .modus-bar {{
        position: fixed; inset: 0 0 auto 0; z-index: 1000; box-sizing: border-box; height: var(--modus-bar);
        display: flex; flex-wrap: wrap; align-content: center; align-items: center; gap: 2px 14px; padding: 0 16px;
        overflow: hidden; background: #0F2A30; color: #DCE7E5; font: 13px/1.35 system-ui, sans-serif;
      }}
      .modus-bar strong {{ color: #fff; }}
      .modus-bar code {{ background: rgba(255,255,255,.14); color: #fff; padding: 1px 6px; border-radius: 4px; }}
      .modus-bar a {{ color: #7FD3C8; margin-left: auto; text-decoration: none; white-space: nowrap; }}
      .modus-bar a:hover {{ text-decoration: underline; }}
      .modus-bar .narrow {{ display: none; }}
      @media (max-width: 760px) {{
        .modus-bar .wide {{ display: none; }}
        .modus-bar .narrow {{ display: inline; }}
        .modus-bar a {{ margin-left: 0; }}
      }}
      iframe[src="django/"] {{
        position: fixed; left: 0; top: var(--modus-bar); z-index: 999; border: 0;
        width: 100vw; height: calc(100vh - var(--modus-bar)); height: calc(100dvh - var(--modus-bar));
      }}
    </style>
    <div class="modus-bar">
      <span><strong>Демо-стенд</strong> · <span class="wide">пароль для всех учётных записей:</span><span
        class="narrow">пароль:</span> <code>{password}</code><span class="wide"> · логины — на странице входа</span></span>
      <a href="django/" target="_blank" rel="noopener">Открыть на весь экран ↗</a>
    </div>
    """,
    unsafe_allow_html=True,
)

components.iframe("django/", height=600, scrolling=True)
