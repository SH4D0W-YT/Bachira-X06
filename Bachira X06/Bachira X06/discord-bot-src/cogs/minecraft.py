import discord
from discord import app_commands
from discord.ext import commands
import re
import config

try:
    from mcstatus import JavaServer, BedrockServer
    MCSTATUS_AVAILABLE = True
except ImportError:
    MCSTATUS_AVAILABLE = False


def clean_motd(text: str) -> str:
    return re.sub(r"§.", "", str(text)).strip()


class Minecraft(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="mcstatus", description="Check a Minecraft server's status and info")
    @app_commands.describe(
        ip="Server IP address (e.g. play.hypixel.net)",
        port="Server port (default 25565 Java / 19132 Bedrock)",
        server_type="java or bedrock (default: java)"
    )
    async def mcstatus(
        self,
        interaction: discord.Interaction,
        ip: str,
        port: int = None,
        server_type: str = "java"
    ):
        if not MCSTATUS_AVAILABLE:
            embed = discord.Embed(
                title="❌ Missing Package",
                description="Run `py -m pip install mcstatus` then restart the bot.",
                color=config.ERROR_COLOR
            )
            embed.set_footer(text="Made by @_bachira1")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        await interaction.response.defer()
        server_type = server_type.lower()

        try:
            if server_type == "bedrock":
                resolved_port = port or 19132
                server = BedrockServer(ip, resolved_port)
                status = server.status()

                embed = discord.Embed(
                    title="⛏️ Minecraft Server Status",
                    description=f"> Made by @_bachira1",
                    color=0x00AA00
                )
                embed.add_field(name="📶 Status",   value="🟢 **Online**",         inline=True)
                embed.add_field(name="🎮 Edition",  value="Bedrock",               inline=True)
                embed.add_field(name="🌐 IP",       value=f"`{ip}`",               inline=True)
                embed.add_field(name="🔢 Port",     value=f"`{resolved_port}`",    inline=True)
                embed.add_field(
                    name="👥 Players",
                    value=f"**{status.players_online}** / {status.players_max}",
                    inline=True
                )
                embed.add_field(
                    name="📦 Version",
                    value=status.version.version or "Unknown",
                    inline=True
                )
                motd = clean_motd(status.motd) if status.motd else "No description"
                embed.add_field(name="📝 MOTD", value=f"```{motd[:200]}```", inline=False)
                embed.set_footer(text="Made by @_bachira1 • Bedrock Server")

            else:
                resolved_port = port or 25565
                server = JavaServer.lookup(f"{ip}:{resolved_port}")
                status = server.status()

                online  = status.players.online
                maximum = status.players.max
                latency = round(status.latency, 2)
                color   = 0x00AA00 if online < maximum else 0xFEE75C

                embed = discord.Embed(
                    title="⛏️ Minecraft Server Status",
                    description=f"> Made by @_bachira1",
                    color=color
                )
                embed.add_field(name="📶 Status",    value="🟢 **Online**",      inline=True)
                embed.add_field(name="🎮 Edition",   value="Java Edition",        inline=True)
                embed.add_field(name="⚡ Ping",      value=f"`{latency}ms`",      inline=True)
                embed.add_field(name="🌐 IP",        value=f"`{ip}`",             inline=True)
                embed.add_field(name="🔢 Port",      value=f"`{resolved_port}`",  inline=True)
                embed.add_field(
                    name="📦 Version",
                    value=status.version.name or "Unknown",
                    inline=True
                )
                embed.add_field(
                    name="👥 Players",
                    value=f"**{online}** / {maximum}",
                    inline=True
                )
                embed.add_field(
                    name="🔧 Protocol",
                    value=str(status.version.protocol),
                    inline=True
                )
                motd = clean_motd(status.description) if status.description else "No description"
                embed.add_field(name="📝 MOTD", value=f"```{motd[:200]}```", inline=False)

                if status.players.sample:
                    names = [p.name for p in status.players.sample[:15]]
                    extra = f"\n*...and {online - len(names)} more*" if online > len(names) else ""
                    embed.add_field(
                        name="🎮 Online Players",
                        value="\n".join(f"• {n}" for n in names) + extra,
                        inline=False
                    )

                embed.set_thumbnail(url=f"https://mc-api.net/v3/server/favicon/{ip}")
                embed.set_footer(text="Made by @_bachira1 • Java Server")

        except ConnectionRefusedError:
            embed = discord.Embed(
                title="⛏️ Minecraft Server Status",
                description="> Made by @_bachira1",
                color=config.ERROR_COLOR
            )
            embed.add_field(name="📶 Status", value="🔴 **Offline**",        inline=True)
            embed.add_field(name="🌐 IP",     value=f"`{ip}`",               inline=True)
            embed.add_field(name="🔢 Port",   value=f"`{port or 25565}`",    inline=True)
            embed.add_field(name="ℹ️ Info",   value="Server is offline or unreachable.", inline=False)
            embed.set_footer(text="Made by @_bachira1")

        except Exception as e:
            embed = discord.Embed(
                title="⛏️ Minecraft Server Status",
                description="> Made by @_bachira1",
                color=config.ERROR_COLOR
            )
            embed.add_field(name="📶 Status", value="🔴 **Offline / Error**", inline=True)
            embed.add_field(name="🌐 IP",     value=f"`{ip}`",                inline=True)
            embed.add_field(name="🔢 Port",   value=f"`{port or 25565}`",     inline=True)
            embed.add_field(name="❌ Error",   value=str(e)[:300],             inline=False)
            embed.set_footer(text="Made by @_bachira1")

        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Minecraft(bot))
