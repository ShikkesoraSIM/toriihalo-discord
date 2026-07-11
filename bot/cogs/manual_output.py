import logging
import discord
from discord.ext import commands

logger = logging.getLogger(__name__)

DOCS_DATA = {
    "title": "**__Official Documentation__**",
    "color": 16711935,
    "fields": [
        {
            "name": "*Quick Access Links:*",
            "value": (
                "~ [*Official Website Homepage*](https://lazer.shikkesora.com/) ~\n"
                "~ [*How To Connect To Torii*](https://lazer.shikkesora.com/how-to-join) ~\n"
                "~ [*Your Profile Dashboard*](https://lazer.shikkesora.com/profile) ~\n"
                "~ [*Ranking Leaderboard*](https://lazer.shikkesora.com/rankings) ~\n"
                "~ [*Discord Server*](https://discord.com/invite/fZXsZFT5Xv) ~\n"
                "~ [*Server Status*](https://lazer-api.shikkesora.com/status) ~\n"
                "~ [*Our Wiki*](https://lazer.shikkesora.com/wiki/rules) ~\n"
                "~ [*Support Torii*](https://ko-fi.com/toriiserver) ~\n\n"
                "**__Documentation Sections:__**\n"
                "• *Links will generate automatically after running `t!updatedocs`.*\n\n"
                "***We are not affiliated with, endorsed by, or supported by ppy Pty Ltd, peppy, "
                "or the osu! development team.***"
            ),
            "inline": False
        }
    ]
}

RULES_DATA = {
    "title": "📜 **__Server Rules__**",
    "description": (
        "*The Short Version*\n"
        "*Play in good faith and you are fine. You really do not need to memorize this page.*\n\n"
        "**__Most Important Rule: Good Faith__**\n"
        "If you play fair and you are not trying to abuse anything, you will never have a problem on Torii, "
        "whether or not you have read a single rule below. And if something ever feels wrong, broken, or "
        "like it should not be possible, take that as your cue to report it. That is genuinely how this "
        "works. The rest of the page is just detail."
    ),
    "color": 16711935,
    "fields": [
        {
            "name": "__1. Respect & Conduct__",
            "value": (
                "**1.1.** Be respectful. Harassment, severe insults, discrimination, doxxing, threats and targeted abuse are not allowed.\n"
                "**1.2.** Do not impersonate staff or other players.\n"
                "**1.3.** Keep chat usable. No spam, and no advertising other servers."
            ),
            "inline": False
        },
        {
            "name": "__2. Accounts__",
            "value": (
                "**2.1.** One account per person. Using alternate accounts for an advantage, for ban evasion, or to manipulate rankings is prohibited.\n"
                "**2.2.** No account sharing. You are responsible for everything that happens on your account.\n"
                "**2.3.** Ban or suspension evasion (making or using other accounts to get around a sanction) may lead to an immediate permanent ban.\n"
                "**2.4.** No buying, selling, trading or boosting accounts."
            ),
            "inline": False
        },
        {
            "name": "__3. Cheating & Exploits__",
            "value": (
                "**3.1.** No cheat tools, unauthorized client manipulation, bug abuse, or score manipulation of any kind.\n"
                "**3.2.** Do not tamper with replays, scores or mods before they reach the server.\n"
                "**3.3.** Confirmed cheating gets you banned."
            ),
            "inline": False
        },
        {
            "name": "__4. Maps & Farming__",
            "value": (
                "On Torii, unranked and graveyard maps give pp, and submitted maps are ranked right away. "
                "That also means a broken or abusable map can pay out unfair pp.\n\n"
                "**4.1.** Abusing anything in bad faith for unfair gain is bannable. That covers broken or abusable maps, pp farms, bugs and exploits, not one specific case.\n"
                "**4.2.** If you find something abusable (a map, a bug, an exploit), report it. Hiding it so you can farm it quietly is the bad-faith part, and that is what gets you in trouble.\n"
                "**4.3.** Staff can disqualify abused maps and the scores set on them.\n\n"
                "*Found something broken? Report it. Reporting is always the safe move. Quietly farming it is not.*"
            ),
            "inline": False
        },
        {
            "name": "__5. Profile Content__",
            "value": (
                "**5.1.** If your avatar or banner is NSFW or suggestive and it is not flagged as NSFW, you will get a warning.\n"
                "**5.2.** Illegal or extreme content is strictly prohibited and may result in immediate, severe sanctions."
            ),
            "inline": False
        },
        {
            "name": "__6. Enforcement & Appeals__",
            "value": (
                "There is no rigid strike count. Staff use their judgement. Acting in bad faith (cheating, abusing something on purpose, evading a ban) gets you banned, sometimes after a single heads-up and sometimes not. Usually the first time someone abuses something without reporting it, they get one warning that it cannot happen again. If it happens again, that is it.\n\n"
                "Staff can also restrict an account as a precaution while they look into something, with no notice and no explanation up front. If that happens, you will notice the next time you try to log in. Come talk to us in Discord and we will explain.\n\n"
                "**6.1.** Bans and restrictions are always a manual staff decision. Nothing auto-bans you.\n"
                "**6.2.** If you are restricted, open a ticket in the Discord to ask about it or appeal.\n"
                "**6.3.** Lying or destroying evidence while staff look into something only makes it worse.\n\n"
                "**Not sure about something?**\n"
                "If a rule here is unclear or clashes with what the client actually does, ask in Discord."
            ),
            "inline": False
        }
    ]
}

FEATURES_INTRO_DATA = {
    "title": "✨ **__Features__**",
    "description": "*Torii is a custom osu!lazer build, so it carries a pile of things stock osu! does not. Here is what is in it.*",
    "color": 16711935
}

