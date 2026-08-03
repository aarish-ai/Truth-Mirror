# Truth Mirror: Features & Capabilities

This document outlines every feature, capability, and functionality available in Truth Mirror, spanning both the user-facing frontend and the powerful backend orchestration.

## 1. User-Facing Dashboard (Frontend Features)

Truth Mirror is served via a lightweight, ultra-fast UI (built with HTML, CSS, and Vanilla JS) accessible right from your browser. 

### The Final Verdict & Confidence Interval
- **Clear Categorization:** Claims receive a definitive label (e.g., `True`, `False`, `Unclear`, `Partially True`).
- **Confidence Scoring:** Alongside the verdict, the system provides a mathematical confidence interval (e.g., "Confidence: 85%"), letting the user know exactly how much trust the AI places in its own synthesis based on the volume and quality of evidence.

### Geopolitical Analysis & Dispute Mapping
- **The Hidden Story:** A dedicated UI panel that exposes the unspoken geopolitical context behind the claim. It answers the "Why is this being said?" question by analyzing hidden implications and omitted facts from the sources.
- **Dispute Analysis:** Explicitly highlights the core disagreements between global actors. If Western media claims X and State Media claims Y, this panel places those arguments side-by-side.
- **Current Situation & Background:** Provides a dynamically generated summary of the ongoing historical and political backdrop of the claim.

### Interactive Evidence Table
- **Source Transparency:** A dynamic, sortable table displaying every single article, paper, and report the AI analyzed to reach its conclusion.
- **Perspective Mapping:** Each source is labeled with its geopolitical alignment (e.g., Western Allied, Neutral, Non-Western State Media).
- **Stance & Snippets:** Shows exactly what the source claimed (Supports / Contradicts) along with a direct excerpt.
- **Wayback Machine Integration:** Includes direct "View Source ↗" links. If a source link is dead or has been scrubbed from the internet, the backend automatically generates a "View Archive ↗" link using the Wayback Machine so the user can still verify the evidence.

### Aesthetic & UX Features
- **Secure Authentication:** A custom UI session-based login screen with a sleek glassmorphism design and Aurora Borealis animated background protects the system from unauthorized access, replacing legacy HTTP Basic Auth.
- **Dark Mode:** A sleek, premium dark-mode aesthetic with vibrant accent colors and smooth micro-animations.
- **Dynamic Loaders:** Informative loading states that guide the user while the backend performs its complex multi-agent retrieval.
- **Terms & Conditions:** A dismissible legal and ethical usage banner for first-time users.

---

## 2. Backend Orchestration (Core Capabilities)

### Claim Gating & Validation (`claim_scope_gate.py`)
To protect server resources and maintain focus, Truth Mirror features a stringent gating mechanism. If a user submits a claim that is purely pop-culture, sports, or domestic triviality, the LLM intercepts the request and instantly rejects it with a polite explanation, preventing unnecessary downstream API calls.

### Narrative Tracking & Memory (`context_tracker.py`)
Truth Mirror remembers the history of queries to detect malicious narrative campaigns.
- **Entity Tracking:** Extracts key entities (people, nations) and tracks claims made about them over time.
- **Narrative Engineering Detection:** If a user (or bot network) submits 4+ semantic variants of the exact same claim within 60 minutes, the system raises a "Narrative Engineering" warning.
- **Mutation Detection:** If semantically similar claims are submitted but the historical verdicts begin to differ wildly, it alerts the user that the claim is mutating.

### Legacy Academic & Specialized Routing (`routing.py` & `retrieval_acad.py`)
Although currently optimized for geopolitics, Truth Mirror retains a highly sophisticated, legacy routing engine.
- **Regex-Based Claim Routing:** Uses complex regular expressions to perfectly categorize incoming text (e.g., identifying policy, legal, or demographic claims).
- **Scientific/Medical Pipelining:** If an edge-case geopolitical claim requires biological or medical verification (e.g., bioweapons, pandemic origins), the system queries:
  - **PubMed:** Chunked and parallelized E-Summary queries for NIH peer-reviewed literature.
  - **Semantic Scholar & arXiv:** Deep indexing of whitepapers, pre-prints, and policy documents.
  
### Perspective Queries & Triangulation
When verifying a geopolitical claim, the `GeoOrchestrator` doesn't just search Google. It forces the search engine to pull from specific silos:
- *Western media (Reuters, AP)*
- *Russian/Chinese media (TASS, CGTN)*
- *Middle Eastern media (Al Jazeera)*
- *Official Government Statements*
By triangulating these distinct geographical data sets, the system ensures that no single geopolitical bloc controls the final verdict.

### Infrastructure Resilience
- **API Rate Limit Bypassing:** Automatic key-rotation seamlessly swaps overloaded LLM API keys in mid-execution.
- **Analysis Fallbacks:** If the primary AI provider goes completely offline, the OpenRouter fallback chain ensures the claim is still successfully verified.
