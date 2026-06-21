import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import json
import random
from datetime import datetime, timezone
import config
from utils.helpers import success_embed, error_embed, parse_duration, format_duration


class GiveawayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎉 Enter Giveaway", style=discord.ButtonStyle.primary, custom_id="giveaway_enter")
    async def enter(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            async with db.execute("SELECT id, participants, ended FROM giveaways WHERE message_id = ?", (interaction.message.id,)) as cursor:
                row = await cursor.fetchone()
            if not row:
                return await interaction.response.send_message("Giveaway not found.", ephemeral=True)
            gid, participants_raw, ended = row
            if ended:
                return await interaction.response.send_message("This giveaway has already ended.", ephemeral=True)
            participants = json.loads(participants_raw)
            if interaction.user.id in participants:
                participants.remove(interaction.user.id)
                await db.execute("UPDATE giveaways SET participants = ? WHERE id = ?", (json.dumps(participants), gid))
                await db.commit()
                return await interaction.response.send_message("You have left the giveaway.", ephemeral=True)
            participants.append(interaction.user.id)
            await db.execute("UPDATE giveaways SET participants = ? WHERE id = ?", (json.dumps(participants), gid))
            await db.commit()
        embed = interaction.message.embeds[0] if interaction.message.embeds else discord.Embed()
        for i, field in enumerate(embed.fields):
            if field.name == "Entries":
                embed.set_field_at(i, name="Entries", value=str(len(participants)), inline=field.inline)
                break
        await interaction.message.edit(embed=embed)
        await interaction.response.send_message("✅ You've entered! Click again to leave.", ephemeral=True)


class Giveaways(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.add_view(GiveawayView())

    @app_commands.command(name="giveaway", description="Manage giveaways")
    @app_commands.describe(action="start / end / reroll", prize="Prize", duration="e.g. 1h, 2d", winners="Number of winners", message_id="Message ID (for end/reroll)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway(self, interaction: discord.Interaction, action: str, prize: str = None, duration: str = None, winners: int = 1, message_id: str = None):
        action = action.lower()
        if action == "start":
            if not prize or not duration:
                return await interaction.response.send_message(embed=error_embed("Missing Args", "Provide `prize` and `duration`."), ephemeral=True)
            td = parse_duration(duration)
            if not td:
                return await interaction.response.send_message(embed=error_embed("Invalid Duration", "e.g. `1h`, `2d`, `30m`"), ephemeral=True)
            ends_at = datetime.now(timezone.utc) + td
            embed = discord.Embed(title="🎉 GIVEAWAY 🎉", description=f"**Prize:** {prize}\n\nClick the button to enter!", color=config.DEFAULT_COLOR, timestamp=ends_at)
            embed.add_field(name="Ends", value=f"<t:{int(ends_at.timestamp())}:R>")
            embed.add_field(name="Winners", value=str(winners))
            embed.add_field(name="Entries", value="0")
            embed.add_field(name="Hosted by", value=interaction.user.mention)
            embed.set_footer(text="Ends at")
            await interaction.response.send_message("Creating giveaway...", ephemeral=True)
            msg = await interaction.channel.send(embed=embed, view=GiveawayView())
            async with aiosqlite.connect(config.DATABASE_PATH) as db:
                await db.execute("INSERT INTO giveaways (guild_id, channel_id, message_id, prize, winners, host_id, ends_at) VALUES (?,?,?,?,?,?,?)", (interaction.guild.id, interaction.channel.id, msg.id, prize, winners, interaction.user.id, ends_at.isoformat()))
                await db.commit()
        elif action == "end":
            if not message_id:
                return await interaction.response.send_message(embed=error_embed("Missing", "Provide the giveaway `message_id`."), ephemeral=True)
            await interaction.response.defer()
            async with aiosqlite.connect(config.DATABASE_PATH) as db:
                async with db.execute("SELECT * FROM giveaways WHERE message_id = ? AND guild_id = ?", (int(message_id), interaction.guild.id)) as cursor:
                    row = await cursor.fetchone()
                    cols = [d[0] for d in cursor.description]
            if not row:
                return await interaction.followup.send(embed=error_embed("Not Found", "No giveaway with that ID."), ephemeral=True)
            g = dict(zip(cols, row))
            participants = json.loads(g["participants"])
            num_winners = min(g["winners"], len(participants))
            channel = interaction.guild.get_channel(g["channel_id"])
            try:
                msg = await channel.fetch_message(g["message_id"])
            except Exception:
                return await interaction.followup.send(embed=error_embed("Error", "Could not find the giveaway message."), ephemeral=True)
            if num_winners == 0:
                embed = discord.Embed(title="🎉 Giveaway Ended", description=f"**{g['prize']}**\n\nNo valid participants.", color=config.ERROR_COLOR)
            else:
                selected = random.sample(participants, num_winners)
                winner_mentions = " ".join(f"<@{w}>" for w in selected)
                embed = discord.Embed(title="🎉 Giveaway Ended!", description=f"**{g['prize']}**\n\n**Winners:** {winner_mentions}", color=config.SUCCESS_COLOR)
                await channel.send(f"🎉 Congratulations {winner_mentions}! You won **{g['prize']}**!")
            await msg.edit(embed=embed, view=None)
            async with aiosqlite.connect(config.DATABASE_PATH) as db:
                await db.execute("UPDATE giveaways SET ended = 1 WHERE message_id = ?", (g["message_id"],))
                await db.commit()
            await interaction.followup.send(embed=success_embed("Giveaway Ended", "Done."))
        elif action == "reroll":
            if not message_id:
                return await interaction.response.send_message(embed=error_embed("Missing", "Provide the giveaway `message_id`."), ephemeral=True)
            async with aiosqlite.connect(config.DATABASE_PATH) as db:
                async with db.execute("SELECT participants, prize, winners FROM giveaways WHERE message_id = ? AND guild_id = ?", (int(message_id), interaction.guild.id)) as cursor:
                    row = await cursor.fetchone()
            if not row:
                return await interaction.response.send_message(embed=error_embed("Not Found", "Giveaway not found."), ephemeral=True)
            participants = json.loads(row[0])
            prize, num_winners = row[1], row[2]
            if not participants:
                return await interaction.response.send_message(embed=error_embed("No Participants", "No one entered."), ephemeral=True)
            selected = random.sample(participants, min(num_winners, len(participants)))
            await interaction.response.send_message(f"🎉 New winner(s) for **{prize}**: {' '.join(f'<@{w}>' for w in selected)}!")
        else:
            await interaction.response.send_message(embed=error_embed("Invalid Action", "Use `start`, `end`, or `reroll`."), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Giveaways(bot))
