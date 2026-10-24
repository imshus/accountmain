"""Safe arithmetic for the calculator and for the AI's ``calculate`` tool.

Expressions are parsed with Python's ``ast`` module; only numbers, + - * /, parentheses,
unary minus, percentages and round/abs/min/max are allowed, so nothing else can run.

- ``evaluate_number`` works on plain numbers with ``Decimal``, so 0.1 + 0.2 is exactly 0.3.
- ``evaluate_columns`` works on pandas Series (one value per row) for column formulas such
  as ``taxable_value + cgst + sgst`` or ``credit - debit``.
"""

import ast
import operator
import re
from decimal import ROUND_HALF_UP, Decimal, DivisionByZero, InvalidOperation, localcontext

import numpy as np
import pandas as pd


class CalcError(ValueError):
    """The expression is invalid. The message is shown to the user."""


# A run of digits and commas such as 1,23,456.78, 250,300 or 5,2; whether its commas group digits or
# separate function arguments depends on where it stands (see _strip_grouping).
_DIGIT_RUN = re.compile(r"(?<![\w.])\d+(?:,\d+)+(?:\.\d+)?")
_GROUPING = re.compile(r"\d{1,2}(?:,\d{2})*,\d{3}|\d{1,3}(?:,\d{3})+")  # Indian 1,23,456 or Western 123,456
_MAX_ARGS = {"abs": 1, "round": 2}
_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*%")
# Rs / INR only in front of a number, so a column such as rs_amount keeps its name.
_CURRENCY = re.compile(r"(?i)₹|\b(?:rs|inr)\.?(?=\s*[-−+(]?\s*[\d.])")

_BINARY = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}
_MAX_LENGTH = 2000
_TOO_DEEP = "The expression is too long or nested too deeply. Split it into smaller steps."


def _argument_frames(text: str) -> tuple[dict[int, bool], set[int]]:
    """For each comma directly inside a function call's brackets: True when it separates arguments.
    Also the commas of abs / round calls that have more commas than arguments (see below).

    In max(1,200, 300) the spaced comma shows how the person separates arguments, so 1,200 is one
    number; in min(250,300) no comma is spaced and arguments win. abs and round fall back to digit
    grouping when the commas would give them too many arguments (round(1,234.5,2), round(12,345,2))."""
    frames: list[dict] = []
    closed: list[dict] = []
    word_start = word_end = -1  # the word just before the current position, spaces after it allowed
    for i, char in enumerate(text):
        if char.isalnum() or char == "_":
            if word_end != i:
                word_start = i
            word_end = i + 1
            continue
        if char.isspace():
            if word_end == i:
                word_end = i + 1
            continue
        if char == "(":
            name = text[word_start:word_end].strip() if word_end == i and word_start >= 0 else ""
            frames.append({"call": name if name[:1].isalpha() or name[:1] == "_" else None, "commas": []})
        elif char == ")" and frames:
            closed.append(frames.pop())
        elif char == "," and frames:
            frames[-1]["commas"].append(i)
        word_start = word_end = -1
    separators: dict[int, bool] = {}
    fitted: set[int] = set()
    for frame in closed + frames:
        commas = frame["commas"]
        if not frame["call"] or not commas:
            continue
        spaced = any(text[c - 1].isspace() or (c + 1 < len(text) and text[c + 1].isspace()) for c in commas)
        too_many = len(commas) + 1 > _MAX_ARGS.get(frame["call"], len(commas) + 1)
        for c in commas:
            # Only a comma between digits is in doubt; a spaced one always separates arguments.
            tight = not (text[c - 1].isspace() or (c + 1 < len(text) and text[c + 1].isspace()))
            separators[c] = not (tight and (spaced or too_many))
            if tight and too_many and not spaced:
                fitted.add(c)
    return separators, fitted


def _fit_grouping(whole: str) -> str:
    """round(12,345,2): read the longest digit grouping first, then the rest as arguments (12345,2)."""
    pieces = whole.split(",")
    numbers = []
    while pieces:
        take = next((n for n in range(len(pieces), 1, -1) if _GROUPING.fullmatch(",".join(pieces[:n]))), 1)
        numbers.append("".join(pieces[:take]))
        pieces = pieces[take:]
    return ",".join(numbers)


def _strip_grouping(text: str) -> str:
    """Remove thousands separators (1,23,456.78 -> 123456.78) but keep commas between function arguments."""
    if "," not in text:
        return text
    separators, fitted = _argument_frames(text)

    def regroup(match: re.Match) -> str:
        run = match.group(0)
        whole, dot, fraction = run.partition(".")
        commas = [match.start() + i for i, ch in enumerate(run) if ch == ","]
        if not any(separators.get(c, False) for c in commas):
            if _GROUPING.fullmatch(whole):
                return whole.replace(",", "") + dot + fraction
            return _fit_grouping(whole) + dot + fraction if any(c in fitted for c in commas) else run
        # Arguments: "00" or "050" is never one someone writes, so in max(1,00,000,5) it continues 1,00,000.
        numbers: list[str] = []
        for piece in whole.split(","):
            if numbers and len(piece) > 1 and piece.startswith("0"):
                numbers[-1] += "," + piece
            else:
                numbers.append(piece)
        numbers = [n.replace(",", "") if "," in n and _GROUPING.fullmatch(n) else n for n in numbers]
        return ",".join(numbers) + dot + fraction

    return _DIGIT_RUN.sub(regroup, text)


