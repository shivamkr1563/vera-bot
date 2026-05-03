from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Set, Any, Tuple, Optional
from datetime import datetime, timezone
import uuid
import time
from composer import compose_message, handle_reply_turn, is_auto_reply as check_auto_reply

# Initialize FastAPI app
app = FastAPI()

# In-memory data storage
contexts: Dict[Tuple[str, str], Dict[str, Any]] = {}  # (scope, context_id) -> {version, payload, ...}
conversations: Dict[str, Dict[str, Any]] = {}  # conversation_id -> {merchant_id, customer_id, turns, status, auto_reply_count}
merchant_auto_reply_count: Dict[str, int] = {}  # merchant_id -> auto_reply_count (tracks across conversations)
sent_suppression: Set[str] = set()  # suppression keys already sent

# Server start time for uptime calculation
server_start_time = time.time()


# Pydantic models for request/response
class ContextRequest(BaseModel):
    scope: str
    context_id: str
    version: int
    payload: Dict[str, Any]
    delivered_at: str


class ContextResponse(BaseModel):
    accepted: bool
    reason: str = None
    ack_id: str = None
    stored_at: str = None


class TickRequest(BaseModel):
    now: str
    available_triggers: List[str]


class TickAction(BaseModel):
    conversation_id: str
    merchant_id: str
    body: str
    cta: str
    rationale: str


class TickResponse(BaseModel):
    actions: List[TickAction]


class ReplyRequest(BaseModel):
    conversation_id: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    from_role: Optional[str] = "merchant"
    message: Optional[str] = None
    body: Optional[str] = None
    received_at: Optional[str] = None
    turn_number: Optional[int] = 0


class ReplyAction(BaseModel):
    action: str  # send, wait, or end
    body: Optional[str] = None
    cta: Optional[str] = None
    rationale: str = ""


class HealthResponse(BaseModel):
    status: str
    uptime_seconds: int
    contexts_loaded: Dict[str, int]


class MetadataResponse(BaseModel):
    team_name: str
    team_members: List[str]
    model: str
    approach: str
    contact_email: str
    version: str
    submitted_at: str


@app.get("/")
def root():
    return {"status": "ok", "service": "Vera Bot", "version": "1.0.0"}

# Endpoint 1: GET /v1/healthz
@app.get("/v1/healthz", response_model=HealthResponse)
def healthz():
    """Health check endpoint with server status and context counts."""
    uptime = int(time.time() - server_start_time)
    
    # Count contexts by scope
    contexts_by_scope = {
        "category": 0,
        "merchant": 0,
        "customer": 0,
        "trigger": 0
    }
    
    for (scope, _), _ in contexts.items():
        if scope in contexts_by_scope:
            contexts_by_scope[scope] += 1
    
    return HealthResponse(
        status="ok",
        uptime_seconds=uptime,
        contexts_loaded=contexts_by_scope
    )

@app.get("/v1/debug")
def debug():
    import os
    import requests as req
    key = os.getenv("OPENROUTER_API_KEY", "NOT_FOUND")
    
    # Test API call directly
    try:
        r = req.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "anthropic/claude-sonnet-4-5",
                "messages": [{"role": "user", "content": "Say hi"}],
                "max_tokens": 10
            },
            timeout=10
        )
        api_status = r.status_code
        api_response = r.json()
    except Exception as e:
        api_status = "error"
        api_response = str(e)
    
    return {
        "key_prefix": key[:15],
        "api_status": api_status,
        "api_response": api_response
    }

# Endpoint 2: GET /v1/metadata
@app.get("/v1/metadata", response_model=MetadataResponse)
def metadata():
    """Return team metadata and system information."""
    return MetadataResponse(
        team_name="Magicpin Vera Challenge",
        team_members=["Team Member 1", "Team Member 2"],
        model="GPT-4",
        approach="Memory-based context and conversation management",
        contact_email="team@magicpin.com",
        version="1.0.0",
        submitted_at=datetime.now(timezone.utc).isoformat()
    )


# Endpoint 3: POST /v1/context
@app.post("/v1/context", response_model=ContextResponse)
def store_context(request: ContextRequest):
    """Store or update context with version control."""
    key = (request.scope, request.context_id)
    
    # Check if context with same or older version already exists
    if key in contexts:
        existing = contexts[key]
        if existing.get("version") >= request.version:
            return ContextResponse(
                accepted=False,
                reason="stale_version"
            )
    
    # Store the context
    ack_id = str(uuid.uuid4())
    stored_at = datetime.now(timezone.utc).isoformat()
    
    contexts[key] = {
        "version": request.version,
        "payload": request.payload,
        "delivered_at": request.delivered_at,
        "stored_at": stored_at,
        "ack_id": ack_id
    }
    
    return ContextResponse(
        accepted=True,
        ack_id=ack_id,
        stored_at=stored_at
    )


