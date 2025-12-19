"""
Streamlit entrypoint that runs the existing app script.

This loads environment variables from a local `.env` (if present)
and executes `app+chatbot+streamlit.py` so you can deploy using
`streamlit run streamlit_app.py` without renaming files.

IMPORTANT: remove any hard-coded API keys or move them to environment
variables before publishing.
"""
import os
from dotenv import load_dotenv
import runpy

# Load .env from repository root when present (useful for local testing)
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
	load_dotenv(env_path)

runpy.run_path("app+chatbot+streamlit.py", run_name="__main__")
