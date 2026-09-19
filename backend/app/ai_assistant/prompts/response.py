"""Response prompt wording.

The response node rephrases verified tool facts. Wording hint only —
nodes/response.py validates claims against tool results before sending.
"""
RESPONSE_INSTRUCTIONS = (
    "Rephrase the given verified facts helpfully in at most 120 words. "
    "Use only the facts provided. Never invent doctors, slots, times, records, "
    "or medical facts. Refer to patient symptoms only as what was reported. "
    "Never diagnose, prescribe, or recommend treatment."
)
