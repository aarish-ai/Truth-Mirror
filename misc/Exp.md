# Truth Mirror — Deep Explanation

---

## Part I: Conceptual Explanation

### The Problem That Started Everything

The world has no shortage of news. The internet has given every person on Earth access to more information than any library in history could hold. And yet, by every measurable indicator — public understanding of geopolitical events, cross-border trust in media institutions, the ability to separate military reality from state narrative — we are arguably *less* informed than we were in the age of printed newspapers. The paradox isn't hard to explain: we don't have an information shortage. We have a curation problem.

When a conflict erupts, or a ceasefire is announced, or a government falls — the BBC, Al Jazeera, CGTN, TASS, and Dawn do not disagree on the raw facts. They disagree on *which* facts are worth reporting, which voices are worth amplifying, and which context frames the story in a way that serves their institutional interests or their audience's priors. This is not lying. It's something far more sophisticated: **narrative construction through selective emphasis and strategic omission**.

The average reader, reading only one outlet, has no way to detect this. They don't know what isn't in the article they're reading. They don't know that the ceasefire their newspaper described as a "diplomatic victory" was characterized as a "tactical retreat under pressure" in another media ecosystem. They have no view from outside the narrative they're already inside.

Truth Mirror was built to provide exactly that: a view from outside.

### The Core Conceptual Model

At the heart of Truth Mirror is a simple but powerful idea: **the truth of a geopolitical event is rarely contained in any single source. It emerges from the intersection of many sources — and often, it is most legible in the gaps between them.**

This is a different epistemological stance from most fact-checkers. Most fact-checking tools operate like a spell-checker: you submit a claim, the tool searches for sources, and it tells you whether the sources agree or disagree with the claim. The implicit model is that the truth is *out there*, and the job of the tool is to *retrieve* it.

Truth Mirror operates on a different model. It treats each media source as a *partial witness* with a specific vantage point, a known bias profile, and an institutional incentive structure. It then convenes those witnesses — organized by geopolitical alignment bloc — and listens not just to what they say, but to what they *collectively omit*, where they *agree despite their usual disagreements*, and where their divergence reveals something about the underlying event that none of them is reporting directly.

This approach has three core conceptual stages:

**Stage 1 — Evidence as signals, not truth.** Retrieved articles are not treated as facts. They are treated as signals. Each source's stance toward a claim is analyzed through the lens of who the source is: which country funds it, what political bloc it serves, what its track record of reliability is, and what it has historically chosen to emphasize. A BBC article and a TASS article saying the same thing is a different kind of evidence than two independent wire services saying the same thing. Institutional corroboration is not the same as independent corroboration.

**Stage 2 — Perspective blocs as analytical units.** The system doesn't analyze sources individually in isolation. It groups them into alignment blocs — Western/NATO-aligned, Russia/China-aligned, Non-Aligned/Global South, Gulf/Arab media, and Independent/Wire services — and then asks a second-order question: *what is this bloc, as a collective, choosing to emphasize or suppress?* This is what the Perspective Synthesizer does. It turns a list of individual source analyses into a geopolitical map of who is saying what and why.

**Stage 3 — Hidden stories as primary output.** The most important output of the system is not the verdict. It is the Hidden Story Extractor's output — the set of narratives that emerge from connecting facts that individual sources report separately, noticing what multiple blocs are collectively avoiding, and reasoning about what those patterns imply about the actual underlying event. This is the kind of analysis that senior intelligence analysts and experienced foreign correspondents do by instinct. Truth Mirror tries to formalize it.

### What Makes This Different From Existing Fact-Checkers

Existing fact-checkers — Snopes, PolitiFact, Full Fact — operate in a fundamentally different paradigm. They are designed for the domestic political context: a politician makes a claim, a journalist verifies it against a database of known facts or quotes. This model works well for claims about domestic statistics, historical records, or clearly falsifiable statements.

Geopolitical claims don't work this way. When a claim is "America has stopped bombing Iran," there is no database to query. There is no ground truth record you can look up. There are competing official statements, there are on-the-ground reports of varying reliability, there are intelligence community assessments you don't have access to, and there are the silences — the outlets that would normally be loudly reporting this that are saying nothing. The right answer to that claim might be: "The bombing has probably stopped in the officially-stated sense, but the silence across all media blocs — rather than confirmation or denial — is itself a red flag that suggests something more complex is happening that none of the parties involved want to formally acknowledge."

That kind of answer — nuanced, directional, epistemically honest about its own uncertainty, and willing to name the silence as evidence — is what Truth Mirror is designed to produce. The `MEDIA_BLACKOUT` verdict captures the category of claims where coordinated silence across otherwise-competing sources is the most informative signal of all.

