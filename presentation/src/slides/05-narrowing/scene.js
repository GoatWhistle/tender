const narrowingColor = (el, name) => {
  const probe = document.createElement("span")
  probe.style.color = `var(${name})`
  el.append(probe)
  const color = getComputedStyle(probe).color
  probe.remove()
  return color
}

deckScene("narrowing", {
  init(el) {
    const canvas = el.querySelector(".nw-field")
    const total = Number(el.querySelector('[data-num="catalog_positions"]')?.dataset.value) || 0
    const cols = 60
    const keep = 14 * cols + 59
    const lost = 15 * cols + 59
    const random = deckKit.rng(7)
    this.cells = Array.from({ length: total }, (_, i) => {
      const col = i % cols
      const row = Math.floor(i / cols)
      return {
        x: col * 16 + 6,
        y: row * 16 + 6,
        d: 0.3 + (col + row) * 0.012 + random() * 0.15,
        group: i === keep || i === lost,
        lost: i === lost,
      }
    })
    this.ctx = canvas.getContext("2d")
    this.ctx.scale(2, 2)
    this.end = 4.2
    this.draw = (t) => {
      const ctx = this.ctx
      if (!this.colors) {
        this.colors = {
          base: narrowingColor(el, "--deck-line-strong"),
          accent: narrowingColor(el, "--deck-accent"),
        }
      }
      ctx.clearRect(0, 0, 960, 528)
      const out = deckKit.ease.out
      const dim = 1 - 0.55 * deckKit.ease.inOut((t - 1.8) / 0.7)
      const grow = 1 + 0.6 * out((t - 1.9) / 0.6)
      const fade = 1 - 0.75 * out((t - 3.6) / 0.5)
      ctx.fillStyle = this.colors.base
      for (const c of this.cells) {
        if (c.group) continue
        const p = out((t - c.d) / 0.45)
        if (p <= 0) continue
        const s = 12 * (0.3 + 0.7 * p)
        ctx.globalAlpha = p * dim
        ctx.fillRect(c.x - s / 2, c.y - s / 2, s, s)
      }
      ctx.fillStyle = this.colors.accent
      for (const c of this.cells) {
        if (!c.group) continue
        const p = out((t - c.d) / 0.45)
        if (p <= 0) continue
        const s = 12 * (0.3 + 0.7 * p) * grow
        ctx.globalAlpha = p * (c.lost ? fade : 1)
        ctx.fillRect(c.x - s / 2, c.y - s / 2, s, s)
      }
      ctx.globalAlpha = 1
    }
    this.draw(this.end)
  },
  enter() {
    this.stop?.()
    this.draw(0)
    this.stop = deckKit.tween({ from: 0, to: this.end, dur: this.end * 1000, curve: "linear", update: (t) => this.draw(t) })
  },
  leave() {
    this.stop?.()
  },
})
