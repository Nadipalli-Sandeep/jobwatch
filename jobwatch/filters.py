"""Decide if a job fits: India, IT/software/AI/data role, 0-1 years experience."""
import re

# ---------- role (title must look like IT / software / data / AI) ----------
ROLE = re.compile(r"""\b(
    software|sde|swe|sdet|developer|programmer|coder|
    full[\s-]?stack|front[\s-]?end|back[\s-]?end|web|mobile|android|ios|flutter|
    devops|devsecops|sre|site\ reliability|cloud|platform|infrastructure|
    data|database|dba|etl|big\ data|
    machine\ learning|ml|mlops|ai|a\.i\.|artificial\ intelligence|deep\ learning|
    nlp|computer\ vision|vision|gen\s?ai|generative|llm|agentic|
    analytics|quant\w*|statistic\w*|
    (data|business|systems?|technology|technical|programmer|product|security|cyber|soc|bi|mis|
     reporting|software|it|application|research|risk\ analytics|decision)\ analyst|
    (data|applied|research|ml|machine\ learning|ai|decision|computer|nlp)\ scientist|
    research\ (engineer|intern|associate|software|fellow)|applied\ research|
    security|cyber|soc|application\ security|
    qa|quality\ assurance|tester|testing|test\ engineer|automation|
    python|java|javascript|typescript|golang|go\ developer|c\+\+|\.net|dotnet|react|angular|node(js)?|
    salesforce\ developer|sap\ (abap|developer|technical)|servicenow|
    embedded\ software|firmware|
    systems?\ engineer|application\ (engineer|developer)|product\ engineer|
    solutions?\ engineer|network\ engineer|it|tech|technology|technical|phd\ intern|research\ phd|
    programmer\ analyst|engineer\ trainee|graduate\ engineer|associate\ engineer|
    member\ of\ technical\ staff|mts
)\b""", re.I | re.X)

# Clear non-IT roles. Checked on the title.
NOT_IT = re.compile(r"""\b(
    sales|marketing|recruit\w*|talent\ acquisition|hr|human\ resources?|payroll|
    telecall\w*|voice\ process|customer\ (care|support|service)|call\ cent(er|re)|bpo|
    data\ entry|field\ (executive|officer)|driver|delivery\ (boy|executive|associate|partner)|
    teacher|tutor|faculty|professor|nurse|nursing|pharmacist|doctor|physician|medical\ (officer|representative)|
    chef|cook|steward|housekeeping|front\ office|receptionist|accountant|accounts\ (executive|payable|receivable)|
    mechanical|civil|chemical|electrical\ (engineer|maintenance)|process\ engineer|maintenance|production|
    plant|store\ keeper|warehouse|picker|packer|security\ guard|legal|lawyer|counsel|paralegal|
    collections?|relationship\ manager|branch|teller|underwriter|actuar\w*|audit\w*|tax|
    content\ writer|copywriter|graphic\ designer|video\ editor|social\ media|
    clinical|regulatory|pharmacovigilance|medical\ (writer|coder|coding)|drug\ safety|
    kyc|aml|credit|financial\ analyst|finance\ analyst|operations\ analyst|fund\ accounting|
    reconciliation|treasury|procurement|supply\ chain|logistics|purchase|insurance\ (advisor|agent)|
    non[\s-]?tech\w*|technician|market\ research|data\ cent(er|re)\ (operations|technician)|
    cash|trade\ (proc\w*|support)|operations?\ support|transactions?|content\ (associate|moderat\w*)
)\b""", re.I | re.X)
_REAL_IT = re.compile(r"software|developer|data\s+(scien|engineer|analy)|machine learning|\bai\b|\bml\b", re.I)

# Too senior for 0 years. Checked on the title.
SENIOR = re.compile(r"""(
    \b(senior|sr|snr|lead|leader|principal|staff|manager|mgr|director|head|architect|
       vp|avp|svp|vice\ president|chief|distinguished|fellow|expert|specialist\ iii)\b|
    \b(ii|iii|iv|v)\b|
    \b(engineer|developer|sde|swe|scientist|analyst|consultant)[\s-]*(2|3|4|5)\b|
    \bsde[\s-]?(2|3)\b|\bl[4-9]\b|\b(ic|p)[3-6]\b|
    \b([2-9]|1[0-9])\s*\+?\s*(yrs?|years?)
)""", re.I | re.X)