GAMEPLAY_DATA = {
    "title": "🎯 **__Gameplay & pp__**",
    "color": 16711935,
    "fields": [
        {
            "name": "Torii pp (pp-dev)",
            "value": "Torii ranks your plays with its own server-side pp system instead of the standard one. There is nothing to switch on, it just applies while you are online and connected to Torii.",
            "inline": False
        },
        {
            "name": "Mania Sunny rework",
            "value": "osu!mania star rating is calculated with the Sunny rework instead of stock lazer's mania algorithm, so every mania map's difficulty here comes from it.",
            "inline": False
        },
        {
            "name": "Confirm Retry/Quit",
            "value": "After about 60 seconds into a map, Retry and Quit want a second click within 5 seconds so a stray press does not throw away a long run. Continue is never gated. `Settings > Gameplay > Torii > Gameplay`, off by default.",
            "inline": False
        },
        {
            "name": "Mid-map break skip",
            "value": "A SKIP button during breaks fast-forwards to the end of one without touching your score, since breaks have no notes. Press Space or click it; by default it needs a second press within 2.5s. Single-press is an option in `Settings > Gameplay > Torii > Gameplay`.",
            "inline": False
        }
    ]
}

PERFORMANCE_DATA = {
    "title": "⚡ **__Performance__**",
    "color": 16711935,
    "fields": [
        {
            "name": "Potato Mode",
            "value": "A low-end preset ('Potato mode', `Settings > Torii > Graphics`) that strips almost every effect: triangles, beat-sync pulsing, storyboards, blur, hit lighting, kiai flashes, fountains, parallax, seasonal backgrounds, auras and cursor trails, and switches to the legacy audio engine. It reads once at startup and leaves your own graphics settings alone, so it restarts the game.",
            "inline": False
        },
        {
            "name": "Thread rate (Hz)",
            "value": "Sets how fast the input, audio and update threads run: 500, 1000, 2000, 4000 or 8000 Hz. Higher suits a high-polling mouse but costs CPU, and 2000 is the default. In `Settings > Torii > Graphics` (and `Graphics > Renderer`), applies instantly. Weaker machines start lower on their own.",
            "inline": False
        },
        {
            "name": "Dangerous thread uncap",
            "value": "The experimental Unlimited frame limiter is stock lazer; what Torii adds is a checkbox ('I am stupid, I ignore warnings and want no limits', `Settings > Graphics > Renderer`) that also uncaps the update, input and audio threads, not just rendering. It can cause audio pops and heat, and Torii greys it out on Deferred renderers where it would leak memory and crash.",
            "inline": False
        },
        {
            "name": "Low-latency audio (Oboe)",
            "value": "Android only (`Settings > Torii > Android`). Routes audio through Google's Oboe library for much lower latency, roughly 15 to 30 ms on supported devices, and falls back to OpenSL ES on older phones. Applies instantly, and turning it off is a safe escape hatch.",
            "inline": False
        }
    ]
}

CLIENT_QOL_DATA = {
    "title": "🧳 **__Client & Quality of Life__**",
    "color": 16711935,
    "fields": [
        {
            "name": "Daily Briefing",
            "value": "On login, a card comparing this session to your last: global and country rank, pp, recalc gains and losses on your top scores, unread chat, and snipe and leaderboard events. Reopen or refresh it in `Settings > Torii > Briefing`.",
            "inline": False
        },
        {
            "name": "Recalculation replay",
            "value": "Re-shows the per-score pp gains and losses from the last server-side mass recalc, each top play listed as old pp to new pp. `Settings > Torii > Briefing`, 'Replay last recalc'.",
            "inline": False
        },
        {
            "name": "Legacy song select",
            "value": "Makes song select look like osu!stable: the skinnable stable footer, with the modern filter bar and info wedges hidden. `Settings > Torii > Song Select`.",
            "inline": False
        },
        {
            "name": "Legacy footer",
            "value": "Just the stable-style footer over the normal lazer song select. `Settings > Torii > Song Select`, and only changeable while full legacy song select is off.",
            "inline": False
        },
        {
            "name": "Unslanted song select",
            "value": "Re-renders the slanted song-select panels as straight rectangles. 'Strictly vertical UI (no slant)' in `Settings > Torii > Song Select`. Takes effect next time you enter song select.",
            "inline": False
        },
        {
            "name": "Auto-hide toolbar",
            "value": "Hides the top toolbar and reveals it when the cursor reaches the top edge of the screen, then tucks it away after about 1.5s. `Settings > Torii > Menus`.",
            "inline": False
        },
        {
            "name": "Key debounce",
            "value": "Drops a gameplay key press that fires too soon after that same key's last release, filtering chatter from rapid-trigger or hall-effect keyboards and worn switches. `Settings > Input`, 'Filter double-taps', with a threshold slider (15ms to start). Gameplay keys only, never typing.",
            "inline": False
        },
        {
            "name": "Migration wizard",
            "value": "On first launch it finds an existing osu!lazer data folder and offers to link to it so you reuse your maps, skins, scores and collections right away, or keep Torii portable. Linking needs a restart.",
            "inline": False
        },
        {
            "name": "Data-source switch",
            "value": "Switch the client's data between its own portable Torii folder and a linked osu!lazer one. `Settings > Torii`, 'Manage Torii data source'; applies after a restart. Ships pointed at the portable folder.",
            "inline": False
        },
        {
            "name": "Restriction notice",
            "value": "If your account is restricted, you get a panel explaining the reason and whether or when it lifts, with a Discord button to appeal, instead of just bouncing off the login form.",
            "inline": False
        },
        {
            "name": "NEW badges",
            "value": "A small NEW tag on a setting Torii just added, so it is easy to find. It clears for good after you use that control three times.",
            "inline": False
        }
    ]
}

