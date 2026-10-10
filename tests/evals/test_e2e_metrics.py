import unittest

from evals.e2e.metrics import summarize


def row(**overrides):
    base = {
        "id": "x",
        "set": "dev",
        "category": "Мебель",
        "tags": ["complete"],
        "gold_groups": ["G1"],
        "gold_codes": ["C1"],
        "gold_facts": [],
        "facts": [],
        "search": ["G1", "G2"],
        "status": "needs_clarification",
        "group": "G1",
        "compatible": ["C1", "C2"],
    }
    return {**base, **overrides}


class E2EMetricsTest(unittest.TestCase):
    def test_recall_counts_only_cases_with_groups(self):
        rows = [
            row(search=["G2", "G1"]),
            row(gold_groups=[], gold_codes=[], search=["G1"], tags=["out_of_scope"]),
        ]
        dev = summarize(rows, supports_out_of_scope=True)["dev"]
        self.assertEqual(dev["recall"]["R@1"], {"n": 0, "of": 1, "share": 0})
        self.assertEqual(dev["recall"]["R@5"]["n"], 1)
        self.assertEqual(dev["out_of_scope"], {"n": 0, "of": 1, "share": 0})

    def test_unsupported_out_of_scope_metric_is_skipped(self):
        summary = summarize(
            [
                row(gold_groups=[], gold_codes=[]),
                row(set="holdout", gold_groups=[], gold_codes=[]),
            ]
        )
        self.assertEqual(summary["dev"]["out_of_scope"], "пропущено")
        self.assertEqual(summary["holdout"]["out_of_scope"], "пропущено")

    def test_issued_code_accuracy_and_coverage(self):
        rows = [
            row(status="resolved", compatible=["C1"]),
            row(status="resolved", compatible=["C2"]),
            row(),
        ]
        codes = summarize(rows)["dev"]["codes"]
        self.assertEqual(codes["accuracy"]["n"], 1)
        self.assertEqual(codes["accuracy"]["of"], 2)
        self.assertEqual(codes["coverage"]["n"], 2)
        self.assertEqual(codes["coverage"]["of"], 3)

    def test_empty_denominator_is_none(self):
        codes = summarize([row()])["dev"]["codes"]
        self.assertIsNone(codes["accuracy"]["share"])

    def test_code_issued_for_out_of_scope_product_counts_as_incorrect(self):
        rows = [
            row(status="resolved", compatible=["C1"]),
            row(status="resolved", compatible=["C2"], gold_groups=[], gold_codes=[]),
            row(status="out_of_scope", compatible=[], gold_groups=[], gold_codes=[]),
        ]
        codes = summarize(rows)["dev"]["codes"]
        self.assertEqual(codes["accuracy"], {"n": 1, "of": 2, "share": 0.5})
        self.assertEqual(codes["coverage"], {"n": 2, "of": 3, "share": 2 / 3})

    def test_ambiguity_requires_all_gold_codes_and_no_issued_code(self):
        rows = [
            row(gold_codes=["C1", "C2"], compatible=["C1", "C2", "C3"]),
            row(gold_codes=["C1", "C2"], compatible=["C1"], status="resolved"),
            row(gold_codes=["C1", "C2"], compatible=["C1", "C2"], group="G9"),
        ]
        self.assertEqual(
            summarize(rows)["dev"]["ambiguity"], {"n": 1, "of": 3, "share": 1 / 3}
        )

    def test_gold_kept_needs_right_group(self):
        rows = [row(), row(group="G2"), row(compatible=["C9"])]
        self.assertEqual(summarize(rows)["dev"]["gold_kept"]["n"], 1)

    def test_facts_precision_and_recall_by_key(self):
        rows = [
            row(
                gold_facts=[["тип каркаса", "деревянный"], ["высота", "length:1.8"]],
                facts=[["тип каркаса", "деревянный"], ["цвет", "белый"]],
            )
        ]
        facts = summarize(rows)["dev"]["facts"]
        self.assertEqual(facts["precision"], {"n": 1, "of": 2, "share": 0.5})
        self.assertEqual(facts["recall"], {"n": 1, "of": 2, "share": 0.5})

    def test_holdout_is_reported_separately(self):
        rows = [row(), row(set="holdout", search=["G3"])]
        summary = summarize(rows)
        self.assertEqual(summary["dev"]["recall"]["R@1"]["n"], 1)
        self.assertEqual(
            summary["holdout"]["recall"]["R@1"], {"n": 0, "of": 1, "share": 0}
        )


if __name__ == "__main__":
    unittest.main()
