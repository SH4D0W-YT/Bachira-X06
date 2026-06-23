import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import config
from utils.helpers import success_embed, error_embed


class RoleButton(discord.ui.Button):
    def __init__(self, role_id: int, label: str):
        super().__init__(label=label, style=discord.ButtonStyle.secondary, custom_id=f"rr_btn_{role_id}")
        self.role_id = role_id

    async def callback(self, interaction: discord.Interaction):
        role = interaction.guild.get_role(self.role_id)
        if not role:
            return await interaction.response.send_message("Role not found.", ephemeral=True)
        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(f"✅ Removed **{role.name}**.", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ Added **{role.name}**.", ephemeral=True)


class ReactionRoleButtonView(discord.ui.View):
    def __init__(self, roles: list[tuple]):
        super().__init__(timeout=None)
        for role_id, label in roles:
            self.add_item(RoleButton(role_id=role_id, label=label))


class RoleSelect(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption]):
        super().__init__(placeholder="Select roles...", min_values=0, max_values=len(options), options=options, custom_id="reaction_role_select")

    async def callback(self, interaction: discord.Interaction):
        selected_ids = [int(v) for v in self.values]
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            async with db.execute("SELECT role_id FROM reaction_roles WHERE message_id = ? AND guild_id = ?", (interaction.message.id, interaction.guild.id)) as cursor:
                rows = await cursor.fetchall()
        for role_id, in rows:
            role = interaction.guild.get_role(role_id)
            if role:
                if role_id in selected_ids and role not in interaction.user.roles:
                    try:
                        await interaction.user.add_roles(role)
                    except Exception:
                        pass
                elif role_id not in selected_ids and role in interaction.user.roles:
                    try:
                        await interaction.user.remove_roles(role)
                    except Exception:
                        pass
        given = [interaction.guild.get_role(r) for r in selected_ids if interaction.guild.get_role(r)]
        desc = "Roles updated!\n" + (" ".join(r.mention for r in given) if given else "All roles removed.")
        await interaction.response.send_message(desc, ephemeral=True)


class RoleSelectView(discord.ui.View):
    def __init__(self, roles: list[tuple]):
        super().__init__(timeout=None)
        options = [discord.SelectOption(label=label, value=str(role_id)) for role_id, label in roles]
        self.add_item(RoleSelect(options=options))


class ReactionRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="reactionrole", description="Create or remove a reaction role panel")
    @app_commands.describe(action="create or remove", roles="Comma-separated role IDs or mentions", style="button or dropdown", title="Panel title", message_id="Message ID (for remove)")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def reactionrole(self, interaction: discord.Interaction, action: str, roles: str = None, style: str = "button", title: str = "Role Selection", message_id: str = None):
        action = action.lower()
        if action == "create":
            if not roles:
                return await interaction.response.send_message(embed=error_embed("Missing Roles", "Provide role mentions or IDs."), ephemeral=True)
            role_list = []
            for part in roles.split(","):
                part = part.strip().strip("<@&>")
                try:
                    role = interaction.guild.get_role(int(part))
                    if role:
                        role_list.append((role.id, role.name))
                except ValueError:
                    pass
            if not role_list:
                return await interaction.response.send_message(embed=error_embed("No Valid Roles", "Could not find any of those roles."), ephemeral=True)
            embed = discord.Embed(title=f"🎭 {title}", description="\n".join(f"• <@&{rid}> — {label}" for rid, label in role_list), color=config.DEFAULT_COLOR)
            await interaction.response.defer()
            view = RoleSelectView(role_list) if style.lower() == "dropdown" else ReactionRoleButtonView(role_list)
            msg = await interaction.channel.send(embed=embed, view=view)
            async with aiosqlite.connect(config.DATABASE_PATH) as db:
                for role_id, label in role_list:
                    await db.execute("INSERT INTO reaction_roles (guild_id, channel_id, message_id, role_id, label) VALUES (?,?,?,?,?)", (interaction.guild.id, interaction.channel.id, msg.id, role_id, label))
                await db.commit()
            await interaction.followup.send(embed=success_embed("Panel Created", "Reaction role panel is live!"), ephemeral=True)
        elif action == "remove":
            if not message_id:
                return await interaction.response.send_message(embed=error_embed("Missing", "Provide the `message_id` of the panel to remove."), ephemeral=True)
            mid = int(message_id)
            async with aiosqlite.connect(config.DATABASE_PATH) as db:
                await db.execute("DELETE FROM reaction_roles WHERE message_id = ? AND guild_id = ?", (mid, interaction.guild.id))
                await db.commit()
            try:
                msg = await interaction.channel.fetch_message(mid)
                await msg.delete()
            except Exception:
                pass
            await interaction.response.send_message(embed=success_embed("Panel Removed", "The panel has been deleted."))
        else:
            await interaction.response.send_message(embed=error_embed("Invalid Action", "Use `create` or `remove`."), ephemeral=True)


async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))
