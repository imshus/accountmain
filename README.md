# Accounts.ai

Upload an Excel sheet, get checked accounting summaries and reports, keep proper double-entry books (vouchers,
ledgers, GST returns, bank reconciliation), and chat with your data in plain English using GPT-6 Luna (or Claude).

```
Accounts.ai/
├── backend/        The server: Python API (FastAPI, pandas, NumPy, SQLAlchemy/SQLite, GPT-6 Luna / Claude)
├── frontend/       The client: React + TypeScript web app, also packaged as the Android app (frontend/android)
├── sample-data/    sample_ledger.xlsx, sample_sales_register.xlsx, sample_purchase_register.xlsx
└── reports/        research reports behind the accuracy and accounting design
```

The backend and frontend are separate programs that talk only over HTTP (`/api/...`). The backend holds
all data and does all the calculating; it can run on this PC or a server. The frontend runs in a browser
or as the Android app and connects to whichever backend you point it at. Each folder has its own
README with its run and build steps.

## What it does

| Screen | Features |
| --- | --- |
| **Chat** (home) | Opens like ChatGPT: a full-window chat with a sidebar of conversations (new chat, search chats, delete), the question in the middle and the message box under it (on phones: menu and new-chat icons on top, the box at the bottom). Attach Excel/CSV files with **+** or by dragging them in; they upload together and appear as file cards labelled with what the app found (**Sales register**, **Purchase register**, **Bank statement**, **Ledger**), with the evidence (voucher-type values such as S/P, customer vs supplier columns, output vs input GST, invoice-number patterns, file names). With a sales and a purchase register (in one go or one after the other), the first answer analyses **both together**: totals, margin, GST payable after input credit by head, month by month, items bought vs sold, common parties and things to check. Follow-up questions use both. Answers stream with live steps and can be stopped, copied or regenerated. **+ → Your files and company books** opens earlier uploads, sales + purchase sets and company books. |
| **Gold** (jewellers) | Every party and the stock carry a **fine-weight** account beside the rupee one (fine = net × tunch ÷ 100; net = gross − (diamond + stone ct) × 0.2). **Jewellery bill**: items with gross, diamond/stone carats, tunch, diamond/stone value and labour per gram, each settled **by weight (Wt)** (the customer owes the fine gold) or **in rupees (Rs)** at a metal rate. **Gold in / out**: metal received from or given to a party. **Rate cut**: converts metal owed into rupees at an agreed rate, as a Sales (or Purchase) voucher with GST. Reports: **who owes metal** (party balances, stock, net metal position, optional value at a rate), **party metal account** (running balance), **stock in grams** by karat and by item. Jewellery registers (Gr.Wt, Dia.Wt, Net.Wt, Tunch, Fine, Wt/Rs columns) import as one voucher per invoice, with every row's net and fine re-computed and differences reported. |
| **Company books** (double entry) | Create a company (name, GSTIN, financial-year start); Tally's 28 groups and the usual ledgers are created. **New voucher**: GST invoice (Sales, Purchase, Credit Note, Debit Note; CGST+SGST or IGST from the party's state, round-off to the rupee), receipt/payment against pending bills (oldest-first allocation, TDS on payments, the rest on account), any voucher line by line with a live Dr/Cr difference. **Vouchers**: search, filter, open lines and bill-wise allocations, cancel. **Reports**: trial balance, P&L, balance sheet, day book, ledger, cash/bank book, receivables and payables bill-wise with ageing, GSTR-1 (B2B, B2CL, B2CS, credit notes, document series), GSTR-3B (with Rule 88A credit use), bank reconciliation. **Ledgers** with Dr/Cr openings, GSTIN and credit days. **Import** sales/purchase registers as vouchers (re-importing skips rows already posted) and bank statements for reconciliation. **Audit trail** that cannot be edited. **Lock** the books up to a date. |
| **Upload** | `.xlsx`, `.xlsm`, `.xls`, `.csv`; every sheet is read. Choose **One file** or **Sales + Purchases** (a sales register and a purchase register, new files or ones already uploaded) |
| **Sales + Purchases** | **Comparison** (totals and GST side by side, margin, month by month, columns in both files such as quantity/weight, item-wise purchased vs sold, parties who are both customer and supplier), **GST** (output vs input credit, cash payable per head in the Rule 88A order, data checks for both registers), **Gross profit** (trading account with opening/closing stock, GST excluded), **Customers & suppliers**, **Party ledger** (sales Dr, purchases Cr, running balance), **Ageing** (receivables and payables), **Day book**, **Analyse** (also on both registers as one table, e.g. taxable value by month, sales vs purchases side by side), **Ask AI** across both registers, **Sheets in this set** (mark sheets as sales/purchases) |
| **Overview** | Data checks, totals, month-by-month, top categories, column statistics, data preview, notes for the AI |
| **Analyse** | No SQL needed: pick what to show (total, number of rows, average, lowest, highest, number of different), group by up to two columns (dates by month, quarter, financial year or year), add conditions, sort and keep the top N; see a bar chart and a table with totals, or spread the second column across (a pivot table); download CSV. Groups beyond the top N become one "All others" row so the column still adds up, and every result proves its groups add up to the overall total. |
| **Ask AI** | Ask GPT-6 Luna or Claude; follow-up questions; the AI uses the same Analyse engine (or SQL when needed), and every answer shows its analyses, queries, calculations and formula checks plus a verification badge. "Open in Analyse" loads what the AI did. A read-only SQL box is under **Advanced: SQL**. |
| **Reports** | Ledger with running Dr/Cr balance, day book, trial balance (editable account groups), profit & loss (with opening/closing stock), balance sheet, receivables/payables ageing, GST summary with data checks, net GST payable (Rule 88A credit order). CSV download. |
| **Entries** | Browse and search entries, add an entry, delete an entry. All totals and reports are recalculated. |
| **Calculator** | Exact decimal calculator (add, subtract, multiply, divide, %), column formulas such as `credit - debit` or `taxable_value + cgst + sgst`, "does this formula match every row?" checks, save a result as a new column |