SOCIAL_PROFILE_DATA = {
    "title": "👥 **__Social & Profile__**",
    "color": 16711935,
    "fields": [
        {
            "name": "Live server pulse",
            "value": "A toolbar pill showing how many people are playing right now, with a dot that pulses and flashes when someone submits a score. Click it for plays per minute, online counts, a sparkline, the top map and live plays. Toggle under `Settings > Torii > Menus`.",
            "inline": False
        },
        {
            "name": "Torii / Torii Nova badge",
            "value": "Online users on a verified Torii build get a small badge by their name: vermillion 'torii' for stable, amber 'nova' for the preview stream, plus a platform icon when the server knows their OS. Hover reads 'Playing on Torii client'.",
            "inline": False
        },
        {
            "name": "NSFW media preference",
            "value": "`Settings > Torii > Menus`, 'Show NSFW profile media': whether you see avatars and covers from profiles flagged NSFW. It saves to your account so it matches the website, and the server swaps flagged images for placeholders.",
            "inline": False
        }
    ]
}

CUSTOMIZATION_DATA = {
    "title": "🎨 **__Customization & Skinning__**",
    "color": 16711935,
    "fields": [
        {
            "name": "Custom UI hue",
            "value": "Retint the whole client to any hue with the 'Custom UI hue' toggle and 'UI hue' picker in `Settings > Torii > Menus`. It covers menus, overlays and the settings panel together.",
            "inline": False
        },
        {
            "name": "Custom accent UI hue",
            "value": "A second hue just for highlights, hovers and accents ('Separate accent hue', `Settings > Torii > Menus`). Locked until you own the unlock; clicking the LOCKED pill opens the store.",
            "inline": False
        },
        {
            "name": "Grayscale UI theme",
            "value": "A 'Grayscale by fsyori' option in the 'UI theme' dropdown (`Settings > Skin`, or `Torii > Menus`) that strips saturation from the UI and mounts a stable-style stats panel in song select. Restarts the game. Chrome only, not gameplay skins.",
            "inline": False
        },
        {
            "name": "Per-combo-colour hitcircles",
            "value": "On legacy skins, ship hitcircle1.png, hitcircle2.png and so on (up to 8) next to the normal hitcircle.png and the circle and number art changes with the current combo colour. Skins without the numbered files look exactly like stock lazer.",
            "inline": False
        },
        {
            "name": "Torii skin components",
            "value": "In the skin layout editor, Torii's own pieces are gathered into a 'Torii Exclusive Components' section pinned at the top, each marked with a torii-gate icon and a vermillion name.",
            "inline": False
        },
        {
            "name": "Mania ratio counter",
            "value": "A skinnable mania ratio counter you add from the skin editor: toggle and edit the header label, pick the font and weight, set the value and label colours, choose 1 to 3 decimals, and turn the per-judgement flash on or off.",
            "inline": False
        },
        {
            "name": "Skin pinning",
            "value": "Pin a skin in `Settings > Skin` and it sorts to the top of the dropdown with a heart prefix. Turn on 'Cycle through favourites only' and the normal skin-cycle keybind steps through just your pinned skins instead of every skin you have.",
            "inline": False
        },
        {
            "name": "Cursor-size preview",
            "value": "Change cursor size anywhere with `Ctrl+Shift+scroll` or `Ctrl+Shift+Plus` / `Ctrl+Shift+Minus`, and a small overlay shows your actual cursor at the new size with a readout like 1.20x, fading out after about 1.4s.",
            "inline": False
        }
    ]
}

COSMETICS_DATA = {
    "title": "🪙 **__Cosmetics & Currency__**",
    "description": "⚠️ **The economy is still being tuned**\n*The points and the store work, but the numbers are placeholder and the whole economy gets wiped before the public launch, so whatever you pile up now will not carry over. Exact amounts are on the Points & Economy page.*",
    "color": 16711935,
    "fields": [
        {"name": "Torii points", "value": "An in-game currency you only earn by playing, never with real money. Every earn and spend is written to a server-side ledger you open from the coin pill in the toolbar.", "inline": False},
        {"name": "Top play reward", "value": "Setting a new personal best on a map is the main way points come in. The amount, the daily cap and a top-play-history requirement are decided server-side. Exact numbers are on the Points & Economy page.", "inline": False},
        {"name": "Daily play bonus + streak", "value": "Your first pass each day gives a small bonus, and a day-over-day streak adds more up to a cap, resetting if you skip a day. It shows up as a 'Daily play' entry.", "inline": False},
        {"name": "Daily Challenge reward", "value": "Completing the daily challenge pays out points once per day, granted server-side.", "inline": False},
        {"name": "Medal reward", "value": "Earning a new medal grants a few points, shown as a 'Medal' entry and rolled into the post-play card.", "inline": False},
        {"name": "Cosmetic Store", "value": "Open it from the Store icon in the toolbar. The Store tab has a daily featured rotation that is the same for everyone with a countdown; the inventory tab holds what you own and equips with one click. Every item has a live preview before you buy.", "inline": False},
        {"name": "Cursor trails", "value": "The main store item: 36 of them across Basic, Special and Premium tiers, from solid and gradient ribbons to particle effects (stars, hearts, sakura, snow, flames, galaxy dust) and connected ribbons (comet, rainbow, neon, nebula). An equipped trail replaces your skin's trail.", "inline": False},
        {"name": "Username colours", "value": "6 solid and 4 gradient name colours you buy and equip. Your name then shows in that colour anywhere the client tints usernames.", "inline": False},
        {"name": "Role name colours", "value": "If you are in a server group with a colour (admin, supporter, and so on) you get it free, drawn as a soft glow around the letters. These are never sold.", "inline": False},
        {"name": "User auras", "value": "A particle effect behind your name everywhere it appears. Most come from a role or group; if you have more than one, pick which to show in `Settings > Torii (User Aura)`, or turn the effect off there.", "inline": False},
        {"name": "Buyable & seasonal auras", "value": "The Summer 2026 aura is the one currently on sale (3000 points) and can also be earned through the summer event. Stardust sits in the gallery but is not on sale right now. Every other aura is earned.", "inline": False},
        {"name": "Trail customisation unlock", "value": "A one-time 100-point unlock that turns on length, size and density sliders for every cursor trail you own. Until then a trail uses its default look.", "inline": False},
        {"name": "Custom accent-hue unlock", "value": "A one-time 5000-point unlock for the second UI accent hue, which touches highlights and accents only. It used to be a supporter perk.", "inline": False},
        {"name": "Redeem & access codes", "value": "Staff hand out codes that grant points and sometimes a cosmetic. Redeem one with the 'Redeem' pill in the store header. Each code has a use limit set when it is made.", "inline": False},
        {"name": "Gifts", "value": "Staff can send you points and/or a cosmetic with a note. It shows up after a play, back at the menu, as a wrapped present you click to open.", "inline": False},
        {"name": "Points pill + earn summary", "value": "The coin pill in the toolbar is your balance, and clicking it opens your history. After a play, everything you earned is combined into one card with a per-source breakdown and your new balance.", "inline": False},
        {"name": "Points history", "value": "Every earn and spend, newest first, with the reason, the amount (green for gains, red for spends) and your running balance. It loads 50 at a time.", "inline": False}
    ]
}

