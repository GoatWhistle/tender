deckScene("final", {
  init(el) {
    deckKit.letters(el.querySelector(".wordmark"))
    const field = el.querySelector(".final-field")
    if (field.childElementCount) return
    const random = deckKit.rng(11)
    const size = 64
    const cx = 960
    const cy = 600
    for (let y = 32; y < 1080; y += 96) {
      for (let x = 32; x < 1920; x += 96) {
        const dx = x + size / 2 - cx
        const dy = y + size / 2 - cy
        const dist = Math.hypot(dx, dy)
        const overTitle = x + size > 440 && x < 1480 && y + size > 80 && y < 340
        const overCard = x + size > 680 && x < 1240 && y + size > 360 && y < 950
        if (overTitle || overCard || random() > 0.42) continue
        const tile = deckKit.svg("rect", { x, y, width: size, height: size }, field)
        const roll = random()
        if (roll < 0.07) tile.classList.add("is-accent")
        else if (roll < 0.3) tile.classList.add("is-base")
        tile.style.setProperty("--d", `${(0.2 + dist / 1400).toFixed(2)}s`)
        tile.style.setProperty("--o", (0.35 + random() * 0.45).toFixed(2))
      }
    }
  },
})
