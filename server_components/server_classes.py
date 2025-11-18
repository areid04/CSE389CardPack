from pydantic import BaseModel

# insecure new user request class; we will never send this password in practice but proof of concept needed
class CreateUser(BaseModel):
    username: str
    email: str
    password: str

class LoginUser(BaseModel):
    email: str
    password: str

class MarketSearchRequest(BaseModel):
    num_items: int
    min_price: float
    max_price: float
    rarities: list[str]
    types: list[str]