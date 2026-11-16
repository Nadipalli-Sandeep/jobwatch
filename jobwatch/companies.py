"""Load the company list and match job-board company names to it.

LinkedIn writes names in its own way ("JPMorganChase", "Citi", "Sun Pharma"),
so each list entry gets several aliases.
"""
import re
from pathlib import Path

from .common import ascii_fold

DATA = Path(__file__).resolve().parent.parent / "data"

# Words that carry no meaning for matching. Removed from both sides.
_FILLER = {
    "india", "indian", "limited", "ltd", "pvt", "private", "inc", "llc", "llp",
    "plc", "corporation", "corp", "company", "co", "the", "group", "technologies",
    "technology", "solutions", "services", "service", "global", "in", "of", "and",
    "centre", "center", "labs", "lab",
}

# Aliases that are too generic to trust after filler words are removed.
_GENERIC = {"health", "finance", "energy", "power", "motors", "capital", "bank",
            "digital", "foods", "software", "systems", "consulting", "international"}

# Different companies whose names start like a list company.
_LOOKALIKES = {"zeta global", "jupiter wagons", "dr reddys foundation"}

# Extra names seen on LinkedIn / career sites. Key = exact line in companies.txt.
EXTRA_ALIASES = {
    "Tata Consultancy Services (TCS)": ["TCS"],
    "HCLTech": ["HCL Technologies", "HCL Tech", "HCL"],
    "LTIMindtree": ["LTI Mindtree", "Mindtree"],
    "LTTS (L&T Technology Services)": ["L&T Technology Services", "LTTS"],
    "Accenture India": ["Accenture in India", "Accenture"],
    "Cognizant India": ["Cognizant Technology Solutions"],
    "NTT DATA India": ["NTT DATA", "NTT DATA Inc", "NTT DATA Services"],
    "EPAM Systems India": ["EPAM", "EPAM Anywhere"],
    "Thoughtworks India": ["Thoughtworks"],
    "UST": ["UST Global"],
    "Oracle Financial Services Software (OFSS)": ["Oracle Financial Services"],
    "Zoho Corporation": ["Zoho"],
    "Yellow.ai": ["Yellow ai"],
    "Gnani.ai": ["Gnani ai"],
    "observe.ai": ["Observe ai", "Observe.AI"],
    "Fractal Analytics": ["Fractal"],
    "Krutrim": ["Ola Krutrim", "Krutrim SI Designs"],
    "Google India": ["Google", "Google DeepMind", "YouTube"],
    "Amazon India": ["Amazon", "Amazon Web Services (AWS)", "AWS", "Amazon Development Centre"],
    "Meta India": ["Meta"],
    "SAP Labs India": ["SAP", "SAP Labs"],
    "VMware (Broadcom) India": ["VMware"],
    "Cisco India": ["Cisco", "Cisco Systems"],
    "Palo Alto Networks India": ["Palo Alto Networks"],
    "HP Inc. India": ["HP", "HP Inc"],
    "Hewlett Packard Enterprise (HPE) India": ["Hewlett Packard Enterprise", "HPE", "Aruba"],
    "Intel India": ["Intel", "Intel Corporation"],
    "AMD India": ["AMD", "Advanced Micro Devices"],
    "Texas Instruments India": ["Texas Instruments", "TI"],
    "ARM India": ["Arm"],
    "Cadence Design Systems India": ["Cadence"],
    "Siemens EDA India": ["Siemens EDA", "Siemens Digital Industries Software"],
    "Samsung R&D Institute India": ["Samsung R&D Institute India - Bangalore",
                                    "Samsung R&D Institute India - Noida",
                                    "Samsung R&D Institute Delhi", "SRI-B", "SRI-Noida"],
    "Samsung Semiconductor India Research": ["Samsung Semiconductor India Research (SSIR)",
                                             "Samsung Semiconductor"],
    "LG Soft India": ["LG Soft India Pvt Ltd", "LG Electronics India Software"],
    "Bosch Global Software Technologies": ["Bosch Global Software Technologies Private Limited", "BGSW"],
    "Harman International India": ["HARMAN International", "HARMAN"],
    "Honeywell Technology Solutions India": ["Honeywell"],
    "GE HealthCare India": ["GE HealthCare", "GE Healthcare"],
    "GE Aerospace India": ["GE Aerospace"],
    "GE Vernova India": ["GE Vernova"],
    "Philips India": ["Philips"],
    "Becton Dickinson (BD) India": ["BD", "Becton, Dickinson and Company"],
    "Johnson & Johnson India": ["Johnson & Johnson", "Johnson & Johnson Innovative Medicine",
                                "Johnson & Johnson MedTech", "J&J"],
    "Merck India": ["MSD", "Merck", "Merck Group"],
    "Bristol Myers Squibb India": ["Bristol Myers Squibb", "BMS"],
    "Eli Lilly India": ["Eli Lilly and Company", "Lilly"],
    "Sun Pharmaceutical Industries": ["Sun Pharma"],
    "Dr. Reddy's Laboratories": ["Dr. Reddy's", "Dr Reddys"],
    "1mg (Tata 1mg)": ["Tata 1mg"],
    "Cure.fit (Cult.fit)": ["cult.fit", "Curefit"],
    "JPMorgan Chase & Co. India": ["JPMorganChase", "JPMorgan Chase", "J.P. Morgan", "JP Morgan"],
    "Goldman Sachs India": ["Goldman Sachs"],
    "Bank of America India": ["Bank of America", "BofA"],
    "Citibank India": ["Citi", "Citigroup", "Citicorp"],
    "Barclays India": ["Barclays"],
    "Deutsche Bank India": ["Deutsche Bank"],
    "BNP Paribas India": ["BNP Paribas", "BNP Paribas India Solutions"],
    "Société Générale India": ["Societe Generale", "Societe Generale Global Solution Centre", "SG GSC"],
    "Credit Agricole India": ["Credit Agricole CIB", "Credit Agricole Corporate and Investment Bank"],
    "BNY Mellon India": ["BNY"],
    "Fidelity Investments India": ["Fidelity Investments", "Fidelity International"],
    "D. E. Shaw India": ["The D. E. Shaw Group", "D. E. Shaw", "DE Shaw"],
    "Citadel Securities India": ["Citadel Securities", "Citadel"],
    "Sequoia Capital India (Peak XV Partners)": ["Peak XV Partners", "Peak XV"],
    "Matrix Partners India (Z47)": ["Z47", "Matrix Partners India"],
    "American Express India": ["American Express", "Amex"],
    "FIS Global India": ["FIS"],
    "NCR Voyix India": ["NCR Voyix", "NCR Atleos"],
    "S&P Global India": ["S&P Global", "S&P Global Market Intelligence"],
    "Moody's India": ["Moody's", "Moody's Corporation", "Moodys"],
    "LSEG (London Stock Exchange Group) India": ["LSEG", "London Stock Exchange Group"],
    "State Bank of India (SBI)": ["SBI", "State Bank of India"],
    "LIC (Life Insurance Corporation of India)": ["LIC", "Life Insurance Corporation of India"],
    "Max Life Insurance": ["Axis Max Life Insurance"],
    "Go Digit General Insurance": ["Digit Insurance", "Go Digit"],
    "Acko General Insurance": ["ACKO"],
    "Policybazaar (PB Fintech)": ["Policybazaar", "PB Fintech", "Policybazaar.com"],
    "Paytm (One97 Communications)": ["Paytm", "One97 Communications"],
    "Open Financial Technologies": ["Open", "Open Money"],
    "Fi Money": ["Fi", "epiFi"],
    "OneCard (FPL Technologies)": ["OneCard", "FPL Technologies"],
    "Navi Technologies": ["Navi"],
    "Nykaa (FSN E-Commerce)": ["Nykaa", "FSN E-Commerce Ventures"],
    "Ajio (Reliance Retail)": ["AJIO", "Reliance Retail"],
    "FirstCry (Brainbees Solutions)": ["FirstCry", "Brainbees Solutions"],
    "Mamaearth (Honasa Consumer)": ["Honasa Consumer", "Mamaearth"],
    "boAt (Imagine Marketing)": ["boAt", "Imagine Marketing"],
    "Zomato": ["Eternal", "Zomato"],
    "Blinkit": ["Blinkit", "Grofers"],
    "Ola Cabs (ANI Technologies)": ["Ola", "OLA", "ANI Technologies"],
    "Uber India": ["Uber"],
    "OYO Rooms": ["OYO"],
    "Indian Hotels Company Limited (IHCL - Taj)": ["IHCL", "Taj Hotels", "The Indian Hotels Company Limited"],
    "Jubilant FoodWorks (Domino's)": ["Jubilant FoodWorks"],
    "Box8 (EatClub)": ["EatClub", "Box8"],
    "Reliance Jio": ["Jio", "Jio Platforms", "Reliance Jio Infocomm"],
    "Bharti Airtel": ["Airtel", "Airtel Digital", "Airtel Payments Bank"],
    "Vodafone Idea": ["Vi", "Vodafone Idea Limited"],
    "Sterlite Technologies": ["STL", "STL - Sterlite Technologies Limited"],
    "Mahindra & Mahindra": ["Mahindra", "Mahindra Group"],
    "Larsen & Toubro (L&T)": ["L&T", "Larsen & Toubro", "L&T Construction"],
    "Lodha Group (Macrotech Developers)": ["Lodha", "Macrotech Developers"],
    "Royal Enfield (Eicher Motors)": ["Royal Enfield", "Eicher Motors"],
    "Motherson Group (Samvardhana Motherson)": ["Motherson", "Samvardhana Motherson"],
    "Sona BLW Precision Forgings (Sona Comstar)": ["Sona Comstar"],
    "Schlumberger (SLB) India": ["SLB", "Schlumberger"],
    "AtkinsRéalis India": ["AtkinsRealis", "Atkins"],
    "BHEL (Bharat Heavy Electricals Limited)": ["BHEL"],
    "ReNew": ["ReNew Power", "ReNew Energy Global"],
    "Trent (Zudio, Westside)": ["Trent", "Zudio", "Westside"],
    "Avenue Supermarts (DMart)": ["DMart", "Avenue Supermarts"],
    "Hindustan Unilever (HUL)": ["Hindustan Unilever", "HUL", "Unilever"],
    "ITC Limited": ["ITC", "ITC Infotech"],
    "Procter & Gamble (P&G) India": ["Procter & Gamble", "P&G"],
    "United Spirits (Diageo India)": ["Diageo", "Diageo India"],
    "Johnson & Johnson Consumer Health India (Kenvue)": ["Kenvue"],
    "Deloitte India": ["Deloitte", "Deloitte USI", "Deloitte South Asia"],
    "PwC India": ["PwC", "PwC Acceleration Centers", "PwC Acceleration Center India"],
    "EY India": ["EY", "EY GDS", "Ernst & Young", "EY Global Delivery Services"],
    "KPMG India": ["KPMG", "KPMG Global Services", "KPMG Delivery Network"],
    "McKinsey & Company India": ["McKinsey & Company", "McKinsey"],
    "Boston Consulting Group (BCG) India": ["Boston Consulting Group (BCG)", "BCG", "Boston Consulting Group"],
    "Bain & Company India": ["Bain & Company"],
    "ZS Associates India": ["ZS", "ZS Associates"],
    "IQVIA India": ["IQVIA"],
    "PPD (Thermo Fisher) India": ["PPD"],
    "Mazars in India": ["Forvis Mazars", "Mazars"],
    "Absolutdata (Infogain)": ["Infogain", "Absolutdata"],
    "MapmyIndia (CE Info Systems)": ["MapmyIndia", "Mappls"],
    "Hinduja Global Solutions (HGS)": ["HGS"],
    "Sutherland": ["Sutherland Global Services"],
    "Teleperformance India": ["Teleperformance", "TP"],
    "WNS Global Services": ["WNS"],
    "EXL Service": ["EXL"],
    "Course5 Intelligence": ["Course5i", "Course5 Intelligence"],
    "Tredence": ["Tredence Inc."],
    "Microsoft India": ["Microsoft", "LinkedIn", "GitHub"],
    "Salesforce India": ["Salesforce"],
    "Adobe India": ["Adobe"],
    "Oracle India": ["Oracle", "Oracle Health"],
    "Apple India": ["Apple"],
    "NVIDIA India": ["NVIDIA"],
}


