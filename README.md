# Torii Discord Bot

Bot para Discord orientado a Torii con dos bloques principales:

- Comandos estilo Bathbot para stats de osu! (`/profile`, `/top`, `/recent`, `/score`, `/beatmap`, `/rankings`).
- Comandos estilo OwO para social/economía (`/link`, `/daily`, `/work`, `/coinflip`, `/pay`, `/coins_top`, `/owoify`).

## Features incluidas

- Link de cuenta Discord -> cuenta Torii.
- Embeds de perfil, top plays, recent plays, score por ID/URL, leaderboard de beatmap, rankings globales.
- Economía persistente con SQLite:
  - saldo
  - daily con streak
  - work con cooldown
  - coinflip
  - transferencias (`/pay`)
  - top de monedas
- Comando admin para sincronizar slash commands.
- Dockerfile + ejemplo de compose.

## Requisitos

- Python 3.11+ (recomendado 3.13).
- Un bot de Discord creado en Discord Developer Portal.
- Token API de Torii con acceso `public` para endpoints v2.

## Setup local

```bash
cd torii-discord-bot
cp .env.example .env
```

Editar `.env`:

- `DISCORD_TOKEN`
- `TORII_API_BASE_URL` (default: `https://lazer-api.shikkesora.com`)
- `TORII_WEB_BASE_URL` (default: `https://lazer.shikkesora.com`)
- `TORII_API_TOKEN` **o** (`TORII_OAUTH_CLIENT_ID` + `TORII_OAUTH_CLIENT_SECRET`)

Instalar y correr:

```bash
python -m venv .venv
. .venv/bin/activate  # en Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m bot.main
```

## Wiring de Discord (lo hacés después)

1. En Discord Developer Portal, crear aplicación/bot.
2. Activar `applications.commands` scope al invitarlo.
3. Invitarlo a tu servidor con permisos básicos.
4. Si querés sync instantáneo en un server de test, setear `DISCORD_GUILD_ID`.
5. Correr `/sync` (owner only) o reiniciar el bot.

## Comandos

- Stats:
  - `/profile`
  - `/top`
  - `/recent`
  - `/score`
  - `/beatmap`
  - `/rankings`
- Link:
  - `/link`
  - `/unlink`
  - `/whoami`
- Economy/Fun:
  - `/balance`
  - `/daily`
  - `/work`
  - `/coinflip`
  - `/pay`
  - `/coins_top`
  - `/owoify`
  - `/ping`
- Admin:
  - `/sync`

## Docker

```bash
cd torii-discord-bot
cp .env.example .env
docker compose -f docker-compose.example.yml up --build -d
```

## Seguridad

- Nunca commitear `.env`.
- Usar token bot con privilegios mínimos.
- Usar un token API de Torii dedicado para este bot.
