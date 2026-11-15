from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from tinydb import TinyDB
from sqlalchemy import func
from sqlmodel import Session, select

from services.api.database import get_db
from services.api.models import (
    Ingredient,
    IngredientEntry,
    IngredientExit,
    IngredientPriceRecord,
    InventoryThreshold,
)
from services.api.telemetry_sender import send_telemetry_event
from services.api.schemas import (
    IngredientCreate,
    IngredientEntryCreate,
    IngredientEntryResponse,
    IngredientExitCreate,
    IngredientExitResponse,
    IngredientOrderResponse,
    IngredientResponse,
    InventoryThresholdCreate,
    DirectStockEditAttempt,
)


router = APIRouter(
    prefix="/inventory",
    tags=["Inventory"],
)


def calculate_stock(
    ingredient_id: int,
    db: Session,
) -> float:
    inbound = db.exec(
        select(func.coalesce(func.sum(IngredientEntry.quantity), 0.0))
        .where(IngredientEntry.ingredient_id == ingredient_id)
    ).one()

    outbound = db.exec(
        select(func.coalesce(func.sum(IngredientExit.quantity), 0.0))
        .where(IngredientExit.ingredient_id == ingredient_id)
    ).one()

    return float(inbound) - float(outbound)




def calculate_location_stock(
    ingredient_id: int,
    location_id: int,
    db: Session,
) -> float:
    inbound = db.exec(
        select(func.coalesce(func.sum(IngredientEntry.quantity), 0.0))
        .where(
            IngredientEntry.ingredient_id == ingredient_id,
            IngredientEntry.location_id == location_id,
        )
    ).one()

    outbound = db.exec(
        select(func.coalesce(func.sum(IngredientExit.quantity), 0.0))
        .where(
            IngredientExit.ingredient_id == ingredient_id,
            IngredientExit.location_id == location_id,
        )
    ).one()

    return float(inbound) - float(outbound)


@router.put("/thresholds")
def configure_inventory_threshold(
    threshold_data: InventoryThresholdCreate,
    db: Session = Depends(get_db),
):
    ingredient = db.get(Ingredient, threshold_data.ingredient_id)
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found.")

    threshold = db.exec(
        select(InventoryThreshold).where(
            InventoryThreshold.ingredient_id == threshold_data.ingredient_id,
            InventoryThreshold.location_id == threshold_data.location_id,
        )
    ).first()

    if threshold:
        threshold.threshold_quantity = threshold_data.threshold_quantity
    else:
        threshold = InventoryThreshold(
            ingredient_id=threshold_data.ingredient_id,
            location_id=threshold_data.location_id,
            threshold_quantity=threshold_data.threshold_quantity,
        )
        db.add(threshold)

    db.commit()
    db.refresh(threshold)

    return {
        "ingredient_id": threshold.ingredient_id,
        "location_id": threshold.location_id,
        "threshold_quantity": threshold.threshold_quantity,
    }


@router.post("/products/{id}/stock", status_code=status.HTTP_409_CONFLICT)
def reject_direct_stock_edit(
    id: int,
    attempt: DirectStockEditAttempt,
    db: Session = Depends(get_db),
):
    ingredient = db.get(Ingredient, id)
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found.")

    country = country_code(ingredient.country)
    if country:
        send_telemetry_event(
            "direct_stock_edit_rejected",
            {
                "location_id": str(attempt.location_id),
                "country": country,
                "product_id": str(ingredient.id),
                "product_category": ingredient.category,
                "operation_type": attempt.operation_type,
                "rejection_result": "rejected",
            },
        )

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Direct stock edits are not allowed. Use an inventory order.",
    )



