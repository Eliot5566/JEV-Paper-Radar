"""Turn a radar profile into Jev System One questions.

Design rules (from TypeSafe's docs and the Jev 1.13 jaggedness notes):
* one atomic question per interest; composition happens in code, not in the prompt;
* exclusions are separate, positively phrased Nouls, never negations inside an interest;
* no counting or date arithmetic is ever delegated to the model;
* every question is asked in one call per paper (speculative fan-out).
"""

from __future__ import annotations

from typing import Any

from .config import Config

INTEREST_PREFIX = "i_"
EXCLUDE_PREFIX = "x_"
SCREEN_INCLUDE_PREFIX = "si_"
SCREEN_EXCLUDE_PREFIX = "sx_"
PAPER_TYPE_KEY = "s_paper_type"
CODE_KEY = "s_code"
EVIDENCE_KEY = "s_evidence"

PAPER_TYPES: dict[str, str] = {
    "new_method": "Proposes a new method, model, algorithm, or architecture",
    "benchmark": "Introduces a benchmark or an evaluation protocol",
    "dataset": "Introduces a new dataset or corpus as its main contribution",
    "empirical_study": "Analyzes or compares existing methods without proposing a new one",
    "survey": "A survey, review, or tutorial of a research area",
    "theory": "Mainly theoretical results such as proofs or bounds",
    "system": "A software system, tool, library, or infrastructure",
    "position": "A position paper, perspective, or opinion piece",
    "application": "Applies existing techniques to a specific domain problem",
}

EVIDENCE_LEVELS: list[str] = [
    "No experiments or evaluation are mentioned",
    "A small or preliminary evaluation is mentioned",
    "Evaluation on standard benchmarks or datasets is reported",
    "Extensive evaluation across many settings with comparisons to strong baselines is reported",
]

CODE_STATEMENT = "The abstract states that code, data, or model weights are publicly released or will be released."


def noul(instructions: str, true: str | None = None, false: str | None = None) -> dict[str, Any]:
    question: dict[str, Any] = {"type": "noul", "instructions": instructions}
    criteria = {k: v for k, v in (("true", true), ("false", false)) if v}
    if criteria:
        question["criteria"] = criteria
    return question


def build_questions(config: Config) -> dict[str, dict[str, Any]]:
    questions: dict[str, dict[str, Any]] = {}
    for interest in config.interests:
        questions[INTEREST_PREFIX + interest.id] = noul(interest.text, interest.true, interest.false)
    for exclusion in config.exclusions:
        questions[EXCLUDE_PREFIX + exclusion.id] = noul(exclusion.text)
    if config.signals.paper_type:
        questions[PAPER_TYPE_KEY] = {
            "type": "choice",
            "instructions": "What is the main contribution type of this paper?",
            "criteria": dict(PAPER_TYPES),
        }
    if config.signals.code_release:
        questions[CODE_KEY] = noul(CODE_STATEMENT)
    if config.signals.evidence:
        questions[EVIDENCE_KEY] = {
            "type": "score",
            "instructions": "How much empirical evaluation does the abstract report?",
            "criteria": list(EVIDENCE_LEVELS),
        }
    return questions


def build_screening_questions(config: Config) -> dict[str, dict[str, Any]]:
    """One Noul per eligibility criterion — nothing else.

    Screening asks a different question from the daily radar ("is this study eligible?"
    rather than "would I want to read this?"), so the paper-type, code and evidence
    signals are left out: they add tokens to every record and no screening decision
    depends on them.
    """
    questions: dict[str, dict[str, Any]] = {}
    for criterion in config.screening.include:
        questions[SCREEN_INCLUDE_PREFIX + criterion.id] = noul(criterion.text)
    for criterion in config.screening.exclude:
        questions[SCREEN_EXCLUDE_PREFIX + criterion.id] = noul(criterion.text)
    return questions
