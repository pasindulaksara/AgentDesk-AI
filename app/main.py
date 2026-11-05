
import html
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from fastapi import FastAPI, Query
from pydantic import BaseModel


app = FastAPI(
    title="AgentDesk AI",
    version="1.0.0",
    description="AI assistant with real remote job search",
)

API_URL = "https://himalayas.app/jobs/api/search"

HEADERS = {
    "User-Agent": "AgentDeskAI/1.0",
    "Accept": "application/json",
}

SEARCH_TERMS = [
    "React",
    "Next.js",
    "Frontend",
    "TypeScript",
]

EXCLUDED_TITLES = [
    "react native",
    "mobile engineer",
    "mobile developer",
    "android developer",
    "ios developer",
    "ui/ux designer",
    "ux designer",
    "graphic designer",
    "product designer",
]

ROLE_TERMS = {
    "react": 10,
    "next.js": 10,
    "nextjs": 10,
    "frontend": 9,
    "front-end": 9,
    "front end": 9,
    "web developer": 8,
    "typescript": 6,
    "javascript": 6,
    "full stack": 5,
    "fullstack": 5,
}


class ChatRequest(BaseModel):
    message: str


def error_response(message):
    return {
        "success": False,
        "message": message,
    }


def valid_https_url(url):
    if not isinstance(url, str):
        return False

    try:
        parsed = urlparse(url)

        return (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
        )
    except ValueError:
        return False


def job_score(title, keyword):
    title = title.lower()
    keyword = keyword.lower().strip()

    if any(term in title for term in EXCLUDED_TITLES):
        return 0

    score = 0

    for term, points in ROLE_TERMS.items():
        if term in title:
            score += points

    # A relevant frontend title is required.
    if score == 0:
        return 0

    if keyword and keyword in title:
        score += 15

    return score


def country_status(restrictions, country):
    if restrictions is None:
        return "unknown"

    if isinstance(restrictions, str):
        restrictions = [restrictions]

    if not isinstance(restrictions, list):
        return "unknown"

    locations = [
        str(item).strip().lower()
        for item in restrictions
    ]

    if not locations:
        return "unknown"

    if country.lower() in locations:
        return "eligible"

    if any(
        value in ("worldwide", "global", "anywhere")
        for value in locations
    ):
        return "eligible"

    return "restricted"


def is_expired(value):
    if value is None:
        return False

    try:
        if isinstance(value, (int, float)):
            timestamp = float(value)

            if timestamp > 10**12:
                timestamp /= 1000

            return timestamp < datetime.now(
                timezone.utc
            ).timestamp()

        if isinstance(value, str):
            date = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )

            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)

            return date < datetime.now(timezone.utc)

    except (ValueError, TypeError, OverflowError):
        pass

    return False


def normalize_job(record, keyword, country):
    if not isinstance(record, dict):
        return None

    title = record.get("title")
    company = record.get("companyName")
    source_url = record.get("guid")
    application_url = record.get("applicationLink")

    if not all(
        isinstance(value, str) and value.strip()
        for value in (
            title,
            company,
            source_url,
            application_url,
        )
    ):
        return None

    if not valid_https_url(source_url):
        return None

    if urlparse(source_url).hostname != "himalayas.app":
        return None

    if not valid_https_url(application_url):
        return None

    title = html.unescape(title.strip())
    company = html.unescape(company.strip())

    score = job_score(title, keyword)

    if score == 0:
        return None

    restrictions = record.get("locationRestrictions")

    eligibility = country_status(
        restrictions,
        country,
    )

    if eligibility == "restricted":
        return None

    if is_expired(record.get("expiryDate")):
        return None

    return {
        "id": source_url,
        "title": title,
        "company": company,
        "match_score": score,
        "country_eligibility": eligibility,
        "location_restrictions": restrictions,
        "published": record.get("pubDate"),
        "expiry_date": record.get("expiryDate"),
        "employment_type": record.get("employmentType"),
        "seniority": record.get("seniority"),
        "salary_min": record.get("minSalary"),
        "salary_max": record.get("maxSalary"),
        "currency": record.get("currency"),
        "application_url": application_url,
        "source_url": source_url,
        "source": "Himalayas",
    }


def find_real_jobs(keyword, limit, country):
    terms = list(dict.fromkeys(
        [keyword] + SEARCH_TERMS
    ))

    candidates = {}
    errors = []
    successful_requests = 0
    requests_made = 0

    # Maximum 8 API requests per search.
    for term in terms[:4]:
        for page in range(1, 3):
            requests_made += 1

            try:
                response = requests.get(
                    API_URL,
                    params={
                        "q": term,
                        "page": page,
                        "sort": "relevant",
                    },
                    headers=HEADERS,
                    timeout=8,
                )

                response.raise_for_status()
                data = response.json()

                if not isinstance(data, dict):
                    raise ValueError(
                        "Unexpected API response"
                    )

                records = data.get("jobs")

                if not isinstance(records, list):
                    raise ValueError(
                        "Missing or invalid jobs list"
                    )

                successful_requests += 1

                for record in records:
                    job = normalize_job(
                        record,
                        keyword,
                        country,
                    )

                    if job:
                        candidates[job["id"]] = job

                if not records:
                    break

            except (
                requests.RequestException,
                ValueError,
                TypeError,
            ) as error:
                errors.append(
                    f"{term} page {page}: {error}"
                )
                break

    jobs = list(candidates.values())

    jobs.sort(
        key=lambda job: (
            job["country_eligibility"] == "eligible",
            job["match_score"],
            str(job.get("published") or ""),
        ),
        reverse=True,
    )

    return {
        "success": successful_requests > 0,
        "keyword": keyword,
        "country": country,
        "count": min(len(jobs), limit),
        "total_matches": len(jobs),
        "requests_made": requests_made,
        "jobs": jobs[:limit],
        "source": "Himalayas",
        "errors": errors,
        "note": (
            "Results are from a public job feed. "
            "Country eligibility is based on published "
            "location restrictions. Unknown eligibility "
            "requires confirmation. Listings may close "
            "or change after retrieval."
        ),
    }


@app.get("/")
def home():
    return {
        "success": True,
        "message": "AgentDesk AI is running!",
        "version": "1.0.0",
    }


@app.post("/chat")
def chat(request: ChatRequest):
    try:
        from app.agent import ask_ai

        response = ask_ai(request.message)

        return {
            "success": True,
            "response": response,
        }

    except Exception as error:
        return {
            "success": False,
            "response": None,
            "error": str(error),
        }


@app.get("/jobs")
def get_jobs(
    keyword: str = Query(
        default="React",
        min_length=1,
    ),
    limit: int = Query(
        default=5,
        ge=1,
        le=20,
    ),
    country: str = Query(
        default="Sri Lanka",
        min_length=1,
    ),
):
    return find_real_jobs(
        keyword=keyword.strip(),
        limit=limit,
        country=country.strip(),
    )
