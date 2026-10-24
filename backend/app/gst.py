"""Indian GST rules used by the GST report: state codes, GSTIN validation and valid rates.

Sources (researched Oct 2026): GST Council 56th meeting press release (rate slabs from
22 Sept 2025), CBIC IGST Act s.7/8, Rule 88A / Circular 98/17/2019 (order of ITC use),
Section 170 CGST Act (rounding). The GSTIN check character follows the industry-standard
mod-36 algorithm (no official GSTN specification is published).
"""

from __future__ import annotations

import re
from datetime import date

STATE_CODES = {
    "01": "Jammu & Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh",
    "05": "Uttarakhand", "06": "Haryana", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh",
    "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
    "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam", "19": "West Bengal",
    "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
    "26": "Dadra & Nagar Haveli and Daman & Diu", "27": "Maharashtra", "29": "Karnataka", "30": "Goa",
    "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu", "34": "Puducherry",
    "35": "Andaman & Nicobar Islands", "36": "Telangana", "37": "Andhra Pradesh", "38": "Ladakh",
    "97": "Other Territory", "99": "Centre Jurisdiction",
}  # fmt: skip

_GSTIN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# GST 2.0 (56th GST Council): 12% and 28% slabs abolished from 22 Sept 2025 (28% stayed for
# tobacco until 31 Jan 2026). 3% (gold/jewellery), 1.5% and 0.25% (diamonds) are special rates.
GST2_DATE = date(2025, 9, 22)
RATES_BEFORE_GST2 = {0, 0.1, 0.25, 1.5, 3, 5, 6, 12, 18, 28}
RATES_FROM_GST2 = {0, 0.1, 0.25, 1.5, 3, 5, 18, 40}
TOBACCO_28_UNTIL = date(2026, 1, 31)


def gstin_check_char(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14.upper()):
        product = _CHARS.index(ch) * (1 if i % 2 == 0 else 2)
        total += product // 36 + product % 36
    return _CHARS[(36 - total % 36) % 36]


def gstin_problem(value: str) -> str | None:
    """None if the GSTIN is valid, else a short reason."""
    gstin = value.strip().upper()
    if len(gstin) != 15:
        return "must be 15 characters"
    if gstin[:2] not in STATE_CODES:
        return f"unknown state code {gstin[:2]}"
    if not _GSTIN.match(gstin):
        return "wrong format"
    if gstin_check_char(gstin[:14]) != gstin[14]:
        return "check character does not match (likely a typing error)"
    return None


def valid_rates(on: date | None) -> set[float]:
    if on is None:
        return RATES_BEFORE_GST2 | RATES_FROM_GST2
    rates = set(RATES_FROM_GST2 if on >= GST2_DATE else RATES_BEFORE_GST2)
    if GST2_DATE <= on <= TOBACCO_28_UNTIL:
        rates.add(28)  # tobacco and pan masala only
    return rates


def nearest_rate(implied: float, on: date | None) -> float | None:
    """The valid slab within 0.05 points of a rate implied by tax / taxable value, if any."""
    best = min(valid_rates(on), key=lambda r: abs(r - implied))
    return best if abs(best - implied) <= 0.05 else None
