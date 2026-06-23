import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

DATABASE_PATH = "database/bot.db"

DEFAULT_COLOR = 0x5865F2
SUCCESS_COLOR = 0x57F287
ERROR_COLOR = 0xED4245
WARNING_COLOR = 0xFEE75C
INFO_COLOR = 0x5865F2

COGS = [
    "cogs.moderation",
    "cogs.logging",
    "cogs.tickets",
    "cogs.giveaways",
    "cogs.polls",
    "cogs.welcome",
    "cogs.reaction_roles",
    "cogs.suggestions",
    "cogs.utility",
    "cogs.dm_system",
    "cogs.minecraft",
    "cogs.invite_tracker",
]
