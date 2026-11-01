# Repository Identity & Lineage Audit

**Project:** Writelynx — VIT-Exclusive Paid Academic SaaS  
**Audit Timestamp:** 2026-11-01T12:05:00+05:30  
**Author / Principal Engineer:** Nikhil Anand (24BCE1674)  
**Target Repository:** `https://github.com/nikhilanand0105/-writelynx.git`

---

## 1. Executive Summary & Verification Findings

Per **Phase 0** instructions, an exhaustive architectural inspection of local working directories, Git remotes, branches, and codebases was conducted to locate the authentic **Writelynx** academic document SaaS and explain prior repository naming discrepancies.

### Key Audit Conclusions:
1. **Prior Misalignment in `writelynx.git`:**
   - The remote repository `git@github.com:nikhilanand0105/writelynx.git` previously contained commits from `/Users/nikhilanand/Downloads/Delta`, which is **QuantLens-XAI** (a Python/Flask algorithmic trading and Explainable AI platform built for the BCSE418L course).
   - This occurred due to an administrative push from the `Delta` working directory.
2. **Identification of the Authentic Document SaaS:**
   - A filesystem-wide deep audit identified the authentic document-editing application in `/Users/nikhilanand/Downloads/PlagFree`.
   - **Backend Stack:** Python 3.11, FastAPI, Pydantic v2, SQLAlchemy, python-docx, lxml, RapidFuzz, PyMuPDF, scikit-learn.
   - **Frontend Stack:** React 18, TypeScript, Vite, Tailwind CSS, Lucide Icons, Zustand state management.
   - **Core Engine:** OOXML direct structural preservation engine, IEEE/APA citation auditor, local n-gram similarity engine, detector report extractor, and headless LibreOffice PDF export.
   - **Verification Baseline:** 67 automated backend tests passing (`67 passed in 33.10s`), and production frontend bundle compiles cleanly in 1.49s.
3. **Preservation Commitment:**
   - The research components and submission package in `/Users/nikhilanand/Downloads/Delta` (QuantLens-XAI) remain completely intact and untouched.
   - `/Users/nikhilanand/Downloads/PlagFree` is adopted as the canonical project directory for **Writelynx**, and will be hardened across all 28 productionization, security, billing, and cost-control phases.

---

## 2. Forensic Codebase Comparison

| Component / Trait | `/Users/nikhilanand/Downloads/Delta` | `/Users/nikhilanand/Downloads/PlagFree` |
|---|---|---|
| **Primary Domain** | Quantitative Finance, Algorithmic Trading, Explainable AI | Academic Document Analysis, Originality, Formatting Preservation |
| **Backend Framework** | Flask 3.0, Server-Sent Events (SSE) | **FastAPI 0.100+, Pydantic v2, SQLAlchemy** |
| **Frontend Framework** | Server-rendered Jinja2 HTML5 + ApexCharts | **React 18, TypeScript, Vite, Tailwind CSS** |
| **Document Processing** | None (CSV historical OHLCV series) | **Direct OOXML manipulation (`lxml`, `python-docx`), PyMuPDF** |
| **Existing Test Suite** | 140 assertions (trading invariants, 10 XAI metrics) | **67 passing tests (OOXML preservation, citations, facts, PDF)** |
| **Authentication Needs**| Single-user local paper broker | **Mandatory VIT Google Workspace (`@vitstudent.ac.in`)** |
| **Billing & Payments** | Simulated paper broker (zero real money) | **Razorpay test-mode integration (₹20, ₹50, ₹100 tiers)** |
| **Correct Target** | **QuantLens-XAI (Preserve Intact)** | **Writelynx SaaS (Productionize & Deploy)** |

---

## 3. Migration & Git Lineage Strategy

To align the GitHub repository `https://github.com/nikhilanand0105/-writelynx.git` with the real application:
1. Initialize Git in `/Users/nikhilanand/Downloads/PlagFree`.
2. Configure remote `origin` pointing to `git@github.com:nikhilanand0105/-writelynx.git`.
3. Retain existing working functionality: all 67 document preservation and analysis tests must continue passing.
4. Add the requested production hardening:
   - VIT-only Google OAuth authentication.
   - Razorpay payment-before-upload gate.
   - Single-use paid entitlement state machine.
   - Client-side size estimator + authoritative server validation.
   - Token & cost budgeting governor.
   - Asynchronous job queue.
   - Admin telemetry dashboard.
   - Complete security threat mitigation and 17 required technical reports.
5. Push the productionized Writelynx application to `https://github.com/nikhilanand0105/-writelynx.git` as the canonical `main` branch.

---

*Verified and Certified: November 1, 2026*
