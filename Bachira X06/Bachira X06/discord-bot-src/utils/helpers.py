import discord
import config
import re
from datetime import timedelta


def success_embed(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(title=f"✅ {title}", description=description, color=config.SUCCESS_COLOR)


def error_embed(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(title=f"❌ {title}", description=description, color=config.ERROR_COLOR)


def info_embed(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(title=f"ℹ️ {title}", description=description, color=config.INFO_COLOR)


def warning_embed(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(title=f"⚠️ {title}", description=description, color=config.WARNING_COLOR)


def parse_duration(duration_str: str) -> timedelta | None:
    pattern = re.compile(r"(\d+)\s*([smhd])", re.IGNORECASE)
    matches = pattern.findall(duration_str)
    if not matches:
        return None
    total = timedelta()
    unit_map = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}
    for value, unit in matches:
        unit = unit.lower()
        if unit in unit_map:
            total += timedelta(**{unit_map[unit]: int(value)})
    return total if total.total_seconds() > 0 else None


def format_duration(td: timedelta) -> str:
    total = int(td.total_seconds())
    days, remainder = divmod(total, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds:
        parts.append(f"{seconds}s")
    return " ".join(parts) if parts else "0s"


def replace_placeholders(text: str, member: discord.Member) -> str:
    return (
        text.replace("{user}", member.mention)
            .replace("{server}", member.guild.name)
            .replace("{membercount}", str(member.guild.member_count))
            .replace("{username}", str(member))
    )
