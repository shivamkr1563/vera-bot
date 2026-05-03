import os
import json
import re
from typing import Dict, List, Any, Optional
import requests
from dotenv import load_dotenv

# Load .env file
load_dotenv()
# Load OpenRouter API key from environment
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def is_auto_reply(message: str) -> bool:
    """
    Check if message matches auto-reply patterns.
    Returns True if message contains any of the predefined auto-reply patterns.
    """
    if not message:
        return False
    
    patterns = [
        "thank you for contacting",
        "i'll get back to you",
        "automated message",
        "automated assistant",
        "aapki jaankari ke liye shukriya",
        "bahut bahut shukriya",
        "main ek automated",
        "team tak pahuncha"
    ]
    
    message_lower = str(message).lower()
    for pattern in patterns:
        if pattern in message_lower:
            return True
    
    return False


def is_stop_signal(message: str) -> bool:
    """
    Check if message contains stop/unsubscribe signals.
    Returns True if message indicates user wants to stop communications.
    """
    if not message:
        return False
    
    patterns = [
        "stop",
        "spam",
        "useless",
        "dont message",
        "not interested",
        "band karo",
        "nahi chahiye",
        "mat bhejo",
        "block",
        "stop messaging",
        "this is spam",
        "useless spam",
        "don't message",
        "dont message me"
    ]
    
    message_lower = str(message).lower()
    for pattern in patterns:
        if pattern in message_lower:
            return True
    
    return False


def is_accept_intent(message: str) -> bool:
    """
    Check if message contains acceptance/interest signals.
    Returns True if message indicates user wants to proceed/accept.
    """
    if not message:
        return False
    
    patterns = [
        "ok",
        "yes",
        "haan",
        "chalo",
        "let's do it",
        "lets do it",
        "go ahead",
        "sure",
        "start",
        "send me",
        "bhejo",
        "karo"
    ]
    
    message_lower = str(message).lower()
    for pattern in patterns:
        if pattern in message_lower:
            return True
    
    return False


def call_openai(system: str, user: str) -> str:
    """
    Call OpenRouter API to generate response.
    Uses Claude Sonnet 4.5 model via OpenRouter with specified parameters.
    Returns the text response.
    """
    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://magicpin.com",
            "X-Title": "Vera Bot"
        }
        
        payload = {
            "model": "anthropic/claude-sonnet-4-5",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            "max_tokens": 800,
            "temperature": 0
        }
        
        response = requests.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code != 200:
            raise Exception(f"API error: {response.status_code} - {response.text}")
        
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        # Return a default response on API error
        return json.dumps({
            "body": "We'll get back to you shortly.",
            "cta": "Thank you for your patience",
            "send_as": "vera",
            "rationale": f"API error: {str(e)}",
            "template_name": "default_error"
        })


