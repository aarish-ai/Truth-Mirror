# Original User Request

## Initial Request — 2026-07-24T10:11:44Z

# Teamwork Project Prompt

Working directory: c:\Users\DELL\.gemini\antigravity\scratch\Truth Mirror
Integrity mode: development

## Requirements

### R1. Fix Critical Issues (C1-C14)
Address all 14 Critical security, data corruption, and logic bugs identified in the codebase audit (e.g., SPARQL injection, XXE vulnerability, Auth bypass, aiohttp socket exhaustion). Ensure fixes are surgical and do not break the existing end-to-end pipeline functionality.

### R2. Programmatic Verification
Expand the existing `test_integration.py` (or write new test scripts) to explicitly assert that the C1-C14 fixes are functioning correctly (e.g., verifying auth enforcement, checking connection pooling, validating sanitized inputs).

## Acceptance Criteria

### Security & Logic Fixes
- [ ] An independent auditor agent reviews the code diffs and confirms that C1-C14 have been logically addressed without introducing regressions.
- [ ] `test_integration.py` runs successfully end-to-end.
- [ ] Programmatic assertions explicitly test at least 5 of the critical fixes (e.g. attempting an auth bypass returns a 401).
