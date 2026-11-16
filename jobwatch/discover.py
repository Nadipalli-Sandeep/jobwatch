"""Find which career-site system each company uses, and save data/sources.json.

Run once (takes a few minutes):  py -3.12 -m jobwatch.discover
It probes Greenhouse / Lever / Ashby / SmartRecruiters / Workday / Eightfold /
Oracle with guessed names, and keeps only those that really answer.
"""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from .common import ascii_fold, get, post
from .companies import DATA, CompanyMatcher, load_company_lines, norm
from .sources import ats

# Hand-made guesses (from public career sites). Each is verified live below.
KNOWN = [
    # --- Eightfold / Oracle / custom APIs
    {"company": "Microsoft India", "type": "eightfold", "host": "apply.careers.microsoft.com", "domain": "microsoft.com", "sticky": True},
    {"company": "Netflix India", "type": "eightfold", "host": "explore.jobs.netflix.net", "domain": "netflix.com", "api": "v2"},
    {"company": "Qualcomm India", "type": "eightfold", "host": "careers.qualcomm.com", "domain": "qualcomm.com"},
    {"company": "Qualcomm India", "type": "eightfold", "host": "careers.qualcomm.com", "domain": "qualcomm.com", "api": "v2"},
    {"company": "American Express India", "type": "eightfold", "host": "aexp.eightfold.ai", "domain": "aexp.com"},
    {"company": "American Express India", "type": "eightfold", "host": "aexp.eightfold.ai", "domain": "aexp.com", "api": "v2"},
    {"company": "Micron Technology India", "type": "eightfold", "host": "micron.eightfold.ai", "domain": "micron.com"},
    {"company": "Oracle India", "type": "oracle", "host": "eeho.fa.us2.oraclecloud.com", "site": "CX_45001", "sticky": True},
    {"company": "JPMorgan Chase & Co. India", "type": "oracle", "host": "jpmc.fa.oraclecloud.com", "site": "CX_1001", "sticky": True},
    {"company": "Amazon India", "type": "amazon", "sticky": True},
]

