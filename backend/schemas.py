from pydantic import BaseModel, EmailStr

# What the React Frontend sends us
class UserConnectRequest(BaseModel):
    username: str  # <--- New field
    email: EmailStr
    password: str

# What we send back to React
class APIResponse(BaseModel):
    status: str
    message: str