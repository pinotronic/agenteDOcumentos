"""
Análisis de dependencias y vulnerabilidades.
Escanea requirements.txt, package.json y detecta problemas de seguridad.
"""
import env_loader  # Cargar .env PRIMERO
import json
import re
from pathlib import Path
from typing import Dict, Any, List
from openai import OpenAI

from config import ORCHESTRATOR_MODEL


class DependencyAnalyzer:
    """Analiza dependencias y vulnerabilidades de proyectos."""
    
    def __init__(self):
        self.client = OpenAI()
        self.model = ORCHESTRATOR_MODEL
    
    def check_dependencies(self, directory: str) -> Dict[str, Any]:
        """
        Escanea archivos de dependencias en un directorio.
        
        Args:
            directory: Directorio del proyecto
            
        Returns:
            Análisis de dependencias encontradas
        """
        print(f"🔍 Escaneando dependencias en: {directory}")
        
        try:
            path = Path(directory).resolve()
            
            if not path.exists() or not path.is_dir():
                return {"error": f"Directorio no válido: {directory}"}
            
            result = {
                "directory": str(path),
                "python_dependencies": None,
                "javascript_dependencies": None,
                "total_dependencies": 0,
                "files_found": []
            }
            
            # Buscar requirements.txt (Python)
            requirements_files = list(path.rglob("requirements*.txt"))
            if requirements_files:
                result["python_dependencies"] = self._parse_requirements(requirements_files[0])
                result["files_found"].append(str(requirements_files[0]))
                result["total_dependencies"] += len(result["python_dependencies"]["packages"])
            
            # Buscar package.json (JavaScript/Node)
            package_json = path / "package.json"
            if package_json.exists():
                result["javascript_dependencies"] = self._parse_package_json(package_json)
                result["files_found"].append(str(package_json))
                deps = result["javascript_dependencies"].get("dependencies", {})
                dev_deps = result["javascript_dependencies"].get("devDependencies", {})
                result["total_dependencies"] += len(deps) + len(dev_deps)
            
            if not result["files_found"]:
                return {
                    "warning": "No se encontraron archivos de dependencias",
                    "suggestion": "Busca requirements.txt o package.json"
                }
            
            print(f"✅ Encontradas {result['total_dependencies']} dependencias")
            return result
        
        except Exception as e:
            return {"error": str(e)}
    
    def _parse_requirements(self, file_path: Path) -> Dict[str, Any]:
        """Parsea un archivo requirements.txt."""
        packages = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    # Extraer nombre y versión
                    match = re.match(r'([a-zA-Z0-9_-]+)([>=<~!]+)?(.*)?', line)
                    if match:
                        name = match.group(1)
                        operator = match.group(2) or ""
                        version = match.group(3).strip() if match.group(3) else "any"
                        
                        packages.append({
                            "name": name,
                            "version": version,
                            "operator": operator,
                            "raw": line
                        })
        
        return {
            "file": str(file_path),
            "type": "python",
            "packages": packages,
            "count": len(packages)
        }
    
    def _parse_package_json(self, file_path: Path) -> Dict[str, Any]:
        """Parsea un archivo package.json."""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return {
            "file": str(file_path),
            "type": "javascript",
            "name": data.get("name", "unknown"),
            "version": data.get("version", "unknown"),
            "dependencies": data.get("dependencies", {}),
            "devDependencies": data.get("devDependencies", {}),
            "count": len(data.get("dependencies", {})) + len(data.get("devDependencies", {}))
        }
    
    def security_audit(self, directory: str) -> Dict[str, Any]:
        """
        Realiza auditoría de seguridad usando LLM.
        Identifica paquetes con vulnerabilidades conocidas.
        
        Args:
            directory: Directorio del proyecto
            
        Returns:
            Reporte de seguridad
        """
        print(f"🛡️ Realizando auditoría de seguridad en: {directory}")
        
        # Primero obtener dependencias
        deps = self.check_dependencies(directory)
        
        if "error" in deps or "warning" in deps:
            return deps
        
        # Usar LLM para análisis de seguridad
        prompt = f"""Analiza las siguientes dependencias del proyecto y identifica posibles vulnerabilidades de seguridad conocidas:

**Dependencias Python:**
{json.dumps(deps.get('python_dependencies'), indent=2) if deps.get('python_dependencies') else 'Ninguna'}

**Dependencias JavaScript:**
{json.dumps(deps.get('javascript_dependencies'), indent=2) if deps.get('javascript_dependencies') else 'Ninguna'}

Para cada dependencia, indica:
1. Si tiene vulnerabilidades conocidas (CVEs)
2. Versión recomendada si está desactualizada
3. Nivel de riesgo (crítico/alto/medio/bajo)
4. Recomendaciones de actualización

Responde en formato JSON:
{{
  "vulnerabilities": [
    {{
      "package": "nombre",
      "current_version": "version",
      "risk_level": "high|medium|low",
      "cve_ids": ["CVE-2023-1234"],
      "description": "Descripción breve",
      "recommended_version": "version",
      "fix": "Acción recomendada"
    }}
  ],
  "summary": {{
    "critical": 0,
    "high": 0,
    "medium": 0,
    "low": 0,
    "total": 0
  }},
  "overall_risk": "high|medium|low",
  "recommendations": ["Recomendación 1", "Recomendación 2"]
}}
"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",  # Usar modelo más potente para análisis de seguridad
                messages=[
                    {"role": "system", "content": "Eres un experto en seguridad de software y análisis de vulnerabilidades. Proporciona análisis precisos basados en vulnerabilidades conocidas."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            audit_result = json.loads(response.choices[0].message.content)
            audit_result["dependencies_analyzed"] = deps
            
            print(f"✅ Auditoría completada: {audit_result['summary']['total']} problemas encontrados")
            return audit_result
        
        except Exception as e:
            return {"error": f"Error en auditoría de seguridad: {str(e)}"}
    
    def generate_dependency_graph(self, directory: str) -> Dict[str, Any]:
        """
        Genera un diagrama Mermaid de las dependencias del proyecto.
        
        Args:
            directory: Directorio del proyecto
            
        Returns:
            Diagrama en formato Mermaid
        """
        print(f"📊 Generando gráfico de dependencias para: {directory}")
        
        deps = self.check_dependencies(directory)
        
        if "error" in deps or "warning" in deps:
            return deps
        
        mermaid_lines = ["```mermaid\n", "graph LR\n"]
        mermaid_lines.append("    %% Diagrama de Dependencias del Proyecto\n\n")
        
        project_name = Path(directory).name or "Proyecto"
        mermaid_lines.append(f"    PROJECT[{project_name}]\n\n")
        
        # Dependencias Python
        if deps.get("python_dependencies"):
            mermaid_lines.append("    PY[🐍 Python Dependencies]\n")
            mermaid_lines.append("    PROJECT --> PY\n")
            
            for idx, pkg in enumerate(deps["python_dependencies"]["packages"][:15]):  # Limitar
                pkg_id = f"PY{idx}"
                pkg_name = pkg["name"]
                version = pkg["version"]
                mermaid_lines.append(f"    PY --> {pkg_id}[{pkg_name} {version}]\n")
            
            if len(deps["python_dependencies"]["packages"]) > 15:
                mermaid_lines.append(f"    PY --> PY_MORE[... y {len(deps['python_dependencies']['packages']) - 15} más]\n")
            
            mermaid_lines.append("\n")
        
        # Dependencias JavaScript
        if deps.get("javascript_dependencies"):
            mermaid_lines.append("    JS[📦 JavaScript Dependencies]\n")
            mermaid_lines.append("    PROJECT --> JS\n")
            
            all_deps = {**deps["javascript_dependencies"].get("dependencies", {}),
                       **deps["javascript_dependencies"].get("devDependencies", {})}
            
            for idx, (name, version) in enumerate(list(all_deps.items())[:15]):
                dep_id = f"JS{idx}"
                mermaid_lines.append(f"    JS --> {dep_id}[{name} {version}]\n")
            
            if len(all_deps) > 15:
                mermaid_lines.append(f"    JS --> JS_MORE[... y {len(all_deps) - 15} más]\n")
        
        mermaid_lines.append("```\n")
        
        diagram = "".join(mermaid_lines)
        
        return {
            "success": True,
            "diagram": diagram,
            "total_dependencies": deps["total_dependencies"],
            "message": "Diagrama de dependencias generado"
        }
    
    def find_outdated_packages(self, directory: str) -> Dict[str, Any]:
        """
        Identifica paquetes desactualizados usando LLM.
        
        Args:
            directory: Directorio del proyecto
            
        Returns:
            Lista de paquetes desactualizados
        """
        print(f"⚠️ Buscando paquetes desactualizados en: {directory}")
        
        deps = self.check_dependencies(directory)
        
        if "error" in deps or "warning" in deps:
            return deps
        
        prompt = f"""Analiza estas dependencias e identifica cuáles están desactualizadas:

{json.dumps(deps, indent=2)}

Para cada paquete desactualizado, proporciona:
1. Versión actual
2. Última versión estable disponible
3. Cambios importantes en la nueva versión
4. Riesgo de actualizar (breaking changes)

Responde en formato JSON:
{{
  "outdated": [
    {{
      "package": "nombre",
      "current": "version",
      "latest": "version",
      "type": "major|minor|patch",
      "breaking_changes": true/false,
      "recommendation": "Actualizar/Mantener/Revisar"
    }}
  ],
  "up_to_date": ["pkg1", "pkg2"],
  "summary": "Resumen general"
}}
"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Eres un experto en gestión de dependencias. Conoces las versiones actuales de paquetes populares."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            print(f"✅ Análisis completado: {len(result.get('outdated', []))} paquetes desactualizados")
            return result
        
        except Exception as e:
            return {"error": f"Error analizando versiones: {str(e)}"}
