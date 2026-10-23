"""Check that every figure in an AI answer comes from a query or calculation result.

Language models can slip when copying or doing arithmetic, so after each answer every
number in the text is compared with the numbers the tools actually returned (and the
numbers in the conversation). A figure counts as verified when it equals one of those
values as shown at the answer's precision. Thousand / lakh / million / crore scaling applies
only when that unit is written after the number; a figure written with a minus sign or in
brackets must match a negative value; a percentage may also be a fraction times 100. A figure
may also be the sum or difference (for a percentage, the ratio) of two figures that are already
confirmed or are overall totals. Anything else is reported as unverified.
"""

import math
import re

import numpy as np

_SCALE = {
    "thousand": 1e3, "k": 1e3,
    "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5, "l": 1e5,
    "million": 1e6, "mn": 1e6,
    "crore": 1e7, "crores": 1e7, "cr": 1e7, "cr.": 1e7,
    "billion": 1e9, "bn": 1e9,
}
# These abbreviations also mean karat (22K), litre or a credit balance (1,23,456.00 Cr), so the
# number may stand at face value too.
_AMBIGUOUS = {"k", "l", "cr", "cr."}
_CURRENCY_MARK = "\x00"  # stands in for ₹ / Rs / INR, so "(₹1,234)" is not mistaken for a negative "(1,234)"
_UNIT = r"(?:(?i:thousand|lakhs?|lacs?|lakh|million|mn|crores?|cr\.?|billion|bn)|[kK]|L)"
# Numbers as people write them: -1,23,456.78  1,234,567  12.5%  35.37 lakh  2.5Cr  500/-.
# Digits glued to letters, hyphens or slashes (GSTR-3B, 26AS, 194C, S/0071, INV-2025-001) are identifiers.
_NUMBER = re.compile(
    r"(?<![\w.,/−-])(?P<sign>[-−]\x00?)?"
    r"(?P<number>\d{1,2}(?:,\d{2})*,\d{3}(?:\.\d+)?|\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?!\d|\.\d|,\d)"
    rf"(?:\s?(?P<percent>%)|\s?(?P<unit>{_UNIT})(?!\w)|(?!\w|/(?!-)))"
)
_MONTH = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
    r"|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?(?![a-z])"
)
_DATES = re.compile(
    r"\b\d{4}-\d{1,2}(?:-\d{1,2})?\b"  # 2025-04-01, 2025-04
    r"|\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b"  # 01/04/2025
    rf"|\b\d{{1,2}}(?:st|nd|rd|th)?\s+{_MONTH}(?:,?\s+\d{{4}}\b|['’]\d{{2}}\b)?"  # 1 April 2025
    rf"|\b{_MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,\s*\d{{4}})?\b(?![.,]?\d)"  # April 1, 2025
    rf"|\b{_MONTH}['’,]?\s*\d{{2,4}}\b(?![.,]?\d)"  # May 2025, Apr'25
    r"|\bFY\s?\d{2,4}(?:-\d{2,4})?\b"
    r"|\bQ[1-4]\b",
    re.IGNORECASE,
)
# Legal references and document numbers: Section 49, Rule 88A, Rules 42 and 43, Table 3.1(a), Form 26AS,
# u/s 194C, Invoice No. 45. They are not amounts.
_REF = r"\d+(?:\.\d+)*[A-Za-z]*(?:\([0-9A-Za-z]+\))*(?![.,]?\d)"
_REFERENCES = re.compile(
    r"(?:\b(?:sections?|secs?\.?|rules?|tables?|form|schedules?|articles?|clauses?|chapters?|paras?|paragraphs?"
    r"|annexures?|notifications?|circulars?)\s+"
    r"|\bu/s\.?\s*"
    r"|\b(?:invoice|inv|bill|voucher|challan|sr|s|serial|ref|entry|order|receipt)\.?\s*(?:no\.?|number|#)\s*[-#:]?\s*)"
    rf"{_REF}(?:\s*(?:,|&|and|or|to)\s*{_REF})*(?!\s?%)",
    re.IGNORECASE,
)
_CURRENCY = re.compile(r"₹\s*|\b(?:Rs|INR)\b\.?\s*(?=[-−]?\d)", re.IGNORECASE)
_LIST_MARKER = re.compile(r"^\s*\d+[.)]\s", re.MULTILINE)
_TOTAL_ROWS = 25  # a tool result this short holds totals, not a listing, so its values may be combined


