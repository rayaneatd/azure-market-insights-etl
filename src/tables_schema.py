from patito._pydantic import column_info
import patito as pt
import msgspec
from typing import (
    ClassVar, 
    Literal,
    Union,
    get_args,
    get_origin
)
from hashlib import sha256
import polars as pl
import datetime

# we can modify the version of the API by changing this variable
#! NEVER PUT A SLASH AT THE END OF THE URL
BASE_IGDB_URL = "https://api.igdb.com/v4"
STARTING_TIMESTAMP_IGDB_TABLES = 1577836800  # by default we start in the year 2020

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

class BaseIGDBSchema(pt.Model):
    """
    Base class for all IGDB schemas.
    Inherits from patito.Model (which itself inherits from Pydantic BaseModel),
    enabling both Pydantic validation at ingestion time and Polars DataFrame
    validation at the transformation step via .validate() / .from_dataframe().

    ClassVars are pipeline metadata (endpoint path, pagination params, etc.)
    and are NOT treated as model fields by Pydantic.
    """

    # Pipeline metadata — invisible to Pydantic/Patito as fields
    _endpoint: ClassVar[str]
    _starting_point: ClassVar[int] = STARTING_TIMESTAMP_IGDB_TABLES
    _limit: ClassVar[int] = 500
    _offset: ClassVar[int] = 0


    # ConfigDict is a Pydantic v2 class for configuring Pydantic models
    # It is used to configure the behavior of the model
    #TODO: i need to edit this later to handle soft changes my way
    model_config = {
        "extra": 'ignore', # allows IGDB to return unknown columns
        "populate_by_name": True # allows instantiation by field name even if alias is set
    }

    def _clean(t):
        # Unwrap Optional / Union
        origin = get_origin(t)
        if origin is Union or origin is list or str(origin).startswith("Union"):
            args = [a for a in get_args(t) if a is not type(None)]
            if args:
                t = args[0]

        if get_origin(t) is list:
            inner = get_args(t)[0]
            return f"List({PY_TO_PL_STR.get(inner, str(inner))})"

        return PY_TO_PL_STR.get(t, getattr(t, '__name__', str(t))) # pyrefly: ignore[no-matching-overload]

    @classmethod # get fields
    def apicalypse_fields(cls) -> str:
        """
        Generates a comma-separated string of all declared fields for the IGDB
        Apicalypse query. Uses field alias if defined, skips ClassVar metadata.
        """
        return ", ".join(
            info.alias or name
            for name, info in cls.model_fields.items()
        )

    @classmethod # build query
    def build_query(
        cls,
        last_update_value: int = 0,
        last_id: int = 0,
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

    @classmethod # get hash signature
    def get_signature(cls) -> str:
        """
        Generates a signature of the table schema.
        """
        return sha256(" ".join(
            info.alias or name
            for name, info in cls.model_fields.items()
        ).encode()).hexdigest()

    @classmethod # get columns snapshot
    def get_columns_snapshot(cls, 
                             format: Literal['json', 'dict', 'list']
    ) -> str | dict | list:
        """
        Returns a JSON string representation of the table schema (field names and types).
        """
        columns_snapshot = {
            name: cls._clean(info.annotation) # pyrefly: ignore
            for name, info in cls.model_fields.items()
        }

        if format == 'json':
            return msgspec.json.encode(columns_snapshot).decode('utf-8')
        elif format == 'dict':
            return columns_snapshot
        elif format == 'list':
            return [name for name, field in cls.model_fields.items()]

# 1. Endpoint: /games
class GameSchema(BaseIGDBSchema):
    _endpoint = "/games"

    id: int = pt.Field(unique=True)
    name: str
    slug: str | None = None
    summary: str | None = None
    storyline: str | None = None

    # Timestamps
    created_at: int | None = None
    updated_at: int | None = None
    first_release_date: int | None = None

    # Métriques d'évaluation et Popularité
    rating: float | None = None
    rating_count: int | None = None
    aggregated_rating: float | None = None
    aggregated_rating_count: int | None = None
    total_rating: float | None = None
    total_rating_count: int | None = None
    hypes: int | None = None

    # Classification
    game_type: int | None = None
    game_status: int | None = None

    # Relations (IGDB renvoie des tableaux d'IDs)
    genres: list[int] = pt.Field(default_factory=list)
    platforms: list[int] = pt.Field(default_factory=list)
    involved_companies: list[int] = pt.Field(default_factory=list)
    release_dates: list[int] = pt.Field(default_factory=list)
    game_modes: list[int] = pt.Field(default_factory=list)
    themes: list[int] = pt.Field(default_factory=list)
    collections: list[int] = pt.Field(default_factory=list)

    # Hiérarchie et metadata
    parent_game: int | None = None
    version_parent: int | None = None
    version_title: str | None = None
    checksum: str | None = None


# 2. Endpoint: /release_dates
class ReleaseDateSchema(BaseIGDBSchema):
    _endpoint = "/release_dates"

    id: int = pt.Field(unique=True)
    game: int | None = None
    platform: int | None = None
    date: int | None = None           # Timestamp Unix
    human: str | None = None          # Ex: "2026-Q3" ou "Dec 31, 2026"
    y: int | None = None              # Année de sortie (e.g. 2026)
    m: int | None = None              # Mois (1-12)
    region: int | None = None         # Region Enum (Europe, US, JP...)
    status: int | None = None         # Release Date Status Enum

    created_at: int | None = None
    updated_at: int | None = None
    checksum: str | None = None


# 3. Endpoint: /genres
class GenreSchema(BaseIGDBSchema):
    _endpoint = "/genres"

    id: int = pt.Field(unique=True)
    name: str
    slug: str | None = None

    created_at: int | None = None
    updated_at: int | None = None
    checksum: str | None = None


# 4. Endpoint: /platforms
class PlatformSchema(BaseIGDBSchema):
    _endpoint = "/platforms"

    id: int = pt.Field(unique=True)
    name: str
    slug: str | None = None
    abbreviation: str | None = None
    alternative_name: str | None = None
    generation: int | None = None
    platform_family: int | None = None  # ID de la famille (PlayStation, Xbox, Nintendo)

    created_at: int | None = None
    updated_at: int | None = None
    checksum: str | None = None


# 5. Endpoint: /companies
class CompanySchema(BaseIGDBSchema):
    _endpoint = "/companies"

    id: int = pt.Field(unique=True)
    name: str
    slug: str | None = None
    description: str | None = None
    country: int | None = None             # Code pays ISO / ID
    parent: int | None = None              # ID de la maison mère si filiale
    changed_company_id: int | None = None  # Historique de restructuration ou rachat

    created_at: int | None = None
    updated_at: int | None = None
    checksum: str | None = None


#^ Colonnes techniques à ajouter automatiquement lors du chargement Postgres (SCD/audit)
class TechnicalSchema:
    pass