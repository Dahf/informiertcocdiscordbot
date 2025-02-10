import discord
import aiohttp
import os
import asyncio
from discord.ext import commands, tasks
from dotenv import load_dotenv
import logging
# Lade Umgebungsvariablen
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
COC_API_TOKEN = os.getenv("COC_API_TOKEN")
CLAN_TAG = os.getenv("CLAN_TAG")
API_URL = f"https://api.clashofclans.com/v1/clans/{CLAN_TAG}/currentwar"
HEADERS = {"Accept": "application/json", "Authorization": f"Bearer {COC_API_TOKEN}"}
logging.basicConfig(level=logging.INFO)
# Bot Setup
intents = discord.Intents.default()
intents.guilds = True  # Benötigt für Channel-Erstellung
bot = commands.Bot(command_prefix="!", intents=intents)

# Speichert den letzten Status
last_war_state = None
war_channel_id = None  # Channel ID speichern


async def fetch_war_data():
    """Ruft die aktuellen Kriegsdaten von der API ab."""
    async with aiohttp.ClientSession() as session:
        async with session.get(API_URL, headers=HEADERS) as resp:
            data = await resp.json()
            logging.info(f"{data}") 
            if resp.status == 200:
                return await resp.json()
            else:
                return None


async def get_or_create_channel(guild):
    """Überprüft, ob der Channel existiert, und erstellt ihn, falls nicht."""
    global war_channel_id
    channel_name = "clan-war-updates"

    # Überprüfen, ob der Channel existiert
    for channel in guild.text_channels:
        if channel.name == channel_name:
            war_channel_id = channel.id
            return channel

    # Falls nicht, erstelle einen neuen Channel
    new_channel = await guild.create_text_channel(channel_name)
    war_channel_id = new_channel.id
    return new_channel


@tasks.loop(minutes=5)  # Alle 5 Minuten prüfen
async def check_war_status():
    """Überprüft regelmäßig den Kriegsstatus und sendet Updates bei Änderungen."""
    global last_war_state

    # Warte, bis der Bot bereit ist
    await bot.wait_until_ready()

    # Channel sicherstellen
    if not bot.guilds:
        print("❌ Bot ist in keinem Server!")
        return

    guild = bot.guilds[0]  # Nimm den ersten Server, auf dem der Bot ist
    channel = await get_or_create_channel(guild)  # Stelle sicher, dass der Channel existiert

    war_data = await fetch_war_data()
    if not war_data or "state" not in war_data:
        return

    war_state = war_data["state"]
    if war_state == last_war_state:
        return  # Kein Update nötig

    last_war_state = war_state  # Speichern des aktuellen Status

    embed = discord.Embed(title="🏆 Clash of Clans Krieg Update!", color=discord.Color.blue())

    if war_state == "preparation":
        embed.description = "⚔️ **Kriegsvorbereitung läuft!**\nBereite deine Angriffe vor!"
        embed.add_field(name="Startet in:", value="Bald! 🕒", inline=False)
    elif war_state == "inWar":
        embed.description = "🔥 **Der Krieg ist in vollem Gange!**"
        embed.add_field(name="Endet in:", value="Bald vorbei! ⏳", inline=False)
    elif war_state == "warEnded":
        embed.description = "🏁 **Der Krieg ist vorbei!**\nSchaut euch die Ergebnisse an!"
    else:
        embed.description = "❓ Unbekannter Status"

    embed.set_footer(text="Automatisches Clash of Clans Update")

    if channel:
        await channel.send(embed=embed)


@bot.event
async def on_ready():
    print(f"✅ {bot.user} ist bereit!")
    check_war_status.start()  # Starte den Task


bot.run(TOKEN)
