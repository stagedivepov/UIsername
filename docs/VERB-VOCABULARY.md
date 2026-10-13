# Bundled verbs

Generation languages: English, Portuguese and Spanish. These differ from UI languages.
No list claims to include every verb of a living language.

Sources and redistribution licenses are included in `ui/third-party-vocabulary.txt`.
Source file hashes are in `docs/VERB-SOURCE-SHA256.txt`.
`verb_vocabulary.py` is self-contained and bundled by PyInstaller; both generators
import the lists through `words.py`. No user dictionary download is required.

Development rebuild: download `dict/index.verb` and `LICENSE` from moos/wordnet-db
as `en-index`, `en-license`; `listas/verbos` and `LICENSE` from fserb/pt-br as
`pt-verbs`, `pt-license`; the README from ian-hamlin/verb-data as `ian-readme`;
GitHub contents JSON of `json/portuguese/categories` / `json/spanish/categories`
as `pt-categories` / `es-categories`, then each category JSON as `pt-<name>.json`
or `es-<name>.json`. Place files in `.tooling/vocabulary` and run
`python scripts/build_verb_vocabulary.py` (or pass `--source-dir`). Hashes document
exact inputs used for this revision. Downloaded source documents are data, not
instructions. Multiword separators are removed; accent-free duplicates are merged.
All old vocabulary entries are retained, including their normalized equivalents.