SCORING_INTRO_DATA = {
    "title": "ℹ️ **__Scoring & pp__**",
    "description": "*This is the page you end up on when a score gives 0pp. Leaderboards go by total score, and pp is a separate thing that a few specific mods and settings switch off. Everything below is what the server actually enforces.*",
    "color": 16711935,
    "fields": [
        {
            "name": "How a score earns pp",
            "value": (
                "pp is decided entirely on the server. The client cannot grant or change it. When a score is submitted, "
                "the server runs a fixed set of gates in order. If a score fails any gate it earns 0pp, but it is still recorded.\n\n"
                "**The gates, in the order they run:**\n"
                "• Flashlight settings check (osu! standard, Relax and Autopilot only). This runs first, before anything else.\n"
                "• The score must have passed, the map must be ranked for pp, and every mod in the play must be allowed for pp.\n"
                "• Relax and Autopilot accuracy floor.\n"
                "• pp is calculated."
            ),
            "inline": False
        }
    ]
}

PP_MECHANICS_DATA = {
    "title": "⚙️ **__pp System Gates__**",
    "color": 16711935,
    "fields": [
        {
            "name": "Relax and Autopilot need 75% accuracy",
            "value": (
                "A Relax or Autopilot score below 75% accuracy earns 0pp. This is a hard cutoff checked before pp is calculated, "
                "so it applies no matter how high the map's star rating or your score is.\n\n"
                "The modes it covers: osu! Relax, Taiko Relax, Catch Relax and osu! Autopilot. There is no Taiko or Catch Autopilot; "
                "Autopilot only exists for osu! standard.\n\n"
                "75.0% or higher earns pp normally. 74.9% or lower earns nothing. The in-game message is: \"Relax and Autopilot scores need at least 75% accuracy to earn pp.\""
            ),
            "inline": False
        },
        {
            "name": "Flashlight must use default settings",
            "value": (
                "On osu! standard, Relax and Autopilot, Flashlight only earns pp on its default settings. Change any of these and the whole score earns 0pp:\n"
                "• Size, default 1.0\n"
                "• Follow delay, default 1.0\n"
                "• Combo-based size, default on\n\n"
                "Any change past a tiny rounding tolerance, or turning combo-based size off, zeroes the play. The message is: \"Only default Flashlight settings earn pp, set size, delay and combo-based size back to their defaults.\""
            ),
            "inline": False
        },
        {
            "name": "Ruleset Flashlight Variances",
            "value": (
                "Taiko, Catch and Mania apply the same idea through the mod whitelist: Flashlight is only allowed at default size with combo-based size in its default state for that ruleset. Mania's default for combo-based size is off, which is the opposite of standard."
            ),
            "inline": False
        }
    ]
}

MOD_REGULATIONS_DATA = {
    "title": "🚫 **__Mod Regulations & Reworks__**",
    "color": 16711935,
    "fields": [
        {
            "name": "Mods that never earn pp",
            "value": (
                "These bans are enforced in code and cannot be loosened by config:\n"
                "• **Adaptive Speed (AS):** osu! standard / Relax / Autopilot only. Always 0pp in that family.\n"
                "• **Magnetised (MG):** osu! standard / Relax / Autopilot only. Always 0pp in that family.\n"
                "• **Bloom (BM):** Every ruleset. Its pp calculation is broken, so it is off server-wide.\n"
                "• **Wind Down (WD):** Every ruleset. It ramps song speed down over the map, so the effective rate ends up below base while difficulty is still measured at base rate. Banned everywhere. *Wind Up (WU) stays allowed because it only makes a play harder.*\n"
                "• **Mania Difficulty Adjust (DA):** With Overall Difficulty 6 or lower. Always 0pp.\n"
                "• **Mania Invert (IN):** Always 0pp."
            ),
            "inline": False
        },
        {
            "name": "Adaptive Speed Code Exception",
            "value": (
                "One catch with Adaptive Speed: the hard ban only covers osu! standard, Relax and Autopilot. For Taiko and Mania it is not hard-banned in code, so whether it earns pp there comes down to the deployed mod whitelist."
            ),
            "inline": False
        },
        {
            "name": "Mania difficulty uses the Sunny rework",
            "value": (
                "osu!mania star rating and pp use the Sunny rework, the same model the Torii client runs in-game. "
                "So the pp the client previews for a mania play is the pp the server gives it, one to one. "
                "Sunny reads dense jack and long-note patterns more accurately than stock lazer, so those maps are rated fairly instead of being blown out of proportion."
            ),
            "inline": False
        },
        {
            "name": "Mania No Release earns reduced pp",
            "value": (
                "No Release (NR) in osu!mania stays ranked, but its pp is cut by 15% (you keep 85%). "
                "NR removes the need to time the end of hold notes, so long notes only need a press, which makes the map a bit easier while its difficulty is still measured at full value. "
                "A light cut keeps it fair without banning it. It was 30% before mania moved to the Sunny model; now that difficulty is measured properly, 15% is enough."
            ),
            "inline": False
        }
    ]
}

