# AuditReady

A barebones working prototype for the BBS × Ramp Hackathon. AuditReady turns audit support requests into an evidence workspace with visible gaps, source documents, human review, and an exportable evidence package.

## Run

Requires Python 3.10+; no dependencies, credentials, or installation needed.

    cd /workspace/ramp
    python server.py

Open port 8000 in your local development browser. The server binds to 127.0.0.1 by default; use `python server.py --host 0.0.0.0 --port 8000` when your development environment requires external binding. This is a development server without authentication; use synthetic data only.

## 90-second demo

1. Start with four PBC requests and eight synthetic source documents. Two requests have missing evidence, one needs judgment, and one has ready evidence.
2. Review the Q3 invoice request: six ledger transactions qualify, but only five have supporting invoices. Summit Consulting's $16,000 invoice is missing. A similarly priced quote is correctly excluded.
3. Expand a source document to see its transaction reference highlighted.
4. Review the reconciliation: a $1,550 difference and missing reviewer sign-off block approval.
5. Review the September statement, inspect its source, check the acknowledgment, and approve it.
6. Export a ZIP containing numbered request folders, source documents, an auditor-facing CSV index, and a JSON manifest. Missing items remain visible; they cannot be marked approved.

## Import your own request list

Download the sample CSV from the UI or supply UTF-8 CSV with these columns:

    id,request,owner
    PBC-01,"All invoices over $10,000 from Q3 2026",Accounts payable
    PBC-02,September 2026 operating bank statement,Treasury

Only `request` is required. Imports replace the current request list and reset approvals. Up to 100 requests; no Excel/PDF ingestion in this version. Matching still uses the seeded corpus, not your company's systems.

Supported demo rules: Q3 2026 invoices strictly over a specified amount (including `$10k`); September/October 2026 bank statements and reconciliations. Other requests go to manual scoping. These are narrow demo templates, not a general natural-language parser: avoid requests with additional conditions or multiple periods.

## Validation

    python -m unittest discover -s tests -v
    node --check static/app.js

## Architecture and next steps

Python's standard-library HTTP server serves the frontend and JSON endpoints: `GET /api/demo`, `POST /api/analyze`, and `POST /api/export`. The browser manages request selection and session-only reviewer acknowledgments. The server recomputes evidence status on export and refuses approval for unresolved requests.

This version has **no LLM, embeddings, OCR, live integrations, durable storage, or authenticated approvals**. Evidence consists of synthetic text documents. Explicit transaction references and structured ledger filters make the initial demo reproducible. Ledger coverage does not establish completeness of the original accounting records. No files are sent to external services.

For the AI hackathon submission, the next milestone is an LLM adapter that translates arbitrary PBC requests into a validated structured scope, with citations and abstention for ambiguous requests. Keep ledger filtering, coverage calculations, and approval eligibility deterministic. Then add PDF page citations, document ingestion, authenticated approval history, and connector access controls. The present prototype demonstrates the workflow; it does not yet satisfy the AI component on its own.
