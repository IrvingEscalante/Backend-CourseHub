from typing import Generic, TypeVar, Optional
from pydantic.generics import GenericModel

T = TypeVar("T")  # variable de tipo genérico

class ResponseModel(GenericModel, Generic[T]):
    success: bool = True
    message: Optional[str] = None
    data: Optional[T] = None
