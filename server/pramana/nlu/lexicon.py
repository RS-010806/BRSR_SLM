"""Domain vocabulary for entity linking and guardrails.

Every metric maps to question numbers that exist in the E1 workbook. Every
out-of-scope topic maps to the chapter of the published IIMB report that
covers it, so the assistant can say where the information lives instead of
guessing.
"""
from __future__ import annotations

# --------------------------------------------------------------------------- metrics
# kind: numeric | intensity | bool | text | category | score | none
METRICS: dict[str, dict] = {
    "scope12": dict(label="Scope 1+2 emissions", kind="numeric", qids=["1330", "1331", "1332", "1333"], phrases=[
        "scope12", "scope12 emissions", "total emissions", "total ghg emissions", "ghg emissions", "greenhouse gas emissions",
        "greenhouse gases", "carbon emissions", "co2 emissions", "co2", "emissions", "emission", "carbon footprint",
        "operational emissions", "absolute emissions", "emitters", "emitter", "emitting", "emit", "emits", "pollutes most",
        "ghg", "carbon", "combined emissions", "direct and indirect emissions"]),
    "scope1": dict(label="Scope 1 emissions", kind="numeric", qids=["1330", "1331"], phrases=[
        "scope1", "scope1 emissions", "direct emissions", "direct ghg emissions", "direct ghg", "direct carbon emissions",
        "fuel combustion emissions"]),
    "scope2": dict(label="Scope 2 emissions", kind="numeric", qids=["1332", "1333"], phrases=[
        "scope2", "scope2 emissions", "indirect emissions", "electricity emissions", "purchased electricity emissions",
        "energy indirect emissions", "emissions from electricity", "grid electricity emissions"]),
    "scope3": dict(label="Scope 3 emissions", kind="numeric", qids=["1388", "1389"], phrases=[
        "scope3", "scope3 emissions", "value chain emissions", "supply chain emissions", "upstream and downstream emissions",
        "financed emissions", "indirect value chain emissions"]),
    "intensity": dict(label="Scope 1+2 intensity per crore of turnover", kind="intensity", qids=["1334", "1335"], phrases=[
        "emission intensity", "emissions intensity", "carbon intensity", "ghg intensity", "intensity per rupee",
        "intensity per crore", "per rupee of turnover", "intensity per turnover", "revenue intensity", "intensity",
        "turnover intensity", "carbon efficiency", "emissions per rupee", "emissions per crore", "decoupling",
        "emission efficiency", "intensive"]),
    "intensity_ppp": dict(label="Scope 1+2 intensity (PPP adjusted)", kind="intensity", qids=["1336", "1337"], phrases=[
        "ppp", "purchasing power parity", "ppp adjusted intensity", "ppp intensity"]),
    "intensity_phys": dict(label="Scope 1+2 intensity per unit of physical output", kind="intensity", qids=["1338", "1339"],
                           phrases=["physical output", "physical intensity", "per unit of production", "per unit of output",
                                    "production intensity", "per tonne", "output intensity", "physical output intensity"]),
    "scope3_intensity": dict(label="Scope 3 intensity per crore of turnover", kind="intensity", qids=["1390", "1391"],
                             phrases=["scope3 intensity", "scope3 emission intensity", "value chain intensity",
                                      "scope3 per rupee", "scope3 emissions intensity"]),
    "targets": dict(label="Commitments, goals and targets", kind="text", qids=["286"], phrases=[
        "targets", "target", "goals", "goal", "commitments", "commitment", "netzero", "netzero target", "netzero targets",
        "decarbonisation targets", "decarbonization targets", "climate targets", "emission targets", "reduction targets",
        "science based targets", "climate goals", "pledges", "pledge", "ambition", "timelines", "carbon neutral",
        "carbon neutrality"]),
    "target_performance": dict(label="Performance against targets", kind="text", qids=["295"], phrases=[
        "performance against targets", "progress on targets", "progress against targets", "progress against goals",
        "achievement of targets", "target achievement", "met its targets", "achieved targets", "achieve targets",
        "performance against goals", "progress on goals", "progress towards targets", "delivered on targets",
        "progress on commitments", "performance against commitments", "track record", "perform against",
        "performed against", "performing against", "against its targets", "against their targets", "against targets",
        "against its goals", "against its commitments", "meet its targets", "meeting targets", "missed targets"]),
    "projects": dict(label="GHG reduction projects", kind="text", qids=["1341", "1342"], phrases=[
        "projects", "project", "ghg reduction projects", "emission reduction projects", "decarbonisation projects",
        "decarbonization projects", "reduction initiatives", "initiatives", "initiative", "measures", "reduction measures",
        "actions to reduce emissions", "decarbonisation", "decarbonization", "abatement", "reduce emissions",
        "emission reduction", "reducing emissions", "cut emissions", "mitigation", "climate action", "what is doing"]),
    "ghg_assurance": dict(label="Independent GHG assurance", kind="bool", qids=["1340"], phrases=[
        "assurance", "assured", "third party verification", "verified", "verification", "independent assurance",
        "external assurance", "audited emissions", "emissions audit", "independently verified", "external verification",
        "reasonable assurance", "limited assurance", "assurer", "assurance provider", "verify", "verifies",
        "verify its", "audit", "audited", "third party assurance", "external verification of emissions"]),
    "scope3_assurance": dict(label="Independent Scope 3 assurance", kind="bool", qids=["1560", "1561"], phrases=[
        "scope3 assurance", "scope3 assured", "scope3 verified", "scope3 verification", "scope3 assurer"]),
    "scope3_reported": dict(label="Scope 3 reporting", kind="bool", qids=["1387"], phrases=[
        "report scope3", "reports scope3", "reporting scope3", "scope3 reporting", "disclose scope3", "discloses scope3",
        "scope3 disclosure", "disclosing scope3", "scope3 reporters"]),
    "policy": dict(label="Principle 6 policy", kind="bool", qids=["232"], phrases=[
        "policy", "policies", "climate policy", "environment policy", "environmental policy", "principle6",
        "principle6 policy", "ngrbc policy", "environmental policies", "climate policies"]),
    "board_approval": dict(label="Board approval of policy", kind="bool", qids=["241"], phrases=[
        "board approval", "board approved", "approved by the board", "board approve", "board sign off"]),
    "policy_link": dict(label="Public policy web link", kind="bool", qids=["250"], phrases=[
        "web link", "weblink", "policy link", "publicly available policy", "public policy link", "url", "link",
        "publicly accessible", "public disclosure of policy", "website link"]),
    "procedures": dict(label="Policy translated into procedures", kind="bool", qids=["259"], phrases=[
        "procedures", "operational procedures", "translated into procedures", "operationalised", "operationalized",
        "sops", "standard operating procedures"]),
    "value_chain": dict(label="Policy extends to value chain", kind="bool", qids=["268"], phrases=[
        "value chain partners", "value chain policy", "extend to value chain", "suppliers", "supplier policy",
        "value chain", "vendors", "partners"]),
    "certifications": dict(label="Codes, certifications and standards", kind="text", qids=["277"], phrases=[
        "certifications", "certification", "certificates", "certificate", "standards", "iso14001", "iso", "codes",
        "labels", "frameworks adopted", "frameworks", "iso14064", "iso50001", "gri", "tcfd", "cdp"]),
    "review_level": dict(label="Governance level of review", kind="category", qids=["308", "317"], phrases=[
        "who reviews", "reviewed by", "oversight", "governance level", "review level", "board oversight",
        "committee", "governance"]),
    "review_frequency": dict(label="Review frequency", kind="category", qids=["326", "335"], phrases=[
        "frequency", "how often", "review frequency", "quarterly", "annually", "half yearly", "how frequently",
        "periodic review", "reviewed"]),
    "policy_assessment": dict(label="Independent assessment of policies", kind="bool", qids=["344", "353"], phrases=[
        "independent assessment of policies", "external assessment", "policy assessment", "evaluation by external agency",
        "independent evaluation", "policy evaluation", "external agency", "assessed its policies"]),
    "ghg_applicable": dict(label="GHG disclosure applicability", kind="bool", qids=["1329"], phrases=[
        "applicable", "applicability", "not applicable"]),
    "green_credits": dict(label="Green credits", kind="none", qids=["2210", "2211"], phrases=[
        "green credits", "green credit", "carbon credits", "carbon credit", "offsets", "carbon offsets"]),
    "index": dict(label="E1 index (derived)", kind="score", qids=[], phrases=[
        "score", "scores", "overall score", "e1 score", "rating", "ratings", "overall rating", "esg score", "index",
        "e1 index", "overall performance", "performance", "scorecard", "maturity", "overall", "disclosure quality",
        "best performer", "leaders", "laggards", "ranking", "rank"]),
}

