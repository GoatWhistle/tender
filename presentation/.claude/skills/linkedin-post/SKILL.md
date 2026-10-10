---
name: linkedin-post
description: Make LinkedIn posts about the hackathon project, one per team member, each with its own angle, its own 4–5 images (1080×1350, rendered in the product's design system) and its own text in that person's voice; also a carousel PDF and a feed preview, all checked by `npm run linkedin`. Use when the hackathon asks for a LinkedIn post, social post, or the team wants to share the project — «пост в линкедин», «линкедин пост», «картинки для поста», «пост про проект», "LinkedIn post", "social post", "share on LinkedIn".
---

# LinkedIn posts

Hackathons often require every team member to post. Identical posts from five people look like a
campaign and get skipped; five different angles on the same product look like a team. Each post is
written by one person, about the part they know, with images that show that part.

Files: `social/posts.json` (team, posts, images), `social/<slug>.md` (the post text exactly as it is
pasted), `social/template.html` (ten image layouts in the product tokens), `social/shot.png` (a real
screenshot). Output in `social/out/` (git-ignored): `<slug>/01.png…05.png`, `<slug>/post.txt`,
`<slug>.pdf` (carousel), and `shots/linkedin-<slug>.png`, the post as the feed shows it.

## 1. Inputs

- How many people post, their names, roles, LinkedIn handles, and optionally a square photo each
  (`social/<name>.jpg`, referenced as `photo`). Ask once if unknown.
- From `../context/PLATFORM.md`: required tags, hashtags, mentions, link rules, deadline, language
  (English unless the hackathon is local).
- The story and numbers: the deck plan, `evidence.md`, the README. Nothing new is claimed.
- A real screenshot of the product at its best moment: `social/shot.png` (a frame from
  `npm run video:shots` or the frontend shots).
- The tokens, fonts and mark are already in the deck (`cd ../frontend && npm run tokens:export -- --fonts`).

## 2. Scaffold

```bash
npm run linkedin:init -- --people 4
```

writes `social/posts.json` and one `social/<slug>.md` per person. Angles are assigned in this
order, so N people never repeat until N exceeds five:

| Angle | Who usually writes it | Images |
| --- | --- | --- |
| `idea` | product lead | cover (accent), the problem number, product screen with zoom, how it works, what changes for the user |
| `engineering` | backend or ML | cover, architecture steps, guarantees list, test count (accent), build facts in four numbers |
| `results` | whoever ran the measurements | result number (accent), before and after, four KPIs, where it fails, what the numbers mean |
| `design` | frontend or design | product screen, zoomed detail, the user's path, design principle quote (accent), fewer steps before and after |
| `team` | anyone, often the last to post | team list with photos, lesson quote (accent), what shipped, three lessons, hours from idea to stand |

Reassign angles to fit the people: the author of a post is the person who did that work. Edit
`posts.json` freely: reorder images, change layouts, drop one (four is fine), set `tone`.

## 3. Not copy-paste

The same product seen by different people. Each post differs in three ways, and the check enforces
each of them:

- **Angle and facts.** Each post is about its author's part. Shared between posts: the product
  name, the links, the headline number. Not shared: sentences, hooks, examples, lessons.
  `npm run linkedin` fails when two posts share a sentence of six words or more or open with the same
  five words, and warns when more than a fifth of their five-word phrases match.
- **Images.** Different layouts in a different order, a different first image (the feed shows it
  largest). Identical image sets fail; the same first image warns.
- **Visual variant.** `variant` 1–5 per post, assigned in order by `init`, changes the composition
  slightly while the palette, fonts and mark stay the same: 1 left-aligned, 2 centered with the
  screenshot tilted left, 3 a short accent bar above the title, 4 a large faint mark in the corner
  with the screenshot tilted right, 5 an inner frame. Two posts with the same variant warn.

Write the posts one at a time, each from its own notes, never by editing a copy of another post.

## 4. Images

Layouts in `social/template.html`: `cover`, `number`, `versus`, `steps`, `shot` (with `focus`
for the zoom circle), `kpis`, `quote`, `team`, `list`. No image carries a link, a URL or a QR code:
links live only in the post text, and the check warns on a link in image text. Tones:
none (base surface), `sunken`, `accent` (the product color as background). One accent image per
post, never two in a row across the carousel.

- One idea per image, readable on a phone: the check fails on text under 28 px or text that does
  not fit; long text shrinks to 55% before failing.
- The first image decides whether anyone stops scrolling: the hook in at most six words, or a number
  that surprises, or the product doing the thing.
- Numbers equal `evidence.md`, each with its source line on the image.
- **The site's visual system, exactly.** Colors, fonts, radii and shadows come from the site's
  tokens through `cd ../frontend && npm run tokens:export -- --fonts`; icons from the deck icon set
  (the frontend `Icon` names), the mark from `src/shell.html`. `npm run linkedin` fails when any
  token differs from the site and warns when the site's fonts were not exported. Change the look on
  the site, re-export, re-render; never restyle the images by hand.
- Only the product palette, fonts, icons and mark. No stock photos, no emoji, no em dashes, no arrow
  or check characters; icons come from the deck icon set (`data-icon` names in `src/shell.html`).
- People photos only with their consent; without a photo the avatar shows initials.

## 5. Text

One `social/<slug>.md` per post, exactly as pasted, in the author's own voice (first person, their
role, their part):

- **Hook paragraph** under 200 characters: a concrete claim, number or moment. LinkedIn cuts after
  about 210 characters with "see more"; what is above the cut is the whole ad.
- **Body**: two or three short paragraphs, one or two sentences each. What the product does on one
  real example, the author's part in it, one number with what it was measured on, one honest
  limitation or lesson.
- **Links**: the stand and the repository (or the submission page, if the rules say so); some
  hackathons require them in the post itself.
- **Mentions**: the hackathon and sponsors exactly as `PLATFORM.md` requires, teammates by handle.
- **Hashtags**: three to five, at the end, the required ones first.
- Different words per person: no shared paragraphs between posts, no repeated hook. The five
  angles share the product name, the link and the numbers, nothing else.
- No "excited to share", "thrilled", "game-changer", "delve", "leverage", no emoji bullets, no
  em dashes. The `humanizer` skill passes over every text.

## 6. Render and check

```bash
npm run linkedin
```

Renders every image, the carousel PDF and the feed preview, copies the text to `post.txt` and checks:
the tokens against the site, fit and minimum size on images, glyphs and emoji everywhere, 3000 characters per post, the hook
length, three to five hashtags, clichés, placeholders, four or five images per post, and the
sameness between posts from section 3. Look at
`shots/linkedin-<slug>.png`: the first image and the hook above it must make sense together at feed
size.

## 7. Hand-off

For each person: the folder `social/out/<slug>/` with the images in order and `post.txt`, the
carousel PDF if they prefer a document post, and a suggested posting time (stagger posts by a few
hours or days, the order follows the angles: idea first, team last). Report each post as
`slug, author, images, characters`.

Done when `npm run linkedin` has 0 errors and no placeholders, every number is in `evidence.md`,
and each preview was looked at.
