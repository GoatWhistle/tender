import fs from "node:fs"
import path from "node:path"
import { pathToFileURL } from "node:url"
import { ROOT, SRC } from "./assemble.mjs"
import { launch } from "./browser.mjs"
import { siteSync } from "./site-tokens.mjs"

const DIR = path.join(ROOT, "social")
const DATA = path.join(DIR, "posts.json")
const TEMPLATE = path.join(DIR, "template.html")
const OUT = path.join(DIR, "out")
const SHOTS = path.join(ROOT, "shots")
const GLYPHS = /[\u2014\u00b7\u2190-\u21ff\u2794\u279c\u27a1\u2713-\u2718\u2705\u274c\u25b6\u25b8]/u
const EMOJI = /\p{Extended_Pictographic}/u
const CLICHES = ["excited to share", "thrilled to", "game-changer", "game changer", "delve", "revolutionary", "cutting-edge", "seamless", "leverage", "in today's", "proud to announce", "unlock the power"]
const ANGLES = {
  idea: [
    { layout: "cover", tone: "accent", kicker: "{{What we built at the hackathon}}", hook: "{{The problem in four words}}", accent: "{{words}}", text: "{{One sentence: who suffers and what changes}}" },
    { layout: "number", kicker: "{{The problem}}", value: "{{47%}}", title: "{{of what fails today, and for whom}}", source: "{{Source of the number}}" },
    { layout: "shot", title: "{{What the product does, on its own screen}}", badge: "{{Live demo}}", focus: { x: 0.5, y: 0.4, scale: 2 }, source: "{{Real run on demo data}}" },
    { layout: "steps", title: "{{How it works}}", steps: [{ icon: "file", title: "{{Input}}", text: "{{what comes in}}" }, { icon: "cpu", title: "{{Mechanism}}", text: "{{the one idea}}" }, { icon: "check", title: "{{Result}}", text: "{{what the user gets}}" }] },
    { layout: "list", tone: "sunken", title: "{{What changes for the user}}", items: ["{{Change one, concrete}}", "{{Change two}}", "{{Change three}}"] },
  ],
  engineering: [
    { layout: "cover", kicker: "{{How we built it}}", hook: "{{The engineering claim}}", accent: "{{claim}}", text: "{{What makes it trustworthy, in one sentence}}" },
    { layout: "steps", title: "{{Architecture in three parts}}", steps: [{ icon: "monitor", title: "{{Interface}}", text: "{{stack and role}}" }, { icon: "server", title: "{{Service}}", text: "{{stack and role}}" }, { icon: "database", title: "{{Data}}", text: "{{stack and role}}" }, { icon: "lock", title: "{{The check}}", text: "{{what code enforces}}" }] },
    { layout: "list", title: "{{What the code guarantees}}", items: ["{{Invariant one}}", "{{Invariant two}}", "{{Invariant three}}"] },
    { layout: "number", tone: "accent", kicker: "{{Tested}}", value: "{{1 342}}", title: "{{tests, and the bug they caught}}", source: "{{Command that runs them}}" },
    { layout: "kpis", tone: "sunken", title: "{{Built in N hours}}", kpis: [{ value: "{{4}}", label: "{{services in compose}}" }, { value: "{{0}}", label: "{{paid API keys needed}}" }, { value: "{{1.2 s}}", label: "{{median response}}" }, { value: "{{98%}}", label: "{{test coverage of the core}}" }], source: "{{Where each number comes from}}" },
  ],
  results: [
    { layout: "number", tone: "accent", kicker: "{{The result}}", value: "{{20/20}}", title: "{{what was caught, on what sample}}", source: "{{Method, sample, date}}" },
    { layout: "versus", tone: "sunken", title: "{{Same task, before and after}}", before: { label: "{{Today}}", value: "{{2 h}}" }, after: { label: "{{With the product}}", value: "{{40 s}}" }, source: "{{How it was measured}}" },
    { layout: "kpis", title: "{{Measured, not promised}}", kpis: [{ value: "{{0.87}}", label: "{{main metric}}" }, { value: "{{1.2 s}}", label: "{{latency}}" }, { value: "{{0}}", label: "{{paid API calls}}" }, { value: "{{233}}", label: "{{cases in the sample}}" }], source: "{{Sample and date}}" },
    { layout: "list", title: "{{Where it still fails}}", items: ["{{Limitation with a number}}", "{{What we have not measured}}", "{{Next step}}"] },
    { layout: "quote", tone: "sunken", quote: "{{What the numbers mean for the user, in one sentence}}" },
  ],
  design: [
    { layout: "shot", title: "{{The screen the user lives in}}", badge: "{{Product}}", source: "{{What is on screen}}" },
    { layout: "shot", title: "{{The detail that matters}}", badge: "{{Detail}}", focus: { x: 0.6, y: 0.45, scale: 2.4 }, source: "{{Why this detail}}" },
    { layout: "steps", title: "{{The user's path}}", steps: [{ icon: "search", title: "{{Find}}", text: "{{step}}" }, { icon: "sliders", title: "{{Decide}}", text: "{{step}}" }, { icon: "check", title: "{{Done}}", text: "{{step}}" }] },
    { layout: "quote", tone: "accent", quote: "{{The design principle we followed, in one sentence}}" },
    { layout: "versus", tone: "sunken", title: "{{Fewer steps for the same task}}", before: { label: "{{Clicks today}}", value: "{{12}}" }, after: { label: "{{Clicks in the product}}", value: "{{3}}" }, source: "{{How it was counted}}" },
  ],
  team: [
    { layout: "team", title: "{{Who built it}}", source: "{{Hackathon, track, dates}}" },
    { layout: "quote", tone: "accent", quote: "{{What I learned, in one honest sentence}}" },
    { layout: "shot", title: "{{What we shipped in N hours}}", badge: "{{Shipped}}", source: "{{What is on screen}}" },
    { layout: "list", title: "{{Three lessons}}", items: ["{{Lesson one}}", "{{Lesson two}}", "{{Lesson three}}"] },
    { layout: "number", tone: "sunken", kicker: "{{The hackathon}}", value: "{{48 h}}", title: "{{from idea to a working stand}}", source: "{{Hackathon, track, dates}}" },
  ],
}
const ORDER = Object.keys(ANGLES)

