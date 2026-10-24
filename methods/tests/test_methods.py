"""Independent, hand-calculated checks; all inputs are invented."""

import copy
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from market_methods import build_report, kendall_w, wilson
from market_methods.engine import average_ranks, canonical_bytes, digest

ROOT = Path(__file__).resolve().parents[1]


def config():
    return {"synthetic": True, "sources": {"s1": {"lens": "l1"}, "s2": {"lens": "l2"}},
            "weights": {"l1": .75, "l2": .25}, "top_k": 1,
            "alternative_weights": {"reverse": {"l1": .25, "l2": .75}}}


def metrics():
    return [{"entity": entity, "source": source, "value": value}
            for entity, source, value in [("a", "s1", 30), ("b", "s1", 20), ("c", "s1", 10),
                                           ("a", "s2", 10), ("b", "s2", 20), ("c", "s2", 30)]]


class RankingTests(unittest.TestCase):
    def test_hand_calculated_weighting_and_sensitivity(self):
        report = build_report(metrics(), config())
        self.assertEqual([r["entity"] for r in report["ranking"]], ["a", "b", "c"])
        self.assertEqual([r["score"] for r in report["ranking"]], [1.5, 2.0, 2.5])
        self.assertEqual([r["index"] for r in report["ranking"]], [75, 50, 25])
        robust = report["robustness"]
        self.assertEqual(robust["alternative_weights"][0]["top"], ["c"])
        self.assertEqual(robust["leave_one_out"][0]["top"], ["c"])
        self.assertEqual(robust["leave_one_out"][1]["top"], ["a"])
        self.assertEqual(robust["kendall"], {"w": 0.0, "entities": 3, "sources": 2})

    def test_missing_is_distinct_from_zero(self):
        rows = [{"entity": "a", "source": "s1", "value": None},
                {"entity": "b", "source": "s1", "value": 0}]
        report = build_report(rows, config())
        by_key = {r["entity"]: r for r in report["ranking"]}
        self.assertIsNone(by_key["a"]["score"])
        self.assertEqual(by_key["b"]["score"], 1)
        self.assertIsNone(by_key["b"]["lens_ranks"]["l2"])

    def test_average_ties_and_top_boundary_disclosure(self):
        cfg = config()
        cfg["weights"] = {"l1": .5, "l2": .5}
        report = build_report(metrics(), cfg)
        self.assertEqual([r["rank"] for r in report["ranking"]], [2, 2, 2])
        self.assertTrue(report["robustness"]["top_boundary_tie"])
        self.assertEqual(average_ranks({"a": 10, "b": 10, "c": 0}), {"a": 1.5, "b": 1.5, "c": 3})

    def test_coverage_gate_uses_ceiling(self):
        cfg = {"sources": {s: {"lens": "l"} for s in ["s1", "s2", "s3"]},
               "weights": {"l": 1}, "minimum_lens_coverage": .5}
        rows = [{"entity": "a", "source": "s1", "value": 1}]
        report = build_report(rows, cfg)
        self.assertIsNone(report["ranking"][0]["score"])
        # Dropping either missing source leaves one of two: coverage becomes sufficient.
        self.assertEqual(report["robustness"]["leave_one_out"][1]["top"], ["a"])

    def test_one_entity_index_is_undefined(self):
        report = build_report([{"entity": "a", "source": "s1", "value": 10}], config())
        self.assertEqual(report["ranking"][0]["score"], 1)
        self.assertIsNone(report["ranking"][0]["index"])

    def test_invalid_inputs_fail(self):
        bad_inputs = [metrics() + [metrics()[0]],
                      [{"entity": "a", "source": "unknown", "value": 1}], []]
        bad_inputs.extend([[{"entity": "a", "source": "s1", "value": v}]
                           for v in [-1, True, "1", math.nan, math.inf]])
        for rows in bad_inputs:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                build_report(rows, config())

    def test_invalid_configuration_fails(self):
        cases = []
        for weights in [{"l1": 1}, {"l1": 0, "l2": 0}, {"l1": -1, "l2": 1}]:
            cfg = config()
            cfg["weights"] = weights
            cases.append(cfg)
        for coverage in [0, 1.1]:
            cfg = config()
            cfg["minimum_lens_coverage"] = coverage
            cases.append(cfg)
        cfg = config()
        cfg["sources"]["s1"]["direction"] = "lower"
        cases.append(cfg)
        for cfg in cases:
            with self.subTest(cfg=cfg), self.assertRaises(ValueError):
                build_report(metrics(), cfg)


