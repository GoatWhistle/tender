import { describe, expect, it } from "vitest"
import {
  bandLabel,
  doubt,
  type KtruBand,
  matchBand,
} from "../../../../src/features/rag-workflow/characteristics/field-kind"

function band(option: string, min: number | null, max: number | null, closed = true): KtruBand {
  return { option, min, min_inclusive: true, max, max_inclusive: !closed }
}

const power = [
  band("lt500", null, 500),
  band("500-600", 500, 600),
  band("600-700", 600, 700),
  band("ge700", 700, null),
]
const thresholds = [band("ge30", 30, null), band("ge60", 60, null), band("ge90", 90, null)]

describe("matchBand", () => {
  it("puts the boundary into the band whose lower edge is inclusive", () => {
    expect(matchBand(power, 499)?.option).toBe("lt500")
    expect(matchBand(power, 500)?.option).toBe("500-600")
    expect(matchBand(power, 10000)?.option).toBe("ge700")
  })

  it("picks the tightest overlapping threshold", () => {
    expect(matchBand(thresholds, 75)?.option).toBe("ge60")
    expect(matchBand(thresholds, 10)).toBeNull()
  })

  it("flags implausible values without rejecting them", () => {
    expect(doubt(power, 300000000)?.code).toBe("large")
    expect(doubt(power, 7000)).toBeNull()
    expect(doubt(power, 12)?.code).toBe("small")
    expect(doubt(power, 0)).toBeNull()
    expect(doubt(power, -5)?.code).toBe("negative")
  })

  it("labels bands with their bounds", () => {
    const format = (value: number) => String(value)
    expect(power.map((item) => bandLabel(item, format))).toEqual([
      "< 500",
      "500–600",
      "600–700",
      "≥ 700",
    ])
  })
})
