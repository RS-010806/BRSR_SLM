"""Curated metadata for the E1 (GHG Emissions & Climate Risk) question set.

Every entry maps a BRSR question number from the "Questions" sheet of
E1_data.xlsx to a plain-language label, the analytical section it belongs to
in the IIMB E1 chapter, its response type, and the report tables that
aggregate it. Nothing here is invented data: labels paraphrase the BRSR
question text, and `report_tables` point at tables that exist in E1_report.docx.
"""

SECTIONS = {
    "governance": {
        "title": "Policy and governance",
        "report_section": "Section 1: Policy Development and Periodic Review",
    },
    "action": {
        "title": "Actions taken",
        "report_section": "Section 2: Operationalization of the Reporting Theme",
    },
    "outcome": {
        "title": "Performance outcomes",
        "report_section": "Section 3: Performance Outcomes of Implemented Measures",
    },
}

# type: bool | category | text | url | numeric
# raw_reliable=False marks Base Data columns whose header text does not match
# the question number (verified during reconciliation); for those the answer
# is taken from the Rating sheet, which reproduces the report tables exactly.
QUESTIONS = {
    "232": dict(key="policy", label="Principle 6 policy in place", section="governance", type="bool",
                ask="Does the entity have policies covering NGRBC Principle 6 (environment)?", report_tables=["1.1"]),
    "241": dict(key="board_approval", label="Policy approved by the Board", section="governance", type="bool",
                raw_reliable=False, ask="Has the policy been approved by the Board?", report_tables=["1.2"]),
    "250": dict(key="policy_link", label="Policy web link", section="governance", type="url",
                ask="Are the policies publicly accessible with a web link?", report_tables=["1.3"]),
    "259": dict(key="procedures", label="Policy translated into procedures", section="governance", type="bool",
                ask="Has the entity translated the policy into procedures?", report_tables=["1.4"]),
    "268": dict(key="value_chain", label="Policy extends to value chain", section="governance", type="bool",
                raw_reliable=False, ask="Do the policies extend to value chain partners?", report_tables=["1.5"]),
    "277": dict(key="certifications", label="Codes, certifications and standards", section="governance", type="text",
                ask="Which national and international codes, certifications, labels or standards has the entity adopted?",
                report_tables=["1.6"], ai_rated=True),
    "286": dict(key="targets", label="Commitments, goals and targets", section="governance", type="text",
                ask="What specific commitments, goals and targets with timelines has the entity set?",
                report_tables=["1.7"], ai_rated=True),
    "295": dict(key="target_performance", label="Performance against targets", section="governance", type="text",
                ask="How has the entity performed against its commitments, goals and targets?",
                report_tables=["1.8"], ai_rated=True),
    "308": dict(key="review_level", label="Who reviews performance", section="governance", type="category",
                ask="At what governance level is performance against the policies reviewed?", report_tables=["1.9"]),
    "317": dict(key="compliance_review_level", label="Who reviews statutory compliance", section="governance",
                type="category", ask="At what level is compliance with statutory requirements reviewed?", report_tables=[]),
    "326": dict(key="review_frequency", label="Performance review frequency", section="governance", type="category",
                ask="How frequently is performance against the policies reviewed?", report_tables=["1.10"]),
    "335": dict(key="compliance_review_frequency", label="Compliance review frequency", section="governance",
                type="category", ask="How frequently is statutory compliance reviewed?", report_tables=[]),
    "344": dict(key="policy_assessment", label="Independent assessment of policies", section="governance", type="bool",
                ask="Has the entity carried out an independent assessment of its policies by an external agency?",
                report_tables=["1.11"]),
    "353": dict(key="policy_assessor", label="Policy assessment agency", section="governance", type="text",
                ask="Which agency carried out the independent assessment of the policies?", report_tables=[]),
    "1329": dict(key="ghg_applicable", label="GHG disclosure applicable", section="action", type="bool",
                 ask="Is the GHG emissions and intensity disclosure applicable to the company?", report_tables=[]),
    "1340": dict(key="ghg_assurance", label="Independent GHG assurance", section="action", type="bool",
                 ask="Has an external agency carried out independent assessment or assurance of GHG emissions?",
                 report_tables=["2.4"]),
    "1341": dict(key="ghg_projects", label="Has GHG reduction projects", section="action", type="bool",
                 ask="Does the entity have any project related to reducing GHG emissions?", report_tables=["2.1"]),
    "1342": dict(key="ghg_project_details", label="GHG reduction project details", section="action", type="text",
                 ask="What are the details of the GHG emission reduction projects?", report_tables=["2.2"], ai_rated=True),
    "1387": dict(key="scope3_reported", label="Reports Scope 3 emissions", section="action", type="bool",
                 ask="Is Scope 3 emissions and intensity disclosure applicable / reported?", report_tables=["2.3"]),
    "1560": dict(key="scope3_assurance", label="Independent Scope 3 assurance", section="action", type="bool",
                 ask="Has an external agency assured the Scope 3 emissions?", report_tables=[]),
    "1561": dict(key="scope3_assurer", label="Scope 3 assurance agency", section="action", type="text",
                 ask="Which external agency assured the Scope 3 emissions?", report_tables=[]),
    "1828": dict(key="scope3_assured_brsr_core", label="Scope 3 assured by assurer (rating only)", section="action",
                 type="bool", rating_only=True,
                 ask="Are the Scope 3 emissions and intensity details assured by the assurer?", report_tables=[]),
    "1330": dict(key="scope1_cy", label="Scope 1 emissions, FY 2024-25", section="outcome", type="numeric",
                 unit="tCO2e", period="CY", pair="1331", ask="Total Scope 1 emissions (current year)",
                 report_tables=["3.1", "3.2", "3.3"]),
    "1331": dict(key="scope1_py", label="Scope 1 emissions, FY 2023-24", section="outcome", type="numeric",
                 unit="tCO2e", period="PY", pair="1330", ask="Total Scope 1 emissions (previous year)", report_tables=["3.2"]),
    "1332": dict(key="scope2_cy", label="Scope 2 emissions, FY 2024-25", section="outcome", type="numeric",
                 unit="tCO2e", period="CY", pair="1333", ask="Total Scope 2 emissions (current year)",
                 report_tables=["3.1", "3.2", "3.3"]),
    "1333": dict(key="scope2_py", label="Scope 2 emissions, FY 2023-24", section="outcome", type="numeric",
                 unit="tCO2e", period="PY", pair="1332", ask="Total Scope 2 emissions (previous year)", report_tables=["3.2"]),
    "1334": dict(key="intensity_cy", label="Scope 1+2 intensity per rupee of turnover, FY 2024-25", section="outcome",
                 type="numeric", unit="tCO2e per rupee", period="CY", pair="1335",
                 ask="Total Scope 1 and 2 emission intensity per rupee of turnover (current year)",
                 report_tables=["3.4", "3.5"]),
    "1335": dict(key="intensity_py", label="Scope 1+2 intensity per rupee of turnover, FY 2023-24", section="outcome",
                 type="numeric", unit="tCO2e per rupee", period="PY", pair="1334",
                 ask="Total Scope 1 and 2 emission intensity per rupee of turnover (previous year)", report_tables=["3.4"]),
    "1336": dict(key="intensity_ppp_cy", label="Scope 1+2 intensity per rupee (PPP adjusted), FY 2024-25",
                 section="outcome", type="numeric", unit="as reported", period="CY", pair="1337",
                 ask="Scope 1 and 2 intensity per rupee of turnover adjusted for PPP (current year)", report_tables=[]),
    "1337": dict(key="intensity_ppp_py", label="Scope 1+2 intensity per rupee (PPP adjusted), FY 2023-24",
                 section="outcome", type="numeric", unit="as reported", period="PY", pair="1336",
                 ask="Scope 1 and 2 intensity per rupee of turnover adjusted for PPP (previous year)", report_tables=[]),
    "1338": dict(key="intensity_phys_cy", label="Scope 1+2 intensity per unit of physical output, FY 2024-25",
                 section="outcome", type="numeric", unit="company-specific unit", period="CY", pair="1339",
                 ask="Scope 1 and 2 intensity in terms of physical output (current year)", report_tables=["3.6", "3.7"]),
    "1339": dict(key="intensity_phys_py", label="Scope 1+2 intensity per unit of physical output, FY 2023-24",
                 section="outcome", type="numeric", unit="company-specific unit", period="PY", pair="1338",
                 ask="Scope 1 and 2 intensity in terms of physical output (previous year)", report_tables=["3.6"]),
    "1388": dict(key="scope3_cy", label="Scope 3 emissions, FY 2024-25", section="outcome", type="numeric",
                 unit="tCO2e", period="CY", pair="1389", ask="Total Scope 3 emissions (current year)", report_tables=["3.8"]),
    "1389": dict(key="scope3_py", label="Scope 3 emissions, FY 2023-24", section="outcome", type="numeric",
                 unit="tCO2e", period="PY", pair="1388", ask="Total Scope 3 emissions (previous year)", report_tables=["3.8"]),
    "1390": dict(key="scope3_intensity_cy", label="Scope 3 intensity per rupee of turnover, FY 2024-25",
                 section="outcome", type="numeric", unit="tCO2e per rupee", period="CY", pair="1391",
                 ask="Total Scope 3 emissions per rupee of turnover (current year)", report_tables=["3.9", "3.10"]),
    "1391": dict(key="scope3_intensity_py", label="Scope 3 intensity per rupee of turnover, FY 2023-24",
                 section="outcome", type="numeric", unit="tCO2e per rupee", period="PY", pair="1390",
                 ask="Total Scope 3 emissions per rupee of turnover (previous year)", report_tables=["3.9"]),
    "2210": dict(key="green_credits_entity", label="Green credits generated or procured (entity)", section="outcome",
                 type="numeric", unit="credits", no_data=True,
                 ask="Number of green credits generated or procured by the listed entity", report_tables=[]),
    "2211": dict(key="green_credits_value_chain", label="Green credits (top ten value chain partners)",
                 section="outcome", type="numeric", unit="credits", no_data=True,
                 ask="Number of green credits generated or procured by the top ten value chain partners", report_tables=[]),
}

