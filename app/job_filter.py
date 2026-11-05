
import html
import time

import requests

from app.job_filter import filter_jobs


API_URL = "https://himalayas.app/jobs/api/search"

HEADERS = {
    "User-Agent": "AgentDeskAI/0.8",
    "Accept": "application/json",
}

SEARCH_TERMS = [
    "React",
    "Next.js",
    "Frontend",
    "TypeScript",
    "JavaScript",
]

MAX_PAGES = 3
MAX_REQUESTS = 15


def normalize_job(record: dict) -> dict | None:
    title = record.get("title")
    company = record.get("companyName")
    guid = record.get("guid")
    apply_url = record.get("applicationLink")

    if not all(
        isinstance(value, str) and value.strip()
        for value in (title, company, guid, apply_url)
    ):
        return None

    if not guid.startswith("https://himalayas.app/"):
        return None

    if not apply_url.startswith("https://"):
        return None

    return {
        "id": guid,
        "title": html.unescape(title),
        "company": html.unescape(company),
        "location_restrictions": record.get(
            "locationRestrictions"
        ),
        "timezone_restrictions": record.get(
            "timezoneRestrictions"
        ),
        "published": record.get("pubDate"),
        "expiry_date": record.get("expiryDate"),
        "employment_type": record.get("employmentType"),
        "seniority": record.get("seniority"),
        "salary_min": record.get("minSalary"),
        "salary_max": record.get("maxSalary"),
        "currency": record.get("currency"),
        "salary_period": record.get("salaryPeriod"),
        "application_url": apply_url,
        "source_url": guid,
        "source": "Himalayas",
    }


def search_jobs(
    keyword: str = "React",
    limit: int = 5,
    role: str = "frontend",
    country: str = "Sri Lanka",
) -> dict:
    limit = max(1, min(int(limit), 20))
    keyword = keyword.strip()
    country = country.strip()

    if not keyword or not country:
        return {
            "success": False,
            "error": "Keyword and country are required.",
            "jobs": [],
        }

    if role != "frontend":
        return {
            "success": False,
            "error": "Only frontend role filtering is supported.",
            "jobs": [],
        }

    terms = list(dict.fromkeys(
        [keyword] + SEARCH_TERMS
    ))

    candidates = {}
    errors = []
    requests_made = 0
    pages_scanned = 0

    for term in terms:
        if requests_made >= MAX_REQUESTS:
            break

        for page in range(1, MAX_PAGES + 1):
            if requests_made >= MAX_REQUESTS:
                break

            requests_made += 1

            try:
                response = requests.get(
                    API_URL,
                    params={
                        "q": term,
                        "country": country,
                        "sort": "relevant",
                        "page": page,
                    },
                    headers=HEADERS,
                    timeout=20,
                )

                response.raise_for_status()
                data = response.json()

                if not isinstance(data, dict):
                    raise ValueError("Invalid API response")

                records = data.get("jobs", [])

                if not isinstance(records, list):
                    raise ValueError("Invalid jobs list")

                pages_scanned += 1

                if not records:
                    break

                for record in records:
                    if not isinstance(record, dict):
                        continue

                    job = normalize_job(record)

                    if job:
                        candidates[job["id"]] = job

                # Stop scanning this term if the API
                # returns fewer than a full page.
                if len(records) < 20:
                    break

            except requests.RequestException as error:
                errors.append(
                    f"{term}, page {page}: {error}"
                )
                break

            except (ValueError, TypeError) as error:
                errors.append(
                    f"{term}, page {page}: {error}"
                )
                break

        # Be considerate of the shared public API.
        if requests_made < MAX_REQUESTS:
            time.sleep(0.3)

    matched = filter_jobs(
        list(candidates.values()),
        role=role,
        country=country,
    )

    return {
        "success": pages_scanned > 0,
        "keyword": keyword,
        "role": role,
        "country": country,
        "count": len(matched[:limit]),
        "total_matches": len(matched),
        "candidates_checked": len(candidates),
        "requests_made": requests_made,
        "jobs": matched[:limit],
        "source": "Himalayas",
        "errors": errors,
        "note": (
            "Country-filtered results come from Himalayas. "
            "Eligibility and job availability must still be "
            "confirmed before applying. Empty restrictions "
            "are marked unknown."
        ),
    }
