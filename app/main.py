
from fastapi import FastAPI
from pydantic import BaseModel
from app.agent import ask_ai

app = FastAPI(title="AgentDesk AI")


class ChatRequest(BaseModel):
    message: str


@app.get("/")
def home():
    return {
        "success": True,
        "message": "AgentDesk AI is running!",
        "version": "0.1.0"
    }


@app.post("/chat")
def chat_with_ai(request: ChatRequest):
    answer = ask_ai(request.message)

    return {
        "success": True,
        "response": answer
    }
