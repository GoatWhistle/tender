import fs from "node:fs"
import path from "node:path"
import { ROOT } from "./assemble.mjs"

export const VIDEO = path.join(ROOT, "video")
export const TEMPLATE = path.join(VIDEO, "template.md")
export const DEFAULTS = { ru: { wpm: 120, sentence: 14 }, en: { wpm: 150, sentence: 16 } }

const SECTION = /^## (\d+[a-z]?)\. (.+), (\d+):(\d{2})[\u2013-](\d+):(\d{2})\s*$/
const FIELD = /^\*\*(Screen|Overlay|Say|Pronounce):\*\*\s*(.*)$/
const STRICT_PHRASES = new Set(["opener", "narration", "thanks"])
const AI_PUNCTUATION = /[\u2014\u00b7\u2190-\u21ff\u2794\u279c\u27a1\u2713-\u2718\u25b6\u25b8]/u
const GATE = /\[after:[^\]]*\]/i
const LOCATION = /`(https?:\/\/[^`\s]+|\/[^`\s]*)`/

export const seconds = (value) => {
  const match = /^(\d+):(\d{2})$/.exec(String(value ?? "").trim())
  if (match) return Number(match[1]) * 60 + Number(match[2])
  const plain = Number(value)
  return Number.isFinite(plain) && String(value ?? "").trim() !== "" ? plain : null
}

export const clock = (total) => {
  const rounded = Math.round(total)
  return `${Math.floor(rounded / 60)}:${String(rounded % 60).padStart(2, "0")}`
}

export const scriptPath = (lang) => path.join(VIDEO, `script.${lang}.md`)

export const scriptLanguages = () =>
  fs.existsSync(VIDEO)
    ? fs
        .readdirSync(VIDEO)
        .map((name) => /^script\.([a-z]{2})\.md$/.exec(name)?.[1])
        .filter(Boolean)
        .sort()
    : []

export const vocabulary = (lang) => {
  const file = path.join(ROOT, "src", "locales", lang, "video.json")
  return fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, "utf8")) : { pause: "pause", phrases: {} }
}

export const parseScript = (text) => {
  const lines = text.replace(/\r/g, "").split("\n")
  const meta = {}
  let index = 0
  if (lines[0] === "---") {
    for (index = 1; index < lines.length && lines[index] !== "---"; index += 1) {
      const pair = /^(\w+):\s*(.*)$/.exec(lines[index])
      if (pair) meta[pair[1]] = pair[2].trim()
    }
    index += 1
  }
  const title = lines.find((line) => line.startsWith("# "))?.slice(2).trim() ?? ""
  const sections = []
  let section = null
  let field = null
  for (; index < lines.length; index += 1) {
    const line = lines[index]
    const head = SECTION.exec(line)
    if (head) {
      section = {
        line: index,
        no: head[1],
        title: head[2],
        start: Number(head[3]) * 60 + Number(head[4]),
        end: Number(head[5]) * 60 + Number(head[6]),
        screen: [],
        overlay: [],
        pronounce: [],
        say: [],
        note: "",
      }
      sections.push(section)
      field = null
    } else if (/^#{1,2} /.test(line)) {
      section = null
      field = null
    } else if (section) {
      const named = FIELD.exec(line)
      if (named) {
        field = named[1].toLowerCase()
        if (field === "say") {
          section.say.push([])
          section.note = named[2].trim()
        } else if (named[2].trim()) section[field].push(named[2].trim())
      } else if (field === "say") {
        const quote = /^>\s?(.*)$/.exec(line)
        if (quote?.[1].trim()) section.say.at(-1).push(quote[1].trim())
      } else if (field && line.trim()) section[field].push(line.trim())
    }
  }
  for (const s of sections) s.say = s.say.filter((block) => block.length > 0)
  return { lines, meta, title, sections }
}

export const settings = (meta, lang) => {
  const base = DEFAULTS[lang] ?? DEFAULTS.en
  return {
    lang,
    wpm: seconds(meta.wpm) ?? base.wpm,
    sentence: seconds(meta.sentence) ?? base.sentence,
    target: seconds(meta.target),
    limit: seconds(meta.limit),
    site: /^https?:\/\//.test(meta.site ?? "") ? meta.site.replace(/\/$/, "") : null,
    theme: meta.theme === "dark" ? "dark" : "light",
  }
}

const pauseMark = (vocab) => new RegExp(`\\[(?:pause|${vocab.pause})\\]`, "giu")

export const words = (text, vocab) =>
  text
    .replace(pauseMark(vocab), " ")
    .split(/\s+/)
    .filter((word) => /[\p{L}\p{N}]/u.test(word)).length

