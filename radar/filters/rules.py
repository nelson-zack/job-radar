from __future__ import annotations
import os, re
import yaml
from typing import Any
from datetime import datetime, timedelta, timezone

# Debug flag and helper for rules
RADAR_DEBUG_RULES = os.getenv("RADAR_DEBUG_RULES", "0") == "1"
def _dbg(reason: str) -> None:
    if RADAR_DEBUG_RULES:
        print(f"[rules] {reason}")

# --- Engineering title heuristics (broadened, with false-positive guards) ---
CORE_SWE_HINTS = re.compile(
    r"\b(software|full[- ]?stack|fullstack|front[- ]?end|frontend|back[- ]?end|backend|platform|web|mobile|ios|android|data|ml|machine\s*learning|devops|swe|sre|site\s*reliability|security|infrastructure)\b",
    re.I,
)
GENERIC_ENGINEER = re.compile(r"\b(engineer|developer)\b", re.I)
# Exclude common non-SWE variants unless paired with core SWE hints
NON_SWE_ENGINEER = re.compile(
    r"\b(sales|account|customer|support|success|implementation|solutions|field|pre[- ]?sales|professional\s*services|broadcast|audio|video|a\/?v|av)\s+(engineer|engineering)\b",
    re.I,
)
SENIOR_BLOCK = re.compile(r"\b(senior|staff|principal|lead|manager|architect|s\.?r\.?)\b", re.I)

# Explicit junior-looking titles (used by providers and ranking)
JUNIOR_TITLE = re.compile(
    r"""(?xi)
    \b(
        junior
        |new\s*grad
        |entry[\-\s]*level
        |associate
        |(?:software|swe|sde|se|developer|engineer)\s*(?:i|1|i\.)
    )\b
    """
)

# Explicit level II/2 titles (generally not junior unless the description contradicts)
ENGINEER_L2 = re.compile(r"\b((software|swe|sde|se|developer|engineer)\s*(ii|2))\b", re.I)

JUNIOR_POSITIVE = re.compile(
    r"\b(junior|new\s*grad|entry\s*level|entry-level|associate|software\s*engineer\s*i|software\s*engineer\s*1|swe\s*[i1]|sde\s*[i1]|se\s*[i1]|level\s*1|l1|ic1|graduate\s*(program)?|university\s*grad(uate)?)\b",
    re.I,
)

YEARS_0_TO_3 = re.compile(
    r"""(?xi)
    # Numeric ranges and simple counts up to 3 years
    (?:
        \b(?:0|1|2|3)(?:\s*[-–]\s*(?:1|2|3))?\s*(?:years?|yrs?)\s*(?:of\s*experience|exp|yoe)?\b
        |\b(?:0|1|2|3)\s*\+\s*(?:years?|yrs?)\b
        |\b(?:up\s*to|≤|<=)\s*3\s*(?:years?|yrs?)\b
        |\b(?:zero|one|two|three)(?:\s*(?:to|[-–])\s*(?:one|two|three))?\s*(?:years?|yrs?)\b
    )
    """
)

# Negatives for descriptions: 4+ years or explicit seniority in text
DESC_4PLUS_YEARS = re.compile(
    r"""(?xi)
    # 4+ years, including word forms and ranges that start at 4 or above
    \b(
        (?:4|5|6|7|8|9|1[0-9])\s*(?:\+|plus)?\s*(?:years?|yrs?)\s*(?:of\s*experience|exp|yoe)?
        |(?:at\s*least|min(?:imum)?\s*of|min\.?\s*)?(?:4|four)\s*(?:years?|yrs?)
        |(?:4|four)\s*[-–]\s*(?:5|six|6|7|seven|8|eight|9|nine|1[0-9])\s*(?:years?|yrs?)
    )\b
    """
)
DESC_SENIOR_WORDS = re.compile(r"\b(senior|staff|principal|lead|architect|manager)\b", re.I)

# Additional positive junior-ish phrases in descriptions
JUNIOR_DESC_POSITIVES = (
    # generic phrases
    "junior",
    "new grad",
    "new college grad",
    "recent grad",
    "recent graduate",
    "recent college graduate",
    "fresh graduate",
    "entry level",
    "entry-level",
    "early career",
    "early in career",
    "college hire",
    "university graduate",
    "graduate role",
    "graduate program",
    "grad program",
    "apprentice",
    "apprenticeship",
    "apprenticeship programme",
    "intern to full-time",
    # explicit level-1 markers
    "engineer i",
    "developer i",
    "software engineer i",
    "level 1",
    "ic-1",
    "ic1",
    "l1",
    # friendly ranges
    "0-1 years", "0–1 years", "0 to 1 years",
    "0-2 years", "0–2 years", "0 to 2 years",
    "1-2 years", "1–2 years", "1 to 2 years",
    "1-3 years", "1–3 years", "1 to 3 years",
    # preference/wording variants
    "0-2 years preferred", "0–2 years preferred", "0 to 2 years preferred",
    "0-3 years preferred", "0–3 years preferred", "0 to 3 years preferred",
    "up to 2 years", "up to 3 years", "under 3 years", "less than 3 years",
    "preferred 0-2 years", "preferred 0–2 years",
    "early talent", "early talent program", "campus hire", "new college graduate",
    "graduate scheme", "rotation program", "rotational program",
    "entry role", "engineer 1", "developer 1", "software engineer 1"
)


