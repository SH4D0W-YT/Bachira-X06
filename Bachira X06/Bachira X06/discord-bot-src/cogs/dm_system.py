import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
from datetime import datetime, timezone
import config
from utils.helpers import success_embed, error_embed, info_embed


class DMSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_owner():
        async def predicate(interaction: discord.Interaction) -> bool:
            return interaction.user.id == config.OWNER_ID
        return app_commands.check(predicate)

    @app_commands.command(name="dm", description="Send a DM to a user (owner only)")
    @app_commands.describe(user="The user to DM", message="The message to send")
    @is_owner()
    async def dm_user(self, interaction: discord.Interaction, user: discord.Member, message: str):
        try:
            embed = discord.Embed(title=f"Message from {interaction.guild.name}", description=message, color=config.INFO_COLOR, timestamp=datetime.now(timezone.utc))
            embed.set_footer(text="Reply to this message and I will forward it to the sender.")
            await user.send(embed=embed)
            async with aiosqlite.connect(config.DATABASE_PATH) as db:
                await db.execute("INSERT OR REPLACE INTO dm_conversations (user_id, last_message) VALUES (?,?)", (user.id, datetime.now(timezone.utc).isoformat()))
                await db.commit()
                async with db.execute("SELECT id FROM dm_conversations WHERE user_id = ?", (user.id,)) as cursor:
                    conv_id = (await cursor.fetchone())[0]
                await db.execute("INSERT INTO dm_history (conversation_id, sender_id, content) VALUES (?,?,?)", (conv_id, interaction.user.id, message))
                await db.commit()
            await interaction.response.send_message(embed=success_embed("DM Sent", f"Your message was sent to {user.mention}."), ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(embed=error_embed("Could Not DM", f"{user.mention} has DMs disabled."), ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if isinstance(message.channel, discord.DMChannel):
            if message.author.id == config.OWNER_ID:
                return
            async with aiosqlite.connect(config.DATABASE_PATH) as db:
                async with db.execute("SELECT id FROM dm_conversations WHERE user_id = ?", (message.author.id,)) as cursor:
                    row = await cursor.fetchone()
                if not row:
                    return
                conv_id = row[0]
                await db.execute("INSERT INTO dm_history (conversation_id, sender_id, content) VALUES (?,?,?)", (conv_id, message.author.id, message.content))
                await db.execute("UPDATE dm_conversations SET last_message = ? WHERE id = ?", (datetime.now(timezone.utc).isoformat(), conv_id))
                await db.commit()
            owner = await self.bot.fetch_user(config.OWNER_ID)
            if owner:
                embed = discord.Embed(title="📨 DM Reply Received", description=message.content, color=config.INFO_COLOR, timestamp=datetime.now(timezone.utc))
                embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
                embed.add_field(name="User ID", value=message.author.id)
                try:
                    await owner.send(embed=embed)
                except Exception:
                    pass

    @app_commands.command(name="dm-history", description="View DM history with a user (owner only)")
    @is_owner()
    async def dm_history(self, interaction: discord.Interaction, user: discord.Member):
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            async with db.execute("SELECT id FROM dm_conversations WHERE user_id = ?", (user.id,)) as cursor:
                row = await cursor.fetchone()
            if not row:
                return await interaction.response.send_message(embed=error_embed("No History", f"No DM history with {user.mention}."), ephemeral=True)
            conv_id = row[0]
            async with db.execute("SELECT sender_id, content, timestamp FROM dm_history WHERE conversation_id = ? ORDER BY timestamp DESC LIMIT 20", (conv_id,)) as cursor:
                rows = await cursor.fetchall()
        embed = discord.Embed(title=f"DM History with {user}", color=config.INFO_COLOR)
        for sender_id, content, ts in reversed(rows):
            name = "You (Owner)" if sender_id == config.OWNER_ID else str(user)
            embed.add_field(name=f"{name} — {ts[:16]}", value=content[:200], inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(embed=error_embed("Owner Only", "This command is restricted to the bot owner."), ephemeral=True)


async def setup(bot):
    await bot.add_cog(DMSystem(bot))
