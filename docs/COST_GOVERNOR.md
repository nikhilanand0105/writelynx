# Writelynx — AI Cost Governor & Budget Circuit Breaker

## 1. FinOps Objectives & Ceilings

To prevent runaway cloud API expenses from eroding margins or exposing the platform to denial-of-wallet attacks, Writelynx enforces strict, hard per-document AI spend ceilings in integer paise:

| Plan Tier | Student Price | Hard AI Budget Ceiling | Maximum Budget in Paise | Target Gross Margin |
| :--- | :--- | :--- | :--- | :--- |
| **Basic** | ₹20 | **₹4.00** | **400 paise** | **80.0%** |
| **Standard** | ₹50 | **₹9.00** | **900 paise** | **82.0%** |
| **Extended** | ₹100 | **₹24.00** | **2,400 paise** | **76.0%** |

---

## 2. Token Accounting & Real-Time Cost Tracking

Every API invocation dispatched through the writing assistant pipeline records prompt and completion tokens in the `ai_cost_reservations` ledger.

$$\text{Cost}_{\text{Paise}} = \left\lceil \left(\frac{\text{Tokens}_{\text{prompt}}}{1000} \times \text{Rate}_{\text{prompt}}\right) + \left(\frac{\text{Tokens}_{\text{comp}}}{1000} \times \text{Rate}_{\text{comp}}\right) \right\rceil$$

Estimated rates per 1,000 tokens (Gemini 1.5 Flash):
- Prompt tokens: ~1 paisa / 1k tokens
- Completion tokens: ~3 paise / 1k tokens
- Local Ollama & deterministic heuristics: 0 paise (Zero cost)

---

## 3. Circuit Breaker Mechanism

```mermaid
flowchart TD
    Req[LLM Invocation Request] --> CheckGlobal{Global AI_API_PAUSED Active?}
    CheckGlobal -- Yes --> UseLocal[Force No-LLM / Local Deterministic Rule Engine]
    CheckGlobal -- No --> CalcSpend[Query Total Spend for Document in ai_cost_reservations]
    
    CalcSpend --> CeilCheck{Total Spend >= Tier Budget Ceiling?}
    CeilCheck -- Yes --> CutOff[Hard Cutoff: Halt External API, Complete Job via Heuristics]
    
    CeilCheck -- No --> WarnCheck{Total Spend >= 85% of Budget?}
    WarnCheck -- Yes --> Downgrade[Downgrade to Local Zero-Cost Model e.g. Ollama]
    WarnCheck -- No --> Execute[Execute Gemini 1.5 Flash / Standard Model]
    
    Execute --> Record[Record AICostReservation in Integer Paise]
```

---

## 4. Emergency Kill Switches

Runtime platform controls can be instantly toggled by administrators via `POST /api/admin/kill-switch` without restarting backend processes:

1. `PURCHASES_PAUSED`: Stops the creation of new Razorpay orders (HTTP 503).
2. `UPLOADS_PAUSED`: Stops the issuance of new upload tokens (HTTP 503).
3. `PROCESSING_PAUSED`: Halts the execution of new document analysis jobs (HTTP 503).
4. `AI_API_PAUSED`: Immediately redirects all writing assistant queries to zero-cost local heuristics, bypassing external cloud billing entirely.
