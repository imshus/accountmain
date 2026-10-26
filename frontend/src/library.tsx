import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "./api";
import { forgetChats, forgetDataset, sweepChats } from "./components/ChatPanel";
import { syncChats } from "./screens/home/chatStore";
import { useSession } from "./session";
import type { BookDetail, BookSummary, DatasetDetail, DatasetSummary, DocumentInfo, RegisterType } from "./types";

/** The uploaded Excel files and the sales + purchase sets built from them, shared by the chat, the library and the books. */

export type LibraryValue = {
  datasets: DatasetSummary[];
  books: BookSummary[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  /** A file was uploaded (or changed: rows added, notes saved): put it at the top of the list. */
  putDataset: (detail: DatasetDetail) => void;
  /** Delete an upload and its chats. The caller asks the user first. */
  deleteDataset: (id: number) => Promise<void>;
  putBook: (book: BookDetail) => void;
  /** Remove a set (the uploaded files stay) and its chats. The caller asks the user first. */
  deleteBook: (id: number) => Promise<void>;
  /** The chat's "compare sales and purchases": build a set from the conversation's detected sheets. */
  createBookFromDocuments: (documents: DocumentInfo[], name: string) => Promise<BookDetail>;
};

export function summarizeDataset(detail: DatasetDetail): DatasetSummary {
  return {
    id: detail.id,
    filename: detail.filename,
    size_bytes: detail.size_bytes,
    uploaded_at: detail.uploaded_at,
    sheet_count: detail.sheets.length,
    row_count: detail.sheets.reduce((sum, sheet) => sum + sheet.row_count, 0),
  };
}

export function summarizeBook(book: BookDetail): BookSummary {
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

const LibraryContext = createContext<LibraryValue | null>(null);

export function LibraryProvider({ children }: { children: ReactNode }) {
  const { status, epoch } = useSession();
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [books, setBooks] = useState<BookSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [list, bookList] = await Promise.all([api.datasets(), api.books()]);
      setDatasets(list);
      setBooks(bookList);
      setError(null);
      sweepChats(
        list.map((d) => d.id),
        bookList.map((b) => b.id),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  // The AI chats' copies on the server are read and sent only while connected, and read again on every reconnect.
  useEffect(() => syncChats(status === "ready", epoch), [status, epoch]);

  useEffect(() => {
    if (status === "ready") void refresh();
  }, [status, epoch, refresh]);

  const putDataset = useCallback((detail: DatasetDetail) => {
    setDatasets((list) => [summarizeDataset(detail), ...list.filter((d) => d.id !== detail.id)]);
  }, []);

  const deleteDataset = useCallback(async (id: number) => {
    await api.deleteDataset(id);
    forgetDataset(id);
    setDatasets((list) => list.filter((d) => d.id !== id));
  }, []);

  const putBook = useCallback((book: BookDetail) => {
    setBooks((list) =>
      list.some((b) => b.id === book.id) ? list.map((b) => (b.id === book.id ? summarizeBook(book) : b)) : [summarizeBook(book), ...list],
    );
  }, []);

  const deleteBook = useCallback(async (id: number) => {
    await api.deleteBook(id);
    forgetChats(`book-${id}`);
    setBooks((list) => list.filter((b) => b.id !== id));
  }, []);

  const createBookFromDocuments = useCallback(async (documents: DocumentInfo[], name: string) => {
    const created = await api.createBook({ name: name.slice(0, 80), ...bookPlan(documents) });
    let book: BookDetail;
    try {
      book = await api.setBookSheets(created.id, sheetRegisters(created, documents));
    } catch (e) {
      // A set with the wrong registers would give wrong figures: remove it.
      await api.deleteBook(created.id).catch(() => null);
      throw e;
    }
    setBooks((list) => [summarizeBook(book), ...list]);
    return book;
  }, []);

  const value = useMemo<LibraryValue>(
    () => ({ datasets, books, loading, error, refresh, putDataset, deleteDataset, putBook, deleteBook, createBookFromDocuments }),
    [datasets, books, loading, error, refresh, putDataset, deleteDataset, putBook, deleteBook, createBookFromDocuments],
  );
  return <LibraryContext.Provider value={value}>{children}</LibraryContext.Provider>;
}

export function useLibrary(): LibraryValue {
  const value = useContext(LibraryContext);
  if (!value) throw new Error("useLibrary() must be used inside <LibraryProvider>");
  return value;
}