export const lineSeconds = (text, conf, vocab) =>
  (words(text, vocab) / conf.wpm) * 60 + (text.match(pauseMark(vocab))?.length ?? 0) * 1.5

export const location = (section) => LOCATION.exec(section.screen.join(" "))?.[1] ?? null

export const labels = (section) => [...section.screen.join(" ").matchAll(/\u00ab([^\u00bb]+)\u00bb/g)].map((m) => m[1])

export const measure = (section, conf, vocab) => {
  const lines = section.say.flat()
  return {
    words: lines.reduce((sum, line) => sum + words(line, vocab), 0),
    need: lines.reduce((sum, line) => sum + lineSeconds(line, conf, vocab), 0),
    slot: section.end - section.start,
  }
}

const phraseHits = (text, vocab) => {
  const lower = text.toLowerCase()
  return Object.entries(vocab.phrases ?? {}).flatMap(([kind, list]) =>
    list.filter((phrase) => new RegExp(`(^|[^\\p{L}])${phrase.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}($|[^\\p{L}])`, "iu").test(lower)).map((phrase) => ({ kind, phrase })),
  )
}

const timingProblems = (script, conf, report) => {
  const { sections } = script
  sections.forEach((s, i) => {
    const expected = i === 0 ? 0 : sections[i - 1].end
    if (s.start !== expected) report.error(s, `starts at ${clock(s.start)}, expected ${clock(expected)} (run with --retime)`)
    if (s.end <= s.start) report.error(s, "ends before it starts")
  })
  const total = sections.at(-1)?.end ?? 0
  if (conf.limit === null) report.warn(null, "limit unknown: set limit from context/PLATFORM.md")
  else if (total > conf.limit) report.error(null, `total ${clock(total)} is over the limit ${clock(conf.limit)}`)
  else if (conf.limit - total < 5) report.warn(null, `total ${clock(total)} leaves less than 5 s under the limit`)
  if (conf.target !== null && Math.abs(total - conf.target) > 15)
    report.warn(null, `total ${clock(total)} is off the target ${clock(conf.target)}`)
  if (!sections.some((s) => s.start < 20 && location(s) !== null))
    report.warn(null, "no product screen in the first 20 s")
  return total
}

const sayProblems = (s, conf, vocab, strict, report) => {
  const open = s.say.flat().filter((line) => line.includes("{{")).length
  if (open > 0) report[strict ? "error" : "warn"](s, `${open} placeholder lines in Say`)
  for (const line of s.say.flat().filter((text) => !text.includes("{{"))) {
    if (AI_PUNCTUATION.test(line)) report.error(s, `em dash, middle dot, arrow or check glyph in Say: ${line.slice(0, 50)}`)
    if (/\d/.test(line)) report.warn(s, `digits in Say, write the number as it is spoken: ${line.slice(0, 50)}`)
    if (/https?:|www\.|\.(ru|com|app|io|dev|org)\b/i.test(line)) report.warn(s, `address in Say, spell it as spoken: ${line.slice(0, 50)}`)
    if (GATE.test(line)) report[strict ? "error" : "warn"](s, `open condition ${GATE.exec(line)[0]}`)
    if (conf.lang === "en" && /[\u0400-\u04ff]/.test(line)) report.error(s, `Cyrillic in an English script: ${line.slice(0, 50)}`)
    for (const sentence of line.split(/(?<=[.!?\u2026])\s+/)) {
      const count = words(sentence, vocab)
      if (count > conf.sentence) report.warn(s, `sentence of ${count} words, keep it under ${conf.sentence}: ${sentence.slice(0, 50)}`)
    }
    for (const { kind, phrase } of phraseHits(line, vocab))
      report[STRICT_PHRASES.has(kind) ? "error" : "warn"](s, `${kind} phrase "${phrase}"`)
  }
}

