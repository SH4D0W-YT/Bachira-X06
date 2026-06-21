import asyncio
import sys
import os
import discord
from discord.ext import commands, tasks
import config
from database.db import init_db

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

intents = discord.Intents.all()


class DiscordBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
        )
        self.start_time = discord.utils.utcnow()

    async def setup_hook(self):
        await init_db()
        for cog in config.COGS:
            try:
                await self.load_extension(cog)
                print(f"[+] Loaded: {cog}")
            except Exception as e:
                print(f"[-] Failed to load {cog}: {e}")
        await self.tree.sync()
        print("[+] Slash commands synced.")

    async def on_ready(self):
        print(f"\n{'='*40}")
        print(f"  Bot: {self.user} ({self.user.id})")
        print(f"  Guilds: {len(self.guilds)}")
        print(f"  discord.py: {discord.__version__}")
        print(f"{'='*40}\n")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{len(self.guilds)} servers | /help"
            )
        )
        self.check_mutes.start()
        self.check_giveaways.start()

    async def on_guild_join(self, guild: discord.Guild):
        from database.db import get_guild_settings
        await get_guild_settings(guild.id)

    @tasks.loop(seconds=30)
    async def check_mutes(self):
        import aiosqlite
        from datetime import datetime, timezone
        from database.db import get_guild_settings
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            async with db.execute(
                "SELECT guild_id, user_id FROM mutes WHERE expires_at <= ? AND expires_at IS NOT NULL",
                (datetime.now(timezone.utc).isoformat(),),
            ) as cursor:
                rows = await cursor.fetchall()
            for guild_id, user_id in rows:
                guild = self.get_guild(guild_id)
                if not guild:
                    continue
                member = guild.get_member(user_id)
                settings = await get_guild_settings(guild_id)
                mute_role_id = settings.get("mute_role")
                if member and mute_role_id:
                    mute_role = guild.get_role(mute_role_id)
                    if mute_role and mute_role in member.roles:
                        await member.remove_roles(mute_role, reason="Mute expired")
                await db.execute(
                    "DELETE FROM mutes WHERE guild_id = ? AND user_id = ?",
                    (guild_id, user_id),
                )
            await db.commit()

    @tasks.loop(seconds=15)
    async def check_giveaways(self):
        import aiosqlite
        import json
        import random
        from datetime import datetime, timezone
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            async with db.execute(
                "SELECT * FROM giveaways WHERE ended = 0 AND ends_at <= ?",
                (datetime.now(timezone.utc).isoformat(),),
            ) as cursor:
                rows = await cursor.fetchall()
                cols = [d[0] for d in cursor.description]
            for row in rows:
                g = dict(zip(cols, row))
                channel = self.get_channel(g["channel_id"])
                if not channel:
                    continue
                try:
                    msg = await channel.fetch_message(g["message_id"])
                except Exception:
                    continue
                participants = json.loads(g["participants"])
                num_winners = min(g["winners"], len(participants))
                if num_winners == 0:
                    embed = discord.Embed(
                        title="🎉 Giveaway Ended",
                        description=f"**{g['prize']}**\n\nNo valid participants.",
                        color=config.ERROR_COLOR,
                    )
                else:
                    winners = random.sample(participants, num_winners)
                    winner_mentions = " ".join(f"<@{w}>" for w in winners)
                    embed = discord.Embed(
                        title="🎉 Giveaway Ended!",
                        description=f"**{g['prize']}**\n\n**Winners:** {winner_mentions}",
                        color=config.SUCCESS_COLOR,
                    )
                    await channel.send(f"🎉 Congratulations {winner_mentions}! You won **{g['prize']}**!")
                await msg.edit(embed=embed, view=None)
                await db.execute(
                    "UPDATE giveaways SET ended = 1 WHERE id = ?", (g["id"],)
                )
            await db.commit()

    @check_mutes.before_loop
    @check_giveaways.before_loop
    async def before_loops(self):
        await self.wait_until_ready()


async def main():
    if not config.TOKEN:
        print("\n" + "="*40)
        print("  ERROR: DISCORD_TOKEN not set!")
        print("  Create a .env file with:")
        print("  DISCORD_TOKEN=your_token_here")
        print("  OWNER_ID=your_user_id_here")
        print("="*40 + "\n")
        return
    bot = DiscordBot()
    async with bot:
        await bot.start(config.TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
