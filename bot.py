import discord
import aiohttp
import os
import asyncio
from discord.ext import commands, tasks
from dotenv import load_dotenv
from datetime import datetime, timezone

# Lade Umgebungsvariablen
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
COC_API_TOKEN = os.getenv("COC_API_TOKEN")
CLAN_TAG = os.getenv("CLAN_TAG").replace("#", "%23")  # Hash muss encodiert werden
API_URL = f"https://api.clashofclans.com/v1/clans/{CLAN_TAG}/currentwar"
HEADERS = {"Accept": "application/json", "Authorization": f"Bearer {COC_API_TOKEN}"}

# Discord Bot Setup
intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Speichert die letzte Nachricht und den letzten Status
war_message = None
last_war_state = None
ping_sent = {"start": False, "end": False}  # Speichert, ob @everyone gesendet wurde


async def fetch_war_data():
    """Ruft die aktuellen Kriegsdaten von der API ab."""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(API_URL, headers=HEADERS) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
        except Exception as e:
            print(f"❌ API-Fehler: {e}")
            return None


async def get_or_create_channel(guild):
    """Überprüft, ob der Channel existiert, und erstellt ihn, falls nicht."""
    channel_name = "clan-war-updates"

    for channel in guild.text_channels:
        if channel.name == channel_name:
            return channel

    return await guild.create_text_channel(channel_name)


def get_time_remaining(time_str):
    """Berechnet die verbleibende Zeit in Stunden."""
    event_time = datetime.strptime(time_str, "%Y%m%dT%H%M%S.%fZ").replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    remaining = (event_time - now).total_seconds() / 3600  # Stunden zurückgeben
    return remaining


@tasks.loop(minutes=5)
async def update_war_status():
    """Löscht alle Nachrichten, sendet einen neuen Embed und aktualisiert ihn alle 5 Minuten."""
    global war_message, last_war_state, ping_sent

    await bot.wait_until_ready()

    if not bot.guilds:
        print("❌ Bot ist in keinem Server!")
        return

    guild = bot.guilds[0]
    channel = await get_or_create_channel(guild)

    # Lösche ALLE Nachrichten im Channel (außer der letzten Nachricht)
    async for message in channel.history(limit=None):  
        if war_message and message.id != war_message.id:
            await message.delete()

    war_data = await fetch_war_data()
    if not war_data or "state" not in war_data:
        return

    war_state = war_data["state"]
    start_time_str = war_data.get("startTime", None)
    end_time_str = war_data.get("endTime", None)

    start_time_left = get_time_remaining(start_time_str) if start_time_str else None
    time_left = get_time_remaining(end_time_str) if end_time_str else None

    # Embed erstellen
    embed = discord.Embed(title="🏆 **Clash of Clans Krieg**", color=discord.Color.blue())

    if war_state == "preparation":
        embed.description = f"⚔️ **Kriegsvorbereitung läuft!**\nDer Krieg startet in **{round(start_time_left, 1)} Stunden.**"
    elif war_state == "inWar":
        embed.description = f"🔥 **Der Krieg läuft!**\nEr endet in **{round(time_left, 1)} Stunden.**"
    elif war_state == "warEnded":
        embed.description = "🏁 **Der Krieg ist vorbei!**\nSchaut euch die Ergebnisse an!"

    # Nur einmal @everyone senden, wenn 1 Stunde übrig ist
    ping_message = None
    if start_time_left and 0.9 < start_time_left < 1.1 and not ping_sent["start"]:
        ping_message = "@everyone ⚠️ **Der Krieg startet in 1 Stunde!**"
        ping_sent["start"] = True

    if time_left and 0.9 < time_left < 1.1 and not ping_sent["end"]:
        ping_message = "@everyone ⏳ **Der Krieg endet in 1 Stunde!** Letzte Chance für Angriffe!"
        ping_sent["end"] = True

    # Falls der Krieg endet, setze die Pings für den nächsten Krieg zurück
    if war_state == "warEnded":
        ping_sent = {"start": False, "end": False}

    # Nachricht aktualisieren oder senden
    if war_message:
        await war_message.edit(content=ping_message if ping_message else "", embed=embed)
    else:
        war_message = await channel.send(content=ping_message if ping_message else "", embed=embed)

    last_war_state = war_state


@bot.event
async def on_ready():
    print(f"✅ {bot.user} ist bereit!")
    update_war_status.start()


bot.run(TOKEN)
