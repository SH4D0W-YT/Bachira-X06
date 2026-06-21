import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone
import config
from utils.helpers import info_embed, success_embed


class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Check the bot's latency")
    async def ping(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🏓 Pong!", color=config.SUCCESS_COLOR)
        embed.add_field(name="Latency", value=f"`{round(self.bot.latency * 1000)}ms`")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="uptime", description="Show how long the bot has been online")
    async def uptime(self, interaction: discord.Interaction):
        delta = discord.utils.utcnow() - self.bot.start_time
        total = int(delta.total_seconds())
        days, rem = divmod(total, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        embed = info_embed("Uptime", f"**{days}d {hours}h {minutes}m {seconds}s**")
        embed.add_field(name="Online since", value=f"<t:{int(self.bot.start_time.timestamp())}:F>")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="userinfo", description="Get information about a user")
    async def userinfo(self, interaction: discord.Interaction, user: discord.Member = None):
        user = user or interaction.user
        embed = discord.Embed(title=f"User Info — {user}", color=config.DEFAULT_COLOR, timestamp=datetime.now(timezone.utc))
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="ID", value=user.id)
        embed.add_field(name="Nickname", value=user.nick or "None")
        embed.add_field(name="Bot", value="Yes" if user.bot else "No")
        embed.add_field(name="Account Created", value=f"<t:{int(user.created_at.timestamp())}:D>")
        embed.add_field(name="Joined Server", value=f"<t:{int(user.joined_at.timestamp())}:D>" if user.joined_at else "Unknown")
        roles = [r.mention for r in sorted(user.roles[1:], key=lambda r: r.position, reverse=True)]
        embed.add_field(name=f"Roles ({len(roles)})", value=" ".join(roles[:10]) if roles else "None", inline=False)
        embed.add_field(name="Top Role", value=user.top_role.mention)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="serverinfo", description="Get information about the server")
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        embed = discord.Embed(title=f"Server Info — {guild.name}", color=config.DEFAULT_COLOR, timestamp=datetime.now(timezone.utc))
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="ID", value=guild.id)
        embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown")
        embed.add_field(name="Created", value=f"<t:{int(guild.created_at.timestamp())}:D>")
        embed.add_field(name="Members", value=guild.member_count)
        embed.add_field(name="Channels", value=len(guild.channels))
        embed.add_field(name="Roles", value=len(guild.roles))
        embed.add_field(name="Boost Level", value=f"Level {guild.premium_tier} ({guild.premium_subscription_count} boosts)")
        embed.add_field(name="Verification", value=str(guild.verification_level).title())
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="avatar", description="Get a user's avatar")
    async def avatar(self, interaction: discord.Interaction, user: discord.Member = None):
        user = user or interaction.user
        embed = discord.Embed(title=f"{user}'s Avatar", color=config.DEFAULT_COLOR)
        embed.set_image(url=user.display_avatar.url)
        embed.description = f"[Download]({user.display_avatar.url})"
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="roleinfo", description="Get information about a role")
    async def roleinfo(self, interaction: discord.Interaction, role: discord.Role):
        embed = discord.Embed(title=f"Role Info — {role.name}", color=role.color, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="ID", value=role.id)
        embed.add_field(name="Color", value=str(role.color))
        embed.add_field(name="Members", value=len(role.members))
        embed.add_field(name="Mentionable", value="Yes" if role.mentionable else "No")
        embed.add_field(name="Hoisted", value="Yes" if role.hoist else "No")
        embed.add_field(name="Position", value=role.position)
        embed.add_field(name="Created", value=f"<t:{int(role.created_at.timestamp())}:D>")
        key_perms = [p.replace("_", " ").title() for p, v in role.permissions if v and p in ("administrator", "manage_guild", "manage_channels", "manage_roles", "kick_members", "ban_members", "manage_messages")]
        embed.add_field(name="Key Permissions", value=", ".join(key_perms) or "None", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="membercount", description="Show the server member count")
    async def membercount(self, interaction: discord.Interaction):
        guild = interaction.guild
        total = guild.member_count
        bots = sum(1 for m in guild.members if m.bot)
        embed = discord.Embed(title=f"Member Count — {guild.name}", color=config.DEFAULT_COLOR)
        embed.add_field(name="Total", value=str(total))
        embed.add_field(name="Humans", value=str(total - bots))
        embed.add_field(name="Bots", value=str(bots))
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="help", description="Show all available commands")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(title="📖 Bot Commands", description="All commands are slash commands. Use `/` to get started.", color=config.DEFAULT_COLOR, timestamp=datetime.now(timezone.utc))
        sections = {
            "🛡️ Moderation": ["/ban", "/unban", "/kick", "/mute", "/unmute", "/warn", "/warnings", "/clear", "/slowmode", "/lock", "/unlock", "/nick", "/automod"],
            "📋 Logging": ["/setlogs", "/logs"],
            "🎫 Tickets": ["/ticket-setup", "/ticket-panel", "/close", "/adduser", "/removeuser", "/transcript"],
            "👋 Welcome": ["/setwelcome", "/setgoodbye", "/welcome-message", "/goodbye-message", "/autorole"],
            "🎉 Giveaways": ["/giveaway start", "/giveaway end", "/giveaway reroll"],
            "📊 Polls": ["/poll", "/poll-end"],
            "💡 Suggestions": ["/suggest", "/suggestion-setup"],
            "🎭 Reaction Roles": ["/reactionrole create", "/reactionrole remove"],
            "🔧 Utility": ["/userinfo", "/serverinfo", "/avatar", "/roleinfo", "/membercount", "/ping", "/uptime", "/help"],
            "⛏️ Minecraft": ["/mcstatus"],
            "💬 DM System": ["/dm", "/dm-history"],
            "⚙️ Settings": ["/settings", "/setowner"],
        }
        for section, cmds in sections.items():
            embed.add_field(name=section, value=" ".join(f"`{c}`" for c in cmds), inline=False)
        embed.set_footer(text="Made by @_bachira1")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="settings", description="Show current server settings")
    @app_commands.checks.has_permissions(administrator=True)
    async def settings(self, interaction: discord.Interaction):
        from database.db import get_guild_settings
        s = await get_guild_settings(interaction.guild.id)
        embed = discord.Embed(title=f"⚙️ Settings — {interaction.guild.name}", color=config.INFO_COLOR)
        embed.add_field(name="Log Channel", value=f"<#{s['log_channel']}>" if s.get("log_channel") else "Not set")
        embed.add_field(name="Welcome Channel", value=f"<#{s['welcome_channel']}>" if s.get("welcome_channel") else "Not set")
        embed.add_field(name="Goodbye Channel", value=f"<#{s['goodbye_channel']}>" if s.get("goodbye_channel") else "Not set")
        embed.add_field(name="Auto Role", value=f"<@&{s['auto_role']}>" if s.get("auto_role") else "Not set")
        embed.add_field(name="Mute Role", value=f"<@&{s['mute_role']}>" if s.get("mute_role") else "Not set")
        embed.add_field(name="Suggestion Channel", value=f"<#{s['suggestion_channel']}>" if s.get("suggestion_channel") else "Not set")
        embed.add_field(name="Anti-Spam", value="✅" if s.get("anti_spam") else "❌")
        embed.add_field(name="Anti-Links", value="✅" if s.get("anti_links") else "❌")
        embed.add_field(name="Anti-Bad Words", value="✅" if s.get("anti_badwords") else "❌")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setowner", description="Set the bot owner for this server")
    @app_commands.checks.has_permissions(administrator=True)
    async def setowner(self, interaction: discord.Interaction, user: discord.Member):
        from database.db import update_guild_setting
        await update_guild_setting(interaction.guild.id, "owner_id", user.id)
        await interaction.response.send_message(embed=success_embed("Owner Set", f"{user.mention} is now the server bot owner."))


async def setup(bot):
    await bot.add_cog(Utility(bot))