def _prepare(expression: str) -> ast.Expression:
    text = expression.strip()
    if not text:
        raise CalcError("Enter an expression, e.g. 1200 + 350 - 75.")
    if len(text) > _MAX_LENGTH:
        raise CalcError("The expression is too long.")
    # strip() again: "INR 1,200" leaves a leading space, which Python reads as an indent.
    text = _CURRENCY.sub("", text).replace("×", "*").replace("÷", "/").replace("−", "-").strip()
    text = _strip_grouping(text)
    text = _PERCENT.sub(r"(\1/100)", text)
    try:
        return ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise CalcError(f"Could not understand the expression near position {exc.offset or 0}.") from exc
    except (RecursionError, MemoryError) as exc:
        raise CalcError(_TOO_DEEP) from exc


def _round_decimal(value: Decimal, places: Decimal | int) -> Decimal:
    exponent = Decimal(1).scaleb(-int(places))
    return value.quantize(exponent, rounding=ROUND_HALF_UP)


def _number_node(node: ast.AST) -> Decimal:
    if isinstance(node, ast.Expression):
        return _number_node(node.body)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return Decimal(str(node.value))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value = _number_node(node.operand)
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
        left, right = _number_node(node.left), _number_node(node.right)
        if isinstance(node.op, ast.Div) and right == 0:
            raise CalcError("Division by zero.")
        return _BINARY[type(node.op)](left, right)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
        args = [_number_node(a) for a in node.args]
        name = node.func.id
        if name == "abs" and len(args) == 1:
            return abs(args[0])
        if name == "round" and len(args) in (1, 2):
            return _round_decimal(args[0], args[1] if len(args) == 2 else 0)
        if name in ("min", "max") and args:
            return min(args) if name == "min" else max(args)
    if isinstance(node, ast.Name):
        raise CalcError(f'"{node.id}" is not a number.')
    raise CalcError("Only numbers, + - * /, %, brackets and round/abs/min/max are allowed.")


def evaluate_number(expression: str) -> Decimal:
    """Exact decimal result of an arithmetic expression on plain numbers."""
    tree = _prepare(expression)
    with localcontext() as ctx:
        ctx.prec = 34
        try:
            result = _number_node(tree)
        except (InvalidOperation, DivisionByZero, OverflowError) as exc:
            raise CalcError("The calculation is not valid.") from exc
        except RecursionError as exc:
            raise CalcError(_TOO_DEEP) from exc
    return result.normalize() if result == result.to_integral_value() else result


def format_decimal(value: Decimal) -> str:
    """Plain decimal text (no exponent), e.g. Decimal('1.2E+3') -> '1200'."""
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _column_node(node: ast.AST, columns: dict[str, pd.Series]):
    if isinstance(node, ast.Expression):
        return _column_node(node.body, columns)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id not in columns:
            raise CalcError(f'Unknown column "{node.id}". Use the column names shown under each header.')
        return columns[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value = _column_node(node.operand, columns)
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
        left, right = _column_node(node.left, columns), _column_node(node.right, columns)
        if isinstance(node.op, ast.Div):
            right = right.replace(0, np.nan) if isinstance(right, pd.Series) else (np.nan if right == 0 else right)
        return _BINARY[type(node.op)](left, right)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
        args = [_column_node(a, columns) for a in node.args]
        name = node.func.id
        if name == "abs" and len(args) == 1:
            return np.abs(args[0])
        if name == "round" and len(args) in (1, 2):
            places = int(args[1]) if len(args) == 2 else 0
            return args[0].round(places) if isinstance(args[0], pd.Series) else round(args[0], places)
        if name in ("min", "max") and len(args) >= 2:
            combine = np.fmin if name == "min" else np.fmax
            result = args[0]
            for arg in args[1:]:
                result = combine(result, arg)
            return result
    raise CalcError("Only column names, numbers, + - * /, %, brackets and round/abs/min/max are allowed.")


def columns_in(expression: str) -> list[str]:
    """Column names used by an expression, in order of first use."""
    tree = _prepare(expression)
    names = [n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id not in {"round", "abs", "min", "max"}]
    return list(dict.fromkeys(names))


def evaluate_columns(expression: str, frame: pd.DataFrame) -> pd.Series:
    """One result per row. Empty cells count as 0 in + and -, so a blank Debit does not blank the row."""
    tree = _prepare(expression)
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} - {"round", "abs", "min", "max"}
    columns = {}
    for name in names:
        if name not in frame.columns:
            raise CalcError(f'Unknown column "{name}". Use the column names shown under each header.')
        if not pd.api.types.is_numeric_dtype(frame[name]) or pd.api.types.is_bool_dtype(frame[name]):
            raise CalcError(f'Column "{name}" is not a number column.')
        columns[name] = frame[name].astype("float64").fillna(0.0)
    if not columns:
        raise CalcError("Use at least one column name, e.g. credit - debit.")
    try:
        result = _column_node(tree, columns)
    except RecursionError as exc:
        raise CalcError(_TOO_DEEP) from exc
    if not isinstance(result, pd.Series):
        result = pd.Series(result, index=frame.index, dtype="float64")
    # Round away binary noise (e.g. 0.30000000000000004) while keeping paise exact.
    return result.astype("float64").round(6)
