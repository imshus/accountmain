import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { api, isApp, serverUrl } from "./api";
import ChatPanel, { forgetChats, forgetDataset, sweepChats } from "./components/ChatPanel";
import DatasetList from "./components/DatasetList";
import ErrorBoundary from "./components/ErrorBoundary";
import ServerSetup from "./components/ServerSetup";

// The chat opens first, so only it is in the main bundle; the other screens load on their own (and are
// fetched in the background once the chat is up, so opening them is still instant).
const loadScreens = {
  BooksView: () => import("./components/BooksView"),
  DatasetView: () => import("./components/DatasetView"),
  UploadPanel: () => import("./components/UploadPanel"),
  CompanyView: () => import("./components/accounts/CompanyView"),
  NewCompany: () => import("./components/accounts/NewCompany"),
};
const BooksView = lazy(loadScreens.BooksView);
const DatasetView = lazy(loadScreens.DatasetView);
const UploadPanel = lazy(loadScreens.UploadPanel);
const CompanyView = lazy(loadScreens.CompanyView);
const NewCompany = lazy(loadScreens.NewCompany);
import { formatCount, formatTimestamp } from "./format";
import type { BookDetail, BookSummary, Company, DatasetDetail, DatasetSummary, DocumentInfo, Health, RegisterType } from "./types";

function summarize(detail: DatasetDetail): DatasetSummary {
  return {
    id: detail.id,
    filename: detail.filename,
    size_bytes: detail.size_bytes,
    uploaded_at: detail.uploaded_at,
    sheet_count: detail.sheets.length,
    row_count: detail.sheets.reduce((sum, sheet) => sum + sheet.row_count, 0),
  };
}

function summarizeBook(book: BookDetail): BookSummary {
  return {
    id: book.id,
    name: book.name,
    created_at: book.created_at,
    sales_sheets: book.sheets.filter((s) => s.register_type === "sales").length,
    purchase_sheets: book.sheets.filter((s) => s.register_type === "purchases").length,
  };
}

/**
 * How to create a sales + purchases set from the chat's detected sheets. The backend forces every sheet of a
 * ``sales`` / ``purchases`` upload into that register, so only uploads whose sheets are all one kind go there;
 * an upload holding both (or a bank / other sheet) goes in ``mixed`` and each sheet is set afterwards.
 */
function bookPlan(documents: DocumentInfo[]): { sales: number[]; purchases: number[]; mixed: number[] } {
  const kinds = new Map<number, Set<string>>();
  for (const d of documents) {
    const set = kinds.get(d.dataset_id) ?? new Set<string>();
    set.add(d.kind === "sales" || d.kind === "purchases" ? d.kind : "other");
    kinds.set(d.dataset_id, set);
  }
  const plan = { sales: [] as number[], purchases: [] as number[], mixed: [] as number[] };
  for (const [id, set] of kinds) {
    if (set.size === 1 && set.has("sales")) plan.sales.push(id);
    else if (set.size === 1 && set.has("purchases")) plan.purchases.push(id);
    else if (set.has("sales") || set.has("purchases")) plan.mixed.push(id);
  }
  // The backend needs one upload in each list unless sheet names say so: lend it a mixed upload when the other
  // side is still covered (the sheet registers are corrected right after).
  const other = { sales: "purchases", purchases: "sales" } as const;
  for (const side of ["sales", "purchases"] as const) {
    if (plan[side].length) continue;
    const pick = plan.mixed.find(
      (id) => kinds.get(id)!.has(side) && (plan[other[side]].length > 0 || plan.mixed.some((o) => o !== id && kinds.get(o)!.has(other[side]))),
    );
    if (pick !== undefined) {
      plan.mixed = plan.mixed.filter((id) => id !== pick);
      plan[side].push(pick);
    }
  }
  return plan;
}

