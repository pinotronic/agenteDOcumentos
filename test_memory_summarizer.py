import unittest
from unittest.mock import Mock, patch

from memory_summarizer import MemorySummarizer


class MemorySummarizerTests(unittest.TestCase):
    def test_summarizer_returns_compact_memory_from_ollama(self):
        summarizer = MemorySummarizer(
            enabled=True,
            base_url="http://localhost:11434",
            model="qwen-test",
            timeout=0.2,
        )

        get_response = Mock()
        get_response.raise_for_status.return_value = None

        post_response = Mock()
        post_response.raise_for_status.return_value = None
        post_response.json.return_value = {
            "response": "MEMORIA COMPACTA:\n- Objetivo actual: revisar el agente\n- Restricciones: contexto corto"
        }

        with patch("memory_summarizer.requests.get", return_value=get_response), patch(
            "memory_summarizer.requests.post", return_value=post_response
        ):
            summary = summarizer.summarize_memory(
                user_query="revisa agent.py",
                facts_summary="INFORMACION CONOCIDA DEL USUARIO:\n- Prefiere cambios minimos",
                similar_messages=[{"content": "Ya revisamos agent.py", "relevance": 0.9, "role": "assistant"}],
                max_chars=500,
            )

        self.assertTrue(summary.startswith("MEMORIA COMPACTA:"))

    def test_summarizer_returns_none_when_ollama_is_unavailable(self):
        summarizer = MemorySummarizer(enabled=True, timeout=0.2)

        with patch("memory_summarizer.requests.get", side_effect=RuntimeError("down")):
            summary = summarizer.summarize_memory(
                user_query="revisa agent.py",
                facts_summary="",
                similar_messages=[{"content": "contexto", "relevance": 0.8, "role": "assistant"}],
                max_chars=200,
            )

        self.assertIsNone(summary)


if __name__ == "__main__":
    unittest.main()