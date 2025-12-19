# Mental Wellness Streamlit App

Quick steps to run locally or deploy on Streamlit:

- Install dependencies:

```bash
python -m pip install -r requirements.txt
```

- IMPORTANT: remove or rotate any embedded API keys found in `app+chatbot+streamlit.py`.
  Prefer setting sensitive values as environment variables (e.g. `GROQ_API_KEY`).

- Run the app locally:

- Run the app locally:

```bash
python -m pip install -r requirements.txt
streamlit run streamlit_app.py
```

- Deploying to Streamlit Cloud (recommended for public hosting):

1. Push this repo to GitHub.
2. On Streamlit Cloud, create a new app and connect the GitHub repo.
3. In the app dashboard go to "Settings -> Secrets" and add `GROQ_API_KEY` (set the value to your GROQ key).
4. Remove any local `.env` containing secrets before pushing, and never commit secret files.

Example: to remove local `.env` (local/dev only):

```bash
rm -f .env
```

Streamlit will automatically set the entrypoint to `streamlit_app.py` (or use that command).

- For Streamlit Cloud or other hosting, set required secrets/env vars in the platform's UI and then use the same run command or set the repository's entrypoint to `streamlit_app.py`.
