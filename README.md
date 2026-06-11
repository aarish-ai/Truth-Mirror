# Truth Mirror — Geopolitical Intelligence Engine

**Note: This is an ongoing project. The underlying technologies, models, and architecture described below may evolve as the project scales.**

## 1. Problem
In the modern information landscape, individuals are constantly exposed to news from countless sources. Sorting fact from fiction is increasingly difficult. Some sources provide verified facts, some share half-truths, and others propagate outright lies or heavily biased narratives. 

Truth Mirror solves this problem by acting as a transparent, automated intelligence engine. When provided with a geopolitical claim, it doesn't just return a binary "True" or "False." Instead, it gathers global sources, analyzes where disputes lie, maps which channels are pushing which narratives, and uncovers the underlying story behind the mainstream headlines. This allows users to see the full, multi-perspective picture of global events.

## 2. Overview
Truth Mirror takes a hybrid multi-agent approach to fact-checking and narrative analysis. We leverage a pipeline that combines local, lightweight language models for fast, structural tasks (like decomposing claims and generating search queries) with a heavy, cloud-based LLM for complex synthesis and reasoning. The engine retrieves live data from academic, news, and encyclopedia sources, categorizes the evidence by geopolitical perspective, and then synthesizes a comprehensive dashboard detailing the veracity of the claim, the core dispute, and the underlying geopolitical story.

## 3. Tech Stack
Our architecture relies on the following technologies:

- **Frontend UI**: Built with pure HTML, CSS, and Vanilla JavaScript for a lightweight, fast, and responsive user experience. We utilize dark mode aesthetics and dynamic layout panels.
- **Backend Server**: Python-based lightweight `BaseHTTPRequestHandler` acting as a REST API to serve the UI and orchestrate the pipeline.
- **Local AI (Ollama)**: We use Ollama running the `qwen2.5:3b` model locally to handle structural tasks: classifying whether a claim is geopolitical, decomposing complex claims into sub-claims, and generating targeted search queries.
- **Cloud AI (Google Gemini)**: We utilize the `gemini-2.5-flash` model via the `google-genai` SDK to perform the heavy lifting: synthesizing evidence, detecting narrative divergence, and writing the final geopolitical story.
- **Fallback AI (OpenRouter)**: To ensure high availability, if Gemini faces rate limits or high load, the system automatically falls back to the `nvidia/nemotron-3-ultra-550b-a55b:free` model via the OpenRouter API.
- **Retrieval Sources**: Live data is pulled in parallel using custom Python connectors for Wikipedia, Wikinews, ArXiv, Crossref, Semantic Scholar, PubMed, NewsRSS, and Fact-Checking databases.

## 4. Example
Consider the claim: **"The US is in an ongoing war with Iran."**

1. **Classification**: The local Ollama model confirms this is a geopolitical claim involving the US and Iran.
2. **Decomposition**: The claim is broken down into verifiable sub-claims (e.g., "The US has officially declared war on Iran," "There are ongoing active military hostilities between the US and Iran").
3. **Retrieval**: The system queries global news and academic databases. It pulls recent articles, official state media statements, and international news reports.
4. **Perspective Tagging**: Evidence is tagged by perspective (e.g., Western Allied Media, State Media, Neutral International).
5. **Synthesis**: The data is sent to Gemini (or Nemotron). The model analyzes the evidence and returns a structured JSON result.
6. **Output**: The user sees the final dashboard. The verdict might be "Unclear" or "Disputed." The "Story" section explains the current geopolitical tensions, proxy conflicts, and background. The "Dispute Analysis" highlights that while there are proxy conflicts, no official war is ongoing. The "Source Perspective Map" shows how different global channels frame the conflict.

## 5. How to Setup

### Requirements
- Python 3.10+
- [Ollama](https://ollama.ai/) installed locally with the `qwen2.5:3b` model downloaded (`ollama run qwen2.5:3b`).
- Valid API keys for Google Gemini and OpenRouter.

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
   Create a `.env` file in the root directory and add your API keys:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   OPENROUTER_API_KEY=your_openrouter_api_key_here
   ```

### Running the App
Start the backend server:
```bash
python app.py
```
Then, open your web browser and navigate to `http://localhost:8080` to access the Truth Mirror dashboard.

## 6. Other Notes
- Ensure Ollama is running in the background before starting the Python server.
- The system heavily relies on structured JSON generation. If you experience parsing errors, ensure your API keys are valid and the models are responding correctly.
- Future updates may include integration with vector databases for historical claim caching and expanded perspective tagging capabilities.
