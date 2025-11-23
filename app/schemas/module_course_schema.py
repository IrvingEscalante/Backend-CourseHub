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