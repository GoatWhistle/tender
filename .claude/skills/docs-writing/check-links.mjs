#!/usr/bin/env node
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs"
import { dirname, extname, join, resolve } from "node:path"

const args = process.argv.slice(2)
const roots = args.length > 0 ? args : ["README.md", "docs"]

const collect = (path) => {
  if (!existsSync(path)) return []
  if (statSync(path).isDirectory()) {
    return readdirSync(path).flatMap((name) => collect(join(path, name)))
  }
  return extname(path) === ".md" ? [path] : []
}

const withoutCode = (text) =>
  text.replace(/^(```|~~~)[^\n]*\n[\s\S]*?^\1[^\n]*$/gm, "").replace(/`[^`\n]*`/g, "")

const slugify = (heading) =>
  heading
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/<[^>]+>/g, "")
    .replace(/[*~]/g, "")
    .trim()
    .toLowerCase()
    .replace(/[^\p{L}\p{M}\p{N}\p{Pc} -]/gu, "")
    .replace(/ /g, "-")

const anchorCache = new Map()

const anchorsOf = (file) => {
  const cached = anchorCache.get(file)
  if (cached) return cached
  const text = readFileSync(file, "utf8").replace(/^(```|~~~)[^\n]*\n[\s\S]*?^\1[^\n]*$/gm, "")
  const seen = new Map()
  const anchors = new Set()
  for (const match of text.matchAll(/^#{1,6}\s+(.+?)\s*#*\s*$/gm)) {
    const base = slugify(match[1])
    const count = seen.get(base) ?? 0
    seen.set(base, count + 1)
    anchors.add(count === 0 ? base : `${base}-${count}`)
  }
  for (const match of text.matchAll(/<a\s+(?:id|name)="([^"]+)"/g)) anchors.add(match[1])
  anchorCache.set(file, anchors)
  return anchors
}

const targetsOf = (text) => {
  const plain = withoutCode(text)
  const markdown = [...plain.matchAll(/\]\(([^)\s]+)(?:\s+"[^"]*")?\)/g)].map((m) => m[1])
  const html = [...plain.matchAll(/(?:href|src)="([^"]+)"/g)].map((m) => m[1])
  const srcset = [...plain.matchAll(/srcset="([^"\s,]+)/g)].map((m) => m[1])
  return [...markdown, ...html, ...srcset]
}

const problems = []

for (const file of roots.flatMap(collect)) {
  for (const target of targetsOf(readFileSync(file, "utf8"))) {
    if (/^[a-z][a-z0-9+.-]*:/i.test(target) || target.includes("{{")) continue
    const [pathPart, anchor] = target.split("#")
    const resolved = pathPart ? resolve(dirname(file), decodeURI(pathPart)) : resolve(file)
    if (!existsSync(resolved)) {
      problems.push(`${file}: ${target} -> missing file`)
      continue
    }
    if (!anchor || extname(resolved) !== ".md") continue
    if (!anchorsOf(resolved).has(decodeURIComponent(anchor))) {
      problems.push(`${file}: ${target} -> missing anchor`)
    }
  }
}

for (const problem of problems) console.log(problem)
process.exit(problems.length > 0 ? 1 : 0)
