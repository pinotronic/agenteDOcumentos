"""
Asistente interactivo de código.
Explica código, asiste en depuración y realiza code reviews.
"""
import env_loader  # Cargar .env PRIMERO
import json
from pathlib import Path
from typing import Dict, Any
from openai import OpenAI

from config import ANALYZER_MODEL


class CodeAssistant:
    """Asistente interactivo para explicar y revisar código."""
    
    def __init__(self):
        self.client = OpenAI()
        self.model = ANALYZER_MODEL
    
    def explain_code(self, code_snippet: str, level: str = "intermediate") -> Dict[str, Any]:
        """
        Explica qué hace un fragmento de código.
        
        Args:
            code_snippet: Fragmento de código o ruta de archivo
            level: Nivel de explicación (beginner, intermediate, expert)
            
        Returns:
            Explicación detallada
        """
        print(f"💬 Explicando código (nivel: {level})")
        
        # Si es una ruta, leer el archivo
        if len(code_snippet) < 500 and Path(code_snippet).exists():
            with open(code_snippet, 'r', encoding='utf-8') as f:
                code_snippet = f.read()
        
        level_prompts = {
            "beginner": "Explica como si fuera para alguien nuevo en programación",
            "intermediate": "Explica con detalle técnico moderado",
            "expert": "Explica con profundidad técnica y detalles de implementación"
        }
        
        prompt = f"""{level_prompts.get(level, level_prompts['intermediate'])}.

Código:
```
{code_snippet}
```

Proporciona:
1. Resumen de qué hace
2. Explicación línea por línea o por sección
3. Conceptos clave utilizados
4. Posibles mejoras
5. Casos de uso

Responde en formato JSON:
{{
  "summary": "Resumen breve",
  "detailed_explanation": "Explicación detallada",
  "key_concepts": ["concepto1", "concepto2"],
  "improvements": ["mejora1", "mejora2"],
  "use_cases": ["caso1", "caso2"]
}}
"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": f"Eres un profesor de programación experto. Explicas código de forma clara y adaptada al nivel {level}."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            result["level"] = level
            result["success"] = True
            
            print("✅ Explicación generada")
            return result
        
        except Exception as e:
            return {"error": str(e)}
    
    def debug_assistant(self, code: str, error_message: str = None) -> Dict[str, Any]:
        """
        Ayuda a debuggear código y encontrar errores.
        
        Args:
            code: Código con problemas
            error_message: Mensaje de error opcional
            
        Returns:
            Análisis y soluciones
        """
        print("🐛 Analizando código para debugging")
        
        prompt = f"""Analiza este código y ayuda a identificar y solucionar problemas:

**Código:**
```
{code}
```

**Mensaje de error (si existe):**
{error_message or "No se proporcionó mensaje de error"}

Proporciona:
1. Identificación del problema
2. Causa raíz
3. Solución paso a paso
4. Código corregido
5. Prevención futura

Responde en formato JSON:
{{
  "problem_identified": "Descripción del problema",
  "root_cause": "Causa raíz",
  "solution_steps": ["paso1", "paso2"],
  "fixed_code": "código corregido",
  "prevention": "Cómo evitar en el futuro",
  "related_issues": ["issue1", "issue2"]
}}
"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Eres un experto en debugging. Identificas problemas rápidamente y proporcionas soluciones claras."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            result["success"] = True
            
            print("✅ Análisis de debugging completado")
            return result
        
        except Exception as e:
            return {"error": str(e)}
    
    def code_review(self, file_path: str) -> Dict[str, Any]:
        """
        Realiza code review como un senior developer.
        
        Args:
            file_path: Ruta del archivo a revisar
            
        Returns:
            Review completo con sugerencias
        """
        print(f"🔍 Realizando code review de: {file_path}")
        
        try:
            path = Path(file_path)
            
            if not path.exists():
                return {"error": f"Archivo no encontrado: {file_path}"}
            
            with open(path, 'r', encoding='utf-8') as f:
                code = f.read()
            
            prompt = f"""Realiza un code review profesional de este archivo como un senior developer:

**Archivo:** {path.name}

```
{code}
```

Evalúa:
1. Calidad del código
2. Mejores prácticas
3. Rendimiento
4. Seguridad
5. Mantenibilidad
6. Testing

Responde en formato JSON:
{{
  "overall_rating": "excellent|good|needs_improvement|poor",
  "strengths": ["punto fuerte 1", "punto fuerte 2"],
  "issues": [
    {{
      "severity": "critical|major|minor",
      "line": número_de_línea,
      "issue": "descripción",
      "suggestion": "cómo arreglarlo"
    }}
  ],
  "best_practices": "Evaluación de mejores prácticas",
  "security_concerns": ["preocupación1"],
  "performance_notes": "Notas de rendimiento",
  "refactoring_suggestions": ["sugerencia1"],
  "summary": "Resumen del review"
}}
"""
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Eres un senior software engineer con 15 años de experiencia. Realizas code reviews constructivos y detallados."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            result["file_reviewed"] = str(path)
            result["success"] = True
            
            print(f"✅ Code review completado: {result['overall_rating']}")
            return result
        
        except Exception as e:
            return {"error": str(e)}