# Workday guesses: (company line, tenant, [hosts wd numbers], [site names])
WORKDAY = [
    ("NVIDIA India", "nvidia", [5], ["NVIDIAExternalCareerSite"]),
    ("Salesforce India", "salesforce", [12], ["External_Career_Site"]),
    ("Adobe India", "adobe", [5], ["external_experienced", "external_university"]),
    ("Intel India", "intel", [1], ["External"]),
    ("Dell Technologies India", "dell", [1], ["External"]),
    ("HP Inc. India", "hp", [5], ["ExternalCareerSite"]),
    ("Hewlett Packard Enterprise (HPE) India", "hpe", [5], ["Jobsathpe", "WFMathpe", "ACJobSite"]),
    ("Broadcom India", "broadcom", [1], ["External_Career"]),
    ("Micron Technology India", "micron", [1], ["External"]),
    ("Mastercard India", "mastercard", [1], ["CorporateCareers"]),
    ("Western Digital India", "wdc", [5, 1], ["WD_External", "External"]),
    ("SanDisk India", "sandisk", [1, 5], ["SanDisk", "External"]),
    ("Applied Materials India", "amat", [1], ["External"]),
    ("KLA India", "kla", [1], ["Search"]),
    ("NXP Semiconductors India", "nxp", [3], ["careers"]),
    ("Analog Devices India", "analogdevices", [1], ["External"]),
    ("Marvell Technology India", "marvell", [1], ["MarvellCareers"]),
    ("Cadence Design Systems India", "cadence", [1], ["External_Careers"]),
    ("Texas Instruments India", "ti", [1, 5], ["External", "TI_Careers"]),
    ("Harman International India", "harman", [3, 5], ["HARMAN"]),
    ("Aptiv India", "aptiv", [5], ["APTIV_CAREERS"]),
    ("Medtronic India", "medtronic", [1], ["MedtronicCareers"]),
    ("Stryker India", "stryker", [1], ["StrykerCareers"]),
    ("Boston Scientific India", "bostonscientific", [1, 5], ["BSCI", "bscicareers"]),
    ("Becton Dickinson (BD) India", "bdx", [1], ["EXTERNAL_CAREER_SITE_INDIA", "EXTERNAL_CAREER_SITE_USA"]),
    ("Thermo Fisher Scientific India", "thermofisher", [5], ["ThermoFisherCareers"]),
    ("Agilent Technologies India", "agilent", [5], ["Agilent_Careers", "External"]),
    ("Illumina India", "illumina", [1], ["illumina-careers"]),
    ("Pfizer India", "pfizer", [1], ["PfizerCareers"]),
    ("AstraZeneca India", "astrazeneca", [3], ["Careers"]),
    ("GSK India", "gsk", [5], ["GSKCareers"]),
    ("Novartis India", "novartis", [3], ["Novartis_Careers"]),
    ("Sanofi India", "sanofi", [3], ["SanofiCareers"]),
    ("Johnson & Johnson India", "jj", [5], ["JJ"]),
    ("Abbott India", "abbott", [5], ["abbottcareers"]),
    ("Bristol Myers Squibb India", "bristolmyerssquibb", [5], ["BMS"]),
    ("Amgen India", "amgen", [1], ["Careers"]),
    ("Gilead Sciences India", "gilead", [1], ["gileadcareers"]),
    ("Takeda India", "takeda", [3], ["External"]),
    ("Merck India", "msd", [5], ["SearchJobs"]),
    ("Eli Lilly India", "lilly", [1, 5], ["LLY"]),
    ("Biogen India", "biibhr", [3], ["external"]),
    ("Bank of America India", "ghr", [1], ["Lateral-US", "Campus", "Lateral-APAC"]),
    ("Citibank India", "citi", [5], ["2"]),
    ("Wells Fargo India", "wf", [1], ["WellsFargoJobs"]),
    ("Barclays India", "barclays", [3], ["External_Career_Site_Barclays"]),
    ("HSBC India", "hsbc", [3], ["external", "HSBC_Careers"]),
    ("Morgan Stanley India", "ms", [5], ["External"]),
    ("BNY Mellon India", "bnymellon", [5], ["BNY_Careers", "BNY"]),
    ("State Street India", "statestreet", [1], ["Global"]),
    ("Northern Trust India", "ntrs", [1], ["northerntrust"]),
    ("Fidelity Investments India", "fmr", [1], ["FidelityCareers", "targeted"]),
    ("BlackRock India", "blackrock", [1], ["BlackRock_Professional", "BlackRock_Campus"]),
    ("Vanguard India", "vanguard", [5], ["vanguard_external"]),
    ("Invesco India", "invesco", [1], ["IVZ"]),
    ("Franklin Templeton India", "franklintempleton", [5], ["Primary-External-1"]),
    ("PayPal India", "paypal", [1], ["jobs"]),
    ("Fiserv India", "fiserv", [5], ["EXT"]),
    ("FIS Global India", "fis", [5], ["SearchJobs"]),
    ("Broadridge Financial Solutions India", "broadridge", [5], ["Careers"]),
    ("S&P Global India", "spgi", [5], ["SPGI_Careers"]),
    ("Moody's India", "moodys", [5], ["Moodys"]),
    ("MSCI India", "msci", [1], ["MSCI_Careers", "External"]),
    ("Nasdaq India", "nasdaq", [1], ["US_External_Career_Site", "Global_External_Site"]),
    ("Thomson Reuters India", "thomsonreuters", [5], ["External_Career_Site"]),
    ("LSEG (London Stock Exchange Group) India", "lseg", [3], ["Careers"]),
    ("Accenture India", "accenture", [103, 3], ["AccentureCareers"]),
    ("DXC Technology", "dxctechnology", [1], ["DXCJobs"]),
    ("CrowdStrike India", "crowdstrike", [5], ["crowdstrikecareers"]),
    ("Akamai Technologies India", "akamai", [1], ["akamaicareers"]),
    ("F5 Networks India", "ffive", [5], ["f5jobs"]),
    ("NetApp India", "netapp", [1], ["NetAppCareers", "External"]),
    ("McAfee India", "mcafee", [1], ["External"]),
    ("Seagate Technology India", "seagatecareers", [1], ["External"]),
    ("Lam Research India", "lamresearch", [1], ["LAM"]),
    ("Philips India", "philips", [3], ["jobs-and-careers"]),
    ("GE HealthCare India", "gehc", [5], ["GEHC_ExternalSite"]),
    ("GE Aerospace India", "geaerospace", [5], ["GE_ExternalSite"]),
    ("GE Vernova India", "gevernova", [5], ["Vernova_ExternalSite"]),
    ("Honeywell Technology Solutions India", "honeywell", [5], ["Honeywell"]),
    ("Magna International India", "magna", [3], ["Magna"]),
    ("Visteon India", "visteon", [5], ["visteonjobs", "External"]),
    ("PwC India", "pwc", [3], ["Global_Experienced_Careers", "Global_Campus_Careers"]),
    ("IQVIA India", "iqvia", [1], ["IQVIA"]),
    ("Labcorp India", "labcorp", [1], ["External"]),
    ("Syneos Health India", "syneoshealth", [12], ["Syneos_Health_External_Site"]),
    ("Parexel India", "parexel", [1], ["Parexel_External_Careers"]),
    ("Johnson & Johnson Consumer Health India (Kenvue)", "kenvue", [1], ["KenvueCareers"]),
    ("Mondelez India", "mdlz", [3], ["External"]),
    ("Coca-Cola India", "coke", [1], ["coca-cola-careers"]),
    ("Kimberly-Clark India", "kimberlyclark", [1], ["GLOBAL"]),
    ("Estée Lauder Companies India", "elcompanies", [1], ["ELC"]),
    ("Reckitt India", "reckitt", [3], ["Reckitt"]),
    ("United Spirits (Diageo India)", "diageo", [3], ["Diageo_Careers"]),
    ("Shell India", "shell", [3], ["ShellCareers"]),
    ("BP India", "bp", [3], ["bpCareers"]),
    ("Chevron India", "chevron", [5], ["jobs"]),
    ("Baker Hughes India", "bakerhughes", [5], ["BakerHughes"]),
    ("Halliburton India", "halliburton", [5], ["Halliburton"]),
    ("AECOM India", "aecom", [1], ["AECOMCareers"]),
    ("Jacobs India", "jacobs", [5], ["Jacobs"]),
    ("Whirlpool of India", "whirlpool", [5], ["Whirlpool_Careers"]),
    ("Carrier Midea India", "carrier", [5], ["jobs"]),
    ("Renesas Electronics India", "renesas", [3], ["jobs"]),
    ("Sophos India", "sophos", [3], ["Sophos_Careers", "External"]),
    ("Zscaler India", "zscaler", [5], ["zscaler_careers"]),
    ("Palo Alto Networks India", "paloaltonetworks", [1, 5], ["External"]),
    ("Juniper Networks India", "juniper", [1], ["JuniperCareers"]),
    ("Lenovo India", "lenovo", [5], ["Lenovo_Careers"]),
    ("Arista Networks India", "arista", [1], ["External"]),
    ("Citadel Securities India", "citadel", [1], ["Citadel"]),
    ("Point72 India", "point72", [1], ["Point72"]),
    ("Blackstone India", "blackstone", [1], ["Blackstone_Careers"]),
    ("KKR India", "kkr", [1], ["KKR"]),
    ("Bain & Company India", "bain", [1], ["External"]),
    ("Kearney India", "kearney", [3], ["Kearney"]),
    ("Alvarez & Marsal India", "alvarezandmarsal", [1], ["alvarezandmarsal"]),
    ("Novo Nordisk India", "novonordisk", [3], ["novonordisk"]),
    ("Teva Pharmaceuticals India", "teva", [5], ["TEVA"]),
    ("Boehringer Ingelheim India", "boehringer", [3], ["BI-Careers"]),
    ("Roche India", "roche", [3], ["roche-ext"]),
    ("Siemens Healthineers India", "healthineers", [3], ["Healthineers"]),
    ("Cummins India", "cummins", [1, 5], ["cummins"]),
    ("Hitachi Energy India", "hitachienergy", [3], ["External"]),
    ("Siemens Energy India", "siemensenergy", [3], ["Siemens_Energy"]),
    ("Schneider Electric India", "schneiderelectric", [3], ["Schneider_Electric"]),
    ("Hilton India", "hilton", [1], ["Hilton"]),
    ("Marriott International India", "marriott", [5], ["Marriott"]),
    ("Concentrix", "concentrix", [1], ["external"]),
    ("TaskUs", "taskus", [1], ["TaskUs_Careers"]),
    ("Genpact", "genpact", [1, 5], ["Genpact"]),
    ("UST", "ust", [5], ["UST"]),
    ("Fortinet India", "fortinet", [1, 5], ["Fortinet"]),
    ("Pure Storage India", "purestorage", [1], ["PureStorage"]),
]

