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
    MAX_FILE_SIZE_MB, SHOW_PERMISSION_WARNINGS
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


def explore_directory(directory: str, recursive: bool = True, max_depth: int = 10) -> Dict[str, Any]:
    """
    Explora un directorio y retorna su estructura.
    
    Args:
        directory: Ruta del directorio a explorar
        recursive: Si debe explorar subdirectorios
        max_depth: Profundidad máxima de exploración
    """
    print(f"⚙️ Explorando directorio: {directory}")
    
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
                "ignored": 0
            }
        }
        
        def explore_recursive(current_path: Path, depth: int = 0):
            if depth > max_depth:
                return
            
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
                    
                    elif item.is_dir() and recursive:
                        result["subdirectories"].append(str(item))
                        explore_recursive(item, depth + 1)
            
            except PermissionError:
                if SHOW_PERMISSION_WARNINGS:
                    print(f"⚠️ Sin permisos para acceder: {current_path}")
                pass  # Silenciar warnings de permisos de carpetas del sistema
        
        explore_recursive(path)
        
        print(f"✅ Exploración completada: {result['stats']['total_files']} archivos encontrados")
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
    Analiza un archivo usando el LLM analizador y guarda en RAG.
    
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
    
    # Guardar en RAG
    doc_id = _rag_storage.save_analysis(file_data["file_path"], analysis)
    
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


# Registro de funciones disponibles
TOOL_FUNCTIONS = {
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
            "name": "explore_directory",
            "description": "Explora un directorio y retorna su estructura completa con archivos y subdirectorios. Ignora automáticamente archivos binarios y directorios comunes como node_modules, __pycache__, etc.",
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
                        "description": "Profundidad máxima de exploración (default: 10)"
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
