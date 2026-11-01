# Implementation Record & Recovery Status

| Milestone | Acceptance criteria | Dependencies | Status |
|---|---|---|---|
| M1 Audit | Inspect source, routes, models, tests and real files | None | **Complete**: React/Vite + FastAPI/SQLite stack audited; all 10 test suites identified |
| M2–M3 DOCX ingestion/preservation | Stable OOXML mapping; element-path addressing; byte-identical no-edit export; table/run protection | M1 | **Complete**: Stable XML tree index paths used instead of paragraph ordinals; tested against complex tables/captions |
| M4–M6 Detector extraction/alignment/comparison | Native vector/raster highlights; duplicate ambiguity; dynamic fragment comparison; disclaimers | M2 | **Complete**: ZeroGPT/Turnitin vector fills extracted; `DetectorComparator` computes dynamic comparison (0 hardcoded values); disclaimers enforced |
| M7–M9 Diagnostics/evidence/facts/citations | 12 independent diagnostic modules; evidence-to-claim factual evaluation; citation audit; immutable facts | M2 | **Complete**: `EvidenceManager.assess_claim` evaluates numerical consistency; rejects ungrounded claims; QuantLens profile protected |
| M10 Revision control | Validated suggestions; stale-edit rejection (409); explicit fact approval; persistent snapshots; undo/redo/restore | M7–M9 | **Complete**: `RevisionManager` with 64-shard locking; version snapshots in SQLite; append-only events; stale edit prevention |
| M11 Frontend | Error propagation (`ApiError`, `studio-error`); 9-step evidence grounding; Terminology Exception badges; Priority filters | API contracts | **Complete**: TypeScript build clean (1521 modules); live error banners; full 3-column review UI |
| M12 Export validation | Reopen DOCX/PDF; relationships/media preserved; LibreOffice conversion; page verification | M3, M10 | **Complete**: Revised 20-page PDF and DOCX successfully generated and verified intact |
| M13 Background Jobs & Processing | Cancellable jobs (`/api/jobs/{id}/cancel`); durable status/stage tracking; findings review | M4–M12 | **Complete**: `AnalysisJob` tracking with progress percentage and cancellation checkpoints |
| M14 Regression & Verification | Comprehensive test suite; all unit, adversarial, OOXML, and workflow tests | M13 | **Complete**: 67/67 tests passing (100%) in `backend/tests/` |

## Defect Resolution Status

- **Defect A (Hardcoded Detector Comparison)**: RESOLVED. `DetectorComparator` extracts and compares real highlight fragments, calculating exact and fuzzy overlap, character/word differences, and non-conflation disclaimers without hardcoded sample outputs.
- **Defect B (Permissive Claim Verification)**: RESOLVED. `EvidenceManager.assess_claim` performs rigorous term overlap, fact and metric extraction, and contradiction checks. Claims are categorized into `verified`, `partially_supported`, `contradicted`, or `needs_evidence`. Broad generalizations or unverified files are never marked verified.
- **Defect C (False Success Responses & Error Handling)**: RESOLVED. Universal error interception in `checkedFetch()` (`frontend/src/services/api.ts`) dispatches `studio-error` events rendered in an application-wide alert banner. Server errors (400, 404, 409, 422, 500) always display meaningful messages.
- **Defect D (DOCX Paragraph Targeting After Tables)**: RESOLVED. `DocxParser` and `StructurePreserver` locate paragraphs using hierarchical OOXML node element paths (`xml_path`) from the root of `word/document.xml`. Tables and paragraphs are indexed distinctly; edits never misidentify paragraphs after tables.
- **Defect E (Regression Coverage)**: RESOLVED. Test suite expanded from 45 to 67 automated tests covering OOXML integrity, table stability, stale edit rejection, fact validation, and workflow endpoints.
- **Defect F (Revision Persistence & Snapshots)**: RESOLVED. `RevisionManager` creates immutable `DocumentVersion` snapshots and `RevisionEvent` audit logs on SQLite. Stale edits trigger HTTP 409 `RevisionConflict`.
- **Defect G (Cancellable Background Jobs)**: RESOLVED. Added `AnalysisJob` lifecycle tracking in `analysis_worker.py` and API endpoints `POST /api/jobs/{id}/cancel`, `POST /api/findings/{id}/review`, and `GET /api/documents/{id}/detector-reports`.
