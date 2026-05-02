# Vera - Magicpin WhatsApp Merchant Assistant

**Vera** is an AI-powered WhatsApp merchant assistant built for magicpin. It helps merchants engage with customers through intelligent, contextual messaging powered by LLM technology.

---

## 📋 Project Overview

Vera is a **FastAPI-based bot** that:
- Stores merchant, customer, category, and trigger contexts
- Generates contextual WhatsApp messages using OpenRouter LLM API
- Detects auto-replies, stop signals, and customer intent
- Tracks conversation state with merchant-level auto-reply limits
- Returns actions: `send`, `wait`, or `end`

**Technology Stack:**
- Python 3.10+
- FastAPI + Uvicorn (Web Framework)
- Pydantic (Type Validation)
- OpenRouter API (LLM Provider: Claude, GPT-4o, DeepSeek)
- In-Memory Storage (Dicts for contexts & conversations)

---

## 🚀 Quick Start

### Prerequisites
```bash
python --version  # Python 3.10 or higher
pip install -r requirements.txt
```

### Installation
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up environment variables
# Create/update .env file with:
OPENROUTER_API_KEY=sk-or-v1-[your-key]
```

### Running the Bot

**Terminal 1: Start the Bot Server**
```bash
python bot.py
# Output: Uvicorn running on http://0.0.0.0:8000
```

**Terminal 2: Run Judge Simulator (Testing)**
```bash
python judge_simulator.py
# Select: 1 for all tests
# Output: [PASS] warmup, auto_reply, intent, hostile
```

---

## 📁 Project Structure

```
.
├── bot.py                      # FastAPI server (5 endpoints)
├── composer.py                 # LLM logic & detection functions
├── judge_simulator.py          # Official test harness
├── requirements.txt            # Python dependencies
├── .env                        # API configuration
│
├── dataset/
│   ├── merchants_seed.json     # 10 merchant templates
│   ├── customers_seed.json     # 15 customer templates
│   ├── triggers_seed.json      # 25 trigger templates
│   └── categories/
│       ├── dentists.json
│       ├── gyms.json
│       ├── pharmacies.json
│       ├── restaurants.json
│       └── salons.json
│
├── test_functionality.py       # Comprehensive module tests
├── test_detection.py           # Auto-reply, stop-signal, intent tests
├── test_merchant_tracking.py   # Merchant-level tracking test
├── test_fixes.py               # Critical fix validation
└── validate_project.py         # Project structure validation
```

---

## 🔌 API Endpoints

### 1. **GET /v1/healthz** - Health Check
```bash
curl http://localhost:8000/v1/healthz
```
**Response:**
```json
{
  "status": "healthy",
  "uptime_seconds": 120,
  "contexts_count": 50,
  "conversations_count": 10
}
```

### 2. **GET /v1/metadata** - Bot Info
```bash
curl http://localhost:8000/v1/metadata
```
**Response:**
```json
{
  "team": "Magicpin Vera Challenge",
  "model": "GPT-4",
  "approach": "LLM-based contextual messaging"
}
```

### 3. **POST /v1/context** - Store Context
```bash
curl -X POST http://localhost:8000/v1/context \
  -H "Content-Type: application/json" \
  -d '{
    "scope": "merchant",
    "context_id": "m_001",
    "version": 1,
    "payload": {"name": "Dr. Meera's Clinic", "category_slug": "dentists"}
  }'
```

### 4. **POST /v1/tick** - Get Trigger Actions
```bash
curl -X POST http://localhost:8000/v1/tick \
  -H "Content-Type: application/json" \
  -d '{
    "now": "2024-01-01T12:00:00Z",
    "available_triggers": ["trg_001", "trg_002"]
  }'
```
**Response:**
```json
{
  "actions": [
    {
      "conversation_id": "conv_123",
      "merchant_id": "m_001",
      "body": "Meera, your CTR is 2.1% — peer median is 3.0%",
      "cta": "open_ended"
    }
  ]
}
```

### 5. **POST /v1/reply** - Handle Customer Reply
```bash
curl -X POST http://localhost:8000/v1/reply \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "conv_123",
    "merchant_id": "m_001",
    "customer_id": "c_001",
    "from_role": "merchant",
    "message": "Stop messaging me!",
    "turn_number": 4,
    "received_at": "2024-01-01T12:05:00Z"
  }'
```
**Response:**
```json
{
  "action": "end",
  "body": null,
  "cta": null,
  "rationale": "Merchant requested to stop"
}
```

---

## 🎯 Key Features

### ✅ Auto-Reply Detection
Detects when a merchant sends an automated response (e.g., "Thank you for contacting us. We will get back to you soon.") and tracks them at the **merchant level** across different conversations.

**Behavior:**
- Turn 1-3: Bot sends follow-up ("send")
- Turn 4+: Bot stops trying ("end")

### ✅ Hostile Message Detection
Detects stop signals (e.g., "Stop messaging me. This is useless spam.") and immediately ends the conversation.

**Patterns Detected:**
- "stop messaging", "spam", "useless", "don't message me"
- Hindi: "mat bhejo", "messaging band karo", "yeh spam hai"

### ✅ Intent Transition
When merchant accepts an offer/request ("Ok let's do it"), bot moves to action mode with contextual follow-ups based on trigger type:
- **Offer**: "Perfect! I'll process your request right away. When would you like to start?"
- **Research**: "Excellent! I'll prepare the details and send them to you shortly."
- **Recall/Update**: "Great! Let me finalize the details for you. What day works best?"

### ✅ Robust JSON Parsing
Handles LLM responses wrapped in markdown backticks:
```json
```json
{"body": "message", "cta": "yes_stop"}
```
```

### ✅ Merchant-Level State Tracking
Global `merchant_auto_reply_count` dictionary tracks auto-replies per merchant across multiple conversations, preventing spam.

---

## 🧪 Testing

### Run All Tests
```bash
# Validate project structure
python validate_project.py

