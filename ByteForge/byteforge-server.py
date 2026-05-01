#!/usr/bin/env python3
"""
ByteForge Backend API
Run with: sudo python3 byteforge-server.py

ByteForge is intentionally CasaOS-independent. Docker is used as the default
runtime for game servers because it keeps setup, limits and restarts simple.
"""

import datetime
import json
import os
import platform
import shlex
import shutil
import subprocess
import threading
import time
from email.parser import BytesParser
from email.policy import default as email_policy
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PLATFORM = platform.system()  # 'Linux', 'Darwin', 'Windows'


def _is_admin():
    if hasattr(os, "geteuid"):
        return os.geteuid() == 0
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


PORT = int(os.environ.get("BYTEFORGE_PORT", "8080"))
DEFAULT_HOME = (
    "/opt/byteforge" if (_is_admin() and PLATFORM != "Windows")
    else str(Path.home() / ".byteforge")
)
BASE_DIR = Path(os.environ.get("BYTEFORGE_HOME", DEFAULT_HOME))
CONFIG_PATH = Path(os.environ.get("BYTEFORGE_CONFIG", str(BASE_DIR / "servers.json")))
FILES_ROOT = Path(os.environ.get("BYTEFORGE_FILES", str(BASE_DIR / "files")))
PUBLIC_ROOT = FILES_ROOT / "public"
PRIVATE_ROOT = FILES_ROOT / "private"
SERVER_ROOT = FILES_ROOT / "servers"
SHARED_ROOT = FILES_ROOT / "shared"

PRIVACY_APPS = {
    "bitwarden": {"name": "Bitwarden",  "image": "vaultwarden/server:latest",    "ports": ["8081:80"],                            "env": {},                                                        "data": "/data"},
    "nextcloud": {"name": "Nextcloud",  "image": "nextcloud:latest",              "ports": ["8888:80"],                            "env": {},                                                        "data": "/var/www/html"},
    "pihole":    {"name": "Pi-hole",    "image": "pihole/pihole:latest",          "ports": ["53:53/tcp", "53:53/udp", "8089:80"],  "env": {"TZ": "Europe/Copenhagen"},                               "data": "/etc/pihole"},
    "wireguard": {"name": "WireGuard",  "image": "linuxserver/wireguard",         "ports": ["51820:51820/udp"],                    "env": {"PUID": "1000", "PGID": "1000", "TZ": "Europe/Copenhagen"}, "data": "/config"},
    "portainer": {"name": "Portainer",  "image": "portainer/portainer-ce:latest", "ports": ["9000:9000"],                          "env": {},                                                        "data": "/data"},
    "grafana":   {"name": "Grafana",    "image": "grafana/grafana:latest",         "ports": ["3000:3000"],                          "env": {},                                                        "data": "/var/lib/grafana"},
    "jellyfin":  {"name": "Jellyfin",   "image": "jellyfin/jellyfin:latest",       "ports": ["8096:8096"],                          "env": {},                                                        "data": "/config"},
    "ollama":    {"name": "Ollama",     "image": "ollama/ollama:latest",           "ports": ["11434:11434"],                        "env": {},                                                        "data": "/root/.ollama"},
}

_STEAM = "https://cdn.cloudflare.steamstatic.com/steam/apps/{}/header.jpg"

