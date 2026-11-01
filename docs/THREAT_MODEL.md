# Writelynx — Comprehensive Threat Model & Security Posture

## 1. Executive Summary

Writelynx processes untrusted user-submitted files (Microsoft Word `.docx` documents) and handles financial transactions from students. Because academic platforms frequently encounter attempts to bypass billing, exploit file parsers, or access peer documents, Writelynx implements defense-in-depth across the application boundary.

---

## 2. Threat Actors & Capabilities

1. **Malicious Student / Casual Attacker**: Attempts parameter tampering (changing plan price in client requests), replay attacks on payment webhooks, or uploading documents exceeding paid limits.
2. **Adversarial Attacker**: Attempts Remote Code Execution (RCE) via weaponized OpenXML packages (VBA macros, embedded executables), Zip bombs to cause server Denial of Service (DoS), or XML External Entity (XXE) attacks to read server files.
3. **Data Scraper / Impersonator**: Attempts unauthorized access to other students' thesis manuscripts or research drafts.

---

## 3. Threat Matrix & Defense Strategy (STRIDE)

| Threat Category | Potential Attack Vector | Applied Mitigation in Writelynx |
| :--- | :--- | :--- |
| **Spoofing** | Forging Google OAuth token or non-VIT email address | Cryptographic verification via `google-auth`; mandatory assertion that `email` ends with `@vitstudent.ac.in` and OAuth hosted domain `hd == "vitstudent.ac.in"`. |
| **Tampering** | Modifying Razorpay transaction amount or payment ID | Authoritative order creation in server-side integer paise; HMAC-SHA256 signature verification comparing `order_id\|payment_id` against `RAZORPAY_KEY_SECRET`. |
| **Repudiation** | Replaying processed webhook events or claiming double refund | Idempotent event ledger (`payment_webhook_events`) keyed by unique `event_id`; duplicate deliveries are detected and safely skipped. |
| **Information Disclosure** | Student A accessing Student B's manuscript or exported files | Multi-tenancy filter in all database queries (`WHERE user_id == current_user.id`); unauthorized access yields HTTP 403 Forbidden. |
| **Denial of Service** | Zip bomb / highly compressed nested XML files | Strict decompression quota (max uncompressed size 100MB; max compression ratio 100:1); excess immediately unlinked. |
| **Elevation of Privilege** | Normal student invoking administrative endpoints | Dependency `require_admin` enforces `user.is_admin == True`; non-admins are denied with HTTP 403. |

---

## 4. Deep OpenXML File Attack Surface & Hardening

1. **VBA Macros & Executables**:
   - Attack: Student uploads `.docm` containing auto-executing malicious macros or embedded OLE objects.
   - Defense: Quarantine inspector traverses package member list and rejects any archive containing `vbaProject.bin`, `vbaData.xml`, or any executable suffix (`.exe`, `.dll`, `.bat`, `.sh`, `.vbs`).
2. **Zip Slip / Path Traversal**:
   - Attack: Zip archive containing file entries like `../../../../etc/shadow`.
   - Defense: Filenames are evaluated using `PurePosixPath`; entries beginning with `/` or containing `..` or `:` trigger immediate rejection and file deletion.
3. **XML External Entity (XXE) & DTD Injection**:
   - Attack: XML parts containing `<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>`.
   - Defense: Raw byte audit scans every XML and `.rels` part for `<!DOCTYPE` and `<!ENTITY` tokens prior to parser instantiation, rejecting weaponized inputs.
