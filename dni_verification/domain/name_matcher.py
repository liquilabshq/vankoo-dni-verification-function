import re
import unicodedata

from dni_verification.domain.models import ProvidedName, RegisteredName


def _tokens(text: str) -> list[str]:
    """Upper-case, accent-free words: 'José  Ñañez' -> ['JOSE', 'NANEZ']."""
    decomposed = unicodedata.normalize("NFKD", text)
    letters = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.findall(r"[A-Z]+", letters.upper())


def names_match(provided: ProvidedName, registered: RegisteredName) -> bool:
    """Whether the declared name is the one the registry holds.

    Tolerant on purpose: ignores case, accents and word order, and accepts a partial
    declaration (only the first of several given names, only the paternal surname).
    It is strict on identity: every declared word must exist in the registry, and the
    whole paternal surname must be declared.
    """
    first = set(_tokens(provided.first_name))
    last = set(_tokens(provided.last_name))
    if not first or not last:
        return False

    registered_first = set(_tokens(registered.first_names))
    paternal = set(_tokens(registered.paternal_surname))
    registered_last = paternal | set(_tokens(registered.maternal_surname))

    return first <= registered_first and last <= registered_last and paternal <= last