/** Each sheet of the new set gets the register the chat detected for it; anything else is not used. */
function sheetRegisters(book: BookDetail, documents: DocumentInfo[]): Record<string, RegisterType> {
  return Object.fromEntries(
    book.sheets.map((sheet) => {
      const kind = documents.find((d) => d.table_name === sheet.table_name)?.kind;
      return [sheet.table_name, kind === "sales" || kind === "purchases" ? kind : "unused"];
    }),
  );
}

type Screen = "home" | "library" | "upload" | "dataset" | "book" | "company" | "new-company" | "server";

// The home chat's starter cards; one beginning with "+" opens the file picker.
const HOME_SUGGESTIONS = [
  "+ Attach a sales register and a purchase register",
  "What is GST input tax credit, and when can I claim it?",
  "How do I read a trial balance?",
  "What must a GST tax invoice show?",
];

// The Android app has no server until the user enters one (menu → Server).
const NEEDS_SERVER = isApp && !serverUrl();

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [backendError, setBackendError] = useState<string | null>(null);
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [books, setBooks] = useState<BookSummary[]>([]);
  const [selected, setSelected] = useState<DatasetDetail | null>(null);
  const [selectedBook, setSelectedBook] = useState<BookDetail | null>(null);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [selectedCompany, setSelectedCompany] = useState<Company | null>(null);
  const [screen, setScreen] = useState<Screen>("home");
  const [openingId, setOpeningId] = useState<number | null>(null);
  const [openError, setOpenError] = useState<string | null>(null);
  useEffect(() => {
    if (NEEDS_SERVER) return;
    // The chat needs only the health check, so it does not wait for the lists.
    api
      .health()
      .then(setHealth)
      .catch((error: Error) => setBackendError(error.message));
    Promise.all([api.datasets(), api.books(), api.companies().catch(() => [] as Company[])])
      .then(([list, bookList, companyList]) => {
        setDatasets(list);
        setBooks(bookList);
        setCompanies(companyList);
        sweepChats(
          list.map((d) => d.id),
          bookList.map((b) => b.id),
        );
      })
      .catch((error: Error) => setBackendError(error.message));
    const prefetch = window.setTimeout(() => Object.values(loadScreens).forEach((load) => void load().catch(() => null)), 2000);
    return () => window.clearTimeout(prefetch);
  }, []);

  const handleUploaded = useCallback((detail: DatasetDetail) => {
    setSelected(detail);
    setScreen("dataset");
    setDatasets((current) => [summarize(detail), ...current.filter((d) => d.id !== detail.id)]);
  }, []);

  const handleBookCreated = useCallback((book: BookDetail, uploaded: DatasetDetail[]) => {
    setDatasets((current) => [...uploaded.map(summarize), ...current.filter((d) => !uploaded.some((u) => u.id === d.id))]);
    setBooks((current) => [summarizeBook(book), ...current]);
    setSelectedBook(book);
    setScreen("book");
  }, []);

  const handleDatasetChange = useCallback((detail: DatasetDetail) => {
    setSelected(detail);
    setDatasets((current) => current.map((d) => (d.id === detail.id ? summarize(detail) : d)));
  }, []);

  const handleBookChange = useCallback((book: BookDetail) => {
    setSelectedBook(book);
    setBooks((current) => current.map((b) => (b.id === book.id ? summarizeBook(book) : b)));
  }, []);

  const handleCompanyCreated = useCallback((company: Company) => {
    setCompanies((current) => [{ ...company, voucher_count: 0 }, ...current]);
    setSelectedCompany(company);
    setScreen("company");
  }, []);

  const handleCompanyChange = useCallback((company: Company) => {
    setSelectedCompany(company);
    setCompanies((current) => current.map((c) => (c.id === company.id ? { ...c, ...company } : c)));
  }, []);

  const handleOpenCompany = useCallback(async (id: number) => {
    setOpenError(null);
    try {
      // Re-read the list so voucher counts are current.
      const list = await api.companies();
      const company = list.find((c) => c.id === id);
      setCompanies(list);
      if (company) {
        setSelectedCompany(company);
        setScreen("company");
      }
    } catch (error) {
      setOpenError((error as Error).message);
    }
  }, []);

  const handleOpen = useCallback(async (id: number) => {
    setOpeningId(id);
    setOpenError(null);
    try {
      setSelected(await api.dataset(id));
      setScreen("dataset");
    } catch (error) {
      setOpenError((error as Error).message);
    } finally {
      setOpeningId(null);
    }
  }, []);

  const handleOpenBook = useCallback(async (id: number) => {
    setOpenError(null);
    try {
      setSelectedBook(await api.book(id));
      setScreen("book");
    } catch (error) {
      setOpenError((error as Error).message);
    }
  }, []);

  const handleDelete = useCallback(async (dataset: DatasetSummary) => {
    if (!window.confirm(`Delete "${dataset.filename}" and its tables? This cannot be undone.`)) return;
    try {
      await api.deleteDataset(dataset.id);
      forgetDataset(dataset.id);
      setDatasets((current) => current.filter((d) => d.id !== dataset.id));
      if (selected?.id === dataset.id) {
        setSelected(null);
        if (screen === "dataset") setScreen("home");
      }
    } catch (error) {
      setOpenError((error as Error).message);
    }
  }, [selected, screen]);

  const handleDeleteBook = useCallback(async (book: BookSummary) => {
    if (!window.confirm(`Remove the set "${book.name}"? The uploaded files stay.`)) return;
    try {
      await api.deleteBook(book.id);
      forgetChats(`book-${book.id}`);
      setBooks((current) => current.filter((b) => b.id !== book.id));
      if (selectedBook?.id === book.id) {
        setSelectedBook(null);
        if (screen === "book") setScreen("home");
      }
    } catch (error) {
      setOpenError((error as Error).message);
    }
  }, [selectedBook, screen]);

  const needsServer = NEEDS_SERVER || ((isApp || serverUrl()) && backendError) || screen === "server";

  if (screen === "home" && !needsServer && !backendError) {
    return (
      <div className="app">
        <ErrorBoundary key="home">
          <ChatPanel
            page
            scope="home"
            subject="your files"
            onLibrary={() => setScreen("library")}
            suggestionList={HOME_SUGGESTIONS}
            health={health}
            stream={(messages, provider, onEvent, options) => api.filesChatStream(options.datasetIds ?? [], messages, provider, onEvent, options)}
            attachments={{
              onUploaded: (detail) => setDatasets((current) => [summarize(detail), ...current.filter((d) => d.id !== detail.id)]),
              onCompare: async (documents, name) => {
                const created = await api.createBook({ name: name.slice(0, 80), ...bookPlan(documents) });
                let book: BookDetail;
                try {
                  book = await api.setBookSheets(created.id, sheetRegisters(created, documents));
                } catch (error) {
                  // A set with the wrong registers would give wrong figures: remove it.
                  await api.deleteBook(created.id).catch(() => null);
                  throw error;
                }
                setBooks((current) => [summarizeBook(book), ...current]);
                setSelectedBook(book);
                setScreen("book");
              },
            }}
          />
        </ErrorBoundary>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="topbar">
        <button className="brand" onClick={() => setScreen("home")} title="Back to the chat">
          <span className="brand-mark" aria-hidden="true">
            A
          </span>
          <span className="brand-name">Accounts.ai</span>
        </button>
        <button className="topbar-back" onClick={() => setScreen("home")}>
          ← Chat
        </button>
      </header>

      <div className="layout">

        <main className="content">
          <Suspense fallback={<p className="muted">Loading…</p>}>
          {needsServer ? (
            <ServerSetup problem={NEEDS_SERVER ? null : backendError} onCancel={screen === "server" && !backendError ? () => setScreen("home") : undefined} />
          ) : backendError ? (
            <div className="callout error">
              <strong>Backend not reachable.</strong> {backendError} Start it with{" "}
              <code>uvicorn app.main:app --reload</code> in the <code>backend</code> folder, then refresh.
            </div>
          ) : screen === "dataset" && selected ? (
            <ErrorBoundary key={`d${selected.id}`}>
              <DatasetView dataset={selected} health={health} onDatasetChange={handleDatasetChange} />
            </ErrorBoundary>
          ) : screen === "book" && selectedBook ? (
            <ErrorBoundary key={`b${selectedBook.id}`}>
              <BooksView book={selectedBook} health={health} onBookChange={handleBookChange} onOpenDataset={(id) => void handleOpen(id)} />
            </ErrorBoundary>
          ) : screen === "company" && selectedCompany ? (
            <ErrorBoundary key={`c${selectedCompany.id}`}>
              <CompanyView company={selectedCompany} books={books} datasets={datasets} onCompanyChange={handleCompanyChange} />
            </ErrorBoundary>
          ) : screen === "new-company" ? (
            <NewCompany onCreated={handleCompanyCreated} onCancel={selectedCompany ? () => setScreen("company") : () => setScreen("home")} />
          ) : screen === "library" ? (
            <section className="library">
              <div className="library-head">
                <h1>Files &amp; books</h1>
                <div className="sql-actions">
                  <button className="button primary" onClick={() => setScreen("upload")}>
                    Upload Excel
                  </button>
                  <button className="button" onClick={() => setScreen("new-company")}>
                    New company books
                  </button>
                </div>
              </div>
              <div className="library-grid">
              <section className="dataset-list" aria-label="Company books">
                <div className="list-head">
                  <h2 className="eyebrow">Company books</h2>
                  <button className="link-button" onClick={() => setScreen("new-company")}>
                    + New
                  </button>
                </div>
                {companies.length ? (
                  <ul>
                    {companies.map((company) => (
                      <li key={company.id}>
                        <button className="dataset-item" onClick={() => void handleOpenCompany(company.id)}>
                          <span className="dataset-name" title={company.name}>
                            {company.name}
                          </span>
                          <span className="muted small">
                            {company.gstin ?? "No GSTIN"} · {formatCount(company.voucher_count ?? 0)} vouchers
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="muted small">Double-entry books with vouchers, ledgers, GST returns and bank reconciliation.</p>
                )}
              </section>
              {books.length ? (
                <section className="dataset-list" aria-label="Sales and purchases sets">
                  <h2 className="eyebrow">Sales + purchase sets</h2>
                  <ul>
                    {books.map((book) => (
                      <li key={book.id}>
                        <button className="dataset-item" onClick={() => void handleOpenBook(book.id)}>
                          <span className="dataset-name" title={book.name}>
                            {book.name}
                          </span>
                          <span className="muted small">
                            {book.sales_sheets} sales · {book.purchase_sheets} purchase sheet{book.purchase_sheets === 1 ? "" : "s"}
                          </span>
                          <span className="muted small">{formatTimestamp(book.created_at)}</span>
                        </button>
                        <button className="icon-button" onClick={() => void handleDeleteBook(book)} aria-label={`Remove ${book.name}`} title="Remove set">
                          ×
                        </button>
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}
              <DatasetList
                datasets={datasets}
                activeId={null}
                openingId={openingId}
                onOpen={handleOpen}
                onDelete={handleDelete}
              />
              {openError ? <p className="error-text">{openError}</p> : null}
              {isApp || serverUrl() ? (
                <button className="link-button server-link" onClick={() => setScreen("server")}>
                  Server: {serverUrl().replace(/^https?:\/\//, "") || "not set"} · Change
                </button>
              ) : null}
              </div>
            </section>
          ) : (
            <UploadPanel
              datasets={datasets}
              onUploaded={handleUploaded}
              onBookCreated={handleBookCreated}
              onCancel={() => setScreen(selectedBook && !selected ? "book" : selected ? "dataset" : "home")}
            />
          )}
          </Suspense>
        </main>
      </div>
    </div>
  );
}
