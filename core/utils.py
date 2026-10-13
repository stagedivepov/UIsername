"""Funções auxiliares sem dependência de UI."""
import random
import re
import unicodedata

rng = random.SystemRandom()   # aleatoriedade "de verdade" do sistema operacional


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def slug_words(text: str):
    """'João da Silva' -> ['joao', 'da', 'silva']"""
    text = re.sub(r"[^a-z0-9]+", " ", strip_accents(text).lower())
    return text.split()
