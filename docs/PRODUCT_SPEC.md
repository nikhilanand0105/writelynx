# Manuscript Integrity Studio

Local academic DOCX review with independently imported detector reports, editorial diagnostics, research evidence, author-approved revisions, and validated exports.

## Boundaries
- Originals are immutable. Revisions are reversible snapshots and append-only events.
- External detector highlights describe third-party judgments, never authorship proof. Report metadata comes from the uploaded file; coverage is limited or unknown unless established.
- Editorial heuristics and retrieved evidence are candidates for review. Retrieval alone cannot verify a research claim.
- No-LLM is the default. Remote providers require explicit selection and disabling offline mode. Uploaded code is read as text and never executed.
- DOCX export patches original OOXML; unsupported structures remain intact and cannot be edited silently.
- Fact or citation changes require explicit author approval with a reason.

## Acceptance workflow
Upload DOCX → import detector PDF(s) → inspect extraction and alignment → run independent analysis → attach evidence → review claims and suggestions → accept/reject/manual edit → undo/redo/restore → validate → export DOCX/PDF → reopen outputs.

Optional dependencies: LibreOffice for PDF conversion; local OCR engine for image-only reports; separately configured LLM for generative editing. Missing optional capability must produce an actionable explanation.