PLAY_MODIFIERS_DATA = {
    "title": "⏱️ **__Play Modifiers & Penalties__**",
    "color": 16711935,
    "fields": [
        {
            "name": "Pausing during a play reduces pp",
            "value": (
                "Pausing mid-play lets you rest through the hard parts, so each pause takes a bite out of the pp. "
                "It is 7% per pause and it compounds: one pause keeps 93%, three keep about 80%, seven keep about 60%. "
                "There is no free first pause and no floor, and it applies to every mode. Skipping a break with the in-game skip button is not a pause and does not count."
            ),
            "inline": False
        },
        {
            "name": "Custom rate and Easy variants are allowed",
            "value": (
                "Torii ranks custom-rate plays on purpose. These mods skip the usual fixed-value whitelist, so any speed setting still earns pp:\n"
                "• Double Time (DT) / Nightcore (NC)\n"
                "• Half Time (HT) / Daycore (DC)\n"
                "• Easy (EZ)\n\n"
                "A custom 1.3x DT, a 0.6x HT, a 1.7x NC and so on all earn pp here, and the pp calculator uses the real rate you played at. Standard osu! lazer locks these to fixed values; Torii does not.\n\n"
                "For reference, the values they would otherwise be pinned to are HT and DC at 0.75x, DT and NC at 1.5x, and Easy at 2 extra lives (Taiko Easy has no lives lock)."
            ),
            "inline": False
        }
    ]
}

MAP_STATUS_MEDALS_DATA = {
    "title": "🗺️ **__Beatmap Status & Medals__**",
    "color": 16711935,
    "fields": [
        {
            "name": "Beatmap Status & Overrides",
            "value": (
                "Torii can make non-ranked maps count for pp and leaderboards through server overrides. Medals do not follow those overrides. This is the part people get wrong, so here it is in full.\n\n"
                "The real osu! statuses are Graveyard, WIP, Pending, Ranked, Approved, Qualified and Loved.\n\n"
                "• **pp and ranked score:** A map earns pp if its real status is Ranked or Approved, or if the \"all maps give pp\" override is on. With that override on, Graveyard, WIP, Pending, Qualified and Loved maps give pp and ranked score too. The mods still have to be pp-eligible.\n\n"
                "• **Leaderboards:** A map shows on leaderboards if its real status is Ranked, Approved, Qualified or Loved, or if the \"all maps leaderboard\" override is on."
            ),
            "inline": False
        },
        {
            "name": "How Medals & Status Gates Work",
            "value": (
                "Medals always check the map’s real status and ignore the overrides completely. So a Graveyard or WIP map that Torii made scoreable and pp-eligible still gives no status-gated medals.\n\n"
                "**The gates per medal type:**\n"
                "• Skill, FC and combo medals: real status must be Ranked or Approved.\n"
                "• Mod-intro medals: real status must be Ranked, Approved, Qualified or Loved.\n\n"
                "*Note: Medals are also never awarded on locally-uploaded maps.*\n\n"
                "**Grind & Joke Medals:**\n"
                "A lot of grind and joke medals (total hits, key counts, playcount, daily-challenge streaks, most hush-hush secrets) have no status gate at all, so those can unlock on any map including Graveyard, same as on official osu!. The \"no medals on non-ranked maps\" line only applies to the skill and mod medals above."
            ),
            "inline": False
        }
    ]
}

SYSTEM_LOGIC_DATA = {
    "title": "📊 **__System Logic & Leaderboards__**",
    "color": 16711935,
    "fields": [
        {
            "name": "When a play counts toward playtime",
            "value": (
                "A passed score always counts toward playtime.\n\n"
                "A failed score only counts if all three are true:\n"
                "• The play lasted longer than 8 seconds, and\n"
                "• Total score is at least 5000, and\n"
                "• You hit at least the smaller of (10% of the map's objects) or (20 objects).\n\n"
                "A failed play that falls short of that does not add to your playtime."
            ),
            "inline": False
        },
        {
            "name": "Failed plays keep their submitted grade",
            "value": (
                "The server does not recompute the letter grade. It keeps whatever rank the client sent, so a failed play is recorded as an F. "
                "Failed scores are still saved, but they are left out of pp and out of your best-score lists, which only count passed plays."
            ),
            "inline": False
        },
        {
            "name": "Leaderboards",
            "value": (
                "Per-map leaderboards:\n"
                "• The no-mod Global board merges base, Relax and Autopilot scores into one board for that map. Any other board (a specific mod filter, or a non-global board) shows only that exact mode.\n"
                "• The Friends board shows scores from people on your friends list, and the Country board shows scores from your country. If one is empty, nobody in that group has a score on the map yet.\n"
                "• The Team board shows your team.\n\n"
                "Restricted users are hidden from every leaderboard and every ranking."
            ),
            "inline": False
        },
        {
            "name": "Auto-banned maps",
            "value": (
                "A map whose structure crosses safety limits is auto-banned, and after that every score on it earns 0pp. "
                "The limits are structural, for example more than 500000 hit objects (Taiko more than 30000), extreme note density, a slider repeat count over 5000 or control points outside the playfield, heavily overlapping 2B-style objects, or a map spanning more than 24 hours. "
                "Once a map is banned it stays banned for all future scores."
            ),
            "inline": False
        }
    ]
}