## How accuracy is enforced

No AI model can promise 100% on its own, so the app is built so that **numbers come from code, not from the model**,
and every number can be traced and checked (see `reports/Accurate AI accounting features.md` for the research):

1. **Import is checked, not silent.** Header rows under titles are found; Indian formats are read (1,23,456.78,
   `(500)`, `500-`, `-`, ₹/Rs./INR, `1,200.00 Dr/Cr`, Dr/Cr stored only in Tally's Excel number formats, DD/MM/YYYY
   with one format per column, Excel date serials). Every unreadable cell is reported with its row number, duplicates
   are flagged, formulas with no saved value are flagged, and each column is reconciled with the file's own Total row.
2. **Exact arithmetic.** Reports convert money to whole paise (integers) before adding, so totals and running
   balances are exact. Sums use `math.fsum`; the calculator uses `Decimal`. Each report shows its proof
   (opening + debits − credits = closing, Dr total = Cr total, assets = liabilities + capital, P&L cross-check).
3. **The AI only plans; tools compute.** The model gets a data dictionary (column meanings, value ranges, exact
   category values, import notes, your notes) and four tools: `analyse` (totals and breakdowns, no SQL),
   `run_sql` (read-only, limited to the upload's tables), `calculate` (exact decimal arithmetic) and
   `check_formula` (tests a formula on every row).
   Queries run on **DuckDB, with pandas around it**: pandas loads and cleans each sheet, and DuckDB stores
   numbers as exact fixed-point decimals (2 places for rupees, 3 for grams) before adding them up. Ordinary
   floating point would give 452.5570000000002 g where the exact total is 452.557 g. Each query runs in a
   private, locked-down DuckDB with file and network access switched off, single SELECT statements only, and
   a time limit.
4. **Every figure is verified.** After each answer, every number in it is compared with the tool results. If one
   doesn't match, and isn't an exact sum, difference or percentage of checked figures, the model is asked to
   recompute it once (at medium effort); anything still unverified is flagged to you.

## Speed

- **Answers stream.** Ask AI shows each step as it happens ("Analysed: Total Fine by Party Name; top 3") and
  writes the answer word by word; the first feedback appears within a second.
- **Fast first pass.** The first answer uses low reasoning effort (about twice as fast as high on this app's
  questions); accuracy comes from the tools and the figure check, and a failed check is redone at medium effort.
- **Instant repeats.** The same question on unchanged data is answered from memory in milliseconds; any edit to
  a sheet changes the data's fingerprint, so a stale answer is never reused. Only checked answers are kept.
- **Prepared data.** Each sheet is read and prepared for DuckDB once and kept in memory until it changes, and
  every request gets a fresh private connection to one shared, locked-down DuckDB, so Analyse, SQL and the
  AI's tools answer in milliseconds. Analyse updates by itself as you change options.
- **Files upload together**, and the sales vs purchases comparison given to the model is computed once (about
  0.1 s) and remembered until the data changes, so a two-file explanation needs no tool calls: the first words
  appear about 4 s after pressing send (upload included) on the sample registers.
- **The chat opens first.** Only the chat is in the main JavaScript bundle; the other screens load separately and
  are fetched in the background a moment later, so the app starts faster (notably on phones).
- OpenAI's prompt cache serves the long instructions (about 3,900 tokens) on repeat calls; each table set
  has a stable cache key so this keeps working.

## Run it locally

You need **Python 3.9 or newer** (3.11+ recommended) and Node.js 20+. On Python 3.9 and 3.10, `pip install -r
requirements.txt` picks the newest library versions that still support them (pandas 2.3, OpenAI SDK 2.x,
DuckDB 1.4); every report and figure has been checked to come out identical to Python 3.11+.
Use two terminals. (For the phone app, see **Android app** below.)

**Backend** (http://127.0.0.1:8000, API docs at `/docs`):

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env            # macOS/Linux: cp .env.example .env  — then add your OPENAI_API_KEY
uvicorn app.main:app --reload --port 8000
```

**Frontend** (http://localhost:5173):

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and drop `sample-data/sample_sales_register.xlsx` and
`sample-data/sample_purchase_register.xlsx` into the chat (they include a 12% rate used after 22 Sept 2025, a tax
amount that doesn't match its rate, and a mistyped GSTIN, so you can see the checks work). Without an API key
everything works except the chat. The chat uses `LLM_PROVIDER` (GPT-6 Luna by default); there is no model picker
on screen.

## Hosting on a server (Hostinger VPS, AWS EC2, any Linux VPS) with Docker

This is the easiest way: Docker builds the backend with the right Python (3.12) and serves the web app
and its API on one address, so the server's own Python version does not matter. Hostinger **shared**
web hosting cannot run the Python backend; use a Hostinger **VPS** (the "Ubuntu 24.04 with Docker"
template already has Docker; on another VPS install it with `curl -fsSL https://get.docker.com | sh`).

```bash
git clone https://github.com/imshus/accountmain.git && cd accountmain
cp backend/.env.example backend/.env    # then edit backend/.env and set OPENAI_API_KEY
docker compose up -d --build            # first build takes a few minutes
```

Open `http://<server-ip>` in a browser; in the Android app enter `http://<server-ip>` as the server.
Allow port 80 in the VPS firewall (Hostinger hPanel → VPS → Firewall, or `ufw allow 80`).

- Update after a new push: `git pull && docker compose up -d --build`
- Logs: `docker compose logs -f backend`
- The books live in the `accounts-data` Docker volume (kept across updates). Back it up with
  `docker compose cp backend:/data ./backup`.
- **The app has no login.** On a public server anyone who knows the address can see your books and use
  your OpenAI key. Turn on the optional password in `frontend/nginx.conf` (instructions inside), or limit
  port 80 to your office IP in the firewall. Use a domain with HTTPS before real use.

## On a Linux server without Docker (e.g. AWS EC2, Amazon Linux 2023)

Amazon Linux 2023's own Python 3.9 works. Use the venv's Python for pip so it installs into the venv:

```bash
cd backend && python3 -m venv venv && venv/bin/python -m pip install --upgrade pip
venv/bin/python -m pip install -r requirements.txt
cp .env.example .env   # then put your OPENAI_API_KEY in it; .env is not in git
pm2 start venv/bin/python --name backend-app --interpreter none -- -m uvicorn app.main:app --host 0.0.0.0 --port 2000
```

Without pm2: `venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 2000`. Allow the port in the
EC2 Security Group (inbound TCP). After a `git pull`, run the `pip install` line again and `pm2 restart backend-app`.

## Android app

`frontend/android` is the Android project. To build the APK, double-click **`build-apk.bat`** in the project
folder (needs Node.js and Android Studio); it builds the web app, copies it into the Android project, runs
Gradle and leaves the result in `apk\Accounts.ai-1.0-debug.apk`. The same steps by hand: `npm run build`,
`npx cap sync android`, then `gradlew.bat assembleDebug` in `frontend/android` (details in `frontend/README.md`).

To use it: on the PC that holds the books, run `backend\start-server.bat` (allow Python on **Private
networks** when Windows Firewall asks), install the APK on the phone, and enter the address the script
prints. There is no password, so use it only on a network you trust. The phone must be on the same Wi-Fi,
or the backend must be hosted where the phone can reach it (use HTTPS for that).

## Documents in Supabase (optional)

With `SUPABASE_URL` and `SUPABASE_SECRET_KEY` in `backend/.env`, every file uploaded from any client (web, the
Android app, the Expo app) is also stored unchanged in a **private** Supabase Storage bucket (a public bucket is
refused, so documents can never be downloaded without the key). The copy is made in the background, so uploads are
not slower and never fail because of it. Until Supabase confirms a copy, the file waits in `DATA_DIR/cloud_outbox`;
passing failures (Supabase or the network down) keep it waiting and it is tried again every 15 minutes and at the
next start; only problems retrying cannot fix (wrong key, public bucket, refused file) mark it failed, and
`POST /api/cloud/retry` sends those again after you fix them. The key is only ever sent over https and never
follows a redirect. File names carry a content fingerprint, so two servers sharing one bucket never overwrite each
other's documents. `GET /api/health` and `GET /api/cloud` show how many copies are sent, waiting or failed, and each
upload's detail (`GET /api/datasets/{id}`) shows its copy's status and path. Deleting an upload in the app keeps
its copy in Supabase. The key never leaves the server; the apps do not talk to Supabase directly.

## MongoDB live copy of records (optional)

With `MONGODB_URI` in `backend/.env`, the backend keeps a live copy of the app's records in MongoDB (database
`MONGODB_DB`, default `accountsai`): collection **uploads**, one document per upload (`_id` = upload id: file name,
size, upload time, each sheet's statistics, notes and report setup — column roles and account groups — and the state
of its Supabase copy), and collection **chats**, one document per conversation (`_id` = `<scope>/<id>`: title, time,
files, turns). Each change (an upload, an entry added or deleted, a calculated column, notes, setup, a chat saved, the
Supabase copy's state) is sent within seconds, and a deleted upload or conversation is deleted there too (deleting an
upload or a set also deletes its conversations). Not copied: the sheets' rows, the company books and vouchers, and the
uploaded files themselves (see Supabase above). SQLite stays the main copy, so MongoDB never slows a request down or
makes it fail: while it cannot be reached, records wait in the `mongo_sync` table and are retried. A pass at startup and
every 5 minutes sends every record that changed since MongoDB last confirmed it, every record when `MONGODB_DB` or the
cluster changed, and every record MongoDB no longer holds (a collection emptied in Atlas), so uploads and chats made
before MongoDB was set up are copied too. A change made to a document directly in MongoDB is not detected. Only
problems retrying cannot fix (wrong password, no permission) are marked failed; after fixing them, restart the backend
or call `POST /api/mongo/retry`.

MongoDB Atlas:

1. Create a free cluster at cloud.mongodb.com.
2. **Database Access**: add a database user with a password and only the **readWrite** role on the database
   `accountsai` (Specific Privileges), not Atlas admin.
3. **Network Access**: add the server's public IP address, not `0.0.0.0/0`.
4. **Connect → Drivers**: copy the `mongodb+srv://…` string and put the user's password in it, percent-encoded (`@`
   as `%40`, `:` as `%3A`, `/` as `%2F`, `?` as `%3F`, `+` as `%2B`, `%` as `%25`; a `+` left as it is is read as a
   space). `python -c "import urllib.parse; print(urllib.parse.quote_plus(input()))"` prints the encoded password.
