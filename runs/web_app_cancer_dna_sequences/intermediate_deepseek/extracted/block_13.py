from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class UserCreate(BaseModel):
    email: str
    password: str

class UserOut(BaseModel):
    id: int
    email: str
    is_active: bool
    created_at: datetime
    class Config: orm_mode = True

class UploadOut(BaseModel):
    id: int
    user_id: int
    filename: str
    original_filename: str
    file_type: str
    status: str
    metadata_json: Dict[str, Any] = {}
    created_at: datetime
    updated_at: Optional[datetime]
    class Config: orm_mode = True

class SequenceOut(BaseModel):
    id: int
    upload_id: int
    sequence_id: str
    description: Optional[str]
    sequence: str
    length: int
    quality: Optional[str]
    md5: Optional[str]
    class Config: orm_mode = True