def _figures(text: str) -> list[dict]:
    """Every number worth checking, with its sign, unit scale and the precision it is written at."""
    cleaned = _CURRENCY.sub(_CURRENCY_MARK, text)
    cleaned = _LIST_MARKER.sub(" ", _REFERENCES.sub(" ", _DATES.sub(" ", cleaned)))
    out = []
    for match in _NUMBER.finditer(cleaned):
        number = match.group("number")
        face = float(number.replace(",", ""))
        decimals = len(number.split(".")[1]) if "." in number else 0
        percent = bool(match.group("percent"))
        unit = (match.group("unit") or "").lower()
        # (1,234.00) in accounts is a negative amount; "(about 11.93 lakh)", "(45.99%)" or "(39 entries)" is an aside.
        bracketed = (
            not unit and not percent and not match.group("sign") and (decimals or "," in number)
            and cleaned[:match.start()].rstrip().endswith("(") and cleaned[match.end():].lstrip().startswith(")")
        )
        negative = bool(match.group("sign")) or bracketed
        if not percent and not unit and decimals == 0 and "," not in number:
            # Small counts ("top 5") and bare years are too ambiguous to check.
            if face < 10 or 1900 <= face <= 2100:
                continue
        sign = -1.0 if negative else 1.0
        half_unit = 0.5 * 10 ** (-decimals)
        readings = [(sign * face * _SCALE[unit], half_unit * _SCALE[unit])] if unit else []
        if not unit or unit in _AMBIGUOUS:
            readings.append((sign * face, half_unit))
        token = match.group(0).replace(_CURRENCY_MARK, "").strip()
        out.append({
            "token": f"({token})" if bracketed else token,
            "readings": readings,  # (value, half a unit in the last place written), most likely first
            "face": face,
            "decimals": decimals,
            "percent": percent,
            "signed": negative,
        })
    return out


def figures_in(text: str) -> list[tuple[str, float, int, bool]]:
    """(original text, value, decimals shown, is percent) for each number worth checking; value includes the unit."""
    return [(f["token"], f["readings"][0][0], f["decimals"], f["percent"]) for f in _figures(text)]


_WESTERN = re.compile(r"(?<![\d,.])(\d{1,3}(?:,\d{3})+)(\.\d+)?(?![\d,])")


def indian_digits(text: str) -> str:
    """Rewrite Western digit grouping as Indian (2,328,413.00 -> 23,28,413.00); smaller numbers look the same."""
    def regroup(match: re.Match) -> str:
        whole = int(match.group(1).replace(",", ""))
        if whole < 100_000:
            return match.group(0)
        digits = str(whole)
        head, tail = digits[:-3], digits[-3:]
        pairs = [head[max(0, i - 2):i] for i in range(len(head), 0, -2)][::-1]
        return ",".join(pairs + [tail]) + (match.group(2) or "")

    return _WESTERN.sub(regroup, text)


class Known(list):
    """Values an answer may quote, plus ``totals``: the ones it may also combine (add, subtract, divide). Totals
    are the conversation and data-dictionary figures and the values of tool results of at most 25 rows;
    combining any two cells of a 500-row listing would let almost any amount through."""

    def __init__(self, values=(), totals=()):
        super().__init__(values)
        self.totals = list(totals)


def _text_values(text: str) -> list[float]:
    return [value for f in _figures(text) for value, _ in f["readings"]]


