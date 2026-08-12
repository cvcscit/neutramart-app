import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional

from app.auth import get_current_user
from app.agent_client import invoke_agent, AgentError
from app.regions import get_data_context
from app.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = []


@router.post("/chat")
@limiter.limit("20/minute")
def chat(
    request: Request,
    body: ChatRequest,
    _user=Depends(get_current_user),
    ctx: dict = Depends(get_data_context),
):
    """Proxy the chat turn to the user's REGIONAL NutraSmart agent on AgentCore Runtime.

    The agent pulls the user's scans / summary / health profile on demand via its tools,
    all within the user's data region.
    """
    user_id = _user["email"].replace("@", "_at_").replace(".", "_")
    history = [{"role": m.role, "content": m.content} for m in (body.history or [])]

    try:
        result = invoke_agent(
            {
                "action": "chat",
                "user_id": user_id,
                "message": body.message,
                "history": history,
            },
            agent_arn=ctx["agent_arn"],
        )
    except AgentError as e:
        logger.error("Chat failed: %s", e)
        raise HTTPException(status_code=502, detail="Chat failed. Please try again.")

    return {"reply": result.get("reply", "")}
