# third party
from sqlalchemy import false
import patito as pt
# local
from .BASE import BaseIGDBSchema

# 1. Endpoint: /games
class GameSchema(BaseIGDBSchema):
    _endpoint = "/games"
    _conserve_history = True
    _use_arrays = False
    _index_at = ()

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

