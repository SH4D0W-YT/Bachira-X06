import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
from datetime import datetime, timezone
import config
from database.db import get_guild_settings, update_guild_setting
from utils.helpers import success_embed, error_embed


class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Confirm Close", style=discord.ButtonStyle.danger, custom_id="ticket_close_confirm")
    async def confirm_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Closing ticket in 5 seconds...", ephemeral=True)
        import asyncio
        await asyncio.sleep(5)
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            await db.execute("UPDATE tickets SET status = 'closed' WHERE channel_id = ?", (interaction.channel.id,))
            await db.commit()
        await interaction.channel.delete(reason="Ticket closed")

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, custom_id="ticket_close_cancel")
    async def cancel_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Close cancelled.", ephemeral=True)
        self.stop()


class TicketCreateView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 Open Ticket", style=discord.ButtonStyle.primary, custom_id="ticket_create")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        settings = await get_guild_settings(guild.id)
        category_id = settings.get("ticket_category")
        category = guild.get_channel(category_id) if category_id else None
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            async with db.execute("SELECT channel_id FROM tickets WHERE guild_id = ? AND user_id = ? AND status = 'open'", (guild.id, interaction.user.id)) as cursor:
                existing = await cursor.fetchone()
        if existing:
            ch = guild.get_channel(existing[0])
            return await interaction.response.send_message(embed=error_embed("Already Open", f"You already have an open ticket: {ch.mention if ch else 'unknown'}."), ephemeral=True)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        channel = await guild.create_text_channel(f"ticket-{interaction.user.name[:16]}", category=category, overwrites=overwrites, topic=f"Ticket for {interaction.user} ({interaction.user.id})")
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            await db.execute("INSERT INTO tickets (guild_id, channel_id, user_id) VALUES (?,?,?)", (guild.id, channel.id, interaction.user.id))
            await db.commit()
        embed = discord.Embed(title="🎫 Support Ticket", description=f"Welcome {interaction.user.mention}! Describe your issue and staff will assist you.\n\nUse `/close` to close this ticket.", color=config.SUCCESS_COLOR, timestamp=datetime.now(timezone.utc))
        await channel.send(embed=embed)
        await interaction.response.send_message(embed=success_embed("Ticket Created", f"Your ticket is at {channel.mention}."), ephemeral=True)


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.add_view(TicketCreateView())
        bot.add_view(TicketCloseView())

    @app_commands.command(name="ticket-setup", description="Configure the ticket system")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_setup(self, interaction: discord.Interaction, category: discord.CategoryChannel = None, log_channel: discord.TextChannel = None):
        if category:
            await update_guild_setting(interaction.guild.id, "ticket_category", category.id)
        if log_channel:
            await update_guild_setting(interaction.guild.id, "ticket_log_channel", log_channel.id)
        settings = await get_guild_settings(interaction.guild.id)
        embed = discord.Embed(title="Ticket Setup", color=config.SUCCESS_COLOR)
        embed.add_field(name="Category", value=f"<#{settings['ticket_category']}>" if settings.get("ticket_category") else "Not set")
        embed.add_field(name="Log Channel", value=f"<#{settings['ticket_log_channel']}>" if settings.get("ticket_log_channel") else "Not set")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ticket-panel", description="Send the ticket creation panel")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_panel(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🎫 Support Tickets", description="Click the button below to open a support ticket.", color=config.DEFAULT_COLOR)
        embed.set_footer(text=interaction.guild.name)
        await interaction.channel.send(embed=embed, view=TicketCreateView())
        await interaction.response.send_message(embed=success_embed("Panel Sent", "Ticket panel has been sent."), ephemeral=True)

    @app_commands.command(name="close", description="Close the current ticket")
    async def close(self, interaction: discord.Interaction):
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            async with db.execute("SELECT user_id FROM tickets WHERE channel_id = ? AND status = 'open'", (interaction.channel.id,)) as cursor:
                row = await cursor.fetchone()
        if not row:
            return await interaction.response.send_message(embed=error_embed("Not a Ticket", "This command can only be used in open ticket channels."), ephemeral=True)
        embed = discord.Embed(title="Close Ticket?", description="Are you sure you want to close this ticket? The channel will be deleted.", color=config.WARNING_COLOR)
        await interaction.response.send_message(embed=embed, view=TicketCloseView())

    @app_commands.command(name="adduser", description="Add a user to the current ticket")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def adduser(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.channel.set_permissions(user, view_channel=True, send_messages=True, read_message_history=True)
        await interaction.response.send_message(embed=success_embed("User Added", f"{user.mention} has been added to this ticket."))

    @app_commands.command(name="removeuser", description="Remove a user from the current ticket")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def removeuser(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.channel.set_permissions(user, overwrite=None)
        await interaction.response.send_message(embed=success_embed("User Removed", f"{user.mention} has been removed from this ticket."))

    @app_commands.command(name="transcript", description="Save a transcript of this ticket")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def transcript(self, interaction: discord.Interaction):
        await interaction.response.defer()
        messages = []
        async for msg in interaction.channel.history(limit=500, oldest_first=True):
            ts = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            messages.append(f"[{ts}] {msg.author} ({msg.author.id}): {msg.content}")
        content = "\n".join(messages) or "No messages."
        import io
        file = discord.File(io.BytesIO(content.encode()), filename=f"transcript-{interaction.channel.name}.txt")
        await interaction.followup.send(embed=success_embed("Transcript Saved", f"Transcript for **{interaction.channel.name}**."), file=file)


async def setup(bot):
    await bot.add_cog(Tickets(bot))
