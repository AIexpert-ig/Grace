from pydantic import BaseModel

class RateCheckRequest(BaseModel):
    check_in_date: str
    room_type: str = "standard"

class CallSummaryRequest(BaseModel):
    caller_name: str
    room_number: str
    callback_number: str
    summary: str
    urgency: str
