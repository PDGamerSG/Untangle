"""Evaluation harness: gold questions in YAML, graph vs vector-only baseline, a Markdown report with
evidence-chain accuracy, supersession correctness, refusal precision/recall, person-to-ask hit rate and latency."""

from kyun.eval.gold import Expect, GoldQuestion, GoldSet, load_gold
from kyun.eval.harness import run_eval

__all__ = ["Expect", "GoldQuestion", "GoldSet", "load_gold", "run_eval"]
