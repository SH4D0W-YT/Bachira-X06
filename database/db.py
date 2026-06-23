import aiosqlite
import config

DB = config.DATABASE_PATH


async def init_db():
    import os
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    async with aiosqlite.connect(DB) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                moderator_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                log_channel INTEGER,
                invite_log_channel INTEGER,
                welcome_channel INTEGER,
                goodbye_channel INTEGER,
                welcome_message TEXT DEFAULT 'Welcome {user} to {server}! You are member #{membercount}.',
                goodbye_message TEXT DEFAULT '{user} has left {server}. We now have {membercount} members.',
                auto_role INTEGER,
                mute_role INTEGER,
                suggestion_channel INTEGER,
                ticket_category INTEGER,
                ticket_log_channel INTEGER,
                giveaway_log_channel INTEGER,
                owner_id INTEGER,
                anti_spam INTEGER DEFAULT 0,
                anti_links INTEGER DEFAULT 0,
                anti_badwords INTEGER DEFAULT 0,
                badwords TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS mutes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                expires_at DATETIME,
                moderator_id INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                claimed_by INTEGER,
                status TEXT DEFAULT 'open',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS giveaways (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL UNIQUE,
                prize TEXT NOT NULL,
                winners INTEGER DEFAULT 1,
                host_id INTEGER NOT NULL,
                ends_at DATETIME NOT NULL,
                ended INTEGER DEFAULT 0,
                participants TEXT DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS polls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL UNIQUE,
                question TEXT NOT NULL,
                options TEXT NOT NULL,
                votes TEXT NOT NULL,
                anonymous INTEGER DEFAULT 0,
                ended INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS reaction_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                emoji TEXT,
                label TEXT
            );

            CREATE TABLE IF NOT EXISTS dm_conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                owner_message_channel INTEGER,
                last_message DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS dm_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                sender_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES dm_conversations(id)
            );

            CREATE TABLE IF NOT EXISTS spam_tracker (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                message_count INTEGER DEFAULT 0,
                window_start DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS invite_watch (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(guild_id, user_id)
            );
        """)
        await db.commit()
        async with db.execute("PRAGMA table_info(guild_settings)") as cursor:
            existing_columns = [row[1] async for row in cursor]
        if "invite_log_channel" not in existing_columns:
            await db.execute("ALTER TABLE guild_settings ADD COLUMN invite_log_channel INTEGER")
            await db.commit()


async def get_guild_settings(guild_id: int) -> dict:
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM guild_settings WHERE guild_id = ?", (guild_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            await db.execute(
                "INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)", (guild_id,)
            )
            await db.commit()
            async with db.execute(
                "SELECT * FROM guild_settings WHERE guild_id = ?", (guild_id,)
            ) as c2:
                row2 = await c2.fetchone()
                return dict(row2) if row2 else {}


async def update_guild_setting(guild_id: int, key: str, value):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            f"INSERT INTO guild_settings (guild_id, {key}) VALUES (?, ?) "
            f"ON CONFLICT(guild_id) DO UPDATE SET {key} = excluded.{key}",
            (guild_id, value),
        )
        await db.commit()


async def add_invite_watch(guild_id: int, user_id: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR IGNORE INTO invite_watch (guild_id, user_id) VALUES (?, ?)",
            (guild_id, user_id),
        )
        await db.commit()


async def has_invite_watch(guild_id: int, user_id: int) -> bool:
    async with aiosqlite.connect(DB) as db:
        async with db.execute(
            "SELECT 1 FROM invite_watch WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ) as cursor:
            row = await cursor.fetchone()
            return row is not None


async def remove_invite_watch(guild_id: int, user_id: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "DELETE FROM invite_watch WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        await db.commit()
