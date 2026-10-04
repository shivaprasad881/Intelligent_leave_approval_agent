from pydantic import BaseModel


class Calendar(BaseModel):
    date: str
    isblacklisted: int = 0
    reason: str = ""