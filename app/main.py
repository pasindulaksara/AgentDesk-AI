
from fastapi import FastAPI, Query
from pydantic import BaseModel
import json

from app.agent import ask_ai
from app.tools import find_jobs
from app.job_filter import filter_jobs


app = FastAPI(
    title="AgentDesk AI",
    version="0.7.0",
)


class ChatRequest(BaseModel):
    message: str


@app.get("/")
def home():
    return {
        "success": True,
        "message": "AgentDesk AI is running!",
        "version": "0.7.0",
    }


@app.post("/chat")
def chat(request: ChatRequest):
    return {
        "success": True,
        "response": ask_ai(request.message),
    }


@app.get("/jobs")
def get_jobs(
    keyword: str = Query(..., min_length=1),
    limit: int = Query(default=5, ge=1, le=10),
    role: str = Query(default="frontend"),
    country: str = Query(default="Sri Lanka"),
):
    # Retrieve up to 10 candidate jobs before filtering.
    # A larger result pool can be added later.
    result = json.loads(find_jobs(keyword, 10))

    jobs = filter_jobs(
        result.get("jobs", []),
        role=role,
        country=country,
    )

    return {
        "success": result.get("success", False),
        "keyword": keyword,
        "role": role,
        "country": country,
        "count": len(jobs[:limit]),
        "jobs": jobs[:limit],
        "sources_checked": result.get("sources_checked", []),
        "errors": result.get("errors", []),
        "note": (
            "Only matching job titles are included. "
            "Eligibility is inferred from published location "
            "restrictions and is not independently verified. "
            "Unknown eligibility requires manual confirmation."
        ),
    }