SERVER_TYPES = {
    "minecraft-vanilla": {
        "name": "Minecraft Vanilla",
        "image": "itzg/minecraft-server",
        "env": {"EULA": "TRUE", "TYPE": "VANILLA"},
        "ports": ["25565:25565"],
        "data": "/data",
        "cover": "https://upload.wikimedia.org/wikipedia/en/5/51/Minecraft_cover.png",
        "category": "Minecraft",
    },
    "minecraft-paper": {
        "name": "Minecraft Paper",
        "image": "itzg/minecraft-server",
        "env": {"EULA": "TRUE", "TYPE": "PAPER"},
        "ports": ["25565:25565"],
        "data": "/data",
        "cover": "https://upload.wikimedia.org/wikipedia/en/5/51/Minecraft_cover.png",
        "category": "Minecraft",
    },
    "minecraft-spigot": {
        "name": "Minecraft Spigot",
        "image": "itzg/minecraft-server",
        "env": {"EULA": "TRUE", "TYPE": "SPIGOT"},
        "ports": ["25565:25565"],
        "data": "/data",
        "cover": "https://upload.wikimedia.org/wikipedia/en/5/51/Minecraft_cover.png",
        "category": "Minecraft",
    },
    "minecraft-forge": {
        "name": "Minecraft Forge",
        "image": "itzg/minecraft-server",
        "env": {"EULA": "TRUE", "TYPE": "FORGE"},
        "ports": ["25565:25565"],
        "data": "/data",
        "cover": "https://upload.wikimedia.org/wikipedia/en/5/51/Minecraft_cover.png",
        "category": "Minecraft",
    },
    "minecraft-fabric": {
        "name": "Minecraft Fabric",
        "image": "itzg/minecraft-server",
        "env": {"EULA": "TRUE", "TYPE": "FABRIC"},
        "ports": ["25565:25565"],
        "data": "/data",
        "cover": "https://upload.wikimedia.org/wikipedia/en/5/51/Minecraft_cover.png",
        "category": "Minecraft",
    },
    "fivem": {
        "name": "FiveM",
        "image": "spritsail/fivem",
        "env": {},
        "ports": ["30120:30120/tcp", "30120:30120/udp"],
        "data": "/config",
        "cover": _STEAM.format(271590),
        "category": "Andre",
    },
    "terraria": {
        "name": "Terraria",
        "image": "ryshe/terraria",
        "env": {"WORLD_FILENAME": "byteforge.wld"},
        "ports": ["7777:7777"],
        "data": "/root/.local/share/Terraria/Worlds",
        "cover": _STEAM.format(105600),
        "category": "Andre",
    },
    # ── Survival / Open World ──
    "ark-survival-evolved": {
        "name": "ARK Survival Evolved",
        "image": "hermsi/ark-server",
        "env": {"SESSION_NAME": "ByteForge ARK", "SERVER_MAP": "TheIsland", "ADMIN_PASSWORD": "byteforge", "MAX_PLAYERS": "20", "SERVER_PASSWORD": ""},
        "ports": ["7777:7777/udp", "7778:7778/udp", "27015:27015/udp"],
        "data": "/ark",
        "cover": _STEAM.format(346110),
        "category": "Survival / Open World",
    },
    "palworld": {
        "name": "Palworld",
        "image": "thijsvanloef/palworld-server-docker",
        "env": {"PLAYERS": "16", "MULTITHREADING": "true", "COMMUNITY": "false", "SERVER_NAME": "ByteForge Palworld", "ADMIN_PASSWORD": "byteforge", "SERVER_PASSWORD": ""},
        "ports": ["8211:8211/udp", "27015:27015/udp"],
        "data": "/palworld",
        "cover": _STEAM.format(1623730),
        "category": "Survival / Open World",
    },
    "rust": {
        "name": "Rust",
        "image": "didstopia/rust-server",
        "env": {"RUST_SERVER_STARTUP_ARGUMENTS": "+server.maxplayers 50 +server.hostname \"ByteForge Rust\"", "TZ": "Europe/Copenhagen"},
        "ports": ["28015:28015/udp", "28016:28016"],
        "data": "/steamcmd/rust",
        "cover": _STEAM.format(252490),
        "category": "Survival / Open World",
    },
    "7-days-to-die": {
        "name": "7 Days to Die",
        "image": "vinanrra/7dtd-server",
        "env": {"START_MODE": "1", "VERSION": "stable", "TZ": "Europe/Copenhagen"},
        "ports": ["26900:26900", "26900:26900/udp", "26901:26901/udp", "26902:26902/udp"],
        "data": "/home/sdtdserver",
        "cover": _STEAM.format(251570),
        "category": "Survival / Open World",
    },
    "dayz": {
        "name": "DayZ",
        "image": "drpain/dayz-server",
        "env": {"SERVER_NAME": "ByteForge DayZ", "MAX_PLAYERS": "20"},
        "ports": ["2302:2302/udp", "2303:2303/udp", "2304:2304/udp"],
        "data": "/dayzsrv",
        "cover": _STEAM.format(221100),
        "category": "Survival / Open World",
    },
    "valheim": {
        "name": "Valheim",
        "image": "lloesche/valheim-server",
        "env": {"SERVER_NAME": "ByteForge Valheim", "WORLD_NAME": "Dedicated", "SERVER_PASS": "byteforge", "SERVER_PUBLIC": "1"},
        "ports": ["2456:2456/udp", "2457:2457/udp", "2458:2458/udp"],
        "data": "/config",
        "cover": _STEAM.format(892970),
        "category": "Survival / Open World",
    },
    "project-zomboid": {
        "name": "Project Zomboid",
        "image": "danixu86/project-zomboid-server",
        "env": {"ADMINPASSWORD": "byteforge"},
        "ports": ["16261:16261/udp", "16262:16262/udp"],
        "data": "/data",
        "cover": _STEAM.format(108600),
        "category": "Survival / Open World",
    },
    "v-rising": {
        "name": "V Rising",
        "image": "trueosiris/vrising",
        "env": {"SERVERNAME": "ByteForge V Rising"},
        "ports": ["9876:9876/udp", "9877:9877/udp"],
        "data": "/mnt/vrising-data",
        "cover": _STEAM.format(1604030),
        "category": "Survival / Open World",
    },
    "sons-of-the-forest": {
        "name": "Sons of the Forest",
        "image": "jammsen/sons-of-the-forest",
        "env": {"SERVER_NAME": "ByteForge SotF", "SERVER_PASSWORD": "byteforge", "MAX_PLAYERS": "8"},
        "ports": ["8766:8766/udp", "27016:27016/udp", "9700:9700/udp"],
        "data": "/sonsoftheforest",
        "cover": _STEAM.format(1326470),
        "category": "Survival / Open World",
    },
    # ── Shooter / Action ──
    "counter-strike-2": {
        "name": "Counter-Strike 2",
        "image": "cm2network/cs2",
        "env": {"CS2_SERVERNAME": "ByteForge CS2", "CS2_CHEATS": "0", "CS2_PORT": "27015"},
        "ports": ["27015:27015/udp", "27015:27015"],
        "data": "/home/steam/cs2-dedicated",
        "cover": _STEAM.format(730),
        "category": "Shooter / Action",
    },
    "team-fortress-2": {
        "name": "Team Fortress 2",
        "image": "cm2network/tf2",
        "env": {"SRCDS_TOKEN": ""},
        "ports": ["27015:27015/udp", "27015:27015"],
        "data": "/home/steam/tf-dedicated",
        "cover": _STEAM.format(440),
        "category": "Shooter / Action",
    },
    "left4dead2": {
        "name": "Left 4 Dead 2",
        "image": "cm2network/l4d2",
        "env": {},
        "ports": ["27015:27015/udp", "27015:27015"],
        "data": "/home/steam/l4d2-dedicated",
        "cover": _STEAM.format(550),
        "category": "Shooter / Action",
    },
    "gmod": {
        "name": "Garry's Mod",
        "image": "cm2network/garrysmod",
        "env": {"SRCDS_TOKEN": ""},
        "ports": ["27015:27015/udp", "27015:27015"],
        "data": "/home/steam/gmod-dedicated",
        "cover": _STEAM.format(4000),
        "category": "Shooter / Action",
    },
    # ── Simulation / Builder ──
    "satisfactory": {
        "name": "Satisfactory",
        "image": "wolveix/satisfactory-server",
        "env": {"MAXPLAYERS": "4", "AUTOPAUSE": "true", "AUTOSAVENUM": "3"},
        "ports": ["7777:7777/udp"],
        "data": "/config",
        "cover": _STEAM.format(526870),
        "category": "Simulation / Builder",
    },
    "factorio": {
        "name": "Factorio",
        "image": "factoriotools/factorio",
        "env": {},
        "ports": ["34197:34197/udp", "27015:27015"],
        "data": "/factorio",
        "cover": _STEAM.format(427520),
        "category": "Simulation / Builder",
    },
    "astroneer": {
        "name": "Astroneer",
        "image": "phntxx/astroneer",
        "env": {},
        "ports": ["8777:8777/udp", "7777:7777/udp"],
        "data": "/data",
        "cover": _STEAM.format(361420),
        "category": "Simulation / Builder",
    },
    "space-engineers": {
        "name": "Space Engineers",
        "image": "mmmaxwwwell/space-engineers-server",
        "env": {"SERVER_NAME": "ByteForge Space Engineers"},
        "ports": ["27016:27016/udp"],
        "data": "/config",
        "cover": _STEAM.format(244850),
        "category": "Simulation / Builder",
    },
    "farming-simulator-22": {
        "name": "Farming Simulator 22",
        "image": "lysander07/farming-simulator-22",
        "env": {},
        "ports": ["10823:10823"],
        "data": "/farmingsimulator22/game",
        "cover": _STEAM.format(1300530),
        "category": "Simulation / Builder",
    },
    "farming-simulator-25": {
        "name": "Farming Simulator 25",
        "image": "lysander07/farming-simulator-25",
        "env": {},
        "ports": ["10823:10823"],
        "data": "/farmingsimulator25/game",
        "cover": _STEAM.format(2300260),
        "category": "Simulation / Builder",
    },
    # ── Other ──
    "unturned": {
        "name": "Unturned",
        "image": "gameservermanagers/gameservermanager",
        "env": {"LGSM_GAMESERVER": "untserver"},
        "ports": ["27015:27015/udp", "27016:27016/udp"],
        "data": "/data/serverfiles",
        "cover": _STEAM.format(304930),
        "category": "Andre",
    },
    "euro-truck-simulator-2": {
        "name": "Euro Truck Simulator 2",
        "image": "brendanmanning/ets2-server",
        "env": {},
        "ports": ["27015:27015/udp"],
        "data": "/data",
        "cover": _STEAM.format(227300),
        "category": "Andre",
    },
    "custom": {
        "name": "Custom Game Server",
        "image": "ubuntu:latest",
        "env": {},
        "ports": [],
        "data": "/data",
        "cover": "",
        "category": "Andre",
    },
}