def _cell_values(cell) -> list[float]:
    if isinstance(cell, bool) or cell is None:
        return []
    if isinstance(cell, (int, float)):
        return [float(cell)] if math.isfinite(cell) else []
    if isinstance(cell, str):
        try:
            value = float(cell.replace(",", ""))
            return [value] if math.isfinite(value) else []
        except ValueError:
            # Numbers inside text values (a purity "14K", an item "Ring 22ct") are in the data too.
            return _text_values(cell)
    return []


def _results(rows: list) -> list[list[list]]:
    """Split tool output into separate results. Rows may come grouped (one list of rows per tool call) or flat;
    in a flat list each run of consecutive rows of the same width is taken as one result."""
    results: list[list[list]] = []
    flat_width = None  # width of the flat run being collected, None when the last result was grouped
    for row in rows:
        if isinstance(row, (list, tuple)) and row and all(isinstance(r, (list, tuple)) for r in row):
            results.append([list(r) for r in row])
            flat_width = None
            continue
        row = list(row) if isinstance(row, (list, tuple)) else [row]
        if flat_width == len(row):
            results[-1].append(row)
        else:
            results.append([row])
            flat_width = len(row)
    return results


def known_values(texts: list[str], rows: list[list]) -> list[float]:
    """Numbers the answer may legitimately use: those in the conversation and every cell the tools returned."""
    values: list[float] = []
    totals: list[float] = []
    for text in texts:
        found = _text_values(text)
        values += found
        totals += found
    for result in _results(rows):
        cells = [value for row in result for cell in row for value in _cell_values(cell)]
        values += cells
        if len(result) <= _TOTAL_ROWS:
            totals += cells
    return Known(values, totals)


def _sorted(values, unique: bool = True) -> np.ndarray:
    array = np.fromiter(values, dtype=np.float64, count=len(values))
    array = array[np.isfinite(array)]
    return np.unique(array) if unique else np.sort(array)


def _within(array: np.ndarray, targets: np.ndarray, tolerance) -> tuple[np.ndarray, np.ndarray]:
    """Index range [low, high) of the sorted array within the tolerance of each target."""
    return (np.searchsorted(array, targets - tolerance, side="left"),
            np.searchsorted(array, targets + tolerance, side="right"))


def _slack(value: float, half_unit: float) -> float:
    return half_unit * (1 + 1e-9) + 1e-9 * max(1.0, abs(value))


def _targets(figure: dict, value: float) -> list[float]:
    # Unsigned prose ("purchases exceeded sales by 2,07,740.31") may quote a negative value; a written minus may not.
    return [value] if figure["signed"] else [value, -value]


def _direct(figure: dict, known: np.ndarray) -> float | None:
    """The reading of the figure that a known value confirms, or None."""
    for value, half_unit in figure["readings"]:
        tolerance = _slack(value, half_unit)
        targets = np.array(_targets(figure, value))
        low, high = _within(known, targets, tolerance)
        if np.any(high > low):
            return value
        if figure["percent"]:
            # 45.99% may be stored as the fraction 0.4599.
            low, high = _within(known, targets / 100, tolerance / 100)
            if np.any(high > low):
                return value
    return None


_SHARE = 0.01  # in a + b or a - b each operand must be at least 1% of the result, so total + 12 rows is no sum


