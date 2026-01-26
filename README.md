%%{init: {
  'theme': 'base',
  'flowchart': { 'curve': 'basis', 'padding': 12, 'nodeSpacing': 55, 'rankSpacing': 70 },
  'themeVariables': {
    'fontFamily': 'Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial',
    'fontSize': '18px',
    'lineColor': '#2B2F3A',
    'textColor': '#121826',
    'primaryColor': '#F7F8FC',
    'primaryTextColor': '#121826',
    'primaryBorderColor': '#2B2F3A',
    'tertiaryColor': '#FFFFFF'
  }
}}%%

flowchart LR

  %% ----------------------------
  %% LAYERS
  %% ----------------------------
  subgraph CX["Guest Experience Layer"]
    direction LR
    U((Guest))
  end

  subgraph EDGE["Channel + Gateway"]
    direction LR
    TG["Telegram"]
    API["FastAPI Gateway<br/><span style='font-size:13px;opacity:.85'>Routing • Auth • Context Builder</span>"]
  end

  subgraph DATA["Data Layer"]
    direction LR
    DB[(PostgreSQL)]
  end

  subgraph AI["AI Orchestration"]
    direction LR
    LLM["OpenRouter / Gemini 2.0<br/><span style='font-size:13px;opacity:.85'>Reasoning • Tone • Responseúss</span>"]
  end

  subgraph OPS["Operations & Escalations"]
    direction LR
    SYS["External Voice AI"]
    STAFF((Hotel Staff))
  end

  %% ----------------------------
  %% FLOWS (Primary)
  %% ----------------------------
  U -- "Message" --> TG
  TG -- "Inbound API Call" --> API
  API -- "Query" --> DB
  DB -- "Rates / Info" --> API
  API -- "Context + Data" --> LLM
  LLM -- "Persona + Draft" --> API
  API -- "Final Response" --> TG
  TG -- "Delivered" --> U

  %% ----------------------------
  %% FLOWS (Ops)
  %% ----------------------------
  SYS -- "HMAC-signed webhook" --> API
  API -- "Urgent alert" --> STAFF

  %% ----------------------------
  %% STYLES
  %% ----------------------------
  classDef guest fill:#0B1220,stroke:#0B1220,color:#FFFFFF,stroke-width:3px;
  classDef channel fill:#FFFFFF,stroke:#CBD5E1,color:#0F172A,stroke-width:2px;
  classDef gateway fill:#EEF2FF,stroke:#4F46E5,color:#111827,stroke-width:3px;
  classDef data fill:#ECFDF5,stroke:#10B981,color:#064E3B,stroke-width:3px;
  classDef ai fill:#EFF6FF,stroke:#2563EB,color:#0B1B3A,stroke-width:3px;
  classDef ops fill:#FFF7ED,stroke:#F97316,color:#7C2D12,stroke-width:3px;
  classDef staff fill:#FFFBEB,stroke:#F59E0B,color:#78350F,stroke-width:3px;

  class U guest;
  class TG channel;
  class API gateway;
  class DB data;
  class LLM ai;
  class SYS ops;
  class STAFF staff;

  %% Subgraph styling (soft cards)
  style CX fill:#F8FAFC,stroke:#E2E8F0,stroke-width:2px,rx:16,ry:16;
  style EDGE fill:#F8FAFC,stroke:#E2E8F0,stroke-width:2px,rx:16,ry:16;
  style DATA fill:#F8FAFC,stroke:#E2E8F0,stroke-width:2px,rx:16,ry:16;
  style AI fill:#F8FAFC,stroke:#E2E8F0,stroke-width:2px,rx:16,ry:16;
  style OPS fill:#F8FAFC,stroke:#E2E8F0,stroke-width:2px,rx:16,ry:16;

  %% Emphasis on primary path
  linkStyle 0,1,2,3,4,5,6,7,8 stroke:#111827,stroke-width:3px;
  %% Ops path
  linkStyle 9,10 stroke:#F97316,stroke-width:3px,stroke-dasharray:6 4;
