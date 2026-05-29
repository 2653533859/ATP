from alembic import command
from alembic.config import Config


def main() -> None:
    """Apply database migrations to head.

    Kept for old runbooks that call `python -m app.bootstrap_db`; the behavior is
    now intentionally Alembic-only.
    """
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")


if __name__ == "__main__":
    main()
