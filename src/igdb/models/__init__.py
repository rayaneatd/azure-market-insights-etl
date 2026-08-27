"""
IGDB models - SSOT.

Central export for all IGDB schemas. 
Import from here, not from individual files.

In case you want to add a new Class, it must be declared here. Or else, you won't see it in analytics
"""

from .BASE import BaseIGDBSchema, BASE_IGDB_URL

from .companies import CompanySchema
from .games import GameSchema
from .genres import GenreSchema
from .platforms import PlatformSchema
from .release_dates import ReleaseDateSchema

__all__ = [
    "BaseIGDBSchema"    ,
    "CompanySchema"     ,
    "GameSchema"        ,
    "GenreSchema"       ,
    "PlatformSchema"    ,
    "ReleaseDateSchema" ,
    # add here in case you create a new class...
]