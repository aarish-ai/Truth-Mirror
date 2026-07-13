# Truth Mirror — Geopolitical Intelligence Engine v2.4

**Note: This is an ongoing project. The underlying technologies, models, and architecture described below may evolve as the project scales.**

## 1. Problem
In the modern information landscape, individuals are constantly exposed to news from countless sources. Sorting fact from fiction is increasingly difficult. Some sources provide verified facts, some share half-truths, and others propagate outright lies or heavily biased narratives. 

Truth Mirror solves this problem by acting as a transparent, automated intelligence engine. When provided with a geopolitical claim, it doesn't just return a binary "True" or "False." Instead, it gathers global sources, analyzes where disputes lie, maps which channels are pushing which narratives, and uncovers the underlying story behind the mainstream headlines. This allows users to see the full, multi-perspective picture of global events.

## 2. Overview
Truth Mirror takes a hybrid multi-agent approach to fact-checking and narrative analysis. We leverage a pipeline that routes tasks intelligently across different API providers to maximize speed, quality, and rate limits. High-volume structural tasks (like decomposing claims, generating search queries, and batch analyzing sources) are routed to Groq. Heavy synthesis and deep reasoning are handled by Google Gemini. The engine retrieves live data from academic, news, and encyclopedia sources, categorizes the evidence by geopolitical perspective, and then synthesizes a comprehensive dashboard detailing the veracity of the claim, the core dispute, and the underlying geopolitical story.

## 3. Tech Stack
Our architecture relies on the following technologies:

- **Frontend UI**: Built with pure HTML, CSS, and Vanilla JavaScript for a lightweight, fast, and responsive user experience. We utilize dark mode aesthetics and dynamic layout panels.
- **Backend Server**: Python-based lightweight `BaseHTTPRequestHandler` acting as a REST API to serve the UI and orchestrate the pipeline.
- **High-Volume AI (Groq)**: We use Groq's lightning-fast inference for `llama-3.3-70b-versatile` to handle structural tasks: classifying whether a claim is geopolitical, extracting temporal intent from claims, decomposing complex claims into sub-claims, generating targeted search queries, and batch-analyzing sources.
- **Deep Synthesis AI (Google Gemini)**: We utilize `gemini-3.5-flash` to perform the heavy lifting: synthesizing evidence, detecting narrative divergence, and writing the final geopolitical story. A custom key-rotator intelligently cycles through a pool of API keys to gracefully manage rate limits.
- **Tertiary Fallback (OpenRouter)**: To ensure absolute high availability, if both Groq and Gemini face rate limits or high load, the system automatically falls back to `qwen/qwen3-next-80b-a3b-instruct:free` via the OpenRouter API.
- **Retrieval Sources**: Live data is pulled in parallel using custom Python connectors for Wikipedia, Wikinews, ArXiv, Crossref, Semantic Scholar, PubMed, Google News RSS, and Non-Western Media outlets (Al Jazeera, TASS, CGTN).

## 4. Example
Consider the claim: **"US invaded Venezuela"**

1. **Classification (Groq)**: The model confirms this is a geopolitical claim involving the US and Venezuela.
2. **Decomposition (Groq)**: The claim is broken down into verifiable sub-claims to build a robust search profile.
3. **Retrieval**: The system queries global news and academic databases. It pulls recent articles, official state media statements, and international news reports, then pre-filters them to drop irrelevant noise.
4. **Source Analysis (Groq/Gemini)**: Evidence is batched and analyzed for specific stances, biases, and omissions.
5. **Perspective Tagging**: Evidence is mapped by perspective (e.g., Western Allied Media, State Media, Neutral International).
6. **Synthesis (Gemini)**: The data is sent to the reasoning engine. The model analyzes the evidence and returns a structured JSON result.
7. **Output**: The user sees the final dashboard. The verdict is generated along with confidence metrics. The "Story" section explains the current geopolitical tensions. The "Dispute Analysis" highlights the core disagreements. The "Source Perspective Map" shows how different global channels frame the conflict.

## 5. How to Setup

### Requirements
- Python 3.10+
- Valid API keys for Google Gemini, Groq, and OpenRouter.

### Installation
1. **Clone the repository** and navigate to the project root.
2. **Set up a virtual environment** (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: .\venv\Scripts\activate
   ```
3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Environment Variables**:
   Create a `.env` file in the root directory and add your API keys. You can provide multiple Gemini keys separated by commas to utilize the key-rotator:
   ```env
   GEMINI_API_KEYS=key1,key2,key3
   GROQ_API_KEY=your_groq_api_key_here
   OPENROUTER_API_KEY=your_openrouter_api_key_here
   ```

### Running the App
Start the backend server:
```bash
python app.py
```
Then, open your web browser and navigate to `http://localhost:8080` to access the Truth Mirror dashboard.

## 6. Other Notes
- The system incorporates aggressive rate-limit protections, including sequential mini-batching and sleep intervals. Do not modify these unless you have upgraded to paid API tiers.
- The system heavily relies on structured JSON generation. If you experience parsing errors, ensure your API keys are valid and the models are responding correctly.
