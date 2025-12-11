"""
Módulo de herramientas para el agente orquestador.
Define las funciones que el agente puede usar para análisis de código.
"""
import os
import json
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

from config import (
    ALL_EXTENSIONS, IGNORE_PATTERNS, BINARY_EXTENSIONS,
    MAX_FILE_SIZE_MB, SHOW_PERMISSION_WARNINGS, CODE_EXTENSIONS
)
from rag_storage_chroma import RAGStorage  # ChromaDB en lugar de JSON
from code_analyzer import CodeAnalyzer
from doc_generator import DocumentationGenerator
from dependency_analyzer import DependencyAnalyzer
from code_generator import CodeGenerator
from code_assistant import CodeAssistant
from external_integrations import ExternalIntegrations
from report_generator import ReportGenerator
from ci_cd_tools import CICDTools
from php_curl_analyzer import PHPCurlAnalyzer
from architect_mode import Architect
from contract_validator import ContractValidator, DoDChecker
from quality_gate import QualityGate
from evidence_generator import EvidenceGenerator
from incremental_committer import IncrementalCommitter
from plan_executor import PlanExecutor, list_directory_recursive
from plan_supervisor import PlanSupervisor

# Instancias globales
_rag_storage = RAGStorage()
_code_analyzer = CodeAnalyzer()
_doc_generator = DocumentationGenerator(rag_storage=_rag_storage)  # Compartir instancia
_dependency_analyzer = DependencyAnalyzer()
_code_generator = CodeGenerator()
_code_assistant = CodeAssistant()
_external_integrations = ExternalIntegrations()
_report_generator = ReportGenerator(rag_storage=_rag_storage)  # Compartir instancia
_ci_cd_tools = CICDTools()
_php_curl_analyzer = PHPCurlAnalyzer(base_url="http://172.16.12.178")
_architect = Architect()
_contract_validator = ContractValidator()
_dod_checker = DoDChecker()
_quality_gate = QualityGate()
_evidence_generator = EvidenceGenerator()
_incremental_committer = IncrementalCommitter()

# Executor y Supervisor se inicializarán después de registrar tools
_plan_executor = None
_plan_supervisor = None


def _should_ignore(path: Path) -> bool:
    """Verifica si un archivo/directorio debe ser ignorado."""
    path_str = str(path)
    name = path.name
    
    # Verificar patrones de ignorar
    for pattern in IGNORE_PATTERNS:
        if pattern.startswith('*.'):
            # Patrón de extensión
            if name.endswith(pattern[1:]):
                return True
        else:
            # Patrón de nombre/directorio
            if pattern in path_str or name == pattern:
                return True
    
    # Verificar extensiones binarias
    if path.suffix.lower() in BINARY_EXTENSIONS:
        return True
    
    return False


def _analyze_file_architecture(file_path: Path, file_info: Dict, architecture: Dict) -> None:
    """
    Analiza un archivo para detectar patrones arquitectónicos.
    Detecta frameworks, entry points, configs, dependencias.
    """
    name = file_path.name.lower()
    ext = file_path.suffix.lower()
    
    # Detectar lenguajes
    if ext in CODE_EXTENSIONS:
        architecture["detected_languages"].add(CODE_EXTENSIONS[ext])
    
    # Entry points comunes
    if name in ["main.py", "app.py", "index.js", "index.php", "server.js", "main.go", "main.java"]:
        architecture["entry_points"].append(str(file_path))
    
    # Archivos de dependencias
    if name in ["requirements.txt", "package.json", "composer.json", "pom.xml", "build.gradle", 
                "go.mod", "cargo.toml", "gemfile", "pipfile"]:
        architecture["dependency_files"].append(str(file_path))
    
    # Archivos de configuración
    if name in ["config.py", "settings.py", ".env", "config.json", "app.config", 
                "web.config", "application.properties", "application.yml"]:
        architecture["config_files"].append(str(file_path))
    
    # Archivos de build
    if name in ["makefile", "dockerfile", "docker-compose.yml", "webpack.config.js", 
                "gulpfile.js", "gruntfile.js", "setup.py", "pyproject.toml"]:
        architecture["build_files"].append(str(file_path))
    
    # Detectar frameworks por archivos característicos
    if name == "manage.py":
        if "Django" not in architecture["detected_frameworks"]:
            architecture["detected_frameworks"].append("Django")
    elif name == "app.py" or name == "wsgi.py":
        if "Flask" not in architecture["detected_frameworks"]:
            architecture["detected_frameworks"].append("Flask/WSGI")
    elif name == "package.json":
        # Podría leer el contenido para detectar React/Vue/Angular
        if "Node.js" not in architecture["detected_frameworks"]:
            architecture["detected_frameworks"].append("Node.js")
    elif name == "composer.json":
        if "PHP/Composer" not in architecture["detected_frameworks"]:
            architecture["detected_frameworks"].append("PHP/Composer")
    elif ext == ".java" and "pom.xml" in str(file_path.parent):
        if "Maven" not in architecture["detected_frameworks"]:
            architecture["detected_frameworks"].append("Maven")
    
    # Detectar directorios de tests
    if "test" in str(file_path.parent).lower() or "tests" in str(file_path.parent).lower():
        test_dir = str(file_path.parent)
        if test_dir not in architecture["test_directories"]:
            architecture["test_directories"].append(test_dir)


def explore_directory(directory: str, recursive: bool = True, max_depth: int = None, analyze_architecture: bool = True) -> Dict[str, Any]:
    """
    Explora un directorio exhaustivamente y retorna su estructura completa.
    Ahora sin límites artificiales para seguir ModoGorila.
    
    Args:
        directory: Ruta del directorio a explorar
        recursive: Si debe explorar subdirectorios
        max_depth: Profundidad máxima (None = sin límite, por defecto)
        analyze_architecture: Si debe detectar patrones arquitectónicos
    """
    print(f"⚙️ [EXPLORACIÓN PROFUNDA] Analizando directorio: {directory}")
    if max_depth is None:
        print("   🔓 Sin límite de profundidad - análisis exhaustivo")
    
    try:
        path = Path(directory).resolve()
        
        if not path.exists():
            return {"error": f"El directorio no existe: {directory}"}
        
        if not path.is_dir():
            return {"error": f"La ruta no es un directorio: {directory}"}
        
        result = {
            "directory": str(path),
            "files": [],
            "subdirectories": [],
            "stats": {
                "total_files": 0,
                "by_type": {},
                "ignored": 0,
                "max_depth_reached": 0
            },
            "architecture": {
                "detected_frameworks": [],
                "detected_languages": set(),
                "entry_points": [],
                "config_files": [],
                "dependency_files": [],
                "test_directories": [],
                "build_files": []
            } if analyze_architecture else None
        }
        
        def explore_recursive(current_path: Path, depth: int = 0):
            if max_depth is not None and depth > max_depth:
                return
            
            # Actualizar profundidad máxima alcanzada
            if depth > result["stats"]["max_depth_reached"]:
                result["stats"]["max_depth_reached"] = depth
            
            try:
                for item in current_path.iterdir():
                    # Verificar si debe ignorarse
                    if _should_ignore(item):
                        result["stats"]["ignored"] += 1
                        continue
                    
                    if item.is_file():
                        file_info = {
                            "path": str(item),
                            "name": item.name,
                            "extension": item.suffix,
                            "size_bytes": item.stat().st_size,
                            "type": ALL_EXTENSIONS.get(item.suffix.lower(), "unknown")
                        }
                        result["files"].append(file_info)
                        result["stats"]["total_files"] += 1
                        
                        # Contar por tipo
                        file_type = file_info["type"]
                        result["stats"]["by_type"][file_type] = result["stats"]["by_type"].get(file_type, 0) + 1
                        
                        # Análisis arquitectónico
                        if analyze_architecture:
                            _analyze_file_architecture(item, file_info, result["architecture"])
                    
                    elif item.is_dir() and recursive:
                        result["subdirectories"].append(str(item))
                        explore_recursive(item, depth + 1)
            
            except PermissionError:
                if SHOW_PERMISSION_WARNINGS:
                    print(f"⚠️ Sin permisos para acceder: {current_path}")
                pass  # Silenciar warnings de permisos de carpetas del sistema
        
        explore_recursive(path)
        
        # Convertir sets a listas para JSON
        if analyze_architecture and result["architecture"]:
            result["architecture"]["detected_languages"] = list(result["architecture"]["detected_languages"])
        
        # Resumen de exploración
        print(f"✅ Exploración completada:")
        print(f"   📊 Archivos: {result['stats']['total_files']}")
        print(f"   📁 Subdirectorios: {len(result['subdirectories'])}")
        print(f"   🗂️  Profundidad alcanzada: {result['stats']['max_depth_reached']}")
        print(f"   🚫 Ignorados: {result['stats']['ignored']}")
        
        if analyze_architecture and result["architecture"]:
            arch = result["architecture"]
            print(f"\n🏗️  ARQUITECTURA DETECTADA:")
            if arch["detected_frameworks"]:
                print(f"   Frameworks: {', '.join(arch['detected_frameworks'])}")
            if arch["detected_languages"]:
                print(f"   Lenguajes: {', '.join(arch['detected_languages'])}")
            if arch["entry_points"]:
                print(f"   Entry points: {len(arch['entry_points'])}")
            if arch["dependency_files"]:
                print(f"   Archivos de dependencias: {len(arch['dependency_files'])}")
        
        return result
    
    except Exception as e:
        return {"error": str(e)}