export const checkScript = (script, conf, vocab, strict) => {
  const errors = []
  const warnings = []
  const where = (s) => (s ? `${s.no}. ${s.title}: ` : "")
  const report = {
    error: (s, message) => errors.push(`${where(s)}${message}`),
    warn: (s, message) => warnings.push(`${where(s)}${message}`),
  }
  if (script.sections.length === 0) {
    report.error(null, "no sections like `## 1. Title, 0:00-0:12`")
    return { errors, warnings, rows: [], total: 0 }
  }
  const total = timingProblems(script, conf, report)
  const rows = script.sections.map((s) => {
    const m = measure(s, conf, vocab)
    const staged = [...s.screen, ...s.overlay].some((line) => line.includes("{{"))
    if (s.screen.length === 0) report.error(s, "no Screen")
    else if (!staged && location(s) === null && !/slide|DevTools/i.test(s.screen.join(" "))) report.warn(s, "Screen has no `/path` or URL")
    if (staged) report[strict ? "error" : "warn"](s, "placeholder in Screen or Overlay")
    if (s.say.length === 0 && !s.note) report.warn(s, "no Say: write the lines or say why it is silent")
    if (m.need > m.slot) report.error(s, `needs ${m.need.toFixed(1)} s at ${conf.wpm} wpm, slot is ${m.slot} s: cut about ${Math.ceil(((m.need - m.slot) * conf.wpm) / 60)} words`)
    else if (m.need > m.slot * 0.9) report.warn(s, `tight: ${m.need.toFixed(1)} s of ${m.slot} s, leave room to breathe`)
    sayProblems(s, conf, vocab, strict, report)
    return { s, ...m, status: m.need > m.slot ? "over" : m.need > m.slot * 0.9 ? "tight" : "ok" }
  })
  return { errors, warnings, rows, total }
}

export const retime = (script) => {
  const lines = [...script.lines]
  let cursor = 0
  for (const s of script.sections) {
    const length = Math.max(1, s.end - s.start)
    lines[s.line] = `## ${s.no}. ${s.title}, ${clock(cursor)}\u2013${clock(cursor + length)}`
    cursor += length
  }
  return lines.join("\n")
}

export const voiceOver = (script, conf, vocab) => {
  const total = script.sections.at(-1)?.end ?? 0
  const out = [`# ${script.title.replace(/:\s*video script$/i, "")}: voice-over`, "", `${conf.lang}, ${clock(total)}, ${conf.wpm} words per minute.`]
  for (const s of script.sections) {
    const blocks = s.say.length > 1 ? s.say.map((block, i) => [`${s.no}${String.fromCharCode(97 + i)}`, block]) : s.say.map((block) => [s.no, block])
    for (const [no, block] of blocks) {
      out.push("", `## ${no}. ${s.title}, ${clock(s.start)}\u2013${clock(s.end)}`, "", block.join(" ").replace(pauseMark(vocab), `[${vocab.pause}]`))
    }
  }
  return `${out.join("\n")}\n`
}

const stamp = (total) => {
  const ms = Math.max(0, Math.round(total * 1000))
  const pad = (value, size = 2) => String(value).padStart(size, "0")
  return `${pad(Math.floor(ms / 3600000))}:${pad(Math.floor(ms / 60000) % 60)}:${pad(Math.floor(ms / 1000) % 60)},${pad(ms % 1000, 3)}`
}

const chunks = (line) => {
  const out = [[]]
  for (const word of line.split(/\s+/).filter(Boolean)) {
    if ([...out.at(-1), word].join(" ").length > 84 && out.at(-1).length > 0) out.push([])
    out.at(-1).push(word)
  }
  return out.map((group) => {
    const text = group.join(" ")
    if (text.length <= 42) return text
    const half = group.findIndex((_, i) => group.slice(0, i + 1).join(" ").length >= text.length / 2)
    return `${group.slice(0, half + 1).join(" ")}\n${group.slice(half + 1).join(" ")}`
  })
}

export const captions = (script, conf, vocab) => {
  const cues = []
  const pauses = (line) => (line.match(pauseMark(vocab))?.length ?? 0) * 1.5
  for (const s of script.sections) {
    const need = s.say.flat().reduce((sum, line) => sum + lineSeconds(line, conf, vocab), 0)
    const scale = Math.min(1, (s.end - s.start - 0.3) / Math.max(need, 0.001))
    s.say.forEach((block, i) => {
      const length = block.reduce((sum, line) => sum + lineSeconds(line, conf, vocab), 0) * scale
      let at = i === 0 || i < s.say.length - 1 ? s.start + 0.3 : Math.max(s.start + 0.3, s.end - length - 0.3)
      for (const line of block) {
        const spoken = line.replace(pauseMark(vocab), " ").replace(/\s+/g, " ").trim()
        const parts = spoken ? chunks(spoken) : []
        const each = ((lineSeconds(line, conf, vocab) - pauses(line)) * scale) / Math.max(1, parts.length)
        for (const part of parts) {
          cues.push({ from: at, to: Math.min(at + each, s.end), text: part })
          at += each
        }
        at += pauses(line) * scale
      }
    })
  }
  return cues.map((cue, i) => `${i + 1}\n${stamp(cue.from)} --> ${stamp(cue.to)}\n${cue.text}\n`).join("\n")
}
