import { readdirSync, readFileSync } from "node:fs"
import { join } from "node:path"

function walk(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) =>
    entry.isDirectory() ? walk(join(directory, entry.name)) : [join(directory, entry.name)],
  )
}
export function violations(path, text) {
  const issues = []
  if (path.endsWith("schema.gen.ts")) return issues
  if (!path.endsWith("schema.gen.ts") && text.trimEnd().split("\n").length > 250)
    issues.push("file-length")
  if (!path.endsWith("schema.gen.ts") && /\/\*|^\s*\/\//m.test(text)) issues.push("no-comments")
  if (
    !path.includes("/tokens/") &&
    /#[0-9a-f]{3,8}\b|\b\d+m?s\b|cubic-bezier\(/i.test(text) &&
    path.endsWith(".css")
  )
    issues.push("css-literals")
  if (/transition:\s*all|scale\(0\)|!important/.test(text)) issues.push("motion-safety")
  if (!path.includes("/locales/") && /[А-Яа-яЁё]/.test(text)) issues.push("cyrillic")
  return issues
}
const failures = walk("src")
  .filter((path) => /\.(tsx?|css)$/.test(path))
  .flatMap((path) => violations(path, readFileSync(path, "utf8")).map((rule) => `${rule}: ${path}`))
for (const [name, sample, path] of [
  ["file-length", "x\n".repeat(251), "sample.ts"],
  ["no-comments", "/* x */", "sample.ts"],
  ["css-literals", "a { color: #fff }", "sample.css"],
  ["motion-safety", "transition: all", "sample.css"],
  ["cyrillic", "Пример", "sample.ts"],
]) {
  if (!violations(path, sample).includes(name)) failures.push(`self-test: ${name}`)
}
if (failures.length) {
  process.stderr.write(`${failures.join("\n")}\n`)
  process.exitCode = 1
}
