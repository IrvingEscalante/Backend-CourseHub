from pydantic import BaseModel

class AddCourseFavorites:
    id_user:int
    id_course:int