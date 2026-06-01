import os
import unittest
from unittest.mock import patch, MagicMock
import requests

from truth_mirror.agent import ReActAgent
from truth_mirror.llm_client import LLMClient
from truth_mirror.vector_store import VectorStore
from truth_mirror.orchestrator import TruthMirrorPipeline

class TestMarathon(unittest.TestCase):
    def test_vector_store_initialization(self):
        """Verify vector store (ChromaDB & sentence-transformers) can initialize and run."""
        vs = VectorStore(backend="faiss")
        self.assertIsNotNone(vs.encoder)
        
        vs.store("doc1", "This is a test document.", {"source": "test"})
        results = vs.search("test document", top_k=1)
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "doc1")
        
    @patch('truth_mirror.llm_client.requests.post')
    def test_llm_client_fallback(self, mock_post):
        """Test that LLMClient falls back to Gemini if Ollama is not running."""
        def side_effect_post(url, *args, **kwargs):
            if "localhost:11434" in url:
                raise requests.exceptions.ConnectionError("Ollama not running")
            else:
                response = MagicMock()
                response.raise_for_status = MagicMock()
                response.json.return_value = {
                    "candidates": [{"content": {"parts": [{"text": "Gemini fallback response"}]}}]
                }
                return response
                
        mock_post.side_effect = side_effect_post
        
        with patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key"}):
            client = LLMClient()
            response = client.complete("Test prompt")
            self.assertEqual(response, "Gemini fallback response")

    @patch.object(LLMClient, 'complete')
    def test_react_agent_loop(self, mock_complete):
        """Test the ReActAgent orchestration loop parsing Thought/Action/Final Answer."""
        mock_complete.side_effect = [
            "Thought: I need to use a tool\nAction: fake_tool\nAction Input: test input\n",
            "Thought: I know the answer\nFinal Answer: Test successful!"
        ]
        
        client = LLMClient()
        def fake_tool(x):
            """A fake tool for testing."""
            return f"Tool executed with {x}"
        
        tools = {"fake_tool": fake_tool}
        
        agent = ReActAgent(client, tools, max_iterations=3)
        result = agent.run("What is the test result?")
        
        self.assertEqual(result, "Test successful!")
        self.assertEqual(mock_complete.call_count, 2)

    @patch('truth_mirror.vector_store.chromadb.PersistentClient')
    def test_orchestrator_initialization(self, mock_chroma):
        """Test that the TruthMirrorPipeline can initialize without errors."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key"}):
            pipeline = TruthMirrorPipeline()
            self.assertIsNotNone(pipeline.llm_client)
            self.assertIsNotNone(pipeline.retriever)

if __name__ == "__main__":
    unittest.main()
