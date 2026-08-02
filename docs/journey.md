# Truth Mirror: The Day 1 Pre-Launch Fixes Journey

## Overview
This document chronicles the extensive Day 1 Pre-Launch hardening and bug-fixing process for Truth Mirror. Following a technical audit, a series of critical vulnerabilities, architectural weaknesses, and user-experience issues were identified and systematically resolved before production launch.

## 1. Blocker / Crashing Issues Resolved
- **H21 - Model Import Initialization Crash:** The NLP pipeline was crashing because it required the `en_core_web_sm` model but failed to download it automatically. We updated `nlp_pipeline.py` to ensure `en_core_web_sm` is the default model and explicitly downloaded it if missing. We also updated the Dockerfile to only download the `sm` model, abandoning the `trf` model to reduce bloat.
- **H22 - Prompt Injection Vulnerability:** Addressed a critical security vulnerability where adversarial users could inject raw commands (e.g., `IGNORE ALL PREVIOUS PROMPTS`) into claim titles or URLs. We implemented an escaping function in `source_analyzer.py` to strip markdown backticks and encapsulate all source text within rigid `<untrusted_content>` tags.

## 2. Technical Audit & Architecture Findings
- **M16 - FAISS Deletion Desync:** The FAISS index vector search was becoming misaligned with the document list upon deletions because the base `IndexFlatL2` does not support explicit ID tracking. We wrapped FAISS in an `IndexIDMap`, linking vector embeddings to persistent integer IDs.
- **M20 - Archival Mock Stubs Removed:** Removed hardcoded test stubs from legacy components (such as UN Documents and Academic Papers) that were artificially polluting the evidence pipeline during testing.

## 3. Low-Level / UX Fixes
- **L1 - Dockerfile Optimization:** Updated the Docker build process to remove unnecessary large transformer models (`en_core_web_trf`), significantly speeding up container deployment.
- **L8 - Frontend Decoupling:** Refactored the monolithic UI by splitting it into `index.html`, `style.css`, and `script.js` to ensure maintainability and easier dynamic routing.
- **L11 - Authentication Overhaul:** **(Major)** Completely replaced the legacy, browser-native HTTP Basic Auth (`WWW-Authenticate`) with a bespoke session-based authentication system. We introduced an in-memory session manager (`_active_sessions`) with UUID tokens, created a dedicated `/api/login` endpoint, and built a custom UI login screen featuring a stunning Aurora Borealis background and glassmorphism.

## 4. Documentation Strategy
To ensure long-term maintainability, we codified the entire architectural philosophy of Truth Mirror into three core documents:
- `Overview.md` for stakeholders and product managers.
- `features.md` outlining every functional capability (including the new login UI).
- `tech.md` providing a deep dive into the multi-agent pipeline and legacy routing structures.

## Conclusion
The application is now structurally sound, secure against prompt injections, and features a polished, professional authentication flow ready for production users.
