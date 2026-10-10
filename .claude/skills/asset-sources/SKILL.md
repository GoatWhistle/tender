---
name: asset-sources
description: Where icons, country flags and company logos come from and how to add them offline — icons from the product icon set (lucide), flags only from flag-icons, third-party brand logos only from theSVG — plus the ban on arrow, check, cross and pointer characters, em dashes and dot separators in UI and slides. Use when a screen, slide or README needs an icon, a flag, a partner or technology logo, or text contains → ✓ ✗ ▶ — · — «иконка», «флаг», «логотип компании», «лого партнёров», "flag", "brand logo", "icon".
---

# Icons, flags, logos

Every visual symbol is a real vector asset in the product style, stored in the repo and working
offline. Characters that imitate icons are not used.

## Characters that never appear in UI or slides

| Instead of | Use |
| --- | --- |
| `→ ← ↑ ↓ ⇒ ➜ ↗` | `Icon` `arrow-right`, `arrow-left`, `chevron-right`, `arrow-up-right` |
| `✓ ✔ ✅` | `Icon` `check` or `StatusBadge` with its icon |
| `✗ ✕ ✖ ❌` | `Icon` `x` (only inside `CloseButton`) or `StatusBadge` |
| `▶ ► ▸ ◀` | `Icon` `play`, `chevron-right`, `chevron-left` |
| `—` anywhere, `·` and `•` as separators, ` \| ` | A colon, a comma, a new sentence, or separate elements with `gap` |
| Emoji | `Icon` |

The frontend check `symbol-glyphs` (with `text-separators` and `no-emoji`) and the deck build fail on
them. A short `–` stays allowed only in numeric ranges.

## Icons

- Frontend: the `Icon` component in `src/shared/ui`, names from `lucide-react`; one concept, one icon.
- Deck and README assets: the same lucide icon as inline SVG (24×24 viewBox, `stroke="currentColor"`,
  the product stroke width), copied from the lucide source of the installed version.

## Country flags: flag-icons

Source: [flag-icons](https://github.com/lipis/flag-icons) (npm `flag-icons`, MIT). Files:
`node_modules/flag-icons/flags/4x3/<code>.svg` and `flags/1x1/<code>.svg`, where `<code>` is the
ISO 3166-1 alpha-2 code in lower case (`ru`, `gb`, `us`).

- Frontend: `npm install flag-icons --silent`, a `Flag` component in `src/shared/ui` that imports
  the needed files as assets (`import ru from "flag-icons/flags/4x3/ru.svg"`), renders `<img>` with
  `alt` from the dictionary, fixed 4:3 or 1:1 box, radius from tokens. Do not import the full
  `flag-icons.css`: it pulls every flag.
- Deck: copy the needed SVGs to `presentation/src/img/flags/`; the build inlines them.
- A language is not a country: the language switch shows the language name, a flag only when the
  task asks for it.
- No emoji flags, no CDN links, no hand-drawn flags.

## Company and technology logos: theSVG

Source: [theSVG](https://thesvg.org) (brand SVGs from Simple Icons, svgl and lobe-icons; code MIT,
logos belong to their trademark holders).

| Need | How |
| --- | --- |
| Find the slug | `curl -s https://thesvg.org/api/registry.json`, filter on `slug`, `title`, `aliases`, `categories`; or `npx @thesvg/cli search "<name>"` |
| Get the file | `npx @thesvg/cli add <slug>` or download `https://thesvg.org/icons/<slug>/<variant>.svg` (mirror: `https://cdn.jsdelivr.net/gh/glincker/thesvg@main/public/icons/<slug>/<variant>.svg`) |
| Pick the variant | `default` (always), `mono`, `light`, `dark`, `wordmark`, `wordmarkLight`, `wordmarkDark`: `light`/`dark` per theme, `mono` when logos sit in a row and must not compete with the product accent |
| Check the licence | the per-icon `license` field in `https://cdn.jsdelivr.net/gh/glincker/thesvg@main/src/data/icons.json`; "Fair Use" means no open licence found |

- Store downloaded files in the repo: frontend `src/shared/ui/brand-logos/<slug>.<variant>.svg`,
  deck `presentation/src/img/logos/`, README assets next to `presentation/readme/`. Never hotlink.
- Use a logo only to name a real integration, data source, partner or the tech stack; never imply
  endorsement. Keep the logo's own colors or the `mono` variant; do not recolor it to the product
  accent.

Done when every symbol on the screen or slide is an `Icon`, a flag-icons file or a theSVG file in the
repo, and the checks pass.
