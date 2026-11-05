
import html
import ipaddress
import json
import re
import socket
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from ddgs import DDGS


HEADERS = {
    "User-Agent": "AgentDeskAI/0.6",
    "Accept": "application/json",
}


def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b


def web_search(query: str) -> str:
    """Search the public web for information."""
    try:
        results = DDGS().text(query, max_results=5)
        return json.dumps(
            [
                {
                    "title": item.get("title"),
                    "url": item.get("href"),
                    "summary": item.get("body"),
                }
                for item in results
            ],
            ensure_ascii=False,
        )
    except Exception as error:
        return f"Web search failed: {error}"


def inspect_website(url: str) -> str:
    """Inspect basic HTML SEO metadata on a public website."""
    try:
        parsed = urlparse(url)

        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 80, 443)
        ):
            return "Invalid public URL."

        if parsed.hostname.lower() == "localhost":
            return "Local URLs are not allowed."

        for result in socket.getaddrinfo(parsed.hostname, None):
            ip = ipaddress.ip_address(result[4][0])
            if not ip.is_global:
                return "Restricted network address."

        response = requests.get(
            url,
            timeout=10,
            allow_redirects=False,
            stream=True,
            headers={"User-Agent": "AgentDeskAI/0.6"},
        )

        try:
            if 300 <= response.status_code < 400:
                return "Redirects are not followed."

            response.raise_for_status()

            if "text/html" not in response.headers.get(
                "Content-Type", ""
            ).lower():
                return "Not an HTML page."

            content = bytearray()

            for chunk in response.iter_content(8192):
                remaining = 500000 - len(content)
                if remaining <= 0:
                    break
                content.extend(chunk[:remaining])

            soup = BeautifulSoup(
                bytes(content),
                "html.parser",
            )
        finally:
            response.close()

        title = (
            soup.title.get_text(strip=True)
            if soup.title else None
        )

        description = soup.find(
            "meta",
            attrs={"name": "description"},
        )

        viewport = soup.find(
            "meta",
            attrs={"name": "viewport"},
        )

        images = soup.find_all("img")

        return json.dumps({
            "url": url,
            "title": title,
            "meta_description": (
                description.get("content")
                if description else None
            ),
            "h1_headings": [
                h.get_text(" ", strip=True)
                for h in soup.find_all("h1")
            ],
            "total_images": len(images),
            "images_missing_alt": sum(
                not image.has_attr("alt")
                for image in images
            ),
            "viewport_present": viewport is not None,
        }, ensure_ascii=False)

    except Exception as error:
        return f"Website inspection failed: {error}"


def search_himalayas(keyword: str, limit: int) -> list:
    """Search real remote job records on Himalayas."""
    response = requests.get(
        "https://himalayas.app/jobs/api/search",
        params={
            "q": keyword,
            "sort": "relevant",
            "page": 1,
        },
        headers=HEADERS,
        timeout=20,
    )

    response.raise_for_status()
    data = response.json()

    if not isinstance(data, dict):
        raise ValueError("Unexpected Himalayas response.")

    records = data.get("jobs", [])

    if not isinstance(records, list):
        raise ValueError("Invalid Himalayas job records.")

    jobs = []

    for record in records:
        if not isinstance(record, dict):
            continue

        title = record.get("title")
        company = record.get("companyName")
        url = record.get("applicationLink")
        guid = record.get("guid")

        if not all([
            isinstance(title, str) and title.strip(),
            isinstance(company, str) and company.strip(),
            isinstance(url, str) and url.startswith("https://"),
            isinstance(guid, str) and guid.startswith(
                "https://himalayas.app/"
            ),
        ]):
            continue

        jobs.append({
            "id": guid,
            "title": html.unescape(title),
            "company": html.unescape(company),
            "location_restrictions": record.get(
                "locationRestrictions", []
            ),
            "published": record.get("pubDate"),
            "salary_min": record.get("minSalary"),
            "salary_max": record.get("maxSalary"),
            "currency": record.get("currency"),
            "salary_period": record.get("salaryPeriod"),
            "application_url": url,
            "source_url": guid,
            "source": "Himalayas",
        })

        if len(jobs) >= limit:
            break

    return jobs


def search_remoteok(keyword: str, limit: int) -> list:
    """Search the recent Remote OK feed as a fallback."""
    response = requests.get(
        "https://remoteok.com/api",
        headers={
            "User-Agent": "Mozilla/5.0 AgentDeskAI/0.6",
            "Accept": "application/json",
        },
        timeout=20,
    )

    response.raise_for_status()
    records = response.json()

    if not isinstance(records, list):
        raise ValueError("Unexpected Remote OK response.")

    keywords = [
        word.lower()
        for word in re.findall(r"[\w.+#-]+", keyword)
        if word.lower() not in {
            "developer", "engineer", "jobs",
            "job", "remote", "and", "or",
        }
    ]

    if not keywords:
        keywords = [keyword.lower().strip()]

    matches = []

    for record in records:
        if not isinstance(record, dict):
            continue

        title = record.get("position")
        company = record.get("company")
        url = record.get("url")

        if not (
            title and company
            and isinstance(url, str)
            and url.startswith("https://remoteok.com/")
        ):
            continue

        description = BeautifulSoup(
            str(record.get("description") or ""),
            "html.parser",
        ).get_text(" ", strip=True)

        tags = record.get("tags") or []
        if not isinstance(tags, list):
            tags = []

        searchable = " ".join([
            str(title),
            " ".join(map(str, tags)),
            description,
        ]).lower()

        score = sum(
            bool(re.search(
                r"(?<!\w)" + re.escape(word) + r"(?!\w)",
                searchable,
            ))
            for word in keywords
        )

        if score == 0:
            continue

        matches.append({
            "id": str(record.get("id")),
            "title": html.unescape(str(title)),
            "company": html.unescape(str(company)),
            "location_restrictions": record.get("location"),
            "published": record.get("date"),
            "application_url": url,
            "source_url": url,
            "source": "Remote OK",
            "_score": score,
        })

    matches.sort(
        key=lambda job: job["_score"],
        reverse=True,
    )

    for job in matches:
        job.pop("_score", None)

    return matches[:limit]


def find_jobs(keyword: str, limit: int = 5) -> str:
    """
    Find real remote jobs from public job APIs.

    Himalayas is the primary source.
    Remote OK is used if additional results are needed.
    """
    limit = max(1, min(int(limit), 10))
    keyword = keyword.strip()

    if not keyword:
        return json.dumps({
            "success": False,
            "error": "Please provide a job keyword.",
        })

    jobs = []
    errors = []
    sources_checked = []

    try:
        sources_checked.append("Himalayas")
        jobs.extend(search_himalayas(keyword, limit))
    except Exception as error:
        errors.append(f"Himalayas: {error}")

    if len(jobs) < limit:
        try:
            sources_checked.append("Remote OK")
            jobs.extend(
                search_remoteok(keyword, limit - len(jobs))
            )
        except Exception as error:
            errors.append(f"Remote OK: {error}")

    unique_jobs = []
    seen = set()

    for job in jobs:
        key = (job["source"], job["id"])

        if key in seen:
            continue

        seen.add(key)
        unique_jobs.append(job)

    return json.dumps({
        "success": len(errors) < len(sources_checked),
        "keyword": keyword,
        "count": len(unique_jobs),
        "jobs": unique_jobs[:limit],
        "sources_checked": sources_checked,
        "errors": errors,
        "note": (
            "Listings are sourced from job APIs. "
            "Check the original listing for current availability "
            "and location eligibility before applying."
        ),
    }, ensure_ascii=False, indent=2)
