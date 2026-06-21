import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone
import config
from database.db import get_guild_settings, update_guild_setting
from utils.helpers import success_embed, replace_placeholders


class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setwelcome", description="Set the welcome channel")
    @app_commands.checks.has_permissions(administrator=True)
    async def setwelcome(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await update_guild_setting(interaction.guild.id, "welcome_channel", channel.id)
        await interaction.response.send_message(embed=success_embed("Welcome Channel Set", f"Welcome messages will be sent to {channel.mention}."))

    @app_commands.command(name="setgoodbye", description="Set the goodbye channel")
    @app_commands.checks.has_permissions(administrator=True)
    async def setgoodbye(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await update_guild_setting(interaction.guild.id, "goodbye_channel", channel.id)
        await interaction.response.send_message(embed=success_embed("Goodbye Channel Set", f"Goodbye messages will be sent to {channel.mention}."))

    @app_commands.command(name="welcome-message", description="Set custom welcome message")
    @app_commands.describe(message="Use {user}, {server}, {membercount}, {username}")
    @app_commands.checks.has_permissions(administrator=True)
    async def welcome_message(self, interaction: discord.Interaction, message: str):
        await update_guild_setting(interaction.guild.id, "welcome_message", message)
        await interaction.response.send_message(embed=success_embed("Welcome Message Updated", f"New message:\n```{message}```"))

    @app_commands.command(name="goodbye-message", description="Set custom goodbye message")
    @app_commands.describe(message="Use {user}, {server}, {membercount}, {username}")
    @app_commands.checks.has_permissions(administrator=True)
    async def goodbye_message(self, interaction: discord.Interaction, message: str):
        await update_guild_setting(interaction.guild.id, "goodbye_message", message)
        await interaction.response.send_message(embed=success_embed("Goodbye Message Updated", f"New message:\n```{message}```"))

    @app_commands.command(name="autorole", description="Set a role to give on member join")
    @app_commands.checks.has_permissions(administrator=True)
    async def autorole(self, interaction: discord.Interaction, role: discord.Role = None):
        await update_guild_setting(interaction.guild.id, "auto_role", role.id if role else None)
        if role:
            await interaction.response.send_message(embed=success_embed("Auto-Role Set", f"New members will receive {role.mention}."))
        else:
            await interaction.response.send_message(embed=success_embed("Auto-Role Removed", "No role will be assigned on join."))

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        settings = await get_guild_settings(member.guild.id)
        welcome_channel_id = settings.get("welcome_channel")
        if welcome_channel_id:
            channel = member.guild.get_channel(welcome_channel_id)
            if channel:
                msg = settings.get("welcome_message") or "Welcome {user} to {server}! You are member #{membercount}."
                text = replace_placeholders(msg, member)
                embed = discord.Embed(title="👋 Welcome!", description=text, color=config.SUCCESS_COLOR, timestamp=datetime.now(timezone.utc))
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.set_footer(text=f"Member #{member.guild.member_count}")
                try:
                    await channel.send(embed=embed)
                except Exception:
                    pass
        auto_role_id = settings.get("auto_role")
        if auto_role_id:
            role = member.guild.get_role(auto_role_id)
            if role:
                try:
                    await member.add_roles(role, reason="Auto-role on join")
                except Exception:
                    pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        settings = await get_guild_settings(member.guild.id)
        goodbye_channel_id = settings.get("goodbye_channel")
        if not goodbye_channel_id:
            return
        channel = member.guild.get_channel(goodbye_channel_id)
        if not channel:
            return
        msg = settings.get("goodbye_message") or "{user} has left {server}. We now have {membercount} members."
        text = replace_placeholders(msg, member)
        embed = discord.Embed(title="👋 Goodbye!", description=text, color=config.ERROR_COLOR, timestamp=datetime.now(timezone.utc))
        embed.set_thumbnail(url=member.display_avatar.url)
        try:
            await channel.send(embed=embed)
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(Welcome(bot))
