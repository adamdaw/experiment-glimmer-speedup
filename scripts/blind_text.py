"""Grading-packet text shared with the parent eval this study was run in (vendored verbatim).

RUBRIC comes from that eval's analyze.py; SCRUB and EXPLORE_RUBRIC_EXTRA from its earlier blind-packet builder.
build_blind_gs.py imported them from those modules; they are copied here so the bundle is self-contained.
"""
import re

RUBRIC = """## Grading rubric (score each answer 1-5 on each axis)

| axis | 5 | 3 | 1 |
|---|---|---|---|
| **Correctness** | Every claim is right; the key conclusion (root cause / planted bugs / behavior) is correct | Main conclusion right but some wrong details | Main conclusion wrong |
| **Completeness** | Covers all key points in the reference notes that matter for the question | Covers about half | Misses most key points |
| **Groundedness** | Every claim is traceable to the provided code/log/doc; no invented functions, lines, config or events | Minor unsupported embellishment | Hallucinated facts that would mislead a reader |
| **Concision** | Tight, well organized, no padding; respects length limits | Some filler/repetition | Bloated or disorganized; key point buried |

Reference notes are guidance, not an exhaustive answer key: credit correct, grounded points that the notes don't list, and penalize confident wrong claims more than omissions. Grade each task's answers side by side. Labels are shuffled per task, so X in one task is unrelated to X in another.

Suggested scoresheet (copy per task): `task | label | correctness | completeness | groundedness | concision | notes`
"""


SCRUB = re.compile(r"\b(gpt-?oss\w*|chatgpt|openai|gpt-?\d[\w.-]*|mistral\w*|magistral|devstral|qwen[\w.-]*|alibaba|gemma[\w.-]*|google|deepmind|claude|anthropic|llama|muse[ -]?glimmer|glimmer|harmony)\b", re.I)

EXPLORE_RUBRIC_EXTRA = """For the two **cited-explore** tasks (`he1_cancel`, `he2_timeouts`), additionally count, per answer:
- **hallucinated citations**: a cited file or line that does not exist in the shown sources, or a citation used for code that is not shown;
- **wrong citations**: the line exists but does not support the claim it is attached to.
Groundedness for these two tasks should drop sharply with each hallucinated or wrong citation.
"""