### The Scope Design Decision

One of the deliberate architectural choices is the scope gate: Truth Mirror only processes geopolitical claims from 2015 onward. This is not a technical limitation but a conceptual one. Events from before 2015 are better served by historical scholarship, archival journalism, and academic databases. The tool is purpose-built for the contemporary geopolitical information environment — where the news cycle is fast, official narratives are contested in real time, and the gap between what governments say and what is actually happening is at its widest and most consequential.

The scope gate uses a local language model (Qwen2.5:3b, running entirely on-device via Ollama) to classify each incoming claim before the expensive pipeline runs. If the claim is about the 1979 Iranian Revolution, or about the freezing point of water, or about a soccer match — it is rejected immediately with a clear, human-readable explanation. Only claims that pass this gate enter the main pipeline.

---

## Part II: Technical Explanation

### Overall Architecture

Truth Mirror is a Python backend built on FastAPI, serving a single-page HTML/CSS/JS frontend. The backend is organized as a Python package (`truth_mirror/`) containing approximately 50 modules that handle every stage of the pipeline. The architecture is deliberately layered: each stage produces a structured data object that the next stage consumes, making the pipeline easy to reason about, debug, and extend.

The main entry point is `TruthMirrorPipeline.verify(claim: str)` in `orchestrator.py`. This method first runs the scope gate, and if the claim passes, instantiates a `GeopoliticalPipeline` from `geo_orchestrator.py` and delegates the full verification run to it.

### Stage 0: Scope Gate (`claim_scope_gate.py`)

The gate is a hybrid system. It first uses a simple regex-based year extractor to look for explicit year mentions in the claim. If an explicit year before 2015 is found, the claim is rejected immediately without any LLM call — a purely deterministic shortcut that saves compute and handles the most obvious cases instantly.

If no disqualifying year is found, a structured prompt is sent to Qwen2.5:3b via Ollama's local inference API. The prompt is precisely engineered to return a JSON object with fields for `is_geopolitical`, `involved_parties`, `claim_subtype`, `in_temporal_scope`, and `temporal_reason`. The `format: "json"` parameter in the Ollama API request forces the model into structured output mode, dramatically reducing parse failures compared to free-form generation.

If the Ollama call fails for any reason (network error, model timeout, invalid JSON), the system falls back to a regex keyword match against a list of geopolitical terms (`GEO_KEYWORDS` from `geo_classifier.py`). This ensures the scope gate never becomes a single point of failure that silently breaks the pipeline.

The result is a `ClaimScopeResult` dataclass that passes the classification forward to the geo orchestrator — meaning the geo orchestrator never needs to re-classify the claim. Classification is done once, at the front, and the result is propagated.

### Stage 1: Claim Decomposition (`local_decomposer.py`)

Complex claims often contain multiple assertions. "America has stopped bombing Iran and the ceasefire was brokered by Qatar" is two separate verifiable claims. The local decomposer sends the claim to Qwen2.5:3b with a prompt that instructs it to return a JSON array of sub-claims. Robust regex extraction with multiple fallback patterns handles cases where the model wraps the array in markdown code blocks or adds extra prose. If all parsing fails, the original claim is returned as a single-element list — a sensible default that allows the pipeline to continue.

### Stage 2: Query Generation (`geo_query_generator.py`)

For each sub-claim, the query generator creates a set of targeted search queries designed to retrieve evidence from multiple geopolitical perspectives. These are not simple keyword searches. The generator creates queries with explicit framing intent:

- A **military facts** query: `"military: united states iran bombing cessation june 2026"`
- A **diplomatic** query: `"diplo: united states iran ceasefire announcement june 2026"`
- An **economic context** query: `"economic: united states iran sanctions status june 2026"`

Additionally, five **perspective queries** are appended to the query list:
- `"{claim} western media coverage {year}"`
- `"{claim} Russia China reaction {year}"`
- `"{claim} Arab Gulf media {year}"`
- `"{claim} official statement government {year}"`
- `"{claim} independent analysis {year}"`

These perspective queries are the key architectural decision that ensures the retrieval phase doesn't just return the most SEO-ranked English-language content. They explicitly force the system to retrieve coverage from different geopolitical angles.

### Stage 3: Parallel Retrieval

The retrieval system is the broadest and most complex part of the codebase. The `FreeSourceRetrieval` class acts as a conductor for a set of independent connectors, each responsible for a different source family:

