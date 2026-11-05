import { Card, Field, FieldRow, Input } from "../../ui";
import { itemKey, KARATS, type EntryItem, type FieldKey, type ItemField, type LabourBasis } from "./form";
import type { AddRequest } from "./AddNameSheet";
import { gramsText } from "./money";
import { Picker } from "./Picker";
import type { useEntry } from "./useEntry";

type Props = {
  entry: ReturnType<typeof useEntry>;
  ask: (request: AddRequest) => void;
  item: EntryItem;
  index: number;
  /** id of the <datalist> of item names. */
  itemList: string;
};

type Worked = "net" | "diaValue" | "stnValue" | "labourValue";
type Words = "name" | "code" | "design" | "diaShape" | "diaColour" | "diaClarity" | "stnShape" | "stnColour" | "stnClarity";
type Figure = "gross" | "purity" | "diaCt" | "diaRate" | "stnCt" | "stnRate" | "labourRate";

const rupeesText = (paise: number) => (paise / 100).toFixed(paise % 100 ? 2 : 0);

/** One item of the bill: the design's Item, Gold, Diamond, Color Stone and Labour cards. */
export function ItemCards({ entry, ask, item, index, itemList }: Props) {
  const { setItem, removeItem, errors, idOf, figures, form, books } = entry;
  const f = figures.items[index];
  const many = form.items.length > 1;
  const set = (patch: Partial<EntryItem>) => setItem(item.id, patch);
  const id = (field: string) => idOf(`${item.id}:${field}` as FieldKey);
  const error = (field: ItemField) => errors[itemKey(item, field)];

  /** A text box (names, codes, shapes, grading). */
  const words = (field: Words, label: string, extra: { list?: string; upper?: boolean } = {}) => (
    <Field label={label} htmlFor={id(field)} error={field === "name" ? error("name") : undefined}>
      <Input
        id={id(field)}
        value={item[field]}
        onChange={(event) => set({ [field]: event.target.value })}
        list={extra.list}
        autoCapitalize={extra.upper ? "characters" : "words"}
        autoComplete="off"
        spellCheck={false}
        maxLength={field === "name" ? 120 : field === "code" || field === "design" ? 40 : 20}
        enterKeyHint="next"
        aria-invalid={field === "name" ? Boolean(error("name")) || undefined : undefined}
      />
    </Field>
  );

  /** A number box. inputMode decimal brings up the number keyboard on phones. */
  const figure = (field: Figure, label: string) => (
    <Field label={label} htmlFor={id(field)} error={error(field)}>
      <Input
        id={id(field)}
        inputMode="decimal"
        enterKeyHint="next"
        autoComplete="off"
        placeholder="0"
        value={item[field]}
        onChange={(event) => set({ [field]: event.target.value })}
        aria-invalid={Boolean(error(field)) || undefined}
      />
    </Field>
  );

  /** A worked-out number (net from gross, a value from weight × rate): shown dashed until typed over; cleared, it is
   * worked out again. */
  const worked = (field: Worked, label: string, auto: string) => {
    const own = item[field] !== null;
    return (
      <Field label={label} htmlFor={id(field)} error={error(field)}>
        <Input
          id={id(field)}
          inputMode="decimal"
          enterKeyHint="next"
          autoComplete="off"
          placeholder="0"
          className={own ? undefined : "entry-auto-input"}
          value={item[field] ?? auto}
          onFocus={(event) => !own && event.target.select()}
          onChange={(event) => set({ [field]: event.target.value.trim() ? event.target.value : null })}
          aria-invalid={Boolean(error(field)) || undefined}
        />
      </Field>
    );
  };

  // The design's karats, then the shop's own, then a karat this item has that neither lists (a draft).
  const karats = [...KARATS.map(([k]) => k), ...(books.masters.karat ?? []), item.karat].filter((k, i, all) => k && all.indexOf(k) === i);

  /** Choosing a karat fills the purity while it is empty, or still the last karat's own purity. */
  const chooseKarat = (karat: string) => {
    const before = KARATS.find(([k]) => k === item.karat)?.[1];
    const fill = KARATS.find(([k]) => k === karat)?.[1];
    set({ karat, ...(fill && (!item.purity.trim() || item.purity === before) ? { purity: fill } : {}) });
  };

  const stone = (prefix: "dia" | "stn", title: string, value: number) => (
    <Card title={title}>
      <FieldRow>
        {words(`${prefix}Shape`, "Shape")}
        {worked(`${prefix}Value`, "Value", value ? rupeesText(value) : "")}
      </FieldRow>
      <FieldRow>
        {words(`${prefix}Colour`, "Color", { upper: true })}
        {words(`${prefix}Clarity`, "Clarity", { upper: true })}
      </FieldRow>
      <FieldRow>
        {figure(`${prefix}Ct`, "Weight")}
        {figure(`${prefix}Rate`, "Rate")}
      </FieldRow>
    </Card>
  );

  return (
    <>
      {many ? (
        <div className="entry-itemhead">
          <b>Item {index + 1}</b>
          <button type="button" className="entry-itemhead__rm" onClick={() => removeItem(item.id)}>
            Remove
          </button>
        </div>
      ) : null}

      <Card>
        {words("name", "Item name", { list: itemList })}
        {words("code", "Jewell code", { upper: true })}
        {words("design", "Design no.", { upper: true })}
      </Card>

      <Card title="Gold">
        <FieldRow>
          {figure("gross", "Gross weight")}
          {worked("net", "Net weight", f.autoNetMg > 0 ? gramsText(f.autoNetMg) : "")}
        </FieldRow>
        <FieldRow>
          {figure("purity", "Purity %")}
          <Field label="Karat" htmlFor={id("karat")}>
            <Picker
              id={id("karat")}
              value={item.karat}
              options={karats.map((karat) => ({ value: karat, label: karat }))}
              onSelect={chooseKarat}
              placeholder="Select"
              onAdd={(typed) =>
                ask({
                  title: "New karat",
                  label: "Karat",
                  initial: typed,
                  description: "For example 20K or 9K. Kept on this device.",
                  submit: (name) => {
                    const karat = name.trim().toUpperCase().replace(/^(\d+)$/, "$1K");
                    if (!karat) throw new Error("Enter the karat.");
                    books.addMaster("karat", karat);
                    chooseKarat(karat);
                  },
                })
              }
            />
          </Field>
        </FieldRow>
      </Card>

      {stone("dia", "Diamond", f.autoDiamond)}
      {stone("stn", "Color Stone", f.autoStone)}

      <Card title="Labour">
        <FieldRow>
          {figure("labourRate", "Labour rate")}
          <Field label="Per" htmlFor={id("labourBasis")}>
            <Picker
              id={id("labourBasis")}
              value={item.labourBasis}
              options={[{ value: "gross", label: "Gr. Wt" }, { value: "net", label: "Nt. Wt." }]}
              onSelect={(basis) => set({ labourBasis: basis as LabourBasis })}
              placeholder="Select"
            />
          </Field>
        </FieldRow>
        {worked("labourValue", "Labour value", f.autoLabour ? rupeesText(f.autoLabour) : "")}
      </Card>
    </>
  );
}
