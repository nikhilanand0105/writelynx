# Writelynx — Open Source Software (OSS) License Audit & PyMuPDF Review

**Document Classification:** Legal & Technical Compliance Audit  
**Target Platform:** Writelynx (Academic Manuscript Studio for VIT Students)  
**Date of Audit:** November 2026  
**Auditor:** Principal Software Architect & Application Security Engineer  

---

## 1. Executive Summary

Writelynx is an academic editing and document analysis platform intended for paying students. This audit provides an evidence-based assessment of all dependencies, specifically reconciling code reality against licensing obligations.

---

## 2. Dependency License Inventory

| Package | Version | Declared License | Commercial SaaS Compatibility | Notes |
|---|---|---|---|---|
| **fastapi** | `>=0.110.0` | MIT | Permissible | High-performance asynchronous web framework |
| **uvicorn** | `>=0.28.0` | BSD-3-Clause | Permissible | Standard ASGI production server |
| **pydantic** | `>=2.6.0` | MIT | Permissible | Data parsing and validation |
| **pydantic-settings** | `>=2.2.0` | MIT | Permissible | Environment settings parsing |
| **sqlalchemy** | `>=2.0.28` | MIT | Permissible | ORM and SQL toolkit |
| **python-docx** | `>=1.1.0` | MIT | Permissible | Primary OOXML Word document parsing and editing |
| **lxml** | `>=5.1.0` | BSD-3-Clause | Permissible | High-performance XML/HTML processing |
| **defusedxml** | `>=0.7.1` | Python-2.0 / PSF | Permissible | XML vulnerability defense wrapper |
| **scikit-learn** | `>=1.4.0` | BSD-3-Clause | Permissible | TF-IDF local text vectorization |
| **rapidfuzz** | `>=3.6.0` | MIT | Permissible | High-speed C++ string similarity matching |
| **pillow** | `>=10.2.0` | HPND | Permissible | Image inspection & validation |
| **httpx** | `>=0.27.0` | BSD-3-Clause | Permissible | Asynchronous HTTP client for provider APIs |
| **aiofiles** | `>=23.2.1` | Apache-2.0 | Permissible | Asynchronous file I/O |
| **python-multipart** | `>=0.0.9` | Apache-2.0 | Permissible | Streaming multipart file uploads |
| **google-auth** | `>=2.28.0` | Apache-2.0 | Permissible | Google OAuth2 ID token verification |
| **razorpay** | `>=2.0.0` | MIT | Permissible | Official Razorpay payment gateway integration |
| **boto3** | `>=1.34.0` | Apache-2.0 | Permissible | Cloudflare R2 object storage SDK |
| **psycopg2-binary** | `>=2.9.9` | LGPL with exception | Permissible | PostgreSQL database driver |
| **alembic** | `>=1.13.0` | MIT | Permissible | Database schema migrations |
| **pymupdf** | `>=1.24.0` | **GNU AGPLv3 / Commercial** | **REQUIRES OWNER ACTION** | Used for vector highlight extraction & layout rendering |

All frontend runtime dependencies (React, Vite, Tailwind, Zustand, React Query, Lucide) are licensed under permissive open-source licenses (MIT, ISC, Apache-2.0, BSD-3-Clause).

---

## 3. In-Depth PyMuPDF Code Reality vs. Licensing Assessment

### 3.1 Audited Code Reality
An exhaustive code inspection confirms that `pymupdf` (MuPDF) is directly imported in four (4) backend modules:
1. `backend/app/services/pdf_highlight_extractor.py`: Extracts vector drawing rectangles (`drawing['items']`), quads, and bounding boxes for ZeroGPT/Turnitin detector PDF highlights.
2. `backend/app/services/export_engine.py`: Renders PDF pixmaps for layout overflow validation and thumbnail generation.
3. `backend/app/services/quarantine_inspector.py`: Verifies PDF page count and structural health.
4. `backend/app/services/external_report_parser.py`: Parses external similarity report PDFs.

### 3.2 Can `pypdf` Replace PyMuPDF?
**No.** `pypdf` is a pure-Python library designed for basic text extraction and PDF merging. It does **not** provide:
- Access to native vector drawing commands (`re`, `m`, `l`, `c`) necessary to locate ZeroGPT's yellow highlight rectangles.
- MuPDF's rendering engine for visual pixmap generation (`get_pixmap()`).
- High-precision glyph coordinate tracking required for paragraph-to-highlight alignment.

Replacing PyMuPDF with `pypdf` would break the external detector highlight extraction and comparison features.

### 3.3 AGPLv3 Implications for Commercial SaaS
PyMuPDF is dual-licensed by Artifex Software Inc.:
- **GNU AGPL v3:** Requires that any organization running the software over a network must provide the complete corresponding source code of the network application to all users.
- **Commercial OEM/SaaS License:** Available for purchase directly from Artifex Software Inc., exempting the licensee from the AGPL copyleft obligations.

### 3.4 Unresolved Owner Action Item (Pre-Launch Blocker)
Prior to accepting real commercial payments from paying students, the project owner must select and execute one of two legal paths:
1. **Purchase an Artifex Commercial License:** Contact Artifex Software Inc. (https://artifex.com/licensing) to obtain a commercial license for MuPDF/PyMuPDF; OR
2. **Publish Under AGPLv3:** Formally declare and license the entire Writelynx application under GNU AGPLv3, making the complete source code publicly accessible.

**Status:** UNRESOLVED OWNER ACTION (Commercial Launch Blocker).
