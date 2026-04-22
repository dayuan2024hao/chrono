from pydantic import BaseModel

class ConfirmRequest(BaseModel):
    alert_id: int