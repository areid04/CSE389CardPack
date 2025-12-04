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

class OpenPackRequest(BaseModel):
    email: str
    pack_name: Optional[str] = None  # If None, opens most recent pack

class AddPackRequest(BaseModel):
    email: str
    pack_name: str

class MarketSearchRequest(BaseModel):
    num_items: int
    min_price: float
    max_price: float
    rarities: List[str]
    types: List[str]