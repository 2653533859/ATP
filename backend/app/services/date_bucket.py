"""Portable daily and Monday-based weekly grouping for run statistics."""

from sqlalchemy import Date, cast, func

from app.core.config import settings


def date_bucket(created_at_column, aggregate: str):
    if settings.ATP_LOCAL_MODE:
        if aggregate == "weekly":
            # SQLite weekday 0 moves to Sunday; subtract six days for Monday.
            return func.date(created_at_column, "weekday 0", "-6 days")
        return func.date(created_at_column)
    if aggregate == "weekly":
        return func.date_trunc("week", created_at_column)
    return cast(created_at_column, Date)
