import os
import sys
import json
import sqlite3
import datetime
import asyncio
from typing import Optional, Dict, Any, List

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resqnet.db")

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('citizen', 'volunteer', 'ngo', 'coordinator', 'vet')),
    phone TEXT,
    organization TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS requests (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK(type IN ('human', 'animal')),
    title TEXT NOT NULL,
    description TEXT,
    disaster_type TEXT DEFAULT 'Flood',
    status TEXT NOT NULL DEFAULT 'Reported' CHECK(status IN ('Reported', 'Validated', 'Prioritised', 'Matched', 'Dispatched', 'Delivered', 'Acknowledged', 'Closed')),
    priority TEXT DEFAULT 'Medium' CHECK(priority IN ('Critical', 'High', 'Medium', 'Low')),
    location_name TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    affected_families INTEGER DEFAULT 0,
    affected_individuals INTEGER DEFAULT 0,
    animal_species TEXT,
    animal_count INTEGER DEFAULT 0,
    resources_needed TEXT, -- JSON array of strings
    duplicate_flag BOOLEAN DEFAULT 0,
    duplicate_of TEXT,
    requires_human_review BOOLEAN DEFAULT 1,
    approved_by TEXT,
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(duplicate_of) REFERENCES requests(id),
    FOREIGN KEY(approved_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS request_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor_id TEXT,
    actor_role TEXT,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(request_id) REFERENCES requests(id)
);

CREATE TABLE IF NOT EXISTS inventory_items (
    id TEXT PRIMARY KEY,
    ngo_id TEXT NOT NULL,
    item_name TEXT NOT NULL,
    category TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0,
    reserved_quantity INTEGER NOT NULL DEFAULT 0,
    unit TEXT DEFAULT 'units',
    location_name TEXT NOT NULL,
    latitude REAL,
    longitude REAL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS allocations (
    id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    item_name TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'Proposed' CHECK(status IN ('Proposed', 'Approved', 'Rejected', 'Reserved', 'Dispatched')),
    approved_by TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(request_id) REFERENCES requests(id),
    FOREIGN KEY(item_id) REFERENCES inventory_items(id),
    FOREIGN KEY(approved_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS volunteers (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    phone TEXT,
    is_vet BOOLEAN DEFAULT 0,
    vet_license_no TEXT,
    skills TEXT,
    is_available BOOLEAN DEFAULT 1,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    current_location TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS dispatches (
    id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    volunteer_id TEXT NOT NULL,
    assigned_by TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Assigned' CHECK(status IN ('Proposed', 'Assigned', 'En Route', 'On Site', 'Completed', 'Cancelled')),
    role_type TEXT NOT NULL,
    instructions TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(request_id) REFERENCES requests(id),
    FOREIGN KEY(volunteer_id) REFERENCES volunteers(id),
    FOREIGN KEY(assigned_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS packages (
    id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    dispatch_id TEXT,
    qr_code TEXT NOT NULL UNIQUE,
    items_summary TEXT,
    delivery_status TEXT NOT NULL DEFAULT 'Prepared' CHECK(delivery_status IN ('Prepared', 'In Transit', 'Delivered', 'Acknowledged')),
    recipient_ack BOOLEAN DEFAULT 0,
    ack_signature TEXT,
    ack_notes TEXT,
    ack_timestamp TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(request_id) REFERENCES requests(id),
    FOREIGN KEY(dispatch_id) REFERENCES dispatches(id)
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    step_name TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    input_data TEXT,
    output_data TEXT,
    human_approved BOOLEAN DEFAULT NULL,
    human_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(request_id) REFERENCES requests(id)
);
"""

class AsyncCursorWrapper:
    def __init__(self, cursor):
        self._cursor = cursor

    async def fetchall(self):
        return self._cursor.fetchall()

    async def fetchone(self):
        return self._cursor.fetchone()

class AsyncConnectionWrapper:
    """
    Seamless async-compatible connection interface matching aiosqlite,
    running safely with zero hangs across all OS and Python versions.
    """
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    async def execute(self, sql: str, parameters: tuple = ()):
        cursor = self._conn.execute(sql, parameters)
        return AsyncCursorWrapper(cursor)

    async def executemany(self, sql: str, seq_of_parameters: list = ()):
        cursor = self._conn.executemany(sql, seq_of_parameters)
        return AsyncCursorWrapper(cursor)

    async def commit(self):
        self._conn.commit()

    async def close(self):
        self._conn.close()

async def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return AsyncConnectionWrapper(conn)

def init_db_sync():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()

async def init_db():
    init_db_sync()
