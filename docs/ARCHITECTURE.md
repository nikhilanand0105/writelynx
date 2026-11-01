# Architecture

React/TypeScript/Vite serves the local review UI. FastAPI exposes typed REST APIs. SQLAlchemy/SQLite stores documents, blocks, findings, evidence, report extraction records, jobs, version snapshots, review events and exports. Alembic owns schema upgrades.

Original uploads are stored with generated identifiers and SHA-256 hashes. Processing reads uploaded content; it never executes code or fetches embedded links. Accepted edits live in database blocks. Export patches a copy of the original OOXML package and validates it before making an artifact downloadable.

Independent service modules handle DOCX structure, PDF highlight geometry, text alignment, writing diagnostics, source retrieval, citation checks, invariant protection and optional LLM adapters. Remote adapters are blocked by offline mode. Source text is delimited untrusted material in prompts; returned edits are schema-checked and reviewed.

Analysis jobs execute in the server's background worker threads with durable stages, progress, cancellation and errors. Single-user loopback deployment is the supported deployment model. Concurrent edits are serialized within the process and stale suggestion content is rejected.
