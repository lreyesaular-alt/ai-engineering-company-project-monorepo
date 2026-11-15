
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class Incident(SQLModel, table=True):
    __tablename__ = "incidents"

    id: int | None = Field(
        default=None,
        primary_key=True,
    )

    location_id: str
    category: str
    description: str
    reporter_id: str
    status: str
    satisfaction_score: float | None = None

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


class Ingredient(SQLModel, table=True):
    __tablename__ = "ingredients"

    id: int | None = Field(
        default=None,
        primary_key=True,
    )

    name: str

    sku: str = Field(
        unique=True,
        index=True,
    )

    unit: str
    category: str
    country: str


class IngredientEntry(SQLModel, table=True):
    __tablename__ = "ingredient_entries"

    id: int | None = Field(
        default=None,
        primary_key=True,
    )

    ingredient_id: int = Field(
        foreign_key="ingredients.id",
    )

    quantity: float
    supplier_name: str
    supplier_id: str | None = None
    unit_price: float | None = None
    currency: str | None = None
    location_id: int

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    user_uuid: str


class IngredientExit(SQLModel, table=True):
    __tablename__ = "ingredient_exits"

    id: int | None = Field(
        default=None,
        primary_key=True,
    )

    ingredient_id: int = Field(
        foreign_key="ingredients.id",
    )

    quantity: float
    reason: str
    waste_reason: str | None = None
    location_id: int

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    user_uuid: str

class InventoryThreshold(SQLModel, table=True):
    __tablename__ = "inventory_thresholds"

    id: int | None = Field(default=None, primary_key=True)
    ingredient_id: int = Field(foreign_key="ingredients.id", index=True)
    location_id: int = Field(index=True)
    threshold_quantity: float = Field(ge=0)


class IngredientPriceRecord(SQLModel, table=True):
    __tablename__ = "ingredient_price_records"

    id: int | None = Field(default=None, primary_key=True)
    ingredient_id: int = Field(foreign_key="ingredients.id", index=True)
    supplier_id: str
    unit_price: float = Field(gt=0)
    currency: str
    location_id: int
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
