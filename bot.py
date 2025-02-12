import discord
import aiohttp
import os
import asyncio
from discord.ext import commands, tasks
from dotenv import load_dotenv
from datetime import datetime, timezone
import logging

# Lade Umgebungsvariablen
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
COC_API_TOKEN = os.getenv("COC_API_TOKEN")
CLAN_TAG = os.getenv("CLAN_TAG").replace("#", "%23")  # Hash muss encodiert werden
API_URL = f"https://api.clashofclans.com/v1/clans/{CLAN_TAG}/currentwar"
HEADERS = {"Accept": "application/json", "Authorization": f"Bearer {COC_API_TOKEN}"}
WARLOG_URL = f"https://api.clashofclans.com/v1/clans/{CLAN_TAG}/warlog"

# Logging konfigurieren
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Discord Bot Setup
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Speichert die letzte Nachricht und den letzten Status
war_message = None
last_war_state = None
ping_sent = {"start": False, "end": False}  # Speichert, ob @everyone gesendet wurde

async def fetch_data(url):
    """Ruft Daten von der Clash of Clans API ab."""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=HEADERS) as resp:
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

@bot.command()
async def stats(ctx):
    """Zeigt die Clan-Statistiken des aktuellen Krieges an."""
    war_data = await fetch_data(API_URL)

    if not war_data or "state" not in war_data:
        await ctx.send("❌ Es gibt aktuell keine Kriegsdaten.")
        return

    # Basis-Statistiken abrufen
    clan_name = war_data.get("clan", {}).get("name", "Unbekannt")
    opponent_name = war_data.get("opponent", {}).get("name", "Unbekannt")
    clan_stars = war_data.get("clan", {}).get("stars", 0)
    opponent_stars = war_data.get("opponent", {}).get("stars", 0)
    attacks_used = war_data.get("clan", {}).get("attacks", 0)
    team_size = war_data.get("teamSize", 0)

    # Durchschnittliche Sterne pro Angriff berechnen
    avg_stars_per_attack = round(clan_stars / attacks_used, 2) if attacks_used > 0 else 0

    # Erstelle Embed
    embed = discord.Embed(title="📊 **Aktuelle Kriegsstatistiken**", color=discord.Color.green())
    embed.add_field(name="🏆 Clan", value=f"**{clan_name}**", inline=True)
    embed.add_field(name="⚔️ Gegner", value=f"**{opponent_name}**", inline=True)
    embed.add_field(name="⭐ Sterne", value=f"{clan_stars} - {opponent_stars}", inline=False)
    embed.add_field(name="🎯 Angriffe genutzt", value=f"{attacks_used} / {team_size * 2}", inline=True)
    embed.add_field(name="📊 Sterne pro Angriff", value=f"{avg_stars_per_attack}", inline=True)
    embed.set_footer(text="Daten live aus der Clash of Clans API.")

    await ctx.send(embed=embed)

@bot.command()
async def warlog(ctx):
    """Zeigt die letzten Clan-Kriege an."""
    warlog_data = await fetch_data(WARLOG_URL)

    if not warlog_data or "items" not in warlog_data:
        await ctx.send("❌ Keine letzten Kriege gefunden.")
        return

    embed = discord.Embed(title="📜 **Letzte Clan-Kriege**", color=discord.Color.purple())

    for war in warlog_data["items"][:5]:  # Nur die letzten 5 Kriege anzeigen
        enemy_clan = war.get("opponent", {}).get("name", "Unbekannt")
        clan_stars = war.get("clan", {}).get("stars", 0)
        enemy_stars = war.get("opponent", {}).get("stars", 0)
        attacks_used = war.get("clan", {}).get("attacks", 0)
        team_size = war.get("teamSize", 0)
        result = war.get("result", "unbekannt").capitalize()

        # Formatierte Infos
        war_summary = f"**Ergebnis:** {result}\n⭐ {clan_stars} - {enemy_stars} Sterne\n🎯 {attacks_used}/{team_size*2} Angriffe genutzt"

        embed.add_field(name=f"🆚 {enemy_clan}", value=war_summary, inline=False)

    embed.set_footer(text="Daten live aus der Clash of Clans API.")
    await ctx.send(embed=embed)

ENEMY_STATS_FILE = "enemy_stats.json"

def load_enemy_stats():
    """Lädt gespeicherte Gegner-Stats aus einer Datei."""
    if os.path.exists(ENEMY_STATS_FILE):
        with open(ENEMY_STATS_FILE, "r") as file:
            return json.load(file)
    return {}

def save_enemy_stats(enemy_stats):
    """Speichert die Gegner-Stats in eine Datei."""
    with open(ENEMY_STATS_FILE, "w") as file:
        json.dump(enemy_stats, file, indent=4)

async def fetch_player_stats(player_tag):
    """Holt die Trophäen & das Rathaus-Level aus der Clash of Clans API."""
    player_tag_encoded = player_tag.replace("#", "%23")
    url = f"https://api.clashofclans.com/v1/players/{player_tag_encoded}"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=HEADERS) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    logging.warning(f"⚠️ Fehler beim Abrufen von {player_tag}: Status {resp.status}")
                    return None
        except Exception as e:
            logging.error(f"❌ API-Fehler bei {player_tag}: {e}")
            return None

