#!/usr/bin/env python3
"""Get OpenAlex IDs for journals."""
import requests
import sys
import time
from pathlib import Path

# AAA & AA journals to add
JOURNALS_TO_ADD = [
    # AAA - Economics
    "American Economic Review",
    "Journal of Political Economy",
    "Quarterly Journal of Economics",
    "Review of Economic Studies",
    "Econometrica",

    # AAA - Political Science
    "American Political Science Review",
    "American Journal of Political Science",
    "World Politics",

    # AAA - Sociology
    "American Journal of Sociology",
    "American Sociological Review",
    "Social Forces",

    # AA - Economics (selected)
    "Journal of Public Economics",
    "Journal of Urban Economics",
    "Review of Economics and Statistics",
    "Journal of Monetary Economics",
    "Economic Journal",
    "Journal of Economic Theory",
    "Games and Economic Behavior",
    "Journal of Economic History",
    "Journal of Financial Economics",
    "Rand Journal of Economics",
    "Journal of Economics and Management Strategy",
    "Theoretical Economics",
    "Journal of the European Economic Association",
    "Journal of Development Economics",
    "European Economic Review",
    "Journal of Economic Behavior & Organization",
    "Regional Science and Urban Economics",
    "Journal of Labor Economics",
    "Oxford Economic Papers",
    "Scandinavian Journal of Economics",
    "National Tax Journal",
    "Journal of Financial Econometrics",
    "Experimental Economics",
    "Economic Inquiry",
    "Southern Economic Journal",
    "International Economic Review",
    "Economic Modelling",
    "Journal of Economic Dynamics and Control",
    "Journal of Economic Geography",
    "Journal of Regulatory Economics",
    "Health Economics",
    "International Journal of Industrial Organization",
    "Journal of Human Resources",
    "Journal of Industrial Economics",
    "Journal of International Economics",
    "Journal of Law and Economics",
    "Journal of Money, Credit and Banking",
    "Macroeconomic Dynamics",
    "Mathematical Finance",
    "Quantitative Economics",
    "Review of Economic Dynamics",
    "Social Choice and Welfare",
    "Theory and Decision",
    "World Bank Economic Review",

    # AA - Sociology
    "Demography",
    "Social Psychology Quarterly",
    "Social Problems",
    "Sociological Methodology",
    "Social Science Research",
    "Social Science History",
    "Journal of Health and Social Behavior",
    "Mobilization",
    "Sociological Forum",
    "Social Networks",

    # AA - Political Science (selected)
    "British Journal of Political Science",
    "Comparative Political Studies",
    "European Journal of Political Research",
    "Government and Opposition",
    "International Organization",
    "International Security",
    "International Studies Quarterly",
    "Journal of Conflict Resolution",
    "Journal of Peace Research",
    "Journal of Politics",
    "Party Politics",
    "Political Analysis",
    "Political Behavior",
    "Political Geography",
    "Polity",
    "Public Opinion Quarterly",
    "Legislative Studies Quarterly",

    # AA - Public Administration
    "Administration & Society",
    "American Review of Public Administration",
    "International Public Management Journal",
    "Journal of Policy Analysis and Management",
    "Journal of Public Administration Research and Theory",
    "Journal of European Public Policy",
    "Policy & Politics",
    "Policy Sciences",
    "Public Administration",
    "Public Administration and Development",
    "Public Administration Review",
    "Public Management Review",
]


def get_openalex_id(journal_name: str) -> tuple[str, str] | None:
    """Get OpenAlex ID for a journal."""
    url = f"https://api.openalex.org/sources"
    params = {
        "filter": f"display_name.search:{journal_name},type:journal",
        "per-page": 5
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("results"):
            # Find exact match
            for r in data["results"]:
                if r["display_name"].lower() == journal_name.lower():
                    return r["display_name"], r["id"].split("/")[-1]
            # Return first result if no exact match
            return data["results"][0]["display_name"], data["results"][0]["id"].split("/")[-1]
    except Exception as e:
        print(f"Error fetching {journal_name}: {e}", file=sys.stderr)

    return None


def main():
    """Main entry point."""
    results = []
    for journal in JOURNALS_TO_ADD:
        print(f"Fetching: {journal}")
        result = get_openalex_id(journal)
        if result:
            display_name, openalex_id = result
            results.append((display_name, openalex_id))
            print(f"  -> {openalex_id}")
        else:
            print(f"  -> NOT FOUND")
        time.sleep(0.1)  # Rate limiting

    # Print Python dict format
    print("\n# Journal mappings")
    for display_name, openalex_id in results:
        # Create alias
        words = display_name.split()
        if len(words) >= 2:
            # JPE, QJE, AER style
            alias = "".join(w[0] for w in words if w[0].isupper()).replace("J", "J")
            # Handle special cases
            if "Journal of" in display_name:
                parts = display_name.split()
                if "Economics" in parts:
                    idx = parts.index("Economics")
                    alias = "".join(p[0] for p in parts[:idx] if p not in ["of", "the"])
                    alias += "Econ"
        else:
            alias = display_name[:10].upper()

        print(f'    "{alias}": "{openalex_id}",  # {display_name}')


if __name__ == "__main__":
    main()
