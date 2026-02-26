from __future__ import annotations

from sqlalchemy import text

from app.database import init_db, engine


def main() -> None:
    if not init_db():
        raise SystemExit("DATABASE_URL not configured or connection failed.")

    with engine.connect() as conn:  # type: ignore[union-attr]
        rows = conn.execute(text("DESCRIBE predictions")).fetchall()

    for row in rows:
        print(tuple(row))


if __name__ == "__main__":
    main()

