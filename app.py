"""Streamlit entry point with automatic official-report initialization."""

import os

from financial_intelligence_copilot.ui import run_app

run_app(auto_load_reports=os.getenv("FIC_AUTO_LOAD_REPORTS", "true").lower() == "true")