# Endpoint 4: POST /v1/tick
@app.post("/v1/tick", response_model=TickResponse)
def tick(request: TickRequest):
    """Process available triggers and generate actions."""
    actions = []
    
    for trigger_id in request.available_triggers:
        # Get trigger from contexts
        trigger_key = ("trigger", trigger_id)
        if trigger_key not in contexts:
            continue
        
        trigger_context = contexts[trigger_key]
        trigger_payload = trigger_context.get("payload", {})
        suppression_key = trigger_payload.get("suppression_key")
        
        # Check if suppression key already sent
        if suppression_key and suppression_key in sent_suppression:
            continue
        
        # Get merchant_id from trigger
        merchant_id = trigger_payload.get("merchant_id")
        if not merchant_id:
            continue
        
        # Get merchant from contexts
        merchant_key = ("merchant", merchant_id)
        if merchant_key not in contexts:
            continue
        
        merchant_context = contexts[merchant_key]
        merchant_payload = merchant_context.get("payload", {})
        
        # Get category from contexts using merchant category_slug
        category_slug = merchant_payload.get("category_slug")
        if not category_slug:
            continue
        
        category_key = ("category", category_slug)
        if category_key not in contexts:
            continue
        
        category_context = contexts[category_key]
        category_payload = category_context.get("payload", {})
        
        # Get customer_id from trigger
        customer_id = trigger_payload.get("customer_id")
        
        # Get customer payload if customer_id exists
        customer_payload = None
        if customer_id:
            customer_key = ("customer", customer_id)
            if customer_key in contexts:
                customer_payload = contexts[customer_key].get("payload", {})
        
        # Get or create conversation
        conversation_id = str(uuid.uuid4())
        conversations[conversation_id] = {
            "merchant_id": merchant_id,
            "customer_id": customer_id,
            "trigger_id": trigger_id,  # Store trigger_id for later use
            "turns": [],
            "status": "active"
        }
        
        # Call compose_message
        try:
            message_result = compose_message(
                category=category_payload,
                merchant=merchant_payload,
                trigger=trigger_payload,
                customer=customer_payload
            )
            
            if message_result:
                body = message_result.get("body", "")
                cta = message_result.get("cta", "")
                rationale = message_result.get("rationale", "")
                
                # Add suppression key to sent_suppression
                if suppression_key:
                    sent_suppression.add(suppression_key)
                
                # Create action
                action = TickAction(
                    conversation_id=conversation_id,
                    merchant_id=merchant_id,
                    body=body,
                    cta=cta,
                    rationale=rationale
                )
                actions.append(action)
        except Exception as e:
            # Log error and continue with next trigger
            continue
    
    return TickResponse(actions=actions)


# Endpoint 5: POST /v1/reply
@app.post("/v1/reply", response_model=ReplyAction)
def reply(request: ReplyRequest):
    """Handle customer reply in a conversation."""
    conversation_id = request.conversation_id
    
    # Extract from_role and message early
    from_role = request.from_role or "merchant"
    message = request.message or request.body or ""
    
    # Get conversation or create temporary one for unknown conversations
    if conversation_id not in conversations:
        # Create temporary conversation for this message
        conversations[conversation_id] = {
            "merchant_id": request.merchant_id or "",
            "customer_id": request.customer_id or "",
            "trigger_id": None,
            "turns": [],
            "status": "active"
        }
    
    conversation = conversations[conversation_id]
    
    # Handle customer responses with keyword matching
    if from_role == "customer":
        if any(word in message.lower() for word in ["yes", "book", "confirm", "please", "ok", "sure"]):
            return ReplyAction(
                action="send",
                body="Confirmed! Your appointment is booked. See you then!",
                cta="none",
                rationale="Customer confirmed booking"
            )
        else:
            return ReplyAction(
                action="send",
                body="Thanks! Is there anything else you need help with?",
                cta="none",
                rationale="Customer reply acknowledged"
            )
    
    # Add message to turns
    turn = {
        "from": from_role,
        "body": message,
        "received_at": request.received_at,
        "turn_number": request.turn_number
    }
    conversation["turns"].append(turn)
    
    # Get context data
    category = None
    merchant = None
    trigger = None
    customer = None
    
    # Get merchant context
    merchant_key = ("merchant", request.merchant_id)
    if merchant_key in contexts:
        merchant = contexts[merchant_key].get("payload", {})
        
        # Get category context using merchant category_slug
        category_slug = merchant.get("category_slug")
        if category_slug:
            category_key = ("category", category_slug)
            if category_key in contexts:
                category = contexts[category_key].get("payload", {})
    
    # Get customer context
    customer_key = ("customer", request.customer_id)
    if customer_key in contexts:
        customer = contexts[customer_key].get("payload", {})
    
    # Get trigger context (if available in conversation)
    trigger_id = conversation.get("trigger_id")
    if trigger_id:
        trigger_key = ("trigger", trigger_id)
        if trigger_key in contexts:
            trigger = contexts[trigger_key].get("payload", {})
    
    # Call handle_reply_turn function with new signature
    try:
        # Get merchant ID - from request or from conversation
        merchant_id = request.merchant_id or conversation.get("merchant_id", "")
        current_auto_reply_count = merchant_auto_reply_count.get(merchant_id, 0)
        
        reply_result = handle_reply_turn(
            turns=conversation["turns"],
            category=category or {},
            merchant=merchant or {},
            trigger=trigger or {},
            customer=customer,
            auto_reply_count=current_auto_reply_count
        )
        
        action = reply_result.get("action", "wait")
        body = reply_result.get("body")
        cta = reply_result.get("cta")
        rationale = reply_result.get("rationale", "")
        
        # Check if merchant's message is an auto-reply and update merchant-level counter
        last_message = ""
        if conversation["turns"]:
            last_message = conversation["turns"][-1].get("body", "")
        
        if check_auto_reply(last_message):
            merchant_auto_reply_count[merchant_id] = merchant_auto_reply_count.get(merchant_id, 0) + 1
        else:
            merchant_auto_reply_count[merchant_id] = 0
        
        # Update conversation status if action is 'end'
        if action == "end":
            conversation["status"] = "ended"
        
        return ReplyAction(
            action=action,
            body=body,
            cta=cta,
            rationale=rationale
        )
    except Exception as e:
        # Return default wait action on error
        return ReplyAction(
            action="wait",
            rationale=f"Error processing reply: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
