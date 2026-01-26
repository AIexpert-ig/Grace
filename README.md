## System Architecture

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'fontSize': '20px', 'fontFamily': 'trebuchet ms'}}}%%
graph LR
    User((Guest)) -- Telegram --> API[FastAPI Gateway]
    API -- Query --> DB[(PostgreSQL)]
    DB -- Rates/Info --> API
    API -- Context + Data --> LLM[OpenRouter / Gemini 2.0]
    LLM -- Elegant Persona --> API
    API -- Final Response --> User
    
    System[External Voice AI] -- HMAC Signed Webhook --> API
    API -- Urgent Alert --> Staff((Hotel Staff))
    
    style API fill:#f9f,stroke:#333,stroke-width:3px
    style LLM fill:#bbf,stroke:#333,stroke-width:3px
    style DB fill:#dfd,stroke:#333,stroke-width:3px
    style Staff fill:#ffd,stroke:#333,stroke-width:2px