APP_CATALOG = {
    # ── Media ──
    "jellyfin":         {"name":"Jellyfin",          "icon":"🎬","desc":"Open-source media server. Stream movies, TV, music.",                 "category":"Media",       "image":"jellyfin/jellyfin:latest",                        "ports":["8096:8096"],                        "data":"/config","env":{}},
    "plex":             {"name":"Plex",               "icon":"🎥","desc":"Premium media server with mobile apps and transcoding.",               "category":"Media",       "image":"plexinc/pms-docker",                              "ports":["32400:32400"],                      "data":"/config","env":{"TZ":"Europe/Copenhagen"}},
    "navidrome":        {"name":"Navidrome",          "icon":"🎵","desc":"Modern music server. Subsonic-compatible API.",                        "category":"Media",       "image":"deluan/navidrome:latest",                         "ports":["4533:4533"],                        "data":"/data","env":{}},
    "photoprism":       {"name":"Photoprism",         "icon":"📸","desc":"AI-powered photo management. Google Photos alternative.",             "category":"Media",       "image":"photoprism/photoprism:latest",                    "ports":["2342:2342"],                        "data":"/photoprism/storage","env":{"PHOTOPRISM_AUTH_MODE":"public"}},
    "immich":           {"name":"Immich",             "icon":"🖼","desc":"High performance self-hosted photo and video backup.",                 "category":"Media",       "image":"ghcr.io/immich-app/immich-server:release",        "ports":["2283:3001"],                        "data":"/usr/src/app/upload","env":{}},
    # ── Development ──
    "vscode-server":    {"name":"VS Code Server",     "icon":"💻","desc":"Full VS Code IDE running in your browser.",                           "category":"Development", "image":"codercom/code-server:latest",                     "ports":["8443:8443"],                        "data":"/home/coder","env":{"PASSWORD":"byteforge"}},
    "gitea":            {"name":"Gitea",              "icon":"🦊","desc":"Lightweight self-hosted Git service. GitHub alternative.",            "category":"Development", "image":"gitea/gitea:latest",                              "ports":["3000:3000","222:22"],               "data":"/data","env":{}},
    "portainer":        {"name":"Portainer",          "icon":"🐋","desc":"Docker management UI. Manage containers, images, volumes.",           "category":"Development", "image":"portainer/portainer-ce:latest",                   "ports":["9000:9000"],                        "data":"/data","env":{}},
    "registry":         {"name":"Docker Registry",   "icon":"📦","desc":"Private Docker image registry.",                                      "category":"Development", "image":"registry:2",                                      "ports":["5000:5000"],                        "data":"/var/lib/registry","env":{}},
    "drone":            {"name":"Drone CI",           "icon":"🚀","desc":"Container-native CI/CD platform.",                                    "category":"Development", "image":"drone/drone:latest",                              "ports":["3005:80"],                          "data":"/data","env":{}},
    # ── Network ──
    "nginx-pm":         {"name":"Nginx Proxy Mgr",   "icon":"🌐","desc":"Reverse proxy with beautiful SSL GUI. Route any domain.",            "category":"Network",     "image":"jc21/nginx-proxy-manager:latest",                 "ports":["80:80","81:81","443:443"],          "data":"/data","env":{}},
    "adguard":          {"name":"AdGuard Home",       "icon":"🛡","desc":"Network-wide ad & tracker blocker. Pi-hole alternative.",            "category":"Network",     "image":"adguard/adguardhome:latest",                      "ports":["53:53/udp","3001:3000"],            "data":"/opt/adguardhome/work","env":{}},
    "traefik":          {"name":"Traefik",            "icon":"🔀","desc":"Modern reverse proxy & load balancer with auto SSL.",                "category":"Network",     "image":"traefik:latest",                                  "ports":["80:80","8080:8080"],               "data":"/etc/traefik","env":{}},
    "wireguard":        {"name":"WireGuard VPN",      "icon":"🔒","desc":"Fast, modern VPN server. Access your homelab from anywhere.",        "category":"Network",     "image":"linuxserver/wireguard",                           "ports":["51820:51820/udp"],                  "data":"/config","env":{"PUID":"1000","PGID":"1000","TZ":"Europe/Copenhagen"}},
    "cloudflared":      {"name":"Cloudflare Tunnel",  "icon":"☁","desc":"Expose services without opening ports. Zero Trust tunnels.",          "category":"Network",     "image":"cloudflare/cloudflared:latest",                   "ports":[],                                  "data":"/etc/cloudflared","env":{}},
    # ── Cloud Storage ──
    "nextcloud":        {"name":"Nextcloud",          "icon":"☁","desc":"Your private cloud. Files, calendar, contacts and more.",             "category":"Cloud",       "image":"nextcloud:latest",                                "ports":["8888:80"],                          "data":"/var/www/html","env":{}},
    "syncthing":        {"name":"Syncthing",          "icon":"🔄","desc":"Continuous file synchronization across all your devices.",           "category":"Cloud",       "image":"syncthing/syncthing:latest",                      "ports":["8384:8384","22000:22000"],          "data":"/var/syncthing","env":{}},
    "duplicati":        {"name":"Duplicati",          "icon":"💾","desc":"Backup to cloud storage with encryption and scheduling.",            "category":"Cloud",       "image":"lscr.io/linuxserver/duplicati:latest",            "ports":["8200:8200"],                        "data":"/config","env":{}},
    # ── Monitoring ──
    "grafana":          {"name":"Grafana",            "icon":"📊","desc":"Analytics & monitoring dashboards. Connect any data source.",        "category":"Monitoring",  "image":"grafana/grafana:latest",                          "ports":["3000:3000"],                        "data":"/var/lib/grafana","env":{}},
    "prometheus":       {"name":"Prometheus",         "icon":"🔥","desc":"Metrics collection & alerting toolkit.",                             "category":"Monitoring",  "image":"prom/prometheus:latest",                          "ports":["9090:9090"],                        "data":"/prometheus","env":{}},
    "uptime-kuma":      {"name":"Uptime Kuma",        "icon":"💓","desc":"Self-hosted uptime monitor. Check websites and services.",           "category":"Monitoring",  "image":"louislam/uptime-kuma:1",                          "ports":["3001:3001"],                        "data":"/app/data","env":{}},
    "netdata":          {"name":"Netdata",            "icon":"📈","desc":"Real-time performance monitoring. Zero config required.",            "category":"Monitoring",  "image":"netdata/netdata:latest",                          "ports":["19999:19999"],                      "data":"/var/lib/netdata","env":{}},
    # ── Security ──
    "bitwarden":        {"name":"Bitwarden",          "icon":"🔑","desc":"Self-hosted password manager. Sync across all devices.",             "category":"Security",    "image":"vaultwarden/server:latest",                       "ports":["8081:80"],                          "data":"/data","env":{}},
    "authelia":         {"name":"Authelia",           "icon":"🔐","desc":"SSO & 2FA portal for all your services.",                            "category":"Security",    "image":"authelia/authelia:latest",                        "ports":["9091:9091"],                        "data":"/config","env":{}},
    "pihole":           {"name":"Pi-hole",            "icon":"🌑","desc":"Network-wide ad blocking DNS server.",                               "category":"Security",    "image":"pihole/pihole:latest",                            "ports":["53:53/tcp","53:53/udp","8089:80"],  "data":"/etc/pihole","env":{"TZ":"Europe/Copenhagen"}},
    "searxng":          {"name":"SearXNG",            "icon":"🔍","desc":"Privacy-respecting metasearch engine.",                              "category":"Security",    "image":"searxng/searxng:latest",                          "ports":["8082:8080"],                        "data":"/etc/searxng","env":{}},
    # ── Database ──
    "mysql":            {"name":"MySQL",              "icon":"🗄","desc":"World's most popular open source database.",                         "category":"Database",    "image":"mysql:8.0",                                       "ports":["3306:3306"],                        "data":"/var/lib/mysql","env":{"MYSQL_ROOT_PASSWORD":"byteforge"}},
    "postgres":         {"name":"PostgreSQL",         "icon":"🐘","desc":"Advanced open source relational database.",                          "category":"Database",    "image":"postgres:15",                                     "ports":["5432:5432"],                        "data":"/var/lib/postgresql/data","env":{"POSTGRES_PASSWORD":"byteforge"}},
    "redis":            {"name":"Redis",              "icon":"⚡","desc":"In-memory data structure store. Cache & message broker.",            "category":"Database",    "image":"redis:alpine",                                    "ports":["6379:6379"],                        "data":"/data","env":{}},
    "mongodb":          {"name":"MongoDB",            "icon":"🍃","desc":"NoSQL document database for modern applications.",                   "category":"Database",    "image":"mongo:latest",                                    "ports":["27017:27017"],                      "data":"/data/db","env":{}},
    "mariadb":          {"name":"MariaDB",            "icon":"🦭","desc":"MySQL-compatible database with extra features.",                     "category":"Database",    "image":"mariadb:latest",                                  "ports":["3307:3306"],                        "data":"/var/lib/mysql","env":{"MARIADB_ROOT_PASSWORD":"byteforge"}},
    # ── Home Automation ──
    "homeassistant":    {"name":"Home Assistant",     "icon":"🏠","desc":"Open source home automation. Control everything from one place.",   "category":"Home",        "image":"homeassistant/home-assistant:stable",             "ports":["8123:8123"],                        "data":"/config","env":{}},
    "node-red":         {"name":"Node-RED",           "icon":"🔴","desc":"Flow-based programming for automation.",                             "category":"Home",        "image":"nodered/node-red:latest",                         "ports":["1880:1880"],                        "data":"/data","env":{}},
    "mosquitto":        {"name":"Mosquitto MQTT",     "icon":"📡","desc":"Lightweight MQTT message broker for IoT.",                          "category":"Home",        "image":"eclipse-mosquitto:latest",                        "ports":["1883:1883"],                        "data":"/mosquitto/data","env":{}},
    # ── Productivity ──
    "bookstack":        {"name":"BookStack",          "icon":"📚","desc":"Simple wiki & documentation platform.",                              "category":"Productivity","image":"lscr.io/linuxserver/bookstack:latest",            "ports":["6875:80"],                          "data":"/config","env":{"APP_URL":"http://localhost:6875"}},
    "wikijs":           {"name":"Wiki.js",            "icon":"📖","desc":"Powerful, extensible open source wiki.",                            "category":"Productivity","image":"ghcr.io/requarks/wiki:2",                         "ports":["3004:3000"],                        "data":"/wiki/data","env":{}},
    "n8n":              {"name":"n8n",                "icon":"⚙","desc":"Workflow automation. Connect anything to anything.",                  "category":"Productivity","image":"n8nio/n8n:latest",                              "ports":["5678:5678"],                        "data":"/home/node/.n8n","env":{}},
    "paperless":        {"name":"Paperless-ngx",      "icon":"📄","desc":"Document management system. Go paperless.",                         "category":"Productivity","image":"ghcr.io/paperless-ngx/paperless-ngx:latest",    "ports":["8000:8000"],                        "data":"/usr/src/paperless/data","env":{}},
    "freshrss":         {"name":"FreshRSS",           "icon":"📰","desc":"Self-hosted RSS feed aggregator.",                                  "category":"Productivity","image":"freshrss/freshrss:latest",                       "ports":["8070:80"],                          "data":"/var/www/FreshRSS/data","env":{}},
    # ── AI ──
    "ollama":           {"name":"Ollama",             "icon":"🤖","desc":"Run LLMs locally. Llama, Mistral, Gemma and more.",                 "category":"AI",          "image":"ollama/ollama:latest",                            "ports":["11434:11434"],                      "data":"/root/.ollama","env":{}},
    "open-webui":       {"name":"Open WebUI",         "icon":"💬","desc":"ChatGPT-like web interface for Ollama.",                            "category":"AI",          "image":"ghcr.io/open-webui/open-webui:main",              "ports":["3002:8080"],                        "data":"/app/backend/data","env":{"OLLAMA_BASE_URL":"http://host.docker.internal:11434"}},
    "stable-diffusion": {"name":"Stable Diffusion",   "icon":"🎨","desc":"AI image generation from text prompts.",                            "category":"AI",          "image":"universonic/stable-diffusion-webui:full",          "ports":["7860:7860"],                        "data":"/data","env":{}},
}

