from pydantic import BaseModel
from typing import Optional, List

class ThemeBase(BaseModel):
    name_theme: str
    status: Optional[bool] = True

class ThemeCreate(ThemeBase):
    pass  # Para crear un tema, solo necesitas name_theme y opcionalmente status

class ThemeUpdate(ThemeBase):
    pass  # Para actualizar un tema

class ThemeResponse(ThemeBase):
    id_theme: int

    class Config:
        from_attributes = True