def read_file(file_path: str) -> Dict[str, Any]:
    """
    Lee el contenido de un archivo.
    
    Args:
        file_path: Ruta del archivo a leer
    """
    print(f"⚙️ Leyendo archivo: {file_path}")
    
    try:
        path = Path(file_path).resolve()
        
        if not path.exists():
            return {"error": f"El archivo no existe: {file_path}"}
        
        if not path.is_file():
            return {"error": f"La ruta no es un archivo: {file_path}"}
        
        # Verificar tamaño
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            return {"error": f"Archivo muy grande: {size_mb:.2f}MB (límite: {MAX_FILE_SIZE_MB}MB)"}
        
        # Verificar si es binario
        if path.suffix.lower() in BINARY_EXTENSIONS:
            return {"error": f"Archivo binario no soportado: {path.suffix}"}
        
        # Leer contenido
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # Intentar con otra codificación
            with open(path, 'r', encoding='latin-1') as f:
                content = f.read()
        
        return {
            "file_path": str(path),
            "file_name": path.name,
            "extension": path.suffix,
            "size_bytes": path.stat().st_size,
            "content": content,
            "lines": len(content.splitlines()),
            "type": ALL_EXTENSIONS.get(path.suffix.lower(), "unknown")
        }
    
    except Exception as e:
        return {"error": str(e)}


def analyze_file(file_path: str) -> Dict[str, Any]:
    """
    Analiza un archivo usando el LLM analizador y guarda en RAG con indexación inteligente.
    
    Args:
        file_path: Ruta del archivo a analizar
    """
    print(f"⚙️ Analizando archivo: {file_path}")
    
    # Primero leer el archivo
    file_data = read_file(file_path)
    
    if "error" in file_data:
        return file_data
    
    # Analizar con el LLM especializado
    analysis = _code_analyzer.analyze_file(
        file_path=file_data["file_path"],
        content=file_data["content"],
        file_type=file_data["type"]
    )
    
    # Guardar en RAG con indexación inteligente (pasa el contenido)
    doc_id = _rag_storage.save_analysis(
        file_path=file_data["file_path"], 
        analysis=analysis,
        content=file_data["content"],  # Pasar contenido para evaluación
        use_smart_indexing=True  # Habilitar indexación inteligente
    )
    
    # Si doc_id es None, significa que no se indexó
    if doc_id is None:
        return {
            "file_path": file_data["file_path"],
            "analysis": analysis,
            "saved_to_rag": False,
            "reason": "No cumple criterios de relevancia para SIGSAPAL"
        }
    
    return {
        "file_path": file_data["file_path"],
        "document_id": doc_id,
        "analysis": analysis,
        "saved_to_rag": True
    }


def analyze_directory(directory: str, file_extensions: List[str] = None) -> Dict[str, Any]:
    """
    Analiza todos los archivos de un directorio.
    
    Args:
        directory: Ruta del directorio
        file_extensions: Lista de extensiones a analizar (ej: ['.py', '.js']). Si es None, analiza todos los soportados.
    """
    print(f"⚙️ Analizando directorio completo: {directory}")
    
    # Explorar directorio
    exploration = explore_directory(directory)
    
    if "error" in exploration:
        return exploration
    
    # Filtrar archivos a analizar
    files_to_analyze = exploration["files"]
    
    if file_extensions:
        files_to_analyze = [f for f in files_to_analyze if f["extension"] in file_extensions]
    else:
        # Solo analizar archivos con extensiones conocidas
        files_to_analyze = [f for f in files_to_analyze if f["type"] != "unknown"]
    
    total_files = len(files_to_analyze)
    print(f"📊 Se analizarán {total_files} archivos")
    
    results = {
        "directory": directory,
        "total_files": total_files,
        "analyzed": [],
        "errors": []
    }
    
    # Analizar cada archivo
    for idx, file_info in enumerate(files_to_analyze, 1):
        print(f"\n📈 Progreso: {idx}/{total_files}")
        
        result = analyze_file(file_info["path"])
        
        if "error" in result:
            results["errors"].append({
                "file": file_info["path"],
                "error": result["error"]
            })
        else:
            results["analyzed"].append({
                "file": file_info["path"],
                "document_id": result["document_id"]
            })
    
    print(f"\n✅ Análisis completado: {len(results['analyzed'])} exitosos, {len(results['errors'])} errores")
    
    return results


def search_in_rag(query: str, search_type: str = "keyword") -> Dict[str, Any]:
    """
    Busca información en el RAG.
    
    Args:
        query: Texto a buscar
        search_type: Tipo de búsqueda ('keyword', 'function', 'type')
    """
    print(f"⚙️ Buscando en RAG: '{query}' (tipo: {search_type})")
    
    try:
        if search_type == "keyword":
            results = _rag_storage.search_by_keyword(query)
        elif search_type == "function":
            results = _rag_storage.search_functions(query)
        elif search_type == "type":
            results = _rag_storage.search_by_type(query)
        else:
            return {"error": f"Tipo de búsqueda no válido: {search_type}"}
        
        return {
            "query": query,
            "search_type": search_type,
            "results_count": len(results),
            "results": results
        }
    
    except Exception as e:
        return {"error": str(e)}


def get_rag_statistics() -> Dict[str, Any]:
    """Obtiene estadísticas del RAG."""
    print("⚙️ Obteniendo estadísticas del RAG")
    return _rag_storage.get_statistics()


