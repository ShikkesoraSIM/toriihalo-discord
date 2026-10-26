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

## Pings al owner

La regla nativa de AutoMod bloquea la mencion directa antes de publicarla y
aplica 30 minutos. Halo escucha solo la accion de timeout de esa regla: el
segundo aviso pasa a 24 horas y el tercero a ban, sin borrar mensajes anteriores.
Admin, Support y bots quedan exentos. No cambia el guard de los otros staff.

El contador se reinicia tras 30 dias sin nuevos pings. Se guardan los ultimos
50 registros por persona, incluidos errores y resets, en `bot_kv`; un restart
no los borra. La configuracion vive en `owner_ping:config` y arranca desactivada
si no esta preparada. No se importan avisos viejos del guard general.

En el canal privado configurado para los logs:
- `t!pingwarnings @usuario`: consultar contador y los ultimos diez registros.
- `t!pingwarningsclear @usuario`: resetear contador (solo admin/owner), sin
  borrar historial ni levantar un timeout o ban existente.

El usuario recibe el aviso por DM; si tiene los DMs cerrados queda registrado.
AutoMod deja su alerta en staff aunque Halo este caido, pero la escalada y los
contadores requieren que el bot este conectado. El filtro apunta al token de
mencion directa: no cubre la mencion implicita de una respuesta ni los DMs.
Un token literal dentro de codigo/citas tambien puede activar la regla.

El owner recibe otro DM silencioso con el autor, canal, texto bloqueado y la
sancion realmente aplicada. No genera menciones ni push; si el texto es largo
va completo en un adjunto. El envio fallido queda registrado sin cambiar la
sancion ni el contador. El texto no se copia a la base del bot.
