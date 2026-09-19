"""Turn service results (DataFrames, Series, numpy scalars, dates, dataclasses) into plain JSON-safe values."""
from __future__ import annotations

import dataclasses
import datetime as dt
import decimal
import math
from typing import Any

import numpy as np
import pandas as pd


def to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, pd.DataFrame):
        return [to_jsonable(row) for row in value.to_dict(orient="records")]
    if isinstance(value, pd.Series):
        return [{"x": to_jsonable(i), "y": to_jsonable(v)} for i, v in value.items()]
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(v) for v in value]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: to_jsonable(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, (pd.Timestamp, dt.datetime, dt.date)):
        return None if pd.isna(value) else value.isoformat()[:10]
    if isinstance(value, np.generic):
        return to_jsonable(value.item())
    if isinstance(value, decimal.Decimal):
        return to_jsonable(float(value))
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, int):
        return value
    return str(value)