# Phrases that are too generic to decide the metric on their own when a more
# specific metric is present in the same query.
WEAK_PHRASES = {"emissions", "emission", "ghg", "carbon", "performance", "overall", "rank", "ranking", "score",
                "rating", "project", "projects", "initiatives", "initiative", "measures", "link", "partners",
                "committee", "governance", "reviewed", "target", "goal", "policy", "policies", "intensive", "co2",
                "emit", "emits", "emitting", "leaders", "laggards", "iso", "codes", "labels", "frameworks",
                "verified", "verification", "applicable", "offsets", "value chain", "suppliers", "vendors"}

# --------------------------------------------------------------------------- sectors
SECTOR_SYNONYMS: dict[str, list[str]] = {
    "Automobile and Auto Components": ["automobile and auto components", "automobile", "automobiles", "auto",
                                       "autos", "auto components", "auto ancillary", "automotive", "car makers",
                                       "carmakers", "two wheeler", "auto sector", "vehicle manufacturers"],
    "Capital Goods": ["capital goods", "engineering", "industrials", "industrial", "machinery", "defence", "defense",
                      "electrical equipment", "heavy engineering"],
    "Chemicals": ["chemicals", "chemical", "specialty chemicals", "speciality chemicals", "fertilisers", "fertilizers",
                  "agrochemicals", "petrochemicals"],
    "Construction": ["construction", "infrastructure", "infra", "epc", "construction companies"],
    "Construction Materials": ["construction materials", "cement", "cements", "cement companies", "cement makers",
                               "building materials", "cement industry", "cement sector"],
    "Consumer Durables": ["consumer durables", "durables", "appliances", "consumer electronics", "electronics"],
    "Consumer Services": ["consumer services", "retail", "retailers", "hotels", "hospitality", "e commerce",
                          "ecommerce", "restaurants", "travel"],
    "Diversified": ["diversified", "conglomerates", "conglomerate"],
    "Fast Moving Consumer Goods": ["fast moving consumer goods", "fmcg", "consumer goods", "consumer staples",
                                   "packaged foods", "food and beverages"],
    "Financial Services": ["financial services", "financials", "finance", "financial", "banks", "banking", "bank",
                           "nbfc", "nbfcs", "insurance", "insurers", "lenders", "asset managers", "fintech"],
    "Forest Materials": ["forest materials", "paper", "paper and pulp", "pulp", "forest products", "wood"],
    "Healthcare": ["healthcare", "health care", "pharma", "pharmaceuticals", "pharmaceutical", "hospitals",
                   "hospital", "drug makers", "life sciences", "diagnostics"],
    "Information Technology": ["information technology", "it", "it services", "tech", "technology", "software",
                               "it companies", "it sector", "tech companies"],
    "Media Entertainment & Publication": ["media entertainment and publication", "media", "entertainment",
                                          "publishing", "broadcasting", "media and entertainment"],
    "Metals & Mining": ["metals and mining", "metals", "metal", "mining", "steel", "steel makers", "steel companies",
                        "aluminium", "aluminum", "iron", "copper", "zinc", "miners"],
    "Oil Gas & Consumable Fuels": ["oil gas and consumable fuels", "oil and gas", "oil gas", "oil", "gas",
                                   "petroleum", "refiners", "refining", "refineries", "consumable fuels", "coal",
                                   "fuels", "o and g", "oil marketing companies", "omcs"],
    "Power": ["power", "power sector", "power generation", "electricity generation", "power companies",
              "power producers", "gencos", "thermal power", "renewable energy companies", "power utilities"],
    "Realty": ["realty", "real estate", "property developers", "developers", "real estate developers"],
    "Services": ["services", "logistics", "services sector", "ports", "shipping", "facility management"],
    "Telecommunication": ["telecommunication", "telecom", "telecoms", "telcos", "telecommunications",
                          "mobile operators"],
    "Textiles": ["textiles", "textile", "apparel", "garments", "yarn", "fabrics", "clothing"],
    "Utilities": ["utilities", "utility", "gas distribution", "city gas distribution", "water utilities"],
}

