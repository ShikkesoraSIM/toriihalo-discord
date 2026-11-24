# ToriiHalo Score Browser Preview

Deployed to the existing ToriiHalo application on 2026-11-24 at the owner's
request. Only the score cog and browser were overlaid on its existing production
image. Identity, configuration, moderation and economy were preserved.
No Bathbot code or assets were copied. The separate preview launcher below is
optional for future development, not required to use /rs on ToriiHalo.

## Features

- `/rs` and the existing `/recent` show a score browser.
- Previous/next, position indicator, list/detail toggle and score link.
- Only the command author can navigate. Controls expire after three minutes.
- PP is the value returned by Torii, not a local recalculation.
- Mod settings include rate changes and Difficulty Adjust values.
- Stars, BPM and CS/AR/OD/HP are explicitly marked NM/base values.
- Missing PP or judgements display `--`, not a made-up zero.
- Score navigation uses one fetched snapshot, with no API calls per click.
- Missing map metadata has a five-minute, 256-entry cache and a concurrency cap
  of three. A metadata failure does not prevent displaying the score.

Direct replay attachments, persona dropdowns, compare, tracking and public
invitations are later work. You can already query a persona by its Torii user ID.
The score link opens the website, where replay downloads use the viewer's login.

## Isolated Discord Test

1. Create a NEW application/bot at https://discord.com/developers/applications.
   Do not reuse the production bot token or application.
2. Fill the local `.env.preview`: `DISCORD_PREVIEW_TOKEN`, the test server's
   `DISCORD_PREVIEW_GUILD_ID`, and Torii public API OAuth client credentials.
   This file is ignored by Git. Never post tokens in chat or commit them.
3. Invite that application with `bot` and `applications.commands` scopes. It only
   needs View Channels, Send Messages and Embed Links. No Administrator, member
   intent or message-content intent is needed for this preview.
4. From this repository directory:

```powershell
python -m bot.preview_stats --check
python -m bot.preview_stats
```

The launcher registers commands only in the specified test server, opens its own
`data/halo-preview.sqlite3`, and loads only `OsuStatsCog`. It never loads staff
alerts, moderation, economy, production linking, or production command sync.

Try `/rs user:<Torii username or profile ID>`, with `mode`, `include_fails` and
`limit` as optional fields. The test database has no linked accounts, so provide
`user` explicitly. Mention-prefix commands also work: `@PreviewBot rs Player`.
The existing production prefix is still `t!`; it has not been changed to `<`.

Test previous/next, list pages, multiple modes, a persona ID, no recent plays,
failed plays, a score without PP, someone else's button click, and timeout.

## Checks

```powershell
python -m pytest
```

Discord rendering and real API authentication still require a live preview test.
Before public invitations, audit command permissions/guild isolation, add
per-guild settings and shared API rate controls, and review replay access.

