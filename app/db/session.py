from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.models import Base


settings = get_settings()
engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if conn.dialect.name == "postgresql":
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS default_currency VARCHAR(8) DEFAULT 'PLN'"))
            await conn.execute(text("UPDATE users SET default_currency = 'PLN' WHERE default_currency IS NULL"))
            await conn.execute(text("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS user_tx_number INTEGER"))
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS budget_limits (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        category VARCHAR(64) NOT NULL,
                        currency VARCHAR(8) DEFAULT 'PLN',
                        amount NUMERIC(12, 2) NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
                        CONSTRAINT uq_budget_limits_user_category_currency UNIQUE (user_id, category, currency)
                    )
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    WITH existing AS (
                        SELECT user_id, coalesce(max(user_tx_number), 0) AS max_number
                        FROM transactions
                        GROUP BY user_id
                    ),
                    ranked AS (
                        SELECT
                            tx.id,
                            coalesce(existing.max_number, 0)
                                + row_number() OVER (PARTITION BY tx.user_id ORDER BY tx.created_at, tx.id) AS number
                        FROM transactions
                        AS tx
                        LEFT JOIN existing ON existing.user_id = tx.user_id
                        WHERE user_tx_number IS NULL
                    )
                    UPDATE transactions
                    SET user_tx_number = ranked.number
                    FROM ranked
                    WHERE transactions.id = ranked.id
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS ix_transactions_user_tx_number_unique
                    ON transactions(user_id, user_tx_number)
                    WHERE user_tx_number IS NOT NULL
                    """
                )
            )


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
