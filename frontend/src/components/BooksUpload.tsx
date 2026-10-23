import { useRef, useState, type DragEvent } from "react";
import { api, uploadFile } from "../api";
import { formatBytes } from "../format";
import type { BookDetail, DatasetDetail, DatasetSummary } from "../types";

type Props = {
  datasets: DatasetSummary[];
  onCreated: (book: BookDetail, uploaded: DatasetDetail[]) => void;
};

type Slot = { file: File | null; existing: number | null; progress: number | null };
const EMPTY: Slot = { file: null, existing: null, progress: null };
const ACCEPTED = [".xlsx", ".xlsm", ".xls", ".csv"];

/** Upload (or pick) a sales register and a purchase register, then compare and combine them. */
export default function BooksUpload({ datasets, onCreated }: Props) {
  const [sales, setSales] = useState<Slot>(EMPTY);
  const [purchases, setPurchases] = useState<Slot>(EMPTY);
  const [name, setName] = useState(() => `Sales & purchases ${new Date().toLocaleDateString("en-IN", { month: "short", year: "numeric" })}`);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ready = (sales.file || sales.existing) && (purchases.file || purchases.existing) && name.trim();

  async function resolve(slot: Slot, setSlot: (s: Slot) => void, uploaded: DatasetDetail[]): Promise<number> {
    if (slot.file) {
      const dataset = await uploadFile(slot.file, (p) => setSlot({ ...slot, progress: p }));
      uploaded.push(dataset);
      setSlot({ ...slot, progress: 1 });
      return dataset.id;
    }
    return slot.existing as number;
  }

  async function create() {
    setBusy(true);
    setError(null);
    const uploaded: DatasetDetail[] = [];
    try {
      const salesId = await resolve(sales, setSales, uploaded);
      const purchasesId = await resolve(purchases, setPurchases, uploaded);
      const book = await api.createBook({ name: name.trim(), sales: [salesId], purchases: [purchasesId] });
      onCreated(book, uploaded);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="books-upload">
      <div className="slots">
        <SlotCard title="Sales register" hint="Invoices to customers (output GST)" slot={sales} setSlot={setSales} datasets={datasets} busy={busy} />
        <SlotCard title="Purchase register" hint="Bills from suppliers (input GST)" slot={purchases} setSlot={setPurchases} datasets={datasets} busy={busy} />
      </div>
      <div className="report-params">
        <label className="field grow">
          <span>Name for this set</span>
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={120} placeholder="e.g. FY 2025-26" />
        </label>
        <button className="button primary" onClick={() => void create()} disabled={!ready || busy}>
          {busy ? "Uploading and comparing…" : "Compare sales and purchases"}
        </button>
      </div>
      {error ? (
        <div className="callout error" role="alert">
          {error}
        </div>
      ) : null}
    </div>
  );
}

function SlotCard({
  title,
  hint,
  slot,
  setSlot,
  datasets,
  busy,
}: {
  title: string;
  hint: string;
  slot: Slot;
  setSlot: (s: Slot) => void;
  datasets: DatasetSummary[];
  busy: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  function choose(file: File | undefined) {
    if (!file) return;
    const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    if (!ACCEPTED.includes(ext)) {
      setProblem(`"${file.name}" is not a spreadsheet.`);
      return;
    }
    setProblem(null);
    setSlot({ file, existing: null, progress: null });
  }

  return (
    <div className="slot">
      <h3>{title}</h3>
      <p className="muted small">{hint}</p>
      <div
        className={`dropzone small-drop${dragging ? " dragging" : ""}${slot.file ? " filled" : ""}`}
        role="button"
        tabIndex={0}
        aria-label={`Choose the ${title.toLowerCase()} file`}
        onClick={() => !busy && input.current?.click()}
        onKeyDown={(e) => {
          if ((e.key === "Enter" || e.key === " ") && !busy) {
            e.preventDefault();
            input.current?.click();
          }
        }}
        onDragOver={(e: DragEvent) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e: DragEvent) => {
          e.preventDefault();
          setDragging(false);
          if (!busy) choose(e.dataTransfer.files[0]);
        }}
      >
        <input ref={input} type="file" accept={ACCEPTED.join(",")} hidden onChange={(e) => {
          choose(e.target.files?.[0]);
          e.target.value = "";
        }} />
        {slot.file ? (
          <>
            <p className="file-name">{slot.file.name}</p>
            <p className="muted small">{formatBytes(slot.file.size)}</p>
            {slot.progress !== null ? (
              <div className="progress">
                <div className="progress-bar" style={{ width: `${Math.round(slot.progress * 100)}%` }} />
              </div>
            ) : (
              <span className="link small">Change file</span>
            )}
          </>
        ) : (
          <>
            <p className="dropzone-title">
              Drop the Excel file or <span className="link">browse</span>
            </p>
            <p className="muted small">.xlsx · .xls · .csv</p>
          </>
        )}
      </div>
      {problem ? <p className="error-text small">{problem}</p> : null}
      {datasets.length ? (
        <label className="field">
          <span>…or use a file already uploaded</span>
          <select
            value={slot.existing ?? ""}
            onChange={(e) => setSlot({ file: null, existing: e.target.value ? Number(e.target.value) : null, progress: null })}
            disabled={busy}
          >
            <option value="">—</option>
            {datasets.map((d) => (
              <option key={d.id} value={d.id}>
                {d.filename} ({d.row_count} rows)
              </option>
            ))}
          </select>
        </label>
      ) : null}
    </div>
  );
}
