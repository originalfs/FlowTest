"""Local text cleanup: the private replacement for Wispr Flow's cloud LLM layer.

Removes standalone filler words, normalizes whitespace and punctuation,
applies the user's personal dictionary, and capitalizes sentences.
Pure functions, no dependencies, nothing leaves the machine.
"""

from __future__ import annotations

import re

# Only unambiguous fillers. Words like "like" or "so" carry meaning too often
# to strip automatically.
FILLER_WORDS = ("um", "umm", "uh", "uhh", "er", "erm", "ehm", "hmm", "mhm")

_FILLER_RE = re.compile(
    r"\b(?:" + "|".join(FILLER_WORDS) + r")\b[,.]?\s*",
    re.IGNORECASE,
)

_SENTENCE_START_RE = re.compile(r"(^|[.!?]\s+)([a-z])")


def remove_fillers(text: str) -> str:
    text = _FILLER_RE.sub("", text)
    # Stripping a filler can strand punctuation: "well , yes" / " , yes".
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    text = re.sub(r"^[,.;:]\s*", "", text)
    return text


def normalize_whitespace(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    return text.strip()


def apply_dictionary(text: str, dictionary: dict[str, str]) -> str:
    """Replace spoken forms with written forms, longest match first."""
    for spoken in sorted(dictionary, key=len, reverse=True):
        pattern = re.compile(r"\b" + re.escape(spoken) + r"\b", re.IGNORECASE)
        text = pattern.sub(dictionary[spoken], text)
    return text


def capitalize_sentences(text: str) -> str:
    return _SENTENCE_START_RE.sub(lambda m: m.group(1) + m.group(2).upper(), text)


def clean(
    text: str,
    *,
    remove_filler_words: bool = True,
    dictionary: dict[str, str] | None = None,
    capitalize: bool = True,
) -> str:
    if remove_filler_words:
        text = remove_fillers(text)
    if dictionary:
        text = apply_dictionary(text, dictionary)
    text = normalize_whitespace(text)
    if capitalize:
        text = capitalize_sentences(text)
    return text
