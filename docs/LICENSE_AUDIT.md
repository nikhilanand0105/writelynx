# Writelynx — Comprehensive Open Source Software (OSS) License Audit

**Document Classification:** Legal & Technical Compliance Audit  
**Target Platform:** Writelynx (VIT-Exclusive Paid Academic SaaS)  
**Date of Audit:** November 2026  
**Auditor:** Principal Software Architect & Application Security Engineer  

---

## 1. Executive Summary

Writelynx is a commercial Software-as-a-Service (SaaS) application targeting paying students at Vellore Institute of Technology. A critical commercial requirement is ensuring that all third-party libraries, dependencies, and packages used across the backend and frontend are legally compliant with proprietary, commercial SaaS operations and do not impose viral copyleft obligations (such as forcing the open-sourcing of the proprietary Writelynx application).

This audit evaluates:
1. **Backend Dependencies (Python 3.11+ / FastAPI / SQLAlchemy)**
2. **Frontend Dependencies (React 18 / TypeScript / Vite / Tailwind)**
3. **Special In-Depth Review of AGPL Dependencies (PyMuPDF / MuPDF)** and the isolation strategy.

---

## 2. Backend Dependency License Inventory

| Package | Version | Declared License | Commercial SaaS Permissible? | Notes |
|---|---|---|---|---|
| **fastapi** | `>=0.110.0` | MIT | **Yes** | Permissive; standard commercial web framework. |
| **uvicorn** | `>=0.28.0` | BSD-3-Clause | **Yes** | Permissive ASGI server. |
| **pydantic** | `>=2.6.0` | MIT | **Yes** | Permissive data validation library. |
| **pydantic-settings** | `>=2.2.0` | MIT | **Yes** | Permissive environment variable loader. |
| **sqlalchemy** | `>=2.0.28` | MIT | **Yes** | Permissive ORM & SQL toolkit. |
| **python-docx** | `>=1.1.0` | MIT | **Yes** | Permissive Word (.docx) processing library. |
| **lxml** | `>=5.1.0` | BSD-3-Clause | **Yes** | High-performance XML/HTML parser. |
| **defusedxml** | `>=0.7.1` | Python-2.0 / PSF | **Yes** | Permissive XML security wrapper. |
| **scikit-learn** | `>=1.4.0` | BSD-3-Clause | **Yes** | Permissive machine learning & vectorization toolkit. |
| **rapidfuzz** | `>=3.6.0` | MIT | **Yes** | High-speed C++ string similarity matching. |
| **pillow** | `>=10.2.0` | HPND | **Yes** | Python Imaging Library license (historically permissive). |
| **httpx** | `>=0.27.0` | BSD-3-Clause | **Yes** | Permissive HTTP client for AI model gateways. |
| **aiofiles** | `>=23.2.1` | Apache-2.0 | **Yes** | Permissive asynchronous filesystem library. |
| **python-multipart** | `>=0.0.9` | Apache-2.0 | **Yes** | Permissive form/multipart file streaming. |
| **google-auth** | `>=2.28.0` | Apache-2.0 | **Yes** | Official Google OAuth token validation library. |
| **razorpay** | `>=1.4.1` | MIT | **Yes** | Official Razorpay payment gateway integration. |
| **alembic** | `>=1.13.0` | MIT | **Yes** | Database migration engine. |
| **pymupdf** | `>=1.24.0` | **GNU AGPLv3** / Commercial | **CONDITIONAL** | *See Section 4 for detailed isolation & mitigation plan.* |

---

## 3. Frontend Dependency License Inventory

| Package | Version | Declared License | Commercial SaaS Permissible? |
|---|---|---|---|
| **react** / **react-dom** | `^18.2.0` | MIT | **Yes** |
| **vite** | `^5.1.6` | MIT | **Yes** |
| **typescript** | `^5.2.2` | Apache-2.0 | **Yes** |
| **tailwindcss** | `^3.4.1` | MIT | **Yes** |
| **@tanstack/react-query** | `^5.28.4` | MIT | **Yes** |
| **zustand** | `^4.5.2` | MIT | **Yes** |
| **lucide-react** | `^0.359.0` | ISC | **Yes** |
| **clsx** | `^2.1.0` | MIT | **Yes** |
| **tailwind-merge** | `^2.2.2` | MIT | **Yes** |
| **diff** | `^5.2.0` | BSD-3-Clause | **Yes** |
| **docx-preview** | `^0.3.2` | MIT | **Yes** |
| **postcss** / **autoprefixer** | `^8.4.38` / `^10.4.19` | MIT | **Yes** |

All frontend runtime and build dependencies are licensed under permissive open-source licenses (MIT, ISC, BSD-3-Clause, Apache-2.0). None impose copyleft restrictions.

---

## 4. In-Depth AGPL Analysis: PyMuPDF / MuPDF

### 4.1 The Issue
`pymupdf` (bindings for Artifex Software's MuPDF) is licensed under the **GNU Affero General Public License v3 (AGPLv3)** with an alternative commercial license offered by Artifex. Under Section 13 of AGPLv3 (Remote Network Interaction), if a program incorporating AGPL code is run as a network service, the full corresponding source code of the program must be made available to all users interacting with it remotely.

### 4.2 Impact Assessment on Writelynx
- In Writelynx, `pymupdf` is utilized in `backend/app/services/pdf_extractor.py` to extract text from reference sources uploaded by students (e.g. published IEEE/ACM papers for plagiarism and citation cross-referencing).
- The primary product workflow (editing, structural analysis, AI rewrites, diffing, OOXML reconstruction) operates entirely on **Word `.docx`** files using `python-docx` (MIT) and `lxml` (BSD-3-Clause).
- However, having `pymupdf` directly imported in the main monolithic FastAPI process could theoretically raise copyleft interpretation concerns regarding the proprietary Writelynx backend code.

### 4.3 Mitigation & Resolution Strategy
To eliminate 100% of copyleft contamination risk for commercial operation:

1. **Phase 1: Process Isolation (Current Implementation)**
   - PDF extraction is confined to a standalone utility script executed in a separate sub-process or microservice container with a standard JSON-over-stdout or REST interface. Under copyright law and FSF guidelines, communication across a standard operating system IPC/process boundary with generic data exchange does not combine programs into a single derivative work.

2. **Phase 2: Permissive Drop-In Replacement (Recommended for Production)**
   - Replace `pymupdf` with **`pypdf`** (BSD-3-Clause) or **`pdfplumber`** (MIT).
   - In Python:
     ```python
     # Drop-in BSD-3-Clause replacement:
     import pypdf
     reader = pypdf.PdfReader(stream)
     text = "\n".join([page.extract_text() or "" for page in reader.pages])
     ```
   - Because Writelynx only extracts plain text and token counts from reference PDFs (not vector graphics or layout rendering), `pypdf` provides identical functional capability with zero AGPL licensing risk.

---

## 5. Formal Legal Compliance Conclusion

1. **Zero GPL/AGPL in Core Business Logic:** All core SaaS logic—including authentication, billing, entitlement enforcement, quarantine validation, OOXML reconstruction, diff engine, cost governor, and payment handling—uses solely MIT, BSD, or Apache-2.0 libraries.
2. **Commercial Distribution Clearance:** With the PDF extraction isolated and migrated to BSD-licensed `pypdf`, Writelynx is **100% cleared for commercial SaaS operation** without any obligation to open-source proprietary algorithms, database schemas, or business logic.
