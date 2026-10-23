import { formatCount, formatTimestamp } from "../format";
import type { DatasetSummary } from "../types";

type Props = {
  datasets: DatasetSummary[];
  activeId: number | null;
  openingId: number | null;
  onOpen: (id: number) => void;
  onDelete: (dataset: DatasetSummary) => void;
};

export default function DatasetList({ datasets, activeId, openingId, onOpen, onDelete }: Props) {
  return (
    <section className="dataset-list" aria-label="Uploaded files">
      <h2 className="eyebrow">Excel files</h2>
      {datasets.length === 0 ? (
        <p className="muted small">No files yet. Upload an Excel sheet to get started.</p>
      ) : (
        <ul>
          {datasets.map((dataset) => (
            <li key={dataset.id} className={dataset.id === activeId ? "active" : undefined}>
              <button className="dataset-item" onClick={() => onOpen(dataset.id)} disabled={openingId !== null}>
                <span className="dataset-name" title={dataset.filename}>
                  {dataset.filename}
                </span>
                <span className="muted small">
                  {openingId === dataset.id
                    ? "Opening…"
                    : `${dataset.sheet_count} sheet${dataset.sheet_count === 1 ? "" : "s"} · ${formatCount(dataset.row_count)} rows`}
                </span>
                <span className="muted small">{formatTimestamp(dataset.uploaded_at)}</span>
              </button>
              <button
                className="icon-button"
                onClick={() => onDelete(dataset)}
                aria-label={`Delete ${dataset.filename}`}
                title="Delete"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
