"""Consultas de reporting semanal de Brasaland."""

from datetime import date
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import create_engine, text


def get_weekly_location_performance(week_start: date) -> list[dict]:
    """Obtiene los KPIs por ubicacion para una semana."""
    if week_start.weekday() != 0:
        raise ValueError("week_start debe corresponder a un lunes.")

    repo_root = Path(__file__).resolve().parents[2]
    env_path = repo_root / "services" / "api" / ".env"
    database_url = dotenv_values(env_path).get("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL no esta configurada.")

    query = text("""
        SELECT
            location_id,
            country,
            week_start,
            total_purchase_cost,
            total_waste_cost,
            waste_ratio,
            stockout_events_count,
            price_alert_events_count,
            currency,
            computed_at
        FROM reporting.weekly_location_performance
        WHERE week_start = :week_start
        ORDER BY country, location_id
    """)

    engine = create_engine(
        database_url,
        echo=False,
        connect_args={"connect_timeout": 10},
    )

    try:
        with engine.connect() as connection:
            records = connection.execute(
                query,
                {"week_start": week_start},
            ).mappings().all()

        return [
            {
                key: (
                    value.isoformat()
                    if isinstance(value, date)
                    else float(value)
                    if key in (
                        "total_purchase_cost",
                        "total_waste_cost",
                        "waste_ratio",
                    )
                    else value
                )
                for key, value in dict(record).items()
            }
            for record in records
        ]
    finally:
        engine.dispose()
