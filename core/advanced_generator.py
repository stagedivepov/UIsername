"""Compiled local patterns, bounded incremental generation, no network access."""
import math
import re
import string
import threading
from dataclasses import dataclass
from core.utils import rng, strip_accents
from words import VERBS_EN, VERBS_PT, VERBS_ES

VOCAB = {'en': VERBS_EN, 'pt': VERBS_PT, 'es': VERBS_ES}
VOWELS = 'aeiou'
CONSONANTS = ''.join(c for c in string.ascii_lowercase if c not in VOWELS)
DEFAULT_RULES = dict(pattern='LLLL', min_length=1, max_length=20, lowercase=True,
                     uppercase=True, numbers=True, underscores=True, allowed='', forbidden='',
                     prefixes='', suffixes='', max_consecutive_digits=4, require_vowel=False,
                     require_consonant=False, no_adjacent_repeat=False, no_repeated_sequences=False,
                     no_numeric_sequences=False, pronounceable=False, banned_words='', language='en',
                     amount=100, max_attempts=100000)
PRESETS = {
    'minimal': ('Minimal', {'pattern': 'LLLL', 'max_length': 4}),
    'short': ('Short Names', {'pattern': 'LL#', 'max_length': 3}),
    'aesthetic': ('Aesthetic', {'pattern': 'word_###', 'max_length': 20}),
    'gaming': ('Gaming', {'pattern': 'prefix+word+##', 'prefixes': 'neo, epic, nova'}),
    'numeric': ('Numeric', {'pattern': '######', 'max_length': 6, 'max_consecutive_digits': 6}),
    'dictionary': ('Dictionary', {'pattern': 'word', 'max_length': 20}),
    'pronounceable': ('Pronounceable', {'pattern': 'CVCVCV', 'pronounceable': True, 'max_length': 6}),
    'custom': ('Custom', {})
}


def presets():
    return [{'id': 'builtin:' + key, 'name': name, 'rules': {**DEFAULT_RULES, **rules}, 'builtin': True}
            for key, (name, rules) in PRESETS.items()]


def _list(value):
    return list(dict.fromkeys(x.strip() for x in re.split(r'[,;\n]+', value) if x.strip()))


@dataclass(frozen=True)
class Pattern:
    rules: dict
    choices: tuple
    raw_space: int
    fixed_width: bool

    def candidate(self, index):
        parts = []
        for values in reversed(self.choices):
            index, offset = divmod(index, len(values)); parts.append(values[offset])
        return ''.join(reversed(parts))

    def accepts(self, value):
        r = self.rules
        if not r['min_length'] <= len(value) <= r['max_length']: return False
        if any(c not in r['_alphabet'] for c in value): return False
        lower = value.lower()
        if r['require_vowel'] and not any(c in VOWELS for c in lower): return False
        if r['require_consonant'] and not any(c in CONSONANTS for c in lower): return False
        if re.search(r'\d{' + str(r['max_consecutive_digits'] + 1) + ',}', value): return False
        if r['no_adjacent_repeat'] and re.search(r'(.)\1', value, re.I): return False
        if r['no_repeated_sequences'] and re.search(r'(.{2,})\1', value, re.I): return False
        if r['no_numeric_sequences'] and any(any(value[i:i+3] in sequence for sequence in ('0123456789', '9876543210'))
                                            for i in range(max(0, len(value)-2)) if value[i:i+3].isdigit()): return False
        if any(word in lower for word in r['_banned']): return False
        if r['pronounceable']:
            letters = [c for c in lower if c.isalpha()]
            if not letters or any((a in VOWELS) == (b in VOWELS) for a,b in zip(letters, letters[1:])): return False
        return True

    def estimate(self, stop=None):
        if self.raw_space <= 20000:
            unique = set()
            for index in range(self.raw_space):
                if stop and stop.is_set(): return {'kind': 'cancelled', 'value': None}
                value = self.candidate(index)
                if self.accepts(value): unique.add(value)
            return {'kind': 'exact', 'value': str(len(unique))}
        r = self.rules
        simple = self.fixed_width and all(len(set(values)) == len(values) for values in self.choices)
        simple = simple and not any(r[key] for key in ('require_vowel', 'require_consonant', 'no_adjacent_repeat',
                              'no_repeated_sequences', 'no_numeric_sequences', 'pronounceable', '_banned'))
        possible_digits = sum(max(sum(c.isdigit() for c in value) for value in values) for values in self.choices)
        simple = simple and possible_digits <= r['max_consecutive_digits']
        return {'kind': 'exact' if simple else 'upper_bound', 'value': str(self.raw_space)}


