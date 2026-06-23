import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone
import config
from database.db import get_guild_settings, update_guild_setting
from utils.helpers import success_embed, info_embed


class Logging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def send_log(self, guild: discord.Guild, embed: discord.Embed):
        settings = await get_guild_settings(guild.id)
        log_channel_id = settings.get("log_channel")
        if not log_channel_id:
            return
        channel = guild.get_channel(log_channel_id)
        if channel:
            try:
                await channel.send(embed=embed)
            except Exception:
                pass

    @app_commands.command(name="setlogs", description="Set the logging channel")
    @app_commands.checks.has_permissions(administrator=True)
    async def setlogs(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await update_guild_setting(interaction.guild.id, "log_channel", channel.id)
        await interaction.response.send_message(embed=success_embed("Log Channel Set", f"Logs will be sent to {channel.mention}."))

    @app_commands.command(name="logs", description="Check the logging status")
    @app_commands.checks.has_permissions(administrator=True)
    async def logs_status(self, interaction: discord.Interaction):
        settings = await get_guild_settings(interaction.guild.id)
        log_channel_id = settings.get("log_channel")
        if log_channel_id:
            channel = interaction.guild.get_channel(log_channel_id)
            desc = f"Logs are being sent to {channel.mention if channel else f'<deleted channel {log_channel_id}>'}."
        else:
            desc = "No log channel set. Use `/setlogs` to configure one."
        await interaction.response.send_message(embed=info_embed("Log Status", desc))

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        embed = discord.Embed(title="🗑️ Message Deleted", color=config.ERROR_COLOR, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Author", value=f"{message.author.mention} ({message.author})")
        embed.add_field(name="Channel", value=message.channel.mention)
        embed.add_field(name="Content", value=message.content[:1024] or "*Empty*", inline=False)
        embed.set_footer(text=f"User ID: {message.author.id}")
        await self.send_log(message.guild, embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or not before.guild or before.content == after.content:
            return
        embed = discord.Embed(title="✏️ Message Edited", color=config.WARNING_COLOR, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Author", value=f"{before.author.mention} ({before.author})")
        embed.add_field(name="Channel", value=before.channel.mention)
        embed.add_field(name="Before", value=before.content[:512] or "*Empty*", inline=False)
        embed.add_field(name="After", value=after.content[:512] or "*Empty*", inline=False)
        embed.set_footer(text=f"User ID: {before.author.id}")
        await self.send_log(before.guild, embed)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        embed = discord.Embed(title="📥 Member Joined", color=config.SUCCESS_COLOR, timestamp=datetime.now(timezone.utc))
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Member", value=f"{member.mention} ({member})")
        embed.add_field(name="Account Created", value=f"<t:{int(member.created_at.timestamp())}:R>")
        embed.add_field(name="Member Count", value=str(member.guild.member_count))
        embed.set_footer(text=f"User ID: {member.id}")
        await self.send_log(member.guild, embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        embed = discord.Embed(title="📤 Member Left", color=config.ERROR_COLOR, timestamp=datetime.now(timezone.utc))
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Member", value=f"{member.mention} ({member})")
        embed.add_field(name="Joined", value=f"<t:{int(member.joined_at.timestamp())}:R>" if member.joined_at else "Unknown")
        roles = [r.mention for r in member.roles[1:]]
        embed.add_field(name="Roles", value=" ".join(roles) if roles else "None", inline=False)
        embed.set_footer(text=f"User ID: {member.id}")
        await self.send_log(member.guild, embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        embed = discord.Embed(title="🔨 Member Banned", color=config.ERROR_COLOR, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="User", value=f"{user.mention} ({user})")
        embed.set_footer(text=f"User ID: {user.id}")
        await self.send_log(guild, embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        embed = discord.Embed(title="🔓 Member Unbanned", color=config.SUCCESS_COLOR, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="User", value=f"{user.mention} ({user})")
        embed.set_footer(text=f"User ID: {user.id}")
        await self.send_log(guild, embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        embed = discord.Embed(title="➕ Channel Created", color=config.SUCCESS_COLOR, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Channel", value=f"{channel.mention} ({channel.name})")
        embed.add_field(name="Type", value=str(channel.type).replace("_", " ").title())
        await self.send_log(channel.guild, embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        embed = discord.Embed(title="➖ Channel Deleted", color=config.ERROR_COLOR, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Channel", value=channel.name)
        embed.add_field(name="Type", value=str(channel.type).replace("_", " ").title())
        await self.send_log(channel.guild, embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        embed = discord.Embed(title="🎭 Role Created", color=config.SUCCESS_COLOR, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Role", value=f"{role.mention} ({role.name})")
        await self.send_log(role.guild, embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        embed = discord.Embed(title="🗑️ Role Deleted", color=config.ERROR_COLOR, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Role", value=role.name)
        await self.send_log(role.guild, embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if before.channel == after.channel:
            return
        if after.channel:
            embed = discord.Embed(title="🎤 Joined Voice", color=config.SUCCESS_COLOR, timestamp=datetime.now(timezone.utc))
            embed.add_field(name="Member", value=f"{member.mention} ({member})")
            embed.add_field(name="Channel", value=after.channel.name)
        else:
            embed = discord.Embed(title="🔇 Left Voice", color=config.ERROR_COLOR, timestamp=datetime.now(timezone.utc))
            embed.add_field(name="Member", value=f"{member.mention} ({member})")
            embed.add_field(name="Channel", value=before.channel.name)
        embed.set_footer(text=f"User ID: {member.id}")
        await self.send_log(member.guild, embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.nick != after.nick:
            embed = discord.Embed(title="📝 Nickname Changed", color=config.INFO_COLOR, timestamp=datetime.now(timezone.utc))
            embed.add_field(name="Member", value=f"{after.mention} ({after})")
            embed.add_field(name="Before", value=before.nick or before.name)
            embed.add_field(name="After", value=after.nick or after.name)
            embed.set_footer(text=f"User ID: {after.id}")
            await self.send_log(after.guild, embed)


async def setup(bot):
    await bot.add_cog(Logging(bot))
