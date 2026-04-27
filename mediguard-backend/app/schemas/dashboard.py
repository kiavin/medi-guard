from pydantic import BaseModel
from typing import Any, Dict

class DashboardResponse(BaseModel):
    role: str
    metrics: Dict[str, Any]
    ai_insights: list[Dict[str, Any]]
    action_items: list[Dict[str, Any]]