# ── METRICS HISTORY ──
_METRICS_HISTORY = []
_METRICS_LOCK = threading.Lock()

def _metrics_collector():
    while True:
        try:
            s = get_system()
            entry = {
                "ts": int(time.time()),
                "cpu": s["cpu"],
                "ram": s["ram_pct"],
                "temp": s["temp"] if isinstance(s["temp"], (int, float)) else 0,
            }
            with _METRICS_LOCK:
                _METRICS_HISTORY.append(entry)
                if len(_METRICS_HISTORY) > 60:
                    _METRICS_HISTORY.pop(0)
        except Exception:
            pass
        time.sleep(5)

def exec_command(cmd):
    BLOCKED = ["rm -rf /", "mkfs", "> /dev/", "dd if=", ":(){:|:&};:", "chmod 777 /", "chmod -R 777 /"]
    cmd_lower = cmd.lower().strip()
    for b in BLOCKED:
        if b in cmd_lower:
            return {"ok": False, "output": "⛔ Kommando blokeret af sikkerhedshensyn", "code": 1}
    out, err, code = run(cmd, timeout=15, shell=True)
    return {"ok": True, "output": out or err or "(ingen output)", "code": code}

def get_appstore():
    apps = []
    for app_id, app in APP_CATALOG.items():
        container = f"byteforge-{app_id}"
        installed = container_exists(container)
        status = docker_status(container) if installed else "not_installed"
        apps.append({**app, "id": app_id, "installed": installed, "status": status})
    return apps

def appstore_install(app_id):
    if not docker_available():
        return {"ok": False, "msg": "Docker er ikke tilgængelig"}
    app = APP_CATALOG.get(app_id)
    if not app:
        return {"ok": False, "msg": f"Ukendt app: {app_id}"}
    container = f"byteforge-{app_id}"
    if container_exists(container):
        return {"ok": False, "msg": f"{app['name']} er allerede installeret"}
    data_path = SERVER_ROOT / "apps" / app_id
    data_path.mkdir(parents=True, exist_ok=True)
    cmd = ["docker", "run", "-d", "--name", container, "--label", "byteforge.app=true", "--restart", "unless-stopped"]
    for k, v in app["env"].items():
        cmd += ["-e", f"{k}={v}"]
    for p in app["ports"]:
        cmd += ["-p", p]
    if app["data"]:
        cmd += ["-v", f"{data_path}:{app['data']}"]
    cmd.append(app["image"])
    out, err, code = run(cmd, timeout=120, shell=False)
    host_port = app["ports"][0].split(":")[0] if app["ports"] else ""
    url = f" → http://localhost:{host_port}" if host_port else ""
    return {"ok": code == 0, "msg": (out or err or f"{app['name']} installeret") + url}

def appstore_uninstall(app_id):
    container = f"byteforge-{app_id}"
    if not container_exists(container):
        return {"ok": False, "msg": "Container ikke fundet"}
    out, err, code = run(["docker", "rm", "-f", container], timeout=15, shell=False)
    return {"ok": code == 0, "msg": out or err or "Afinstalleret"}


def ensure_dirs():
    for path in (BASE_DIR, FILES_ROOT, PUBLIC_ROOT, PRIVATE_ROOT, SERVER_ROOT, SHARED_ROOT):
        path.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        save_config({"servers": default_servers(), "users": default_users(), "settings": default_settings()})


def default_servers():
    return [
        {
            "id": "minecraft-main",
            "name": "Minecraft Main",
            "type": "minecraft-paper",
            "container": "byteforge-minecraft-main",
            "port": 25565,
            "cpu_limit": "2",
            "memory_limit": "4g",
            "auto_restart": True,
            "owner": "lucas",
            "visibility": "shared",
            "path": str(SERVER_ROOT / "minecraft-main"),
        }
    ]


def default_users():
    return [
        {"id": "lucas", "name": "Lucas", "role": "owner", "access": ["*"]},
        {"id": "guest", "name": "Guest", "role": "viewer", "access": ["public"]},
    ]


def default_settings():
    return {"theme": "forge-dark", "language": "da", "background": "grid", "website_hosting": True}


def load_config():
    ensure_dirs()
    try:
        with CONFIG_PATH.open() as f:
            data = json.load(f)
    except Exception:
        data = {}
    data.setdefault("servers", default_servers())
    data.setdefault("users", default_users())
    data.setdefault("settings", default_settings())
    return data


def save_config(data):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".tmp")
    with tmp.open("w") as f:
        json.dump(data, f, indent=2)
    tmp.replace(CONFIG_PATH)


def run(cmd, timeout=10, shell=True):
    try:
        r = subprocess.run(cmd, shell=shell, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except Exception as exc:
        return "", str(exc), 1


def docker_available():
    _, _, code = run(["docker", "version"], timeout=4, shell=False)
    return code == 0


def docker_status(container):
    out, _, code = run(["docker", "inspect", "--format={{.State.Status}}", container], timeout=5, shell=False)
    return out if code == 0 and out else "stopped"


def docker_logs(container, tail=30):
    out, err, _ = run(["docker", "logs", f"--tail={tail}", container], timeout=8, shell=False)
    return out or err


def docker_stats(container):
    fmt = "{{.CPUPerc}}|{{.MemUsage}}|{{.NetIO}}"
    out, _, code = run(["docker", "stats", "--no-stream", "--format", fmt, container], timeout=6, shell=False)
    if code != 0 or "|" not in out:
        return {"cpu": "-", "memory": "-", "network": "-"}
    cpu, memory, network = out.split("|", 2)
    return {"cpu": cpu, "memory": memory, "network": network}


def slugify(value):
    clean = "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")
    return "-".join(part for part in clean.split("-") if part)[:48] or f"server-{int(time.time())}"


