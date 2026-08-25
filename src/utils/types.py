import datetime
import msgspec
import polars as pl


# ================================================================
# 1. TYPE MAPPING
# ================================================================

PY_TO_PL = {
    int: pl.Int64,
    str: pl.Utf8,
    float: pl.Float64,
    bool: pl.Boolean,
    datetime.datetime: pl.Datetime("ms"),
    datetime.date: pl.Date,
    bytes: pl.Binary,
}


PY_TO_PL_STR = {k: str(v) for k, v in PY_TO_PL.items()} 

import re

PY_TO_SQL = {
    # signed ints
    "Int8": "SMALLINT",
    "Int16": "SMALLINT",
    "Int32": "INTEGER",
    "Int64": "BIGINT",
    # unsigned ints -> PG a pas d'unsigned, on upsize
    "UInt8": "SMALLINT",
    "UInt16": "INTEGER",
    "UInt32": "BIGINT",
    "UInt64": "BIGINT",
    # floats
    "Float32": "REAL",
    "Float64": "DOUBLE PRECISION",
    # others
    "Utf8": "TEXT",
    "String": "TEXT",
    "Boolean": "BOOLEAN",
    "Date": "DATE",
    "Datetime": "TIMESTAMPTZ",
    "Time": "TIME",
    "Binary": "BYTEA",
    "Null": "TEXT", # fallback
}

_LIST_RE = re.compile(r"^List\((.+)\)$")

# ================================================================
# 2. TYPE DEFINITIONS - for schema change detection
# ================================================================

class TypeChange(msgspec.Struct):
    """
    Represents the change in a column type.
    
    Attributes:
        old: The old type of the column.
        new: The new type of the column.
    """
    old: str
    new: str
                    
class ChangedColumns(msgspec.Struct):
    """
    Represents the changes in a table schema.
    
    Attributes:
        added: List of columns that were added to the schema.
        removed: List of columns that were removed from the schema.
        type_changed: Dictionary of columns whose types have changed.
    """
    added: list[str]
    removed: list[str]
    type_changed: dict[str, TypeChange]