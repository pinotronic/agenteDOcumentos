"""
Generador de código automático.
Genera tests, docstrings, archivos de configuración y Dockerfiles.
"""
import env_loader  # Cargar .env PRIMERO
import json
from pathlib import Path
from typing import Dict, Any
from openai import OpenAI

from config import ANALYZER_MODEL


class CodeGenerator:
    """Genera código automáticamente usando LLM."""
    
    def __init__(self):
        self.client = OpenAI()
        self.model = ANALYZER_MODEL  # Usar modelo potente para generación
    
    def generate_tests(self, file_path: str, framework: str = "pytest") -> Dict[str, Any]:
        """
        Genera unit tests para un archivo de código.
        
        Args:
            file_path: Ruta del archivo a testear
            framework: Framework de testing (pytest, unittest, jest, etc.)
            
        Returns:
            Código de tests generado
        """
        print(f"🧪 Generando tests para: {file_path}")
        
        try:
            path = Path(file_path)
            
            if not path.exists():
                return {"error": f"Archivo no encontrado: {file_path}"}
            
            # Leer código fuente
            with open(path, 'r', encoding='utf-8') as f:
                source_code = f.read()
            
            file_type = path.suffix.lower()
            
            prompt = f"""Genera unit tests completos para el siguiente código usando {framework}:

**Archivo:** {path.name}
**Tipo:** {file_type}

**Código:**
```{file_type[1:]}
{source_code}
```

Requisitos:
1. Tests para todas las funciones y métodos públicos
2. Tests de casos edge y errores
3. Mocks para dependencias externas si es necesario
4. Docstrings explicativos
5. Cobertura completa

Responde en formato JSON:
{{
  "test_file_name": "nombre del archivo de test",
  "test_code": "código completo del test",
  "test_count": número de tests,
  "coverage_estimate": "porcentaje estimado",
  "notes": "Notas sobre los tests generados"
}}
"""
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": f"Eres un experto en testing de software. Generas tests completos y de alta calidad usando {framework}."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            result["source_file"] = str(path)
            result["framework"] = framework
            result["success"] = True
            
            print(f"✅ {result['test_count']} tests generados")
            return result
        
        except Exception as e:
            return {"error": str(e)}
    
    def generate_docstrings(self, file_path: str, style: str = "google") -> Dict[str, Any]:
        """
        Genera o mejora docstrings para funciones y clases.
        
        Args:
            file_path: Ruta del archivo
            style: Estilo de docstring (google, numpy, sphinx)
            
        Returns:
            Código con docstrings mejorados
        """
        print(f"📝 Generando docstrings para: {file_path}")
        
        try:
            path = Path(file_path)
            
            if not path.exists():
                return {"error": f"Archivo no encontrado: {file_path}"}
            
            with open(path, 'r', encoding='utf-8') as f:
                source_code = f.read()
            
            file_type = path.suffix.lower()
            
            prompt = f"""Analiza el siguiente código y agrega/mejora los docstrings usando el estilo {style}:

**Archivo:** {path.name}

```{file_type[1:]}
{source_code}
```

Para cada función/clase/método:
1. Agrega docstring completo si falta
2. Mejora docstrings existentes incompletos
3. Incluye: descripción, Args, Returns, Raises
4. Usa el estilo {style}

Responde en formato JSON:
{{
  "updated_code": "código completo con docstrings mejorados",
  "changes_made": número de docstrings agregados/mejorados,
  "functions_documented": ["func1", "func2"],
  "classes_documented": ["Class1", "Class2"],
  "summary": "Resumen de cambios"
}}
"""
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": f"Eres un experto en documentación de código. Generas docstrings completos y profesionales en estilo {style}."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            result["original_file"] = str(path)
            result["docstring_style"] = style
            result["success"] = True
            
            print(f"✅ {result['changes_made']} docstrings agregados/mejorados")
            return result
        
        except Exception as e:
            return {"error": str(e)}
    
    def generate_config_files(self, directory: str, project_type: str = "python") -> Dict[str, Any]:
        """
        Genera archivos de configuración para el proyecto.
        
        Args:
            directory: Directorio del proyecto
            project_type: Tipo de proyecto (python, javascript, java, etc.)
            
        Returns:
            Archivos de configuración generados
        """
        print(f"🔧 Generando archivos de configuración para proyecto {project_type}")
        
        try:
            path = Path(directory).resolve()
            
            if not path.exists():
                return {"error": f"Directorio no encontrado: {directory}"}
            
            # Analizar estructura del proyecto
            files = list(path.rglob("*"))[:100]  # Limitar a 100 archivos
            file_structure = [str(f.relative_to(path)) for f in files if f.is_file()]
            
            prompt = f"""Genera archivos de configuración apropiados para este proyecto {project_type}:

**Directorio:** {directory}
**Estructura de archivos (muestra):**
{json.dumps(file_structure[:30], indent=2)}

Genera los siguientes archivos de configuración:
1. .gitignore - Ignorar archivos innecesarios
2. .editorconfig - Configuración del editor
3. README.md - README básico
4. LICENSE - Licencia MIT
5. setup.py o package.json (según tipo)
6. .env.example - Variables de entorno de ejemplo

Para cada archivo, proporciona el contenido completo y apropiado para este tipo de proyecto.

Responde en formato JSON:
{{
  "files": [
    {{
      "name": ".gitignore",
      "content": "contenido del archivo",
      "description": "Descripción del archivo"
    }}
  ],
  "project_analysis": "Análisis breve del proyecto",
  "recommendations": ["Recomendación 1", "Recomendación 2"]
}}
"""
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": f"Eres un experto en configuración de proyectos {project_type}. Generas archivos de configuración completos y profesionales."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            result["directory"] = str(path)
            result["project_type"] = project_type
            result["success"] = True
            
            print(f"✅ {len(result['files'])} archivos de configuración generados")
            return result
        
        except Exception as e:
            return {"error": str(e)}
    
    def generate_dockerfile(self, directory: str, optimize: bool = True) -> Dict[str, Any]:
        """
        Genera un Dockerfile optimizado para el proyecto.
        
        Args:
            directory: Directorio del proyecto
            optimize: Si debe optimizar para producción
            
        Returns:
            Dockerfile generado
        """
        print(f"🐳 Generando Dockerfile para: {directory}")
        
        try:
            path = Path(directory).resolve()
            
            if not path.exists():
                return {"error": f"Directorio no encontrado: {directory}"}
            
            # Detectar tipo de proyecto
            project_info = {
                "has_requirements": (path / "requirements.txt").exists(),
                "has_package_json": (path / "package.json").exists(),
                "has_pom_xml": (path / "pom.xml").exists(),
                "has_go_mod": (path / "go.mod").exists(),
                "python_files": len(list(path.rglob("*.py"))),
                "js_files": len(list(path.rglob("*.js"))),
            }
            
            # Leer archivos de dependencias si existen
            dependencies_content = ""
            if project_info["has_requirements"]:
                with open(path / "requirements.txt", 'r') as f:
                    dependencies_content = f.read()
            elif project_info["has_package_json"]:
                with open(path / "package.json", 'r') as f:
                    dependencies_content = f.read()
            
            prompt = f"""Genera un Dockerfile {"optimizado para producción" if optimize else "básico"} para este proyecto:

**Directorio:** {directory}
**Info del proyecto:**
{json.dumps(project_info, indent=2)}

**Dependencias:**
{dependencies_content[:1000] if dependencies_content else "No encontradas"}

Requisitos:
1. Multi-stage build si es para producción
2. Usuario no-root por seguridad
3. Cache de dependencias optimizado
4. Tamaño de imagen minimizado
5. Healthcheck si aplica
6. Variables de entorno apropiadas

Responde en formato JSON:
{{
  "dockerfile": "contenido completo del Dockerfile",
  "dockerignore": "contenido del .dockerignore",
  "estimated_size": "Tamaño estimado de la imagen",
  "base_image": "Imagen base usada",
  "build_command": "Comando para construir",
  "run_command": "Comando para ejecutar",
  "optimization_notes": "Notas sobre optimizaciones aplicadas"
}}
"""
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Eres un experto en Docker y containerización. Generas Dockerfiles optimizados siguiendo las mejores prácticas."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            result["directory"] = str(path)
            result["optimized"] = optimize
            result["success"] = True
            
            print(f"✅ Dockerfile generado (tamaño estimado: {result.get('estimated_size', 'N/A')})")
            return result
        
        except Exception as e:
            return {"error": str(e)}
