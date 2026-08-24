# 1. stdlib
import types
from typing import (
    ClassVar, 
    Literal,
    Union,
    get_args,
    get_origin
)
from hashlib import sha256

# 2. third party
import patito as pt
import msgspec
from pydantic import ConfigDict

# 3. local
from src.utils.types import (
    PY_TO_PL_STR
)


# ================================================================
# 1. CONFIG
# ================================================================

# we can modify the version of the API by changing this variable
#! NEVER PUT A SLASH AT THE END OF THE URL
BASE_IGDB_URL = "https://api.igdb.com/v4"

# 1577836800 means we start in the year 2020
STARTING_TIMESTAMP_IGDB_TABLES = 1577836800  

MODEL_CONFIG = ConfigDict(
    extra            = 'ignore',
    populate_by_name = True    
)


# ================================================================
# 2. TECHNICAL COLUMNS - for postgres only
# ================================================================

#^ Colonnes techniques à ajouter automatiquement lors du chargement Postgres (SCD/audit)
class TechnicalSchema:
    pass

# ================================================================
# 3. BASE SCHEMA - basically the mother of classes
# ================================================================

class BaseIGDBSchema(pt.Model):
    """
    Base class for all IGDB schemas.
    Inherits from patito.Model (which itself inherits from Pydantic BaseModel),
    enabling both Pydantic validation at ingestion time and Polars DataFrame
    validation at the transformation step via .validate() / .from_dataframe().

    ClassVars are pipeline metadata (endpoint path, pagination params, etc.)
    and are NOT treated as model fields by Pydantic.
    """

    # ==========================================================
    # VARIABLES 
    # ==========================================================

        # propreties        
    _endpoint: ClassVar[str]
    _starting_point: ClassVar[int] = STARTING_TIMESTAMP_IGDB_TABLES
    _limit: ClassVar[int] = 500
    _offset: ClassVar[int] = 0

        # config
    model_config = MODEL_CONFIG



    # ==========================================================
    # METHODS 
    # ==========================================================

    # private

    @staticmethod
    def _clean_type(t) -> str:
        """
        Convert Python annotation to Polars type string.
        Unwraps Optional[T], handles List[T] to List(PolType), etc.
        """
        origin = get_origin(t)
        if origin is Union or origin is types.UnionType:
            args = [a for a in get_args(t) if a is not type(None)]
            if args:
                t = args[0]
                origin = get_origin(t)

        if origin is list:
            inner = get_args(t)[0]
            # au cas où c'est list[str | None]
            inner_origin = get_origin(inner)
            if inner_origin is Union or inner_origin is types.UnionType:
                inner_args = [a for a in get_args(inner) if a is not type(None)]
                if inner_args:
                    inner = inner_args[0]
            return f"List({PY_TO_PL_STR.get(inner, getattr(inner, '__name__', str(inner)))})"

        return PY_TO_PL_STR.get(t, getattr(t, "__name__", str(t)))
        # get col snapshot dict
    @classmethod
    def _get_columns_snapshot_dict(cls, is_clean):
        return {
            name: cls._clean_type(info.annotation) if is_clean else info.annotation
            for name, info in cls.model_fields.items()
        }

    # public
        # get fields
    @classmethod 
    def apicalypse_fields(cls) -> str:
        """
        Generates a comma-separated string of all declared fields for the IGDB
        Apicalypse query. Uses field alias if defined, skips ClassVar metadata.
        """
        return ", ".join(
            info.alias or name
            for name, info in cls.model_fields.items()
        )
        # build query
    @classmethod 
    def build_query(
        cls,
        last_update_value: int = 0,
        filters: str = "",
        sort: str = "updated_at asc",  #! MULTI SORTING IS NOT SUPPORTED BY IGDB API
        limit: int = 500,
        offset: int = 0
    ) -> str:
        """
        Constructs a complete Apicalypse query string for the IGDB API.

        Parameters:
        - last_update_value: Unix timestamp to fetch only records updated after this date.
        - filters: Additional custom Apicalypse filter conditions (e.g., "platforms = (48)").
        - sort: Sorting criteria (defaults to ascending order of update time).
        - limit: Maximum number of records to return (capped at 500).
        - offset: Number of records to skip for pagination.
        """
        query_parts = [f"fields {cls.apicalypse_fields()};"]
        where_conditions = []

        if last_update_value:
            where_conditions.append(f"updated_at >= {last_update_value}")

        if filters:
            where_conditions.append(f"({filters})")

        if where_conditions:
            query_parts.append(f"where {' & '.join(where_conditions)};")

        if sort:
            query_parts.append(f"sort {sort};")

        query_parts.append(f"limit {min(limit, 500)};")

        if offset:
            query_parts.append(f"offset {offset};")

        return " ".join(query_parts)
        # get columns snapshot
    @classmethod 
    def get_columns_snapshot(cls, 
                             format: Literal['json', 'dict', 'list']
    ) -> str | dict | list:
        """
        Returns a representation of the table schema (field names and types) in different formats.

        Types are also converted to Polar types with the _clean_type() function. 
        """
        columns_snapshot = cls._get_columns_snapshot_dict(is_clean=True)

        if format == 'json':
            return msgspec.json.encode(columns_snapshot).decode('utf-8')
        elif format == 'dict':
            return columns_snapshot
        elif format == 'list':
            return [name for name, field in cls.model_fields.items()]
        # get hash signature
    @classmethod 
    def get_signature(cls) -> str:
        """
        Generates a signature of the table schema.
        """
        columns_snapshot = cls._get_columns_snapshot_dict(is_clean=True)
        

        return sha256(" ".join(columns_snapshot).encode()).hexdigest()