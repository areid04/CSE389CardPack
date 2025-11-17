from pydantic import BaseModel

# insecure new user request class; we will never send this password in practice but proof of concept needed
class CreateUser(BaseModel):
    username: str
    email: str
    password: str