import { useState, type ReactNode } from "react";
import { purityCode } from "../../books";
import { readAmount } from "../../components/accounts/shared";
import type { EntryKind } from "../../router";
import type { Metal } from "../../types";
import { AutoValue, Button, Card, Field, FieldRow, Input, Notice, Segmented, Select } from "../../ui";
import type { AddRequest } from "./AddNameSheet";
import { GST_DEFAULT, type FieldKey } from "./form";
import { grams, gramsText, money } from "./money";
import { TotalPanel } from "./TotalPanel";
import type { useEntry } from "./useEntry";

type Props = { entry: ReturnType<typeof useEntry>; kind: EntryKind; ask: (request: AddRequest) => void };

const OTHER = "__other";
const METALS: { value: Metal; label: string }[] = [
  { value: "gold", label: "Gold" },
  { value: "silver", label: "Silver" },
];

/** Weights, purity, rates and the live bill: the design's "Weight & rates" card. */
export function WeightCard({ entry, kind, ask }: Props) {
  const { form, set, errors, idOf, figures: f, books, general, saving } = entry;
  const [editGst, setEditGst] = useState(form.gst !== GST_DEFAULT);
  const sale = kind === "sale";
  const rs = form.settle === "Rs";
  const tunch = readAmount(form.purity);
  const karat = form.metal === "gold" && Number.isFinite(tunch) ? purityCode(tunch) : "";
  const purities = books.masters.purity.includes(form.purity) || !form.purity ? books.masters.purity : [...books.masters.purity, form.purity];
  const netTyped = form.net !== null;
  const taxedOn = ["labour", "diamond", ...(f.stone ? ["stones"] : []), ...(rs ? ["metal"] : [])].join(" + ");
  const split = !f.tax ? undefined : f.interState ? `IGST ${money(f.igst)}` : `CGST ${money(f.cgst)} + SGST ${money(f.sgst)}`;

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
        <Segmented variant="metal" label="Metal" options={METALS} value={form.metal} onChange={(metal) => set({ metal })} />
      </div>

      <FieldRow>
        {num("gross", "Gross weight (g)", "0.000")}
        <Field
          label="Net weight (g)"
          htmlFor={idOf("net")}
          error={errors.net}
          hint={
            netTyped && f.autoNetMg > 0 && f.autoNetMg !== f.netMg ? (
              <button type="button" className="entry-link" onClick={() => set({ net: null })}>
                Use auto ({grams(f.autoNetMg)})
              </button>
            ) : netTyped && f.grossMg && f.netMg > f.grossMg ? (
              "More than the gross weight"
            ) : !netTyped && (form.diamondCt || form.stoneCt) ? (
              "gross − stones × 0.2 g/ct"
            ) : undefined
          }
        >
          <Input
            id={idOf("net")}
            inputMode="decimal"
            enterKeyHint="next"
            autoComplete="off"
            placeholder="0.000"
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
          {!form.purity ? <option value="">Choose…</option> : null}
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

      <Field label="Settle metal">
        <Segmented
          label="Settle the metal"
          value={form.settle}
          onChange={(settle) => set({ settle })}
          options={[
            { value: "Wt", label: "By weight" },
            { value: "Rs", label: "In rupees" },
          ]}
        />
      </Field>

      {rs ? (
        <>
          {num("metalRate", `${form.metal === "gold" ? "Gold" : "Silver"} rate (₹/g fine)`, "0")}
          <Field label="Metal value">
            <AutoValue value={money(f.metalValue)} note="fine wt × rate" />
          </Field>
        </>
      ) : null}

      <FieldRow>
        {num("diamondCt", "Diamond (ct)")}
        {num("diamondRate", "Diamond rate (₹/ct)")}
      </FieldRow>
      <FieldRow>
        {num("stoneCt", "Stone (ct)")}
        {num("stoneRate", "Stone rate (₹/ct)")}
      </FieldRow>
      {num("labourRate", "Labour rate (₹/g)")}

      <Field label="Labour amount">
        <AutoValue value={money(f.labour)} note="net wt × labour rate" />
      </Field>
      <Field label="Diamond amount">
        <AutoValue value={money(f.diamond)} note="rate × carats" />
      </Field>
      {f.stone || form.stoneCt ? (
        <Field label="Stone amount">
          <AutoValue value={money(f.stone)} note="rate × carats" />
        </Field>
      ) : null}

      <Field
        label={
          <span className="entry-labelrow">
            <span>GST {form.gst.trim() || "0"}%</span>
            {!editGst ? (
              <button type="button" className="entry-link" onClick={() => setEditGst(true)}>
                Change rate
              </button>
            ) : null}
          </span>
        }
        error={errors.gst}
        hint={split}
      >
        {editGst ? (
          <Input
            id={idOf("gst")}
            inputMode="decimal"
            enterKeyHint="next"
            autoComplete="off"
            aria-label="GST rate %"
            value={form.gst}
            onChange={(event) => set({ gst: event.target.value })}
            aria-invalid={Boolean(errors.gst) || undefined}
          />
        ) : null}
        <AutoValue value={money(f.tax)} note={`on ${taxedOn}`} />
      </Field>

      <TotalPanel figures={f} form={form} sale={sale} />

      {general ? <Notice tone="error">{general}</Notice> : null}
      <Button variant="primary" size="lg" block type="submit" busy={saving}>
        {saving ? "Saving…" : sale ? "Save sale" : "Save purchase"}
      </Button>
      <p className="entry-note">Posted to the books as a GST invoice · number given if left blank</p>
    </Card>
  );
}
