import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask
from threading import Thread
import os
import re

# ---- CONFIG ----
GUILD_ID = 1330009513402830848  # replace with your server ID
MOD_QUEUE_CHANNEL_ID = 1412025983875289129
CHALLENGE_CHANNEL_ID = 1412025983875289129
MOD_LINKS_CHANNEL_ID = 1412025983875289129
GEOROLE_ID = 1403305282569900072
INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.reactions = True
INTENTS.guilds = True
INTENTS.members = True  # required for member permissions

bot = commands.Bot(command_prefix="!", intents=INTENTS)

bot.pending = {}
geo_profiles = {}  # discord_id -> geoguessr profile URL

# ---- READY EVENT ----
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    try:
        guild = discord.Object(id=GUILD_ID)
        synced = await bot.tree.sync(guild=guild)
        print(f"🔧 Synced {len(synced)} slash commands in your server only.")
    except Exception as e:
        print(f"Sync error: {e}")

# ---- ATTACHMENT SYSTEM ----
@bot.tree.command(name="attach", description="Upload a file for mod approval")
@app_commands.describe(file="The file you want to upload")
async def attach(interaction: discord.Interaction, file: discord.Attachment):
    if interaction.guild.id != GUILD_ID:
        await interaction.response.send_message("❌ This command is only available in the official server.", ephemeral=True)
        return

    mod_channel = bot.get_channel(MOD_QUEUE_CHANNEL_ID)
    if not mod_channel:
        await interaction.response.send_message("⚠️ Mod queue channel not found.", ephemeral=True)
        return

    image_extensions = ["png", "jpg", "jpeg", "gif", "webp"]
    ext = file.filename.split('.')[-1].lower()

    embed = discord.Embed(
        title="📥 New Attachment Pending Review",
        description=f"User: {interaction.user.mention}\nChannel: {interaction.channel.mention}\nFile: [{file.filename}]({file.url})",
        color=discord.Color.orange()
    )
    embed.set_footer(text="Mods: React ✅ to approve, ❌ to deny.")

    if ext in image_extensions:
        embed.set_image(url=file.url)

    msg = await mod_channel.send(embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")

    bot.pending[msg.id] = {"file": file, "user": interaction.user, "channel": interaction.channel}

    await interaction.response.send_message("📨 File submitted for review.", ephemeral=True)

# ---- FIXED REACTION HANDLER ----
@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return
    if payload.message_id not in bot.pending:
        return
    if str(payload.emoji) not in ["✅", "❌"]:
        return

    data = bot.pending[payload.message_id]
    file, user, channel = data["file"], data["user"], data["channel"]

    guild = bot.get_guild(payload.guild_id)
    if guild is None:
        return

    # fetch member to avoid cache issues
    try:
        member = await guild.fetch_member(payload.user_id)
    except:
        return

    if not member.guild_permissions.manage_messages:
        return

    if str(payload.emoji) == "✅":
        try:
            await channel.send(
                content=f"✅ Approved by {member.mention}. Submitted by {user.mention}",
                file=await file.to_file()
            )
        except:
            await channel.send(f"✅ Approved by {member.mention}. Submitted by {user.mention}, but file could not be sent.")
    else:
        try:
            await user.send(f"❌ Your file upload in {channel.mention} was denied by {member.mention}.")
        except:
            pass

    # Remove from pending
    del bot.pending[payload.message_id]

    # Clear reactions to prevent multiple approvals/denials
    mod_channel = bot.get_channel(MOD_QUEUE_CHANNEL_ID)
    if mod_channel:
        try:
            msg = await mod_channel.fetch_message(payload.message_id)
            await msg.clear_reactions()
        except:
            pass

# ---- GEOGUESSR PROFILE LINKING ----
@bot.tree.command(name="link", description="Link your Geoguessr profile")
@app_commands.describe(url="Your Geoguessr profile URL")
async def link(interaction: discord.Interaction, url: str):
    if interaction.guild.id != GUILD_ID:
        await interaction.response.send_message("❌ This command is only available in the official server.", ephemeral=True)
        return

    if not re.match(r"^https://(www\.)?geoguessr\.com/user/.+", url):
        await interaction.response.send_message("❌ Invalid Geoguessr URL. Must start with https://www.geoguessr.com/user/", ephemeral=True)
        return

    geo_profiles[interaction.user.id] = url
    await interaction.response.send_message(f"✅ Your profile has been linked: {url}", ephemeral=True)

    mod_links_channel = bot.get_channel(MOD_LINKS_CHANNEL_ID)
    if mod_links_channel:
        await mod_links_channel.send(f"📝 {interaction.user.mention} linked their Geoguessr profile: {url}")

# ---- GEOGUESSR CHALLENGE ANNOUNCEMENT ----
@bot.tree.command(name="challenge", description="Post a Geo challenge link")
@app_commands.describe(link="The Geoguessr challenge URL", pingrole="Ping the Geoguessr role?")
async def challenge(interaction: discord.Interaction, link: str, pingrole: bool = False):
    if interaction.guild.id != GUILD_ID:
        await interaction.response.send_message("❌ This command is only available in the official server.", ephemeral=True)
        return

    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("❌ You don’t have permission to post challenges.", ephemeral=True)
        return

    channel = bot.get_channel(CHALLENGE_CHANNEL_ID)
    if channel:
        msg = f"🌍 New Geo Challenge! {link}"
        if pingrole:
            msg = f"<@&{GEOROLE_ID}> {msg}"
        await channel.send(msg)
        await interaction.response.send_message("✅ Challenge posted.", ephemeral=True)
    else:
        await interaction.response.send_message("⚠️ Challenge channel not found.", ephemeral=True)

# ---- KEEP-ALIVE ----
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run_web).start()  # start Flask server in background

# ---- RUN BOT ----
TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
