# Writelynx — Privacy, Data Protection & Ephemeral Retention Policy

**Document Classification:** Confidential & Operational Specification  
**Target Platform:** Writelynx (VIT-Exclusive Paid Academic SaaS)  
**Applicability:** All student submissions, document processing pipelines, session storage, and database persistence.

---

## 1. Executive Summary & Core Guarantees

Writelynx is built on a fundamental security principle: **student academic manuscripts are high-stakes, proprietary intellectual property that must never be retained permanently, leaked to third parties, or used for model training.**

Unlike generic consumer editing tools or unvetted freemium "humanizers" that harvest user text to train LLMs or build reference databases:
1. **Zero AI Training Guarantee:** No student manuscript, excerpt, citation, revision, or feedback data is ever submitted to, stored by, or used to fine-tune or train any foundational or proprietary AI model.
2. **Student Intellectual Property Ownership:** Students retain 100% exclusive copyright and moral rights over their submitted text, research data, and generated revisions. Writelynx acts purely as an ephemeral computational processor.
3. **Automated Ephemeral Retention (7-Day TTL Purging):** Raw uploaded files, extracted paragraph chunks, intermediate structures, and generated outputs are automatically purged after **7 days**. Students can execute immediate synchronous hard deletion at any time.
4. **Deny-by-Default Multi-Tenancy:** Storage paths, database records, and memory structures are strictly partitioned by VIT Student User ID (`user_id`). No cross-tenant visibility is physically possible.

---

## 2. Zero-Retention AI Integration Policy

When an AI model is invoked for sentence-level revision or academic tone polishing:
- **Zero Data Retention (ZDR) Enforcement:** External API integrations (e.g., Anthropic Claude, OpenAI, Google Gemini) must use enterprise endpoints with contractual zero-data-retention terms where inputs and outputs are not logged to persistent disk or used for training.
- **Deterministic Rule-First Engine:** Whenever possible, Writelynx leverages local regex, rule-based transforms, and scikit-learn local vectorizers (TF-IDF + Cosine similarity) which execute entirely on the local VPS without dispatching any text to external networks.
- **Circuit Breaker Data Minimization:** If external AI spend reaches 85% or external API is paused via admin kill switches (`AI_API_PAUSED`), the system seamlessly switches to local zero-cost deterministic heuristics without degradation of user workflow or external network exposure.

---

## 3. Storage Hierarchy & Ephemeral Lifecycle

```
[ Upload Attempt ]
       │
       ▼
1. /storage/quarantine/   ──(Security/Overage Failure / 2-Hr TTL)──► Immediate Secure Unlink
       │
       ▼ (Passes Inspection & Validation)
2. /storage/documents/{doc_id}/ 
       │
       ├─► Authoritative OOXML Parser & Diff Engine
       ├─► Analysis findings & sentence hashes
       ├─► DOCX Track Changes & PDF Exports
       │
       ▼ (User Downloads Final Package or 7 Days Elapsed)
3. Scheduled TTL Purge ────► Hard File Unlink & SQLite Scrubbing
```

### 3.1 Stage 1: Quarantine Isolation (`/storage/quarantine/`)
- When a document is uploaded via `POST /api/upload-gate/upload-doc`, it is streamed directly into an isolated quarantine staging directory.
- The file is checked for magic bytes (`PK\x03\x04`), macros (`.docm`, `vbaProject.bin`), zip bomb decompression ratios (> 100:1 or > 100MB), zip-slip path traversal, and raw XML entity injection (`<!DOCTYPE`, `<!ENTITY`).
- **Failure Action:** If the file fails any inspection check or if the word/page count exceeds the student's purchased plan limits without an upgrade, the quarantined file is **immediately deleted from disk** (`os.unlink()`). Orphaned scratch files older than 2 hours are swept by `RetentionService.purge_failed_quarantine_files()`.

### 3.2 Stage 2: Promoted Active Storage (`/storage/documents/`)
- Conforming documents are moved atomically via filesystem rename to `/storage/documents/{doc_id}_{filename}`.
- All file permissions are set to `0600` (readable/writable only by the isolated `writelynx` system user).
- Extracted text chunks, structure metadata, and sentence hashes are indexed in the local SQLite database (`manuscript_studio.db`), bound to the student's `user_id`.

### 3.3 Stage 3: Automated TTL Deletion Engine (`RetentionService`)
- **Completed Output Retention (7 Days):** Active manuscripts, paragraph caches, and generated exports have a maximum Time-To-Live (TTL) of **7 days** (`DOCUMENT_RETENTION_DAYS=7`).
- **Abandoned Upload Retention (1 Hour):** Unused upload reservation tokens older than 1 hour are automatically expired and unlinked (`RetentionService.purge_abandoned_upload_reservations()`).
- **Automated Background Reaper:** The background worker (`durable_worker.py`) periodically runs `RetentionService.run_all_purges()` to scrub expired records and disk files.
  - Disk artifacts (DOCX, exports, sources, detector PDFs) are securely unlinked.
  - Database records in `documents`, `revisions`, `findings`, and `reference_sources` are cascaded and deleted.
- **User-Initiated Immediate Purge:** Students can click "Delete Document" in the UI (`DELETE /api/documents/{id}`), triggering synchronous disk unlinking across all primary files, exports, sources, and detector PDFs, followed by database row deletion across all dependent tables.

---

## 4. Cryptographic Security & Identity Protection

| Layer | Standard / Mechanism | Implementation Details |
|---|---|---|
| **In-Transit Encryption** | TLS 1.3 / TLS 1.2 | Mandatory HTTPS enforced by Caddy reverse proxy; HSTS with 1-year duration; A+ SSL Labs target. |
| **At-Rest Encryption** | LUKS / AES-256-XTS | Host VPS block storage encrypted at rest. Document hashes computed with SHA-256 for tampering detection. |
| **Authentication Tokens** | 256-bit CSPRNG | 32-byte cryptographic random tokens generated via `secrets.token_hex(32)`. Validated against active sessions with 7-day TTL. |
| **Upload Reservation Tokens**| Single-Use CSPRNG | 16-byte upload tokens valid for 15 minutes; invalidated immediately upon upload consumption. |
| **Payment Signature Auth** | HMAC-SHA256 | Razorpay webhook and client payment signatures verified via constant-time comparison (`hmac.compare_digest`). |

---

## 5. Compliance with Indian DPDP Act (2023)

Writelynx complies fully with the Indian Digital Personal Data Protection Act (DPDP Act 2023):
1. **Purpose Limitation (Section 4):** Student email addresses (`@vitstudent.ac.in`) and registration numbers (e.g., `21BCE1042`) are collected solely for authenticating VIT enrollment, verifying student eligibility, and routing notifications. No data is sold or profiled for advertising.
2. **Data Minimization (Section 5):** No unnecessary personally identifiable information (PII) such as phone numbers, home addresses, or government IDs are collected or stored.
3. **Right to Erasure (Section 12):** Students possess an unconditional right to request total account deletion. Deleting an account wipes session tokens, entitlement histories, document logs, and personal audit trails.
4. **Data Processor Transparency:** All cloud infrastructure and database instances are hosted in regional data centers ensuring low latency and sovereign compliance.
