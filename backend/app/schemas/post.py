from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_POST_LENGTH = 500


class PostCreate(BaseModel):
    content: str = Field(min_length=1, max_length=MAX_POST_LENGTH)

    @field_validator("content", mode="before")
    @classmethod
    def strip_content(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class PostAuthor(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str


class PostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    created_at: datetime
    author: PostAuthor