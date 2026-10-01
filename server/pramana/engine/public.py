"""What an end user sees as the source of a figure.

Every value comes from a company's own BRSR filing, so that is what a citation
names: the company, the disclosure item in plain words, the financial year and
where in the BRSR format the item sits. Nothing here refers to how the data is
stored or processed.
"""
from __future__ import annotations

CY, PY = "FY 2024-25", "FY 2023-24"
SEC_B = "BRSR Section B: management and process disclosures"
P6_E = "BRSR Section C, Principle 6: essential indicators"
P6_L = "BRSR Section C, Principle 6: leadership indicators"

# qid -> (disclosure item, financial year, place in the BRSR format)
ITEMS: dict[str, tuple[str, str, str]] = {
    "232": ("Policy covering Principle 6 (environment)", CY, SEC_B),
    "241": ("Policy approved by the Board", CY, SEC_B),
    "250": ("Web link of the policies", CY, SEC_B),
    "259": ("Policy translated into procedures", CY, SEC_B),
    "268": ("Policies extend to value chain partners", CY, SEC_B),
    "277": ("Codes, certifications, labels and standards adopted", CY, SEC_B),
    "286": ("Specific commitments, goals and targets with timelines", CY, SEC_B),
    "295": ("Performance against commitments, goals and targets", CY, SEC_B),
    "308": ("Who reviews performance against the policies", CY, SEC_B),
    "317": ("Who reviews compliance with statutory requirements", CY, SEC_B),
    "326": ("How often performance against the policies is reviewed", CY, SEC_B),
    "335": ("How often statutory compliance is reviewed", CY, SEC_B),
    "344": ("Independent assessment of the working of policies", CY, SEC_B),
    "353": ("Agency that assessed the working of policies", CY, SEC_B),
    "1329": ("Applicability of the GHG emissions disclosure", CY, P6_E),
    "1330": ("Total Scope 1 emissions", CY, P6_E),
    "1331": ("Total Scope 1 emissions", PY, P6_E),
    "1332": ("Total Scope 2 emissions", CY, P6_E),
    "1333": ("Total Scope 2 emissions", PY, P6_E),
    "1334": ("Scope 1 and Scope 2 emission intensity per rupee of turnover", CY, P6_E),
    "1335": ("Scope 1 and Scope 2 emission intensity per rupee of turnover", PY, P6_E),
    "1336": ("Scope 1 and Scope 2 emission intensity per rupee of turnover, adjusted for PPP", CY, P6_E),
    "1337": ("Scope 1 and Scope 2 emission intensity per rupee of turnover, adjusted for PPP", PY, P6_E),
    "1338": ("Scope 1 and Scope 2 emission intensity in terms of physical output", CY, P6_E),
    "1339": ("Scope 1 and Scope 2 emission intensity in terms of physical output", PY, P6_E),
    "1340": ("Independent assessment or assurance of GHG emissions", CY, P6_E),
    "1341": ("Projects to reduce GHG emissions", CY, P6_E),
    "1342": ("Details of projects to reduce GHG emissions", CY, P6_E),
    "1387": ("Scope 3 emissions disclosure", CY, P6_L),
    "1388": ("Total Scope 3 emissions", CY, P6_L),
    "1389": ("Total Scope 3 emissions", PY, P6_L),
    "1390": ("Scope 3 emission intensity per rupee of turnover", CY, P6_L),
    "1391": ("Scope 3 emission intensity per rupee of turnover", PY, P6_L),
    "1560": ("Independent assurance of Scope 3 emissions", CY, P6_L),
    "1561": ("Agency that assured Scope 3 emissions", CY, P6_L),
}

# Short topic names for sentences: "its disclosure on targets".
TOPIC: dict[str, str] = {
    "286": "commitments, goals and targets", "295": "performance against its targets",
    "1342": "projects to reduce GHG emissions", "277": "codes, certifications and standards",
    "353": "the agency that assessed its policies", "1561": "the agency that assured its Scope 3 emissions",
}

# Plain-language notes for values that look like they were filed in a different unit.
FLAG_NOTE = {
    "magnitude_check": "This figure is shown exactly as disclosed. It is far lower than is typical for the sector, which "
                       "suggests it was reported in a different unit (for example thousand tonnes), so it is not "
                       "compared with other companies.",
    "unit_check": "The disclosed emission intensity appears to use a different unit from most filings. It is shown as "
                  "disclosed and is not compared with other companies.",
    "report_exclusion": "One disclosed value appears to be in a different unit and is left out of totals.",
}


def item(qid: str) -> tuple[str, str, str]:
    return ITEMS.get(qid, ("BRSR disclosure", CY, "BRSR"))
