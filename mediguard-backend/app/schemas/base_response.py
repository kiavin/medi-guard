from pydantic import BaseModel
from typing import Generic, TypeVar, Optional, Dict, Any

# T represents whatever data schema you are returning (e.g., Token, UserResponse)
T = TypeVar('T')

class Alertify(BaseModel):
    theme: str = "success"
    type: str = "alert"
    message: str

class DataPayload(BaseModel, Generic[T]):
    data: T
    alertify: Optional[Alertify] = None

class APIResponse(BaseModel, Generic[T]):
    dataPayload: DataPayload[T]

# Utility function to quickly generate the success payload in your routers
def send_success(data: Any, message: Optional[str] = None, theme: str = "success", alert_type: str = "alert") -> dict:
    payload = {
        "dataPayload": {
            "data": data
        }
    }
    if message:
        payload["dataPayload"]["alertify"] = {
            "theme": theme,
            "type": alert_type,
            "message": message
        }
    return payload