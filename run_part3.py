import asyncio
import time
from truth_mirror.geo_orchestrator import GeopoliticalPipeline
from truth_mirror.run_tracker import tracker

claims = [
    "The UAE is covertly funding the RSF in Sudan while publicly calling for peace.",
    "France is sending nuclear weapons to Ukraine.",
    "China's economic growth slowed to 4.7% in Q2 2024.",
    "The US lifted sanctions on Venezuela's oil sector in late 2025",
    "Imran Khan is the current Prime Minister of Pakistan",
    "Iran has suspended uranium enrichment following the 2026 war",
    "The ICC arrest warrant for Vladimir Putin is still active",
    "US troops have fully withdrawn from Syria",
    "The Houthi movement in Yemen is still attacking Red Sea shipping in 2026",
    "Turkey has formally applied for or joined BRICS",
    "India and Pakistan reached a permanent ceasefire after the May 2025 conflict",
    "Benjamin Netanyahu remains the Prime Minister of Israel in 2026",
    "Germany has restarted nuclear power generation",
    "The Wagner Group is operating in Mali and other West African countries under Russian state direction",
    "The United States has imposed new sanctions on Iran following the 2025-2026 military conflict"
]

async def run():
    pipeline = GeopoliticalPipeline()
    print('| Claim | Verdict | Confidence | Runtime | Models Used |')
    print('|---|---|---|---|---|')
    for claim in claims:
        start_time = time.time()
        res = await pipeline.run_async(claim)
        elapsed = time.time() - start_time
        summary = tracker.get_stage_summary()
        models_used = ', '.join([f'{e.get("stage")}: {e.get("model")}' for e in summary])
        conf = f'{res.confidence * 100:.1f}%' if res.confidence else 'N/A'
        print(f'| {claim} | {res.verdict} | {conf} | {elapsed:.1f}s | {models_used} |', flush=True)

asyncio.run(run())

