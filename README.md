```mermaid
%%{init: {
  'theme': 'base',
  'flowchart': { 'curve': 'basis', 'padding': 20, 'nodeSpacing': 50, 'rankSpacing': 80, 'useMaxWidth': false },
  'themeVariables': {
    'fontFamily': 'Inter, system-ui, sans-serif',
    'fontSize': '18px',
    'lineColor': '#334155',
    'textColor': '#1e293b',
    'primaryColor': '#f8fafc',
    'primaryTextColor': '#0f172a',
    'primaryBorderColor': '#94a3b8'
  }
}}%%

flowchart LR

  subgraph CX["GUEST INTERFACE"]
    direction LR
    U(((Guest)))
  end

  subgraph GATEWAY["INTELLIGENT GATEWAY"]
    direction LR
    TG[Telegram Bot]
    API[["FastAPI Core<br/><span style='font-size:13px;opacity:.8'>Logic • Auth • Routing</span>"]]
  end

  subgraph BRAIN["NEURAL ORCHESTRATOR"]
    direction LR
    LLM["OpenRouter / Gemini 2.0<br/><span style='font-size:13px;opacity:.8'>Reasoning & Persona</span>"]
    MEM[(Guest Context<br/>Redis Cache)]
  end

  subgraph DATA["KNOWLEDGE BASE"]
    direction LR
    DB[(PostgreSQL<br/>Rates & Inventory)]
  end

  subgraph OPS["SECURITY & STAFF"]
    direction LR
    SHIELD{{HMAC Validator}}
    STAFF((Hotel Staff))
  end

  U -- "Inquiry" --> TG
  TG -- "Secure Request" --> API
  
  API -. "Verify" .-> SHIELD
  API -. "Fetch context" .-> MEM
  API -- "Query rates" --> DB
  
  API -- "Enriched Payload" --> LLM
  LLM -- "Polished Response" --> API
  
  API -- "Personalized Reply" --> TG
  TG -- "Delivered" --> U
  SHIELD -- "Urgent Alert" --> STAFF

  classDef guest fill:#0f172a,stroke:#0f172a,color:#fff,stroke-width:4px;
  classDef core fill:#eef2ff,stroke:#6366f1,color:#1e1b4b,stroke-width:4px;
  classDef brain fill:#f0f9ff,stroke:#0ea5e9,color:#0c4a6e,stroke-width:4px;
  classDef knowledge fill:#f0fdf4,stroke:#22c55e,color:#052e16,stroke-width:3px;
  classDef security fill:#fff7ed,stroke:#f97316,color:#7c2d12,stroke-width:3px;

  class U guest;
  class API,TG core;
  class LLM,MEM brain;
  class DB knowledge;
  class SHIELD,STAFF security;

  style CX fill:#f8fafc,stroke:#e2e8f0,rx:20,ry:20;
  style GATEWAY fill:#f8fafc,stroke:#e2e8f0,rx:20,ry:20;
  style BRAIN fill:#f8fafc,stroke:#e2e8f0,rx:20,ry:20;
  style DATA fill:#f8fafc,stroke:#e2e8f0,rx:20,ry:20;
  style OPS fill:#f8fafc,stroke:#e2e8f0,rx:20,ry:20;
```
## Retell Custom LLM

**Handler:** `WebSocket /llm-websocket/{call_id}` in `app/main.py`

**Where prompts live**
- `SYSTEM_PROMPT` constant in `app/main.py`
- Guardrails enforced in the websocket handler before calling the model

**Guardrails**
- If user message is empty/unclear, respond with a clarifying question
- Prevent repeating the last assistant message
- Dedupe repeated user utterances within 10 seconds

**Debug marker (temporary)**
- To verify Retell is using our Custom LLM, set `RETELL_DEBUG_MARKER=1` in Railway env vars and redeploy.
- When enabled, every response will be prefixed with `GRACE_WS_OK: `.
- Disable after verification by unsetting `RETELL_DEBUG_MARKER` or setting it to `0`.