5. Add `MONGODB_URI=<that string>` to `backend/.env` (and `MONGODB_DB` if the database is not `accountsai`), then
   restart the backend.
6. `GET /api/mongo` (also in `GET /api/health`) shows the hosts, the database, how many records are sent, waiting or
   failed, and the last error. The connection string and its password never appear in a message, log or answer; only
   the host names do. A plain `mongodb://` address must use `tls=true` unless MongoDB runs on the same machine.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Backend status and which chat models have API keys |
| POST | `/api/upload` | Upload a spreadsheet (multipart field `file`); also copied to Supabase when set up |
| GET / POST | `/api/cloud` · `/api/cloud/retry` | Supabase copies: counts; send failed copies again |
| GET / POST | `/api/mongo` · `/api/mongo/retry` | MongoDB live copy: hosts, database, counts and the last error; send failed records again (409 when not set up) |
| GET | `/api/chats?scope=home` | Chat history kept on the server, per scope (`home`, `ds-<upload id>`, `book-<set id>`): `{"chats": [conversation, ...], "deleted": [{"id", "updated"}]}`; `deleted` lists conversations removed on any device. The newest 100 conversations per scope are kept: older ones become deletions at their own time, and deleting an upload or a set deletes its conversations |
| PUT | `/api/chats/{scope}/{id}` | Save a conversation `{"id", "title", "updated", "datasetIds", "documents", "turns"}` (at most 40 turns and 2 MB; a larger body is refused with 413 before it is read): the larger `updated` (ms) wins, equal keeps the server's copy; answers `{"chat": the copy kept}`, or `{"chat": null, "deleted": {"id", "updated"}}` when a deletion as new or newer won |
| DELETE | `/api/chats/{scope}/{id}?updated=<ms>` | Delete a conversation on every device: a tombstone at that time (default now), unless the server's copy is newer |
| GET / DELETE | `/api/datasets[/{id}]` | List, open or delete uploads |
| POST | `/api/datasets/{id}/sql` | Run a read-only DuckDB `SELECT` |
| GET | `/api/datasets/{id}/fields` · `/api/books/{id}/fields` | Tables and columns available to Analyse (kind and exact decimals) |
| POST | `/api/datasets/{id}/analyse` · `/api/books/{id}/analyse` | Analyse: `{"table", "measures": [{"agg": "sum", "column"}], "group_by": [{"column", "bucket": "month"}], "filters": [{"column", "op", "value"}], "sort", "limit", "across"}` |
| POST | `/api/datasets/{id}/chat` | Chat: `{"messages": [...], "provider": "openai"}` → answer, queries, calculations, formula checks, verification |
| POST | `/api/chat/stream` | The home chat over the files shared in it: `{"dataset_ids": [...], "messages": [...]}`; streams Server-Sent Events (`step`, `delta`, `reset`, `analysis`, `done`, `error`). With a sales and a purchase register, the model also gets the app's exact comparison of the two. `/api/datasets/{id}/chat/stream` and `/api/books/{id}/chat/stream` stream the same way |
| POST | `/api/chat/followups` | Up to three suggested next questions: `{"messages": [...], "dataset_ids": [...], "book_id": null, "provider": null}` → `{"suggestions": [...]}`; an empty list when the model is not set up or fails |
| POST | `/api/documents` | What each shared file is: `{"dataset_ids": [...]}` → kind (sales, purchases, bank, ledger, other), confidence, reasons |
| POST | `/api/ai/warm` | Opens the connection to OpenAI while the person types, so the first answer starts sooner |
| POST | `/api/calc` | Exact calculator: `{"expression": "1,200 - 350.50"}` |
| POST | `/api/datasets/{id}/sheets/{table}/calculate` | Column formula; optional `compare_to`, `tolerance`, `save_as` |
| GET / POST | `/api/datasets/{id}/sheets/{table}/rows` | List/search entries; add an entry |
| DELETE | `/api/datasets/{id}/sheets/{table}/rows/{rowid}` | Delete an entry |
| GET / PUT | `/api/datasets/{id}/sheets/{table}/setup` | Column roles and account groups used by the reports |
| GET | `/api/datasets/{id}/sheets/{table}/reports/{kind}` | `ledger`, `day_book`, `trial_balance`, `profit_and_loss`, `balance_sheet`, `ageing`, `gst` |
| GET | `/api/datasets/{id}/gst-net?sales=&purchases=` | Net GST payable after input tax credit |
| PUT | `/api/datasets/{id}/sheets/{table}/notes` | Notes for the AI about a sheet |
| GET / POST | `/api/books` | List sales + purchases sets; create one: `{"name", "sales": [upload ids], "purchases": [upload ids]}` |
| GET / DELETE | `/api/books/{id}` | Open or remove a set (the uploads stay) |
| PUT | `/api/books/{id}/sheets` | Mark sheets: `{"registers": {"table": "sales" \| "purchases" \| "unused"}}` |
| GET | `/api/books/{id}/reports/{kind}` | `compare`, `gst`, `stock`, `profit_and_loss`, `parties`, `party_ledger`, `ageing`, `day_book` |
| POST | `/api/books/{id}/chat` · `/api/books/{id}/sql` | Chat or read-only SQL across both registers |
| GET / POST | `/api/companies` | List companies; create one: `{"name", "gstin", "fy_start"}` |
| GET / PUT | `/api/companies/{id}` | Open; rename, set GSTIN, lock books: `{"locked_until": "2025-06-30"}` |
| GET / POST / PUT | `/api/companies/{id}/ledgers[/{ledger_id}]` | Ledgers with closing balances; create/edit `{"name", "group", "opening", "gstin", "credit_days"}` (opening + = Dr) |
| GET / POST | `/api/companies/{id}/vouchers` | List (filters `vtype`, `start`, `end`, `search`); post any voucher `{"vtype", "date", "lines": [{"ledger_id", "dr", "cr"}]}` |
| GET / PUT / DELETE | `/api/companies/{id}/vouchers/{voucher_id}` | Open, alter, cancel (vouchers are never deleted) |
| POST | `/api/companies/{id}/vouchers/invoice` | GST invoice: `{"vtype", "date", "party_id", "items": [{"taxable", "rate"}]}` |
| POST | `/api/companies/{id}/vouchers/settlement` | Receipt/payment: `{"vtype", "date", "party_id", "cash_bank_id", "amount", "against": [{"bill_ref", "amount"}], "tds"}` |
| GET | `/api/companies/{id}/bills/{party_id}` · `/audit` | Pending bills of a party · audit trail |
| POST | `/api/companies/{id}/import/register` · `/import/book` · `/import/bank` | Post an uploaded register or a sales + purchases set as vouchers; load a bank statement |
| POST | `/api/companies/{id}/vouchers/jewellery` | Jewellery bill: `{"vtype", "date", "party_id", "metal", "items": [{"gross", "diamond_ct", "stone_ct", "tunch", "diamond_value", "labour_rate", "settle": "Wt"}], "gst_rate", "metal_rate"}` |
| POST | `/api/companies/{id}/vouchers/metal` | Metal received / given: `{"vtype": "Metal Receipt" \| "Metal Issue", "date", "party_id", "items": [{"net", "tunch"}]}` |
| POST | `/api/companies/{id}/vouchers/rate-cut` | `{"date", "party_id", "metal", "fine", "rate", "gst_rate"}` |
| GET | `/api/companies/{id}/metal-balance/{party_id}` | Fine metal a party owes (+) or is owed (−), in grams |
| GET | `/api/companies/{id}/reports/{kind}` | `dashboard`, `day_book`, `ledger`, `cash_bank_book`, `trial_balance`, `profit_and_loss`, `balance_sheet`, `receivables`, `payables`, `gstr1`, `gstr3b`, `bank_reconciliation`, `metal_balances`, `metal_ledger`, `stock_grams` (`metal=gold\|silver`, `rate=`) |

