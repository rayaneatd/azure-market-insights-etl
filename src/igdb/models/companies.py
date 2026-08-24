# third party
import patito as pt
# local
from .BASE import BaseIGDBSchema

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

