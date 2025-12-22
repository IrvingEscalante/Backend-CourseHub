from pydantic import BaseModel

class PullRequestCreate(BaseModel):
    id_course_source: int
    id_course_target: int
    title: str
    description: str | None = None
