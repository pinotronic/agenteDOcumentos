"""
Agente analizador de código especializado.
LLM dedicado a analizar archivos individuales en profundidad.
"""
import env_loader  # Cargar .env PRIMERO
import json
from typing import Dict, Any
from openai import OpenAI

from config import ANALYZER_MODEL, ANALYZER_SYSTEM_PROMPT, MAX_TOKENS_PER_FILE


class CodeAnalyzer:
    """LLM especializado en análisis profundo de código y documentación."""
    
    def __init__(self, model: str = ANALYZER_MODEL):
        """
        Inicializa el analizador de código.
        
        Args:
            model: Modelo de OpenAI a usar para análisis
        """
        self.model = model
        self.client = OpenAI()
        self.system_prompt = ANALYZER_SYSTEM_PROMPT
    
    def _estimate_tokens(self, text: str) -> int:
        """Estima el número de tokens en un texto (aproximado)."""
        # Aproximación: 1 token ≈ 4 caracteres
        return len(text) // 4
    
    def analyze_file(self, file_path: str, content: str, file_type: str) -> Dict[str, Any]:
        """
        Analiza un archivo de código o documentación.
        
        Args:
            file_path: Ruta del archivo
            content: Contenido del archivo
            file_type: Tipo de archivo (python, javascript, etc.)
            
        Returns:
            Análisis estructurado en formato JSON
        """
        print(f"🔍 Analizando: {file_path}")
        
        # Verificar tamaño
        tokens = self._estimate_tokens(content)
        if tokens > MAX_TOKENS_PER_FILE:
            print(f"⚠️ Archivo muy grande ({tokens} tokens). Tomando primeras líneas...")
            # Tomar aproximadamente la mitad del límite
            content = content[:MAX_TOKENS_PER_FILE * 2]  # 2 chars ≈ 1 token
        
        # Preparar prompt de análisis
        user_prompt = f"""Analiza el siguiente archivo de código/documentación:

**Ruta del archivo:** {file_path}
**Tipo de archivo:** {file_type}

**Contenido:**
```{file_type}
{content}
```

Proporciona un análisis completo en formato JSON siguiendo la estructura especificada en tu prompt del sistema.
"""
        
        try:
            # Llamar al LLM analizador
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,  # Baja temperatura para análisis consistente
                response_format={"type": "json_object"}  # Forzar respuesta JSON
            )
            
            # Extraer y parsear respuesta
            analysis_text = response.choices[0].message.content
            analysis = json.loads(analysis_text)
            
            # Agregar metadata adicional
            analysis["file_path"] = file_path
            analysis["tokens_analyzed"] = tokens
            
            print(f"✅ Análisis completado: {file_path}")
            return analysis
            
        except json.JSONDecodeError as e:
            print(f"❌ Error parseando JSON del análisis: {e}")
            # Retornar análisis básico de fallback
            return {
                "file_path": file_path,
                "file_type": file_type,
                "summary": "Error: No se pudo parsear el análisis",
                "error": str(e),
                "raw_response": analysis_text if 'analysis_text' in locals() else None
            }
        
        except Exception as e:
            print(f"❌ Error analizando archivo: {e}")
            return {
                "file_path": file_path,
                "file_type": file_type,
                "summary": f"Error durante el análisis: {str(e)}",
                "error": str(e)
            }
    
    def analyze_batch(self, files: list[tuple[str, str, str]]) -> list[Dict[str, Any]]:
        """
        Analiza múltiples archivos en lote.
        
        Args:
            files: Lista de tuplas (file_path, content, file_type)
            
        Returns:
            Lista de análisis
        """
        results = []
        total = len(files)
        
        for idx, (file_path, content, file_type) in enumerate(files, 1):
            print(f"\n📊 Progreso: {idx}/{total}")
            analysis = self.analyze_file(file_path, content, file_type)
            results.append(analysis)
        
        return results
    
    def quick_summary(self, file_path: str, content: str, file_type: str) -> str:
        """
        Genera un resumen rápido sin estructura JSON completa.
        
        Args:
            file_path: Ruta del archivo
            content: Contenido del archivo
            file_type: Tipo de archivo
            
        Returns:
            Resumen en texto plano
        """
        prompt = f"""Resume brevemente (2-3 oraciones) qué hace este archivo:

**Archivo:** {file_path}
**Tipo:** {file_type}

```{file_type}
{content[:5000]}
```

Responde solo con el resumen, sin formato adicional."""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Modelo más rápido para resúmenes
                messages=[
                    {"role": "system", "content": "Eres un experto en análisis de código. Proporciona resúmenes concisos y precisos."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=200
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            return f"Error generando resumen: {str(e)}"
