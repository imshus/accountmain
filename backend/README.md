# Accounts.ai backend

The server: reads Excel uploads, keeps the books (SQLite), computes every report, and talks to GPT-6 Luna.
It runs on its own; the web frontend and the Android app are clients that call its HTTP API (`/api/...`,
interactive docs at `/docs`).

## Set up (once)

```bash
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env            # macOS/Linux: cp .env.example .env  — then add OPENAI_API_KEY
```

## Run

| For | Command | Reachable from |
| --- | --- | --- |
| Development on this PC | `uvicorn app.main:app --reload --port 8000` | this PC only |
| The Android app / other computers | `start-server.bat` | your network (prints the line to put in `frontend/.env` before building the APK) |

There is no password: anyone on the same network who knows the address can open the books, so run
`start-server.bat` only on a network you trust (your office or home Wi-Fi). The first time, Windows Firewall asks whether Python may accept connections: allow **Private networks**
only. To reach the server from outside your network, host it (a VPS or office server) behind HTTPS
rather than opening a port on your router.

## Settings (`.env`)

| Variable | Default | |
| --- | --- | --- |
| `OPENAI_API_KEY` | — | Enables GPT-6 Luna in the chat |
| `ANTHROPIC_API_KEY` | — | Enables Claude as a second chat model |
| `CORS_ORIGINS` | dev server + Android app | Web pages allowed to call the API; add a hosted frontend's address |
| `DATA_DIR` | `backend/data` | Where `accounts.db` (all books and uploads) is stored; back this folder up |
| `MAX_UPLOAD_MB` | `25` | Upload size limit |

See `.env.example` for the model and effort settings.
