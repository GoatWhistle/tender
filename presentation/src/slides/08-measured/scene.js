deckScene("measured", {
  init(el) {
    for (const item of el.querySelectorAll(".ms-rings li")) {
      const part = Number(item.querySelector(".ms-value .count")?.dataset.value)
      const whole = Number(item.querySelector(".ms-value small .num")?.dataset.value)
      const arc = item.querySelector(".ms-arc")
      if (arc && whole > 0 && Number.isFinite(part)) arc.style.setProperty("--w", String(part / whole))
    }
  },
})
