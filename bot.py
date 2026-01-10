import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone
import os

# ===================== CONFIG =====================

GUILD_ID = 1437438257972379870  # JOUW SERVER ID

VERIFY_ROLE_NAME = "Inwoner"
SNEAKPEAKS_ROLE_NAME = "Sneakpeaks"

# 🔽 ECHTE CHANNEL ID'S
MONITORING_CHANNEL_ID = 1459132474276974735
VERIFY_LOG_CHANNEL_ID = 1459132382098620501
ANTI_NUKE_CHANNEL_ID = 1459132519290245196
JOIN_LOG_CHANNEL_ID = 1459132310719955172
LEAVE_LOG_CHANNEL_ID = 1459132249202233479

# Minimum account leeftijd
MIN_ACCOUNT_AGE_DAYS = 7
ENABLE_MIN_AGE_CHECK = True

# ===================== INTENTS =====================

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ===================== HELPER =====================

ANTI_NUKE_WHITELIST_USERS = set()  # id's van whitelisted gebruikers

def get_log_channel(channel_id: int):
    channel = bot.get_channel(channel_id)
    if not channel:
        print(f"[WARN] Kanaal {channel_id} niet gevonden")
    return channel

# ===================== VERIFY VIEW =====================

class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Klik Hier Om je Rollen te ontvangen",
        style=discord.ButtonStyle.success,
        custom_id="verify_button"
    )
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = discord.utils.get(interaction.guild.roles, name=VERIFY_ROLE_NAME)
        log_channel = get_log_channel(VERIFY_LOG_CHANNEL_ID)

        if not role:
            await interaction.response.send_message("❌ Rol niet gevonden.", ephemeral=True)
            return

        now = datetime.now(timezone.utc)
        account_age_days = (now - interaction.user.created_at).days

        if ENABLE_MIN_AGE_CHECK and account_age_days < MIN_ACCOUNT_AGE_DAYS:
            await interaction.response.send_message(
                f"⚠️ Je account is te jong ({account_age_days} dagen).",
                ephemeral=True
            )
            return

        if role in interaction.user.roles:
            await interaction.response.send_message("ℹ️ Je bent al geverifieerd.", ephemeral=True)
            return

        await interaction.user.add_roles(role)
        await interaction.response.send_message("✅ Verificatie voltooid!", ephemeral=True)

        embed = discord.Embed(
            title="✅ Verificatie Voltooid",
            color=discord.Color.green(),
            timestamp=now
        )
        embed.add_field(name="👤 Gebruiker", value=f"{interaction.user}\n{interaction.user.id}", inline=False)
        embed.add_field(name="📅 Account Leeftijd", value=f"{account_age_days} dagen", inline=False)
        embed.add_field(name="🏷️ Rol", value=VERIFY_ROLE_NAME, inline=False)
        embed.set_footer(text="Nova District • Security System")

        if log_channel:
            await log_channel.send(embed=embed)

# ===================== SNEAKPEAKS VIEW =====================

