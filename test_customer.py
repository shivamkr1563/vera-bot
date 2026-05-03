import requests

BOT_URL = "http://localhost:8080"

resp = requests.post(f"{BOT_URL}/v1/reply", json={
    "conversation_id": "test_conv_123",
    "merchant_id": "m_001",
    "customer_id": "c_001",
    "from_role": "customer",
    "message": "Yes please book me for Wed 5 Nov 6pm",
    "received_at": "2026-05-03T10:00:00Z",
    "turn_number": 1
})
print("Customer reply:", resp.json())