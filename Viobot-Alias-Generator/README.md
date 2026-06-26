# Viobot Alias Generator

A single, self-contained web tool for building **Viobot** Discord aliases & embeds
without hand-writing the pseudocode. Pick a template (or start blank), fill in the
fields, drop in dynamic variables, watch the live Discord-style preview, then copy the
exact `!alias create …` / `!palias create …` command and paste it into your server.

It mirrors the **live Viobot alias engine** exactly (actions, embed options, every
variable/function, conditionals, limits), so what you generate is what the bot runs —
no unsupported fields, no surprises.

## Run it

It's one file with no build step and no dependencies.

- **Quickest:** double-click `index.html` (opens via `file://`).
- **Best (clipboard + saved presets fully work):** serve it locally, e.g.
  - Python: `python -m http.server 8090` in this folder → open `http://localhost:8090`
  - Node: `npx serve .`
- Append `?selftest` to the URL (or click the **self-test** button) to run the built-in
  spec-fidelity tests; results print to the browser console (F12).

> On `file://`, the clipboard and `localStorage` can be restricted by the browser. Copy
> falls back to a manual select-and-copy, and presets can be moved with **Export/Import
> (.json)** instead of relying on `localStorage`. Serving over `http://localhost` avoids
> both limitations.

## What it supports (the full DSL)

Everything the bot's `!alias tools` guide documents:

**Commands** — `!alias create <name> help="..." access=modonly|public` (public) and
`!palias create <name> help="..."` (private to the creator).

**Actions** — `say` (a message) and `/embed` (attaches to the preceding `say`, so one
message can carry multiple embeds; multiple `say` blocks = multiple messages).

**Embed options** — `title`, `description` (multi-line), `color` (hex/decimal),
repeatable `field` (`Name|Value` + optional `inline`), `footer`, `image`, `thumbnail`.
*(Author / url / timestamp / footer-icon are intentionally **not** offered — the engine
ignores them, so we don't emit them.)*

**Variables & functions** (insert into any text field via the **`$ ▾`** button) —
- Arguments: `$0`, `$1`…`$N`, `$slice(start,end)`
- User: `$n` `$u` `$id` (and `$n($1)` `$u($1)` `$id($1)` for a user passed as an argument)
- Channel: `$c` `$cid` `$channel`
- Conditionals: `$if(cond,then)`, `$ifelse(cond,then,else)` (use `null` for empty)
- Tests: `$is_url(x)`, `$is_channel(x)`
- Server variables: `$var(name)`, `$var(name|fallback)` (managed in Discord with `!var`)

These nest freely — e.g. `$if($1,$n($1)) welcome!` or
`$ifelse($is_url($1),$1,No link)` — which is the "dynamic vars inside the alias" power.

**Markdown** — bold/italic/underline/strike/code/code-block/quote/masked-link helpers,
plus channel/user/role mention syntax. (Viobot suppresses pings, so mentions render but
don't notify.)

## Easy mode vs Advanced mode

A toggle in the top bar switches between two views over the **same** alias:

- **Easy (default)** — built so you never touch `$`-syntax:
  - **Start from a goal**: pick a template card (Greet a member, Links, Staff quick-reply, Rules, Warn + reason, Share-a-link) and just reword it.
  - **Inputs**: declare what people type after the command in plain words ("user", "reason"), choose User or Text (and "rest" for multi-word). A live `Usage: !cmd [user] [reason…]` line shows the syntax.
  - **Insert ▾**: a plain-English menu on every field — "👤 Mention them", "👤 Tag <your input>", "📺 this channel", "🏷️ server variable…", "✨ tag them only if given". It writes the correct `$n($1)` / `$slice(1)` / `$var(...)` for you.
  - **＋ If**: a visual conditional — "Only show … when [your input] is a link / was given", with an optional "otherwise" — emits `$if` / `$ifelse`.
- **Advanced** — today's full-power form with the raw `$ ▾` token palette, for anything Easy doesn't cover. Nothing is lost; both modes read/write the identical output.

## Features

- Multi-message, multi-embed builder with reorder/remove on messages, embeds, and fields.
- Variable palette + markdown toolbar on every text field.
- Live, Discord-accurate preview with a **sample-arguments** bar and a **Resolve
  variables** toggle (faithful in-browser port of the engine's `expandAliasVars`).
- Exact paste-ready output (engine quoting/escaping rules) with copy + download.
- Live validation against Discord limits (title 256, description 4096, field name 256 /
  value 1024, footer 2048, ≤25 fields, ≤6000 total, ≤10 embeds) plus name/reserved-word
  and `|`-in-field warnings, and the free-tier 50-alias note.
- **Import / reverse-parse**: paste an existing alias to load it back into the builder.
- **Presets**: starter templates + save/load your own (localStorage + JSON export/import).
- **Cheatsheet**: the same reference Viobot shows with `!alias tools`.

## How it stays accurate

The whole UI is driven by a single in-file `VIOBOT_SPEC` (functions, embed options,
limits, cheatsheet) and the generator/preview/import logic are direct ports of the bot's
`src/utils/aliasEngine.js` (`parseAliasBody`, `expandAliasVars`, `$if`/`$ifelse`/`$slice`,
balanced-paren and top-level comma/pipe splitting). If the bot adds a feature, update
`VIOBOT_SPEC` and the matching branch — the UI follows.

Source of truth: the Viobot bot repo (`src/utils/aliasEngine.js`,
`src/MessageCommands/alias.js` + `palias.js`, `src/utils/aliasLimits.js`,
`src/MessageCommands/var.js`).

## Deploy later (not done yet — local only for now)

When you want it hosted, it follows the same pattern as the other static Haven sites
(e.g. SkyScraper): serve the folder read-only from an nginx container on the Pi.

1. Copy this folder to the Pi (e.g. `~/docker/viobot-alias/`).
2. Mount the **whole folder** read-only into nginx:
   `./viobot-alias/:/usr/share/nginx/html:ro`
3. Either add it as a path on the existing Viobot site (`viobot.havenmap.online/generator`)
   or give it its own subdomain (new Cloudflare DNS record + cert + NPM proxy host).

No build, no compile — just ship `index.html`.
