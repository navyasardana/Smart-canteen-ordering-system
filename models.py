from pydantic import BaseModel, field_validator
from typing import List, Optional


class OrderRequest(BaseModel):
    student_name: str
    student_id: str
    items: List[str]
    quantity: int
    slot_id: Optional[int] = None  # student can request a specific slot

    @field_validator("student_id")
    @classmethod
    def student_id_alphanumeric(cls, v: str) -> str:
        if not v.isalnum():
            raise ValueError("Student ID must be alphanumeric (letters and numbers only)")
        return v

    @field_validator("quantity")
    @classmethod
    def quantity_range(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Quantity must be at least 1")
        if v > 10:
            raise ValueError("Quantity cannot exceed 10 per order")
        return v

    @field_validator("items")
    @classmethod
    def items_not_empty(cls, v: List[str]) -> List[str]:
        cleaned = [i.strip() for i in v if i.strip()]
        if not cleaned:
            raise ValueError("Items list cannot be empty")
        return cleaned


class StatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def status_valid(cls, v: str) -> str:
        allowed = {"Pending", "Being Prepared", "Ready for Pickup", "Collected"}
        if v not in allowed:
            raise ValueError(f"Status must be one of: {', '.join(allowed)}")
        return v


class SlotUpdate(BaseModel):
    wait_time: Optional[int] = None
    closed: Optional[bool] = None
