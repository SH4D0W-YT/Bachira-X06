import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import json
from datetime import datetime, timezone
import config
from utils.helpers import success_embed, error_embed


class PollButton(discord.ui.Button):
    def __init__(self, label: str, option_index: int, poll_id: int):
        super().__init__(label=label, style=discord.ButtonStyle.secondary, custom_id=f"poll_{poll_id}_{option_index}")
        self.option_index = option_index

    async def callback(self, interaction: discord.Interaction):
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            async with db.execute("SELECT options, votes, ended FROM polls WHERE message_id = ?", (interaction.message.id,)) as cursor:
                row = await cursor.fetchone()
            if not row:
                return await interaction.response.send_message("Poll not found.", ephemeral=True)
            options_raw, votes_raw, ended = row
            if ended:
                return await interaction.response.send_message("This poll has already ended.", ephemeral=True)
            options = json.loads(options_raw)
            votes = json.loads(votes_raw)
            uid = str(interaction.user.id)
            for key in votes:
                if uid in votes[key]:
                    votes[key].remove(uid)
            key = str(self.option_index)
            if key not in votes:
                votes[key] = []
            votes[key].append(uid)
            await db.execute("UPDATE polls SET votes = ? WHERE message_id = ?", (json.dumps(votes), interaction.message.id))
            await db.commit()
        total = sum(len(v) for v in votes.values())
        desc = ""
        for i, opt in enumerate(options):
            count = len(votes.get(str(i), []))
            bar_len = int((count / total) * 10) if total > 0 else 0
            bar = "█" * bar_len + "░" * (10 - bar_len)
            pct = round((count / total) * 100) if total > 0 else 0
            desc += f"**{opt}**\n{bar} {count} votes ({pct}%)\n\n"
        embed = interaction.message.embeds[0].copy()
        embed.description = desc
        embed.set_footer(text=f"Total votes: {total}")
        await interaction.message.edit(embed=embed)
        await interaction.response.send_message("✅ Vote recorded!", ephemeral=True)


class PollView(discord.ui.View):
    def __init__(self, options: list[str], poll_id: int):
        super().__init__(timeout=None)
        for i, option in enumerate(options):
            self.add_item(PollButton(label=option, option_index=i, poll_id=poll_id))


class Polls(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="poll", description="Create a poll")
    @app_commands.describe(question="The poll question", options="Comma-separated options (2-5)", anonymous="Make votes anonymous")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def poll(self, interaction: discord.Interaction, question: str, options: str, anonymous: bool = False):
        option_list = [o.strip() for o in options.split(",") if o.strip()]
        if len(option_list) < 2:
            return await interaction.response.send_message(embed=error_embed("Too Few Options", "Provide at least 2 options."), ephemeral=True)
        if len(option_list) > 5:
            return await interaction.response.send_message(embed=error_embed("Too Many Options", "Max 5 options."), ephemeral=True)
        votes = {str(i): [] for i in range(len(option_list))}
        desc = "\n\n".join(f"**{opt}**\n{'░' * 10} 0 votes (0%)" for opt in option_list)
        embed = discord.Embed(title=f"📊 {question}", description=desc, color=config.INFO_COLOR, timestamp=datetime.now(timezone.utc))
        embed.set_footer(text=f"Total votes: 0 | {'Anonymous' if anonymous else 'Public'}")
        await interaction.response.defer()
        msg = await interaction.channel.send(embed=embed)
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            await db.execute("INSERT INTO polls (guild_id, channel_id, message_id, question, options, votes, anonymous) VALUES (?,?,?,?,?,?,?)", (interaction.guild.id, interaction.channel.id, msg.id, question, json.dumps(option_list), json.dumps(votes), int(anonymous)))
            await db.commit()
            async with db.execute("SELECT id FROM polls WHERE message_id = ?", (msg.id,)) as cursor:
                poll_id = (await cursor.fetchone())[0]
        await msg.edit(view=PollView(option_list, poll_id))
        await interaction.followup.send(embed=success_embed("Poll Created", "Your poll has been posted."), ephemeral=True)

    @app_commands.command(name="poll-end", description="End a poll")
    @app_commands.describe(message_id="The message ID of the poll")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def poll_end(self, interaction: discord.Interaction, message_id: str):
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            async with db.execute("SELECT question, options, votes FROM polls WHERE message_id = ? AND guild_id = ?", (int(message_id), interaction.guild.id)) as cursor:
                row = await cursor.fetchone()
            if not row:
                return await interaction.response.send_message(embed=error_embed("Not Found", "Poll not found."), ephemeral=True)
            question, options_raw, votes_raw = row
            options = json.loads(options_raw)
            votes = json.loads(votes_raw)
            await db.execute("UPDATE polls SET ended = 1 WHERE message_id = ?", (int(message_id),))
            await db.commit()
        total = sum(len(v) for v in votes.values())
        desc = ""
        for i, opt in enumerate(options):
            count = len(votes.get(str(i), []))
            pct = round((count / total) * 100) if total > 0 else 0
            bar = "█" * int(pct // 10) + "░" * (10 - int(pct // 10))
            desc += f"**{opt}**\n{bar} {count} votes ({pct}%)\n\n"
        embed = discord.Embed(title=f"📊 Poll Ended: {question}", description=desc, color=config.SUCCESS_COLOR)
        embed.set_footer(text=f"Final total: {total} votes")
        try:
            msg = await interaction.channel.fetch_message(int(message_id))
            await msg.edit(embed=embed, view=None)
        except Exception:
            pass
        await interaction.response.send_message(embed=success_embed("Poll Ended", "The poll has been closed."))


async def setup(bot):
    await bot.add_cog(Polls(bot))