# Comprehensive functionality tests
python test_functionality.py

# Test detection functions
python test_detection.py

# Test merchant-level tracking
python test_merchant_tracking.py

# Test critical fixes
python test_fixes.py

# Official judge simulator
python judge_simulator.py
```

### Expected Results
```
✓ All modules import successfully
✓ 10 merchants, 15 customers, 25 triggers loaded
✓ All detection functions working
✓ Merchant-level auto-reply tracking correct
✓ Turn 4 ends automatically (auto-reply limit)
✓ Hostile messages end immediately
✓ Intent transitions work with context
✓ Judge simulator: [PASS] warmup, auto_reply, intent, hostile
```

---

## 🔍 Detection Functions

### `is_auto_reply(message: str) -> bool`
Detects automated responses from merchants.

**Examples:**
- ✓ "Thank you for contacting us. We will get back to you soon."
- ✓ "This is an automated message."
- ✓ "Shukriya. Aap se jald contact karenge." (Hindi)
- ✗ "Sure, let's discuss this offer!"

### `is_stop_signal(message: str) -> bool`
Detects stop/spam signals from merchants.

**Examples:**
- ✓ "Stop messaging me!"
- ✓ "This is spam."
- ✓ "Don't message me again."
- ✓ "Useless."
- ✗ "I'm not interested right now."

### `is_accept_intent(message: str) -> bool`
Detects acceptance/interest from merchants.

**Examples:**
- ✓ "Yes, let's do it!"
- ✓ "Sure, book it."
- ✓ "Haan, chalo." (Hindi)
- ✗ "Maybe later."

---

## 📊 Message Generation

Vera generates messages following strict guidelines:

**Rules:**
1. NO emojis, bullet points, or asterisks
2. Start with merchant owner_first_name directly
3. Hindi-English mix when appropriate
4. Use EXACT numbers from context only
5. Max 3 sentences, no generic greetings
6. Peer tone, not promotional
7. Trigger-specific content (research_digest, perf_dip, recall_due)
8. Single CTA at end

**Example:**
```
Meera, your CTR is 2.1% — peer median is 3.0% se neeche.
Let's boost this with targeted offers.
Reply YES / STOP
```

---

## 🐛 Known Issues & Fixes

### Fix #1: Merchant-Level Auto-Reply Tracking ✅
**Problem:** Bot was tracking auto-replies per conversation, allowing 4 attempts per unique conversation ID.

**Solution:** Changed to global `merchant_auto_reply_count` dictionary. Now tracks per merchant across all conversations.

### Fix #2: Pydantic Model Validation ✅
**Problem:** `ReplyAction` model rejected `None` values for `body` and `cta` on action="end".

**Solution:** Changed to `Optional[str] = None` in Pydantic model.

### Fix #3: JSON Parsing Robustness ✅
**Problem:** LLM sometimes returns JSON wrapped in markdown backticks.

**Solution:** Enhanced parsing to extract JSON from markdown code blocks and handle dict CTA values.

---

## 🔧 Configuration

### Environment Variables
```bash
# .env file
OPENROUTER_API_KEY=sk-or-v1-[your-api-key]
```

### LLM Provider
Default: **OpenRouter (gpt-4o-mini)**

Supports:
- Claude models
- GPT-4o, GPT-4o-mini
- DeepSeek
- Groq
- Ollama (local)

### Model Settings
- Temperature: 0 (deterministic responses)
- Max tokens: 500 (message length limit)

---

## 📝 License & Credits

**Built for:** Magicpin AI Challenge
**Framework:** FastAPI
**LLM Provider:** OpenRouter
**Date:** May 2026

---

## 🤝 Support

For issues or questions:
1. Check test output: `python test_functionality.py`
2. Validate project: `python validate_project.py`
3. Run judge simulator: `python judge_simulator.py`
4. Review logs in bot server terminal

---

## ✨ Features Summary

| Feature | Status | Details |
|---------|--------|---------|
| FastAPI Server | ✅ | 5 endpoints, automatic docs |
| LLM Integration | ✅ | OpenRouter with fallback handling |
| Auto-Reply Detection | ✅ | 8 pattern recognition rules |
| Stop Signal Detection | ✅ | 14 pattern recognition rules |
| Intent Recognition | ✅ | 12 pattern recognition rules |
| Merchant Tracking | ✅ | Global state, cross-conversation |
| Message Generation | ✅ | Contextual, trigger-aware, peer-tone |
| JSON Parsing | ✅ | Markdown-robust, dict handling |
| State Management | ✅ | In-memory conversations & contexts |
| Error Handling | ✅ | Graceful fallbacks, safe defaults |
| Testing Suite | ✅ | Comprehensive validation tests |
| Judge Compatible | ✅ | All scenarios passing |

---

**Ready to use!** 🚀 Start the server and begin sending messages to merchants.