def compose_message(
    category: Dict[str, Any],
    merchant: Dict[str, Any],
    trigger: Dict[str, Any],
    customer: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Compose a message using context from category, merchant, trigger, and customer.
    Calls OpenAI API to generate the message content.
    Returns dict with: body, cta, send_as, rationale, template_name
    """
    # Build detailed system prompt for Vera
    system_prompt = """You are Vera, magicpin WhatsApp merchant assistant.
Compose ONE WhatsApp message using the context provided.

RULES (never break):
1. NO emojis. NO bullet points. NO asterisks.
2. Start with merchant owner_first_name directly. Example: "Meera,"
3. If languages include "hi" use Hindi-English mix naturally.
4. Use EXACT numbers from context only. NEVER invent.
5. Max 3 sentences. No greetings like Hope you are well.
6. Peer tone. Not promotional.
7. Single CTA at end: "Reply YES / STOP" or open question.
8. cta field must be STRING: "yes_stop" or "open_ended" or "none"
9. For research_digest: cite exact journal, page number, stat, sample size.
10. For perf_dip: mention exact dropped metric vs peer median.
11. For regulation_change: mention exact regulation authority name, old value/limit, new value/limit, effective deadline date, and exactly what the merchant must do to comply. Example: DCI ne IOPA dose limit 1.5 mSv se 1.0 mSv kar diya hai, effective Dec 15. E-speed film ya RVG sensors comply karte hain, D-speed nahi. Apna X-ray setup audit karo.
12. For recall_due: mention patient name, last visit, specific service.

OUTPUT: Raw JSON only. No markdown. No backticks.
{"body": "...", "cta": "yes_stop", "send_as": "vera", "rationale": "..."}"""
    
    # Build user prompt with full context as JSON
    user_prompt = "CATEGORY:\n"
    user_prompt += json.dumps(category if category else {}, indent=2) + "\n\n"
    
    user_prompt += "MERCHANT:\n"
    user_prompt += json.dumps(merchant if merchant else {}, indent=2) + "\n\n"
    
    user_prompt += "TRIGGER:\n"
    user_prompt += json.dumps(trigger if trigger else {}, indent=2) + "\n\n"
    
    user_prompt += "CUSTOMER:\n"
    if customer:
        user_prompt += json.dumps(customer, indent=2) + "\n\n"
    else:
        user_prompt += "none\n\n"
    
    # Get trigger kind for task specification
    trigger_kind = trigger.get("kind", trigger.get("type", "general")) if trigger else "general"
    
    user_prompt += f"TASK: Compose the message for this trigger kind: {trigger_kind}"
    
    # Call OpenAI API
    response_text = call_openai(system_prompt, user_prompt)
    
    # Parse JSON response
    try:
        text = response_text.strip()
        if "```" in text:
            for part in text.split("```"):
                part = part.strip().lstrip("json").strip()
                if part.startswith("{"):
                    try:
                        message_data = json.loads(part)
                        break
                    except:
                        continue
        else:
            message_data = json.loads(text)
        
        # Fix cta if it's a dict instead of string
        if isinstance(message_data.get("cta"), dict):
            message_data["cta"] = "open_ended"
            
    except json.JSONDecodeError:
        message_data = {
            "body": "We'll get back to you shortly.",
            "cta": "none",
            "send_as": "vera",
            "rationale": "Failed to parse response",
            "template_name": "default_error"
        }
    
    # Ensure all required fields are present
    if "template_name" not in message_data:
        message_data["template_name"] = "vera_generated"
    
    return message_data


def handle_reply_turn(
    turns: List[Dict[str, Any]],
    category: Optional[Dict[str, Any]] = None,
    merchant: Optional[Dict[str, Any]] = None,
    trigger: Optional[Dict[str, Any]] = None,
    customer: Optional[Dict[str, Any]] = None,
    auto_reply_count: int = 0
) -> Dict[str, Any]:
    """
    Handle customer reply in a conversation.
    Analyzes the latest message in turns and determines the appropriate action.
    Logic order: auto-reply → stop signal → accept intent → follow-up
    Returns dict with: action (send/wait/end), body, cta, rationale
    """
    # Get the latest message from turns (merchant's reply)
    message = ""
    if turns:
        last_turn = turns[-1]
        message = last_turn.get("body") or last_turn.get("message") or ""
    message = str(message) if message else ""
    
    # 1. CHECK AUTO-REPLY FIRST
    if is_auto_reply(message):
        if auto_reply_count >= 1:
            # End conversation after 1 auto-reply detected
            return {
                "action": "end",
                "body": None,
                "cta": None,
                "rationale": f"Auto-reply limit reached ({auto_reply_count + 1} attempts). Ending conversation."
            }
        else:
            # Increment counter and send one more attempt
            return {
                "action": "send",
                "body": "We'd love to connect with you when you're available. Please let us know!",
                "cta": "Reply when ready",
                "rationale": f"Auto-reply detected, attempting follow-up (attempt {auto_reply_count + 1}/4)"
            }
    
    # 2. CHECK STOP SIGNAL SECOND
    if is_stop_signal(message):
        return {
            "action": "end",
            "body": None,
            "cta": None,
            "rationale": "Merchant requested to stop"
        }
    
    # 3. CHECK ACCEPT INTENT THIRD
    # Check both current message and raw turns data for acceptance signals
    if is_accept_intent(message):
        # Build a contextual follow-up based on trigger/offer details
        follow_up = "Let me set this up for you. What's the best time to proceed?"
        if trigger and trigger.get("kind"):
            trigger_kind = trigger.get("kind")
            if "offer" in trigger_kind.lower():
                follow_up = "Perfect! I'll process your request right away. When would you like to start?"
            elif "research" in trigger_kind.lower():
                follow_up = "Excellent! I'll prepare the details and send them to you shortly."
            elif "update" in trigger_kind.lower() or "recall" in trigger_kind.lower():
                follow_up = "Great! Let me finalize the details for you. What day works best?"
        
        return {
            "action": "send",
            "body": follow_up,
            "cta": "confirm_action",
            "rationale": "Merchant accepted - moving to actionable next step based on trigger context"
        }
    
    # 4. OTHERWISE: SEND FOLLOW-UP MESSAGE
    try:
        system_prompt = """You are an AI assistant helping merchants engage with customers.
Generate a thoughtful follow-up message based on the customer's message.
Keep it conversational and helpful.

Always respond with valid JSON containing: body, cta, rationale"""
        
        # Safely extract merchant name with fallbacks
        merchant_name = ""
        if merchant and isinstance(merchant, dict):
            merchant_name = merchant.get("name", "") or merchant.get("identity", {}).get("name", "") or ""
        if not merchant_name:
            merchant_name = "N/A"
        
        user_prompt = f"""Customer responded with: "{message}"
Merchant: {merchant_name}
Generate a follow-up response.

Return ONLY valid JSON:
{{
    "body": "Follow-up message",
    "cta": "CTA text",
    "rationale": "Reason for this message"
}}"""
        
        response_text = call_openai(system_prompt, user_prompt)
        
        # Parse response with safe defaults
        try:
            # Remove markdown code blocks if present
            text = response_text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            reply_data = json.loads(text)
            body = reply_data.get("body") or "Thank you for your response!"
            cta = reply_data.get("cta") or "open_ended"
            rationale = reply_data.get("rationale") or "Follow-up message"
        except (json.JSONDecodeError, TypeError):
            body = "Thank you for your response!"
            cta = "open_ended"
            rationale = "Follow-up message"
        
        return {
            "action": "send",
            "body": body,
            "cta": cta,
            "rationale": rationale
        }
    
    except Exception as e:
        # Catch-all for any unexpected errors
        print(f"ERROR in handle_reply_turn: {str(e)}")
        return {
            "action": "send",
            "body": "Thank you for your response!",
            "cta": "open_ended",
            "rationale": f"Error handling reply: {str(e)}"
        }
