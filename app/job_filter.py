
import re


def match_job_type(job: dict, role: str = "frontend") -> bool:
    """Filter jobs based on the requested role."""

    title = job.get("title", "").lower()

    if role == "frontend":
        excluded = [
            "react native",
            "mobile engineer",
            "mobile developer",
            "ui/ux designer",
            "ux designer",
            "graphic designer",
            "product designer",
        ]

        if any(term in title for term in excluded):
            return False

        relevant = [
            "frontend",
            "front-end",
            "front end",
            "react",
            "next.js",
            "web developer",
            "javascript",
            "typescript",
            "full stack",
            "fullstack",
            "software engineer",
        ]

        return any(term in title for term in relevant)

    return True


def check_country(job: dict, country: str = "Sri Lanka") -> str:
    """
    Return eligible, restricted, or unknown.

    Empty restrictions do not prove worldwide eligibility.
    """

    restrictions = job.get("location_restrictions")

    if not restrictions:
        return "unknown"

    if isinstance(restrictions, str):
        restrictions = [restrictions]

    locations = [str(item).lower() for item in restrictions]

    if country.lower() in locations:
        return "eligible"

    if any(
        location in ("worldwide", "anywhere", "global")
        for location in locations
    ):
        return "eligible"

    return "restricted"


def filter_jobs(
    jobs: list,
    role: str = "frontend",
    country: str = "Sri Lanka",
) -> list:
    """Filter jobs and attach eligibility information."""

    filtered = []

    for job in jobs:
        if not match_job_type(job, role):
            continue

        eligibility = check_country(job, country)

        if eligibility == "restricted":
            continue

        filtered.append({
            **job,
            "country_eligibility": eligibility,
        })

    return filtered