- **Wikipedia**: Uses the MediaWiki `search` API in JSON format. Returns article extracts directly from the knowledge graph — reliable for factual background but often lags behind breaking news.
- **Wikinews**: Uses the same MediaWiki JSON API (recently migrated from a broken RSS endpoint that was returning HTML error pages). Good for recent events covered by the Wikinews community.
- **Crossref**: Queries academic citation databases for peer-reviewed sources, useful for scientific or economic claims.
- **Google News RSS**: Parses the Google News RSS feed using feedparser for a broad sweep of current headlines.
- **GDELT**: Queries the GDELT Project's API, which indexes news from 65 languages and 200+ countries, providing genuine global coverage.
- **Al Jazeera, TASS, CGTN, Dawn**: These non-Western connectors scrape or query the RSS feeds/APIs of each outlet directly, providing sources from the Gulf/Qatari, Russian state, Chinese state, and Pakistani perspectives respectively.

All retrieval happens in parallel using a `ThreadPoolExecutor` with a cap of 10 concurrent workers. Each thread calls `self.retriever.retrieve(query, claim_subtype)` and results are collected as they complete via `concurrent.futures.as_completed`. The result is a flat list of `EvidenceItem` dataclass objects, which are then deduplicated by URL/title key before the next stage.

### Stage 4: Per-Source Analysis (`source_analyzer.py`)

This is the most computationally intensive stage of the pipeline. For each deduplicated `EvidenceItem`, the `SourceAnalyzer` sends a structured prompt to Qwen2.5:3b via aiohttp. The prompt provides:

1. The original claim
2. The source's metadata (name, country, alignment) looked up from `source_registry.py` — a large JSON registry mapping domain patterns to geopolitical metadata
3. The article title and first 800 characters of the excerpt

The model is instructed to return a JSON object with: `summary`, `stance` (one of five labels: SUPPORTS, CONTRADICTS, PARTIALLY_SUPPORTS, INCONCLUSIVE, BACKGROUND_ONLY), `stance_confidence`, `stance_reasoning`, `key_claims`, `what_emphasized`, `what_omitted`, and `hidden_implication`.

Crucially, all analyses run concurrently using `asyncio.Semaphore(max_concurrent=5)` — a semaphore that allows up to 5 analyses to run simultaneously against the local Ollama server without overwhelming it. The timeout for each individual analysis is 120 seconds (increased from 60 to handle larger articles). If an analysis times out or produces unparseable output, a `SourceAnalysis` with an empty `summary` is returned, and these are filtered out downstream with `[s for s in source_analyses if s.summary]`.

### Stage 5: Consensus & Dispute Detection (`geo_orchestrator.py`)

After source analyses are collected, `compute_consensus_disputes()` performs a lightweight string-matching algorithm across all `key_claims` arrays. It normalizes claim text to lowercase, then checks if any two claims share a substring of more than 10 characters. If the same claim appears across multiple sources with at least 20% of total sources (minimum 3) mentioning it, it's flagged as significant. If all mentions have `SUPPORTS` or `PARTIALLY_SUPPORTS` stances, it's a consensus point. If there's a mix of `SUPPORTS` and `CONTRADICTS`, it's disputed.

This is deliberately simple — no NLP library, no embedding similarity. The tradeoff is accepted: it misses paraphrased versions of the same fact, but it avoids the latency and dependency cost of running a sentence transformer on every claim comparison.

### Stage 6: Perspective Synthesis (`perspective_synthesizer.py`)

The `PerspectiveSynthesizer` groups all `SourceAnalysis` objects by their `alignment` field (e.g., `western`, `russia_state`, `china_state`, `gulf`, `independent`). For each group, it formats a structured summary and sends all groups simultaneously in a single prompt to Gemini 2.5 Flash via the Google GenAI SDK.

The prompt asks Gemini to characterize what each media bloc is *collectively* saying about the claim — producing a `PerspectiveGroup` object per bloc with fields for `collective_stance`, `collective_narrative`, `what_they_emphasize`, `what_they_omit`, `internal_disagreements`, and `credibility_note`.

The retry logic uses exponential backoff: the first retry waits 1 second, the second waits 2 seconds, the third waits 4 seconds, the fourth waits 8 seconds. This handles the Google API's occasional `503 Service Unavailable` spikes during high-demand periods, which previously caused the system to permanently fail after just 2 linear-wait retries.

The fallback chain is: Gemini 2.5 Flash → NVIDIA Nemotron Ultra (via OpenRouter). If both fail, an empty list is returned and the downstream stages degrade gracefully.

### Stage 7: Hidden Story Extraction (`hidden_story_extractor.py`)

