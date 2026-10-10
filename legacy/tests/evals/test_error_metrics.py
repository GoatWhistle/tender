import copy
import json
import unittest
from decimal import Decimal
from pathlib import Path

from evals.errors.score import score

ROOT = Path(__file__).resolve().parents[2]


class ErrorMetricsTest(unittest.TestCase):
    def setUp(self):
        self.dataset = json.loads(
            (ROOT / "evals/datasets/errors_ru_v1.json").read_text()
        )
        self.rows = [
            {"id": case["id"], "errors": [], "normalizations": []}
            for case in self.dataset["cases"]
        ]

    def test_empty_predictions_count_misses_and_no_false_alarms(self):
        result = score(self.dataset, self.rows)
        self.assertEqual(result["cases"], 24)
        self.assertEqual(result["false_alarm_cases"], 0)
        for metrics in result["per_kind"].values():
            self.assertEqual(metrics["fn"], 3)
            self.assertEqual(metrics["recall"], 0)

    def test_correct_class_with_wrong_quote_is_not_correct_diagnostic(self):
        case = self.dataset["cases"][0]
        self.rows[0]["errors"] = [{"kind": "typo", "source_quote": case["text"]}]
        result = score(self.dataset, self.rows)["per_kind"]["typo"]
        self.assertEqual(result["tp"], 1)
        self.assertEqual(result["diagnostics"], {"tp": 0, "fp": 1, "fn": 3})

    def test_synonym_false_alarm_and_wrong_suggestion(self):
        case = self.dataset["cases"][18]
        quote = case["text"]
        self.rows[18]["errors"] = [{"kind": "typo", "source_quote": quote}]
        self.rows[18]["normalizations"] = [
            {"kind": "synonym", "source_quote": quote, "suggestion": "wrong"}
        ]
        result = score(self.dataset, self.rows)
        self.assertEqual(result["synonyms_reported_as_errors"], 1)
        self.assertEqual(result["false_alarm_rate"], 1 / 15)
        self.assertEqual(result["correct_suggestions"], 0)
        self.assertEqual(result["per_kind"]["synonym"]["tp"], 1)

    def test_correct_suggestion_counts_detection_and_replacement(self):
        event = self.dataset["cases"][0]["expected"][0]
        self.rows[0]["errors"] = [event]
        result = score(self.dataset, self.rows)
        self.assertEqual(result["per_kind"]["typo"]["diagnostics"]["tp"], 1)
        self.assertEqual(result["correct_suggestions"], 1)
        self.assertEqual(result["expected_suggestions"], 6)

    def test_absent_positive_class_has_undefined_recall(self):
        dataset = {"cases": [self.dataset["cases"][1]]}
        result = score(dataset, [self.rows[1]])
        self.assertIsNone(result["per_kind"]["typo"]["recall"])
        self.assertIsNone(result["suggestion_accuracy"])

    def test_reject_missing_duplicate_unknown_ids(self):
        for rows in [
            self.rows[:-1],
            self.rows + self.rows[:1],
            self.rows + [{"id": "unknown"}],
        ]:
            with self.subTest(rows=len(rows)), self.assertRaises(ValueError):
                score(self.dataset, rows)

    def test_reject_invalid_contracts(self):
        for event in [
            {"kind": "synonym", "source_quote": self.dataset["cases"][0]["text"]},
            {"kind": "typo", "source_quote": "not in the text"},
        ]:
            rows = copy.deepcopy(self.rows)
            rows[0]["errors"] = [event]
            with self.subTest(event=event), self.assertRaises(ValueError):
                score(self.dataset, rows)

    def test_dataset_covers_all_classes_and_categories(self):
        positive = {
            (c["category"], e["kind"])
            for c in self.dataset["cases"]
            for e in c["expected"]
        }
        self.assertEqual(len(positive), 12)
        for alias in self.dataset["aliases"]:
            self.assertTrue(alias["reviewed"])
            self.assertTrue(alias["source"]["cells"])
        self.assertEqual(len(self.dataset["rules"]), 6)

    def test_numeric_examples_use_complete_value_sets_and_boundaries(self):
        def accepts(value, rule):
            x = Decimal(value)
            for v in rule["characteristic"]["values"]:
                if v["concrete"] is not None:
                    if x == Decimal(str(v["concrete"])):
                        return True
                    continue
                lo = v["min"]
                hi = v["max"]
                lower = lo is None or (
                    x > Decimal(str(lo))
                    if v["min_op"] == "greater"
                    else x >= Decimal(str(lo))
                )
                upper = hi is None or (
                    x < Decimal(str(hi))
                    if v["max_op"] == "less"
                    else x <= Decimal(str(hi))
                )
                if lower and upper:
                    return True
            return False

        for slug, good, bad in [
            ("clothes", "200", "201"),
            ("furniture", "90", "135"),
            ("tools", "1", "3"),
        ]:
            rule = self.dataset["rules"][slug + "_numeric"]
            self.assertTrue(accepts(good, rule))
            self.assertFalse(accepts(bad, rule))
        self.assertTrue(accepts("146", self.dataset["rules"]["clothes_numeric"]))
        self.assertFalse(accepts("145.999", self.dataset["rules"]["clothes_numeric"]))


if __name__ == "__main__":
    unittest.main()