GENERIC_SITES = ["External", "Careers", "External_Career_Site", "ExternalCareerSite", "careers",
                 "Search", "jobs", "External_Careers", "Global"]


# Slugs that answered but belong to a different company (checked by hand).
BAD = {("greenhouse", "india"), ("ashby", "apollo"), ("greenhouse", "apollo"), ("ashby", "applied"),
       ("ashby", "analog"), ("lever", "ashoka"), ("greenhouse", "metropolis")}


def slugs_for(line):
    """Return [(slug, full)] where full=True means the slug is the whole company name."""
    base = re.sub(r"\(.*?\)", "", line)
    base = re.sub(r"\b(India|Limited|Ltd|Inc\.?|Pvt)\b", "", base)
    base = ascii_fold(base).lower()
    words = re.findall(r"[a-z0-9]+", base.replace("&", "and"))
    cands = []
    if words:
        cands.append(("".join(words), True))
        cands.append(("-".join(words), True))
        if len(words) > 1:
            cands.append((words[0], False))
    for inner in re.findall(r"\((.*?)\)", line):
        w = re.findall(r"[a-z0-9]+", ascii_fold(inner).lower())
        if w and "".join(w) != "india":
            cands.append(("".join(w), len(w) > 1))
    seen, out = set(), []
    for c, full in cands:
        if c and c not in seen and len(c) >= 3:
            seen.add(c)
            out.append((c, full))
    return out


