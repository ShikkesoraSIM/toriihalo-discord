from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import aiosqlite


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def dt_to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat()


def iso_to_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value).astimezone(UTC)


@dataclass(slots=True)
class LinkedAccount:
    discord_user_id: int
    torii_user_id: int
    torii_username: str
    linked_at: datetime


@dataclass(slots=True)
class Wallet:
    discord_user_id: int
    coins: int
    daily_streak: int
    last_daily_at: datetime | None
    last_work_at: datetime | None


class BotDatabase:
    def __init__(self, db_path: str) -> None:
        self._db_path = Path(db_path)
        self._conn: aiosqlite.Connection | None = None
        self._write_lock = asyncio.Lock()

    async def initialize(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self._db_path.as_posix())
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL;")
        await self._conn.execute("PRAGMA foreign_keys=ON;")
        await self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS user_links (
                discord_user_id INTEGER PRIMARY KEY,
                torii_user_id INTEGER NOT NULL,
                torii_username TEXT NOT NULL,
                linked_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS economy_wallets (
                discord_user_id INTEGER PRIMARY KEY,
                coins INTEGER NOT NULL DEFAULT 0,
                daily_streak INTEGER NOT NULL DEFAULT 0,
                last_daily_at TEXT NULL,
                last_work_at TEXT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS economy_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_discord_user_id INTEGER NOT NULL,
                target_discord_user_id INTEGER NULL,
                amount INTEGER NOT NULL,
                kind TEXT NOT NULL,
                metadata TEXT NULL,
                created_at TEXT NOT NULL
            );

            -- Generic key-value store for cog-level state that doesn't
            -- justify its own table (e.g. "last seen upstream realm
            -- schema_version", periodic-task watermarks, one-off flags).
            -- Values are stored as TEXT — callers serialise their own
            -- types in / out. Keep keys namespaced (e.g. "upstream_watch.*"
            -- or "feature_name.*") to avoid collisions between cogs.
            CREATE TABLE IF NOT EXISTS bot_kv (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database is not initialized.")
        return self._conn

    async def link_account(self, discord_user_id: int, torii_user_id: int, torii_username: str) -> None:
        now = dt_to_iso(utc_now())
        async with self._write_lock:
            await self.conn.execute(
                """
                INSERT INTO user_links (discord_user_id, torii_user_id, torii_username, linked_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(discord_user_id)
                DO UPDATE SET
                    torii_user_id=excluded.torii_user_id,
                    torii_username=excluded.torii_username,
                    linked_at=excluded.linked_at
                """,
                (discord_user_id, torii_user_id, torii_username, now),
            )
            await self.conn.commit()

    async def unlink_account(self, discord_user_id: int) -> bool:
        async with self._write_lock:
            cursor = await self.conn.execute(
                "DELETE FROM user_links WHERE discord_user_id=?",
                (discord_user_id,),
            )
            await self.conn.commit()
            return cursor.rowcount > 0

    async def get_linked_account(self, discord_user_id: int) -> LinkedAccount | None:
        cursor = await self.conn.execute(
            "SELECT discord_user_id, torii_user_id, torii_username, linked_at FROM user_links WHERE discord_user_id=?",
            (discord_user_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return LinkedAccount(
            discord_user_id=int(row["discord_user_id"]),
            torii_user_id=int(row["torii_user_id"]),
            torii_username=str(row["torii_username"]),
            linked_at=iso_to_dt(row["linked_at"]) or utc_now(),
        )

    async def _ensure_wallet(self, discord_user_id: int, *, commit: bool = True) -> None:
        now = dt_to_iso(utc_now())
        await self.conn.execute(
            """
            INSERT INTO economy_wallets (discord_user_id, coins, daily_streak, last_daily_at, last_work_at, updated_at)
            VALUES (?, 0, 0, NULL, NULL, ?)
            ON CONFLICT(discord_user_id) DO NOTHING
            """,
            (discord_user_id, now),
        )
        if commit:
            await self.conn.commit()

    async def get_wallet(self, discord_user_id: int, *, in_transaction: bool = False) -> Wallet:
        await self._ensure_wallet(discord_user_id, commit=not in_transaction)
        cursor = await self.conn.execute(
            """
            SELECT discord_user_id, coins, daily_streak, last_daily_at, last_work_at
            FROM economy_wallets
            WHERE discord_user_id=?
            """,
            (discord_user_id,),
        )
        row = await cursor.fetchone()
        if not row:
            raise RuntimeError("Wallet creation failed.")
        return Wallet(
            discord_user_id=int(row["discord_user_id"]),
            coins=int(row["coins"]),
            daily_streak=int(row["daily_streak"]),
            last_daily_at=iso_to_dt(row["last_daily_at"]),
            last_work_at=iso_to_dt(row["last_work_at"]),
        )

    async def _record_transaction(
        self,
        actor_discord_user_id: int,
        amount: int,
        kind: str,
        target_discord_user_id: int | None = None,
        metadata: str | None = None,
    ) -> None:
        now = dt_to_iso(utc_now())
        await self.conn.execute(
            """
            INSERT INTO economy_transactions
            (actor_discord_user_id, target_discord_user_id, amount, kind, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (actor_discord_user_id, target_discord_user_id, amount, kind, metadata, now),
        )

    async def add_coins(self, discord_user_id: int, amount: int, kind: str, metadata: str | None = None) -> int:
        async with self._write_lock:
            await self.conn.execute("BEGIN IMMEDIATE")
            try:
                wallet = await self.get_wallet(discord_user_id, in_transaction=True)
                new_balance = wallet.coins + amount
                if new_balance < 0:
                    raise ValueError("Insufficient balance.")
                now = dt_to_iso(utc_now())
                await self.conn.execute(
                    """
                    UPDATE economy_wallets
                    SET coins=?, updated_at=?
                    WHERE discord_user_id=?
                    """,
                    (new_balance, now, discord_user_id),
                )
                await self._record_transaction(discord_user_id, amount, kind, metadata=metadata)
                await self.conn.commit()
                return new_balance
            except Exception:
                await self.conn.rollback()
                raise

    async def claim_daily(self, discord_user_id: int, minimum: int, maximum: int) -> tuple[int, int, datetime, int]:
        now = utc_now()
        async with self._write_lock:
            await self.conn.execute("BEGIN IMMEDIATE")
            try:
                wallet = await self.get_wallet(discord_user_id, in_transaction=True)
                if wallet.last_daily_at and now - wallet.last_daily_at < timedelta(hours=24):
                    next_claim = wallet.last_daily_at + timedelta(hours=24)
                    raise ValueError(f"cooldown:{int((next_claim - now).total_seconds())}")

                streak = 1
                if wallet.last_daily_at and now - wallet.last_daily_at <= timedelta(hours=48):
                    streak = wallet.daily_streak + 1

                streak_bonus = min(streak, 7) * 10
                reward = random.randint(minimum, maximum) + streak_bonus
                new_balance = wallet.coins + reward

                await self.conn.execute(
                    """
                    UPDATE economy_wallets
                    SET coins=?, daily_streak=?, last_daily_at=?, updated_at=?
                    WHERE discord_user_id=?
                    """,
                    (
                        new_balance,
                        streak,
                        dt_to_iso(now),
                        dt_to_iso(now),
                        discord_user_id,
                    ),
                )
                await self._record_transaction(discord_user_id, reward, "daily", metadata=f"streak={streak}")
                await self.conn.commit()
                return reward, streak, now + timedelta(hours=24), new_balance
            except Exception:
                await self.conn.rollback()
                raise

    async def work(
        self,
        discord_user_id: int,
        minimum: int,
        maximum: int,
        cooldown_minutes: int,
    ) -> tuple[int, datetime, int]:
        now = utc_now()
        cooldown = timedelta(minutes=cooldown_minutes)
        async with self._write_lock:
            await self.conn.execute("BEGIN IMMEDIATE")
            try:
                wallet = await self.get_wallet(discord_user_id, in_transaction=True)
                if wallet.last_work_at and now - wallet.last_work_at < cooldown:
                    next_claim = wallet.last_work_at + cooldown
                    raise ValueError(f"cooldown:{int((next_claim - now).total_seconds())}")

                reward = random.randint(minimum, maximum)
                new_balance = wallet.coins + reward
                await self.conn.execute(
                    """
                    UPDATE economy_wallets
                    SET coins=?, last_work_at=?, updated_at=?
                    WHERE discord_user_id=?
                    """,
                    (new_balance, dt_to_iso(now), dt_to_iso(now), discord_user_id),
                )
                await self._record_transaction(discord_user_id, reward, "work")
                await self.conn.commit()
                return reward, now + cooldown, new_balance
            except Exception:
                await self.conn.rollback()
                raise

    async def coinflip(self, discord_user_id: int, amount: int, won: bool) -> tuple[int, int]:
        if amount <= 0:
            raise ValueError("Amount must be positive.")
        async with self._write_lock:
            await self.conn.execute("BEGIN IMMEDIATE")
            try:
                wallet = await self.get_wallet(discord_user_id)
                if wallet.coins < amount:
                    raise ValueError("Insufficient balance.")

                delta = amount if won else -amount
                new_balance = wallet.coins + delta
                await self.conn.execute(
                    "UPDATE economy_wallets SET coins=?, updated_at=? WHERE discord_user_id=?",
                    (new_balance, dt_to_iso(utc_now()), discord_user_id),
                )
                kind = "coinflip_win" if won else "coinflip_loss"
                await self._record_transaction(discord_user_id, delta, kind, metadata=f"bet={amount}")
                await self.conn.commit()
                return delta, new_balance
            except Exception:
                await self.conn.rollback()
                raise

    async def pay(self, from_user_id: int, to_user_id: int, amount: int) -> tuple[int, int]:
        if amount <= 0:
            raise ValueError("Amount must be positive.")
        if from_user_id == to_user_id:
            raise ValueError("Cannot transfer to yourself.")

        async with self._write_lock:
            await self.conn.execute("BEGIN IMMEDIATE")
            try:
                from_wallet = await self.get_wallet(from_user_id, in_transaction=True)
                to_wallet = await self.get_wallet(to_user_id, in_transaction=True)
                if from_wallet.coins < amount:
                    raise ValueError("Insufficient balance.")

                now = dt_to_iso(utc_now())
                await self.conn.execute(
                    "UPDATE economy_wallets SET coins=?, updated_at=? WHERE discord_user_id=?",
                    (from_wallet.coins - amount, now, from_user_id),
                )
                await self.conn.execute(
                    "UPDATE economy_wallets SET coins=?, updated_at=? WHERE discord_user_id=?",
                    (to_wallet.coins + amount, now, to_user_id),
                )
                await self._record_transaction(
                    from_user_id,
                    -amount,
                    "pay_out",
                    target_discord_user_id=to_user_id,
                )
                await self._record_transaction(
                    to_user_id,
                    amount,
                    "pay_in",
                    target_discord_user_id=from_user_id,
                )
                await self.conn.commit()
                return from_wallet.coins - amount, to_wallet.coins + amount
            except Exception:
                await self.conn.rollback()
                raise

    # ---------------------------------------------------------------
    #  Generic key-value store (bot_kv)
    # ---------------------------------------------------------------

    async def kv_get(self, key: str) -> str | None:
        """Read a value from the cog-shared KV table. Returns None if unset."""
        cursor = await self.conn.execute("SELECT value FROM bot_kv WHERE key=?", (key,))
        row = await cursor.fetchone()
        if not row:
            return None
        return str(row["value"])

    async def kv_set(self, key: str, value: str) -> None:
        """Upsert a value into the cog-shared KV table."""
        now = dt_to_iso(utc_now())
        async with self._write_lock:
            await self.conn.execute(
                """
                INSERT INTO bot_kv (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key)
                DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                """,
                (key, value, now),
            )
            await self.conn.commit()

    async def top_wallets(self, limit: int = 10) -> list[tuple[int, int, str | None]]:
        safe_limit = max(1, min(limit, 50))
        cursor = await self.conn.execute(
            """
            SELECT
              w.discord_user_id,
              w.coins,
              l.torii_username
            FROM economy_wallets w
            LEFT JOIN user_links l ON l.discord_user_id = w.discord_user_id
            ORDER BY w.coins DESC, w.discord_user_id ASC
            LIMIT ?
            """,
            (safe_limit,),
        )
        rows = await cursor.fetchall()
        return [(int(r["discord_user_id"]), int(r["coins"]), r["torii_username"]) for r in rows]
