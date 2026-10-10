from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class ClosedDateIn(BaseModel):
    reason: str = Field(default="", max_length=100)


class ClosedDateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    day: date
    reason: str
