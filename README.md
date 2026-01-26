%%{init: {
  'theme': 'base',
  'flowchart': { 'curve': 'basis', 'padding': 25, 'nodeSpacing': 65, 'rankSpacing': 90, 'useMaxWidth': false },
  'themeVariables': {
    'fontFamily': 'Inter, system-ui, sans-serif',
    'fontSize': '19px',
    'lineColor': '#475569',
    'textColor': '#1e293b',
    'primaryColor': '#f8fafc',
    'primaryTextColor': '#0f172a',
    'primaryBorderColor': '#94a3b8',
    'tertiaryColor': '#ffffff'
  }
}}%%

flowchart LR

  %% ----------------------------
  %% LAYERS
  %% ----------------------------
  subgraph CX["GUEST INTERFACE"]
    direction LR
    U(((Guest)))
  end

  subgraph EDGE["ORCHESTRATION GATEWAY"]
    direction LR
    TG[Telegram Bot]
    API[["FastAPI Core<br/><span style='font-size:14px;opacity:.8'>Auth • Logic • Routing</span>"]]
  end

  subgraph BRAIN["NEURAL ENGINE"]
    direction LR
    LLM["OpenRouter / Gemini 2.0<br/><span style='font-size:14px;opacity:.8'>Reasoning & Persona</span>"]
    MEM[(Guest History<br/>Redis Cache)]
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

  %% ----------------------------
  %% THE "SMART" FLOW
  %% ----------------------------
  U -- "Inquiry" --> TG
  TG -- "Secure Request" --> API
  
  %% Parallel Smart Check
  API -- "Verify Identity" --> SHIELD
  API -- "Fetch Context" --> MEM
  API -- "Check Inventory" --> DB
  
  %% Synthesis
  API -- "Enriched Context" --> LLM
  LLM -- "Polished Response" --> API
  
  API -- "Personalized Reply" --> TG
  TG -- "Delivered" --> U

  %% Escalation Path
  SHIELD -- "Valid Alert" --> API
  API -- "Staff Dispatch" --> STAFF

  %% ----------------------------
  %% STYLING (The "Luxury" Look)
  %% ----------------------------
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
  style EDGE fill:#f8fafc,stroke:#e2e8f0,rx:20,ry:20;
  style BRAIN fill:#f8fafc,stroke:#e2e8f0,rx:20,ry:20;
  style DATA fill:#f8fafc,stroke:#e2e8f0,rx:20,ry:20;
  style OPS fill:#f8fafc,stroke:#e2e8f0,rx:20,ry:20;

  linkStyle default stroke:#64748b,stroke-width:2px;
  linkStyle 9,10 stroke:#f97316,stroke-width:3px,stroke-dasharray: 8 5;