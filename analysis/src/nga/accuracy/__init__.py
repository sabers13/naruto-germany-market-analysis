"""Keyword accuracy harness (ANALYSIS_PLAN.md §6).

Draw a fixed stratified sample from the matches files, produce a labelling
packet, then turn labels into precision numbers and treatments.

Modules: sample.py (draw), packet.py (labelling packet), precision.py (score).
CLI: uv run python -m nga.accuracy sample|packet|score
"""

SEED = 20261023

#: In-score sources that are keyword-matched (plan §6.2 / §6.8).
KEYWORD_SOURCES = ("amazon", "ebay", "kleinanzeigen", "youtube", "anime2you")

#: Sample quotas per keyword source (plan §6.2).
N_RANDOM = 40
N_AMBIGUOUS = 15
N_TOP5 = 10

#: Ambiguous characters with a dedicated oversample stratum (plan §6.2).
AMBIGUOUS_CHARACTERS = ("hinata_hyuga", "nagato_pain")

#: Labeller verdicts (plan §6.3). `unclear` counts as wrong.
LABELS = ("correct", "wrong_character", "not_naruto", "unclear")
