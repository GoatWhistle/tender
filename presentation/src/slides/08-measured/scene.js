deckScene("measured", {
  init(el) {
    for (const card of el.querySelectorAll(".kpi")) {
      const [part, whole] = [...card.querySelectorAll(".num")].map((n) => Number(n.dataset.value))
      const fill = card.querySelector(".kg-fill")
      if (fill && Number.isFinite(part) && whole > 0) fill.style.setProperty("--w", String(part / whole))
    }
  },
})
