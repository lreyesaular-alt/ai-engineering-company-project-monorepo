"""Acceso a PostgreSQL para los trabajos en segundo plano."""

from data.pipelines.run_registry import get_engine


__all__ = ["get_engine"]