# Rubrics for the AI-scored questions come from the report's own quality scales
# (Tables 1.6, 1.7, 1.8 and 2.2), ordered from 0 to 100.
AI_RUBRICS = {
    "277": ["No certificate from the E-certificates reference list", "One certificate from the list",
            "Two certificates from the list", "Three certificates from the list", "Four or more certificates from the list"],
    "286": [
        "No clear targets or commitments mentioned, just written \"Yes\", or shared that they would be doing it in future.",
        "Targets are vague, generic, or lack measurable indicators.",
        "Targets are partially clear and measurable but lack ambition or completeness.",
        "Targets are specific, measurable, and time-bound with moderate ambition.",
        "Targets are highly specific, measurable, time-bound, and demonstrate strong ambition (e.g., science-based, aligned with global standards).",
    ],
    "295": [
        "No performance data provided or no action taken",
        "Minimal progress reported, with poor or no explanation for shortfalls",
        "Some progress made; partial achievement of targets with limited explanation for gaps",
        "Good progress with most targets achieved or well-justified reasons for any gaps",
        "Targets fully achieved or exceeded, supported by transparent, verifiable performance data",
    ],
    "1342": [
        "No projects undertaken or only intent expressed without any concrete action.",
        "Projects are ad-hoc, small in scale, or symbolic in nature with negligible measurable impact on GHG reduction.",
        "Projects show some measurable reduction in GHG emissions but are limited in scope, coverage, or ambition; outcomes are partially documented.",
        "Projects are well-defined, implemented at a reasonable scale, with measurable and time-bound GHG reductions; demonstrate moderate ambition and alignment with company goals.",
        "Projects are highly impactful, innovative, and large in scale; achieve significant, measurable, and time-bound GHG reductions; aligned with global best practices or standards (e.g., SBTi, Net Zero pathways).",
    ],
}

