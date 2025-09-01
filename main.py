import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask
from threading import Thread
import os
import re

# ---- CONFIG ----
MOD_QUEUE_CHANNEL_ID = 1412025983875289129  # mod queue channel
CHALLENGE_CHANNEL_ID = 1412025983875289129  # challenge channel
MOD_LINKS_CHANNEL_ID = 1412025983875289129  # mod channel for linked profiles
GEOROLE_ID = 1403305282569900072  # Geoguessr role ID to ping
INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.reactions = True
INTENTS.guilds = True

bot = commands.Bot(command_prefix="!", intents=INTENTS)

# Store pending submissions and geoguessr profiles
bot.pending = {}
geo_profiles = {}  # discord_id -> geoguessr profile URL

# ---- READY EVENT ----
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"🔧 Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"Sync error: {e}")

# ---- ATTACHMENT SYSTEM ----
@bot.tree.command(name="attach", description="Upload a file for mod approval")
@app_commands.describe(file="The file you want to upload")
async def attach(interaction: discord.Interaction, file: discord.Attachment):
    mod_channel = bot.get_channel(MOD_QUEUE_CHANNEL_ID)
    if mod_channel is None:
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

    bot.pending[msg.id] = {
        "file": file,
        "user": interaction.user,
        "channel": interaction.channel
    }

    await interaction.response.send_message("📨 File submitted for review.", ephemeral=True)

@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return
    if payload.message_id not in bot.pending:
        return
    if str(payload.emoji) not in ["✅", "❌"]:
        return

    data = bot.pending[payload.message_id]
    file = data["file"]
    user = data["user"]
    channel = data["channel"]

    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)

    if not member.guild_permissions.manage_messages:
        return

    if str(payload.emoji) == "✅":
        await channel.send(
            content=f"✅ Approved by {member.mention}. Submitted by {user.mention}",
            file=await file.to_file()
        )
    else:
        try:
            await user.send(
                f"❌ Your file upload in {channel.mention} was denied by {member.mention}."
            )
        except:
            pass

    del bot.pending[payload.message_id]

# ---- GEOGUESSR PROFILE LINKING ----
@bot.tree.command(name="link", description="Link your Geoguessr profile")
@app_commands.describe(url="Your Geoguessr profile URL")
async def link(interaction: discord.Interaction, url: str):
    # Validate URL format
    if not re.match(r"^https://(www\.)?geoguessr\.com/user/.+", url):
        await interaction.response.send_message(
            "❌ Invalid Geoguessr URL. It must start with `https://www.geoguessr.com/user/`",
            ephemeral=True
        )
        return

    geo_profiles[interaction.user.id] = url
    await interaction.response.send_message(f"✅ Your profile has been linked: {url}", ephemeral=True)

    # Post to mod channel
    mod_links_channel = bot.get_channel(MOD_LINKS_CHANNEL_ID)
    if mod_links_channel:
        await mod_links_channel.send(f"📝 {interaction.user.mention} linked their Geoguessr profile: {url}")

# ---- GEOGUESSR CHALLENGE ANNOUNCEMENT ----
@bot.tree.command(name="challenge", description="Post a Geo challenge link")
@app_commands.describe(link="The Geoguessr challenge URL", pingrole="Ping the Geoguessr role?")
async def challenge(interaction: discord.Interaction, link: str, pingrole: bool = False):
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("❌ You don’t have permission to post challenges.", ephemeral=True)
        return

    channel = bot.get_channel(CHALLENGE_CHANNEL_ID)
    if channel:
        msg = f"🌍 New Geo Challenge! {link}"
        if pingrole:
            msg = f"<@&{GEOROLE_ID}> " + msg
        await channel.send(msg)
        await interaction.response.send_message("✅ Challenge posted.", ephemeral=True)
    else:
        await interaction.response.send_message("⚠️ Challenge channel not found.", ephemeral=True)

# ---- KEEP-ALIVE FOR REPLIT ----
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

keep_alive()  # Start Flask server before bot

# ---- RUN BOT ----
TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
