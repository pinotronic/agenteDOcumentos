"""
Resumidor de memoria para comprimir contexto antes de inyectarlo al prompt.
Usa un LLM local via Ollama cuando esta disponible y cae a fallback silencioso.
"""
import json
import subprocess
from typing import Dict, List, Optional

import requests

from config import (
    MEMORY_SUMMARIZER_BACKEND,
    MEMORY_SUMMARIZER_ENABLED,
    MEMORY_SUMMARIZER_MAX_INPUT_CHARS,
    MEMORY_SUMMARIZER_MAX_OUTPUT_CHARS,
    MEMORY_SUMMARIZER_OLLAMA_MODEL,
    MEMORY_SUMMARIZER_OLLAMA_TIMEOUT,
    MEMORY_SUMMARIZER_OLLAMA_URL,
)


class MemorySummarizer:
    """Compacta contexto recuperado para ventanas de contexto cortas."""

    def __init__(
        self,
        enabled: Optional[bool] = None,
        backend: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
        max_input_chars: Optional[int] = None,
        max_output_chars: Optional[int] = None,
    ):
        self.enabled = MEMORY_SUMMARIZER_ENABLED if enabled is None else enabled
        self.backend = (backend or MEMORY_SUMMARIZER_BACKEND).lower()
        self.base_url = (base_url or MEMORY_SUMMARIZER_OLLAMA_URL).rstrip("/")
        self.model = model or MEMORY_SUMMARIZER_OLLAMA_MODEL
        self.timeout = MEMORY_SUMMARIZER_OLLAMA_TIMEOUT if timeout is None else timeout
        self.max_input_chars = max_input_chars or MEMORY_SUMMARIZER_MAX_INPUT_CHARS
        self.max_output_chars = max_output_chars or MEMORY_SUMMARIZER_MAX_OUTPUT_CHARS
        self._availability_checked = False
        self._available = False

    def summarize_memory(
        self,
        user_query: Optional[str],
        facts_summary: str,
        similar_messages: List[Dict],
        max_chars: int,
    ) -> Optional[str]:
        """Resume hechos y mensajes recuperados en un bloque corto y estructurado."""
        if not self.enabled:
            return None

        if self.backend != "ollama":
            print(f"[MEMORIA] Backend de resumen no soportado: {self.backend}")
            return None

        if not facts_summary and not similar_messages:
            return None

        if not self._check_ollama_available():
            return None

        prompt = self._build_prompt(
            user_query=user_query or "",
            facts_summary=facts_summary,
            similar_messages=similar_messages,
            max_chars=min(max_chars, self.max_output_chars),
        )

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "think": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 220,
                    },
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            summary = self._normalize_summary(data.get("response", ""), max_chars)
            if summary:
                print(f"[MEMORIA] Resumen local generado con {self.model}")
                return summary
        except Exception as exc:
            print(f"[MEMORIA] No se pudo resumir con Ollama: {exc}")

        cli_summary = self._summarize_with_ollama_cli(prompt, max_chars)
        if cli_summary:
            print(f"[MEMORIA] Resumen local generado con CLI de Ollama usando {self.model}")
            return cli_summary

        return None

    def _summarize_with_ollama_cli(self, prompt: str, max_chars: int) -> Optional[str]:
        try:
            result = subprocess.run(
                ["ollama", "run", self.model, "--think", "false", "--hidethinking", prompt],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=max(self.timeout, 30),
                check=True,
            )
        except Exception as exc:
            print(f"[MEMORIA] Fallback CLI de Ollama no disponible: {exc}")
            return None

        return self._normalize_summary(result.stdout, max_chars)

    def _check_ollama_available(self) -> bool:
        if self._availability_checked:
            return self._available

        self._availability_checked = True
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=min(self.timeout, 1.5),
            )
            response.raise_for_status()
            self._available = True
            print(f"[MEMORIA] Ollama disponible en {self.base_url}")
        except Exception as exc:
            self._available = False
            print(f"[MEMORIA] Ollama no disponible, usando fallback local: {exc}")

        return self._available

    def _build_prompt(
        self,
        user_query: str,
        facts_summary: str,
        similar_messages: List[Dict],
        max_chars: int,
    ) -> str:
        messages = []
        current_chars = 0

        for msg in similar_messages:
            content = (msg.get("content", "") or "").strip().replace("\r", " ")
            if not content:
                continue

            snippet = content[:400]
            line = {
                "role": msg.get("role", "unknown"),
                "relevance": round(float(msg.get("relevance", 0)), 3),
                "timestamp": msg.get("timestamp", ""),
                "content": snippet,
            }
            encoded = json.dumps(line, ensure_ascii=False)
            if current_chars + len(encoded) > self.max_input_chars:
                break
            messages.append(line)
            current_chars += len(encoded)

        facts_block = (facts_summary or "")[: self.max_input_chars // 2]

        message_lines = []
        for msg in messages:
            line = f"- [{msg['relevance']}] {msg['content']}"
            message_lines.append(line)

        return f"""Resume memoria para un agente de codigo.
    No inventes nada. Usa solo lo relevante para la consulta actual.
    Maximo {max_chars} caracteres.

    Salida exacta:
    MEMORIA COMPACTA:
    - Objetivo actual: ...
    - Restricciones: ...
    - Hechos persistentes: ...
    - Contexto relevante: ...
    - Decisiones previas: ...
    - Siguientes pasos: ...

    Consulta: {user_query}
    Hechos: {facts_block if facts_block else 'Ninguno'}
    Mensajes:
    {chr(10).join(message_lines) if message_lines else '- Ninguno'}
    """

    def _normalize_summary(self, summary: str, max_chars: int) -> str:
        cleaned = (summary or "").strip()
        marker = "MEMORIA COMPACTA:"
        if marker in cleaned:
            cleaned = cleaned[cleaned.rfind(marker):]
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
        if not cleaned:
            return ""
        if len(cleaned) > max_chars:
            cleaned = cleaned[: max_chars - 3].rstrip() + "..."
        return cleaned