const [, , command = "render", ...args] = process.argv
const option = (name) => {
  const index = args.indexOf(`--${name}`)
  return index === -1 ? null : args[index + 1]
}
const rel = (file) => path.relative(ROOT, file).split(path.sep).join("/")

const init = () => {
  const people = Number(option("people") ?? 3)
  if (!Number.isInteger(people) || people < 1 || people > 10) {
    console.error("usage: npm run linkedin:init -- --people 3 [--force]")
    process.exit(2)
  }
  if (fs.existsSync(DATA) && !args.includes("--force")) {
    console.error(`${rel(DATA)} exists, pass --force to overwrite`)
    process.exit(1)
  }
  const team = Array.from({ length: people }, (_, i) => ({ name: `{{Name ${i + 1}}}`, role: `{{Role ${i + 1}}}`, photo: "" }))
  const posts = team.map((_, i) => {
    const angle = ORDER[i % ORDER.length]
    return { slug: `${i + 1}-${angle}`, author: i, angle, variant: (i % 5) + 1, images: ANGLES[angle] }
  })
  const data = { product: "{{PRODUCT}}", hackathon: "{{HACKATHON}}", url: "{{DOMAIN}}", repo: "github.com/{{REPO}}", shot: "shot.png", team, posts }
  fs.writeFileSync(DATA, `${JSON.stringify(data, null, 2)}\n`)
  for (const post of posts) {
    const file = path.join(DIR, `${post.slug}.md`)
    if (!fs.existsSync(file) || args.includes("--force"))
      fs.writeFileSync(file, `{{Hook: a concrete claim from the ${post.angle} angle, under 200 characters}}\n\n{{Two or three short paragraphs in the author's own voice}}\n\n{{Try it: ${data.url}}}\n{{Code: ${data.repo}}}\n\n{{@mentions of the hackathon and sponsors}}\n\n#{{tag}} #{{tag}} #{{tag}}\n`)
  }
  console.log(`${rel(DATA)}: ${people} people, angles ${posts.map((p) => p.angle).join(", ")}; texts in social/<slug>.md`)
}

