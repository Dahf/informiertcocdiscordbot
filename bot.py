import discord
import aiohttp
import asyncio
import os
from discord.ext import commands, tasks
from dotenv import load_dotenv

# Lade Umgebungsvariablen
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
COC_API_TOKEN = "#" + os.getenv("COC_API_TOKEN")
CLAN_TAG = os.getenv("CLAN_TAG").replace("#", "%23")  # Hash muss encodiert werden
API_URL = f"https://api.clashofclans.com/v1/clans/{CLAN_TAG}/currentwar"
HEADERS = {"Accept": "application/json", "Authorization": f"Bearer {COC_API_TOKEN}"}

# Bot Setup
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# Speichert den letzten Status
last_war_state = None


async def fetch_war_data():
    """Ruft die aktuellen Kriegsdaten von der API ab."""
    async with aiohttp.ClientSession() as session:
        async with session.get(API_URL, headers=HEADERS) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                return None


@tasks.loop(minutes=5)  # Alle 5 Minuten prüfen
async def check_war_status():
    """Überprüft regelmäßig den Kriegsstatus und sendet Updates bei Änderungen."""
    global last_war_state
    channel = bot.get_channel(DEIN_DISCORD_CHANNEL_ID)  # Setze deine Channel-ID hier ein
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