def get_system():
    cpu, total, used, temp, uptime = 0, 0, 0, "?", "?"

    if PLATFORM == "Linux":
        cpu_out, _, _ = run("top -bn1 | grep 'Cpu(s)' | awk '{print $2}'")
        if not cpu_out:
            cpu_out, _, _ = run("grep 'cpu ' /proc/stat | awk '{usage=($2+$4)*100/($2+$3+$4+$5)} END {print usage}'")
        try:
            cpu = round(float(cpu_out), 1)
        except Exception:
            cpu = 0
        try:
            with open("/proc/meminfo") as f:
                mem = {l.split(":")[0]: int(l.split(":")[1].strip().split()[0]) for l in f if ":" in l}
            total = mem.get("MemTotal", 0)
            used = total - mem.get("MemAvailable", 0)
        except Exception:
            pass
        try:
            temp_raw, _, _ = run("cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null")
            temp = round(int(temp_raw) / 1000, 1)
        except Exception:
            t2, _, _ = run("sensors 2>/dev/null | grep 'Core 0' | awk '{print $3}' | tr -d '+°C'")
            temp = t2 or "?"
        try:
            uptime_s = int(open("/proc/uptime").read().split()[0].split(".")[0])
            h, m = divmod(uptime_s // 60, 60)
            d, h = divmod(h, 24)
            uptime = f"{d}d {h}h {m}m" if d else f"{h}h {m}m"
        except Exception:
            pass

    elif PLATFORM == "Darwin":
        cpu_out, _, _ = run("top -l 1 -s 0 | grep 'CPU usage' | awk '{print $3}' | tr -d '%'")
        try:
            cpu = round(float(cpu_out), 1)
        except Exception:
            cpu = 0
        try:
            mem_out, _, _ = run("sysctl hw.memsize")
            total = int(mem_out.split(":")[1].strip()) // 1024
            vm_out, _, _ = run("vm_stat")
            page_size = 4096
            pages_free = pages_inactive = 0
            for line in vm_out.splitlines():
                if "page size of" in line:
                    page_size = int(line.split("page size of")[1].split("bytes")[0].strip())
                elif "Pages free" in line:
                    pages_free = int(line.split(":")[1].strip().rstrip("."))
                elif "Pages inactive" in line:
                    pages_inactive = int(line.split(":")[1].strip().rstrip("."))
            avail = (pages_free + pages_inactive) * page_size // 1024
            used = total - avail
        except Exception:
            pass
        temp_out, _, _ = run("osx-cpu-temp 2>/dev/null || echo '?'")
        temp = temp_out.replace("°C", "").strip() or "?"
        try:
            boot_out, _, _ = run("sysctl kern.boottime | awk '{print $5}' | tr -d ','")
            uptime_s = int(time.time()) - int(boot_out)
            h, m = divmod(uptime_s // 60, 60)
            d, h = divmod(h, 24)
            uptime = f"{d}d {h}h {m}m" if d else f"{h}h {m}m"
        except Exception:
            pass

    elif PLATFORM == "Windows":
        cpu_out, _, _ = run("wmic cpu get loadpercentage /value", shell=True)
        try:
            cpu = round(float(next(l for l in cpu_out.splitlines() if "=" in l).split("=")[1].strip()), 1)
        except Exception:
            cpu = 0
        try:
            mem_out, _, _ = run("wmic OS get FreePhysicalMemory,TotalVisibleMemorySize /value", shell=True)
            vals = {l.split("=")[0].strip(): l.split("=")[1].strip() for l in mem_out.splitlines() if "=" in l and l.split("=")[1].strip()}
            total = int(vals.get("TotalVisibleMemorySize", 0))
            used = total - int(vals.get("FreePhysicalMemory", 0))
        except Exception:
            pass
        try:
            boot_out, _, _ = run("wmic os get lastbootuptime /value", shell=True)
            boot_str = next(l for l in boot_out.splitlines() if "=" in l).split("=")[1].strip()[:14]
            boot_dt = datetime.datetime.strptime(boot_str, "%Y%m%d%H%M%S")
            uptime_s = int((datetime.datetime.now() - boot_dt).total_seconds())
            h, m = divmod(uptime_s // 60, 60)
            d, h = divmod(h, 24)
            uptime = f"{d}d {h}h {m}m" if d else f"{h}h {m}m"
        except Exception:
            pass
        temp = "?"

    return {
        "cpu": cpu,
        "ram_used_mb": used // 1024,
        "ram_total_mb": total // 1024,
        "ram_pct": round(used / total * 100, 1) if total else 0,
        "temp": temp,
        "uptime": uptime,
    }


def get_disks():
    disks = []
    if PLATFORM == "Windows":
        out, _, _ = run("wmic logicaldisk get caption,size,freespace /format:csv", shell=True)
        seen = set()
        for line in out.splitlines()[2:]:
            parts = line.strip().split(",")
            if len(parts) >= 4:
                caption, free_s, size_s = parts[1], parts[2], parts[3]
                if caption and size_s and caption not in seen:
                    seen.add(caption)
                    try:
                        total_g = int(size_s) // (1024 ** 3) or 1
                        free_g = int(free_s) // (1024 ** 3)
                        used_g = total_g - free_g
                        disks.append({"mount": caption, "total": str(total_g), "used": str(used_g),
                                      "free": str(free_g), "pct": str(round(used_g / total_g * 100))})
                    except Exception:
                        pass
        return disks
    if PLATFORM == "Darwin":
        cmd = f"df -g / {shlex.quote(str(FILES_ROOT))} 2>/dev/null || df -g /"
    else:
        cmd = f"df -BG / {shlex.quote(str(FILES_ROOT))} 2>/dev/null || df -BG /"
    out, _, _ = run(cmd)
    seen = set()
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 6 and parts[5] not in seen:
            seen.add(parts[5])
            disks.append({
                "mount": parts[5],
                "total": parts[1].replace("G", ""),
                "used": parts[2].replace("G", ""),
                "free": parts[3].replace("G", ""),
                "pct": parts[4].replace("%", ""),
            })
    return disks


def get_raid():
    if PLATFORM != "Linux":
        return {"status": "inactive", "info": f"RAID administration ikke understøttet på {PLATFORM}"}
    md, _, _ = run("cat /proc/mdstat 2>/dev/null")
    if not md or "md" not in md:
        return {"status": "inactive", "info": "Ingen RAID konfigureret"}
    info = [line.strip() for line in md.splitlines() if line.strip()]
    state = "active" if "active" in md else "degraded" if "degraded" in md else "unknown"
    return {"status": state, "info": "\n".join(info[:6])}


def get_nas():
    if PLATFORM == "Windows":
        return {"status": "inactive", "shares": [], "path": str(SHARED_ROOT)}
    if PLATFORM == "Darwin":
        exports, _, _ = run("cat /etc/exports 2>/dev/null")
        active, _, _ = run("nfsd status 2>/dev/null | head -1")
        shares = [l.strip() for l in exports.splitlines() if l.strip() and not l.startswith("#")]
        return {"status": "active" if "running" in active.lower() else "inactive", "shares": shares, "path": str(SHARED_ROOT)}
    exports, _, _ = run("cat /etc/exports 2>/dev/null")
    active, _, _ = run("systemctl is-active nfs-server 2>/dev/null || systemctl is-active nfs-kernel-server 2>/dev/null")
    shares = [line.strip() for line in exports.splitlines() if line.strip() and not line.startswith("#")]
    return {"status": active.strip(), "shares": shares, "path": str(SHARED_ROOT)}


def get_hardware():
    cpu_model = cpu_cores = gpu = ""
    if PLATFORM == "Linux":
        m, _, _ = run("grep 'model name' /proc/cpuinfo | head -1 | cut -d: -f2")
        cpu_model = m.strip()
        c, _, _ = run("nproc --all 2>/dev/null || grep -c processor /proc/cpuinfo")
        cpu_cores = c.strip()
        g, _, _ = run("lspci 2>/dev/null | grep -iE 'vga|3d|display' | head -1 | sed 's/.*: //'")
        gpu = g.strip()
        if not gpu:
            g2, _, _ = run("nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1")
            gpu = g2.strip()
    elif PLATFORM == "Darwin":
        m, _, _ = run("sysctl machdep.cpu.brand_string 2>/dev/null | cut -d: -f2")
        cpu_model = m.strip()
        c, _, _ = run("sysctl hw.logicalcpu 2>/dev/null | cut -d: -f2")
        cpu_cores = c.strip()
        g, _, _ = run("system_profiler SPDisplaysDataType 2>/dev/null | grep 'Chipset Model' | head -1 | cut -d: -f2")
        gpu = g.strip()
    elif PLATFORM == "Windows":
        mo, _, _ = run("wmic cpu get name /value", shell=True)
        cpu_model = next((l.split("=", 1)[1].strip() for l in mo.splitlines() if "=" in l and l.split("=", 1)[1].strip()), "")
        co, _, _ = run("wmic cpu get NumberOfLogicalProcessors /value", shell=True)
        cpu_cores = next((l.split("=", 1)[1].strip() for l in co.splitlines() if "=" in l and l.split("=", 1)[1].strip()), "")
        go, _, _ = run("wmic path win32_VideoController get name /value", shell=True)
        gpu = next((l.split("=", 1)[1].strip() for l in go.splitlines() if "=" in l and l.split("=", 1)[1].strip()), "")
    hostname, _, _ = run("hostname")
    mb = ""
    if PLATFORM == "Linux":
        mb_v, _, _ = run("cat /sys/class/dmi/id/board_vendor 2>/dev/null")
        mb_n, _, _ = run("cat /sys/class/dmi/id/board_name 2>/dev/null")
        mb = f"{mb_v.strip()} {mb_n.strip()}".strip()
    elif PLATFORM == "Darwin":
        mb_o, _, _ = run("system_profiler SPHardwareDataType 2>/dev/null | grep 'Model Name' | cut -d: -f2")
        mb = mb_o.strip()
    elif PLATFORM == "Windows":
        mb_o, _, _ = run("wmic baseboard get manufacturer,product /value", shell=True)
        parts = {l.split("=")[0].strip(): l.split("=")[1].strip() for l in mb_o.splitlines() if "=" in l and l.split("=")[1].strip()}
        mb = f"{parts.get('Manufacturer','')} {parts.get('Product','')}".strip()
    return {
        "cpu_model": cpu_model or "Ukendt CPU",
        "cpu_cores": cpu_cores or "?",
        "gpu": gpu or "Ingen GPU fundet",
        "motherboard": mb or "?",
        "hostname": hostname.strip(),
        "platform": PLATFORM,
    }


def get_docker():
    out, _, _ = run("docker ps --format '{{.Names}}|{{.Status}}|{{.Image}}' 2>/dev/null")
    containers = []
    for line in out.splitlines():
        if "|" in line:
            name, status, image = line.split("|", 2)
            containers.append({"name": name, "status": status, "image": image})
    return containers


def get_game_servers(include_logs=False):
    config = load_config()
    servers = []
    for server in config["servers"]:
        item = dict(server)
        item["kind"] = SERVER_TYPES.get(item.get("type"), SERVER_TYPES["custom"])["name"]
        item["status"] = docker_status(item["container"])
        item["stats"] = docker_stats(item["container"]) if item["status"] == "running" else {"cpu": "-", "memory": "-", "network": "-"}
        item["logs"] = docker_logs(item["container"]) if include_logs else ""
        item["path"] = str(Path(item.get("path", SERVER_ROOT / item["id"])))
        servers.append(item)
    return servers


def legacy_minecraft():
    servers = get_game_servers(include_logs=True)
    mc = next((s for s in servers if s["type"].startswith("minecraft")), None)
    if not mc:
        return {"status": "stopped", "logs": "", "players": "", "port": 25565}
    players = ""
    if mc["status"] == "running":
        out, _, _ = run(["docker", "exec", mc["container"], "rcon-cli", "list"], timeout=5, shell=False)
        players = out
    return {"status": mc["status"], "logs": mc["logs"], "players": players, "port": mc.get("port", 25565)}


def container_exists(container):
    _, _, code = run(["docker", "inspect", "--format={{.Id}}", container], timeout=5, shell=False)
    return code == 0


def _docker_run_server(server):
    profile = SERVER_TYPES.get(server.get("type"), SERVER_TYPES["custom"])
    data_path = Path(server.get("path", str(SERVER_ROOT / server["id"])))
    data_path.mkdir(parents=True, exist_ok=True)
    cmd = ["docker", "run", "-d", "--name", server["container"], "--label", "byteforge.server=true"]
    cmd += ["--cpus", str(server.get("cpu_limit", "2")), "--memory", str(server.get("memory_limit", "2g"))]
    if server.get("auto_restart", True):
        cmd += ["--restart", "unless-stopped"]
    for key, value in profile["env"].items():
        cmd += ["-e", f"{key}={value}"]
    port = server.get("port", 0)
    for mapping in profile["ports"]:
        host, rest = mapping.split(":", 1)
        if port and host.isdigit():
            mapping = f"{port}:{rest}"
        cmd += ["-p", mapping]
    cmd += ["-v", f"{data_path}:{profile['data']}", profile["image"]]
    out, err, code = run(cmd, timeout=120, shell=False)
    return {"ok": code == 0, "msg": out or err or f"{server['name']} startet"}


def game_action(server_id, action):
    server = next((s for s in load_config()["servers"] if s["id"] == server_id), None)
    if not server:
        return {"ok": False, "msg": "Server ikke fundet"}
    if action not in ("start", "stop", "restart"):
        return {"ok": False, "msg": "Ukendt kommando"}
    if not docker_available():
        return {"ok": False, "msg": "Docker er ikke tilgængelig"}
    if action == "start" and not container_exists(server["container"]):
        return _docker_run_server(server)
    out, err, code = run(["docker", action, server["container"]], timeout=45, shell=False)
    return {"ok": code == 0, "msg": out or err or f"{server['name']} {action}"}


def create_game_server(body):
    config = load_config()
    name = body.get("name") or "ByteForge Server"
    server_type = body.get("type") or "minecraft-paper"
    profile = SERVER_TYPES.get(server_type, SERVER_TYPES["custom"])
    sid = slugify(name)
    existing_ids = {s["id"] for s in config["servers"]}
    base_sid = sid
    index = 2
    while sid in existing_ids:
        sid = f"{base_sid}-{index}"
        index += 1

    port = int(body.get("port") or (profile["ports"][0].split(":", 1)[0].split("/", 1)[0] if profile["ports"] else 0) or 0)
    container = f"byteforge-{sid}"
    data_path = SERVER_ROOT / sid
    data_path.mkdir(parents=True, exist_ok=True)

    server = {
        "id": sid,
        "name": name,
        "type": server_type,
        "container": container,
        "port": port,
        "cpu_limit": str(body.get("cpu_limit") or "2"),
        "memory_limit": str(body.get("memory_limit") or "2g"),
        "auto_restart": bool(body.get("auto_restart", True)),
        "owner": body.get("owner") or "lucas",
        "visibility": body.get("visibility") or "shared",
        "path": str(data_path),
    }
    config["servers"].append(server)
    save_config(config)

    if not body.get("deploy", True):
        return {"ok": True, "server": server, "msg": "Serverprofil oprettet uden deploy"}
    if not docker_available():
        return {"ok": False, "server": server, "msg": "Docker er ikke tilgængelig. Profilen er gemt."}

    cmd = ["docker", "run", "-d", "--name", container, "--label", "byteforge.server=true"]
    cmd += ["--cpus", server["cpu_limit"], "--memory", server["memory_limit"]]
    if server["auto_restart"]:
        cmd += ["--restart", "unless-stopped"]
    for key, value in profile["env"].items():
        cmd += ["-e", f"{key}={value}"]
    for mapping in profile["ports"]:
        host, rest = mapping.split(":", 1)
        if port and host.isdigit():
            mapping = f"{port}:{rest}"
        cmd += ["-p", mapping]
    cmd += ["-v", f"{data_path}:{profile['data']}", profile["image"]]

    out, err, code = run(cmd, timeout=120, shell=False)
    return {"ok": code == 0, "server": server, "msg": out or err or "Server oprettet"}


def setup_status():
    svc_path = Path("/etc/systemd/system/byteforge.service")
    return {
        "docker_ok": docker_available(),
        "service_ok": svc_path.exists(),
        "port": PORT,
        "base_dir": str(BASE_DIR),
    }


def install_docker_system():
    if docker_available():
        return {"ok": True, "msg": "Docker er allerede installeret"}
    if PLATFORM == "Windows":
        return {"ok": False, "msg": "Download Docker Desktop fra https://www.docker.com/products/docker-desktop og genstart ByteForge."}
    if PLATFORM == "Darwin":
        out, err, code = run("brew install --cask docker 2>&1", timeout=300, shell=True)
        return {"ok": code == 0, "msg": (out or err or "Docker installeret via Homebrew. Start Docker.app manuelt.")[-2000:]}
    distro_out, _, _ = run("cat /etc/os-release 2>/dev/null")
    distro = ""
    for line in distro_out.splitlines():
        if line.startswith("ID="):
            distro = line.split("=", 1)[1].strip().strip('"').lower()
    if distro in ("arch", "manjaro", "endeavouros", "garuda"):
        out, err, code = run("pacman -Sy --noconfirm docker && systemctl enable --now docker", timeout=300, shell=True)
    elif distro in ("ubuntu", "debian", "linuxmint", "pop"):
        out, err, code = run("apt-get update -qq && apt-get install -y docker.io && systemctl enable --now docker", timeout=300, shell=True)
    elif distro in ("fedora", "rhel", "centos", "rocky"):
        out, err, code = run("dnf install -y docker && systemctl enable --now docker", timeout=300, shell=True)
    else:
        out, err, code = run("curl -fsSL https://get.docker.com | sh && systemctl enable --now docker", timeout=300, shell=True)
    return {"ok": code == 0, "msg": (out or err or "Docker installeret")[-2000:]}


def install_service_system():
    script_path = Path(__file__).resolve()
    python_path = shutil.which("python3") or shutil.which("python") or "python3"

    if PLATFORM == "Linux":
        unit = "\n".join([
            "[Unit]", "Description=ByteForge Platform", "After=network.target docker.service", "Wants=docker.service",
            "", "[Service]", "Type=simple",
            f"ExecStart={python_path} {script_path}", "Restart=always", "RestartSec=5",
            f"Environment=BYTEFORGE_PORT={PORT}",
            "", "[Install]", "WantedBy=multi-user.target", "",
        ])
        try:
            Path("/etc/systemd/system/byteforge.service").write_text(unit)
            run("systemctl daemon-reload && systemctl enable --now byteforge", timeout=20, shell=True)
            return {"ok": True, "msg": f"ByteForge installeret som systemd service på port {PORT}. Starter automatisk ved boot."}
        except Exception as exc:
            return {"ok": False, "msg": str(exc)}

    if PLATFORM == "Darwin":
        plist_path = Path("/Library/LaunchDaemons/com.byteforge.server.plist")
        plist = "\n".join([
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">',
            '<plist version="1.0"><dict>',
            "  <key>Label</key><string>com.byteforge.server</string>",
            "  <key>ProgramArguments</key>",
            f"  <array><string>{python_path}</string><string>{script_path}</string></array>",
            "  <key>EnvironmentVariables</key>",
            f"  <dict><key>BYTEFORGE_PORT</key><string>{PORT}</string></dict>",
            "  <key>RunAtLoad</key><true/>",
            "  <key>KeepAlive</key><true/>",
            "</dict></plist>",
        ])
        try:
            plist_path.write_text(plist)
            run(f"launchctl load -w {plist_path}", timeout=10, shell=True)
            return {"ok": True, "msg": f"ByteForge installeret som LaunchDaemon på port {PORT}. Starter ved boot."}
        except Exception as exc:
            return {"ok": False, "msg": str(exc)}

    if PLATFORM == "Windows":
        try:
            bat_dir = Path(os.environ.get("APPDATA", str(Path.home()))) / "ByteForge"
            bat_dir.mkdir(exist_ok=True)
            bat_path = bat_dir / "start.bat"
            bat_path.write_text(f'@echo off\nset BYTEFORGE_PORT={PORT}\n"{python_path}" "{script_path}"\n')
            task_cmd = f'schtasks /create /tn "ByteForge" /tr "{bat_path}" /sc onstart /ru SYSTEM /f'
            out, err, code = run(task_cmd, timeout=15, shell=True)
            return {"ok": code == 0, "msg": out or err or "ByteForge tilføjet til Windows Task Scheduler. Starter ved login."}
        except Exception as exc:
            return {"ok": False, "msg": str(exc)}

    return {"ok": False, "msg": f"Service installation ikke understøttet på {PLATFORM}"}


def docker_container_action(container, action):
    if not container:
        return {"ok": False, "msg": "Ingen container angivet"}
    if action == "remove":
        out, err, code = run(["docker", "rm", "-f", container], timeout=15, shell=False)
    elif action in ("start", "stop", "restart"):
        out, err, code = run(["docker", action, container], timeout=30, shell=False)
    else:
        return {"ok": False, "msg": "Ukendt handling"}
    return {"ok": code == 0, "msg": out or err or f"{container} {action}"}


def nas_service_action(action):
    if PLATFORM == "Darwin":
        _, _, code = run(f"nfsd {action} 2>/dev/null", timeout=15, shell=True)
        return {"ok": code == 0, "msg": f"NFS {action} gennemført" if code == 0 else "NFS fejlede"}
    if PLATFORM == "Windows":
        return {"ok": False, "msg": "NFS administration ikke understøttet på Windows"}
    for svc in ("nfs-server", "nfs-kernel-server"):
        _, _, code = run(f"systemctl {action} {svc} 2>/dev/null", timeout=15, shell=True)
        if code == 0:
            return {"ok": True, "msg": f"NFS {action} gennemført"}
    return {"ok": False, "msg": "NFS service ikke fundet"}


def deploy_app(app_id):
    if not docker_available():
        return {"ok": False, "msg": "Docker er ikke tilgængelig. Installer Docker først."}
    profile = PRIVACY_APPS.get(app_id)
    if not profile:
        return {"ok": False, "msg": f"Ukendt app: {app_id}"}
    container = f"byteforge-{app_id}"
    if container_exists(container):
        return {"ok": False, "msg": f"{profile['name']} kører allerede (container: {container})"}
    data_path = SERVER_ROOT / "apps" / app_id
    data_path.mkdir(parents=True, exist_ok=True)
    cmd = ["docker", "run", "-d", "--name", container, "--label", "byteforge.app=true", "--restart", "unless-stopped"]
    for k, v in profile["env"].items():
        cmd += ["-e", f"{k}={v}"]
    for p in profile["ports"]:
        cmd += ["-p", p]
    cmd += ["-v", f"{data_path}:{profile['data']}", profile["image"]]
    out, err, code = run(cmd, timeout=120, shell=False)
    host_port = profile["ports"][0].split(":")[0] if profile["ports"] else ""
    url = f" → http://localhost:{host_port}" if host_port else ""
    return {"ok": code == 0, "msg": (out or err or f"{profile['name']} deployet") + url}


def safe_path(scope, rel=""):
    roots = {
        "public": PUBLIC_ROOT,
        "private": PRIVATE_ROOT,
        "shared": SHARED_ROOT,
        "servers": SERVER_ROOT,
    }
    config = load_config()
    for server in config["servers"]:
        roots[server["id"]] = Path(server["path"])
    root = roots.get(scope, PUBLIC_ROOT).resolve()
    target = (root / rel.lstrip("/")).resolve()
    if target != root and root not in target.parents:
        raise ValueError("Ugyldig sti")
    return root, target


def list_files(scope, rel=""):
    _, target = safe_path(scope, rel)
    target.mkdir(parents=True, exist_ok=True)
    if not target.is_dir():
        return {"path": rel, "items": []}
    items = []
    for entry in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        stat = entry.stat()
        items.append({
            "name": entry.name,
            "type": "folder" if entry.is_dir() else "file",
            "size": stat.st_size,
            "modified": int(stat.st_mtime),
        })
    return {"path": rel, "items": items}


def search_files(scope, query):
    root, _ = safe_path(scope, "")
    matches = []
    if not query:
        return matches
    for path in root.rglob("*"):
        if query.lower() in path.name.lower():
            matches.append({"path": str(path.relative_to(root)), "type": "folder" if path.is_dir() else "file"})
        if len(matches) >= 100:
            break
    return matches


def file_action(body):
    action = body.get("action")
    scope = body.get("scope", "public")
    path = body.get("path", "")
    _, target = safe_path(scope, path)
    if action == "mkdir":
        target.mkdir(parents=True, exist_ok=True)
        return {"ok": True, "msg": "Mappe oprettet"}
    if action == "delete":
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        return {"ok": True, "msg": "Slettet"}
    if action == "move":
        _, dest = safe_path(scope, body.get("dest", ""))
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(target), str(dest))
        return {"ok": True, "msg": "Flyttet"}
    if action == "search":
        return {"ok": True, "matches": search_files(scope, body.get("query", ""))}
    return {"ok": False, "msg": "Ukendt filhandling"}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send_json(self, data, code=200):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, mime):
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", len(data))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        try:
            if path == "/api/system":
                self.send_json(get_system())
            elif path == "/api/disks":
                self.send_json(get_disks())
            elif path == "/api/raid":
                self.send_json(get_raid())
            elif path == "/api/nas":
                self.send_json(get_nas())
            elif path == "/api/minecraft":
                self.send_json(legacy_minecraft())
            elif path == "/api/docker":
                self.send_json(get_docker())
            elif path == "/api/hardware":
                self.send_json(get_hardware())
            elif path == "/api/setup":
                self.send_json(setup_status())
            elif path == "/api/game-servers":
                self.send_json({"types": SERVER_TYPES, "servers": get_game_servers(qs.get("logs", ["0"])[0] == "1")})
            elif path == "/api/files":
                self.send_json(list_files(qs.get("scope", ["public"])[0], qs.get("path", [""])[0]))
            elif path == "/api/users":
                data = load_config()
                self.send_json({"users": data["users"], "settings": data["settings"]})
            elif path == "/api/all":
                self.send_json({
                    "system": get_system(),
                    "hardware": get_hardware(),
                    "disks": get_disks(),
                    "raid": get_raid(),
                    "nas": get_nas(),
                    "minecraft": legacy_minecraft(),
                    "docker": get_docker(),
                    "game_servers": get_game_servers(),
                })
            elif path == "/api/metrics/history":
                with _METRICS_LOCK:
                    self.send_json(list(_METRICS_HISTORY))
            elif path == "/api/appstore":
                self.send_json(get_appstore())
            elif path == "/api/background":
                for ext in ("jpg", "jpeg", "png", "gif", "webp"):
                    p = BASE_DIR / f"background.{ext}"
                    if p.exists():
                        self.send_file(p, f"image/{ext}")
                        return
                self.send_json({"error": "No background image set"}, 404)
            elif path in ("/", "/index.html"):
                html_path = Path(__file__).with_name("byteforge-platform.html")
                self.send_file(html_path, "text/html; charset=utf-8")
            else:
                self.send_json({"error": "Not found"}, 404)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 500)

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        ctype = self.headers.get("Content-Type", "")
        try:
            if parsed.path in ("/api/files/upload", "/api/background/upload"):
                raw = self.rfile.read(length)
                message = BytesParser(policy=email_policy).parsebytes(
                    b"Content-Type: " + ctype.encode() + b"\r\n\r\n" + raw
                )
                fields = {}
                file_part = None
                for part in message.iter_parts():
                    name = part.get_param("name", header="content-disposition")
                    filename = part.get_filename()
                    if filename:
                        file_part = part
                    elif name:
                        fields[name] = part.get_content()
                if not file_part:
                    self.send_json({"ok": False, "msg": "Ingen fil modtaget"}, 400)
                    return
                if parsed.path == "/api/background/upload":
                    ext = Path(file_part.get_filename()).suffix.lower() or ".jpg"
                    for old_ext in ("jpg", "jpeg", "png", "gif", "webp"):
                        old_p = BASE_DIR / f"background.{old_ext}"
                        if old_p.exists():
                            old_p.unlink()
                    dest = BASE_DIR / f"background{ext}"
                    with dest.open("wb") as f:
                        f.write(file_part.get_payload(decode=True) or b"")
                    cfg = load_config()
                    cfg["settings"]["background"] = "/api/background"
                    save_config(cfg)
                    self.send_json({"ok": True, "url": "/api/background"})
                    return
                scope = fields.get("scope", "public")
                rel = fields.get("path", "")
                _, folder = safe_path(scope, rel)
                folder.mkdir(parents=True, exist_ok=True)
                dest = folder / Path(file_part.get_filename()).name
                with dest.open("wb") as f:
                    f.write(file_part.get_payload(decode=True) or b"")
                self.send_json({"ok": True, "msg": "Upload færdig", "file": dest.name})
                return

            body = json.loads(self.rfile.read(length) or "{}")
            if parsed.path == "/api/minecraft/action":
                self.send_json(game_action("minecraft-main", body.get("action", "")))
            elif parsed.path == "/api/game-servers/action":
                self.send_json(game_action(body.get("id", ""), body.get("action", "")))
            elif parsed.path == "/api/game-servers/create":
                self.send_json(create_game_server(body))
            elif parsed.path == "/api/files/action":
                self.send_json(file_action(body))
            elif parsed.path == "/api/settings":
                data = load_config()
                data["settings"].update(body)
                save_config(data)
                self.send_json({"ok": True, "settings": data["settings"]})
            elif parsed.path == "/api/setup/docker":
                self.send_json(install_docker_system())
            elif parsed.path == "/api/setup/service":
                self.send_json(install_service_system())
            elif parsed.path == "/api/docker/action":
                self.send_json(docker_container_action(body.get("container", ""), body.get("action", "")))
            elif parsed.path == "/api/nas/action":
                self.send_json(nas_service_action(body.get("action", "restart")))
            elif parsed.path == "/api/apps/deploy":
                self.send_json(deploy_app(body.get("app", "")))
            elif parsed.path == "/api/appstore/install":
                self.send_json(appstore_install(body.get("app", "")))
            elif parsed.path == "/api/appstore/uninstall":
                self.send_json(appstore_uninstall(body.get("app", "")))
            elif parsed.path == "/api/terminal/exec":
                self.send_json(exec_command(body.get("cmd", "")))
            else:
                self.send_json({"error": "Not found"}, 404)
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, 500)


if __name__ == "__main__":
    ensure_dirs()
    threading.Thread(target=_metrics_collector, daemon=True).start()
    print("\033[38;5;208m")
    print("  ByteForge Platform starter på port", PORT)
    print("  Data:", BASE_DIR)
    print("\033[0m")
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stoppet.")