The `HiddenStoryExtractor` is architecturally the most ambitious part of the system. It takes the full `source_analyses` list, the `perspective_groups` list, the consensus/dispute points, and the formatted omissions per bloc, and sends them all to Gemini 2.5 Flash with a deeply specialized prompt.

The prompt instructs Gemini to identify 2–5 hidden stories that: emerge from connecting facts individual sources report separately, explain why certain facts are being emphasized or suppressed, and represent what "an experienced intelligence analyst or senior journalist would conclude by reading between the lines." The prompt explicitly names categories of analysis to look for: economic incentives, military strategy, domestic political pressures, diplomatic back-channels, historical patterns being repeated, or facts that contradict the official narrative of multiple parties simultaneously.

Each hidden story is a JSON object with: `title`, `explanation`, `supporting_facts`, `which_sources_hint_at_this`, `which_sources_suppress_this`, and `significance`.

### Stage 8: Verdict Generation (`verdict_engine.py`)

The `VerdictEngine` consolidates everything into a final structured verdict. It counts source stances (support/contradict/partial/inconclusive), formats bloc narratives, and passes the hidden story titles and omissions to Gemini with a verdict prompt.

The latest version explicitly instructs the model to incorporate hidden stories into its full reasoning, and introduces the `MEDIA_BLACKOUT` verdict category for claims where coordinated silence — rather than contradiction — is the most informative signal. The full verdict object includes: `verdict`, `confidence` (0.0–1.0), `confidence_label`, `one_line_verdict`, `full_reasoning`, `what_is_true`, `what_is_false`, `what_is_unclear`, `strongest_evidence_for`, `strongest_evidence_against`, and `source_quality_note`.

### Stage 9: Result Assembly & Serialization

The final `GeopoliticalResult` dataclass is assembled in `run_async()` and returned to the FastAPI app layer, which calls `TruthMirrorPipeline.to_json()` to serialize it into a dictionary that the frontend's JavaScript can consume. The `to_json()` method is carefully written to provide safe defaults for every field the frontend expects, preventing `undefined` errors in the UI even when optional fields are missing from the result.

### Frontend Architecture

The frontend is a single `index.html` file using vanilla JavaScript, CSS custom properties, and a hand-coded dark glassmorphism design. There are no frameworks, no build steps, no npm dependencies. The JavaScript makes a single `POST` request to `/verify` with the claim text, then renders the structured response progressively — showing source analyses as a grid, perspective blocs as cards, hidden stories as expandable sections, and the final verdict as a prominently styled badge.

A specific UI upgrade handles scope gate rejections: instead of a JavaScript `alert()` dialog, the frontend renders a styled rejection component with an explanation of why the claim was rejected.

---

## Part III: What I Learned

### 1. Epistemology Before Engineering

The single most important thing I learned from this project is that the hardest part of building an intelligent system is not the code. It's the conceptual framework the code is implementing. Before writing a single line, I had to answer questions I'd never thought seriously about before: What does it mean for a claim to be "verified"? Is it sufficient that multiple sources say the same thing? What's the difference between institutional corroboration and independent corroboration? Is silence evidence? Can a fact be true and misleading simultaneously?

These are not engineering questions. They're epistemological ones. I ended up reading significantly about media theory, intelligence analysis methodologies (specifically how intelligence communities reason under uncertainty), and the philosophy of testimony. The concept of a `MEDIA_BLACKOUT` verdict didn't come from a product requirement — it came from understanding how intelligence analysts treat coordinated omission in state media as a first-class signal, and realizing that my verdict system had no way to express that insight even when the hidden story extractor had correctly identified it.

### 2. The Gap Between "Working" and "Correct"

Early versions of the pipeline would return results that looked impressive on the surface — a confidence score, a verdict label, a list of sources — but were epistemically hollow. The verdict was "UNVERIFIABLE" even when the hidden story extractor had produced a brilliant analysis showing that coordinated inconclusiveness was itself the story. The pipeline was *functioning* — no errors, no crashes — but it wasn't *thinking* correctly. The model was ignoring the most interesting part of its own output.

This taught me something crucial: **the prompt is the algorithm**. When working with large language models, the system's intelligence is not primarily in the Python code. It's in the quality of the instructions you give the model at each stage. Realizing that the verdict engine's prompt didn't say "use the hidden stories in your reasoning" — and that this was why it wasn't doing so — was a moment of real clarity about how LLM-based systems actually work. You don't debug them the way you debug a deterministic function. You audit the instructions.

### 3. Failure Is Invisible Until It's Catastrophic