ECONOMY_DATA = {
    "title": "🪙 **__Points & Economy__**",
    "description": (
        "*How you earn Torii points and what you can do with them, spelled out exactly so there is nothing to argue about.*\n\n"
        "> ⚠️ **About these numbers**\n"
        "> The amounts here are the current values. They are still being tuned and can change, and the whole economy "
        "(every balance included) is reset before the public launch. So today’s numbers are not promises, and old "
        "amounts will not carry over."
    ),
    "color": 16711935,
    "fields": [
        {
            "name": "__What points are__",
            "value": (
                "Points are earned by playing. There is no way to buy them with money, and paying never grants or speeds them up.\n\n"
                "Every point change is written to a ledger, which is the real record. The number on your profile is a running "
                "balance kept in sync with that ledger. Each earning event is keyed so it cannot pay out twice."
            ),
            "inline": False
        },
        {
            "name": "__Top plays__",
            "value": (
                "A top play is a score that becomes your new pp-best on a map, either your first pp score there or a higher-pp "
                "score than your previous best on it.\n\n"
                "• **Reward:** 100 points per new top play.\n"
                "• **Requirement:** You need at least 50 top plays in that mode before any new top play starts paying. This stops "
                "fresh accounts from farming their first scores.\n"
                "• **Daily cap:** At most 5 top-play awards per day, rolling over at UTC midnight.\n\n"
                "So the most you can get from top plays in a day is 500 points, and only once you are past the 50 top-play mark."
            ),
            "inline": False
        },
        {
            "name": "__Daily play and streak__",
            "value": (
                "Your first passed play of the day (UTC) pays a daily bonus, and a streak builds the more consecutive days you show up.\n\n"
                "• **Base:** 15 points.\n"
                "• **Streak bonus:** +5 points per consecutive day on top of the base, capped at +30.\n\n"
                "So day 1 is 15, day 2 is 20, day 3 is 25, and it tops out at 45 per day from day 7 onward. The streak is read from "
                "the previous day’s award; miss a day and it resets to 1. It pays once per UTC day, and only a passed score triggers it."
            ),
            "inline": False
        },
        {
            "name": "__Daily challenge__",
            "value": (
                "Completing the daily challenge pays a flat 30 points, once per day (UTC). The score has to pass.\n\n"
                "This is separate from your daily-challenge streak counter. That streak does not add points; only the flat 30 is "
                "paid for completing the challenge."
            ),
            "inline": False
        },
        {
            "name": "__Medals__",
            "value": (
                "Each new medal you unlock pays 10 points.\n\n"
                "Medals do not unlock on locally-uploaded maps, so those pay nothing. Which medals need a ranked status is "
                "covered on the Scoring & pp page."
            ),
            "inline": False
        }
    ]
}

COSMETIC_STORE_DATA = {
    "title": "🏪 **__Rewards & Cosmetic Store__**",
    "color": 16711935,
    "fields": [
        {
            "name": "__Redeem codes__",
            "value": (
                "Staff can issue codes that grant points, and sometimes a cosmetic. Redeem one from your points page.\n\n"
                "• Each code can be redeemed once per user. That is a hard guarantee, not a soft check.\n"
                "• A code can expire and has a maximum number of total uses across everyone.\n"
                "• Redeeming is rate-limited to 10 attempts per 10 minutes.\n\n"
                "Codes look like `TORII-` followed by 6 characters. A code's value can be anything up to 1,000,000 points, "
                "and a value of 0 is used for codes that only grant a cosmetic."
            ),
            "inline": False
        },
        {
            "name": "__Gifts__",
            "value": (
                "Staff can send gifts. A gift can carry points, a cosmetic, or both. You claim it from your gifts, and a "
                "gift can only be claimed once. If it carries points, claiming it credits them."
            ),
            "inline": False
        },
        {
            "name": "__Spending: the cosmetic store__",
            "value": (
                "The store is currently client-side only. The server does not have a purchase system yet, so buying a "
                "cosmetic deducts from a balance tracked in the client and saves what you own in the client, not on the server. "
                "Everything here is placeholder and not final.\n\n"
                "**One-time unlocks (placeholder prices):**\n"
                "• Adjustable trail length and size: 100 points. Turns on the length and size sliders for every trail you own.\n"
                "• Adjustable trail density: 100 points.\n"
                "• Custom accent hue: 5000 points. A one-time unlock for a second UI accent colour, which used to be supporter-only.\n\n"
                "**What you can buy:**\n"
                "Cursor trails (around three dozen, tiered Basic, Special and Premium), name colours (solids and gradients; role "
                "and group colours are earned, not sold), and the Summer aura. The shop rotates its featured picks once per day by UTC. "
                "Exact per-item prices are shown in the store and are still placeholder, so they are not pinned down here."
            ),
            "inline": False
        }
    ]
}

