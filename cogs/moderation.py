import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
from datetime import datetime, timezone
import config
from database.db import get_guild_settings, update_guild_setting
from utils.helpers import success_embed, error_embed, info_embed, warning_embed, parse_duration, format_duration


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_or_create_mute_role(self, guild: discord.Guild) -> discord.Role:
        settings = await get_guild_settings(guild.id)
        mute_role_id = settings.get("mute_role")
        if mute_role_id:
            role = guild.get_role(mute_role_id)
            if role:
                return role
        role = await guild.create_role(name="Muted", color=discord.Color.dark_gray(), reason="Auto-created Muted role")
        for channel in guild.channels:
            try:
                await channel.set_permissions(role, send_messages=False, speak=False, add_reactions=False)
            except Exception:
                pass
        await update_guild_setting(guild.id, "mute_role", role.id)
        return role

    async def log_action(self, guild: discord.Guild, embed: discord.Embed):
        settings = await get_guild_settings(guild.id)
        log_channel_id = settings.get("log_channel")
        if log_channel_id:
            channel = guild.get_channel(log_channel_id)
            if channel:
                try:
                    await channel.send(embed=embed)
                except Exception:
                    pass

    @app_commands.command(name="ban", description="Ban a member from the server")
    @app_commands.describe(user="The user to ban", reason="Reason for the ban")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
        if user.top_role >= interaction.user.top_role:
            return await interaction.response.send_message(embed=error_embed("Permission Error", "You cannot ban someone with an equal or higher role."), ephemeral=True)
        try:
            await user.send(embed=info_embed(f"Banned from {interaction.guild.name}", f"**Reason:** {reason}"))
        except Exception:
            pass
        await user.ban(reason=f"{reason} | By: {interaction.user}")
        embed = success_embed("Member Banned", f"**User:** {user.mention}\n**Reason:** {reason}\n**Moderator:** {interaction.user.mention}")
        await interaction.response.send_message(embed=embed)
        log_embed = discord.Embed(title="🔨 Member Banned", color=config.ERROR_COLOR, timestamp=datetime.now(timezone.utc))
        log_embed.add_field(name="User", value=f"{user} ({user.id})")
        log_embed.add_field(name="Moderator", value=str(interaction.user))
        log_embed.add_field(name="Reason", value=reason)
        await self.log_action(interaction.guild, log_embed)

    @app_commands.command(name="unban", description="Unban a user by ID")
    @app_commands.describe(user_id="The ID of the user to unban")
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str):
        try:
            uid = int(user_id)
            user = await self.bot.fetch_user(uid)
            await interaction.guild.unban(user)
            await interaction.response.send_message(embed=success_embed("Member Unbanned", f"**User:** {user} ({user.id})"))
        except discord.NotFound:
            await interaction.response.send_message(embed=error_embed("Not Found", "That user is not banned or doesn't exist."), ephemeral=True)

    @app_commands.command(name="kick", description="Kick a member from the server")
    @app_commands.describe(user="The user to kick", reason="Reason for the kick")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
        if user.top_role >= interaction.user.top_role:
            return await interaction.response.send_message(embed=error_embed("Permission Error", "You cannot kick someone with an equal or higher role."), ephemeral=True)
        try:
            await user.send(embed=info_embed(f"Kicked from {interaction.guild.name}", f"**Reason:** {reason}"))
        except Exception:
            pass
        await user.kick(reason=f"{reason} | By: {interaction.user}")
        await interaction.response.send_message(embed=success_embed("Member Kicked", f"**User:** {user.mention}\n**Reason:** {reason}"))

    @app_commands.command(name="mute", description="Mute a member")
    @app_commands.describe(user="The user to mute", duration="Duration (e.g. 10m, 1h, 2d)", reason="Reason")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def mute(self, interaction: discord.Interaction, user: discord.Member, duration: str = "10m", reason: str = "No reason provided"):
        await interaction.response.defer()
        td = parse_duration(duration)
        if not td:
            return await interaction.followup.send(embed=error_embed("Invalid Duration", "Use formats like `10m`, `1h`, `2d`."), ephemeral=True)
        mute_role = await self.get_or_create_mute_role(interaction.guild)
        await user.add_roles(mute_role, reason=reason)
        expires_at = datetime.now(timezone.utc) + td
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO mutes (guild_id, user_id, expires_at, moderator_id) VALUES (?,?,?,?)",
                (interaction.guild.id, user.id, expires_at.isoformat(), interaction.user.id)
            )
            await db.commit()
        await interaction.followup.send(embed=success_embed("Member Muted", f"**User:** {user.mention}\n**Duration:** {format_duration(td)}\n**Reason:** {reason}"))

    @app_commands.command(name="unmute", description="Unmute a member")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def unmute(self, interaction: discord.Interaction, user: discord.Member):
        settings = await get_guild_settings(interaction.guild.id)
        mute_role_id = settings.get("mute_role")
        if not mute_role_id:
            return await interaction.response.send_message(embed=error_embed("No Mute Role", "No mute role configured."), ephemeral=True)
        mute_role = interaction.guild.get_role(mute_role_id)
        if mute_role and mute_role in user.roles:
            await user.remove_roles(mute_role)
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            await db.execute("DELETE FROM mutes WHERE guild_id = ? AND user_id = ?", (interaction.guild.id, user.id))
            await db.commit()
        await interaction.response.send_message(embed=success_embed("Member Unmuted", f"**User:** {user.mention}"))

    @app_commands.command(name="warn", description="Warn a member")
    @app_commands.describe(user="The user to warn", reason="Reason for the warning")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def warn(self, interaction: discord.Interaction, user: discord.Member, reason: str):
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            await db.execute(
                "INSERT INTO warnings (guild_id, user_id, moderator_id, reason) VALUES (?,?,?,?)",
                (interaction.guild.id, user.id, interaction.user.id, reason)
            )
            await db.commit()
        try:
            await user.send(embed=warning_embed(f"Warning in {interaction.guild.name}", f"**Reason:** {reason}"))
        except Exception:
            pass
        await interaction.response.send_message(embed=success_embed("Member Warned", f"**User:** {user.mention}\n**Reason:** {reason}"))

    @app_commands.command(name="warnings", description="View warnings for a member")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def warnings(self, interaction: discord.Interaction, user: discord.Member):
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            async with db.execute(
                "SELECT reason, moderator_id, timestamp FROM warnings WHERE guild_id = ? AND user_id = ? ORDER BY timestamp DESC",
                (interaction.guild.id, user.id)
            ) as cursor:
                rows = await cursor.fetchall()
        if not rows:
            return await interaction.response.send_message(embed=info_embed("No Warnings", f"{user.mention} has no warnings."))
        embed = discord.Embed(title=f"Warnings for {user}", color=config.WARNING_COLOR)
        for i, (reason, mod_id, ts) in enumerate(rows, 1):
            embed.add_field(name=f"#{i} — {ts[:10]}", value=f"**Reason:** {reason}\n**By:** <@{mod_id}>", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="clear", description="Delete messages in bulk")
    @app_commands.describe(amount="Number of messages to delete (1-100)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100] = 10):
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(embed=success_embed("Messages Cleared", f"Deleted **{len(deleted)}** messages."), ephemeral=True)

    @app_commands.command(name="slowmode", description="Set channel slowmode")
    @app_commands.describe(seconds="Slowmode delay in seconds (0 to disable)")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def slowmode(self, interaction: discord.Interaction, seconds: app_commands.Range[int, 0, 21600] = 0):
        await interaction.channel.edit(slowmode_delay=seconds)
        msg = "Slowmode disabled." if seconds == 0 else f"Slowmode set to **{seconds}s**."
        await interaction.response.send_message(embed=success_embed("Slowmode Updated", msg))

    @app_commands.command(name="lock", description="Lock the current channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lock(self, interaction: discord.Interaction):
        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message(embed=success_embed("Channel Locked", "Members can no longer send messages here."))

    @app_commands.command(name="unlock", description="Unlock the current channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unlock(self, interaction: discord.Interaction):
        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = None
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message(embed=success_embed("Channel Unlocked", "Members can now send messages here."))

    @app_commands.command(name="nick", description="Change a member's nickname")
    @app_commands.describe(user="The user", nickname="New nickname (leave empty to reset)")
    @app_commands.checks.has_permissions(manage_nicknames=True)
    async def nick(self, interaction: discord.Interaction, user: discord.Member, nickname: str = None):
        old = user.display_name
        await user.edit(nick=nickname)
        desc = f"**User:** {user.mention}\n**Old:** {old}\n**New:** {nickname or user.name}"
        await interaction.response.send_message(embed=success_embed("Nickname Changed", desc))

    @app_commands.command(name="automod", description="Configure auto-moderation settings")
    @app_commands.describe(anti_spam="Enable anti-spam", anti_links="Enable anti-links", anti_badwords="Enable anti-bad words", badwords="Comma-separated bad words list")
    @app_commands.checks.has_permissions(administrator=True)
    async def automod(self, interaction: discord.Interaction, anti_spam: bool = None, anti_links: bool = None, anti_badwords: bool = None, badwords: str = None):
        if anti_spam is not None:
            await update_guild_setting(interaction.guild.id, "anti_spam", int(anti_spam))
        if anti_links is not None:
            await update_guild_setting(interaction.guild.id, "anti_links", int(anti_links))
        if anti_badwords is not None:
            await update_guild_setting(interaction.guild.id, "anti_badwords", int(anti_badwords))
        if badwords is not None:
            await update_guild_setting(interaction.guild.id, "badwords", badwords.lower())
        settings = await get_guild_settings(interaction.guild.id)
        embed = discord.Embed(title="Auto-Mod Settings", color=config.INFO_COLOR)
        embed.add_field(name="Anti-Spam", value="✅" if settings.get("anti_spam") else "❌")
        embed.add_field(name="Anti-Links", value="✅" if settings.get("anti_links") else "❌")
        embed.add_field(name="Anti-Bad Words", value="✅" if settings.get("anti_badwords") else "❌")
        if settings.get("badwords"):
            embed.add_field(name="Bad Words", value=settings["badwords"], inline=False)
        await interaction.response.send_message(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        settings = await get_guild_settings(message.guild.id)
        if message.author.guild_permissions.manage_messages:
            return
        if settings.get("anti_links") and ("http://" in message.content or "https://" in message.content):
            await message.delete()
            await message.channel.send(embed=error_embed("Links Not Allowed", f"{message.author.mention}, links are not permitted here."), delete_after=5)
            return
        if settings.get("anti_badwords") and settings.get("badwords"):
            bad = [w.strip() for w in settings["badwords"].split(",") if w.strip()]
            if any(b in message.content.lower() for b in bad):
                await message.delete()
                await message.channel.send(embed=error_embed("Inappropriate Language", f"{message.author.mention}, please keep the chat clean."), delete_after=5)
                return
        if settings.get("anti_spam"):
            now = datetime.now(timezone.utc)
            async with aiosqlite.connect(config.DATABASE_PATH) as db:
                async with db.execute("SELECT message_count, window_start FROM spam_tracker WHERE guild_id = ? AND user_id = ?", (message.guild.id, message.author.id)) as cursor:
                    row = await cursor.fetchone()
                if row:
                    count, window_start = row
                    ws = datetime.fromisoformat(window_start).replace(tzinfo=timezone.utc)
                    if (now - ws).total_seconds() < 5:
                        count += 1
                        if count >= 5:
                            await message.delete()
                            await message.channel.send(embed=error_embed("Spam Detected", f"{message.author.mention}, slow down!"), delete_after=5)
                            await db.execute("UPDATE spam_tracker SET message_count = 0, window_start = ? WHERE guild_id = ? AND user_id = ?", (now.isoformat(), message.guild.id, message.author.id))
                            await db.commit()
                            return
                        await db.execute("UPDATE spam_tracker SET message_count = ? WHERE guild_id = ? AND user_id = ?", (count, message.guild.id, message.author.id))
                    else:
                        await db.execute("UPDATE spam_tracker SET message_count = 1, window_start = ? WHERE guild_id = ? AND user_id = ?", (now.isoformat(), message.guild.id, message.author.id))
                else:
                    await db.execute("INSERT INTO spam_tracker (guild_id, user_id, message_count, window_start) VALUES (?,?,1,?)", (message.guild.id, message.author.id, now.isoformat()))
                await db.commit()

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(embed=error_embed("Missing Permissions", "You don't have permission to use this command."), ephemeral=True)
        else:
            await interaction.response.send_message(embed=error_embed("Error", str(error)), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Moderation(bot))
