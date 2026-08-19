# Flight Hunter

Backend scaffold for searching, verifying, tracking, and notifying about flight offers.

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[test]"
uvicorn app.main:app --reload
```

The health endpoint is available at `http://127.0.0.1:8000/health`.
