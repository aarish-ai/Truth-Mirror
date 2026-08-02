# Truth Mirror: Overview

## Introduction
In the modern information landscape, individuals are constantly exposed to news from countless global sources. Sorting fact from fiction is increasingly difficult. Traditional fact-checkers often provide binary "True" or "False" labels, which fail to capture the nuance of global events. Some sources provide verified facts, some share half-truths, and others propagate outright lies, heavily biased narratives, or omit crucial context.

**Truth Mirror** is a transparent, automated intelligence engine designed to solve this problem. When provided with a claim, it does not just return a simple rating. Instead, it acts as a comprehensive intelligence analyst: gathering global sources, mapping which channels are pushing which narratives, uncovering the underlying story behind the mainstream headlines, and explicitly highlighting where global perspectives diverge.

## The Geopolitical Focus
While Truth Mirror has the underlying architecture to process scientific, medical, and general claims, its primary gated focus is on **Geopolitics**. 

In global conflicts, elections, and diplomacy, the truth is often fragmented across borders. A claim that is stated as absolute fact in Western media might be completely contradicted by State Media in another region. Truth Mirror’s core value lies in its ability to aggregate these disparate perspectives (e.g., Reuters vs. Al Jazeera vs. TASS) and synthesize a neutral, highly detailed breakdown of the geopolitical reality, pointing out exactly where and why the narratives clash.

## High-Level Workflow

The user journey and system execution follow a robust, multi-stage pipeline:

1. **Authentication & Access:** Access is secured via a custom UI session-based login system (replacing legacy HTTP Basic Auth) to ensure only authorized users can query the engine.
2. **Claim Submission:** The authenticated user submits a claim via the web dashboard (e.g., "The US invaded Venezuela").
2. **Gating & Classification:** The system immediately classifies the claim. If it is purely non-geopolitical (e.g., a sports score), it is gracefully rejected to save resources. If it is valid, the engine determines its logical type (e.g., policy, military, biographical).
3. **Decomposition:** Complex claims are broken down into simpler, verifiable sub-claims to ensure comprehensive searching.
4. **Parallel Retrieval:** The engine simultaneously reaches out across the internet to pull live data. It queries standard news aggregators, non-western media RSS feeds, encyclopedia sources, and (if applicable) academic/scientific databases.
5. **Source Analysis:** Each piece of gathered evidence is analyzed individually to determine its stance on the claim, its inherent bias, and what information it might be intentionally omitting.
6. **Synthesis:** A highly capable reasoning AI reviews all the analyzed evidence, looking for consensus, disputes, and narrative engineering.
7. **The Final Dashboard:** The user is presented with a rich, interactive UI detailing the final verdict, confidence levels, the "Hidden Story", and an interactive table of all sources analyzed.

## Value Proposition
- **Nuance Over Binary:** Understand *why* a claim is disputed, not just whether it is true or false.
- **Radical Transparency:** Every source used in the synthesis is linked and categorized by its geopolitical alignment. 
- **Real-Time Intelligence:** Unlike static AI models that rely on training data cut-offs, Truth Mirror pulls live, real-time reports from the web.
- **Narrative Tracking:** The system remembers past claims, allowing it to detect orchestrated narrative campaigns or claims that mutate over time.
