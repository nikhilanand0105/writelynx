# Writelynx — Pricing Strategy, Unit Economics & Margin Model

## 1. Value Proposition & Competitive Positioning

Existing academic tools either cost excessive recurring subscriptions ($15–$30/month) or lack formatting preservation, corrupting headings and tables when exporting revised manuscripts.

Writelynx offers **pay-per-document microtransactions** calibrated specifically for Indian college students:
- Single-use, no recurring subscriptions, no forced auto-renewals.
- Zero risk: Document formatting, references, and citations are guaranteed to be protected.
- Upgrades charge only the exact mathematical difference in paise.

---

## 2. Unit Economics per Processed Document

| Metric | Basic Plan (Up to 4 Pages) | Standard Plan (Up to 20 Pages) | Extended Plan (Up to 50 Pages) |
| :--- | :--- | :--- | :--- |
| **Retail Price (Student Pays)** | **₹20.00 (2,000p)** | **₹50.00 (5,000p)** | **₹100.00 (10,000p)** |
| **Payment Gateway Fee (Razorpay ~2% + GST)** | ₹0.47 (47p) | ₹1.18 (118p) | ₹2.36 (236p) |
| **AI LLM Cost (Gemini 1.5 Flash)** | ₹0.60–₹1.50 | ₹2.00–₹4.50 | ₹5.00–₹12.00 |
| **Hard AI Budget Ceiling** | **₹4.00 (400p)** | **₹9.00 (900p)** | **₹24.00 (2,400p)** |
| **Fixed Infrastructure Share (at 500 docs/mo)** | ₹0.96 (96p) | ₹0.96 (96p) | ₹0.96 (96p) |
| **Net Contribution Margin per Doc** | **₹14.50 – ₹17.90** | **₹38.80 – ₹45.80** | **₹71.20 – ₹89.20** |
| **Gross Margin % (Worst-Case AI Ceiling)** | **72.7%** | **77.7%** | **70.6%** |
| **Gross Margin % (Typical Usage)** | **82.5%** | **84.2%** | **79.5%** |

---

## 3. Break-Even & Revenue Projections

- **Fixed Monthly Costs**:
  - Hetzner Cloud CPX21: ~₹480/month
  - Domain renewal (amortized): ~₹80/month
  - Total Fixed Costs: **~₹560/month**
- **Break-Even Volume**:
  $$\text{Break-Even} = \frac{₹560}{₹38.80\text{ (avg margin per Standard doc)}} \approx \mathbf{15\text{ documents per month}}$$

At VIT (Vellore campus alone has 35,000+ students):
- **100 documents / month**: ₹4,200 net profit
- **500 documents / month**: ~₹21,000 net profit
- **2,000 documents / month** (deadline peak): ~₹84,000 net profit