def list_files_in_dir(directory: str = ".") -> Dict[str, Any]:
    """Lista los archivos en un directorio dado (herramienta básica legacy)."""
    print(f"⚙️ Herramienta llamada: list_files_in_dir(directory='{directory}')")
    try:
        files = os.listdir(directory)
        return {"files": files, "count": len(files)}
    except Exception as e:
        return {"error": str(e)}


def create_file(file_path: str, content: str) -> Dict[str, Any]:
    """
    Crea un nuevo archivo con el contenido especificado.
    
    Args:
        file_path: Ruta completa del archivo a crear
        content: Contenido del archivo
    """
    print(f"⚙️ Creando archivo: {file_path}")
    
    try:
        path = Path(file_path)
        
        # Verificar si ya existe
        if path.exists():
            return {"error": f"El archivo ya existe: {file_path}. Usa write_file para sobrescribir."}
        
        # Crear directorios padre si no existen
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Escribir archivo
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return {
            "success": True,
            "file_path": str(path),
            "size_bytes": path.stat().st_size,
            "message": f"Archivo creado exitosamente: {path.name}"
        }
    
    except Exception as e:
        return {"error": str(e)}


def write_file(file_path: str, content: str, create_if_missing: bool = True) -> Dict[str, Any]:
    """
    Escribe/sobrescribe el contenido de un archivo.
    
    Args:
        file_path: Ruta completa del archivo
        content: Contenido a escribir
        create_if_missing: Si debe crear el archivo si no existe
    """
    print(f"⚙️ Escribiendo archivo: {file_path}")
    
    try:
        path = Path(file_path)
        
        # Verificar si existe
        if not path.exists() and not create_if_missing:
            return {"error": f"El archivo no existe: {file_path}"}
        
        # Crear directorios padre si no existen
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Escribir archivo
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return {
            "success": True,
            "file_path": str(path),
            "size_bytes": path.stat().st_size,
            "message": f"Archivo escrito exitosamente: {path.name}"
        }
    
    except Exception as e:
        return {"error": str(e)}


def append_to_file(file_path: str, content: str) -> Dict[str, Any]:
    """
    Agrega contenido al final de un archivo existente.
    
    Args:
        file_path: Ruta completa del archivo
        content: Contenido a agregar
    """
    print(f"⚙️ Agregando contenido a: {file_path}")
    
    try:
        path = Path(file_path)
        
        if not path.exists():
            return {"error": f"El archivo no existe: {file_path}"}
        
        # Agregar contenido
        with open(path, 'a', encoding='utf-8') as f:
            f.write(content)
        
        return {
            "success": True,
            "file_path": str(path),
            "size_bytes": path.stat().st_size,
            "message": f"Contenido agregado exitosamente a: {path.name}"
        }
    
    except Exception as e:
        return {"error": str(e)}


def generate_documentation(directory: str, output_file: str = None, include_diagrams: bool = True) -> Dict[str, Any]:
    """
    Genera documentación en formato Markdown para un directorio analizado.
    Incluye diagramas UML en Mermaid si se solicita.
    
    Args:
        directory: Directorio para generar documentación (debe estar analizado en RAG)
        output_file: Ruta del archivo MD de salida (opcional, se genera automáticamente)
        include_diagrams: Si debe incluir diagramas UML en Mermaid
    """
    print(f"⚙️ Generando documentación para: {directory}")
    
    try:
        result = _doc_generator.generate_documentation(
            directory=directory,
            output_file=output_file,
            include_diagrams=include_diagrams
        )
        
        return result
    
    except Exception as e:
        return {"error": str(e)}


def open_file_in_editor(file_path: str) -> Dict[str, Any]:
    """
    Abre un archivo en el editor VS Code para que el usuario lo edite.
    
    Args:
        file_path: Ruta completa del archivo a abrir
    """
    print(f"📂 Abriendo archivo en editor: {file_path}")
    
    try:
        from pathlib import Path
        import subprocess
        import os
        
        # Verificar que el archivo existe
        file_path_obj = Path(file_path)
        
        if not file_path_obj.exists():
            return {
                "error": f"El archivo no existe: {file_path}",
                "success": False
            }
        
        # Obtener ruta absoluta
        abs_path = str(file_path_obj.absolute())
        
        # Abrir en VS Code
        try:
            # Intentar abrir con 'code' (VS Code CLI)
            subprocess.run(['code', abs_path], check=False, shell=True)
            
            return {
                "success": True,
                "file_path": abs_path,
                "message": f"Archivo abierto en editor: {file_path_obj.name}"
            }
        except Exception as cmd_error:
            # Si falla, intentar con start (Windows)
            if os.name == 'nt':
                os.startfile(abs_path)
                return {
                    "success": True,
                    "file_path": abs_path,
                    "message": f"Archivo abierto con editor predeterminado: {file_path_obj.name}"
                }
            else:
                raise cmd_error
    
    except Exception as e:
        return {
            "error": str(e),
            "success": False
        }


# === HERRAMIENTAS DE DEPENDENCIAS ===

def check_dependencies(project_path: str) -> Dict[str, Any]:
    """Verifica las dependencias del proyecto y su estado."""
    return _dependency_analyzer.check_dependencies(project_path)


def security_audit(project_path: str) -> Dict[str, Any]:
    """Realiza auditoría de seguridad en las dependencias."""
    return _dependency_analyzer.security_audit(project_path)


def generate_dependency_graph(project_path: str, output_file: str = None) -> Dict[str, Any]:
    """Genera un grafo de dependencias en formato Mermaid."""
    return _dependency_analyzer.generate_dependency_graph(project_path, output_file)


def find_outdated_packages(project_path: str) -> Dict[str, Any]:
    """Encuentra paquetes desactualizados."""
    return _dependency_analyzer.find_outdated_packages(project_path)


# === HERRAMIENTAS DE GENERACIÓN DE CÓDIGO ===

def generate_tests(file_path: str, test_framework: str = "pytest") -> Dict[str, Any]:
    """Genera tests para un archivo de código."""
    return _code_generator.generate_tests(file_path, test_framework)


def generate_docstrings(file_path: str, style: str = "google") -> Dict[str, Any]:
    """Genera docstrings para un archivo de código."""
    return _code_generator.generate_docstrings(file_path, style)


def generate_config_files(project_path: str, files: List[str] = None) -> Dict[str, Any]:
    """Genera archivos de configuración para el proyecto."""
    return _code_generator.generate_config_files(project_path, files)


def generate_dockerfile(project_path: str, language: str = None) -> Dict[str, Any]:
    """Genera un Dockerfile para el proyecto."""
    return _code_generator.generate_dockerfile(project_path, language)


# === HERRAMIENTAS DE ASISTENCIA INTERACTIVA ===

def explain_code(file_path: str, detail_level: str = "intermediate") -> Dict[str, Any]:
    """Explica el código de un archivo."""
    return _code_assistant.explain_code(file_path, detail_level)


def debug_assistant(file_path: str, error_message: str = None) -> Dict[str, Any]:
    """Asiste en la depuración de código."""
    return _code_assistant.debug_assistant(file_path, error_message)


def code_review(file_path: str) -> Dict[str, Any]:
    """Realiza una revisión de código."""
    return _code_assistant.code_review(file_path)


# === HERRAMIENTAS DE INTEGRACIÓN EXTERNA ===

def search_stackoverflow(query: str, max_results: int = 5) -> Dict[str, Any]:
    """Busca soluciones en StackOverflow."""
    return _external_integrations.search_stackoverflow(query, max_results)