# --------------------------------------------------------------------------- guardrails
# Topics outside the E1 dataset. `chapter`: code in the IIMB report,
# `pdf_page`: first page of that chapter, `summary_page`: executive summary page.
OFFTOPIC: list[dict] = [
    dict(key="E2", label="Air emissions (NOx, SOx, particulate matter)", chapter="E2", pdf_page=51, summary_page=8,
         phrases=["nox", "sox", "particulate", "particulate matter", "pm10", "pm2", "air quality", "air pollution",
                  "air emissions", "voc", "hap", "pop", "stack emissions", "sulphur", "sulfur"]),
    dict(key="E3", label="Water management", chapter="E3", pdf_page=57, summary_page=8,
         phrases=["water", "water withdrawal", "water consumption", "water intensity", "wastewater", "effluent",
                  "water stress", "water discharge", "freshwater"]),
    dict(key="E4", label="Energy management", chapter="E4", pdf_page=66, summary_page=9,
         phrases=["energy consumption", "energy use", "energy intensity", "renewable share", "renewable energy share",
                  "share of renewables", "energy mix", "gigajoules", "gj", "energy management", "energy consumed",
                  "renewable percentage", "percentage of renewable", "total energy", "fuel consumption",
                  "electricity consumption", "energy efficiency ratio"]),
    dict(key="E5", label="Biodiversity and climate adaptation", chapter="E5", pdf_page=74, summary_page=9,
         phrases=["biodiversity", "ecologically sensitive", "ecosystem", "habitat", "species", "climate adaptation",
                  "adaptation", "business continuity", "physical risk", "deforestation"]),
    dict(key="E6", label="Waste and hazardous materials", chapter="E6", pdf_page=82, summary_page=9,
         phrases=["waste", "plastic waste", "e waste", "ewaste", "hazardous waste", "hazardous materials",
                  "waste recovery", "recycling rate", "landfill", "waste generated"]),
    dict(key="E7", label="Resource efficiency", chapter="E7", pdf_page=91, summary_page=9,
         phrases=["resource efficiency", "circular economy", "circularity", "r and d spend", "capex on",
                  "life cycle assessment", "lca", "reclaimed products", "packaging material"]),
    dict(key="S1", label="Human rights", chapter="S1", pdf_page=103, summary_page=10,
         phrases=["human rights", "child labour", "child labor", "forced labour", "forced labor", "posh",
                  "sexual harassment", "discrimination"]),
    dict(key="S2", label="Labour practices", chapter="S2", pdf_page=115, summary_page=10,
         phrases=["labour practices", "labor practices", "minimum wage", "wages", "provident fund", "gratuity",
                  "contract workers", "labour", "labor", "unions"]),
    dict(key="S3", label="Employee health and safety", chapter="S3", pdf_page=123, summary_page=10,
         phrases=["safety", "fatalities", "fatality", "injuries", "ltifr", "trir", "accidents", "occupational health",
                  "health and safety", "deaths"]),
    dict(key="S4", label="Employee engagement, diversity and inclusion", chapter="S4", pdf_page=137, summary_page=11,
         phrases=["diversity", "gender", "women", "female employees", "attrition", "turnover rate", "employees",
                  "employee", "workforce", "headcount", "inclusion", "parental leave", "training hours", "staff"]),
    dict(key="S5", label="Supply chain management", chapter="S5", pdf_page=146, summary_page=11,
         phrases=["msme", "msmes", "procurement", "sourcing", "supply chain management", "local sourcing"]),
    dict(key="S6", label="Customer privacy and data security", chapter="S6", pdf_page=152, summary_page=11,
         phrases=["data privacy", "privacy", "cybersecurity", "cyber security", "data breach", "data breaches",
                  "customer complaints", "product recall"]),
    dict(key="S7", label="Access, affordability and community relations", chapter="S7", pdf_page=163, summary_page=11,
         phrases=["csr", "corporate social responsibility", "community", "communities", "csr spend",
                  "aspirational districts", "beneficiaries", "social impact"]),
    dict(key="G1", label="Anti-corruption and bribery", chapter="G1", pdf_page=173, summary_page=12,
         phrases=["corruption", "bribery", "anti corruption", "anti bribery", "disciplinary action"]),
    dict(key="G2", label="Business ethics and transparency", chapter="G2", pdf_page=179, summary_page=12,
         phrases=["business ethics", "conflict of interest", "related party", "related parties", "ethics"]),
    dict(key="G3", label="Competitive behaviour", chapter="G3", pdf_page=189, summary_page=12,
         phrases=["antitrust", "anti competitive", "competition law", "trade associations", "industry associations",
                  "lobbying", "public policy advocacy"]),
    dict(key="G4", label="Risk and crisis management", chapter="G4", pdf_page=196, summary_page=12,
         phrases=["risk management", "crisis management", "fines", "penalties", "material issues", "materiality",
                  "board training"]),
    dict(key="G5", label="Board structure and oversight", chapter="G5", pdf_page=202, summary_page=13,
         phrases=["board structure", "independent directors", "board composition", "board diversity",
                  "female directors", "women directors", "key managerial personnel", "kmp"]),
    dict(key="G6", label="Stakeholder engagement", chapter="G6", pdf_page=208, summary_page=13,
         phrases=["stakeholder engagement", "stakeholders", "stakeholder consultation", "grievance",
                  "grievances"]),
    dict(key="G7", label="Executive compensation", chapter="G7", pdf_page=219, summary_page=13,
         phrases=["executive compensation", "salary", "salaries", "remuneration", "ceo pay", "pay ratio",
                  "executive pay", "compensation"]),
    dict(key="FIN", label="Financial and market data", chapter=None, pdf_page=None, summary_page=None,
         phrases=["revenue", "revenues", "sales", "profit", "profits", "net income", "market cap",
                  "market capitalisation", "market capitalization", "share price", "stock price", "stock", "shares",
                  "valuation", "dividend", "dividends", "eps", "earnings", "debt", "ebitda", "turnover figure",
                  "total turnover", "annual turnover", "balance sheet", "invest in", "buy", "sell"]),
    dict(key="PEOPLE", label="People and corporate facts", chapter=None, pdf_page=None, summary_page=None,
         phrases=["ceo", "chairman", "founder", "founded", "headquarters", "headquartered", "address", "contact",
                  "phone number", "email", "managing director", "owner", "owns"]),
    dict(key="FUTURE", label="Forecasts and predictions", chapter=None, pdf_page=None, summary_page=None,
         phrases=["forecast", "predict", "prediction", "projection", "next year", "future emissions", "will emit",
                  "expected emissions", "estimate for", "outlook", "going to emit", "will reduce"]),
    dict(key="WEB", label="Live web or news", chapter=None, pdf_page=None, summary_page=None,
         phrases=["search the web", "search online", "google", "internet", "latest news", "news", "today",
                  "twitter", "wikipedia", "chatgpt", "current events", "website of"]),
    dict(key="GENERAL", label="General knowledge", chapter=None, pdf_page=None, summary_page=None,
         phrases=["weather", "recipe", "poem", "joke", "song", "movie", "cricket", "football", "election",
                  "politics", "president", "prime minister", "capital of", "translate", "write code", "python",
                  "javascript", "bitcoin", "crypto", "horoscope", "who are you really", "meaning of life"]),
]