def check_inventory_threshold(
    ingredient: Ingredient,
    location_id: int,
    previous_stock: float,
    db: Session,
) -> None:
    threshold = db.exec(
        select(InventoryThreshold).where(
            InventoryThreshold.ingredient_id == ingredient.id,
            InventoryThreshold.location_id == location_id,
        )
    ).first()

    if not threshold:
        return

    current_stock = calculate_location_stock(
        ingredient.id,
        location_id,
        db,
    )

    if (
        previous_stock > threshold.threshold_quantity
        and current_stock <= threshold.threshold_quantity
    ):
        country = country_code(ingredient.country)
        if country:
            send_telemetry_event(
                "stock_threshold_triggered",
                {
                    "location_id": str(location_id),
                    "country": country,
                    "product_id": str(ingredient.id),
                    "product_category": ingredient.category,
                    "quantity": current_stock,
                    "unit": ingredient.unit,
                    "threshold_quantity": threshold.threshold_quantity,
                },
            )


SUPPLIERS_DB_FILE = (
    Path(__file__).resolve().parents[3]
    / "services"
    / "suppliers"
    / "suppliers.json"
)


def country_code(country: str) -> str | None:
    normalized = country.strip().lower()
    if normalized in {"colombia", "co"}:
        return "CO"
    if normalized in {"usa", "us", "united states"}:
        return "US"
    return None


def currency_for_country(country: str) -> str | None:
    code = country_code(country)
    return {"CO": "COP", "US": "USD"}.get(code)


def find_supplier(supplier_name: str, ingredient: Ingredient):
    if not SUPPLIERS_DB_FILE.exists():
        return None

    db = TinyDB(SUPPLIERS_DB_FILE)
    try:
        matches = [
            supplier
            for supplier in db.all()
            if supplier.get("name", "").strip().casefold()
            == supplier_name.strip().casefold()
            and supplier.get("status") == "active"
            and supplier.get("country") in {"Colombia", "USA"}
            and country_code(supplier.get("country", ""))
            == country_code(ingredient.country)
            and ingredient.category in supplier.get("categories", [])
        ]
        return matches[0] if len(matches) == 1 else None
    finally:
        db.close()


@router.get(
    "/products",
    response_model=list[IngredientResponse],
)
def get_products(
    db: Session = Depends(get_db),
):
    ingredients = db.exec(
        select(Ingredient)
    ).all()

    return [
        IngredientResponse(
            id=ingredient.id,
            name=ingredient.name,
            sku=ingredient.sku,
            unit=ingredient.unit,
            category=ingredient.category,
            country=ingredient.country,
            current_stock=calculate_stock(
                ingredient.id,
                db,
            ),
        )
        for ingredient in ingredients
    ]


