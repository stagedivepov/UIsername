"""Geração de usernames (sem UI e sem rede)."""
import re

from core.config import SUFFIXES, PREFIXES
from core.platform_base import Platform
from core.utils import rng, slug_words, strip_accents
from words import VERBS_EN, VERBS_PT, VERBS_ES, SUFFIXES_PT, PREFIXES_PT, SUFFIXES_ES, PREFIXES_ES


def generate_random(p: Platform, length: int) -> str:
    if length < 1:
        return ""
    return (rng.choice(p.first_chars or p.random_chars)
            + "".join(rng.choice(p.random_chars) for _ in range(length - 1)))


def generate_from_verbs(p: Platform, verbs, two_words=False, digits=True, use_sep=False) -> str:
    name = ""
    for _ in range(50):
        # com 2 verbos, sorteia dois DIFERENTES entre si
        words = rng.sample(verbs, 2) if two_words else [rng.choice(verbs)]
        if p.style == "title":
            words = [w.capitalize() for w in words]
        name = (p.sep if use_sep and two_words else "").join(words)
        if digits:
            # número de tamanho variável: 1 a 4 dígitos (ex: 7, 42, 815, 9034)
            name += str(rng.randint(0, 10 ** rng.choice((1, 2, 3, 4)) - 1))
        name = strip_accents(name)
        if p.local_ok(name):
            return name
    return name[:p.max_len]


def generate_from_name(p: Platform, text: str, suffixes=True, digits=True, language="en") -> str:
    """Sugestões a partir de um nome, com sufixos/prefixos profissionais."""
    words = slug_words(text) or ["user"]
    first, last = words[0], words[-1]
    bases = list({"".join(words), p.sep.join(words), first, last, first + last, last + first,
                  first[0] + last, first + last[0]})
    sep, cand = p.sep, ""
    endings, beginnings = {"pt": (SUFFIXES_PT, PREFIXES_PT),
                           "es": (SUFFIXES_ES, PREFIXES_ES)}.get(language, (SUFFIXES, PREFIXES))
    for _ in range(40):
        cand = rng.choice(bases)
        if suffixes:
            style = rng.choice(["suffix", "suffix_sep", "prefix", "none"])
            if style == "suffix":
                cand += rng.choice(endings)
            elif style == "suffix_sep":
                cand += sep + rng.choice(endings)
            elif style == "prefix":
                cand = rng.choice(beginnings) + cand
        if digits and rng.random() < 0.6:
            cand += str(rng.randint(1, 999))
        cand = re.sub(re.escape(sep) + "{2,}", sep, cand).strip(sep)[:p.max_len].strip(sep)
        if p.local_ok(cand):
            return cand
    return cand


def generate_username(p: Platform, cfg: dict) -> str:
    mode = cfg["mode"]
    if mode == "random":
        return generate_random(p, cfg["length"])
    if mode == "name":
        return generate_from_name(p, cfg["base_name"], cfg["suffixes"], cfg["digits"], cfg.get("name_language", "en"))
    verbs = {"en": VERBS_EN, "pt": VERBS_PT, "es": VERBS_ES}[mode]
    return generate_from_verbs(p, verbs, cfg["two_words"], cfg["digits"], cfg["use_sep"])