def fetch_api_docs(package_name: str, language: str = "python") -> Dict[str, Any]:
    """Obtiene documentación de APIs."""
    return _external_integrations.fetch_api_docs(package_name, language)


# === HERRAMIENTAS DE REPORTES ===

def generate_html_dashboard(directory: str, output_file: str = None) -> Dict[str, Any]:
    """Genera un dashboard HTML del proyecto."""
    return _report_generator.generate_html_dashboard(directory, output_file)


def technical_debt_report(directory: str) -> Dict[str, Any]:
    """Genera reporte de deuda técnica."""
    return _report_generator.technical_debt_report(directory)


# === HERRAMIENTAS DE CI/CD ===

def run_linters(directory: str, linters: List[str] = None) -> Dict[str, Any]:
    """Ejecuta linters en el proyecto."""
    return _ci_cd_tools.run_linters(directory, linters)


def run_tests(directory: str, framework: str = None) -> Dict[str, Any]:
    """Ejecuta tests del proyecto."""
    return _ci_cd_tools.run_tests(directory, framework)


def check_build(directory: str) -> Dict[str, Any]:
    """Verifica que el proyecto compile/build correctamente."""
    return _ci_cd_tools.check_build(directory)


def deployment_check(directory: str) -> Dict[str, Any]:
    """Verifica readiness de deployment."""
    return _ci_cd_tools.deployment_check(directory)


def add_diagram_to_php(file_path: str, diagram_content: str, diagram_type: str = "flowchart") -> Dict[str, Any]:
    """
    Guarda un diagrama Mermaid como metadata en el RAG.
    NO crea archivos .mmd, solo actualiza metadatos.
    
    Args:
        file_path: Ruta del archivo PHP en el RAG
        diagram_content: Contenido del diagrama Mermaid
        diagram_type: Tipo de diagrama (flowchart, sequence, class, etc.)
    
    Returns:
        Resultado de la operación
    """
    print(f"📊 Guardando diagrama en RAG para: {file_path}")
    
    try:
        # Verificar que existe en el RAG
        existing = _rag_storage.get_analysis(file_path)
        if not existing:
            return {
                "success": False,
                "error": f"Archivo no encontrado en el RAG: {file_path}"
            }
        
        # Preparar metadata del diagrama
        diagram_metadata = {
            "mermaid_diagram": diagram_content,
            "diagram_type": diagram_type,
            "diagram_added_at": datetime.now().isoformat()
        }
        
        # Actualizar metadata en el RAG
        success = _rag_storage.update_document_metadata(file_path, diagram_metadata)
        
        if success:
            return {
                "success": True,
                "file_path": file_path,
                "diagram_type": diagram_type,
                "diagram_length": len(diagram_content),
                "message": "Diagrama guardado en metadatos del RAG (NO se creó archivo físico)"
            }
        else:
            return {
                "success": False,
                "error": "No se pudo actualizar metadata en el RAG"
            }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Error guardando diagrama: {str(e)}"
        }


def add_curl_test_to_php(file_path: str) -> Dict[str, Any]:
    """
    Analiza un archivo PHP, genera comandos curl y los guarda en metadatos del RAG.
    NO crea archivos nuevos, solo actualiza el RAG.
    """
    print(f"🔍 Analizando archivo PHP para generar curl: {file_path}")
    
    try:
        # Verificar que existe en el RAG
        existing_analysis = _rag_storage.get_analysis(file_path)
        if not existing_analysis:
            return {
                "success": False,
                "error": f"Archivo no encontrado en el RAG: {file_path}. Debe ser analizado primero con analyze_file."
            }
        
        # Leer contenido del archivo
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            return {
                "success": False,
                "error": f"No se pudo leer el archivo: {e}"
            }
        
        # Analizar con PHPCurlAnalyzer
        curl_metadata = _php_curl_analyzer.analyze_php_file(file_path, content)
        
        # Actualizar el análisis en el RAG con los metadatos de curl
        analysis = existing_analysis["analysis"]
        _rag_storage.save_analysis(file_path, analysis, curl_metadata)
        
        print(f"✅ Curl guardado en RAG para: {file_path}")
        
        return {
            "success": True,
            "file_path": file_path,
            "curl_command": curl_metadata["curl_command"],
            "endpoint_url": curl_metadata["url_endpoint"],
            "method": curl_metadata["method"],
            "post_parameters": curl_metadata["post_parameters"],
            "get_parameters": curl_metadata["get_parameters"],
            "curl_examples": curl_metadata["curl_examples"],
            "requires_auth": curl_metadata["requires_auth"],
            "has_database": curl_metadata["has_database"],
            "message": "Comandos curl generados y guardados en metadatos del RAG"
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Error procesando archivo PHP: {str(e)}"
        }


def test_php_endpoint(file_path: str, custom_params: Dict = None) -> Dict[str, Any]:
    """
    Ejecuta el curl guardado en el RAG para probar un endpoint PHP.
    """
    import subprocess
    
    print(f"🧪 Probando endpoint PHP: {file_path}")
    
    try:
        # Obtener análisis del RAG
        doc = _rag_storage.get_analysis(file_path)
        if not doc:
            return {
                "success": False,
                "error": "Archivo no encontrado en el RAG"
            }
        
        # Verificar si tiene curl_command
        curl_command = doc.get("curl_command")
        if not curl_command:
            return {
                "success": False,
                "error": "Este archivo no tiene comando curl. Usa add_curl_test_to_php primero."
            }
        
        # Ejecutar curl
        print(f"   Ejecutando: {curl_command}")
        result = subprocess.run(
            curl_command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        return {
            "success": result.returncode == 0,
            "file_path": file_path,
            "curl_command": curl_command,
            "endpoint_url": doc.get("endpoint_url", ""),
            "status_code": result.returncode,
            "response": result.stdout[:1000] if result.stdout else "",  # Primeros 1000 chars
            "error": result.stderr[:500] if result.stderr else "",
            "execution_time": "< 30s"
        }
    
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Timeout: El endpoint tardó más de 30 segundos"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error ejecutando curl: {str(e)}"
        }


def generate_analysis_plan(
    repository_path: str,
    user_requirements: str,
    scope: str = "full"
) -> Dict[str, Any]:
    """
    Genera un plan de análisis estructurado usando el Arquitecto.
    Sigue ModoGorila: Contract-Driven con Spec Pack, DoD y TestPlan.
    
    Args:
        repository_path: Ruta del repositorio a analizar
        user_requirements: Descripción de lo que el usuario necesita analizar
        scope: Alcance del análisis (full, quick, targeted)
    
    Returns:
        Plan estructurado con pasos, contratos, DoD y métricas
    """
    print(f"\n🏗️  [ARQUITECTO] Iniciando generación de plan...")
    
    try:
        plan = _architect.generate_analysis_plan(
            repository_path=repository_path,
            user_requirements=user_requirements,
            scope=scope
        )
        
        return {
            "success": True,
            "plan": plan,
            "message": "Plan de análisis generado exitosamente"
        }
    
    except Exception as e:
        print(f"❌ Error generando plan: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Error al generar plan de análisis"
        }