class QualityTests(unittest.TestCase):
    def test_known_wilson_interval(self):
        result = wilson(8, 10)
        self.assertEqual(result["precision"], .8)
        self.assertAlmostEqual(result["ci_low"], .4901568, places=6)
        self.assertAlmostEqual(result["ci_high"], .9433191, places=6)
        for correct, total in [(0, 0), (-1, 10), (11, 10), (True, 10), (1.5, 10)]:
            with self.subTest(counts=(correct, total)), self.assertRaises(ValueError):
                wilson(correct, total)

    def test_quality_adjusts_and_excludes_before_ranking(self):
        rows = [{"entity": "a", "source": "s1", "value": 100},
                {"entity": "b", "source": "s1", "value": 90},
                {"entity": "c", "source": "s1", "value": 200}]
        quality = [{"entity": "a", "source": "s1", "correct": 8, "total": 10},
                   {"entity": "c", "source": "s1", "correct": 6, "total": 10}]
        report = build_report(rows, config(), quality)
        self.assertEqual([r["entity"] for r in report["ranking"]], ["b", "a", "c"])
        self.assertIsNone(report["ranking"][2]["score"])
        self.assertEqual(report["ranking"][1]["quality_treatments"]["s1"], "adjust")
        self.assertEqual(report["ranking"][0]["quality_treatments"]["s1"], "unassessed")

    def test_quality_boundaries_fallback_and_stop(self):
        quality = [{"source": "s1", "correct": 9, "total": 10},
                   {"source": "s1", "entity": "a", "correct": 7, "total": 10}]
        report = build_report(metrics(), config(), quality)
        treatments = {r["entity"]: r["quality_treatments"]["s1"] for r in report["ranking"]}
        self.assertEqual(treatments, {"a": "adjust", "b": "use", "c": "use"})
        with self.assertRaisesRegex(ValueError, "quality stop"):
            build_report(metrics(), config(), [{"source": "s1", "correct": 4, "total": 10}])
        with self.assertRaisesRegex(ValueError, "duplicate quality"):
            build_report(metrics(), config(), quality + [quality[0]])


class AgreementTests(unittest.TestCase):
    def test_agreement_and_opposition(self):
        forward = {"a": 1, "b": 2, "c": 3}
        backward = {"a": 3, "b": 2, "c": 1}
        self.assertEqual(kendall_w([forward, forward])["w"], 1)
        self.assertEqual(kendall_w([forward, backward])["w"], 0)

    def test_ties_and_gapped_complete_subset(self):
        self.assertEqual(kendall_w([{"a": 1, "b": 8}, {"a": 2, "b": 10}])["w"], 1)
        tied = {"a": 1.5, "b": 1.5, "c": 3}
        self.assertEqual(kendall_w([tied, tied])["w"], 1)
        # Rank sums 2.5, 4.5, 5 -> S=3.5; denominator=96-12=84; W=42/84.
        self.assertAlmostEqual(kendall_w([tied, {"a": 1, "b": 3, "c": 2}])["w"], .5)

    def test_undefined_agreement_is_null(self):
        for columns in [[], [{"a": 1}], [{"a": 1}, {"b": 1}],
                        [{"a": 1, "b": 1}, {"a": 1, "b": 1}]]:
            with self.subTest(columns=columns):
                self.assertIsNone(kendall_w(columns)["w"])


class ReleaseTests(unittest.TestCase):
    def test_determinism_permutation_and_content_address(self):
        rows, cfg = metrics(), config()
        before = copy.deepcopy((rows, cfg))
        first = build_report(rows, cfg)
        self.assertEqual(canonical_bytes(first), canonical_bytes(build_report(list(reversed(rows)), cfg)))
        self.assertEqual((rows, cfg), before)
        payload = {key: value for key, value in first.items() if key != "release_id"}
        self.assertEqual(first["release_id"], digest(payload))
        rows[0]["value"] += 1
        self.assertNotEqual(first["release_id"], build_report(rows, cfg)["release_id"])

    def test_caller_data_is_not_silently_labelled_synthetic(self):
        cfg = config()
        cfg.pop("synthetic")
        self.assertEqual(build_report(metrics(), cfg)["data_kind"], "user_supplied_unverified")

    def test_cli_and_committed_example_are_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "demo.json"
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            completed = subprocess.run([sys.executable, "-m", "market_methods",
                                       "--metrics", str(ROOT / "examples/metrics.json"),
                                       "--config", str(ROOT / "examples/config.json"),
                                       "--quality", str(ROOT / "examples/quality.json"),
                                       "--out", str(out)], env=env, cwd=directory,
                                      capture_output=True, text=True, check=True)
            self.assertIn("synthetic", completed.stdout)
            self.assertEqual(out.read_bytes(), (ROOT / "examples/demo-report.json").read_bytes())
            self.assertEqual(json.loads(out.read_bytes())["data_kind"], "synthetic")


if __name__ == "__main__":
    unittest.main()
