import type { ReactNode } from "react";
import { purityCode } from "../../books";
import { readAmount } from "../../components/accounts/shared";
import type { EntryKind } from "../../router";
import { AutoValue, Button, Card, Field, FieldRow, Input, Notice, Select } from "../../ui";
import type { AddRequest } from "./AddNameSheet";
import type { FieldKey } from "./form";
import { grams, gramsText, money } from "./money";
import { TotalPanel } from "./TotalPanel";
import type { useEntry } from "./useEntry";

type Props = { entry: ReturnType<typeof useEntry>; kind: EntryKind; ask: (request: AddRequest) => void };

const OTHER = "__other";

/** Weights, purity, rates and the live bill: the design's "Weight & rates" card, with only its fields (the metal and how
 * it is settled keep their defaults: gold, by weight; no stones, no GST). */
export function WeightCard({ entry, kind, ask }: Props) {
  const { form, set, errors, idOf, figures: f, books, general, saving } = entry;
  const sale = kind === "sale";
  const tunch = readAmount(form.purity);
  const karat = form.metal === "gold" && Number.isFinite(tunch) ? purityCode(tunch) : "";
  const purities = books.masters.purity.includes(form.purity) || !form.purity ? books.masters.purity : [...books.masters.purity, form.purity];
  const netTyped = form.net !== null;

  /** A number box. inputMode decimal brings up the number keyboard on phones. */
  const num = (key: FieldKey & keyof typeof form, label: string, placeholder = "0", extra: { hint?: ReactNode } = {}) => (
    <Field label={label} htmlFor={idOf(key)} error={errors[key]} hint={extra.hint}>
      <Input
        id={idOf(key)}
        inputMode="decimal"
        enterKeyHint="next"
        autoComplete="off"
        placeholder={placeholder}
        value={(form[key] as string | null) ?? ""}
        onChange={(event) => set({ [key]: event.target.value })}
        aria-invalid={Boolean(errors[key]) || undefined}
      />
    </Field>
  );

  const askPurity = () =>
    ask({
      title: "New purity",
      label: "Purity / tunch %",
      initial: "",
      numeric: true,
      description: "For example 76 or 92.5. Kept on this device.",
      submit: (text) => {
        const value = readAmount(text);
        if (!Number.isFinite(value) || value <= 0 || value > 100) throw new Error("Enter a percent more than 0 and at most 100.");
        const purity = String(value);
        books.addMaster("purity", purity);
        set({ purity });
      },
    });

  return (
    <Card>
      <div className="entry-head">
        <h2 className="entry-head__title">Weight &amp; rates</h2>
      </div>

      <FieldRow>
        {num("gross", "Gross weight")}
        <Field
          label="Net weight"
          htmlFor={idOf("net")}
          error={errors.net}
          hint={
            netTyped && f.autoNetMg > 0 && f.autoNetMg !== f.netMg ? (
              <button type="button" className="entry-link" onClick={() => set({ net: null })}>
                Use auto ({grams(f.autoNetMg)})
              </button>
            ) : netTyped && f.grossMg && f.netMg > f.grossMg ? (
              "More than the gross weight"
            ) : !netTyped && form.diamondCt ? (
              "gross − diamond × 0.2 g/ct"
            ) : undefined
          }
        >
          <Input
            id={idOf("net")}
            inputMode="decimal"
            enterKeyHint="next"
            autoComplete="off"
            placeholder="0"
            className={netTyped ? undefined : "entry-auto-input"}
            value={form.net ?? (f.autoNetMg > 0 ? gramsText(f.autoNetMg) : "")}
            onFocus={(event) => !netTyped && event.target.select()}
            onChange={(event) => set({ net: event.target.value.trim() ? event.target.value : null })}
            aria-invalid={Boolean(errors.net) || undefined}
          />
        </Field>
      </FieldRow>

      <Field label="Purity %" htmlFor={idOf("purity")} error={errors.purity}>
        <Select
          id={idOf("purity")}
          value={form.purity}
          tag={karat.endsWith("K") ? karat : undefined}
          onChange={(event) => (event.target.value === OTHER ? askPurity() : set({ purity: event.target.value }))}
          aria-invalid={Boolean(errors.purity) || undefined}
        >
          {!form.purity ? <option value="">Select</option> : null}
          {purities.map((p) => (
            <option key={p} value={p}>
              {p}%
            </option>
          ))}
          <option value={OTHER}>Other…</option>
        </Select>
      </Field>

      <Field label="Fine weight">
        <AutoValue value={grams(f.fineMg)} note="net wt × purity %" tone="gold" />
      </Field>

      <FieldRow>
        {num("diamondCt", "Diamond weight")}
        {num("diamondRate", "Diamond rate")}
      </FieldRow>
      {num("labourRate", "Labour rate")}

      <Field label="Labour amount">
        <AutoValue value={money(f.labour)} note="net wt × labour rate" />
      </Field>
      <Field label="Diamond amount">
        <AutoValue value={money(f.diamond)} note="rate × weight" />
      </Field>

      <TotalPanel figures={f} />

      {general ? <Notice tone="error">{general}</Notice> : null}
      <Button variant="primary" size="lg" block type="submit" busy={saving}>
        {saving ? "Saving…" : sale ? "Save sale" : "Save purchase"}
      </Button>
      <p className="entry-note">Posted to the books · bill number given if left blank</p>
    </Card>
  );
}
