import { useEffect, useId, useState, type FormEvent } from "react";
import { Button, Field, Input, Sheet } from "../../ui";

export type AddRequest = {
  title: string; // "New customer"
  label: string; // "Customer name"
  initial: string;
  /** Customers and suppliers can carry a GSTIN (it sets the state, so CGST + SGST or IGST). */
  withGstin?: boolean;
  /** A number (purity %) rather than a name. */
  numeric?: boolean;
  description?: string;
  submit: (name: string, gstin: string) => Promise<void> | void;
};

/** "Add new" for the entry lists: a name (and a GSTIN for a party). Errors from the server stay in the sheet. */
export function AddNameSheet({ request, onClose }: { request: AddRequest | null; onClose: () => void }) {
  const nameId = useId();
  const gstinId = useId();
  const [name, setName] = useState("");
  const [gstin, setGstin] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!request) return;
    setName(request.initial);
    setGstin("");
    setError(null);
    setBusy(false);
  }, [request]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!request || busy) return;
    if (!name.trim()) {
      setError(request.numeric ? "Enter the purity." : "Enter a name.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await request.submit(name.trim(), gstin.trim().toUpperCase());
      onClose();
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };

  return (
    <Sheet open={request !== null} onClose={onClose} title={request?.title ?? ""} description={request?.description}>
      <form className="entry-add" onSubmit={submit} noValidate>
        <Field label={request?.label ?? ""} htmlFor={nameId} error={error && !request?.withGstin ? error : undefined}>
          <Input
            id={nameId}
            data-autofocus
            value={name}
            onChange={(event) => setName(event.target.value)}
            inputMode={request?.numeric ? "decimal" : undefined}
            autoCapitalize={request?.numeric ? "off" : "words"}
            autoComplete="off"
            enterKeyHint={request?.withGstin ? "next" : "done"}
            maxLength={request?.numeric ? 8 : 120}
          />
        </Field>
        {request?.withGstin ? (
          <Field label="GSTIN (optional)" htmlFor={gstinId} hint="Sets the state, so the bill gets CGST + SGST or IGST." error={error ?? undefined}>
            <Input
              id={gstinId}
              value={gstin}
              onChange={(event) => setGstin(event.target.value.toUpperCase())}
              autoCapitalize="characters"
              autoComplete="off"
              spellCheck={false}
              maxLength={15}
              placeholder="e.g. 07AABCM1234F1ZZ"
              enterKeyHint="done"
            />
          </Field>
        ) : null}
        <div className="entry-add__actions">
          <Button variant="plain" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="brand" type="submit" busy={busy}>
            Add
          </Button>
        </div>
      </form>
    </Sheet>
  );
}
