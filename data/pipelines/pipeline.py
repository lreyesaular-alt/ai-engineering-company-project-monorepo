"""Pipeline semanal de desempeño de negocio de Brasaland."""

import argparse
from datetime import date, timedelta
from pathlib import Path


def parse_week_start(value: str) -> date:
    """Valida que la fecha sea ISO y corresponda a un lunes."""
    try:
        week_start = date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "week_start debe tener formato YYYY-MM-DD."
        ) from exc

    if week_start.isoformat() != value:
        raise argparse.ArgumentTypeError(
            "week_start debe tener formato YYYY-MM-DD."
        )

    if week_start.weekday() != 0:
        raise argparse.ArgumentTypeError(
            "week_start debe corresponder a un lunes."
        )

    return week_start


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pipeline semanal de desempeño de Brasaland."
    )
    parser.add_argument(
        "--week-start",
        required=True,
        type=parse_week_start,
        help="Lunes de la semana a procesar (YYYY-MM-DD).",
    )
    args = parser.parse_args()

    print(f"Semana validada: {args.week_start.isoformat()}")
    result = weekly_performance_flow(args.week_start.isoformat())
    print(f"Filas procesadas: {result}")
from prefect import flow, task
from prefect.cache_policies import INPUTS


@task(name="extract-telemetry", retries=2, retry_delay_seconds=5)
def extract_telemetry(week_start: str) -> list[dict]:
    """Extrae los eventos relevantes de una semana desde PostgreSQL."""
    from datetime import timedelta
    from dotenv import dotenv_values
    from sqlalchemy import create_engine, text

    start_date = date.fromisoformat(week_start)
    end_date = start_date + timedelta(days=7)

    repo_root = Path(__file__).resolve().parents[2]
    env_path = repo_root / "services" / "api" / ".env"
    database_url = dotenv_values(env_path).get("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL no esta configurada.")

    query = text("""
        SELECT timestamp, event_type, tags
        FROM public.telemetry_events
        WHERE timestamp >= :start_date
          AND timestamp < :end_date
          AND event_type IN (
              'inbound_order_created',
              'stock_waste_registered',
              'stock_threshold_triggered',
              'ingredient_price_variance_detected'
          )
        ORDER BY timestamp
    """)

    engine = create_engine(
        database_url,
        echo=False,
        connect_args={"connect_timeout": 10},
    )

    try:
        with engine.connect() as connection:
            rows = connection.execute(
                query,
                {"start_date": start_date, "end_date": end_date},
            ).mappings().all()

        events = [dict(row) for row in rows]
        print(f"Eventos extraidos: {len(events)}")
        return events
    finally:
        engine.dispose()


@task(
    name="transform-weekly-kpis",
    cache_policy=INPUTS,
    cache_expiration=timedelta(hours=1),
)
def transform_weekly_kpis(events: list[dict]) -> list[dict]:
    """Agrupa eventos por ubicacion y semana, validando los costos."""
    from collections import defaultdict
    from decimal import Decimal, InvalidOperation

    grouped = {}

    for event in events:
        tags = event.get("tags") or {}
        location_id = tags.get("location_id")
        country = tags.get("country")
        currency = tags.get("currency") or {
            "CO": "COP",
            "US": "USD",
        }.get(country)

        if not location_id or country not in ("CO", "US"):
            raise ValueError("Evento sin ubicacion o pais valido.")

        if currency != {"CO": "COP", "US": "USD"}[country]:
            raise ValueError("Moneda incompatible con el pais.")

        event_date = event["timestamp"].date()
        week_start = event_date.fromordinal(
            event_date.toordinal() - event_date.weekday()
        )

        key = (location_id, week_start)

        if key not in grouped:
            grouped[key] = {
                "location_id": location_id,
                "country": country,
                "currency": currency,
                "week_start": week_start,
                "total_purchase_cost": Decimal("0"),
                "total_waste_cost": Decimal("0"),
                "stockout_events_count": 0,
                "price_alert_events_count": 0,
            }

        row = grouped[key]

        if row["country"] != country or row["currency"] != currency:
            raise ValueError("Pais o moneda inconsistente para la ubicacion.")

        event_type = event["event_type"]

        if event_type in ("inbound_order_created", "stock_waste_registered"):
            raw_cost = tags.get("total_cost")

            if raw_cost is None:
                raise ValueError(
                    f"Costo monetario faltante en {event_type}; "
                    f"location_id={location_id}"
                )

            try:
                cost = Decimal(str(raw_cost))
            except InvalidOperation as exc:
                raise ValueError("Costo monetario invalido.") from exc

            if not cost.is_finite() or cost < 0:
                raise ValueError("Costo monetario debe ser finito y no negativo.")

            field = (
                "total_purchase_cost"
                if event_type == "inbound_order_created"
                else "total_waste_cost"
            )
            row[field] += cost

        elif event_type == "stock_threshold_triggered":
            row["stockout_events_count"] += 1

        elif event_type == "ingredient_price_variance_detected":
            row["price_alert_events_count"] += 1

    results = []

    for row in grouped.values():
        purchases = row["total_purchase_cost"]
        waste = row["total_waste_cost"]
        row["waste_ratio"] = waste / purchases if purchases else Decimal("0")
        results.append(row)

    print(f"Ubicaciones-semana transformadas: {len(results)}")
    return results