async def analyze_team_with_cache(team_data, is_enemy_team=False):
    """Berechnet das durchschnittliche Rathaus-Level & die Trophäen und speichert Gegner-Stats."""
    total_th_level = 0
    total_trophies = 0
    player_count = len(team_data)
    
    if player_count == 0:
        return {"avg_th": 0, "avg_trophies": 0}
    
    enemy_stats = load_enemy_stats() if is_enemy_team else {}

    tasks = []
    for player in team_data:
        player_tag = player["tag"]
        if is_enemy_team and player_tag in enemy_stats:
            logging.info(f"⚡ Verwende gespeicherte Daten für Gegner {player_tag}")
            continue  # Falls Spieler schon gespeichert ist, keine neue Anfrage senden
        tasks.append(fetch_player_stats(player_tag))

    results = await asyncio.gather(*tasks)

    valid_players = 0
    for player, player_data in zip(team_data, results):
        if player_data:
            player_tag = player["tag"]
            town_hall = player_data.get("townHallLevel", 0)
            trophies = player_data.get("trophies", 0)
            
            total_th_level += town_hall
            total_trophies += trophies
            valid_players += 1

            if is_enemy_team:
                enemy_stats[player_tag] = {"townHallLevel": town_hall, "trophies": trophies}

    if is_enemy_team:
        save_enemy_stats(enemy_stats)  # Speichere Gegner-Stats nur einmal

    if valid_players == 0:
        return {"avg_th": 0, "avg_trophies": 0}

    return {
        "avg_th": round(total_th_level / valid_players, 1),
        "avg_trophies": round(total_trophies / valid_players, 1),
    }

@tasks.loop(seconds=5)  # Alle 5 Sekunden
async def update_war_status():
    """Holt Kriegsdaten, analysiert unser Team mit der Spieler-API und speichert Gegner-Stats."""
    global war_message, last_war_state, ping_sent

    logging.info("🔄 update_war_status wird ausgeführt...")

    await bot.wait_until_ready()

    if not bot.guilds:
        logging.warning("❌ Bot ist in keinem Server!")
        return

    guild = bot.guilds[0]
    channel = await get_or_create_channel(guild)

    war_data = await fetch_data(API_URL)
    if not war_data or "state" not in war_data:
        logging.warning("⚠️ API gibt keine Kriegsdaten zurück.")
        return

    war_state = war_data["state"]
    start_time_str = war_data.get("startTime", None)
    end_time_str = war_data.get("endTime", None)

    start_time_left = get_time_remaining(start_time_str) if start_time_str else None
    time_left = get_time_remaining(end_time_str) if end_time_str else None

    # Kriegsinfos sammeln
    clan_name = war_data.get("clan", {}).get("name", "Unbekannt")
    opponent_name = war_data.get("opponent", {}).get("name", "Unbekannt")
    clan_stars = war_data.get("clan", {}).get("stars", 0)
    opponent_stars = war_data.get("opponent", {}).get("stars", 0)
    attacks_used = war_data.get("clan", {}).get("attacks", 0)
    team_size = war_data.get("teamSize", 0)
    remaining_attacks = team_size * 2 - attacks_used

    # **Team-Analyse mit API und Cache**
    clan_analysis = await analyze_team_with_cache(war_data.get("clan", {}).get("members", []), is_enemy_team=False)
    opponent_analysis = await analyze_team_with_cache(war_data.get("opponent", {}).get("members", []), is_enemy_team=True)

    # Embed für den Krieg erstellen
    embed = discord.Embed(title="🏆 **Clash of Clans Krieg**", color=discord.Color.blue())

    if war_state == "preparation":
        embed.description = f"⚔️ **Kriegsvorbereitung läuft!**\nDer Krieg startet in **{round(start_time_left, 1)} Stunden.**"
    elif war_state == "inWar":
        embed.description = f"🔥 **Der Krieg läuft!**\nEr endet in **{round(time_left, 1)} Stunden.**"
    elif war_state == "warEnded":
        embed.description = "🏁 **Der Krieg ist vorbei!**\nSchaut euch die Ergebnisse an!"

    # Detailierte Kriegsinfos hinzufügen
    embed.add_field(name="🏆 Clan", value=f"**{clan_name}**", inline=True)
    embed.add_field(name="⚔️ Gegner", value=f"**{opponent_name}**", inline=True)
    embed.add_field(name="⭐ Sterne", value=f"{clan_stars} - {opponent_stars}", inline=False)
    embed.add_field(name="🎯 Angriffe genutzt", value=f"{attacks_used} / {team_size * 2}", inline=True)
    embed.add_field(name="⚡ Verbleibende Angriffe", value=f"{remaining_attacks}", inline=True)
    embed.add_field(name="📊 Team-Analyse", value=f"🏠 **Ø Rathaus-Level**: {clan_analysis['avg_th']} vs. {opponent_analysis['avg_th']}\n🏆 **Ø Trophäen**: {clan_analysis['avg_trophies']} vs. {opponent_analysis['avg_trophies']}", inline=False)

    # Nachricht aktualisieren oder neue senden
    if war_message:
        await war_message.edit(embed=embed)
        logging.info("✅ Embed-Nachricht aktualisiert.")
    else:
        war_message = await channel.send(embed=embed)
        logging.info("✅ Neue Embed-Nachricht gesendet.")

@bot.event
async def on_ready():
    print(f"✅ {bot.user} ist bereit!")
    update_war_status.start()


bot.run(TOKEN)
