# Basis-Image mit Python
FROM python:3.10

# Setze das Arbeitsverzeichnis im Container
WORKDIR /app

# Kopiere die benötigten Dateien
COPY requirements.txt .
COPY bot.py .

# Installiere die Abhängigkeiten
RUN pip install --no-cache-dir -r requirements.txt

# Starte den Bot
CMD ["python", "bot.py"]
