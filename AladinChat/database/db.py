import os
from typing import Optional

import asyncpg


DATABASE_URL = os.getenv("DATABASE_URL")

_pool: Optional[asyncpg.Pool] = None


async def init_db():
    global _pool

    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL не найден")

    _pool = await asyncpg.create_pool(DATABASE_URL)

    async with _pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE NOT NULL,
                username TEXT,
                name TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS user_memory (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                interests TEXT DEFAULT '',
                crypto_knowledge TEXT DEFAULT '',
                staking_interest TEXT DEFAULT '',
                concerns TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                summary TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS user_stage (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                stage TEXT DEFAULT 'new',
                started_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS bot_config (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)


async def close_db():
    global _pool

    if _pool:
        await _pool.close()
        _pool = None


async def add_user(
    telegram_id: int,
    username: Optional[str] = None,
    name: Optional[str] = None,
):
    async with _pool.acquire() as conn:
        user = await conn.fetchrow("""
            INSERT INTO users (telegram_id, username, name)
            VALUES ($1, $2, $3)
            ON CONFLICT (telegram_id)
            DO UPDATE SET
                username = EXCLUDED.username,
                name = EXCLUDED.name,
                updated_at = NOW()
            RETURNING *;
        """, telegram_id, username, name)

        await conn.execute("""
            INSERT INTO user_memory (user_id)
            VALUES ($1)
            ON CONFLICT (user_id) DO NOTHING;
        """, user["id"])

        await conn.execute("""
            INSERT INTO user_stage (user_id)
            VALUES ($1)
            ON CONFLICT (user_id) DO NOTHING;
        """, user["id"])

        return user


async def get_user(telegram_id: int):
    async with _pool.acquire() as conn:
        return await conn.fetchrow("""
            SELECT *
            FROM users
            WHERE telegram_id = $1;
        """, telegram_id)


async def delete_user(telegram_id: int):
    async with _pool.acquire() as conn:
        result = await conn.execute("""
            DELETE FROM users
            WHERE telegram_id = $1;
        """, telegram_id)

        return result


async def save_message(
    telegram_id: int,
    role: str,
    content: str,
):
    async with _pool.acquire() as conn:
        user = await conn.fetchrow("""
            SELECT id
            FROM users
            WHERE telegram_id = $1;
        """, telegram_id)

        if not user:
            return

        await conn.execute("""
            INSERT INTO messages (user_id, role, content)
            VALUES ($1, $2, $3);
        """, user["id"], role, content)


async def get_messages(
    telegram_id: int,
    limit: int = 20,
):
    async with _pool.acquire() as conn:
        return await conn.fetch("""
            SELECT m.role, m.content, m.created_at
            FROM messages m
            JOIN users u ON u.id = m.user_id
            WHERE u.telegram_id = $1
            ORDER BY m.created_at DESC
            LIMIT $2;
        """, telegram_id, limit)


async def get_memory(telegram_id: int):
    async with _pool.acquire() as conn:
        return await conn.fetchrow("""
            SELECT m.*
            FROM user_memory m
            JOIN users u ON u.id = m.user_id
            WHERE u.telegram_id = $1;
        """, telegram_id)


async def update_memory(
    telegram_id: int,
    interests: Optional[str] = None,
    crypto_knowledge: Optional[str] = None,
    staking_interest: Optional[str] = None,
    concerns: Optional[str] = None,
    notes: Optional[str] = None,
    summary: Optional[str] = None,
):
    fields = []
    values = []
    index = 1

    data = {
        "interests": interests,
        "crypto_knowledge": crypto_knowledge,
        "staking_interest": staking_interest,
        "concerns": concerns,
        "notes": notes,
        "summary": summary,
    }

    for field, value in data.items():
        if value is not None:
            fields.append(f"{field} = ${index}")
            values.append(value)
            index += 1

    if not fields:
        return

    values.append(telegram_id)

    async with _pool.acquire() as conn:
        await conn.execute(
            f"""
            UPDATE user_memory
            SET {", ".join(fields)}
            WHERE user_id = (
                SELECT id
                FROM users
                WHERE telegram_id = ${index}
            );
            """,
            *values,
        )


async def get_stage(telegram_id: int):
    async with _pool.acquire() as conn:
        return await conn.fetchrow("""
            SELECT s.*
            FROM user_stage s
            JOIN users u ON u.id = s.user_id
            WHERE u.telegram_id = $1;
        """, telegram_id)


async def set_stage(
    telegram_id: int,
    stage: str,
):
    async with _pool.acquire() as conn:
        await conn.execute("""
            UPDATE user_stage
            SET stage = $1,
                updated_at = NOW()
            WHERE user_id = (
                SELECT id
                FROM users
                WHERE telegram_id = $2
            );
        """, stage, telegram_id)


async def get_config(
    key: str,
    default: Optional[str] = None,
):
    async with _pool.acquire() as conn:
        value = await conn.fetchval("""
            SELECT value
            FROM bot_config
            WHERE key = $1;
        """, key)

        return value if value is not None else default


async def set_config(
    key: str,
    value: str,
):
    async with _pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO bot_config (key, value)
            VALUES ($1, $2)
            ON CONFLICT (key)
            DO UPDATE SET value = EXCLUDED.value;
        """, key, value)