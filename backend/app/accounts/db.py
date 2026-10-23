"""Tables for the double-entry books. Money is stored as whole paise (INTEGER), never floats."""

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Table, Text, UniqueConstraint

from ..database import metadata

companies = Table(
    "companies",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(200), nullable=False),
    Column("gstin", String(15)),
    Column("state_code", String(2)),
    Column("fy_start", Date, nullable=False),  # first day of the current financial year (1 April)
    Column("locked_until", Date),  # vouchers on or before this date cannot be changed
    Column("created_at", DateTime(timezone=True), nullable=False),
)

ledgers = Table(
    "ledgers",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("company_id", Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("name", String(200), nullable=False),
    Column("group_name", String(60), nullable=False),
    Column("opening_paise", Integer, nullable=False, default=0),  # + = Dr, - = Cr, as at fy_start
    Column("tax_kind", String(20)),  # output_cgst, input_igst, tds_payable... for GST/TDS reports
    Column("gstin", String(15)),
    Column("state_code", String(2)),
    Column("credit_days", Integer),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("company_id", "name", name="uq_ledger_name"),
)

vouchers = Table(
    "vouchers",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("company_id", Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("vtype", String(20), nullable=False),
    Column("number", String(40), nullable=False),
    Column("date", Date, nullable=False, index=True),
    Column("narration", Text),
    Column("reference", String(60)),  # supplier's bill number, cheque/UTR number...
    Column("source", String(120), index=True),  # "manual" or "import:<table>:<rowid>" (prevents double imports)
    Column("cancelled", Boolean, nullable=False, default=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

voucher_lines = Table(
    "voucher_lines",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("voucher_id", Integer, ForeignKey("vouchers.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("position", Integer, nullable=False),
    Column("ledger_id", Integer, ForeignKey("ledgers.id"), nullable=False, index=True),
    Column("dr_paise", Integer, nullable=False, default=0),
    Column("cr_paise", Integer, nullable=False, default=0),
)

# Bill-wise details on party lines (Tally: New Ref / Agst Ref / Advance / On Account).
bill_allocations = Table(
    "bill_allocations",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("line_id", Integer, ForeignKey("voucher_lines.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("ledger_id", Integer, ForeignKey("ledgers.id"), nullable=False, index=True),
    Column("kind", String(12), nullable=False),  # new | against | advance | on_account
    Column("bill_ref", String(60)),
    Column("amount_paise", Integer, nullable=False),  # + = Dr, - = Cr
    Column("bill_date", Date),
    Column("due_date", Date),
)

bank_lines = Table(
    "bank_lines",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("company_id", Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("bank_ledger_id", Integer, ForeignKey("ledgers.id"), nullable=False, index=True),
    Column("date", Date, nullable=False),
    Column("narration", Text),
    Column("reference", String(80)),
    Column("withdrawal_paise", Integer, nullable=False, default=0),
    Column("deposit_paise", Integer, nullable=False, default=0),
    Column("balance_paise", Integer),
    Column("source", String(120)),
    Column("matched_line_id", Integer, ForeignKey("voucher_lines.id", ondelete="SET NULL")),
    Column("match_note", String(120)),
)

audit_log = Table(
    "audit_log",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("company_id", Integer, nullable=False, index=True),
    Column("at", DateTime(timezone=True), nullable=False),
    Column("action", String(20), nullable=False),  # create | update | cancel | delete | import | lock
    Column("entity", String(20), nullable=False),  # voucher | ledger | company | bank
    Column("entity_id", Integer),
    Column("before_json", Text),
    Column("after_json", Text),
)

# Metal (gold / silver) moved by a voucher, in whole milligrams of FINE metal (net weight x tunch / 100).
# Like rupee lines, a voucher's metal debits equal its metal credits for each metal. A party's metal
# balance is what it owes us (Dr) or we owe it (Cr) in fine weight; the stock ledger's is metal in hand.
metal_lines = Table(
    "metal_lines",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("voucher_id", Integer, ForeignKey("vouchers.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("position", Integer, nullable=False),
    Column("ledger_id", Integer, ForeignKey("ledgers.id"), nullable=False, index=True),
    Column("metal", String(10), nullable=False),  # gold | silver
    Column("dr_mg", Integer, nullable=False, default=0),
    Column("cr_mg", Integer, nullable=False, default=0),
    # Item details on stock lines: weights in mg, stones in thousandths of a carat, tunch in hundredths of a percent.
    Column("item", String(120)),
    Column("purity", String(20)),
    Column("tunch_bp", Integer),
    Column("gross_mg", Integer),
    Column("net_mg", Integer),
    Column("dia_mct", Integer),
    Column("stn_mct", Integer),
    Column("pieces", Integer),
    Column("tag_no", String(40)),
)

metal_openings = Table(
    "metal_openings",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("ledger_id", Integer, ForeignKey("ledgers.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("metal", String(10), nullable=False),
    Column("opening_mg", Integer, nullable=False, default=0),  # + = Dr (owes us metal / metal in hand), as at fy_start
    UniqueConstraint("ledger_id", "metal", name="uq_metal_opening"),
)