## Configuration (`backend/.env`)

| Variable | Default | |
| --- | --- | --- |
| `OPENAI_API_KEY` | — | Enables GPT-6 Luna in the chat |
| `OPENAI_MODEL` | `gpt-6-luna` | OpenAI model used for chat |
| `OPENAI_REASONING_EFFORT` | `low` | Effort for the first answer, `none` … `max`; low answers about twice as fast as high, and every figure is still checked |
| `OPENAI_REPAIR_EFFORT` | `medium` | Effort for the correction round, used only when a figure fails the check |
| `OPENAI_FOLLOWUP_EFFORT` | `low` | Effort for the suggested next questions shown under an answer |
| `OPENAI_SERVICE_TIER` | — | Set `priority` for faster processing from OpenAI at a higher price per token |
| `ANTHROPIC_API_KEY` | — | Enables Claude as a second option in the chat |
| `ANTHROPIC_MODEL` | `claude-opus-5-5` | Claude model used for chat |
| `ANTHROPIC_EFFORT` / `ANTHROPIC_REPAIR_EFFORT` | `low` / `medium` | Same, for Claude |
| `LLM_PROVIDER` | `openai` | Model selected first when both keys are set |
| `MAX_UPLOAD_MB` | `25` | Upload size limit |
| `SUPABASE_URL` / `SUPABASE_SECRET_KEY` | — | Optional: also store every uploaded document in Supabase Storage (the https:// Project URL, and a secret key `sb_secret_…` from Supabase → Project Settings → API Keys; a legacy service_role key also works; `SUPABASE_SERVICE_KEY` is accepted as the name too) |
| `SUPABASE_BUCKET` / `SUPABASE_FOLDER` | `documents` / `uploads` | Private bucket (created if missing; a public one is refused) and folder: `<folder>/<YYYY-MM>/<upload id>-<content fingerprint>-<file name>` |
| `MONGODB_URI` / `MONGODB_DB` | — / `accountsai` | Optional: a live copy of the uploads (sheet statistics, notes, setup) and chat conversations in MongoDB; the `mongodb+srv://` string from Atlas (TLS with certificate checks is required for any host but this machine) |
| `DATA_DIR` | `backend/data` | Where `accounts.db` is stored |

## Limits to know

- On an uploaded sheet, a **balance sheet and a tallying trial balance need a full double-entry ledger or trial-balance
  export**. Registers and bank statements record one side of each entry, so the app explains why they do not tally.
  To get books that always tally, import the registers into **Company books**, which posts both sides.
- Gold: GST on a by-weight (Wt) sale is charged on the rupee part only, as the registers show; the research
  report argues it may be due on the full value including metal; have your CA confirm. Opening stock is one
  fine figure (not split by karat), stock is not valued in rupees from the metal account, karigar
  wastage and metal loans are not separate entries yet, and HUID / hallmark details are not tracked.
- Company books do not yet cover: reverse charge (RCM), GST on advances, GSTR-2B matching, the HSN summary,
  stock items inside vouchers (stock is valued from the registers under Sales + Purchases → Stock summary), cost
  centres, multi-currency, or e-invoice/e-way bill generation. TDS is posted to one "TDS Payable" ledger; section-wise
  TDS (renumbered under the Income-tax Act 2025 from 1 April 2026) is not tracked.
- **Closing stock** cannot be derived from ledgers; enter it in the P&L / balance sheet report.
- Account groups are suggested from names (Tally's groups); unclear ones are marked **Unclassified** and should be
  set in the trial balance.
- The GST rules follow GST 2.0 (5%/18%/40% from 22 Sept 2025). Tolerances such as ₹1 per invoice are design choices;
  have a chartered accountant review the GST checks before relying on them for filing.
- Tally, Busy and bank export layouts vary; test the import with your own real exports.

## Code map

| File | What it does |
| --- | --- |
| `backend/app/main.py` | HTTP routes |
| `backend/app/excel_loader.py` | Reads and checks Excel/CSV (formats, Dr/Cr, dates, totals, duplicates) |
| `backend/app/analytics.py` | NumPy/pandas statistics and summaries |
| `backend/app/reports.py` | Ledger, day book, trial balance, P&L, balance sheet, ageing, GST (exact paise arithmetic) |
| `backend/app/books.py` | Sales vs purchases: comparison, net GST, stock summary (AS-2 weighted average), gross profit, parties, party ledger, ageing, day book |
| `backend/app/accounts/` | Double-entry books: groups and default ledgers (`chart.py`), tables and audit triggers (`db.py`), voucher posting and validation (`service.py`), register and bank imports (`imports.py`), reports and GST returns (`reports.py`), fine-metal accounts, jewellery import and gold reports (`metal.py`), routes (`api.py`) |
| `backend/app/classify.py` / `gst.py` | Tally account groups; GSTIN validation, state codes, GST 2.0 rates |
| `backend/app/calc.py` | Safe exact calculator and column formulas |
| `backend/app/editing.py` | Add/delete entries, calculated columns, formula checks, notes, report setup |
| `backend/app/database.py` | SQLAlchemy storage (SQLite) |
| `backend/app/duck.py` | DuckDB query engine: sheets loaded with pandas, exact DECIMAL columns, locked-down sessions |
| `backend/app/analysis.py` | Analyse: request → parameterised DuckDB query → pandas (averages, top N + "All others", pivot, proof checks) |
| `backend/app/detect.py` | Which shared file is a sales register, purchase register, bank statement or ledger, with the evidence |
| `backend/app/llm/` | Chat: prompt, data dictionary and tools (`common.py`), answer verification (`verify.py`), GPT-6 Luna (`gpt.py`), Claude (`claude.py`) |
| `frontend/src/components/` | `UploadPanel` + `BooksUpload`, `DatasetView`, `BooksView`, `AnalysePanel`, `ChatPanel`, `ReportsPanel`, `EntriesPanel`, `CalculatorPanel`; `accounts/` holds the company books screens (`CompanyView`, `VoucherEntry`, `VouchersPanel`, `LedgersPanel`, `AccountsReports`, `AccountsImport`) |