def _cases(figures: list[dict]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Every (figure index, target value, tolerance) to try: each reading, and its negative when unsigned."""
    owner, targets, tolerances = [], [], []
    for index, figure in enumerate(figures):
        for value, half_unit in figure["readings"]:
            for target in _targets(figure, value):
                owner.append(index)
                targets.append(target)
                tolerances.append(_slack(value, half_unit))
    return np.array(owner, dtype=np.int64), np.array(targets), np.array(tolerances)


def _sums(figures: list[dict], operands: np.ndarray) -> np.ndarray:
    """For each figure, whether it is a + b or a - b of two different operands, e.g. a net GST of
    12,060.10 = 26,100.10 - 14,040.00. All figures are looked up together, one row of operands each."""
    found = np.zeros(len(figures), dtype=bool)
    if len(operands) < 2 or not figures:
        return found
    owner, targets, tolerances = _cases(figures)
    target, tolerance = targets[:, None], tolerances[:, None]
    smallest = _SHARE * np.abs(target)
    a = operands[None, :]
    count = len(operands)
    positions = np.arange(count)[None, :]
    hit = np.zeros(len(targets), dtype=bool)
    for wanted in (target - a, a - target):  # b for target = a + b, and for target = a - b
        low = np.searchsorted(operands, wanted - tolerance)
        other = np.zeros(wanted.shape, dtype=bool)
        # The operands within the tolerance start at low; if that one is a itself, the next may be b.
        # b must be another operand than a: a - a = 0 proves nothing.
        for index in (low, low + 1):
            other |= (index < count) & (index != positions) & (operands[np.minimum(index, count - 1)] <= wanted + tolerance)
        hit |= (other & (np.abs(a) >= smallest) & (np.abs(wanted) >= smallest)).any(axis=1)
    np.logical_or.at(found, owner, hit)
    return found


def _ratios(figures: list[dict], stated: np.ndarray, operands: np.ndarray) -> np.ndarray:
    """For each percentage, whether it is a / b x 100 where a or b is a figure the answer itself states."""
    found = np.zeros(len(figures), dtype=bool)
    if not figures or not len(stated) or not len(operands):
        return found
    with np.errstate(divide="ignore", invalid="ignore"):
        ratios = np.concatenate([(stated[:, None] / operands[None, :]).ravel(),
                                 (operands[:, None] / stated[None, :]).ravel()]) * 100
        same = np.concatenate([(stated[:, None] == operands[None, :]).ravel(),
                               (operands[:, None] == stated[None, :]).ravel()])
    ratios = np.sort(ratios[~same & np.isfinite(ratios)])
    owner, targets, tolerances = _cases(figures)
    low, high = _within(ratios, targets, tolerances)
    np.logical_or.at(found, owner, high > low)
    return found


def _precise(figure: dict) -> bool:
    # Arithmetic counts only for figures precise enough that a coincidence is unlikely.
    return figure["percent"] or figure["decimals"] > 0 or figure["face"] >= 1000


def verify(answer: str, known: list[float]) -> dict:
    figures = _figures(answer)
    values = _sorted(known, unique=False)
    direct = [_direct(f, values) for f in figures]
    unverified = []
    if any(value is None for value in direct):
        totals = getattr(known, "totals", None)
        if totals is None:
            # A plain list has no structure: it counts as one result, so only a short one holds totals.
            totals = known if len(known) <= _TOTAL_ROWS else []
        # A derived figure may combine figures the answer states (and that check out) or overall totals,
        # never two arbitrary cells of a long listing. Percentages add and subtract only with each other.
        amounts = [v for f, v in zip(figures, direct) if v is not None and not f["percent"]]
        percents = _sorted([v for f, v in zip(figures, direct) if v is not None and f["percent"]])
        operands = _sorted(list(totals) + amounts)
        stated = _sorted(amounts)
        open_amounts = [f for f, v in zip(figures, direct) if v is None and not f["percent"] and _precise(f)]
        open_percents = [f for f, v in zip(figures, direct) if v is None and f["percent"]]
        derived = {id(f) for f, ok in zip(open_amounts, _sums(open_amounts, operands)) if ok}
        derived |= {id(f) for f, ok in zip(open_percents, _sums(open_percents, percents) | _ratios(open_percents, stated, operands)) if ok}
        unverified = [f["token"] for f, v in zip(figures, direct) if v is None and id(f) not in derived]
    unique = list(dict.fromkeys(unverified))
    if not figures:
        status = "no_figures"
    elif unique:
        status = "unverified"
    else:
        status = "verified"
    return {"status": status, "figures": len(figures), "unverified": unique}