def looks_like_engineering(title: str) -> bool:
    t = (title or "").strip()
    if not t:
        return False
    # Block obvious non-SWE engineer variants unless accompanied by core hints
    if NON_SWE_ENGINEER.search(t) and not CORE_SWE_HINTS.search(t):
        return False
    # Positive matches: core SWE hints or generic engineer/developer
    if CORE_SWE_HINTS.search(t):
        return True
    # Only allow generic "Engineer/Developer" when not in the non-SWE bucket
    if GENERIC_ENGINEER.search(t):
        return True
    return False


def is_junior_title_or_desc(title: str, description_html: str | None, relaxed: bool = False) -> bool:
    t = (title or "")
    # Hard block on senior-ish titles
    if SENIOR_BLOCK.search(t):
        _dbg(f"blocked by senior title: {t}")
        return False
    # "Engineer II / 2" is usually not junior unless description clearly says otherwise
    if ENGINEER_L2.search(t):
        if not (relaxed and description_html):
            _dbg("blocked by level II/2 title")
            return False
        else:
            # Require explicit junior signals in the description (≤3 YOE or junior phrases)
            _text = description_html.lower()
            if not (YEARS_0_TO_3.search(_text) or any(k in _text for k in JUNIOR_DESC_POSITIVES)):
                _dbg("blocked by level II/2 title (no junior positives in description)")
                return False
    # Guard: explicit level III/3 titles are not junior
    if re.search(r"\b(iii|3)\b", t, re.I):
        if not (relaxed and description_html and YEARS_0_TO_3.search(description_html.lower())):
            _dbg("blocked by level III/3 title")
            return False
    # Positive title hints
    if JUNIOR_TITLE.search(t) or YEARS_0_TO_3.search(t):
        _dbg(f"accepted by title: {t}")
        return True

    # If not relaxed or no description, stop here
    if not relaxed or not description_html:
        _dbg("no desc or not relaxed; title alone didn't qualify")
        return False

    text = description_html.lower()

    # Negative guards in description: 4+ years or explicit senior terms
    if DESC_4PLUS_YEARS.search(text):
        _dbg("blocked by 4+ years in description")
        return False
    if DESC_SENIOR_WORDS.search(text) and not any(k in text for k in JUNIOR_DESC_POSITIVES):
        _dbg("blocked by senior words in description without junior positives")
        return False

    # Positive desc signals (junior phrases or <=3 years)
    if any(k in text for k in JUNIOR_DESC_POSITIVES):
        _dbg("accepted by junior-positive phrase in description")
        return True
    if YEARS_0_TO_3.search(text):
        _dbg("accepted by <=3 years in description")
        return True

    _dbg("no junior signals found")
    return False


def looks_remote_us(location: str | None, description_html: str | None) -> bool:
    def _usish(txt: str) -> bool:
        t = txt.lower()
        return any(kw in t for kw in [
            "united states", "u.s.", "usa", "u.s.a", "us only", "remote - us", "remote (us)", "us-remote", "remote/us"
        ])

    NON_US_MARKERS = [
        "canada", "canadian", "toronto", "vancouver", "montreal",
        "united kingdom", "uk", "europe", "eu", "emea", "apac", "australia", "new zealand", "nz",
        "mexico", "latam", "brazil", "argentina", "colombia", "chile", "peru",
        "india", "singapore", "philippines",
        "africa", "south africa", "nigeria", "mena", "uae", "dubai", "middle east",
        "germany", "france", "spain", "italy", "portugal", "netherlands", "belgium",
        "sweden", "norway", "denmark", "finland", "ireland", "poland", "romania"
    ]

    def _has_non_us_remote(txt: str) -> bool:
        t = txt.lower()
        return "remote" in t and any(m in t for m in NON_US_MARKERS) and not _usish(t)

    # Prefer explicit positives, but block explicit non‑US remotes
    if location:
        loc = location.lower()
        if _has_non_us_remote(loc):
            return False
        if "remote" in loc and _usish(loc):
            return True

    if description_html:
        text = description_html.lower()
        if _has_non_us_remote(text):
            return False
        if "remote" in text and _usish(text):
            return True

    return False


def is_recent(posted_at: datetime | None, days: int = 7) -> bool:
    """Return True if `posted_at` is within the last `days` days (UTC).
    Expects a naive UTC datetime (providers normalize to naive).
    """
    if not posted_at:
        return False
    try:
        now = datetime.now(timezone.utc)
        # If posted_at is naive, assume it's UTC; otherwise compare directly
        if posted_at.tzinfo is None:
            return (now.replace(tzinfo=None) - posted_at) <= timedelta(days=days)
        return (now - posted_at) <= timedelta(days=days)
    except Exception:
        return False


# --- YAML rules loader (Phase 2 support) ---
def load_rules_file(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data
