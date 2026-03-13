"""
Agente especializado en generación de código.
Genera código funcional en múltiples lenguajes basado en especificaciones.
"""
import env_loader  # Cargar .env PRIMERO
import os
import json
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
from openai import OpenAI
from pathlib import Path


class CodeGeneratorAgent:
    """
    Agente especializado en generación de código multi-lenguaje.

    Capacidades:
    - Generación de funciones, clases y módulos
    - Generación de APIs y endpoints REST
    - Generación de operaciones CRUD completas
    - Soporte multi-lenguaje (Python, JS/TS, PHP, Java, Go, etc.)
    """

    # Modelos para diferentes tareas
    GENERATION_MODEL = "gpt-4o"  # Mejor calidad para generación
    QUICK_MODEL = "gpt-4o-mini"  # Para tareas simples

    # Templates de estructura por lenguaje
    LANGUAGE_TEMPLATES = {
        "python": {
            "extension": ".py",
            "class_template": "class {name}:\n    \"\"\"Docstring.\"\"\"\n    pass",
            "function_template": "def {name}({params}):\n    \"\"\"Docstring.\"\"\"\n    pass",
            "import_style": "from {module} import {name}",
            "frameworks": ["fastapi", "django", "flask", "pytest"],
        },
        "javascript": {
            "extension": ".js",
            "class_template": "class {name} {{\n  constructor() {{}}\n}}",
            "function_template": "function {name}({params}) {{\n  // TODO\n}}",
            "import_style": "import {{ {name} }} from '{module}';",
            "frameworks": ["express", "react", "node", "jest"],
        },
        "typescript": {
            "extension": ".ts",
            "class_template": "class {name} {{\n  constructor() {{}}\n}}",
            "function_template": "function {name}({params}): ReturnType {{\n  // TODO\n}}",
            "import_style": "import {{ {name} }} from '{module}';",
            "frameworks": ["express", "react", "nestjs", "jest"],
        },
        "php": {
            "extension": ".php",
            "class_template": "<?php\nclass {name} {{\n    public function __construct() {{}}\n}}",
            "function_template": "function {name}({params}) {{\n    // TODO\n}}",
            "import_style": "use {module}\\{name};",
            "frameworks": ["laravel", "symfony", "slim"],
        },
        "java": {
            "extension": ".java",
            "class_template": "public class {name} {{\n    public {name}() {{}}\n}}",
            "function_template": "public ReturnType {name}({params}) {{\n    // TODO\n}}",
            "import_style": "import {module}.{name};",
            "frameworks": ["spring", "quarkus"],
        },
        "go": {
            "extension": ".go",
            "class_template": "type {name} struct {{\n}}\n\nfunc New{name}() *{name} {{\n    return &{name}{{}}\n}}",
            "function_template": "func {name}({params}) error {{\n    // TODO\n    return nil\n}}",
            "import_style": "import \"{module}\"",
            "frameworks": ["gin", "echo", "fiber"],
        },
    }

    # Prompts del sistema por tipo de generación
    SYSTEM_PROMPTS = {
        "general": """Eres un experto generador de código. Tu tarea es generar código limpio,
bien documentado y siguiendo las mejores prácticas del lenguaje especificado.

REGLAS:
1. Genera SOLO el código solicitado, sin explicaciones adicionales
2. Incluye docstrings/comentarios apropiados
3. Sigue convenciones de nombrado del lenguaje (snake_case para Python, camelCase para JS, etc.)
4. Incluye type hints cuando el lenguaje lo soporte
5. Maneja errores apropiadamente
6. El código debe ser funcional y listo para usar

Responde SOLO con el código en formato:
```{language}
<código aquí>
```""",

        "api": """Eres un experto en diseño de APIs REST. Genera endpoints siguiendo mejores prácticas:

REGLAS:
1. Usa verbos HTTP correctos (GET, POST, PUT, DELETE, PATCH)
2. Implementa validación de entrada
3. Retorna códigos de estado HTTP apropiados
4. Incluye manejo de errores
5. Documenta con OpenAPI/Swagger cuando sea posible
6. Implementa autenticación si se solicita
7. Sigue principios RESTful

Responde SOLO con el código en formato:
```{language}
<código aquí>
```""",

        "crud": """Eres un experto en arquitectura de software. Genera operaciones CRUD completas:

REGLAS:
1. Crea modelo/entidad con validaciones
2. Implementa repositorio/DAO con todas las operaciones
3. Crea servicio/controlador con lógica de negocio
4. Incluye DTOs si el lenguaje lo requiere
5. Implementa paginación para listados
6. Maneja errores y excepciones
7. Incluye soft-delete si es apropiado

Genera código organizado en secciones claras:
# === MODELO ===
# === REPOSITORIO ===
# === SERVICIO ===
# === CONTROLADOR/RUTAS ===

Responde SOLO con el código en formato:
```{language}
<código aquí>
```""",

        "refactor": """Eres un experto en refactorización de código. Tu tarea es mejorar código existente:

REGLAS:
1. Mantén la funcionalidad original
2. Mejora legibilidad y mantenibilidad
3. Aplica principios SOLID cuando sea apropiado
4. Elimina código duplicado
5. Mejora nombres de variables/funciones
6. Añade type hints si faltan
7. Optimiza rendimiento si es posible sin complicar

Responde con el código refactorizado en formato:
```{language}
<código aquí>
```

Y un breve resumen de cambios:
## Cambios realizados:
- ...
"""
    }

    def __init__(self):
        """Inicializa el agente generador de código."""
        self.client = OpenAI()
        self.generation_history = []
        print("[CODE-GENERATOR] Agente inicializado")

    def _detect_language(self, context: str = None, file_path: str = None) -> str:
        """Detecta el lenguaje basándose en contexto o extensión de archivo."""
        if file_path:
            ext = Path(file_path).suffix.lower()
            ext_map = {
                ".py": "python",
                ".js": "javascript",
                ".ts": "typescript",
                ".tsx": "typescript",
                ".jsx": "javascript",
                ".php": "php",
                ".java": "java",
                ".go": "go",
                ".rb": "ruby",
                ".rs": "rust",
                ".cs": "csharp",
            }
            if ext in ext_map:
                return ext_map[ext]

        if context:
            context_lower = context.lower()
            if any(kw in context_lower for kw in ["python", "django", "flask", "fastapi", "pytest"]):
                return "python"
            elif any(kw in context_lower for kw in ["typescript", "tsx", "nestjs"]):
                return "typescript"
            elif any(kw in context_lower for kw in ["javascript", "react", "node", "express", "jsx"]):
                return "javascript"
            elif any(kw in context_lower for kw in ["php", "laravel", "symfony"]):
                return "php"
            elif any(kw in context_lower for kw in ["java", "spring", "quarkus"]):
                return "java"
            elif any(kw in context_lower for kw in ["golang", " go ", "gin", "fiber"]):
                return "go"

        return "python"  # Default

    def _extract_code_from_response(self, response: str, language: str) -> str:
        """Extrae el código de la respuesta del LLM."""
        # Buscar bloques de código con el lenguaje especificado
        patterns = [
            rf"```{language}\n(.*?)```",
            rf"```{language.lower()}\n(.*?)```",
            r"```\n(.*?)```",
            r"```(.*?)```",
        ]

        for pattern in patterns:
            match = re.search(pattern, response, re.DOTALL)
            if match:
                return match.group(1).strip()

        # Si no hay bloques de código, retornar la respuesta limpia
        return response.strip()

    def _validate_syntax(self, code: str, language: str) -> Dict[str, Any]:
        """Valida la sintaxis del código generado."""
        result = {"valid": True, "errors": []}

        if language == "python":
            try:
                compile(code, "<string>", "exec")
            except SyntaxError as e:
                result["valid"] = False
                result["errors"].append(f"Línea {e.lineno}: {e.msg}")

        elif language in ["javascript", "typescript"]:
            # Validación básica de balance de llaves
            if code.count("{") != code.count("}"):
                result["valid"] = False
                result["errors"].append("Llaves desbalanceadas")
            if code.count("(") != code.count(")"):
                result["valid"] = False
                result["errors"].append("Paréntesis desbalanceados")

        return result

    def generate_code(
        self,
        specification: str,
        language: str = None,
        generation_type: str = "general",
        context_files: List[str] = None,
        output_file: str = None,
        framework: str = None
    ) -> Dict[str, Any]:
        """
        Genera código basado en especificación en lenguaje natural.

        Args:
            specification: Descripción de lo que se quiere generar
            language: Lenguaje objetivo (auto-detecta si None)
            generation_type: general|api|crud|refactor
            context_files: Archivos de contexto para mantener consistencia
            output_file: Archivo donde guardar el código (opcional)
            framework: Framework específico a usar (fastapi, express, etc.)

        Returns:
            Dict con código generado, metadata y validación
        """
        print(f"\n[CODE-GENERATOR] Generando código: {generation_type}")
        print(f"   Especificación: {specification[:100]}...")

        # Detectar lenguaje
        detected_lang = language or self._detect_language(specification, output_file)
        print(f"   Lenguaje: {detected_lang}")

        # Construir contexto adicional
        context_content = ""
        if context_files:
            for file_path in context_files[:3]:  # Máximo 3 archivos de contexto
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()[:5000]  # Máximo 5000 chars por archivo
                        context_content += f"\n\n--- Contexto de {Path(file_path).name} ---\n{content}"
                except Exception as e:
                    print(f"   [WARN] No se pudo leer {file_path}: {e}")

        # Construir prompt
        system_prompt = self.SYSTEM_PROMPTS.get(generation_type, self.SYSTEM_PROMPTS["general"])
        system_prompt = system_prompt.replace("{language}", detected_lang)

        user_prompt = f"""ESPECIFICACIÓN:
{specification}

LENGUAJE: {detected_lang}
"""

        if framework:
            user_prompt += f"FRAMEWORK: {framework}\n"

        if context_content:
            user_prompt += f"\nCONTEXTO DEL PROYECTO:{context_content}\n"

        user_prompt += "\nGenera el código siguiendo las instrucciones."

        try:
            # Llamar al LLM
            response = self.client.chat.completions.create(
                model=self.GENERATION_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,  # Baja para código consistente
                max_tokens=4000
            )

            raw_response = response.choices[0].message.content
            generated_code = self._extract_code_from_response(raw_response, detected_lang)

            # Validar sintaxis
            validation = self._validate_syntax(generated_code, detected_lang)

            # Guardar en archivo si se especificó
            saved_to = None
            if output_file and validation["valid"]:
                try:
                    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(generated_code)
                    saved_to = output_file
                    print(f"   Guardado en: {output_file}")
                except Exception as e:
                    print(f"   [ERROR] No se pudo guardar: {e}")

            # Registrar en historial
            self.generation_history.append({
                "timestamp": datetime.now().isoformat(),
                "type": generation_type,
                "language": detected_lang,
                "specification": specification[:200],
                "lines_generated": len(generated_code.split("\n")),
                "valid": validation["valid"]
            })

            result = {
                "success": True,
                "code": generated_code,
                "language": detected_lang,
                "generation_type": generation_type,
                "framework": framework,
                "validation": validation,
                "saved_to": saved_to,
                "stats": {
                    "lines": len(generated_code.split("\n")),
                    "characters": len(generated_code),
                    "tokens_used": response.usage.total_tokens
                }
            }

            print(f"   Generado: {result['stats']['lines']} líneas")
            print(f"   Validación: {'OK' if validation['valid'] else 'ERRORES: ' + str(validation['errors'])}")

            return result

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "language": detected_lang,
                "generation_type": generation_type
            }

    def generate_api_endpoint(
        self,
        endpoint_spec: str,
        method: str = "GET",
        language: str = None,
        framework: str = None,
        include_tests: bool = False,
        output_file: str = None
    ) -> Dict[str, Any]:
        """
        Genera un endpoint de API REST completo.

        Args:
            endpoint_spec: Descripción del endpoint (ej: "endpoint para listar usuarios con paginación")
            method: HTTP method (GET, POST, PUT, DELETE, PATCH)
            language: Lenguaje (auto-detecta si None)
            framework: Framework (fastapi, express, laravel, spring, gin)
            include_tests: Si debe incluir tests del endpoint
            output_file: Archivo de salida

        Returns:
            Dict con código del endpoint
        """
        # Inferir framework si no se especifica
        detected_lang = language or self._detect_language(endpoint_spec)
        if not framework:
            framework_defaults = {
                "python": "fastapi",
                "javascript": "express",
                "typescript": "express",
                "php": "laravel",
                "java": "spring",
                "go": "gin"
            }
            framework = framework_defaults.get(detected_lang, "")

        spec = f"""Genera un endpoint {method} para: {endpoint_spec}

Framework: {framework}
Requisitos:
- Validación de entrada
- Manejo de errores con códigos HTTP apropiados
- Documentación del endpoint
- Tipado completo
"""

        if include_tests:
            spec += "- Incluye tests unitarios para el endpoint\n"

        return self.generate_code(
            specification=spec,
            language=detected_lang,
            generation_type="api",
            framework=framework,
            output_file=output_file
        )

    def generate_crud(
        self,
        entity_name: str,
        fields: Dict[str, str],
        language: str = None,
        framework: str = None,
        include_soft_delete: bool = True,
        include_pagination: bool = True,
        output_dir: str = None
    ) -> Dict[str, Any]:
        """
        Genera operaciones CRUD completas para una entidad.

        Args:
            entity_name: Nombre de la entidad (ej: "User", "Product")
            fields: Diccionario de campos {nombre: tipo} (ej: {"name": "string", "age": "int"})
            language: Lenguaje objetivo
            framework: Framework a usar
            include_soft_delete: Incluir borrado lógico
            include_pagination: Incluir paginación en listados
            output_dir: Directorio para guardar archivos

        Returns:
            Dict con código CRUD completo
        """
        detected_lang = language or self._detect_language(f"{framework or ''} crud")

        # Formatear campos para el prompt
        fields_desc = "\n".join([f"  - {name}: {ftype}" for name, ftype in fields.items()])

        spec = f"""Genera CRUD completo para la entidad '{entity_name}' con los siguientes campos:
{fields_desc}

Requisitos:
- Modelo/Entidad con validaciones
- Repositorio/DAO con operaciones: create, get_by_id, get_all, update, delete
- Servicio con lógica de negocio
- Controlador/Rutas REST para cada operación
"""

        if include_soft_delete:
            spec += "- Implementa soft-delete (campo deleted_at)\n"

        if include_pagination:
            spec += "- Implementa paginación en get_all (page, limit, total)\n"

        result = self.generate_code(
            specification=spec,
            language=detected_lang,
            generation_type="crud",
            framework=framework
        )

        # Si se especificó directorio, guardar archivos separados
        if output_dir and result.get("success"):
            try:
                Path(output_dir).mkdir(parents=True, exist_ok=True)
                ext = self.LANGUAGE_TEMPLATES.get(detected_lang, {}).get("extension", ".txt")

                # Guardar código completo en un archivo
                full_path = Path(output_dir) / f"{entity_name.lower()}_crud{ext}"
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(result["code"])

                result["saved_to"] = str(full_path)
                print(f"   CRUD guardado en: {full_path}")

            except Exception as e:
                print(f"   [ERROR] No se pudo guardar: {e}")

        return result

    def refactor_code(
        self,
        code: str = None,
        file_path: str = None,
        instructions: str = "Mejora la calidad y legibilidad del código",
        output_file: str = None
    ) -> Dict[str, Any]:
        """
        Refactoriza código existente.

        Args:
            code: Código a refactorizar (o usar file_path)
            file_path: Ruta del archivo a refactorizar
            instructions: Instrucciones específicas de refactorización
            output_file: Archivo de salida (si None, sobreescribe original)

        Returns:
            Dict con código refactorizado y cambios realizados
        """
        if file_path and not code:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    code = f.read()
            except Exception as e:
                return {"success": False, "error": f"No se pudo leer {file_path}: {e}"}

        if not code:
            return {"success": False, "error": "Se requiere código o file_path"}

        detected_lang = self._detect_language(file_path=file_path) if file_path else self._detect_language(code)

        spec = f"""Refactoriza el siguiente código:

```{detected_lang}
{code}
```

INSTRUCCIONES DE REFACTORIZACIÓN:
{instructions}
"""

        result = self.generate_code(
            specification=spec,
            language=detected_lang,
            generation_type="refactor",
            output_file=output_file or file_path
        )

        return result

    def generate_function(
        self,
        name: str,
        description: str,
        parameters: Dict[str, str] = None,
        return_type: str = None,
        language: str = None,
        async_function: bool = False
    ) -> Dict[str, Any]:
        """
        Genera una función individual.

        Args:
            name: Nombre de la función
            description: Descripción de lo que hace
            parameters: Dict de {nombre_param: tipo}
            return_type: Tipo de retorno
            language: Lenguaje
            async_function: Si es función asíncrona

        Returns:
            Dict con función generada
        """
        params_desc = ""
        if parameters:
            params_desc = "\n".join([f"  - {pname}: {ptype}" for pname, ptype in parameters.items()])
            params_desc = f"\nParámetros:\n{params_desc}"

        async_str = "asíncrona " if async_function else ""
        return_str = f"\nRetorna: {return_type}" if return_type else ""

        spec = f"""Genera una función {async_str}llamada '{name}' que:
{description}
{params_desc}
{return_str}

Incluye:
- Docstring completo
- Type hints
- Manejo de errores apropiado
- Código funcional y listo para usar
"""

        return self.generate_code(
            specification=spec,
            language=language,
            generation_type="general"
        )

    def generate_class(
        self,
        name: str,
        description: str,
        methods: List[Dict[str, str]] = None,
        attributes: Dict[str, str] = None,
        language: str = None,
        parent_class: str = None
    ) -> Dict[str, Any]:
        """
        Genera una clase completa.

        Args:
            name: Nombre de la clase
            description: Descripción de la clase
            methods: Lista de {name, description, params, return_type}
            attributes: Dict de {nombre_attr: tipo}
            language: Lenguaje
            parent_class: Clase padre (herencia)

        Returns:
            Dict con clase generada
        """
        attrs_desc = ""
        if attributes:
            attrs_desc = "\n".join([f"  - {aname}: {atype}" for aname, atype in attributes.items()])
            attrs_desc = f"\nAtributos:\n{attrs_desc}"

        methods_desc = ""
        if methods:
            for m in methods:
                methods_desc += f"\n  - {m.get('name', 'method')}: {m.get('description', '')}"
                if m.get('params'):
                    methods_desc += f" (params: {m['params']})"
            methods_desc = f"\nMétodos:{methods_desc}"

        inheritance = f" que hereda de {parent_class}" if parent_class else ""

        spec = f"""Genera una clase llamada '{name}'{inheritance} que:
{description}
{attrs_desc}
{methods_desc}

Incluye:
- Docstring de clase
- Constructor con inicialización apropiada
- Type hints en todos los métodos
- Métodos con docstrings
"""

        return self.generate_code(
            specification=spec,
            language=language,
            generation_type="general"
        )

    def get_generation_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de generación."""
        if not self.generation_history:
            return {"total_generations": 0}

        by_type = {}
        by_language = {}
        total_lines = 0
        valid_count = 0

        for gen in self.generation_history:
            gtype = gen.get("type", "unknown")
            lang = gen.get("language", "unknown")

            by_type[gtype] = by_type.get(gtype, 0) + 1
            by_language[lang] = by_language.get(lang, 0) + 1
            total_lines += gen.get("lines_generated", 0)
            if gen.get("valid"):
                valid_count += 1

        return {
            "total_generations": len(self.generation_history),
            "by_type": by_type,
            "by_language": by_language,
            "total_lines_generated": total_lines,
            "validation_success_rate": valid_count / len(self.generation_history) if self.generation_history else 0,
            "recent": self.generation_history[-5:]  # Últimas 5
        }


# Instancia global para uso en tools.py
_code_generator_agent = None


def get_code_generator() -> CodeGeneratorAgent:
    """Obtiene o crea la instancia del agente generador."""
    global _code_generator_agent
    if _code_generator_agent is None:
        _code_generator_agent = CodeGeneratorAgent()
    return _code_generator_agent