# --------------------------------------------------------------------------- companies
# Common short names people use. Values must match names in the dataset exactly;
# the builder validates this at startup.
CURATED_ALIASES: dict[str, str] = {
    "tcs": "Tata Consultancy Services Limited",
    "tata consultancy": "Tata Consultancy Services Limited",
    "ril": "Reliance Industries Limited",
    "reliance": "Reliance Industries Limited",
    "l and t": "Larsen & Toubro Limited",
    "lt": "Larsen & Toubro Limited",
    "larsen": "Larsen & Toubro Limited",
    "hul": "Hindustan Unilever Limited",
    "unilever": "Hindustan Unilever Limited",
    "sbi": "State Bank of India",
    "ioc": "Indian Oil Corporation Limited",
    "iocl": "Indian Oil Corporation Limited",
    "indian oil": "Indian Oil Corporation Limited",
    "bpcl": "BHARAT PETROLEUM CORPORATION LIMITED",
    "hpcl": "HINDUSTAN PETROLEUM CORPORATION LIMITED",
    "sail": "Steel Authority of India Limited",
    "bhel": "BHARAT HEAVY ELECTRICALS LIMITED",
    "hal": "HINDUSTAN AERONAUTICS LIMITED",
    "airtel": "Bharti Airtel Limited",
    "bharti": "Bharti Airtel Limited",
    "maruti": "Maruti Suzuki India Limited",
    "maruti suzuki": "Maruti Suzuki India Limited",
    "jsw steel": "JSW STEEL LIMITED",
    "jsw energy": "JSW ENERGY LIMITED",
    "ultratech": "UltraTech Cement Limited",
    "ultra tech": "UltraTech Cement Limited",
    "ambuja": "AMBUJA CEMENTS LIMITED",
    "ambuja cement": "AMBUJA CEMENTS LIMITED",
    "acc": "ACC LIMITED",
    "acc cement": "ACC LIMITED",
    "shree cement": "SHREE CEMENT LIMITED",
    "shree cements": "SHREE CEMENT LIMITED",
    "dalmia": "Dalmia Bharat Limited",
    "dalmia cement": "Dalmia Bharat Limited",
    "power grid": "POWER GRID CORPORATION OF INDIA LIMITED",
    "powergrid": "POWER GRID CORPORATION OF INDIA LIMITED",
    "pgcil": "POWER GRID CORPORATION OF INDIA LIMITED",
    "ntpc": "NTPC LIMITED",
    "coal india": "COAL INDIA LIMITED",
    "cil": "COAL INDIA LIMITED",
    "vedanta": "VEDANTA LIMITED",
    "hindalco": "HINDALCO INDUSTRIES LIMITED",
    "hindustan zinc": "HINDUSTAN ZINC LIMITED",
    "asian paints": "Asian Paints Limited",
    "itc": "ITC Limited",
    "nestle": "NESTLE INDIA LIMITED",
    "britannia": "BRITANNIA INDUSTRIES LIMITED",
    "dabur": "DABUR INDIA LIMITED",
    "sun pharma": "Sun Pharmaceutical Industries Limited",
    "sun pharmaceutical": "Sun Pharmaceutical Industries Limited",
    "dr reddy": "DR. REDDY'S LABORATORIES LIMITED",
    "dr reddys": "DR. REDDY'S LABORATORIES LIMITED",
    "drreddy": "DR. REDDY'S LABORATORIES LIMITED",
    "reddy": "DR. REDDY'S LABORATORIES LIMITED",
    "cipla": "CIPLA LIMITED",
    "hdfc bank": "HDFC Bank Limited",
    "hdfc": "HDFC Bank Limited",
    "icici bank": "ICICI BANK LIMITED",
    "icici": "ICICI BANK LIMITED",
    "axis bank": "AXIS BANK LIMITED",
    "axis": "AXIS BANK LIMITED",
    "kotak": "KOTAK MAHINDRA BANK LIMITED",
    "kotak bank": "KOTAK MAHINDRA BANK LIMITED",
    "kotak mahindra": "KOTAK MAHINDRA BANK LIMITED",
    "bajaj auto": "BAJAJ AUTO LIMITED",
    "bajaj finance": "BAJAJ FINANCE LIMITED",
    "bajaj finserv": "BAJAJ FINSERV LIMITED",
    "titan": "TITAN COMPANY LIMITED",
    "grasim": "Grasim Industries Limited",
    "eicher": "EICHER MOTORS LIMITED",
    "royal enfield": "EICHER MOTORS LIMITED",
    "hero": "HERO MOTOCORP LIMITED",
    "hero motocorp": "HERO MOTOCORP LIMITED",
    "lupin": "LUPIN LIMITED",
    "tech mahindra": "TECH MAHINDRA LIMITED",
    "techm": "TECH MAHINDRA LIMITED",
    "gail": "GAIL (INDIA) LIMITED",
    "jindal steel": "Jindal Steel & Power Limited",
    "jspl": "Jindal Steel & Power Limited",
    "jindal stainless": "JINDAL STAINLESS LIMITED",
    "nmdc": "NMDC LIMITED",
    "havells": "HAVELLS INDIA LIMITED",
    "pidilite": "PIDILITE INDUSTRIES LIMITED",
    "godrej consumer": "GODREJ CONSUMER PRODUCTS LIMITED",
    "gcpl": "GODREJ CONSUMER PRODUCTS LIMITED",
    "godrej properties": "GODREJ PROPERTIES LIMITED",
    "dlf": "DLF LIMITED",
    "paytm": "ONE 97 COMMUNICATIONS LIMITED",
    "one97": "ONE 97 COMMUNICATIONS LIMITED",
    "nykaa": "FSN E COMMERCE VENTURES LIMITED",
    "vi": "VODAFONE IDEA LIMITED",
    "vodafone": "VODAFONE IDEA LIMITED",
    "vodafone idea": "VODAFONE IDEA LIMITED",
    "indus towers": "INDUS TOWERS LIMITED",
    "bosch": "BOSCH LIMITED",
    "cummins": "CUMMINS INDIA LIMITED",
    "lic": "LIFE INSURANCE CORPORATION OF INDIA",
    "tata steel": "Tata Steel Limited",
    "tata power": "TATA POWER COMPANY LIMITED",
    "tata chemicals": "Tata Chemicals Limited",
    "tata consumer": "TATA CONSUMER PRODUCTS LIMITED",
    "tata elxsi": "TATA ELXSI LIMITED",
    "tata communications": "Tata Communications Limited",
    "infosys": "Infosys Limited",
    "infy": "Infosys Limited",
    "wipro": "WIPRO LIMITED",
    "hcl": "HCL TECHNOLOGIES LIMITED",
    "hcl tech": "HCL TECHNOLOGIES LIMITED",
    "hcltech": "HCL TECHNOLOGIES LIMITED",
    "adani power": "ADANI POWER LIMITED",
    "adani ports": "ADANI PORTS AND SPECIAL ECONOMIC ZONE LIMITED",
    "apsez": "ADANI PORTS AND SPECIAL ECONOMIC ZONE LIMITED",
    "adani enterprises": "ADANI ENTERPRISES LIMITED",
    "adani total": "ADANI TOTAL GAS LIMITED",
    "adani total gas": "ADANI TOTAL GAS LIMITED",
    "adani energy": "ADANI ENERGY SOLUTIONS LIMITED",
    "mahindra and mahindra": None,  # validated below: resolved only if present
}

