# Writelynx — Pricing Strategy, Unit Economics & Margin Model

## 1. Value Proposition & Competitive Positioning

Conventional academic editing services charge either steep recurring subscriptions ($15–$30/month) or force auto-renewals on students who only need document assistance during milestone submission weeks (CAT, FAT, and Capstones). Furthermore, commercial humanizers frequently corrupt complex table dimensions, IEEE citation links, and formulas.

Writelynx offers **pay-per-document microtransactions** exclusively engineered for university students:
- Single-use, zero recurring subscriptions, zero forced auto-renewals.
- Guaranteed document formatting, references, and numeric invariant protection.
- Upgrades charge only the exact mathematical difference in paise without penalty.

---

## 2. Unit Economics per Processed Document

| Metric | Basic Plan (Max 4 Pgs / 15k Chars) | Standard Plan (Max 20 Pgs / 65k Chars) | Extended Plan (Max 50 Pgs / 160k Chars) |
| :--- | :--- | :--- | :--- |
| **Retail Selling Price** | **₹20.00 (2,000p)** | **₹50.00 (5,000p)** | **₹100.00 (10,000p)** |
| **Variable Cost Target (AI Spend)** | ₹4.00 (400p) | ₹9.00 (900p) | ₹24.00 (2,400p) |
| **Estimated Gateway Fee (Razorpay ~2% + GST)** | ₹0.47 (47p) | ₹1.18 (118p) | ₹2.36 (236p) |
| **Expected Contribution per Document** | **₹15.53 (1,553p)** | **₹39.82 (3,982p)** | **₹73.64 (7,364p)** |
| **Expected Contribution Margin %** | **77.65%** | **79.64%** | **73.64%** |

*Note: In local deterministic No-LLM mode, variable AI cost is ₹0.00, raising the contribution margin to 97.6% (₹19.53), 97.6% (₹48.82), and 97.6% (₹97.64) respectively.*

---

## 3. Financial Planning & Volume Models

### 3.1 Illustrative Sales Mix
- **50% Basic** (₹20.00)
- **35% Standard** (₹50.00)
- **15% Extended** (₹100.00)

**Weighted Blended Metrics per Document:**
- **Blended Revenue:** $0.50(20) + 0.35(50) + 0.15(100) = \mathbf{₹42.50}$
- **Blended Gateway Fee:** $0.50(0.47) + 0.35(1.18) + 0.15(2.36) = \mathbf{₹1.00}$
- **Blended AI Processing Target:** $0.50(4.00) + 0.35(9.00) + 0.15(24.00) = \mathbf{₹8.75}$
- **Blended Contribution Margin:** $42.50 - 1.00 - 8.75 = \mathbf{₹32.75}\text{ (77.06%)}$

---

### 3.2 Monthly Operating Results Across Volume Tiers

#### Scenario A: Lean VPS Hosting (~₹700 / month, e.g. Hetzner CPX11 + Domain)
| Monthly Volume | Gross Revenue | Gateway Fees | AI Variable Cost | Fixed Hosting | Net Operating Margin | Operating Margin % |
|---|---|---|---|---|---|---|
| **50 docs/mo** | ₹2,125 | ₹50 | ₹438 | ₹700 | **₹937** | **44.1%** |
| **100 docs/mo** | ₹4,250 | ₹100 | ₹875 | ₹700 | **₹2,575** | **60.6%** |
| **200 docs/mo** | ₹8,500 | ₹200 | ₹1,750 | ₹700 | **₹5,850** | **68.8%** |
| **500 docs/mo** | ₹21,250 | ₹500 | ₹4,375 | ₹700 | **₹15,675** | **73.8%** |
| **1,000 docs/mo** | ₹42,500 | ₹1,000 | ₹8,750 | ₹700 | **₹32,050** | **75.4%** |

*Break-Even Volume: $\frac{₹700}{₹32.75} \approx \mathbf{22\text{ documents/month}}$.*

---

#### Scenario B: Intermediate VPS Hosting (~₹1,500 / month, e.g. Hetzner CPX21 + Backups + Alerts)
| Monthly Volume | Gross Revenue | Gateway Fees | AI Variable Cost | Fixed Hosting | Net Operating Margin | Operating Margin % |
|---|---|---|---|---|---|---|
| **50 docs/mo** | ₹2,125 | ₹50 | ₹438 | ₹1,500 | **₹137** | **6.4%** |
| **100 docs/mo** | ₹4,250 | ₹100 | ₹875 | ₹1,500 | **₹1,775** | **41.8%** |
| **200 docs/mo** | ₹8,500 | ₹200 | ₹1,750 | ₹1,500 | **₹5,050** | **59.4%** |
| **500 docs/mo** | ₹21,250 | ₹500 | ₹4,375 | ₹1,500 | **₹14,875** | **70.0%** |
| **1,000 docs/mo** | ₹42,500 | ₹1,000 | ₹8,750 | ₹1,500 | **₹31,250** | **73.5%** |

*Break-Even Volume: $\frac{₹1,500}{₹32.75} \approx \mathbf{46\text{ documents/month}}$.*

---

#### Scenario C: Managed Cloud Hosting (~₹3,000 / month, e.g. Cloud Run + Cloud SQL)
| Monthly Volume | Gross Revenue | Gateway Fees | AI Variable Cost | Fixed Hosting | Net Operating Margin | Operating Margin % |
|---|---|---|---|---|---|---|
| **50 docs/mo** | ₹2,125 | ₹50 | ₹438 | ₹3,000 | **-₹1,363** (Loss) | **-64.1%** |
| **100 docs/mo** | ₹4,250 | ₹100 | ₹875 | ₹3,000 | **₹275** | **6.5%** |
| **200 docs/mo** | ₹8,500 | ₹200 | ₹1,750 | ₹3,000 | **₹3,550** | **41.8%** |
| **500 docs/mo** | ₹21,250 | ₹500 | ₹4,375 | ₹3,000 | **₹13,375** | **62.9%** |
| **1,000 docs/mo** | ₹42,500 | ₹1,000 | ₹8,750 | ₹3,000 | **₹29,750** | **70.0%** |

*Break-Even Volume: $\frac{₹3,000}{₹32.75} \approx \mathbf{92\text{ documents/month}}$.*

---

## 4. Stress-Testing: AI Cost Inflation Scenarios

To protect founder solvency during edge-case document structures or complex revisions, Writelynx includes an active Cost Governor with hard spend caps.

### 4.1 Stress Case 1: AI Token Costs Double ($2\times$)
- Blended AI Cost: $2 \times ₹8.75 = \mathbf{₹17.50}$
- Blended Contribution: $₹42.50 - ₹1.00 - ₹17.50 = \mathbf{₹24.00}$ (56.5% Contribution Margin)
- At 500 docs/mo (Lean VPS ₹700): Net Operating Profit = $500(24.00) - 700 = \mathbf{₹11,300}$ (53.2% Margin)

### 4.2 Stress Case 2: AI Token Costs Hit 100% Circuit Breaker Cap ($2.5\times - 3\times$)
- Basic Tier Ceiling: Hard cap at ₹4.00
- Standard Tier Ceiling: Hard cap at ₹9.00
- Extended Tier Ceiling: Hard cap at ₹24.00
- When the circuit breaker trips at 85% spend, the system switches to compact prompts. At 100%, the Cost Governor instantly halts remote model calls and serves deterministic local transformations (zero marginal cost).
- **Guaranteed Margin Floor:** Variable processing cost can never exceed the configured ceiling. Minimum gross margin is strictly bounded at **> 70%** across all tiers.