const textProblems = (slug, text) => {
  const errors = []
  const warnings = []
  const chars = [...text.trim()].length
  if (chars > 3000) errors.push(`${slug}.md: ${chars} characters, LinkedIn allows 3000`)
  const hook = text.trim().split(/\n\s*\n/)[0]
  if ([...hook].length > 210) warnings.push(`${slug}.md: first paragraph is ${[...hook].length} characters, "see more" cuts it near 210`)
  const tags = text.match(/(^|\s)#[\p{L}\p{N}_]+/gu) ?? []
  if (tags.length < 3 || tags.length > 5) warnings.push(`${slug}.md: ${tags.length} hashtags, use three to five`)
  if (GLYPHS.test(text) || EMOJI.test(text)) errors.push(`${slug}.md: em dash, middle dot, arrow, check glyph or emoji`)
  if (text.includes("{{")) warnings.push(`${slug}.md: placeholders left`)
  for (const phrase of CLICHES) if (text.toLowerCase().includes(phrase)) warnings.push(`${slug}.md: cliche "${phrase}"`)
  return { errors, warnings, chars }
}

const words = (text) =>
  text
    .toLowerCase()
    .replace(/https?:\/\/\S+|[@#][\p{L}\p{N}_.-]+|\{\{[^}]*\}\}/gu, " ")
    .split(/[^\p{L}\p{N}]+/u)
    .filter(Boolean)
const shingles = (text) => {
  const list = words(text)
  return new Set(list.slice(0, Math.max(0, list.length - 4)).map((_, i) => list.slice(i, i + 5).join(" ")))
}
const sentences = (text) =>
  text
    .split(/(?<=[.!?])\s+|\n+/)
    .map((line) => words(line).join(" "))
    .filter((line) => line.split(" ").length >= 6)

const sameness = (posts, texts) => {
  const errors = []
  const warnings = []
  for (let i = 0; i < texts.length; i += 1) {
    for (let j = i + 1; j < texts.length; j += 1) {
      const [a, b] = [texts[i], texts[j]]
      if (!words(a.text).length || !words(b.text).length) continue
      const shared = sentences(a.text).filter((line) => sentences(b.text).includes(line))
      if (shared.length) errors.push(`${a.slug} and ${b.slug} share a sentence: "${shared[0].slice(0, 60)}"`)
      const hookA = words(a.text.trim().split(/\n\s*\n/)[0]).slice(0, 5).join(" ")
      const hookB = words(b.text.trim().split(/\n\s*\n/)[0]).slice(0, 5).join(" ")
      if (hookA && hookA === hookB) errors.push(`${a.slug} and ${b.slug} open with the same words: "${hookA}"`)
      const [sa, sb] = [shingles(a.text), shingles(b.text)]
      const common = [...sa].filter((item) => sb.has(item)).length
      const overlap = common / Math.max(1, Math.min(sa.size, sb.size))
      if (overlap > 0.2) warnings.push(`${a.slug} and ${b.slug} overlap by ${Math.round(overlap * 100)}% of their phrases, rewrite one from its own angle`)
    }
  }
  const signature = (post) => post.images.map((image) => `${image.layout}:${image.tone ?? ""}`).join(",")
  for (let i = 0; i < posts.length; i += 1) {
    for (let j = i + 1; j < posts.length; j += 1) {
      const [a, b] = [posts[i], posts[j]]
      if (signature(a) === signature(b)) errors.push(`${a.slug} and ${b.slug} use the same images in the same order`)
      else if (a.images[0] && b.images[0] && a.images[0].layout === b.images[0].layout && (a.images[0].tone ?? "") === (b.images[0].tone ?? "")) warnings.push(`${a.slug} and ${b.slug} start with the same first image, the feed shows it largest`)
      if ((a.variant ?? 1) === (b.variant ?? 1) && posts.length <= 5) warnings.push(`${a.slug} and ${b.slug} share visual variant ${a.variant ?? 1}`)
    }
  }
  return { errors, warnings }
}

const strings = (value) => (typeof value === "string" ? [value] : Array.isArray(value) ? value.flatMap(strings) : value && typeof value === "object" ? Object.values(value).flatMap(strings) : [])

const render = async () => {
  if (!fs.existsSync(DATA)) {
    console.error(`${rel(DATA)} not found, run npm run linkedin:init -- --people 3`)
    process.exit(1)
  }
  const data = JSON.parse(fs.readFileSync(DATA, "utf8"))
  const shell = fs.readFileSync(path.join(SRC, "shell.html"), "utf8")
  const mark = /<template id="brand-mark">\s*([\s\S]*?)\s*<\/template>/.exec(shell)?.[1] ?? ""
  const icons = /<template id="deck-icons">([\s\S]*?)<\/template>/.exec(shell)?.[1] ?? ""
  const file = (ref) => (ref && fs.existsSync(path.resolve(DIR, ref)) ? pathToFileURL(path.resolve(DIR, ref)).href : null)
  const site = siteSync()
  const errors = [...site.errors]
  const warnings = [...site.warnings]
  if (!file(data.shot)) warnings.push(`no screenshot at social/${data.shot}: shot frames render empty`)
  for (const post of data.posts ?? []) {
    if (post.images.some((image) => image.layout === "cta" || /https?:|www\.|\.(com|app|io|dev|ru|org)\b|github/i.test(strings(image).join(" "))))
      warnings.push(`${post.slug}: a link or QR on an image; links live only in the post text`)
  }
  for (const text of strings(data)) {
    if (GLYPHS.test(text) || EMOJI.test(text)) errors.push(`posts.json: em dash, middle dot, glyph or emoji in "${text.slice(0, 50)}"`)
  }

  fs.rmSync(OUT, { recursive: true, force: true })
  fs.mkdirSync(OUT, { recursive: true })
  fs.mkdirSync(SHOTS, { recursive: true })
  const browser = await launch()
  const page = await browser.newPage({ viewport: { width: 1200, height: 1500 }, deviceScaleFactor: 1 })
  await page.goto(pathToFileURL(TEMPLATE).href)
  const summary = []
  const texts = []

  for (const post of data.posts ?? []) {
    const author = data.team?.[post.author] ?? {}
    const team = (data.team ?? []).map((person) => ({ ...person, photo: file(person.photo) }))
    await page.evaluate(
      ({ post, data, author, team, mark, icons, shot }) => {
        const out = document.getElementById("out")
        out.innerHTML = ""
        const set = document.createElement("template")
        set.innerHTML = icons
        const el = (tag, cls, text) => {
          const node = document.createElement(tag)
          if (cls) node.className = cls
          if (text !== undefined) node.textContent = text
          return node
        }
        const icon = (name) => {
          const host = el("span", "ico")
          const svg = set.content.querySelector(`svg[data-icon="${name}"]`)
          if (svg) host.append(svg.cloneNode(true))
          return host
        }
        const initials = (name) =>
          String(name ?? "")
            .replace(/[{}]/g, "")
            .split(/\s+/)
            .filter(Boolean)
            .map((part) => part[0])
            .join("")
            .slice(0, 2)
        const avatar = (host, person) => {
          host.textContent = ""
          if (person.photo) {
            const img = el("img")
            img.src = person.photo
            host.append(img)
          } else host.textContent = initials(person.name)
        }
        for (const spec of post.images) {
          const template = document.getElementById(`layout-${spec.layout}`)
          if (!template) continue
          const node = template.content.firstElementChild.cloneNode(true)
          if (spec.tone) node.classList.add(`is-${spec.tone}`)
          node.classList.add(`v-${post.variant ?? 1}`)
          if ((post.variant ?? 1) === 4) node.append(Object.assign(el("span", "mark watermark"), { innerHTML: mark }))
          const values = {
            product: data.product,
            hackathon: data.hackathon,
            author: [author.name, author.role].filter(Boolean).join(", "),
            name: author.name,
            role: author.role,
            "before-label": spec.before?.label,
            "before-value": spec.before?.value,
            "after-label": spec.after?.label,
            "after-value": spec.after?.value,
            ...spec,
          }
          for (const slot of node.querySelectorAll("[data-slot]")) {
            const key = slot.dataset.slot
            const text = values[key]
            if (text === undefined || text === null || text === "") {
              slot.remove()
              continue
            }
            const accent = (key === "hook" || key === "title" || key === "quote") && spec.accent && String(text).includes(spec.accent) ? spec.accent : null
            if (accent) {
              const at = text.indexOf(accent)
              slot.append(text.slice(0, at), el("em", "", accent), text.slice(at + accent.length))
            } else slot.textContent = text
          }
          for (const list of node.querySelectorAll("[data-list]")) {
            const kind = list.dataset.list
            if (kind === "steps")
              (spec.steps ?? []).forEach((step, i, all) => {
                const tile = el("span", `tile${i === all.length - 1 ? " is-accent" : ""}`)
                tile.append(icon(step.icon))
                const body = el("div")
                body.append(el("b", "", step.title), el("span", "", step.text))
                const li = el("li")
                li.append(tile, body)
                list.append(li)
              })
            if (kind === "kpis")
              for (const kpi of spec.kpis ?? []) {
                const box = el("div", "kpi")
                box.append(el("b", "", kpi.value), el("span", "", kpi.label))
                list.append(box)
              }
            if (kind === "items") for (const item of spec.items ?? []) list.append(el("li", "", item))
            if (kind === "people")
              for (const person of team) {
                const li = el("li")
                const face = el("span", "avatar")
                avatar(face, person)
                const body = el("div")
                body.append(el("b", "", person.name), el("span", "", person.role))
                li.append(face, body)
                list.append(li)
              }
          }
          for (const host of node.querySelectorAll("[data-avatar]")) avatar(host, author)
          for (const frame of node.querySelectorAll("[data-img]")) {
            if (!shot) {
              frame.classList.add("is-empty")
              frame.querySelector("[data-zoom]")?.remove()
              continue
            }
            const img = el("img")
            img.src = shot
            frame.prepend(img)
            const zoom = frame.querySelector("[data-zoom]")
            if (zoom && spec.focus) {
              const inner = el("img")
              inner.src = shot
              inner.dataset.focus = JSON.stringify(spec.focus)
              zoom.append(inner)
            } else zoom?.remove()
          }
          for (const host of node.querySelectorAll("[data-icon]")) {
            const svg = set.content.querySelector(`svg[data-icon="${host.dataset.icon}"]`)
            if (svg && !host.firstElementChild) host.append(svg.cloneNode(true))
          }
          for (const host of node.querySelectorAll("[data-mark]")) host.innerHTML = mark
          out.append(node)
        }
      },
      { post, data, author, team, mark, icons, shot: file(data.shot) },
    )
    await page.evaluate(() => document.fonts.ready)
    await page.evaluate(() => Promise.all([...document.images].map((img) => img.decode().catch(() => null))))
    const found = await page.evaluate(() => {
      for (const img of document.querySelectorAll(".zoom img")) {
        const focus = JSON.parse(img.dataset.focus)
        const frame = img.closest(".frame")
        const size = img.parentElement.clientWidth
        const width = frame.clientWidth * focus.scale
        const height = (width * img.naturalHeight) / Math.max(1, img.naturalWidth)
        img.style.width = `${width}px`
        img.style.left = `${size / 2 - focus.x * width}px`
        img.style.top = `${size / 2 - focus.y * height}px`
      }
      for (const el of document.querySelectorAll("[data-fit]")) {
        const lines = Number(el.dataset.fit)
        let size = Number.parseFloat(getComputedStyle(el).fontSize)
        const min = size * 0.55
        const tooBig = () => el.scrollWidth > el.clientWidth + 1 || el.getBoundingClientRect().height > Number.parseFloat(getComputedStyle(el).lineHeight) * lines + 2
        while (tooBig() && size > min) {
          size -= 2
          el.style.fontSize = `${size}px`
        }
      }
      return [...document.querySelectorAll(".post")].flatMap((card, index) => {
        const box = card.getBoundingClientRect()
        const issues = []
        for (const el of card.querySelectorAll("*")) {
          if (el.closest("svg") || !el.textContent.trim() || el.children.length) continue
          const r = el.getBoundingClientRect()
          const text = el.textContent.trim().slice(0, 40)
          if (el.textContent.includes("{{")) continue
          if (r.right > box.right - 40 || r.bottom > box.bottom - 40 || el.scrollWidth > el.clientWidth + 1) issues.push(`image ${index + 1}: "${text}" does not fit`)
          if (Number.parseFloat(getComputedStyle(el).fontSize) < 28) issues.push(`image ${index + 1}: "${text}" is under 28 px, unreadable in the feed`)
        }
        return issues
      })
    })
    errors.push(...found.map((issue) => `${post.slug}: ${issue}`))

    const dir = path.join(OUT, post.slug)
    fs.mkdirSync(dir, { recursive: true })
    const cards = page.locator(".post")
    const files = []
    for (let i = 0; i < (await cards.count()); i += 1) {
      const target = path.join(dir, `${String(i + 1).padStart(2, "0")}.png`)
      await cards.nth(i).screenshot({ path: target })
      files.push(target)
    }
    if (files.length < 4 || files.length > 5) warnings.push(`${post.slug}: ${files.length} images, LinkedIn posts read best with four or five`)

    const textFile = path.join(DIR, `${post.slug}.md`)
    const text = fs.existsSync(textFile) ? fs.readFileSync(textFile, "utf8") : ""
    if (!text) warnings.push(`${post.slug}: social/${post.slug}.md is missing`)
    texts.push({ slug: post.slug, text })
    const checked = textProblems(post.slug, text)
    errors.push(...checked.errors)
    warnings.push(...checked.warnings)
    fs.writeFileSync(path.join(dir, "post.txt"), text.trim() + "\n")

    const uri = (target) => `data:image/png;base64,${fs.readFileSync(target).toString("base64")}`
    const carousel = await browser.newPage()
    await carousel.setContent(`<!doctype html><style>@page{size:1080px 1350px;margin:0}body{margin:0}img{display:block;width:1080px;height:1350px;break-after:page}</style>${files.map((target) => `<img src="${uri(target)}">`).join("")}`)
    await carousel.pdf({ path: path.join(OUT, `${post.slug}.pdf`), width: "1080px", height: "1350px", printBackground: true })
    await carousel.close()

    const escape = (value) => String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;")
    const lines = escape(text.trim()).split("\n").slice(0, 3).join("<br>")
    const grid = files.length >= 5 ? "five" : files.length === 4 ? "four" : "few"
    const feed = await browser.newPage({ viewport: { width: 640, height: 900 } })
    await feed.setContent(`<!doctype html><meta charset="utf-8"><style>
      body{margin:0;padding:24px;background:#f4f2ee;font:14px/1.45 -apple-system,Segoe UI,sans-serif;color:#1d1d1d}
      article{width:555px;margin:auto;background:#fff;border-radius:8px;box-shadow:0 0 0 1px #e0dfdc}
      header{display:flex;gap:10px;align-items:center;padding:12px 16px}
      header i{width:48px;height:48px;border-radius:50%;background:#d0d0d0}
      header b{display:block}header span{color:#666;font-size:12px}
      p{margin:0;padding:0 16px 12px}p em{color:#666;font-style:normal}
      .g{display:grid;gap:2px}.g img{display:block;width:100%;height:100%;object-fit:cover}
      .g.four{grid-template-columns:repeat(3,1fr);grid-template-rows:440px 180px}.g.four img:first-child{grid-column:1/-1}
      .g.five{grid-template-columns:repeat(6,1fr);grid-template-rows:340px 180px}.g.five img:nth-child(-n+2){grid-column:span 3}.g.five img:nth-child(n+3){grid-column:span 2}.g.five img:nth-child(n+6){display:none}
      .g.few{grid-template-columns:repeat(${Math.max(1, files.length)},1fr)}
    </style><article><header><i></i><span><b>${escape(author.name ?? "")}</b><span>${escape(author.role ?? "")}</span></span></header><p>${lines} <em>...more</em></p><div class="g ${grid}">${files.map((target) => `<img src="${uri(target)}">`).join("")}</div></article>`)
    await feed.screenshot({ path: path.join(SHOTS, `linkedin-${post.slug}.png`), fullPage: true })
    await feed.close()
    summary.push(`${post.slug}: ${files.length} images, ${checked.chars} characters, by ${author.name ?? "?"}`)
  }
  await browser.close()

  errors.push(...sameness(data.posts ?? [], texts).errors)
  warnings.push(...sameness(data.posts ?? [], texts).warnings)
  for (const line of summary) console.log(line)
  console.log(`images and post.txt in social/out/<slug>/, carousel PDF social/out/<slug>.pdf, feed preview shots/linkedin-<slug>.png`)
  for (const message of warnings) console.log(`warn  ${message}`)
  for (const message of errors) console.log(`error ${message}`)
  console.log(`${errors.length} errors, ${warnings.length} warnings`)
  if (errors.length) process.exit(1)
}

if (command === "init") init()
else await render()
