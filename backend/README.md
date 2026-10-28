# Accounts.ai backend

The server: reads Excel uploads, keeps the books (in a PostgreSQL database, e.g. Supabase), computes every report, and
talks to GPT-6 Luna. Nothing is stored on the server's disk: the books, uploads and chats are all in the database.
It runs on its own; the web frontend and the Android app are clients that call its HTTP API (`/api/...`,
interactive docs at `/docs`).

## Set up (once)

```bash
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env            # macOS/Linux: cp .env.example .env  — then add DATABASE_URL and OPENAI_API_KEY
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
| `DATABASE_URL` | — | Required: the database that holds everything. Supabase → Connect → **Session pooler** (port 5432), the URI with the database password; `sslmode=require` is added for you. Back-ups: Supabase → Database → Backups |
| `DATABASE_PASSWORD` | — | The database password, when it has characters such as `@ : / % # ? +`: leave `[YOUR-PASSWORD]` in `DATABASE_URL` and put the password here as it is |
| `DATABASE_SCHEMA` | `accountsai` | The schema the app's tables are made in (not `public`, which Supabase's web API exposes) |
| `OPENAI_API_KEY` | — | Enables GPT-6 Luna in the chat |
| `CORS_ORIGINS` | dev server + Android app | Web pages allowed to call the API; add a hosted frontend's address |
| `MAX_UPLOAD_MB` | `25` | Upload size limit |

See `.env.example` for the model and effort settings, and for the optional Supabase Storage (`SUPABASE_URL`,
`SUPABASE_SECRET_KEY`) and MongoDB (`MONGODB_URI`, `MONGODB_DB`) copies.

Use a separate database (another Supabase project, or a PostgreSQL on your PC) for development: the database is the
only copy of the books, so a backend on your PC pointed at the server's `DATABASE_URL` changes the real books.
