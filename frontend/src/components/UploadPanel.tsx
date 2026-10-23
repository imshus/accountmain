import { useRef, useState, type DragEvent } from "react";
import { uploadFile } from "../api";
import { formatBytes } from "../format";
import type { BookDetail, DatasetDetail, DatasetSummary } from "../types";
import BooksUpload from "./BooksUpload";

const ACCEPTED = [".xlsx", ".xlsm", ".xls", ".csv"];
const MAX_MB = 25;

type Props = {
  datasets: DatasetSummary[];
  onUploaded: (dataset: DatasetDetail) => void;
  onBookCreated: (book: BookDetail, uploaded: DatasetDetail[]) => void;
  onCancel?: () => void;
};

type Status =
  | { state: "idle" }
  | { state: "uploading"; file: File; progress: number }
  | { state: "processing"; file: File }
  | { state: "error"; message: string };

function validate(file: File): string | null {
  const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (!ACCEPTED.includes(ext)) return `"${file.name}" is not a spreadsheet. Use ${ACCEPTED.join(", ")}.`;
  if (file.size > MAX_MB * 1024 * 1024) return `"${file.name}" is ${formatBytes(file.size)}; the limit is ${MAX_MB} MB.`;
  if (file.size === 0) return `"${file.name}" is empty.`;
  return null;
}

export default function UploadPanel({ datasets, onUploaded, onBookCreated, onCancel }: Props) {
  const [mode, setMode] = useState<"single" | "books">("single");
  const inputRef = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<Status>({ state: "idle" });
  const [dragging, setDragging] = useState(false);
  const busy = status.state === "uploading" || status.state === "processing";

  async function start(file: File) {
    const problem = validate(file);
    if (problem) {
      setStatus({ state: "error", message: problem });
      return;
    }
    setStatus({ state: "uploading", file, progress: 0 });
    try {
      const dataset = await uploadFile(file, (progress) =>
        setStatus(progress < 1 ? { state: "uploading", file, progress } : { state: "processing", file }),
      );
      setStatus({ state: "idle" });
      onUploaded(dataset);
    } catch (error) {
      setStatus({ state: "error", message: (error as Error).message });
    }
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files[0];
    if (file && !busy) void start(file);
  }

  return (
    <section className="upload-page">
      <div className="upload-heading">
        <h1>{mode === "single" ? "Upload your Excel sheet" : "Upload sales and purchases"}</h1>
        <p className="muted">
          {mode === "single"
            ? "Ledger, bank statement, sales register or invoices. Every sheet is read and checked."
            : "Your sales and purchase registers side by side: margin, stock, GST to pay, customers and suppliers."}
        </p>
      </div>

      <div className="segmented mode-switch" role="tablist" aria-label="Upload type">
        <button role="tab" aria-selected={mode === "single"} className={mode === "single" ? "active" : ""} onClick={() => setMode("single")} disabled={busy}>
          One file
        </button>
        <button role="tab" aria-selected={mode === "books"} className={mode === "books" ? "active" : ""} onClick={() => setMode("books")} disabled={busy}>
          Sales + Purchases
        </button>
      </div>

      {mode === "books" ? <BooksUpload datasets={datasets} onCreated={onBookCreated} /> : null}

      <div
        hidden={mode !== "single"}
        className={`dropzone${dragging ? " dragging" : ""}${busy ? " busy" : ""}`}
        onDragOver={(event) => {
          event.preventDefault();
          if (!busy) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => !busy && inputRef.current?.click()}
        onKeyDown={(event) => {
          if ((event.key === "Enter" || event.key === " ") && !busy) {
            event.preventDefault();
            inputRef.current?.click();
          }
        }}
        role="button"
        tabIndex={0}
        aria-disabled={busy}
        aria-label="Choose a spreadsheet to upload"
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED.join(",")}
          hidden
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            if (file) void start(file);
          }}
        />
        {status.state === "uploading" || status.state === "processing" ? (
          <div className="upload-progress">
            <p className="file-name">{status.file.name}</p>
            <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={100}
              aria-valuenow={status.state === "uploading" ? Math.round(status.progress * 100) : 100}>
              <div
                className={`progress-bar${status.state === "processing" ? " indeterminate" : ""}`}
                style={{ width: status.state === "uploading" ? `${Math.round(status.progress * 100)}%` : "100%" }}
              />
            </div>
            <p className="muted small">
              {status.state === "uploading"
                ? `Uploading… ${Math.round(status.progress * 100)}%`
                : "Reading sheets and calculating summaries…"}
            </p>
          </div>
        ) : (
          <>
            <div className="dropzone-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="1.8">
                <path d="M12 16V4m0 0l-4 4m4-4l4 4" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2" strokeLinecap="round" />
              </svg>
            </div>
            <p className="dropzone-title">
              Drop a file here or <span className="link">browse</span>
            </p>
            <p className="muted small">
              {ACCEPTED.join(" · ")} · up to {MAX_MB} MB
            </p>
          </>
        )}
      </div>

      {status.state === "error" && mode === "single" ? (
        <div className="callout error" role="alert">
          {status.message}
        </div>
      ) : null}

      {onCancel && !busy ? (
        <button className="button ghost" onClick={onCancel}>
          ← Back
        </button>
      ) : null}

      <p className="muted small">
        To keep full accounts (vouchers, GST returns, gold ledger), open <strong>Company books</strong> from the menu and import the
        file there.
      </p>
    </section>
  );
}
