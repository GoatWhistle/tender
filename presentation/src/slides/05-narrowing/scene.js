const narrowingCenter = (node, root) => {
  let x = node.offsetWidth / 2
  let y = node.offsetHeight / 2
  while (node && node !== root) {
    x += node.offsetLeft
    y += node.offsetTop
    node = node.offsetParent
  }
  return { x, y }
}

deckScene("narrowing", {
  init(el) {
    const fc = el.querySelector(".fc")
    this.svg = deckKit.svg("svg", { class: "fc-flow", "aria-hidden": "true" })
    fc.prepend(this.svg)
  },
  enter(el) {
    this.stop?.()
    const fc = el.querySelector(".fc")
    const svg = this.svg
    svg.replaceChildren()
    svg.setAttribute("viewBox", `0 0 ${fc.offsetWidth} ${fc.offsetHeight}`)
    const [a, b, c] = [...fc.querySelectorAll(".fc-circle")].map((node) => narrowingCenter(node, fc))
    const random = deckKit.rng(5)
    const dots = Array.from({ length: 46 }, (_, i) => {
      const angle = random() * Math.PI * 2
      const radius = Math.sqrt(random()) * 88
      const dot = deckKit.svg("circle", { r: i < 2 ? 7 : 5, class: i === 0 ? "fc-dot is-key" : "fc-dot" }, svg)
      return {
        dot,
        sx: a.x + Math.cos(angle) * radius,
        sy: a.y + Math.sin(angle) * radius,
        cut: i < 2 ? 2 : 0.25 + random() * 0.6,
        drift: (random() - 0.5) * 140,
        lane: (random() - 0.5) * 36,
        keep: i === 0,
      }
    })
    const place = (d, x, y, alpha) => {
      d.dot.setAttribute("cx", x.toFixed(1))
      d.dot.setAttribute("cy", y.toFixed(1))
      d.dot.style.opacity = String(Math.max(0, Math.min(1, alpha)))
    }
    dots.forEach((d) => place(d, d.sx, d.sy, 0))
    const first = deckKit.tween({
      delay: 1300,
      dur: 1700,
      curve: "inOut",
      update: (t) => {
        for (const d of dots) {
          const tx = d.keep ? b.x - 16 : b.x + 16
          const ty = b.y + 48
          const x = d.sx + (tx + (d.cut < 2 ? d.lane : 0) - d.sx) * t
          const fall = t > d.cut ? (t - d.cut) * d.drift : 0
          const y = d.sy + (ty - d.sy) * t + Math.abs(fall)
          const alpha = t < 0.08 ? t / 0.08 : t > d.cut ? 1 - (t - d.cut) * 6 : 1
          place(d, x, y, alpha)
        }
      },
      done: () => {
        this.second = deckKit.tween({
          delay: 500,
          dur: 1300,
          curve: "inOut",
          update: (t) => {
            const [keep, lost] = dots
            place(keep, b.x - 16 + (c.x - b.x + 16) * t, b.y + 48 + (c.y + 48 - b.y - 48) * t, t > 0.92 ? (1 - t) * 12 : 1)
            place(lost, b.x + 16 + t * 30, b.y + 48 + t * 120, 1 - t * 2.5)
          },
          done: () => {
            el.querySelector(".fc-circle.is-accent")?.animate(
              [{ transform: "scale(1)" }, { transform: "scale(1.12)" }, { transform: "scale(1)" }],
              { duration: 520, easing: "ease-out" },
            )
          },
        })
      },
    })
    this.stop = () => {
      first()
      this.second?.()
    }
  },
  leave() {
    this.stop?.()
  },
})
