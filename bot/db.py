"""Baza de date SQLite (evenimente, înscrieri, anunțuri de schimb, reputație, știri)."""
from __future__ import annotations

import os
from pathlib import Path

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    message_id INTEGER,
    title TEXT NOT NULL,
    game TEXT,
    description TEXT,
    starts_at INTEGER NOT NULL,
    capacity INTEGER,
    created_by INTEGER NOT NULL,
    reminded_24h INTEGER DEFAULT 0,
    reminded_1h INTEGER DEFAULT 0,
    cancelled INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS rsvps (
    event_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    PRIMARY KEY (event_id, user_id)
);
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    thread_id INTEGER,
    message_id INTEGER,
    user_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    closed INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS reputation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    giver_id INTEGER NOT NULL,
    note TEXT,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS feeds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    url TEXT NOT NULL,
    channel_id INTEGER NOT NULL,
    name TEXT,
    initialized INTEGER DEFAULT 0,
    UNIQUE (guild_id, url, channel_id)
);
CREATE TABLE IF NOT EXISTS feed_seen (
    feed_id INTEGER NOT NULL,
    entry_id TEXT NOT NULL,
    PRIMARY KEY (feed_id, entry_id)
);
"""


async def connect() -> aiosqlite.Connection:
    data_dir = Path(os.environ.get("DATA_DIR", "./data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(data_dir / "cmc.db")
    db.row_factory = aiosqlite.Row
    await db.executescript(SCHEMA)
    await db.commit()
    return db
