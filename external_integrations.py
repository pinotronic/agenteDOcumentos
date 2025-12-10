"""
Integraciones con APIs externas.
Búsqueda en StackOverflow y documentación de APIs.
"""
import env_loader  # Cargar .env PRIMERO
import json
import requests
from typing import Dict, Any
from openai import OpenAI

from config import ORCHESTRATOR_MODEL


class ExternalIntegrations:
    """Integración con APIs y servicios externos."""
    
    def __init__(self):
        self.client = OpenAI()
        self.model = ORCHESTRATOR_MODEL
    
    def search_stackoverflow(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """
        Busca en StackOverflow usando la API y resume con LLM.
        
        Args:
            query: Consulta de búsqueda
            max_results: Número máximo de resultados
            
        Returns:
            Resultados resumidos
        """
        print(f"🔍 Buscando en StackOverflow: {query}")
        
        try:
            # API de StackOverflow
            url = "https://api.stackexchange.com/2.3/search/advanced"
            params = {
                "order": "desc",
                "sort": "relevance",
                "q": query,
                "accepted": "True",  # Solo preguntas con respuesta aceptada
                "site": "stackoverflow",
                "pagesize": max_results
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if not data.get("items"):
                return {
                    "query": query,
                    "results": [],
                    "message": "No se encontraron resultados"
                }
            
            # Resumir con LLM
            items_summary = json.dumps(data["items"][:max_results], indent=2)
            
            prompt = f"""Resume los siguientes resultados de StackOverflow para la consulta: "{query}"

{items_summary}

Proporciona un resumen útil con los puntos clave y enlaces.

Responde en formato JSON:
{{
  "summary": "Resumen general",
  "top_solutions": [
    {{
      "title": "Título",
      "link": "URL",
      "score": puntos,
      "solution": "Resumen de la solución"
    }}
  ],
  "key_points": ["punto1", "punto2"]
}}
"""
            
            llm_response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Eres un experto en resumir soluciones técnicas de StackOverflow."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(llm_response.choices[0].message.content)
            result["query"] = query
            result["total_results"] = len(data["items"])
            result["success"] = True
            
            print(f"✅ {len(result['top_solutions'])} soluciones encontradas")
            return result
        
        except requests.exceptions.RequestException as e:
            return {"error": f"Error de conexión: {str(e)}"}
        except Exception as e:
            return {"error": str(e)}
    
    def fetch_api_docs(self, package_name: str, language: str = "python") -> Dict[str, Any]:
        """
        Obtiene documentación de una API o paquete usando LLM.
        
        Args:
            package_name: Nombre del paquete/API
            language: Lenguaje de programación
            
        Returns:
            Documentación resumida
        """
        print(f"📚 Obteniendo documentación de: {package_name} ({language})")
        
        prompt = f"""Proporciona documentación completa y ejemplos de uso para {package_name} en {language}:

Incluye:
1. Descripción general
2. Instalación
3. Conceptos principales
4. Ejemplos de código común
5. APIs/funciones principales
6. Best practices
7. Enlaces oficiales

Responde en formato JSON:
{{
  "package": "{package_name}",
  "description": "Descripción",
  "installation": "Comando de instalación",
  "main_concepts": ["concepto1", "concepto2"],
  "examples": [
    {{
      "title": "Ejemplo 1",
      "code": "código de ejemplo",
      "explanation": "explicación"
    }}
  ],
  "main_apis": [
    {{
      "name": "función/clase",
      "signature": "firma",
      "description": "qué hace"
    }}
  ],
  "best_practices": ["práctica1"],
  "official_docs": "URL si existe"
}}
"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": f"Eres un experto en documentación de APIs y paquetes de {language}. Proporcionas información precisa y actualizada."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            result["language"] = language
            result["success"] = True
            
            print(f"✅ Documentación obtenida para {package_name}")
            return result
        
        except Exception as e:
            return {"error": str(e)}