# Short, human names for the 22 NSE sectors (report Table 2.2 order).
SECTOR_SHORT = {
    "Automobile and Auto Components": "Auto and components",
    "Capital Goods": "Capital goods",
    "Chemicals": "Chemicals",
    "Construction": "Construction",
    "Construction Materials": "Construction materials",
    "Consumer Durables": "Consumer durables",
    "Consumer Services": "Consumer services",
    "Diversified": "Diversified",
    "Fast Moving Consumer Goods": "FMCG",
    "Financial Services": "Financial services",
    "Forest Materials": "Forest materials",
    "Healthcare": "Healthcare",
    "Information Technology": "Information technology",
    "Media Entertainment & Publication": "Media and entertainment",
    "Metals & Mining": "Metals and mining",
    "Oil Gas & Consumable Fuels": "Oil, gas and fuels",
    "Power": "Power",
    "Realty": "Realty",
    "Services": "Services",
    "Telecommunication": "Telecom",
    "Textiles": "Textiles",
    "Utilities": "Utilities",
}

# NSE sector codes from report Table 2.2 (PDF page 23).
SECTOR_NSE_CODE = {
    "Automobile and Auto Components": "IN0201", "Capital Goods": "IN0702", "Chemicals": "IN0101",
    "Construction": "IN0701", "Construction Materials": "IN0102", "Consumer Durables": "IN0202",
    "Consumer Services": "IN0206", "Diversified": "IN1201", "Fast Moving Consumer Goods": "IN0401",
    "Financial Services": "IN0501", "Forest Materials": "IN0104", "Healthcare": "IN0601",
    "Information Technology": "IN0801", "Media Entertainment & Publication": "IN0204", "Metals & Mining": "IN0103",
    "Oil Gas & Consumable Fuels": "IN0301", "Power": "IN1101", "Realty": "IN0205", "Services": "IN0901",
    "Telecommunication": "IN1001", "Textiles": "IN0203", "Utilities": "IN1102",
}

# Pillars for the derived composite. Equal-weighted means of Rating-sheet scores.
PILLARS = {
    "governance": ["232", "241", "250", "259", "268", "277", "286", "295", "308", "317", "326", "335", "344", "353"],
    "action": ["1329", "1340", "1341", "1342", "1387", "1560", "1561", "1828"],
    "performance": ["1330", "1332", "1334", "1335", "1336", "1337", "1338", "1339", "1388", "1390", "1391"],
}