def compile_pattern(patch):
    if not isinstance(patch, dict): raise ValueError('Regras inválidas.')
    unknown = set(patch) - set(DEFAULT_RULES)
    if unknown: raise ValueError('Regra desconhecida: ' + ', '.join(sorted(unknown)))
    r = {**DEFAULT_RULES, **patch}
    for key in ('min_length','max_length','max_consecutive_digits','amount','max_attempts'):
        if type(r[key]) is not int: raise ValueError('Use números inteiros nas regras.')
    if not 1 <= r['min_length'] <= r['max_length'] <= 255: raise ValueError('Comprimentos devem estar entre 1 e 255.')
    if not 0 <= r['max_consecutive_digits'] <= 255 or not 1 <= r['amount'] <= 10000 or not 1 <= r['max_attempts'] <= 1000000:
        raise ValueError('Quantidade ou limite de tentativas inválido.')
    for key, default in DEFAULT_RULES.items():
        if type(default) is bool and type(r[key]) is not bool: raise ValueError('Opção inválida: ' + key)
        if isinstance(default, str) and (not isinstance(r[key], str) or len(r[key]) > 4000): raise ValueError('Texto inválido: ' + key)
    if r['language'] not in VOCAB: raise ValueError('Idioma de palavras inválido.')
    if not r['pattern'] or len(r['pattern']) > 128: raise ValueError('Padrão deve ter de 1 a 128 caracteres.')
    alphabet = (string.ascii_lowercase if r['lowercase'] else '') + (string.ascii_uppercase if r['uppercase'] else '')
    alphabet += (string.digits if r['numbers'] else '') + ('_' if r['underscores'] else '')
    if r['allowed']:
        # Additional punctuation is explicit, category switches remain authoritative.
        alphabet += ''.join(c for c in r['allowed'] if c.isascii() and c.isprintable() and not c.isspace() and not c.isalnum() and c != '_')
        alphabet = ''.join(c for c in alphabet if c in r['allowed'])
    alphabet = ''.join(c for c in dict.fromkeys(alphabet) if c not in r['forbidden'])
    if not alphabet: raise ValueError('Nenhum caractere permitido pelas regras.')
    r['_alphabet'] = alphabet; r['_banned'] = [x.lower() for x in _list(r['banned_words'])]
    groups = {'L': string.ascii_lowercase, 'U': string.ascii_uppercase, '?': string.ascii_letters,
              '#': string.digits, 'C': CONSONANTS, 'V': VOWELS}
    words = list(dict.fromkeys(strip_accents(x).lower() for x in VOCAB[r['language']]))
    groups.update(word=words, prefix=_list(r['prefixes']), suffix=_list(r['suffixes']))
    pattern, tokens, i = r['pattern'], [], 0
    while i < len(pattern):
        c = pattern[i]
        if c == '\\':
            i += 1
            if i == len(pattern): raise ValueError('Escape incompleto no padrão.')
            values = [pattern[i]]; i += 1
        elif c == '+': i += 1; continue
        elif c == '{':
            end = pattern.find('}', i)
            if end == -1 or pattern[i+1:end] not in ('word','prefix','suffix'): raise ValueError('Token entre chaves inválido.')
            key = pattern[i+1:end]; values = groups[key]; i = end+1
        elif c in groups and len(c) == 1: values = list(groups[c]); i += 1
        else:
            key = next((key for key in ('prefix','suffix','word') if pattern.startswith(key, i)
                        and (i+len(key) == len(pattern) or not pattern[i+len(key)].isalpha())), None)
            if key: values = groups[key]; i += len(key)
            elif c == '}': raise ValueError('Chave inesperada no padrão.')
            else: values = [c]; i += 1
        values = tuple(dict.fromkeys(value for value in values if value and all(c in alphabet for c in value)))
        if not values: raise ValueError('Um token não possui opções compatíveis com os caracteres permitidos.')
        tokens.append(values)
    if not tokens: raise ValueError('O padrão não contém caracteres.')
    shortest = sum(min(map(len, values)) for values in tokens)
    longest = sum(max(map(len, values)) for values in tokens)
    if shortest > r['max_length'] or longest < r['min_length']: raise ValueError('Padrão incompatível com o comprimento configurado.')
    # Remove impossible length choices for a fixed-width pattern.
    if shortest == longest and not r['min_length'] <= shortest <= r['max_length']: raise ValueError('Comprimento impossível.')
    if r['require_vowel'] and not any(any(c.lower() in VOWELS for c in v) for t in tokens for v in t): raise ValueError('O padrão não permite vogais.')
    if r['require_consonant'] and not any(any(c.lower() in CONSONANTS for c in v) for t in tokens for v in t): raise ValueError('O padrão não permite consoantes.')
    forced_run = 0
    for values in tokens:
        forced_run = forced_run + min(map(len, values)) if all(value.isdigit() for value in values) else 0
        if forced_run > r['max_consecutive_digits']: raise ValueError('O padrão exige mais números consecutivos do que o limite.')
    if r['require_vowel'] and r['require_consonant'] and longest < 2: raise ValueError('O comprimento não permite vogal e consoante simultaneamente.')
    compiled = Pattern(r, tuple(tokens), math.prod(map(len, tokens)), all(len(set(map(len,t))) == 1 for t in tokens))
    if all(len(t) == 1 for t in tokens) and not compiled.accepts(compiled.candidate(0)): raise ValueError('As regras rejeitam o único candidato do padrão.')
    return compiled


def generate(compiled, stop=None, progress=None, interval=0.0):
    stop = stop or threading.Event()
    estimate = compiled.estimate(stop)
    names, seen, attempts = [], set(), 0
    space = compiled.raw_space
    offset = rng.randrange(space)
    step = rng.randrange(1, space) if space > 1 else 1
    while math.gcd(step, space) != 1: step = (step + 1) % space or 1
    limit = min(space, compiled.rules['max_attempts'])
    while attempts < limit and len(names) < compiled.rules['amount']:
        if stop and stop.is_set(): break
        value = compiled.candidate((offset + attempts * step) % space); attempts += 1
        if value not in seen and compiled.accepts(value):
            seen.add(value); names.append(value)
            if interval > 0:
                if progress: progress(len(names), attempts)
                if len(names) < compiled.rules['amount'] and attempts < limit and stop.wait(interval): break
        if progress and attempts % 200 == 0: progress(len(names), attempts)
    cancelled = bool(stop and stop.is_set())
    return {'names': names, 'attempts': attempts, 'requested': compiled.rules['amount'], 'estimate': estimate,
            'status': 'cancelled' if cancelled else 'completed' if len(names) == compiled.rules['amount'] else 'exhausted' if attempts == space else 'attempt_limit'}
