# Writelynx — Incident Response Playbook & Disaster Recovery

**Document Classification:** Production Operations & Security Runbook  
**Target Platform:** Writelynx (VIT-Exclusive Paid Academic SaaS)  
**Applicability:** Production operations, DevOps, emergency interventions, and student support.

---

## 1. Incident Severity Classification

| Severity | Definition | Target Response | Target Resolution | Examples |
|---|---|---|---|---|
| **SEV-1 (Critical)** | Core service completely down; payment corruption; security breach; cross-tenant data leak. | < 15 minutes | < 2 hours | Database corruption, unauthorized file access, payment double-charging. |
| **SEV-2 (Major)** | External AI provider failure; upload processing stalled; student login degradation. | < 30 minutes | < 4 hours | Razorpay webhook delay, OpenAI/Anthropic API outage, worker queue backlog. |
| **SEV-3 (Minor)** | Non-blocking UI glitch; formatting warning in export; slow response on non-critical routes. | < 2 hours | < 24 hours | Cosmetic CSS misalignment, minor docx preview artifact, slow telemetry load. |

---

## 2. Emergency Kill Switches Overview

The admin system exposes 4 global kill switches accessible via `POST /api/admin/kill-switch` with the `X-Admin-Key` header:

```bash
# Emergency Kill Switch Activation Command:
curl -X POST https://writelynx.app/api/admin/kill-switch \
  -H "X-Admin-Key: $ADMIN_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"key": "PURCHASES_PAUSED", "enabled": true}'
```

| Switch Key | When to Activate | Effect on Application |
|---|---|---|
| `PURCHASES_PAUSED` | Razorpay API downtime, payment discrepancies, banking gateway maintenance. | `/api/payments/create-order` returns HTTP 503; users cannot purchase new entitlements. Existing valid entitlements still process. |
| `UPLOADS_PAUSED` | Storage exhaustion, filesystem corruption, or malware wave. | `/api/upload-gate/upload-doc` returns HTTP 503; students cannot upload new files. Active jobs complete. |
| `PROCESSING_PAUSED` | Backend CPU/RAM thrashing, critical bug discovered in OOXML parser. | Job worker pauses dispatching new analysis tasks. Running jobs complete; queued jobs wait safely. |
| `AI_API_PAUSED` | External AI vendor outage, unexpected API rate limit, or billing spike. | Backend immediately switches 100% of document rewrites to local deterministic rule-based transforms with zero external cost. |

---

## 3. Incident Playbooks

### 3.1 Playbook A: Razorpay Webhook Failure / Payment Desynchronization
**Scenario:** A student pays successfully on Razorpay, but their browser window closes or network drops before the client verify request reaches Writelynx, and the Razorpay webhook delivery is delayed.

1. **Verify Payment on Razorpay Dashboard:**
   - Log into Razorpay Merchant Dashboard and search for the student's email (`regno@vitstudent.ac.in`).
   - Confirm status is `captured` and note `order_id` and `payment_id`.
2. **Execute Manual Reconciliation CLI:**
   ```bash
   cd /opt/writelynx/backend
   venv/bin/python scripts/reconcile_payment.py \
     --order-id "order_xxxxxx" \
     --payment-id "pay_xxxxxx"
   ```
3. **Automated Mechanism:**
   - The webhook handler is fully idempotent. When Razorpay retries webhook delivery, the `PaymentWebhookEvent` table detects unhandled orders, verifies the HMAC signature, transitions the entitlement to `AVAILABLE`, and grants the student's slot.

---

### 3.2 Playbook B: Malicious Upload or Zip Bomb Attempt
**Scenario:** A student uploads a file disguised as `.docx` containing an embedded exploit, macro payload, or zip bomb.

1. **Automated Interception:**
   - The quarantine inspector traps the anomaly during stream inspection.
   - The file is deleted from `/storage/quarantine/` immediately.
   - An audit log entry is written with `severity=HIGH` recording the student's `user_id`, filename, and violation type.
2. **Admin Investigation & Suspension:**
   ```bash
   # Check recent high-severity audit logs:
   curl -s https://writelynx.app/api/admin/audit-logs \
     -H "X-Admin-Key: $ADMIN_MASTER_KEY" | jq '.[] | select(.severity=="HIGH")'
   
   # Restrict abusive student account:
   curl -X POST https://writelynx.app/api/admin/restrict-user \
     -H "X-Admin-Key: $ADMIN_MASTER_KEY" \
     -H "Content-Type: application/json" \
     -d '{"user_id": "usr_suspect_id", "is_restricted": true, "reason": "Malicious payload injection"}'
   ```

---

### 3.3 Playbook C: External AI Vendor Outage (Anthropic / OpenAI / Gemini)
**Scenario:** External AI provider experiences 500 errors, degraded performance, or rate limits during a major submission evening.

1. **Automated Circuit Breaker:**
   - When the cost governor detects upstream failure or 85% budget consumption, it automatically degrades to deterministic mode.
2. **Operator Force-Override:**
   - Activate `AI_API_PAUSED`:
     ```bash
     curl -X POST https://writelynx.app/api/admin/kill-switch \
       -H "X-Admin-Key: $ADMIN_MASTER_KEY" \
       -H "Content-Type: application/json" \
       -d '{"key": "AI_API_PAUSED", "enabled": true}'
     ```
   - Students receive instantaneous local rule-based transforms without pipeline aborts or unhandled exceptions.
3. **Student Notification:**
   - Frontend displays a notice: *"Operating in high-speed local processing mode during peak network traffic."*

---

### 3.4 Playbook D: Host Memory Pressure / Job Queue Stall
**Scenario:** Concurrency bursts cause host RAM utilization to exceed 85%.

1. **Check System Health:**
   ```bash
   top -b -n 1 | head -n 20
   free -m
   ```
2. **Reap Stale Jobs & Clear Zombie Processes:**
   ```bash
   # Trigger stale job reaper:
   cd /opt/writelynx/backend && venv/bin/python -c "
   from app.services.job_queue import reap_stale_jobs
   from app.db.session import SessionLocal
   db = SessionLocal()
   reap_stale_jobs(db)
   db.close()
   print('Stale jobs reaped successfully')
   "
   ```
3. **Restart Backend Worker (Zero Downtime):**
   ```bash
   sudo systemctl reload-or-restart writelynx
   ```

---

## 4. Post-Mortem & Review Process

Following any SEV-1 or SEV-2 incident:
1. Conduct a blameless post-mortem within 24 hours.
2. Export and archive audit logs from SQLite `audit_logs` table.
3. Create automated regression test in `test_writelynx_security_suite.py` replicating the failure conditions.
4. Verify that no student funds were improperly deducted and issue manual entitlement credits if necessary.