@task(name="load-weekly-report", retries=2, retry_delay_seconds=5)
def load_weekly_report(rows: list[dict]) -> int:
    """Guarda los KPIs mediante UPSERT idempotente."""
    from dotenv import dotenv_values
    from sqlalchemy import create_engine, text

    if not rows:
        print("Sin filas para cargar.")
        return 0

    repo_root = Path(__file__).resolve().parents[2]
    env_path = repo_root / "services" / "api" / ".env"
    database_url = dotenv_values(env_path).get("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL no esta configurada.")

    query = text("""
        INSERT INTO reporting.weekly_location_performance (
            location_id,
            country,
            week_start,
            total_purchase_cost,
            total_waste_cost,
            waste_ratio,
            stockout_events_count,
            price_alert_events_count,
            currency
        )
        VALUES (
            :location_id,
            :country,
            :week_start,
            :total_purchase_cost,
            :total_waste_cost,
            :waste_ratio,
            :stockout_events_count,
            :price_alert_events_count,
            :currency
        )
        ON CONFLICT (location_id, week_start)
        DO UPDATE SET
            country = EXCLUDED.country,
            total_purchase_cost = EXCLUDED.total_purchase_cost,
            total_waste_cost = EXCLUDED.total_waste_cost,
            waste_ratio = EXCLUDED.waste_ratio,
            stockout_events_count = EXCLUDED.stockout_events_count,
            price_alert_events_count = EXCLUDED.price_alert_events_count,
            currency = EXCLUDED.currency,
            computed_at = NOW()
    """)

    engine = create_engine(
        database_url,
        echo=False,
        connect_args={"connect_timeout": 10},
    )

    try:
        with engine.begin() as connection:
            connection.execute(query, rows)

        print(f"Filas guardadas o actualizadas: {len(rows)}")
        return len(rows)
    finally:
        engine.dispose()


@task(name="optional-run-summary")
def optional_run_summary(week_start: str, row_count: int) -> None:
    """Registra un resumen informativo, no critico para el ETL."""
    from prefect import get_run_logger

    logger = get_run_logger()
    logger.info(
        "Resumen opcional: semana=%s, filas=%s",
        week_start,
        row_count,
    )


@flow(name="brasaland-weekly-performance")
def weekly_performance_flow(week_start: str) -> int:
    """Ejecuta el ETL y registra su resultado en PostgreSQL."""
    from prefect import get_run_logger
    try:
        from data.pipelines.run_registry import (
            start_pipeline_run,
            finish_pipeline_run,
        )
    except ModuleNotFoundError as exc:
        if exc.name not in ("data", "data.pipelines"):
            raise
        from run_registry import (
        start_pipeline_run,
        finish_pipeline_run,
    )

    logger = get_run_logger()
    run_id = start_pipeline_run(date.fromisoformat(week_start))

    logger.info(
        "Pipeline iniciado: run_id=%s, week_start=%s",
        run_id,
        week_start,
    )

    try:
        events = extract_telemetry(week_start)
        rows = transform_weekly_kpis(events)
        row_count = load_weekly_report(rows)
    except Exception as exc:
        try:
            finish_pipeline_run(
                run_id,
                status="failed",
                error_message=f"{type(exc).__name__}: {exc}"[:1000],
            )
        except Exception:
            logger.exception(
                "No se pudo registrar el fallo: run_id=%s",
                run_id,
            )
        raise

    finish_pipeline_run(
        run_id,
        status="completed",
        rows_processed=row_count,
    )

    try:
        optional_run_summary(week_start, row_count)
    except Exception as exc:
        logger.warning(
            "La tarea opcional fallo; el ETL principal termino: %s",
            exc,
        )

    logger.info(
        "Pipeline completado: run_id=%s, filas=%s",
        run_id,
        row_count,
    )
    return row_count


if __name__ == "__main__":
    main()