# Absolute-emission values the report excludes from sector totals (verified:
# with these two exclusions every row of Tables 3.1 and 3.2 reproduces exactly).
REPORT_EXCLUSIONS = [
    {"company": "SIS Limited", "qids": ["1330", "1331", "1332", "1333"],
     "reason": "Reported Scope 1 and 2 values (up to 39.2 billion tCO2e) exceed the entire Power sector; excluded from sector totals in Report Tables 3.1 and 3.2."},
    {"company": "Patel Engineering Limited", "qids": ["1333"],
     "reason": "Previous-year Scope 2 of 31.3 billion tCO2e is implausible against current-year 136,691 tCO2e; excluded from Report Table 3.2 totals."},
]

# Per-rupee intensity above this value implies more than 10,000 tCO2e per crore
# of turnover, roughly 10x the median of the most carbon-intensive sectors
# (Report Table 3.5: Construction Materials 1,095.9, Power 1,079.0). Such values
# are shown as reported but flagged as a probable unit inconsistency and kept
# out of level rankings.
INTENSITY_PER_RUPEE_PLAUSIBLE_MAX = 1e-3

# Absolute Scope 1+2 below this share of the sector median is flagged as a
# probable scaled-unit filing (see build_dataset.magnitude_check).
MAGNITUDE_RATIO = 1e-3

# Source sector classifications that look like a row swap in the Base Data
# "Actual Sector" column (adjacent rows 378 and 379). They are kept as filed so
# that sector figures keep matching the report, and flagged wherever shown.
# Sector corrections. In the source sheet the sector column is displaced by one row for the fifteen consecutive
# companies from Hi-Tech Pipes to Hindware Home Innovation (each carries the sector of the row above it, and the first
# carries the last one's). The corrected sectors below restore the alignment. Agreed in review on 2 Oct 2026, starting
# with Hindalco Industries -> Metals & Mining.
SECTOR_CORRECTIONS = {
    "Hi-Tech Pipes Limited": "Capital Goods",
    "Hikal Limited": "Healthcare",
    "Himadri Speciality Chemical Limited": "Chemicals",
    "Himatsingka Seide Limited": "Textiles",
    "HINDALCO INDUSTRIES LIMITED": "Metals & Mining",
    "Hinduja Global Solutions Limited": "Services",
    "HINDUSTAN AERONAUTICS LIMITED": "Capital Goods",
    "Hindustan Construction Company Limited": "Construction",
    "Hindustan Copper Limited": "Metals & Mining",
    "Hindustan Foods Limited": "Fast Moving Consumer Goods",
    "Hindustan Oil Exploration Company Limited": "Oil Gas & Consumable Fuels",
    "HINDUSTAN PETROLEUM CORPORATION LIMITED": "Oil Gas & Consumable Fuels",
    "Hindustan Unilever Limited": "Fast Moving Consumer Goods",
    "HINDUSTAN ZINC LIMITED": "Metals & Mining",
    "Hindware Home Innovation Limited": "Consumer Durables",
    "PUNJAB & SIND BANK": "Financial Services",
    # isolated entries filed under an unrelated sector
    "Narayana Hrudayalaya Limited": "Healthcare",
    "Dr. Lal Path Labs Limited": "Healthcare",
    "UNITED BREWERIES LIMITED": "Fast Moving Consumer Goods",
    # the V block (rows from V-Mart Retail to Vishnu Chemicals): the sector column is displaced, mostly by two rows
    "V-Mart Retail Limited": "Consumer Services",
    "VA Tech Wabag Limited": "Utilities",
    "Vadilal Industries Limited": "Fast Moving Consumer Goods",
    "Vaibhav Global Limited": "Consumer Durables",
    "Vakrangee Limited": "Information Technology",
    "Valiant Organics Limited": "Chemicals",
    "Valor Estate Limited": "Realty",
    "Vardhman Special Steels Limited": "Capital Goods",
    "Vardhman Textiles Limited": "Textiles",
    "Varroc Engineering Limited": "Automobile and Auto Components",
    "Vedant Fashions Limited": "Consumer Services",
    "VEDANTA LIMITED": "Metals & Mining",
    "Venky's (India) Limited": "Fast Moving Consumer Goods",
    "Venus Pipes & Tubes Limited": "Capital Goods",
    "Veranda Learning Solutions Limited": "Consumer Services",
    "Vijaya Diagnostic Centre Limited": "Healthcare",
    "Vindhya Telelinks Limited": "Telecommunication",
    "VIP Industries Limited": "Consumer Durables",
    "Visaka Industries Limited": "Construction Materials",
    "Vishnu Chemicals Limited": "Chemicals",
}

CLASSIFICATION_NOTES = {}