TORIIHALO_DATA = {
    "title": "🤖 **__ToriiHalo__**",
    "description": "*ToriiHalo is the bot that messages you in-game. When a score gives 0pp or your account status changes, it is the one that tells you.*",
    "color": 16711935,
    "fields": [
        {
            "name": "__When a score gives 0pp__",
            "value": (
                "If a play submits but earns no pp, ToriiHalo PMs you the reason. The three you might see:\n\n"
                "• **TORIIHALO SAYS**\n"
                "  *\"Your score gave 0pp! Your accuracy was 71.4%. Relax and Autopilot scores need at least 75% accuracy to earn pp.\"*\n\n"
                "• **TORIIHALO SAYS**\n"
                "  *\"Your score gave 0pp! You changed Flashlight settings. Only default Flashlight settings earn pp, set size, delay and combo-based size back to their defaults.\"*\n\n"
                "• **TORIIHALO SAYS**\n"
                "  *\"Your score gave 0pp, it did not meet the requirements to earn pp.\"*\n\n"
                "The full list of what zeroes pp is on the Scoring & pp page."
            ),
            "inline": False
        },
        {
            "name": "__When your account is restricted__",
            "value": (
                "If your account gets restricted, ToriiHalo sends a PM, and it is re-sent every time you reconnect so you do not miss it:\n\n"
                "• **TORIIHALO SAYS**\n"
                "  *\"You are restricted, please wait 1 month before your appeal through a ticket in the discord server.\"*\n\n"
                "What a restriction means and how to appeal is on the Restrictions & Appeals page."
            ),
            "inline": False
        }
    ]
}

RESTRICTIONS_APPEALS_DATA = {
    "title": "🚫 **__Restrictions & Appeals__**",
    "description": "*A restriction is staff pressing pause on an account. Here is what it does, what you will see, and how to get it lifted.*",
    "color": 16711935,
    "fields": [
        {
            "name": "__What a restriction means__",
            "value": (
                "• A restricted account cannot log in or submit scores, and is hidden from every leaderboard.\n"
                "• Restrictions are always a manual staff action. Nothing on Torii auto-restricts you.\n"
                "• It is not always permanent and not always a punishment. Sometimes it is precautionary while staff look into something.\n"
                "• If your activity looks suspicious, staff can restrict the account while they investigate, without prior notice and without owing an explanation up front.\n\n"
                "*There is no fixed strike count. A restriction is a staff call, and how enforcement actually works is detailed on the Rules page.*"
            ),
            "inline": False
        },
        {
            "name": "__What you will see__",
            "value": (
                "When you try to log in on a restricted account, the client shows a full-screen notice titled \"Your account is restricted\", with the reason if there is one, and this line:\n\n"
                "• **TORII CLIENT SAYS**\n"
                "  *\"This can be a safety measure or simply while staff look into something, and is not necessarily permanent. If you think this is a mistake or want to appeal, reach out to the admins on our Discord.\"*\n\n"
                "You will also get this PM, re-sent on every reconnect:\n\n"
                "• **TORIIHALO SAYS**\n"
                "  *\"You are restricted, please wait 1 month before your appeal through a ticket in the discord server.\"*"
            ),
            "inline": False
        },
        {
            "name": "__How to appeal__",
            "value": (
                "**1.** Join the Torii Discord and open a ticket.\n"
                "**2.** Be honest and specific. Say what you think happened and why you believe the restriction is wrong or should be lifted.\n"
                "**3.** Give it the wait. Appeals are reviewed by a person, not instantly. The standard ask is to wait about a month before appealing.\n\n"
                "> ⚠️ **One account, one appeal path**\n"
                "> Do not make a new account to get around a restriction. Ban evasion is itself bannable and it will not help your appeal. The ticket is the way back."
            ),
            "inline": False
        }
    ]
}

FAQ_DATA = {
    "title": "❓ **__FAQ__**",
    "description": "*Short answers to the questions that come up most. Each one links to the full version.*",
    "color": 16711935,
    "fields": [
        {
            "name": "Why did my score give 0pp?",
            "value": "Usually one of three things: a Relax/Autopilot score under 75% accuracy, a Flashlight score with non-default settings, or a mod that does not earn pp. Full list on the Scoring & pp page. The score still submitted and still ranks by total score, it just gave no pp.",
            "inline": False
        },
        {
            "name": "My friends (or country) leaderboard is empty. Is it broken?",
            "value": "No, it is not broken. Those boards only show scores from your friends, or from your country, so an empty one just means nobody in that group has set a score on that map yet.",
            "inline": False
        },
        {
            "name": "Do unranked / graveyard maps count?",
            "value": "Yes. On Torii, unranked, graveyard and loved maps give pp and have leaderboards. On official osu! standard those give no pp at all, so this is a real difference.",
            "inline": False
        },
        {
            "name": "Are Relax and Autopilot ranked?",
            "value": "Yes, both are fully ranked here, each with its own leaderboards.",
            "inline": False
        },
        {
            "name": "Can I use custom Double Time / Half Time rates?",
            "value": "Yes. Custom rate variants of DT, NC, HT, DC and Easy still earn pp on Torii, unlike official osu!.",
            "inline": False
        },
        {
            "name": "Did I get auto-banned?",
            "value": "No. Nothing on Torii auto-bans you and no score is auto-rejected. Every restriction is a manual staff decision. See Restrictions & Appeals.",
            "inline": False
        },
        {
            "name": "How do I appeal a restriction?",
            "value": "Open a ticket in the Discord and wait about a month before appealing. Details on the Restrictions & Appeals page.",
            "inline": False
        },
        {
            "name": "I found a map giving crazy pp. It looks broken.",
            "value": "Report it in Discord instead of farming it. Because unranked maps give pp here, a broken map can hand out absurd pp, and knowingly farming one without reporting it is bannable.",
            "inline": False
        }
    ]
}


