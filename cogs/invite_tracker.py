import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone
import config
from database.db import (
    get_guild_settings,
    update_guild_setting,
    add_invite_watch,
    has_invite_watch,
    remove_invite_watch,
)
from utils.helpers import success_embed, info_embed, error_embed


class InviteTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.invites = {}

    async def fetch_guild_invites(self, guild: discord.Guild):
        try:
            invites = await guild.invites()
        except Exception:
            self.invites[guild.id] = {}
            return {}
        self.invites[guild.id] = {invite.code: invite.uses for invite in invites}
        return invites

    async def get_log_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        settings = await get_guild_settings(guild.id)
        channel_id = settings.get("invite_log_channel") or settings.get("log_channel")
        if not channel_id:
            return None
        return guild.get_channel(channel_id)

    async def send_log(self, guild: discord.Guild, embed: discord.Embed):
        channel = await self.get_log_channel(guild)
        if not channel:
            return
        try:
            await channel.send(embed=embed)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            await self.fetch_guild_invites(guild)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        await self.fetch_guild_invites(guild)

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        if invite.guild:
            self.invites.setdefault(invite.guild.id, {})
            self.invites[invite.guild.id][invite.code] = invite.uses

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        if invite.guild and invite.guild.id in self.invites:
            self.invites[invite.guild.id].pop(invite.code, None)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        previous = self.invites.get(guild.id, {})
        try:
            current = await guild.invites()
        except Exception:
            current = []

        used_invite = None
        for invite in current:
            previous_uses = previous.get(invite.code, 0)
            if invite.uses > previous_uses:
                used_invite = invite
                break

        self.invites[guild.id] = {invite.code: invite.uses for invite in current}

        if used_invite and used_invite.inviter:
            inviter = used_invite.inviter
            uses = used_invite.uses
            description = (
                f"{member.mention} joined with the invite of {inviter.mention}, "
                f"Now they have {uses} invites."
            )
        else:
            description = f"{member.mention} joined, but the invite source could not be determined."

        embed = discord.Embed(
            title="📈 Invite Tracker",
            description=description,
            color=config.SUCCESS_COLOR,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text=f"Member ID: {member.id}")
        await self.send_log(guild, embed)

        if await has_invite_watch(guild.id, member.id):
            owner = guild.owner or guild.get_member(config.OWNER_ID)
            owner_mention = owner.mention if owner else f"<@{config.OWNER_ID}>" if config.OWNER_ID else "Server owner"
            extra_embed = discord.Embed(
                title="🔍 Sought Member Joined",
                description=f"{member.mention} has joined the server.\n{owner_mention}",
                color=config.INFO_COLOR,
                timestamp=datetime.now(timezone.utc),
            )
            await self.send_log(guild, extra_embed)
            await remove_invite_watch(guild.id, member.id)

    @app_commands.command(name="track-enable", description="Enable invite tracking into a channel")
    @app_commands.checks.has_permissions(administrator=True)
    async def track_enable(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ):
        await update_guild_setting(interaction.guild.id, "invite_log_channel", channel.id)
        await self.fetch_guild_invites(interaction.guild)
        await interaction.response.send_message(
            embed=success_embed(
                "Invite Tracker Enabled",
                f"Invite logs will be sent to {channel.mention}.",
            )
        )

    @app_commands.command(name="seek", description="Watch a user and alert owner when they join")
    @app_commands.describe(member="The member to watch")
    @app_commands.checks.has_permissions(administrator=True)
    async def seek(self, interaction: discord.Interaction, member: discord.Member):
        await add_invite_watch(interaction.guild.id, member.id)
        await interaction.response.send_message(
            embed=success_embed(
                "Seek Enabled",
                f"I will log when {member.mention} joins the server.",
            )
        )


async def setup(bot):
    await bot.add_cog(InviteTracker(bot))