def _try(src):
    try:
        jobs = ats.fetch(src)
        return src, len(jobs)
    except Exception:
        return src, -1


def probe_simple(line, matcher):
    """Greenhouse / Lever / Ashby / SmartRecruiters by slug."""
    hits = []
    for slug, full in slugs_for(line):
        # Lever / Ashby give no company name, so only trust a slug that is the full name.
        long_enough = full and len(slug) >= 6
        # Greenhouse: board name check
        try:
            r = get(f"https://boards-api.greenhouse.io/v1/boards/{slug}", timeout=15)
            if r.status_code == 200 and (matcher.match(r.json().get("name", "")) == line or long_enough):
                hits.append({"company": line, "type": "greenhouse", "slug": slug})
        except Exception:
            pass
        try:
            r = get(f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json", "limit": 1}, timeout=15)
            if r.status_code == 200 and isinstance(r.json(), list) and long_enough:
                hits.append({"company": line, "type": "lever", "slug": slug})
        except Exception:
            pass
        try:
            r = get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}", timeout=15)
            if r.status_code == 200 and r.json().get("jobs") is not None and long_enough:
                hits.append({"company": line, "type": "ashby", "slug": slug})
        except Exception:
            pass
        try:
            r = get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings", params={"limit": 1}, timeout=15)
            if r.status_code == 200:
                d = r.json()
                if d.get("totalFound", 0) > 0:
                    name = ((d["content"][0].get("company") or {}).get("name", ""))
                    if matcher.match(name) == line:
                        hits.append({"company": line, "type": "smartrecruiters", "slug": slug})
        except Exception:
            pass
    return hits