# Strong "this is for freshers / students" signals.
FRESH_TITLE = re.compile(r"""\b(
    intern|internship|trainee|apprentice|fresher|freshers|graduate|new\ grad|grad|
    campus|university|entry[\s-]?level|early\ career|junior|jr|
    associate\ (software|engineer|developer|data|consultant|analyst)|
    (sde|swe|engineer|developer|analyst|scientist)[\s-]?(i|1)\b|
    20(26|27)|batch|summer|winter|co-?op|phd\ intern|research\ intern
)\b""", re.I | re.X)

# Title words that mean "students / new grads" even if the text mentions years.
STRONG_FRESH_TITLE = re.compile(r"""\b(
    intern|internship|trainee|apprentice|fresher|freshers|new\ grad|graduate|campus|
    university|entry[\s-]?level|early\ career|20(26|27)|summer|co-?op
)\b""", re.I | re.X)

FRESH_TEXT = re.compile(r"""(
    \bfreshers?\b|\bnew\ grad|\b20(26|27)\s*(batch|grad|pass|graduat)|
    \bgraduating\ in\ 20(26|27)|\bclass\ of\ 20(26|27)|\bearly\ career\b|\bentry[\s-]level\b|
    \b0\s*(-|–|to)\s*[12]\s*(yrs?|years?)|\bno\ (prior\ )?experience\ (is\ )?required|
    \bcampus\ (hire|hiring|recruit)
)""", re.I | re.X)

INTERN = re.compile(r"\b(intern|internship|summer\s+analyst|co-?op|apprentice)\b", re.I)

# "3+ years", "2-5 years", "minimum of 4 yrs", "at least 2 years"
_YEARS = re.compile(
    r"(\d{1,2})(?:\.\d)?\s*(?:\+|plus)?\s*(?:(?:-|–|—|to)\s*(\d{1,2})\s*)?\+?\s*(?:years?|yrs?)",
    re.I)
_EXP_WORD = re.compile(r"experien|exp\b|work(ing)?\s+in|industry|hands[\s-]on|relevant", re.I)

INDIA = re.compile(r"""\b(
    india|bharat|bengaluru|bangalore|hyderabad|secunderabad|chennai|pune|mumbai|bombay|navi\ mumbai|thane|
    delhi|new\ delhi|ncr|gurgaon|gurugram|noida|greater\ noida|ghaziabad|faridabad|kolkata|calcutta|
    ahmedabad|gandhinagar|vadodara|surat|kochi|cochin|trivandrum|thiruvananthapuram|coimbatore|madurai|
    mysore|mysuru|mangalore|mangaluru|hubli|jaipur|indore|bhopal|chandigarh|mohali|panchkula|nagpur|
    visakhapatnam|vizag|vijayawada|tirupati|warangal|bhubaneswar|lucknow|kanpur|patna|ranchi|goa|
    dehradun|nashik|aurangabad|raipur|guwahati|ind
)\b""", re.I | re.X)


def is_india(location: str, country: str = "") -> bool:
    c = (country or "").strip().lower()
    if c in ("in", "ind", "india"):
        return True
    return bool(INDIA.search(location or ""))


def title_ok(title: str):
    """Return (ok, reason)."""
    t = title or ""
    if not ROLE.search(t):
        return False, "not IT role"
    if re.search(r"data\s+entry", t, re.I):
        return False, "non-IT role"
    if NOT_IT.search(t) and not _REAL_IT.search(t):
        return False, "non-IT role"
    if SENIOR.search(t):
        return False, "senior title"
    return True, ""


def min_years(text: str):
    """Smallest 'N years' that talks about experience. None if not found."""
    if not text:
        return None
    found = []
    for m in _YEARS.finditer(text):
        lo = int(m.group(1))
        if lo > 20:
            continue
        window = text[max(0, m.start() - 90): m.end() + 90]
        if _EXP_WORD.search(window):
            found.append(lo)
    return min(found) if found else None


def classify(title: str, desc: str = "", entry_hint: bool = False):
    """Return (keep, tag, years). tag is a short label for the alert."""
    ok, _ = title_ok(title)
    if not ok:
        return False, "", None
    yrs = min_years(desc)
    fresh_t = bool(FRESH_TITLE.search(title or ""))
    strong_t = bool(STRONG_FRESH_TITLE.search(title or ""))
    fresh_d = bool(FRESH_TEXT.search(desc or ""))
    if yrs is not None and yrs >= 2 and not strong_t:
        return False, "", yrs
    if INTERN.search(title or ""):
        return True, "INTERNSHIP", yrs
    if yrs == 1 and not strong_t:
        return True, "0-1 YRS", yrs
    if fresh_t or fresh_d or yrs == 0:
        return True, "FRESHER", yrs
    if entry_hint:
        return True, "ENTRY LEVEL", yrs
    return True, "EXP NOT STATED", yrs
