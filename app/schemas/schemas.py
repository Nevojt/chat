from typing import Optional
from pydantic import BaseModel, Field
from typing_extensions import Annotated
from datetime import datetime

        

    
        
class SocketModel(BaseModel):
    created_at: datetime
    receiver_id: Optional[int] = None
    id: int
    message: str
    user_name: Optional[str] = "DELETE"
    avatar: Optional[str] = "https://tygjaceleczftbswxxei.supabase.co/storage/v1/object/public/image_bucket/inne/image/boy_1.webp"
    verified: Optional[bool] = None
    vote: int
    id_return: Optional[int] = None
        
class SocketUpdate(BaseModel):
    id: int
    message: str
    
class SocketDelete(BaseModel):
    id: int
        
        
    
class TokenData(BaseModel):
    id: Optional[int] = None
    
class Vote(BaseModel):
    message_id: int
    dir: Annotated[int, Field(strict=True, le=1)]