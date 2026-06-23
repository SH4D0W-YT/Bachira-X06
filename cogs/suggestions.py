import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
from datetime import datetime, timezone
import config
from database.db import get_guild_settings, update_guild_setting
from utils.helpers import success_embed, error_embed


class SuggestionReviewView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✅ Approve", style=discord.ButtonStyle.success, custom_id="suggestion_approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("No permission.", ephemeral=True)
        await self._update(interaction, "approved", discord.Color.green())

    @discord.ui.button(label="❌ Reject", style=discord.ButtonStyle.danger, custom_id="suggestion_reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("No permission.", ephemeral=True)
        await self._update(interaction, "rejected", discord.Color.red())

    async def _update(self, interaction: discord.Interaction, status: str, color: discord.Color):
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            await db.execute("UPDATE suggestions SET status = ? WHERE message_id = ?", (status, interaction.message.id))
            await db.commit()
        embed = interaction.message.embeds[0].copy()
        embed.color = color
        for i, f in enumerate(embed.fields):
            if f.name == "Status":
                embed.set_field_at(i, name="Status", value=f"**{status.title()}** by {interaction.user.mention}", inline=False)
                break
        await interaction.message.edit(embed=embed, view=None)
        await interaction.response.send_message(f"Suggestion **{status}**.", ephemeral=True)


class Suggestions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.add_view(SuggestionReviewView())

    @app_commands.command(name="suggest", description="Submit a suggestion")
    @app_commands.describe(suggestion="Your suggestion")
    async def suggest(self, interaction: discord.Interaction, suggestion: str):
        settings = await get_guild_settings(interaction.guild.id)
        channel_id = settings.get("suggestion_channel")
        if not channel_id:
            return await interaction.response.send_message(embed=error_embed("Not Configured", "Ask an admin to use `/suggestion-setup`."), ephemeral=True)
        channel = interaction.guild.get_channel(channel_id)
        if not channel:
            return await interaction.response.send_message(embed=error_embed("Channel Not Found", "The suggestion channel no longer exists."), ephemeral=True)
        embed = discord.Embed(title="💡 New Suggestion", description=suggestion, color=config.INFO_COLOR, timestamp=datetime.now(timezone.utc))
        embed.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="Status", value="**Pending** — Awaiting review", inline=False)
        embed.set_footer(text=f"User ID: {interaction.user.id}")
        msg = await channel.send(embed=embed, view=SuggestionReviewView())
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            await db.execute("INSERT INTO suggestions (guild_id, channel_id, message_id, user_id, content) VALUES (?,?,?,?,?)", (interaction.guild.id, channel_id, msg.id, interaction.user.id, suggestion))
            await db.commit()
        await interaction.response.send_message(embed=success_embed("Suggestion Submitted", f"Posted in {channel.mention}."), ephemeral=True)

    @app_commands.command(name="suggestion-setup", description="Set the suggestions channel")
    @app_commands.checks.has_permissions(administrator=True)
    async def suggestion_setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await update_guild_setting(interaction.guild.id, "suggestion_channel", channel.id)
        await interaction.response.send_message(embed=success_embed("Suggestions Configured", f"Suggestions will be sent to {channel.mention}."))


async def setup(bot):
    await bot.add_cog(Suggestions(bot))