@router.post(
    "/products",
    response_model=IngredientResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_product(
    ingredient_data: IngredientCreate,
    db: Session = Depends(get_db),
):
    existing = db.exec(
        select(Ingredient).where(
            Ingredient.sku == ingredient_data.sku
        )
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Ingredient with SKU '{ingredient_data.sku}' already exists.",
        )

    ingredient = Ingredient(
        name=ingredient_data.name,
        sku=ingredient_data.sku,
        unit=ingredient_data.unit,
        category=ingredient_data.category,
        country=ingredient_data.country,
    )

    db.add(ingredient)
    db.commit()
    db.refresh(ingredient)

    return IngredientResponse(
        id=ingredient.id,
        name=ingredient.name,
        sku=ingredient.sku,
        unit=ingredient.unit,
        category=ingredient.category,
        country=ingredient.country,
        current_stock=0.0,
    )


@router.get(
    "/products/{id}",
    response_model=IngredientResponse,
)
def get_product(
    id: int,
    db: Session = Depends(get_db),
):
    ingredient = db.get(
        Ingredient,
        id,
    )

    if not ingredient:
        raise HTTPException(
            status_code=404,
            detail="Ingredient not found.",
        )

    return IngredientResponse(
        id=ingredient.id,
        name=ingredient.name,
        sku=ingredient.sku,
        unit=ingredient.unit,
        category=ingredient.category,
        country=ingredient.country,
        current_stock=calculate_stock(
            ingredient.id,
            db,
        ),
    )


@router.post(
    "/orders/inbound",
    response_model=IngredientEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_inbound_order(
    entry_data: IngredientEntryCreate,
    db: Session = Depends(get_db),
):
    ingredient = db.get(
        Ingredient,
        entry_data.ingredient_id,
    )

    if not ingredient:
        raise HTTPException(
            status_code=404,
            detail="Ingredient not found.",
        )

    supplier = find_supplier(entry_data.supplier_name, ingredient)
    currency = currency_for_country(ingredient.country)
    country = country_code(ingredient.country)

    if not supplier:
        raise HTTPException(
            status_code=422,
            detail="Supplier is not active or does not match the ingredient.",
        )

    supplier_id = str(supplier["id"])

    if entry_data.supplier_id and entry_data.supplier_id != supplier_id:
        raise HTTPException(
            status_code=422,
            detail="Supplier ID does not match the supplier name.",
        )

    if entry_data.unit_price is not None:
        if not currency or entry_data.currency != currency:
            raise HTTPException(
                status_code=422,
                detail="Price currency must match the ingredient country.",
            )

    previous_stock = calculate_location_stock(
        ingredient.id,
        entry_data.location_id,
        db,
    )

    entry = IngredientEntry(
        ingredient_id=entry_data.ingredient_id,
        quantity=entry_data.quantity,
        supplier_name=entry_data.supplier_name,
        supplier_id=supplier_id,
        unit_price=entry_data.unit_price,
        currency=entry_data.currency or currency,
        location_id=entry_data.location_id,
        user_uuid=entry_data.user_uuid,
    )

    db.add(entry)
    db.commit()
    db.refresh(entry)

    check_inventory_threshold(
        ingredient,
        entry.location_id,
        previous_stock,
        db,
    )

    if entry.unit_price is not None and entry.currency:
        previous_price = db.exec(
            select(IngredientPriceRecord)
            .where(
                IngredientPriceRecord.ingredient_id == ingredient.id,
                IngredientPriceRecord.supplier_id == supplier_id,
                IngredientPriceRecord.location_id == entry.location_id,
                IngredientPriceRecord.currency == entry.currency,
            )
            .order_by(IngredientPriceRecord.created_at.desc())
        ).first()

        price_record = IngredientPriceRecord(
            ingredient_id=ingredient.id,
            supplier_id=supplier_id,
            unit_price=entry.unit_price,
            currency=entry.currency,
            location_id=entry.location_id,
        )
        db.add(price_record)
        db.commit()

        if previous_price and previous_price.unit_price > 0:
            variance = (
                (entry.unit_price - previous_price.unit_price)
                / previous_price.unit_price
            ) * 100

            if abs(variance) > 10 and country:
                send_telemetry_event(
                    "ingredient_price_variance_detected",
                    {
                        "location_id": str(entry.location_id),
                        "country": country,
                        "product_id": str(ingredient.id),
                        "product_category": ingredient.category,
                        "currency": entry.currency,
                        "previous_price": previous_price.unit_price,
                        "new_price": entry.unit_price,
                        "variance_percentage": round(variance, 2),
                        "supplier_id": supplier_id,
                    },
                )

    if supplier and currency and country:
        send_telemetry_event(
            "inbound_order_created",
            {
                "location_id": str(entry.location_id),
                "country": country,
                "product_id": str(ingredient.id),
                "product_category": ingredient.category,
                "quantity": entry.quantity,
                "unit": ingredient.unit,
                "currency": currency,
                "supplier_id": str(supplier["id"]),
                "order_id": str(entry.id),
            },
        )

    return entry


@router.post(
    "/orders/outbound",
    response_model=IngredientExitResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_outbound_order(
    exit_data: IngredientExitCreate,
    db: Session = Depends(get_db),
):
    ingredient = db.get(
        Ingredient,
        exit_data.ingredient_id,
    )

    if not ingredient:
        raise HTTPException(
            status_code=404,
            detail="Ingredient not found.",
        )

    if exit_data.reason not in {"consumption", "waste"}:
        raise HTTPException(
            status_code=422,
            detail="Reason must be 'consumption' or 'waste'.",
        )

    available = calculate_stock(
        ingredient.id,
        db,
    )

    if exit_data.quantity > available:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Insufficient stock for ingredient "
                f"'{ingredient.name}'. "
                f"Available: {available}, "
                f"requested: {exit_data.quantity}."
            ),
        )

    previous_location_stock = calculate_location_stock(
        ingredient.id,
        exit_data.location_id,
        db,
    )

    exit_record = IngredientExit(
        ingredient_id=exit_data.ingredient_id,
        quantity=exit_data.quantity,
        reason=exit_data.reason,
        waste_reason=exit_data.waste_reason,
        location_id=exit_data.location_id,
        user_uuid=exit_data.user_uuid,
    )

    db.add(exit_record)
    db.commit()
    db.refresh(exit_record)

    check_inventory_threshold(
        ingredient,
        exit_record.location_id,
        previous_location_stock,
        db,
    )

    currency = currency_for_country(ingredient.country)
    country = country_code(ingredient.country)

    if currency and country:
        properties = {
            "location_id": str(exit_record.location_id),
            "country": country,
            "product_id": str(ingredient.id),
            "product_category": ingredient.category,
            "quantity": exit_record.quantity,
            "unit": ingredient.unit,
            "currency": currency,
            "order_id": str(exit_record.id),
        }

        if exit_record.reason == "waste":
            properties["reason"] = exit_record.waste_reason

        send_telemetry_event(
            "outbound_order_created",
            properties,
        )

        if exit_record.reason == "waste":
            send_telemetry_event(
                "stock_waste_registered",
                {
                    "location_id": str(exit_record.location_id),
                    "country": country,
                    "product_id": str(ingredient.id),
                    "product_category": ingredient.category,
                    "quantity": exit_record.quantity,
                    "unit": ingredient.unit,
                    "reason": exit_record.waste_reason,
                    "currency": currency,
                    "order_id": str(exit_record.id),
                },
            )

    return exit_record


@router.get(
    "/orders",
    response_model=list[IngredientOrderResponse],
)
def get_orders(
    db: Session = Depends(get_db),
):
    inbound_entries = db.exec(
        select(
            IngredientEntry,
            Ingredient,
        )
        .join(
            Ingredient,
            Ingredient.id == IngredientEntry.ingredient_id,
        )
    ).all()

    outbound_exits = db.exec(
        select(
            IngredientExit,
            Ingredient,
        )
        .join(
            Ingredient,
            Ingredient.id == IngredientExit.ingredient_id,
        )
    ).all()

    orders = []

    for entry, ingredient in inbound_entries:
        orders.append(
            IngredientOrderResponse(
                id=entry.id,
                ingredient_id=entry.ingredient_id,
                ingredient_name=ingredient.name,
                type="inbound",
                quantity=entry.quantity,
                supplier_name=entry.supplier_name,
                reason=None,
                location_id=entry.location_id,
                created_at=entry.created_at,
                user_uuid=entry.user_uuid,
            )
        )

    for exit_record, ingredient in outbound_exits:
        orders.append(
            IngredientOrderResponse(
                id=exit_record.id,
                ingredient_id=exit_record.ingredient_id,
                ingredient_name=ingredient.name,
                type="outbound",
                quantity=exit_record.quantity,
                supplier_name=None,
                reason=exit_record.reason,
                location_id=exit_record.location_id,
                created_at=exit_record.created_at,
                user_uuid=exit_record.user_uuid,
            )
        )

    orders.sort(
        key=lambda order: order.created_at,
        reverse=True,
    )

    return orders