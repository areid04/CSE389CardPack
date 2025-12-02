from pydantic import BaseModel
from typing import List, Optional

class CreateUser(BaseModel):
    username: str
    email: str
    password: str

class LoginUser(BaseModel):
    email: str
    password: str

class Email(BaseModel):
    email: str

class MarketSearchRequest(BaseModel):
    num_items: int
    min_price: float
    max_price: float
    rarities: List[str]
    types: List[str]