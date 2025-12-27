from pydantic import BaseModel
from datetime import datetime

class ModuleCourseResponse(BaseModel):
    id_module: int
    id_course: int
    name_module: str
    description_module: str
    status_module: bool
    order_index: int
    date_created: datetime

    class Config:
        from_attributes = True

class CreateModule(BaseModel):
    id_course: int
    name_module: str
    description_module: str
    status_module: bool
    order_index: int

class EditModule(BaseModel):
    id_module: int
    name_module: str | None = None
    description_module: str | None = None
    status_module: bool | None = None
    order_index: int | None = None