# Well-known companies that are NOT among the 982 filings, so the assistant can
# say so plainly instead of fuzzy-matching them to something else.
KNOWN_ABSENT = {
    "ongc": "Oil and Natural Gas Corporation", "oil and natural gas": "Oil and Natural Gas Corporation",
    "tata motors": "Tata Motors", "siemens": "Siemens", "abb": "ABB India", "zomato": "Zomato (Eternal)",
    "eternal": "Eternal (Zomato)", "swiggy": "Swiggy", "m and m": "Mahindra & Mahindra",
    "mahindra and mahindra": "Mahindra & Mahindra", "adani green": "Adani Green Energy", "tata sons": "Tata Sons",
    "apple": "Apple", "google": "Google", "microsoft": "Microsoft", "amazon": "Amazon", "tesla": "Tesla",
    "flipkart": "Flipkart", "byjus": "Byju's", "ola": "Ola",
}

# Words that never count as a company mention on their own.
STOP = set("""
a an the and or of for to in on at by with from about as is are was were be been being it its this that these those
which who whom whose what when where why how do does did done has have had having can could should would will shall
may might must me my we our us you your i he she they them their there here all any each both few more most other some
such no nor not only own same so than too very just also show tell give list find get compare comparison versus vs
between among across within per over under up down out into off again further then once please kindly help want need
like know let see look view display draw plot chart graph table summary summarise summarize overview detail details
report reports reporting reported disclose disclosed disclosure disclosures data number numbers value values figure
figures company companies firm firms sector sectors industry industries peer peers competitor competitors rival
rivals best worst top bottom highest lowest largest smallest biggest most least better worse good bad great average
median mean total year years current previous last this prior fy change changes trend growth increase decrease
reduced reduction rise fall higher lower leader leaders laggard laggards india indian limited ltd corporation corp
co inc private pvt public group holdings enterprises industries india's many much how's what's whats one two three
new green clean energy power gas oil steel cement metal metals mining bank banks finance financial services service
capital goods chemicals chemical textiles textile realty media telecom health healthcare consumer products product
motors motor auto systems solutions technologies technology tech international global national united general
home life insurance infra infrastructure engineering electricals electric electronics foods food agro paper
""".split())
