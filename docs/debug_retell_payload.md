# Retell Custom LLM Payload (Observed)

**Handler:** `WebSocket /llm-websocket/{call_id}` in `app/main.py`.

**Expected fields (observed):**
- `interaction_type`: string (expects `"response_required"`)
- `transcript`: list of turns, last item includes `content`
- `response_id`: string
- `call_id`: provided via websocket path

**Minimal example**
```json
{
  "interaction_type": "response_required",
  "response_id": "abc",
  "transcript": [
    {"role": "user", "content": "Hello?"}
  ]
}
```

**Notes**
- Latest user text is extracted from `transcript[-1].content` or `user_text` if provided.
- Guardrails prevent empty/duplicate responses and ask a clarifying question when input is unclear.