def norm(name: str) -> str:
    s = ascii_fold(name).lower().replace("&", " and ").replace("'", "")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    words = [w for w in s.split() if w not in _FILLER]
    return " ".join(words)


def load_company_lines():
    lines = (DATA / "companies.txt").read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")]


def _aliases_for(line: str):
    out = {line}
    base = re.sub(r"\(.*?\)", "", line).strip()
    out.add(base)
    for inner in re.findall(r"\((.*?)\)", line):
        for part in re.split(r",| - ", inner):
            out.add(part.strip())
    out.update(EXTRA_ALIASES.get(line, []))
    return {a for a in out if a}


class CompanyMatcher:
    def __init__(self, lines=None):
        self.lines = lines or load_company_lines()
        self.exact = {}        # normalized alias -> canonical line
        self.joined = {}       # alias with spaces removed -> canonical line
        for line in self.lines:
            for a in _aliases_for(line):
                n = norm(a)
                if len(n) < 2 or n in _GENERIC:
                    continue
                self.exact.setdefault(n, line)
                self.joined.setdefault(n.replace(" ", ""), line)
        # Longest first so "tata consultancy" wins over "tata".
        self.prefixes = sorted(self.exact.items(), key=lambda kv: -len(kv[0]))

    def match(self, company_name: str):
        """Return the canonical list line, or None."""
        if not company_name:
            return None
        n = norm(company_name)
        if not n or n in _LOOKALIKES:
            return None
        if n in self.exact:
            return self.exact[n]
        j = n.replace(" ", "")
        if j in self.joined and len(j) >= 4:
            return self.joined[j]
        # "amazon web services aws" starts with alias "amazon"
        for alias, line in self.prefixes:
            if len(alias) >= 3 and n.startswith(alias + " "):
                return line
        return None
