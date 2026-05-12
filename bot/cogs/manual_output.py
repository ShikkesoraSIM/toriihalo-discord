import logging
import discord
from discord.ext import commands

logger = logging.getLogger(__name__)

EMBED_DATA = {
    "title": "**__Roles__**",
    "description": "*Here, you can see what each role does, and apply some roles to yourself.*",
    "color": 16711935,
    "fields": [
        {"name": "*All Pings*", "value": "*Choose this if you don't mind pings.*"},
        {"name": "*Client Pings*", "value": "*Notified about Torii Client changes.*"},
        {"name": "*Web Pings*", "value": "*Notified about website changes.*"},
        {"name": "*Servers Pings*", "value": "*Notified about Server API changes.*"}
    ]
}

DOCS_DATA = {
    "title": "**__Official Documentation__**",
    "color": 16711935,
    "fields": [
        {
            "name": "*Quick Access Links:*",
            "value": (
                "~ [*Official Website Homepage*](https://lazer.shikkesora.com/) ~\n"
                "~ [*How To Connect To Torii*](https://lazer.shikkesora.com/how-to-join) ~\n"
                "~ [*Your Profile Dashboard*](https://lazer.shikkesora.com/profile) ~\n"
                "~ [*Torii Ranking List*](https://lazer.shikkesora.com/rankings) ~\n"
                "~ [*Discord Server*](https://discord.com/invite/fZXsZFT5Xv) ~\n"
                "~ [*Torii Status*](https://lazer-api.shikkesora.com/status) ~\n"
                "~ [*Support Torii*](https://ko-fi.com/toriiserver) ~\n\n"
                "*This is a heavy work in progress. Much more will be added later, and information "
                "listed here or anywhere official for Torii is subject to change.*"
                "***We are not affiliated with, endorsed by, or supported by ppy Pty Ltd, peppy, "
                "or the osu! development team.***"
            ),
            "inline": False
        }
    ]
}

class RoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        custom_id="role_selector_menu",
        placeholder="Select a role to add/remove...",
        options=[
            discord.SelectOption(label="All Pings", value="1495234795557621790", emoji="❗"),
            discord.SelectOption(label="Client Pings", value="1502190199663493170", emoji="❗"),
            discord.SelectOption(label="Web Pings", value="1502190127534051388", emoji="❗"),
            discord.SelectOption(label="Server Pings", value="1502190217463988294", emoji="❗"),
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        role_id = int(select.values[0])
        role = interaction.guild.get_role(role_id)
        
        if role is None:
            await interaction.response.send_message("❌ Role not found!", ephemeral=True)
            return

        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            msg = f"✅ Removed the **{role.name}** role."
        else:
            await interaction.user.add_roles(role)
            msg = f"✅ Added the **{role.name}** role!"

        await interaction.response.send_message(msg, ephemeral=True)
        select.values.clear()
        await interaction.message.edit(view=self)

class Roles(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="postmenu")
    @commands.has_permissions(administrator=True)
    async def postmenu(self, ctx: commands.Context) -> None:
        embed = discord.Embed.from_dict(EMBED_DATA)
        embed.set_footer(text="Torii - Forged in Shikke's Dojo", icon_url="https://lazer.shikkesora.com/image/logos/logo@2x.png")
        await ctx.send(embed=embed, view=RoleView())

    @commands.command(name="postdocs")
    @commands.has_permissions(administrator=True)
    async def postdocs(self, ctx: commands.Context) -> None:
        embed = discord.Embed.from_dict(DOCS_DATA)
        embed.set_footer(text="Torii - Forged in Shikke's Dojo", icon_url="https://lazer.shikkesora.com/image/logos/logo@2x.png")
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Roles(bot))