class SneakpeaksView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="👀 Ontvang Sneakpeaks Rol",
        style=discord.ButtonStyle.primary,
        custom_id="sneakpeaks_button"
    )
    async def sneakpeaks(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = discord.utils.get(interaction.guild.roles, name=SNEAKPEAKS_ROLE_NAME)

        if not role:
            await interaction.response.send_message("❌ Sneakpeaks rol niet gevonden.", ephemeral=True)
            return

        if role in interaction.user.roles:
            await interaction.response.send_message("ℹ️ Je hebt deze rol al.", ephemeral=True)
            return

        await interaction.user.add_roles(role)
        await interaction.response.send_message(
            "✅ Je hebt nu toegang tot **Sneakpeaks**!",
            ephemeral=True
        )

# ===================== EVENTS =====================

@bot.event
async def on_ready():
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    bot.add_view(VerifyView())
    bot.add_view(SneakpeaksView())
    print(f"🟢 Bot online als {bot.user}")

    monitoring = get_log_channel(MONITORING_CHANNEL_ID)
    if monitoring:
        await monitoring.send("🟢 Nova District is succesvol opgestart")

@bot.event
async def on_member_join(member):
    channel = get_log_channel(JOIN_LOG_CHANNEL_ID)
    if channel:
        await channel.send(f"🟢 **{member}** is gejoined")

@bot.event
async def on_member_remove(member):
    channel = get_log_channel(LEAVE_LOG_CHANNEL_ID)
    if channel:
        await channel.send(f"🔴 **{member}** heeft de server verlaten")

# ===================== ANTI-NUKE EVENT =====================

@bot.event
async def on_guild_channel_delete(channel):
    guild = channel.guild
    log_channel = get_log_channel(ANTI_NUKE_CHANNEL_ID)

    # Audit log check
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
        user = entry.user
        break
    else:
        return

    # Whitelist check
    if user.id in ANTI_NUKE_WHITELIST_USERS:
        if log_channel:
            await log_channel.send(
                f"🟡 **Whitelist actie**\n👤 {user.mention}\n📁 Kanaal: **{channel.name}**"
            )
        return

    # Rollen strippen
    member = guild.get_member(user.id)
    if not member:
        return

    roles_to_remove = [role for role in member.roles if role != guild.default_role and role < guild.me.top_role]
    try:
        await member.remove_roles(*roles_to_remove, reason="Anti-Nuke: kanaal verwijderd")
    except discord.Forbidden:
        if log_channel:
            await log_channel.send("❌ Bot mist permissies om rollen te verwijderen.")
        return

    if log_channel:
        embed = discord.Embed(
            title="🚨 ANTI-NUKE ACTIVATED",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="👤 Dader", value=f"{user} ({user.id})", inline=False)
        embed.add_field(name="📁 Kanaal", value=channel.name, inline=False)
        embed.add_field(name="⚖️ Straf", value="Alle rollen verwijderd", inline=False)
        embed.set_footer(text="Nova District • Anti-Nuke System")
        await log_channel.send(embed=embed)

# ===================== ANTI-NUKE WHITELIST COMMANDS =====================

@bot.tree.command(name="antinuke", description="Anti-Nuke whitelist beheer")
@app_commands.guilds(discord.Object(id=GUILD_ID))
@app_commands.describe(action="add/remove/list", member="Tag de gebruiker")
async def antinuke(interaction: discord.Interaction, action: str, member: discord.Member = None):
    global ANTI_NUKE_WHITELIST_USERS
    action = action.lower()

    if action == "add":
        if not member:
            await interaction.response.send_message("❌ Geef een gebruiker om toe te voegen.", ephemeral=True)
            return
        ANTI_NUKE_WHITELIST_USERS.add(member.id)
        await interaction.response.send_message(f"✅ {member.mention} toegevoegd aan de whitelist.", ephemeral=True)

    elif action == "remove":
        if not member:
            await interaction.response.send_message("❌ Geef een gebruiker om te verwijderen.", ephemeral=True)
            return
        ANTI_NUKE_WHITELIST_USERS.discard(member.id)
        await interaction.response.send_message(f"✅ {member.mention} verwijderd uit de whitelist.", ephemeral=True)

    elif action == "list":
        if not ANTI_NUKE_WHITELIST_USERS:
            await interaction.response.send_message("ℹ️ Er zijn geen gebruikers in de whitelist.", ephemeral=True)
            return
        mentions = [f"<@{uid}>" for uid in ANTI_NUKE_WHITELIST_USERS]
        await interaction.response.send_message(f"📋 Whitelisted gebruikers:\n" + "\n".join(mentions), ephemeral=True)

    else:
        await interaction.response.send_message("❌ Ongeldige actie. Gebruik: add/remove/list", ephemeral=True)

# ===================== OVERIGE COMMANDS =====================

# Verify, Sneakpeaks, DiscordLinks, APV commands hier zoals eerder…

# ===================== START =====================

bot.run(os.getenv("TOKEN"))