def _wd_ok(host, tenant, site):
    try:
        r = post(f"https://{host}/wday/cxs/{tenant}/{site}/jobs",
                 data=json.dumps({"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""}),
                 headers={"Content-Type": "application/json", "Accept": "application/json"}, timeout=15)
        return r.status_code == 200 and '"total"' in r.text
    except Exception:
        return False


def probe_workday(entry):
    line, tenant, wds, sites = entry
    hits = []
    for wd in wds:
        host = f"{tenant}.wd{wd}.myworkdayjobs.com"
        hits = [{"company": line, "type": "workday", "host": host, "tenant": tenant, "site": s}
                for s in sites if _wd_ok(host, tenant, s)]
        if hits:
            return hits
    for wd in wds:
        host = f"{tenant}.wd{wd}.myworkdayjobs.com"
        for s in GENERIC_SITES:
            if s not in sites and _wd_ok(host, tenant, s):
                return [{"company": line, "type": "workday", "host": host, "tenant": tenant, "site": s}]
    return []


def main():
    matcher = CompanyMatcher()
    lines = load_company_lines()
    found = []

    print("1/3 Workday ...", flush=True)
    with ThreadPoolExecutor(16) as ex:
        for res in ex.map(probe_workday, WORKDAY):
            found.extend(res)
    print(f"   workday sites answering: {len(found)}", flush=True)

    print("2/3 Greenhouse / Lever / Ashby / SmartRecruiters for all companies ...", flush=True)
    with ThreadPoolExecutor(24) as ex:
        futs = [ex.submit(probe_simple, ln, matcher) for ln in lines]
        for i, f in enumerate(as_completed(futs)):
            found.extend(f.result())
            if i % 100 == 0:
                print(f"   {i}/{len(lines)}", flush=True)

    found = [s for s in found if (s["type"], s.get("slug")) not in BAD]
    found.extend(KNOWN)

    print("3/3 checking each source returns India jobs ...", flush=True)
    keep = []
    with ThreadPoolExecutor(16) as ex:
        for src, n in ex.map(_try, found):
            tag = f"{src['type']:15} {src['company'][:40]:40} {src.get('slug') or src.get('site') or src.get('host', '')}"
            if n < 0 and src.get("sticky"):
                n = 1        # hand-checked source that had a passing network error: keep it
            if n > 0:
                src = dict(src)
                keep.append(src)
                print(f"   OK  {n:4} India jobs  {tag}")
            elif n == 0:
                print(f"   --     0 India jobs  {tag}")
            else:
                print(f"   ERR                {tag}")
    # one entry per (company, type, slug/site/host)
    uniq = {}
    for s in keep:
        k = (s["company"], s["type"], s.get("slug"), s.get("site"), s.get("host"), s.get("api"))
        uniq[k] = s
    # if both pcsx and v2 work for an Eightfold host, keep one
    final, ef_hosts = [], set()
    for s in uniq.values():
        if s["type"] == "eightfold":
            if s["host"] in ef_hosts:
                continue
            ef_hosts.add(s["host"])
        final.append(s)
    final.sort(key=lambda s: (s["company"], s["type"]))
    (DATA / "sources.json").write_text(json.dumps(final, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved {len(final)} career-site sources for "
          f"{len({s['company'] for s in final})} companies -> data/sources.json")


if __name__ == "__main__":
    sys.exit(main())
