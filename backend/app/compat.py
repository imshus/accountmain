"""pandas 3 behaviour on pandas 2, so Python 3.9 and 3.10 (which get pandas 2.x) give the same answers.

The app is written for pandas 3. On pandas 2 this module, loaded once with the package, switches on
copy-on-write (pandas 3's only mode: changing a column taken from a table never changes the table) and
provides ``to_datetime`` and ``to_timestamp``, which keep pandas 3's date range.
"""

from __future__ import annotations

import re
from datetime import datetime

import numpy as np
import pandas as pd
from pandas.tseries.api import guess_datetime_format

PANDAS_3 = int(pd.__version__.split(".")[0]) >= 3

if not PANDAS_3:
    pd.set_option("mode.copy_on_write", True)

_YEAR = re.compile(r"(?<!\d)\d{4}(?!\d)|^\d{4}(?=\d{4}$)")  # a year, or the YYYY of YYYYMMDD
_NO_DATE = {"", "NaT", "nat", "NAT", "nan", "NaN", "NAN"}


def to_datetime(values: pd.Series, dayfirst: bool = False) -> pd.Series:
    """``pd.to_datetime(values, errors="coerce", dayfirst=dayfirst)`` with pandas 3's microsecond dates (years 1
    to 9999).

    pandas 2 parses to nanoseconds, which end in 2262, so a mistyped year such as 17/04/2925 would quietly
    become a blank date there, while pandas 3 keeps it and the mistake shows."""
    result = pd.to_datetime(values, errors="coerce", dayfirst=dayfirst)
    if PANDAS_3 or pd.api.types.is_datetime64_any_dtype(values):
        return result
    present = values.notna().to_numpy()
    lost = np.flatnonzero(result.isna().to_numpy() & present)
    fmt = None
    if lost.size:
        # pandas reads the whole column in the format of its first date (skipping "" and "NaT"); pandas 2 cannot
        # even guess the format of a date past 2262, so guess it with the year set to 2000.
        start = next((i for i in np.flatnonzero(present) if values.iloc[i] not in _NO_DATE), None)
        first = values.iloc[start] if start is not None else None
        if isinstance(first, str):
            fmt = guess_datetime_format(_YEAR.sub("2000", first), dayfirst=dayfirst)
            if fmt and start in lost:
                result = pd.to_datetime(values, format=fmt, errors="coerce")
                lost = np.flatnonzero(result.isna().to_numpy() & present)
    stamps = result.to_numpy(dtype="datetime64[us]")
    for i in lost:
        stamps[i] = _one(values.iloc[i], fmt, dayfirst)
    return pd.Series(stamps, index=values.index, name=values.name)


def to_timestamp(text: str, dayfirst: bool = False):
    """One date string as ``pd.to_datetime(text, errors="coerce", dayfirst=dayfirst)`` reads it on pandas 3."""
    parsed = pd.to_datetime(text, errors="coerce", dayfirst=dayfirst)
    if PANDAS_3 or not pd.isna(parsed):
        return parsed
    return to_datetime(pd.Series([text], dtype=object), dayfirst=dayfirst).iloc[0]


def _one(value, fmt: str | None, dayfirst: bool) -> np.datetime64:
    try:
        if isinstance(value, str):
            moment = datetime.strptime(value, fmt) if fmt else _year_2000(value, dayfirst)
        else:
            moment = pd.Timestamp(value).to_pydatetime()
    except (TypeError, ValueError):
        moment = None
    return np.datetime64(moment, "us") if moment is not None else np.datetime64("NaT", "us")


def _year_2000(text: str, dayfirst: bool) -> datetime | None:
    """A date with no single format ("17 Sept 2925") read by pandas' own parser with the year set to 2000, then
    given its year back; an impossible date (29 Feb 2925) raises ValueError."""
    years = _YEAR.findall(text)
    if len(years) != 1:
        return None
    moment = pd.to_datetime(_YEAR.sub("2000", text), errors="coerce", dayfirst=dayfirst)
    return None if pd.isna(moment) else moment.to_pydatetime().replace(year=int(years[0]))
