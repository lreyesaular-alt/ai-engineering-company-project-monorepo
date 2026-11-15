
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class IngredientCreate(BaseModel):
    name: str
    sku: str
    unit: str
    category: str
    country: str


class IngredientResponse(BaseModel):
    id: int
    name: str
    sku: str
    unit: str
    category: str
    country: str
    current_stock: float


class IngredientEntryCreate(BaseModel):
    ingredient_id: int
    quantity: float = Field(gt=0)
    supplier_name: str
    supplier_id: str | None = None
    unit_price: float | None = Field(default=None, gt=0)
    currency: Literal["COP", "USD"] | None = None
    location_id: int = Field(ge=1, le=14)
    user_uuid: str


class IngredientEntryResponse(BaseModel):
    id: int
    ingredient_id: int
    quantity: float
    supplier_name: str
    supplier_id: str | None = None
    unit_price: float | None = None
    currency: str | None = None
    location_id: int
    created_at: datetime
    user_uuid: str


class IngredientExitCreate(BaseModel):
    ingredient_id: int
    quantity: float = Field(gt=0)
    reason: Literal["consumption", "waste"]
    waste_reason: Literal[
        "expired",
        "kitchen_error",
        "theft_suspected",
    ] | None = None
    location_id: int = Field(ge=1, le=14)
    user_uuid: str

    @model_validator(mode="after")
    def validate_waste_reason(self):
        if self.reason == "waste" and self.waste_reason is None:
            raise ValueError(
                "waste_reason is required when reason is 'waste'"
            )

        if self.reason == "consumption" and self.waste_reason is not None:
            raise ValueError(
                "waste_reason is only allowed when reason is 'waste'"
            )

        return self


class IngredientExitResponse(BaseModel):
    id: int
    ingredient_id: int
    quantity: float
    reason: str
    location_id: int
    created_at: datetime
    user_uuid: str


class IngredientOrderResponse(BaseModel):
    id: int
    ingredient_id: int
    ingredient_name: str
    type: str
    quantity: float
    supplier_name: str | None = None
    reason: str | None = None
    location_id: int
    created_at: datetime
    user_uuid: str

class InventoryThresholdCreate(BaseModel):
    ingredient_id: int
    location_id: int = Field(ge=1, le=14)
    threshold_quantity: float = Field(ge=0)


class DirectStockEditAttempt(BaseModel):
    location_id: int = Field(ge=1, le=14)
    operation_type: str = Field(min_length=1, max_length=100)
