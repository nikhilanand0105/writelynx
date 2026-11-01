# Writelynx — Entitlement State Machine & Double-Spend Protection

## 1. Single-Use Entitlement Lifecycle

An **Entitlement** in Writelynx represents a paid authorization to process exactly one manuscript document under specific plan constraints (page count, character count, and file size).

```mermaid
stateDiagram-v2
    [*] --> AVAILABLE: Verified Purchase / Webhook Fulfillment
    AVAILABLE --> UPLOAD_AUTHORIZED: /api/upload-gate/request-token
    UPLOAD_AUTHORIZED --> FILE_VALIDATING: Upload Received at Quarantine
    FILE_VALIDATING --> READY: File Inspection Passed & Within Limits
    FILE_VALIDATING --> OVER_LIMIT_PENDING_UPGRADE: File Exceeds Plan Limits
    OVER_LIMIT_PENDING_UPGRADE --> AVAILABLE: Upgrade Difference Paid
    READY --> RESERVED: Ingestion Complete, doc_id Linked
    RESERVED --> PROCESSING: /api/documents/{id}/analyze Started
    PROCESSING --> COMPLETED: All Diagnostics & Revisions Finished
    COMPLETED --> [*]
    
    AVAILABLE --> REFUNDED: Admin Refund
    AVAILABLE --> REVOKED: Integrity Violation / Ban
```

---

## 2. Double-Spending Mitigation

1. **State Transition Locks**: Every transition checks current state against `VALID_TRANSITIONS`. Attempting to transition from `PROCESSING` or `COMPLETED` back to `AVAILABLE` triggers HTTP 409 Conflict.
2. **Single-Use Upload Tokens**:
   - Calling `/api/upload-gate/request-token` transitions the entitlement from `AVAILABLE` to `UPLOAD_AUTHORIZED` and mints an ephemeral 15-minute token in `upload_reservations`.
   - Any prior unconsumed reservation for that entitlement is invalidated.
   - Upon upload receipt, the token is permanently flagged `is_consumed = True`.
3. **One Document per Entitlement**: The `entitlements` table enforces a foreign key relationship to `documents.id`. Once linked, the entitlement cannot be bound to a second document.