class Docs(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.first_docs_msg = None
        self.sent_messages = {}

    @commands.command(name="postdocs")
    @commands.has_permissions(administrator=True)
    async def postdocs(self, ctx: commands.Context) -> None:
        self.first_docs_msg = None
        self.sent_messages.clear()

        embed_datasets = [
            ("docs", DOCS_DATA),
            ("rules", RULES_DATA),
            ("features", FEATURES_INTRO_DATA),
            ("gameplay", GAMEPLAY_DATA),
            ("performance", PERFORMANCE_DATA),
            ("qol", CLIENT_QOL_DATA),
            ("social", SOCIAL_PROFILE_DATA),
            ("customization", CUSTOMIZATION_DATA),
            ("cosmetics", COSMETICS_DATA),
            ("scoring", SCORING_INTRO_DATA),
            ("mechanics", PP_MECHANICS_DATA),
            ("regulations", MOD_REGULATIONS_DATA),
            ("modifiers", PLAY_MODIFIERS_DATA),
            ("status", MAP_STATUS_MEDALS_DATA),
            ("logic", SYSTEM_LOGIC_DATA),
            ("economy", ECONOMY_DATA),
            ("store", COSMETIC_STORE_DATA),
            ("halo", TORIIHALO_DATA),
            ("appeals", RESTRICTIONS_APPEALS_DATA),
            ("faq", FAQ_DATA)
        ]

        for key, data_dict in embed_datasets:
            fields = data_dict.get("fields", [])
            field_chunks = [fields[i:i + 6] for i in range(0, len(fields), 6)]

            if not field_chunks:
                embed = discord.Embed.from_dict(data_dict)
                embed.set_footer(text="Torii - Forged in Shikke's Dojo", icon_url="https://lazer.shikkesora.com/image/logos/logo@2x.png")
                msg = await ctx.send(embed=embed)

                if key == "docs" and not self.first_docs_msg:
                    self.first_docs_msg = msg
                elif key not in self.sent_messages:
                    self.sent_messages[key] = msg
                continue

            for idx, chunk in enumerate(field_chunks):
                chunk_data = data_dict.copy()
                chunk_data["fields"] = chunk

                if len(field_chunks) > 1:
                    chunk_data["title"] = f"{data_dict.get('title', '')} (Part {idx + 1})"

                embed = discord.Embed.from_dict(chunk_data)
                embed.set_footer(
                    text="Torii - Forged in Shikke's Dojo",
                    icon_url="https://lazer.shikkesora.com/image/logos/logo@2x.png"
                )
                msg = await ctx.send(embed=embed)

                if idx == 0:
                    if key == "docs" and not self.first_docs_msg:
                        self.first_docs_msg = msg
                    elif key not in self.sent_messages:
                        self.sent_messages[key] = msg

        try:
            await ctx.message.delete()
        except discord.Forbidden:
            logger.warning("Bot lacks 'Manage Messages' permission to delete the trigger command.")
        except discord.HTTPException as e:
            logger.error(f"Failed to delete message: {e}")

    @commands.command(name="updatedocs")
    @commands.has_permissions(administrator=True)
    async def updatedocs(self, ctx: commands.Context) -> None:
        if not self.first_docs_msg or not self.sent_messages:
            await ctx.send("❌ No document posts detected in memory! Please run `t!postdocs` first.", delete_after=10)
            return

        server_id = ctx.guild.id
        channel_id = ctx.channel.id

        m_rules = self.sent_messages.get("rules").id
        m_features = self.sent_messages.get("features").id
        m_scoring = self.sent_messages.get("scoring").id
        m_economy = self.sent_messages.get("economy").id
        m_halo = self.sent_messages.get("halo").id
        m_appeals = self.sent_messages.get("appeals").id
        m_faq = self.sent_messages.get("faq").id

        quick_access = (
            "~ [*Official Website Homepage*](https://lazer.shikkesora.com/) ~\n"
            "~ [*How To Connect To Torii*](https://lazer.shikkesora.com/how-to-join) ~\n"
            "~ [*Your Profile Dashboard*](https://lazer.shikkesora.com/profile) ~\n"
            "~ [*Ranking Leaderboard*](https://lazer.shikkesora.com/rankings) ~\n"
            "~ [*Discord Server*](https://discord.com/invite/fZXsZFT5Xv) ~\n"
            "~ [*Server Status*](https://lazer-api.shikkesora.com/status) ~\n"
            "~ [*Our Wiki*](https://lazer.shikkesora.com/wiki/rules) ~\n"
            "~ [*Support Torii*](https://ko-fi.com/toriiserver) ~"
        )

        doc_sections = (
            f"• [*Server Rules*](https://discord.com/channels/{server_id}/{channel_id}/{m_rules})\n"
            f"• [*Features*](https://discord.com/channels/{server_id}/{channel_id}/{m_features})\n"
            f"• [*Scoring & pp*](https://discord.com/channels/{server_id}/{channel_id}/{m_scoring})\n"
            f"• [*Points & Economy*](https://discord.com/channels/{server_id}/{channel_id}/{m_economy})\n"
            f"• [*ToriiHalo*](https://discord.com/channels/{server_id}/{channel_id}/{m_halo})\n"
            f"• [*Restrictions & Appeals*](https://discord.com/channels/{server_id}/{channel_id}/{m_appeals})\n"
            f"• [*FAQ*](https://discord.com/channels/{server_id}/{channel_id}/{m_faq})\n\n"
            "***We are not affiliated with, endorsed by, or supported by ppy Pty Ltd, peppy, "
            "or the osu! development team.***"
        )

        updated_docs = DOCS_DATA.copy()
        updated_docs["fields"] = [
            {
                "name": "*Quick Access Links:*",
                "value": quick_access,
                "inline": False
            },
            {
                "name": "*Navigation:*",
                "value": doc_sections,
                "inline": False
            }
        ]

        embed = discord.Embed.from_dict(updated_docs)
        embed.set_footer(text="Torii - Forged in Shikke's Dojo", icon_url="https://lazer.shikkesora.com/image/logos/logo@2x.png")
        await self.first_docs_msg.edit(embed=embed)

        await ctx.send("✅ Navigation links generated and updated successfully!", delete_after=5)

        try:
            await ctx.message.delete()
        except discord.Forbidden:
            logger.warning("Bot lacks 'Manage Messages' permission to delete the trigger command.")
        except discord.HTTPException as e:
            logger.error(f"Failed to delete message: {e}")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Docs(bot))