One of the most painful debugging experiences was discovering that three modules — `perspective_synthesizer.py`, `hidden_story_extractor.py`, and `verdict_engine.py` — had all been silently broken for an extended period. The bug was a Python scoping issue: an `import json` statement inside a fallback code block was creating a local variable named `json` that shadowed the module-level import. So when the code reached `json.loads()` earlier in the same function (before the inline import), Python's runtime saw that `json` was assigned later in the same function scope and threw an `UnboundLocalError`.

What made this catastrophic is that these errors were being caught by broad `except Exception` blocks and silently logged as `perspective synthesis failed entirely`, returning empty lists. The pipeline continued. The frontend rendered. Nothing looked obviously wrong. It was only by deliberately inspecting the logs line by line that I noticed the systematic absence of perspective groups and hidden stories in the output. The lesson: **catch-all exception handling is not defensive programming. It is error burial.** Every exception should be logged with enough context (including `type(e).__name__`) to enable recovery, not just acknowledged and swallowed.

### 4. Real-World APIs Are Not Reliable

I assumed, naively, that if a public API existed, it would work reliably. The Wikinews RSS feed was a lesson in why that assumption is wrong. The endpoint formally exists. It returns a `200 OK`. But the response body is an HTML error page, not XML. This breaks `xml.etree.ElementTree.fromstring()` with a confusing error about "mismatched tag" that has nothing to do with my code and everything to do with Wikinews's infrastructure. The fix — switching to the stable JSON MediaWiki API — took 20 minutes once I understood the problem. Understanding the problem took much longer, because the error message was completely misleading.

Similarly, Google's Gemini API returns `503 Service Unavailable` during peak demand periods. A simple 2-retry loop with a 2-second wait is not enough. Exponential backoff — waiting 1, 2, 4, 8 seconds — dramatically increases the probability of success on subsequent attempts. I also learned to think of external API calls not as reliable function calls but as probabilistic operations that may need multiple attempts under real-world conditions.

### 5. Source Metadata Is as Important as Source Content

Early versions of the source analyzer sent just the article title and excerpt to the local model and asked it to infer the source's bias. This was unreliable — small local papers and major state broadcasters look the same when you only have a 300-word excerpt to go on. The `source_registry.py` module, which maps domain patterns to precomputed metadata (country, alignment, reliability tier, category), was one of the most impactful architectural additions to the system. By telling the model "this source is TASS, a Russian state broadcaster" rather than asking it to figure that out from the text, the quality of the stance analysis improved measurably. Knowing who is speaking before you analyze what they say is not cheating. It's how human analysts read news too.

### 6. Async Programming Is Genuinely Different

The source analysis stage — running 30–50 Ollama calls concurrently — forced me to deeply understand Python's asyncio model. I initially wrote the source analyzer using `concurrent.futures.ThreadPoolExecutor`, which worked but was slow and unpredictable. Rewriting it using `async/await` with `aiohttp` and `asyncio.Semaphore` reduced the analysis phase from several minutes to under 60 seconds for a typical claim, by allowing the Python event loop to efficiently manage hundreds of simultaneous network operations without spawning a thread per request.

The conceptual shift was understanding that asyncio's concurrency is not about parallelism — it's about *waiting efficiently*. When an HTTP request is waiting for a response from Ollama, the event loop can run code from another coroutine. This kind of cooperative multitasking is perfectly suited to I/O-bound workloads like calling a local inference server dozens of times. CPU-bound work (like actually running the model) still happens in a single-threaded process on Ollama's side, but the network I/O on our side becomes essentially free.

### 7. The Most Important Insight Is What's Not There

Perhaps the most profound conceptual lesson — one that the project taught through its own outputs rather than through any book — is that the most significant information in a geopolitical analysis is often the *absence* of information. When a claim is true and globally significant, you expect noise: multiple competing narratives, outlet-specific framings, partisan takes, at least one authoritative denial or confirmation. When everything is quietly "INCONCLUSIVE," that's not a neutral data state. That's a signal.

Building a system that can formally represent and reason about that insight — that can issue a `MEDIA_BLACKOUT` verdict when the silence is the story — required not just technical implementation but a willingness to expand the conceptual vocabulary of what "fact-checking" means. Most verification systems are built to find the truth. Truth Mirror is also built to notice when the truth is being actively hidden, and to say so.

---

*Truth Mirror is entirely self-funded, self-directed, and independently developed. No institution assigned it, no grade motivated it, and no external deadline shaped it. It exists because the question that generated it — why do well-informed people believe completely different things about the same events — seemed important enough to build something to help answer it.*