def validate_contract(
    data: Dict[str, Any],
    schema_name: str = None,
    custom_schema: Dict = None
) -> Dict[str, Any]:
    """
    Valida un output contra un JSON Schema.
    Verifica que los datos cumplan con el contrato especificado.
    
    Args:
        data: Datos a validar
        schema_name: Nombre del schema predefinido (analysis_result, exploration_result, plan_result)
        custom_schema: Schema personalizado en formato JSON Schema
    
    Returns:
        Resultado de validación con errores si los hay
    """
    print(f"\n📋 [CONTRACT] Validando contra schema: {schema_name or 'custom'}...")
    
    try:
        result = _contract_validator.validate_output(
            data=data,
            schema_name=schema_name,
            custom_schema=custom_schema
        )
        
        if result["valid"]:
            print(f"   ✅ Validación exitosa")
        else:
            print(f"   ❌ Validación falló: {result.get('error')}")
        
        return {
            "success": True,
            "validation": result
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def check_dod_compliance(
    dod: Dict[str, Any],
    execution_evidence: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Verifica cumplimiento de Definition of Done.
    Valida que se cumplan todos los criterios de aceptación.
    
    Args:
        dod: Definition of Done del plan (con checklist, criteria, metrics)
        execution_evidence: Evidencia de ejecución con resultados y métricas
    
    Returns:
        Reporte de cumplimiento con gaps y score
    """
    print(f"\n✅ [DoD] Verificando cumplimiento...")
    
    try:
        result = _dod_checker.check_dod(
            dod=dod,
            execution_evidence=execution_evidence
        )
        
        return {
            "success": True,
            "compliance": result,
            "dod_satisfied": result["dod_satisfied"],
            "score": result["score"]
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def run_quality_gates(
    check_build: bool = True,
    check_lint: bool = True,
    check_tests: bool = False,
    files_to_check: List[str] = None
) -> Dict[str, Any]:
    """
    Ejecuta gates de calidad: compilación, lint, tests.
    Self-check obligatorio antes de continuar.
    
    Args:
        check_build: Si debe verificar sintaxis/compilación
        check_lint: Si debe ejecutar linters
        check_tests: Si debe ejecutar tests
        files_to_check: Lista de archivos específicos (None = todos)
    
    Returns:
        Resultado de gates con evidencia de cada verificación
    """
    print(f"\n🚦 [QUALITY GATES] Ejecutando verificaciones...")
    
    try:
        result = _quality_gate.run_all_gates(
            check_build=check_build,
            check_lint=check_lint,
            check_tests=check_tests,
            files_to_check=files_to_check
        )
        
        # Generar evidencia estructurada
        evidence = _quality_gate.generate_evidence(result)
        
        return {
            "success": True,
            "gates_passed": result["gates_passed"],
            "gates": result["gates"],
            "evidence": evidence,
            "message": "Verificaciones completadas"
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Error ejecutando quality gates"
        }


def generate_execution_evidence(
    step_title: str,
    gates_result: Dict = None,
    dod_result: Dict = None,
    validation_result: Dict = None,
    custom_data: Dict = None
) -> Dict[str, Any]:
    """
    Genera evidencia estructurada completa de ejecución de un paso.
    Incluye gates, DoD, validaciones y métricas.
    
    Args:
        step_title: Título del paso ejecutado
        gates_result: Resultado de quality gates
        dod_result: Resultado de verificación de DoD
        validation_result: Resultado de validación de contratos
        custom_data: Datos adicionales personalizados
    
    Returns:
        Evidencia estructurada en formato estándar
    """
    print(f"\n📋 [EVIDENCE] Generando evidencia para: {step_title}...")
    
    try:
        evidence = _evidence_generator.generate_execution_evidence(
            step_title=step_title,
            gates_result=gates_result,
            dod_result=dod_result,
            validation_result=validation_result,
            custom_data=custom_data
        )
        
        # Exportar a Markdown
        markdown = _evidence_generator.export_evidence_to_markdown(evidence)
        
        return {
            "success": True,
            "evidence": evidence,
            "markdown": markdown,
            "message": "Evidencia generada exitosamente"
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def generate_unified_diff(
    file_path: str,
    original_content: str,
    modified_content: str
) -> Dict[str, Any]:
    """
    Genera unified diff entre contenido original y modificado.
    
    Args:
        file_path: Ruta del archivo
        original_content: Contenido original
        modified_content: Contenido modificado
    
    Returns:
        Diff unificado con estadísticas
    """
    print(f"\n📝 [DIFF] Generando diff para: {file_path}...")
    
    try:
        diff_result = _evidence_generator.generate_unified_diff(
            file_path=file_path,
            original_content=original_content,
            modified_content=modified_content
        )
        
        print(f"   +{diff_result['stats']['additions']} -{diff_result['stats']['deletions']}")
        
        return {
            "success": True,
            "diff": diff_result
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def create_incremental_commit(
    message: str,
    files_to_add: List[str] = None,
    include_dod: bool = True,
    dod_data: Dict = None,
    evidence_data: Dict = None
) -> Dict[str, Any]:
    """
    Crea un commit incremental siguiendo ModoGorila.
    Verifica límite ≤200 líneas y genera mensaje estructurado.
    
    Args:
        message: Mensaje base del commit
        files_to_add: Archivos a agregar (None = todos)
        include_dod: Si debe incluir DoD en mensaje
        dod_data: Datos de DoD para incluir
        evidence_data: Datos de evidencia para incluir
    
    Returns:
        Resultado del commit con hash y estadísticas
    """
    print(f"\n💾 [COMMIT] Creando commit incremental...")
    
    try:
        # Analizar tamaño de cambios primero
        change_analysis = _incremental_committer.analyze_change_size(files_to_add)
        
        if not change_analysis.get("within_limit", True):
            print(f"   ⚠️  Cambios exceden límite: {change_analysis['total_changes']} > 200 líneas")
            print(f"   💡 Recomendación: Dividir en múltiples commits")
        
        # Crear commit
        result = _incremental_committer.create_commit(
            message=message,
            files_to_add=files_to_add,
            include_dod=include_dod,
            dod_data=dod_data,
            evidence_data=evidence_data
        )
        
        if result.get("success"):
            print(f"   ✅ Commit creado: {result.get('commit_hash', 'N/A')[:8]}")
            print(f"   📊 Cambios: {result['changes']['total_changes']} líneas")
        
        return result
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def check_git_status() -> Dict[str, Any]:
    """
    Verifica el estado del repositorio Git.
    
    Returns:
        Estado con archivos modificados, staged, untracked
    """
    print(f"\n📂 [GIT] Verificando estado del repositorio...")
    
    try:
        status = _incremental_committer.check_git_status()
        
        if status.get("is_git_repo"):
            print(f"   ✅ Repositorio Git válido")
            print(f"   📝 Cambios: {status.get('total_changes', 0)}")
        else:
            print(f"   ❌ No es un repositorio Git")
        
        return {
            "success": True,
            "status": status
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def batch_add_curl_to_php_files(limit: int = 50) -> Dict[str, Any]:
    """
    Procesa múltiples archivos PHP del RAG y genera curl para todos.
    """
    print(f"📦 Procesando archivos PHP del RAG (límite: {limit})...")
    
    try:
        # Buscar todos los archivos PHP en el RAG
        php_files = _rag_storage.search_by_type("php")
        
        if not php_files:
            return {
                "success": False,
                "error": "No se encontraron archivos PHP en el RAG"
            }
        
        # Limitar cantidad
        php_files = php_files[:limit]
        
        results = {
            "total_files": len(php_files),
            "processed": 0,
            "success": 0,
            "failed": 0,
            "files_processed": []
        }
        
        for doc in php_files:
            file_path = doc["file_path"]
            result = add_curl_test_to_php(file_path)
            
            results["processed"] += 1
            if result.get("success"):
                results["success"] += 1
                results["files_processed"].append({
                    "file": Path(file_path).name,
                    "curl": result.get("curl_command", "")[:100]
                })
            else:
                results["failed"] += 1
        
        print(f"✅ Procesados {results['processed']} archivos PHP: {results['success']} éxito, {results['failed']} fallos")
        
        return {
            "success": True,
            **results
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Error en procesamiento batch: {str(e)}"
        }


def list_directory_recursive_wrapper(
    directory_path: str,
    extensions: List[str] = None,
    max_depth: int = None,
    include_hidden: bool = False
) -> Dict[str, Any]:
    """
    [PLAN EXECUTOR] Lista TODOS los archivos en un directorio recursivamente.
    Sin límites artificiales, filtra por extensión si se necesita.
    """
    return list_directory_recursive(
        directory_path=directory_path,
        extensions=extensions,
        max_depth=max_depth,
        include_hidden=include_hidden
    )


def execute_plan(plan: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    [PLAN EXECUTOR] Ejecuta un plan generado por el Architect paso a paso.
    Registra evidencia y maneja errores con reintentos.
    """
    global _plan_executor
    
    # Inicializar executor si no existe
    if _plan_executor is None:
        _plan_executor = PlanExecutor(TOOL_FUNCTIONS)
    
    return _plan_executor.execute_plan(plan, context)


def supervise_plan_execution(
    plan: Dict[str, Any],
    context: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    [SUPERVISOR] Ejecuta y valida un plan completo con reintentos inteligentes.
    El supervisor LLM verifica cumplimiento de DoD y decide si reintentar o escalar.
    """
    global _plan_executor, _plan_supervisor
    
    # Inicializar si no existen
    if _plan_executor is None:
        _plan_executor = PlanExecutor(TOOL_FUNCTIONS)
    
    if _plan_supervisor is None:
        from openai import OpenAI
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        _plan_supervisor = PlanSupervisor(client)
    
    return _plan_supervisor.supervise_plan_execution(plan, _plan_executor, context)


# Registro de funciones disponibles
TOOL_FUNCTIONS = {
    "generate_analysis_plan": generate_analysis_plan,
    "validate_contract": validate_contract,
    "check_dod_compliance": check_dod_compliance,
    "run_quality_gates": run_quality_gates,
    "generate_execution_evidence": generate_execution_evidence,
    "generate_unified_diff": generate_unified_diff,
    "create_incremental_commit": create_incremental_commit,
    "check_git_status": check_git_status,
    "list_directory_recursive": list_directory_recursive_wrapper,
    "execute_plan": execute_plan,
    "supervise_plan_execution": supervise_plan_execution,
    "list_files_in_dir": list_files_in_dir,
    "explore_directory": explore_directory,
    "read_file": read_file,
    "analyze_file": analyze_file,
    "analyze_directory": analyze_directory,
    "search_in_rag": search_in_rag,
    "get_rag_statistics": get_rag_statistics,
    "create_file": create_file,
    "write_file": write_file,
    "append_to_file": append_to_file,
    "generate_documentation": generate_documentation,
    "open_file_in_editor": open_file_in_editor,
    # Dependencias
    "check_dependencies": check_dependencies,
    "security_audit": security_audit,
    "generate_dependency_graph": generate_dependency_graph,
    "find_outdated_packages": find_outdated_packages,
    # Generación de código
    "generate_tests": generate_tests,
    "generate_docstrings": generate_docstrings,
    "generate_config_files": generate_config_files,
    "generate_dockerfile": generate_dockerfile,
    # Asistencia interactiva
    "explain_code": explain_code,
    "debug_assistant": debug_assistant,
    "code_review": code_review,
    # Integraciones externas
    "search_stackoverflow": search_stackoverflow,
    "fetch_api_docs": fetch_api_docs,
    # Reportes
    "generate_html_dashboard": generate_html_dashboard,
    "technical_debt_report": technical_debt_report,
    # CI/CD
    "run_linters": run_linters,
    "run_tests": run_tests,
    "check_build": check_build,
    "deployment_check": deployment_check,
    # PHP Testing & Diagrams
    "add_diagram_to_php": add_diagram_to_php,
    "add_curl_test_to_php": add_curl_test_to_php,
    "test_php_endpoint": test_php_endpoint,
    "batch_add_curl_to_php_files": batch_add_curl_to_php_files,
}

# Definición de herramientas para OpenAI
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "generate_analysis_plan",
            "description": "🏗️ [ARQUITECTO] Genera un plan de análisis estructurado siguiendo ModoGorila. Crea Spec Pack, contratos, DoD, TestPlan y pasos incrementales. USA ESTA HERRAMIENTA PRIMERO antes de explorar o analizar un repositorio completo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repository_path": {
                        "type": "string",
                        "description": "Ruta del repositorio a analizar"
                    },
                    "user_requirements": {
                        "type": "string",
                        "description": "Descripción detallada de lo que el usuario necesita: análisis completo, búsqueda específica, auditoría, documentación, etc."
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["full", "quick", "targeted"],
                        "description": "Alcance: full=análisis exhaustivo completo, quick=exploración rápida de estructura, targeted=análisis enfocado en archivos/módulos específicos"
                    }
                },
                "required": ["repository_path", "user_requirements"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "validate_contract",
            "description": "📋 Valida un output contra un JSON Schema. Verifica que los datos cumplan con el contrato especificado (schemas predefinidos: analysis_result, exploration_result, plan_result).",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "object",
                        "description": "Datos a validar (objeto JSON)"
                    },
                    "schema_name": {
                        "type": "string",
                        "enum": ["analysis_result", "exploration_result", "plan_result"],
                        "description": "Nombre del schema predefinido a usar"
                    },
                    "custom_schema": {
                        "type": "object",
                        "description": "Schema personalizado en formato JSON Schema (si no se usa schema predefinido)"
                    }
                },
                "required": ["data"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_dod_compliance",
            "description": "✅ Verifica cumplimiento de Definition of Done. Valida que se cumplan criterios de aceptación, checklist y métricas del plan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dod": {
                        "type": "object",
                        "description": "Definition of Done del plan (debe incluir: checklist, acceptance_criteria, metrics)"
                    },
                    "execution_evidence": {
                        "type": "object",
                        "description": "Evidencia de ejecución con resultados, stats, métricas alcanzadas"
                    }
                },
                "required": ["dod", "execution_evidence"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_quality_gates",
            "description": "🚦 Ejecuta gates de calidad: sintaxis/compilación, linters, tests. Self-check obligatorio antes de continuar con siguiente paso.",
            "parameters": {
                "type": "object",
                "properties": {
                    "check_build": {
                        "type": "boolean",
                        "description": "Si debe verificar sintaxis/compilación (default: true)"
                    },
                    "check_lint": {
                        "type": "boolean",
                        "description": "Si debe ejecutar linters (default: true)"
                    },
                    "check_tests": {
                        "type": "boolean",
                        "description": "Si debe ejecutar tests (default: false, ya que puede ser lento)"
                    },
                    "files_to_check": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Lista de archivos específicos a verificar (null = todos los .py)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_execution_evidence",
            "description": "📋 Genera evidencia estructurada completa de ejecución de un paso. Incluye gates, DoD, validaciones y métricas en formato estándar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "step_title": {
                        "type": "string",
                        "description": "Título descriptivo del paso ejecutado"
                    },
                    "gates_result": {
                        "type": "object",
                        "description": "Resultado de quality gates ejecutados"
                    },
                    "dod_result": {
                        "type": "object",
                        "description": "Resultado de verificación de DoD"
                    },
                    "validation_result": {
                        "type": "object",
                        "description": "Resultado de validación de contratos"
                    },
                    "custom_data": {
                        "type": "object",
                        "description": "Datos adicionales personalizados para incluir en la evidencia"
                    }
                },
                "required": ["step_title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_unified_diff",
            "description": "📝 Genera unified diff entre contenido original y modificado de un archivo. Útil para documentar cambios exactos con estadísticas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Ruta del archivo"
                    },
                    "original_content": {
                        "type": "string",
                        "description": "Contenido original del archivo"
                    },
                    "modified_content": {
                        "type": "string",
                        "description": "Contenido modificado del archivo"
                    }
                },
                "required": ["file_path", "original_content", "modified_content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_incremental_commit",
            "description": "💾 Crea un commit incremental siguiendo ModoGorila. Verifica límite ≤200 líneas, genera mensaje estructurado con DoD y evidencia.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Mensaje base del commit (ej: 'feat: Implementar X', 'fix: Corregir Y')"
                    },
                    "files_to_add": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Lista de archivos a agregar al commit (null = todos los modificados)"
                    },
                    "include_dod": {
                        "type": "boolean",
                        "description": "Si debe incluir DoD en el mensaje del commit (default: true)"
                    },
                    "dod_data": {
                        "type": "object",
                        "description": "Datos de DoD para incluir en el mensaje"
                    },
                    "evidence_data": {
                        "type": "object",
                        "description": "Datos de evidencia (gates, validaciones) para incluir"
                    }
                },
                "required": ["message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_git_status",
            "description": "📂 Verifica el estado del repositorio Git. Retorna archivos modificados, staged, untracked y estadísticas.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory_recursive",
            "description": "📂 [ESCANEO RECURSIVO] Lista TODOS los archivos en un directorio y subdirectorios. Filtra por extensión (ej: ['.php', '.py']). Retorna árbol completo con estadísticas. Perfecto para descubrir archivos que explore_directory no detectó.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory_path": {
                        "type": "string",
                        "description": "Ruta del directorio a escanear recursivamente"
                    },
                    "extensions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Lista de extensiones a filtrar (ej: ['.php', '.py', '.js']). null = todos los archivos"
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Profundidad máxima (null = sin límite, recomendado)"
                    },
                    "include_hidden": {
                        "type": "boolean",
                        "description": "Incluir archivos/carpetas ocultos (default: false)"
                    }
                },
                "required": ["directory_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_plan",
            "description": "⚙️ [EJECUTOR] Ejecuta un plan generado por generate_analysis_plan paso a paso. Registra evidencia, maneja errores con reintentos automáticos (max 2).",
            "parameters": {
                "type": "object",
                "properties": {
                    "plan": {
                        "type": "object",
                        "description": "Plan completo del Architect con execution_steps"
                    },
                    "context": {
                        "type": "object",
                        "description": "Contexto adicional (rutas, parámetros) para sustituir variables ${var}"
                    }
                },
                "required": ["plan"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "supervise_plan_execution",
            "description": "👁️ [SUPERVISOR] Ejecuta y valida un plan completo con LLM supervisor. Verifica DoD, detecta problemas, reintenta automáticamente si es posible, o escala al usuario si falla. USA ESTA HERRAMIENTA después de generate_analysis_plan para ejecutar y validar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "plan": {
                        "type": "object",
                        "description": "Plan completo del Architect con execution_steps y DoD"
                    },
                    "context": {
                        "type": "object",
                        "description": "Contexto adicional (rutas, parámetros)"
                    }
                },
                "required": ["plan"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "explore_directory",
            "description": "Explora un directorio exhaustivamente y retorna su estructura completa con detección de arquitectura, frameworks, entry points, dependencias. SIN LÍMITES de profundidad por defecto. Ignora automáticamente archivos binarios y directorios comunes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Ruta del directorio a explorar"
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Si debe explorar subdirectorios recursivamente (default: true)"
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Profundidad máxima de exploración. null=sin límite (recomendado para análisis exhaustivo), número=limitar a N niveles"
                    },
                    "analyze_architecture": {
                        "type": "boolean",
                        "description": "Si debe detectar patrones arquitectónicos, frameworks, entry points, dependencias (default: true)"
                    }
                },
                "required": ["directory"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Lee el contenido completo de un archivo de texto. No funciona con archivos binarios.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Ruta completa del archivo a leer"
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_file",
            "description": "Analiza un archivo de código o documentación usando un LLM especializado. Extrae funciones, clases, imports, documentación y guarda el resultado en el RAG para consultas futuras.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Ruta completa del archivo a analizar"
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_directory",
            "description": "Analiza todos los archivos de código en un directorio completo y guarda los resultados en el RAG. Proceso que puede tomar varios minutos dependiendo del número de archivos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Ruta del directorio a analizar"
                    },
                    "file_extensions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Lista opcional de extensiones a analizar (ej: ['.py', '.js']). Si se omite, analiza todos los tipos soportados."
                    }
                },
                "required": ["directory"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_in_rag",
            "description": "Busca información en el RAG (base de conocimiento de archivos analizados). Puede buscar por palabra clave, nombre de función o tipo de archivo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Texto o término a buscar"
                    },
                    "search_type": {
                        "type": "string",
                        "enum": ["keyword", "function", "type"],
                        "description": "Tipo de búsqueda: 'keyword' (busca en nombres y resúmenes), 'function' (busca funciones específicas), 'type' (busca por tipo de archivo como 'python', 'javascript')"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_rag_statistics",
            "description": "Obtiene estadísticas sobre los archivos almacenados en el RAG: total de documentos, distribución por tipo, fechas, etc.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files_in_dir",
            "description": "Lista simple de archivos en un directorio (sin información detallada). Para exploración completa usa explore_directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directorio a listar (default: directorio actual)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Crea un nuevo archivo con el contenido especificado. Falla si el archivo ya existe.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Ruta completa del archivo a crear"
                    },
                    "content": {
                        "type": "string",
                        "description": "Contenido del archivo a crear"
                    }
                },
                "required": ["file_path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Escribe/sobrescribe el contenido completo de un archivo. Puede crear el archivo si no existe.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Ruta completa del archivo"
                    },
                    "content": {
                        "type": "string",
                        "description": "Contenido completo a escribir en el archivo"
                    },
                    "create_if_missing": {
                        "type": "boolean",
                        "description": "Si debe crear el archivo si no existe (default: true)"
                    }
                },
                "required": ["file_path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "append_to_file",
            "description": "Agrega contenido al final de un archivo existente sin sobrescribir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Ruta completa del archivo existente"
                    },
                    "content": {
                        "type": "string",
                        "description": "Contenido a agregar al final del archivo"
                    }
                },
                "required": ["file_path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_documentation",
            "description": "Genera documentación completa en formato Markdown para un directorio analizado. Incluye resúmenes de archivos, funciones, clases y diagramas UML en Mermaid. El directorio debe haber sido analizado previamente con analyze_directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directorio para el cual generar documentación (debe estar analizado en RAG)"
                    },
                    "output_file": {
                        "type": "string",
                        "description": "Ruta del archivo Markdown de salida (opcional, se genera automáticamente si se omite)"
                    },
                    "include_diagrams": {
                        "type": "boolean",
                        "description": "Si debe incluir diagramas UML en formato Mermaid (default: true)"
                    }
                },
                "required": ["directory"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_file_in_editor",
            "description": "Abre un archivo en el editor VS Code para que el usuario lo edite. Útil cuando el usuario necesita revisar o modificar manualmente un archivo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Ruta completa del archivo a abrir en el editor"
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_dependencies",
            "description": "Verifica las dependencias del proyecto y su estado. Parsea requirements.txt o package.json.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Ruta del proyecto a analizar"
                    }
                },
                "required": ["project_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "security_audit",
            "description": "Realiza auditoría de seguridad en las dependencias del proyecto. Identifica vulnerabilidades conocidas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Ruta del proyecto a auditar"
                    }
                },
                "required": ["project_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_dependency_graph",
            "description": "Genera un grafo de dependencias en formato Mermaid.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Ruta del proyecto"
                    },
                    "output_file": {
                        "type": "string",
                        "description": "Archivo de salida opcional"
                    }
                },
                "required": ["project_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_outdated_packages",
            "description": "Encuentra paquetes desactualizados y sus versiones más recientes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Ruta del proyecto"
                    }
                },
                "required": ["project_path"]
            }
        }
    },
    # === HERRAMIENTAS DE GENERACIÓN DE CÓDIGO ===
    {
        "type": "function",
        "function": {
            "name": "generate_tests",
            "description": "Genera tests unitarios para un archivo de código usando pytest o unittest.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Ruta del archivo a testear"
                    },
                    "test_framework": {
                        "type": "string",
                        "description": "Framework de testing: pytest o unittest"
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_docstrings",
            "description": "Genera docstrings para un archivo de código en estilo Google o Numpy.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Ruta del archivo"
                    },
                    "style": {
                        "type": "string",
                        "description": "Estilo de docstring: google o numpy"
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_config_files",
            "description": "Genera archivos de configuración (.gitignore, setup.py, requirements.txt, etc).",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Ruta del proyecto"
                    },
                    "files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Lista de archivos a generar: gitignore, readme, setup, requirements"
                    }
                },
                "required": ["project_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_dockerfile",
            "description": "Genera un Dockerfile optimizado para el proyecto.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Ruta del proyecto"
                    },
                    "language": {
                        "type": "string",
                        "description": "Lenguaje del proyecto: python, nodejs, java, etc"
                    }
                },
                "required": ["project_path"]
            }
        }
    },
    # === HERRAMIENTAS DE ASISTENCIA INTERACTIVA ===
    {
        "type": "function",
        "function": {
            "name": "explain_code",
            "description": "Explica el código de un archivo en diferentes niveles de detalle.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Ruta del archivo a explicar"
                    },
                    "detail_level": {
                        "type": "string",
                        "description": "Nivel de detalle: beginner, intermediate, expert"
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "debug_assistant",
            "description": "Asiste en la depuración de código, identifica problemas y sugiere soluciones.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Ruta del archivo con problemas"
                    },
                    "error_message": {
                        "type": "string",
                        "description": "Mensaje de error opcional"
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "code_review",
            "description": "Realiza una revisión de código desde la perspectiva de un desarrollador senior.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Ruta del archivo a revisar"
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    # === HERRAMIENTAS DE INTEGRACIÓN EXTERNA ===
    {
        "type": "function",
        "function": {
            "name": "search_stackoverflow",
            "description": "Busca soluciones en StackOverflow y las resume con IA.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Consulta de búsqueda"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Número máximo de resultados (default: 5)"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_api_docs",
            "description": "Obtiene documentación comprensiva de APIs o paquetes usando IA.",
            "parameters": {
                "type": "object",
                "properties": {
                    "package_name": {
                        "type": "string",
                        "description": "Nombre del paquete o API"
                    },
                    "language": {
                        "type": "string",
                        "description": "Lenguaje de programación: python, javascript, etc"
                    }
                },
                "required": ["package_name"]
            }
        }
    },
    # === HERRAMIENTAS DE REPORTES ===
    {
        "type": "function",
        "function": {
            "name": "generate_html_dashboard",
            "description": "Genera un dashboard HTML interactivo del proyecto con estadísticas y gráficos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directorio del proyecto"
                    },
                    "output_file": {
                        "type": "string",
                        "description": "Archivo HTML de salida opcional"
                    }
                },
                "required": ["directory"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "technical_debt_report",
            "description": "Genera reporte de deuda técnica: código duplicado, complejidad, problemas de arquitectura.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directorio del proyecto a analizar"
                    }
                },
                "required": ["directory"]
            }
        }
    },
    # === HERRAMIENTAS DE CI/CD ===
    {
        "type": "function",
        "function": {
            "name": "run_linters",
            "description": "Ejecuta linters (pylint, flake8, eslint) en el proyecto.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directorio del proyecto"
                    },
                    "linters": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Lista de linters a ejecutar"
                    }
                },
                "required": ["directory"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "Ejecuta tests del proyecto con pytest, unittest o jest.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directorio del proyecto"
                    },
                    "framework": {
                        "type": "string",
                        "description": "Framework de testing: pytest, unittest, jest"
                    }
                },
                "required": ["directory"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_build",
            "description": "Verifica que el proyecto compile/build correctamente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directorio del proyecto"
                    }
                },
                "required": ["directory"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "deployment_check",
            "description": "Verifica readiness de deployment: README, tests, secretos, dependencias.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directorio del proyecto"
                    }
                },
                "required": ["directory"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_diagram_to_php",
            "description": "Guarda un diagrama Mermaid (.mmd) como metadatos en el RAG para un archivo PHP. NO CREA archivos .mmd físicos, solo actualiza el RAG. Usa esto cuando necesites crear diagramas de flujo, secuencia, clases, etc para documentar archivos PHP.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Ruta completa del archivo PHP en el RAG (ej: \\\\172.16.2.181\\ms4w\\apps\\GeoPROCESO\\htdocs\\php\\acercarxy.php)"
                    },
                    "diagram_content": {
                        "type": "string",
                        "description": "Contenido del diagrama Mermaid (ej: 'graph TD;\\n    A[Inicio] --> B[Proceso];')"
                    },
                    "diagram_type": {
                        "type": "string",
                        "description": "Tipo de diagrama: flowchart, sequence, class, state, er, gantt (default: flowchart)"
                    }
                },
                "required": ["file_path", "diagram_content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_curl_test_to_php",
            "description": "Analiza un archivo PHP del RAG, genera comandos curl de prueba automáticamente y los guarda en los metadatos del RAG. NO CREA archivos PHP nuevos, solo actualiza el RAG con información de testing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Ruta completa del archivo PHP en el RAG (ej: \\\\172.16.2.181\\ms4w\\apps\\GeoPROCESO\\htdocs\\php\\capas_dinamicas\\cortesyreconexiones\\carga_folios.php)"
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "test_php_endpoint",
            "description": "Ejecuta el comando curl guardado en el RAG para probar un endpoint PHP y valida la respuesta.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Ruta del archivo PHP cuyo curl se ejecutará"
                    },
                    "custom_params": {
                        "type": "object",
                        "description": "Parámetros personalizados para sobrescribir los valores por defecto (opcional)"
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "batch_add_curl_to_php_files",
            "description": "Procesa múltiples archivos PHP del RAG y genera comandos curl para todos ellos. Ideal para agregar testing a todos los endpoints PHP del proyecto.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Número máximo de archivos PHP a procesar (default: 50, evita sobrecarga)"
                    }
                },
                "required": []
            }
        }
    }
]
