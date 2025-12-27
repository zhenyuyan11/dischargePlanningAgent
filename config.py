# config.py
# Configuration and environment variable loading

import os
from dotenv import load_dotenv

# Load environment variables from .env file (for local development)
load_dotenv()

# OpenAI Configuration
# Try Streamlit secrets first (for deployed app), then fall back to .env
try:
    import streamlit as st
    OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY"))
except (ImportError, FileNotFoundError):
    # Streamlit not available or secrets file not found - use .env
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# PDF Export Configuration
HOSPITAL_NAME = "Medical Center"  # Customize as needed
PDF_HEADER_COLOR = "#003366"  # Professional blue
PDF_EMERGENCY_NUMBER = "911"

# Validate that required environment variables are set
def validate_config():
    """Check if required configuration is present"""
    if not OPENAI_API_KEY or OPENAI_API_KEY == "your-openai-api-key-here":
        return False, "OPENAI_API_KEY not configured in .env file"
    return True, "Configuration valid"
