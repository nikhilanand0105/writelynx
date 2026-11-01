# Writelynx — Terms of Service, Privacy Policy & Consumer Disclosures

**Last Updated:** November 2026  
**Service URL:** https://writelynx.in | https://writelynx.pages.dev  
**Contact Email:** support@writelynx.in | security@writelynx.in  

---

## 1. Independent Operation Disclaimer (VIT Trademark & Brand Separation)

**Writelynx is an independent software-as-a-service application developed for students at Vellore Institute of Technology. It is NOT an official product, department, or affiliated service of Vellore Institute of Technology (VIT).**
- All trademarks, service marks, and institution names mentioned are the property of their respective owners.
- Institutional Google OAuth (`@vitstudent.ac.in`) is used strictly as an eligibility gate to prevent unauthorized access and verify student standing.
- No institutional endorsement, grading authority, or academic sanction is implied or represented.

---

## 2. Terms of Service

1. **Eligibility:** Access to Writelynx is strictly restricted to students currently possessing a valid, active `@vitstudent.ac.in` Google Workspace identity. Personal email addresses (`@gmail.com`, etc.) are automatically rejected at the gateway.
2. **Pay-Per-Document Single-Use Entitlements:**
   - **Basic Tier:** ₹20 — up to 4 pages / 15,000 characters / 10 MB DOCX.
   - **Standard Tier:** ₹50 — up to 20 pages / 65,000 characters / 20 MB DOCX.
   - **Extended Tier:** ₹100 — up to 50 pages / 160,000 characters / 30 MB DOCX.
   - Each entitlement authorizes processing for exactly one (1) manuscript. Once an analysis job completes successfully, the entitlement is fully consumed and cannot be reused for a different document.
3. **Academic Integrity Commitment:** Writelynx is an academic editing, proofreading, citation validation, and manuscript structure preservation engine. Users agree not to use the service to generate fraudulent academic submissions or misrepresent source citations.
4. **Account Conduct:** Any attempt to reverse engineer API endpoints, bypass quarantine gate checks, submit decompression bombs (ZIP bombs), manipulate payment parameters, or access other users' manuscripts will result in immediate permanent suspension without refund.

---

## 3. Refund & Cancellation Policy

1. **Pre-Processing Refund:** If a payment is successfully captured by the payment gateway but technical failure prevents the issuance of an entitlement token, the transaction will be refunded in full to the original UPI payment method within 5–7 business days upon receipt of request to `support@writelynx.in`.
2. **Quarantine Overage Protection:** If an uploaded manuscript exceeds the page or character capacity of the purchased plan, the student's entitlement is **not** consumed. The student is offered the option to:
   - Upgrade to the next plan for the exact price difference; OR
   - Cancel and submit a different document within their purchased tier; OR
   - Request a full refund if no alternative document will be submitted.
3. **Completed Output:** Once document analysis and editing suggestions have been generated and delivered, the single-use entitlement is deemed fulfilled and non-refundable.

---

## 4. Privacy Policy & Data Sovereignty (DPDP Act 2023)

1. **Zero AI Training Guarantee:** No student manuscript, reference text, citation, or editing revision is ever retained for model training or shared with external data brokers.
2. **Strict Ephemeral Retention (7-Day TTL):**
   - Uploaded DOCX manuscripts and exported documents are retained for exactly **7 days** to allow students to review suggestions and download revised files.
   - After 7 days, all files on disk and associated detailed findings are permanently and irreversibly purged by the automated retention daemon.
   - Students may execute immediate hard deletion at any time via the document interface.
   - Failed quarantine uploads are automatically wiped after 2 hours. Abandoned upload reservations expire after 1 hour.
3. **Data Security & Encryption:** Data in transit is protected using TLS 1.3 with HSTS. Multi-tenant access controls enforce deny-by-default document ownership. No student can view, edit, or download another student's document.

---

## 5. Security Incident Response & Contact

If you identify a potential security vulnerability or privacy defect in Writelynx:
- Email: **security@writelynx.in**
- PGP Fingerprint: Available on request.
- We acknowledge vulnerability reports within 24 hours and do not take legal action against bona fide security researchers acting in good faith.
