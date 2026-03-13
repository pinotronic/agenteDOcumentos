"""
Módulo de herramientas para el agente orquestador.
Define las funciones que el agente puede usar para análisis de código.
"""
import os
import json
import subprocess
import hashlib
import re
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from collections import defaultdict

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
from intra_repo_tracing import detect_intra_repo_dependencies, detect_intra_repo_calls
from conversation_memory import ConversationMemory
from code_generator_agent import get_code_generator

# Instancias globales
_rag_storage = RAGStorage()
_conversation_memory = None  # Se inicializa bajo demanda para evitar conflictos
_code_gen_agent = None  # Se inicializa bajo demanda
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

    # Enriquecer relaciones con trazabilidad determinista (archivo -> archivo)
    try:
        relationships = analysis.get("relationships")
        if not isinstance(relationships, dict):
            relationships = {
                "intra_repo_dependencies": [],
                "cross_service_calls": [],
                "datastores": [],
                "events_or_queues": [],
                "exposed_endpoints": []
            }
            analysis["relationships"] = relationships

        trace = detect_intra_repo_dependencies(
            file_path=file_data["file_path"],
            content=file_data["content"],
            file_type=file_data["type"],
            repo_root=str(Path.cwd().resolve()),
        )

        if trace.resolved_file_paths:
            # Preservar lo que haya venido del LLM (módulos/strings) pero priorizar paths reales
            existing = relationships.get("intra_repo_dependencies") or []
            if isinstance(existing, list) and existing:
                # Heurística: si no parece path, guardarlo como módulo
                existing_modules = [x for x in existing if isinstance(x, str) and ("/" not in x and "\\" not in x and not x.lower().endswith((".py", ".js", ".ts", ".php")))]
                if existing_modules:
                    relationships["intra_repo_dependencies_modules"] = list(dict.fromkeys(existing_modules))

            # `intra_repo_dependencies` se convierte en lista de archivos (trazabilidad real)
            relationships["intra_repo_dependencies"] = list(dict.fromkeys(trace.resolved_file_paths))

        if trace.unresolved_refs:
            relationships["intra_repo_dependencies_unresolved"] = trace.unresolved_refs[:50]

        # Trazabilidad de comunicación (calls) intra-repo (inicialmente Python)
        calls = detect_intra_repo_calls(
            file_path=file_data["file_path"],
            content=file_data["content"],
            file_type=file_data["type"],
            repo_root=str(Path.cwd().resolve()),
        )
        if calls.called_file_paths:
            relationships["intra_repo_calls"] = calls.called_file_paths
        if calls.unresolved_call_refs:
            relationships["intra_repo_calls_unresolved"] = calls.unresolved_call_refs[:50]
    except Exception as e:
        # No romper el pipeline por trazabilidad
        analysis.setdefault("relationships", {}).setdefault("intra_repo_dependencies_trace_error", str(e))
    
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
            doc_id = result.get("document_id")
            results["analyzed"].append({
                "file": file_info["path"],
                "document_id": doc_id,
                "saved_to_rag": result.get("saved_to_rag", bool(doc_id)),
                "reason": result.get("reason")
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
    print("[RAG] Obteniendo estadisticas del RAG")
    return _rag_storage.get_statistics()


def query_memory(
    query: str = None,
    action: str = "search",
    category: str = None,
    limit: int = 5
) -> Dict[str, Any]:
    """
    Consulta la memoria conversacional del agente.
    Permite buscar conversaciones previas, hechos almacenados y contexto de sesiones.

    Args:
        query: Texto a buscar (para action=search)
        action: search|facts|history|stats
        category: Categoría de hechos (tech_stack, project_info, preferences, workflow)
        limit: Máximo de resultados

    Returns:
        Información de memoria encontrada
    """
    global _conversation_memory

    print(f"[MEMORIA] Consultando: action={action}, query={query[:30] if query else 'N/A'}...")

    try:
        # Inicializar memoria si no existe
        if _conversation_memory is None:
            _conversation_memory = ConversationMemory(user_id="default")

        result = {
            "success": True,
            "action": action,
            "data": None
        }

        if action == "search" and query:
            # Búsqueda semántica en conversaciones
            similar = _conversation_memory.search_similar_conversations(
                query=query,
                limit=limit
            )
            result["data"] = {
                "query": query,
                "matches": similar,
                "count": len(similar)
            }

        elif action == "facts":
            # Obtener hechos almacenados
            facts = _conversation_memory.get_facts(category=category)
            result["data"] = {
                "facts": facts,
                "count": len(facts),
                "summary": _conversation_memory.get_facts_summary()
            }

        elif action == "history":
            # Historial de sesión actual
            session_id = _conversation_memory._get_or_create_session()
            history = _conversation_memory.get_session_history(session_id, limit=limit)
            result["data"] = {
                "session_id": session_id,
                "messages": history,
                "count": len(history)
            }

        elif action == "stats":
            # Estadísticas de memoria
            stats = _conversation_memory.get_statistics()
            result["data"] = stats

        elif action == "context":
            # Contexto reciente formateado
            context = _conversation_memory.get_recent_context(limit=limit)
            result["data"] = {
                "context": context,
                "chars": len(context)
            }

        else:
            return {"success": False, "error": f"Accion no reconocida: {action}"}

        return result

    except Exception as e:
        return {"success": False, "error": str(e)}


def get_relationship_graph(scope: str = None, include_external: bool = True) -> Dict[str, Any]:
    """Construye un grafo ligero de relaciones entre archivos/servicios/datos desde el RAG."""
    print(f"?? Construyendo grafo de relaciones (scope={scope})")
    return _rag_storage.get_relationship_graph(file_filter=scope, include_external=include_external)


def get_file_trace(file_path: str, include_external: bool = False) -> Dict[str, Any]:
    """Retorna trazabilidad entrante/saliente (calls/depends_on) para un archivo."""
    print(f"?? Trazabilidad de archivo: {file_path}")
    try:
        resolved = str(Path(file_path).resolve())
    except Exception:
        resolved = file_path
    return _rag_storage.get_file_trace(file_path=resolved, include_external=include_external)


def get_trace_hotspots(scope: str = None, include_external: bool = False, top_n: int = 20) -> Dict[str, Any]:
    """Retorna rankings de hotspots de comunicación/dependencias (calls/depends_on)."""
    print(f"?? Hotspots de trazabilidad (scope={scope}, top_n={top_n})")
    return _rag_storage.get_trace_hotspots(scope=scope, include_external=include_external, top_n=top_n)


def generate_trace_report(scope: str = None, include_external: bool = False, top_n: int = 20, output_file: str = None) -> Dict[str, Any]:
    """Genera un reporte Markdown de trazabilidad (hotspots + previews) y lo guarda en archivo."""
    print(f"?? Generando reporte de trazabilidad (scope={scope}, top_n={top_n})")
    try:
        out = Path(output_file).resolve() if output_file else (Path.cwd() / "TRACEABILITY_REPORT.md").resolve()
    except Exception:
        out = Path.cwd() / "TRACEABILITY_REPORT.md"

    md = _rag_storage.generate_trace_report_markdown(
        scope=scope,
        include_external=include_external,
        top_n=top_n,
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    return {"success": True, "output_file": str(out), "bytes": out.stat().st_size}


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
        import shutil
        
        # Verificar que el archivo existe
        file_path_obj = Path(file_path)
        
        if not file_path_obj.exists():
            return {
                "error": f"El archivo no existe: {file_path}",
                "success": False
            }
        
        # Obtener ruta absoluta
        abs_path = str(file_path_obj.absolute())
        
        # Estrategia 1: Intentar abrir con VS Code CLI
        vscode_commands = ['code', 'code.cmd', 'code-insiders']
        vscode_found = False
        
        for cmd in vscode_commands:
            if shutil.which(cmd):
                try:
                    result = subprocess.run(
                        [cmd, abs_path],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    
                    if result.returncode == 0:
                        print(f"✅ Archivo abierto en VS Code con comando: {cmd}")
                        return {
                            "success": True,
                            "file_path": abs_path,
                            "method": "vscode_cli",
                            "message": f"Archivo abierto en VS Code: {file_path_obj.name}"
                        }
                    vscode_found = True
                except Exception as e:
                    print(f"⚠️ Error con {cmd}: {e}")
                    continue
        
        # Estrategia 2: Usar editor predeterminado del sistema
        if os.name == 'nt':  # Windows
            try:
                os.startfile(abs_path)
                print(f"✅ Archivo abierto con editor predeterminado de Windows")
                return {
                    "success": True,
                    "file_path": abs_path,
                    "method": "windows_default",
                    "message": f"Archivo abierto con editor predeterminado: {file_path_obj.name}",
                    "note": "Si deseas usar VS Code, asegúrate de que esté instalado y en el PATH"
                }
            except Exception as e:
                return {
                    "error": f"No se pudo abrir el archivo: {str(e)}",
                    "success": False
                }
        else:  # Linux/Mac
            try:
                # Intentar xdg-open (Linux) o open (Mac)
                open_cmd = 'open' if os.uname().sysname == 'Darwin' else 'xdg-open'
                subprocess.run([open_cmd, abs_path], check=True)
                print(f"✅ Archivo abierto con comando: {open_cmd}")
                return {
                    "success": True,
                    "file_path": abs_path,
                    "method": "system_default",
                    "message": f"Archivo abierto con editor predeterminado: {file_path_obj.name}"
                }
            except Exception as e:
                return {
                    "error": f"No se pudo abrir el archivo: {str(e)}",
                    "success": False
                }
    
    except Exception as e:
        return {
            "error": f"Error inesperado: {str(e)}",
            "success": False,
            "file_path": file_path
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


# =============================================================================
# CODE GENERATOR AGENT - Generación de código multi-lenguaje
# =============================================================================

def ai_generate_code(
    specification: str,
    language: str = None,
    generation_type: str = "general",
    framework: str = None,
    output_file: str = None
) -> Dict[str, Any]:
    """
    [CODE-GENERATOR] Genera código basado en especificación en lenguaje natural.

    Args:
        specification: Descripción de lo que se quiere generar
        language: Lenguaje objetivo (python, javascript, typescript, php, java, go) - auto-detecta si None
        generation_type: Tipo de generación (general|api|crud|refactor)
        framework: Framework específico (fastapi, express, laravel, spring, gin, etc.)
        output_file: Archivo donde guardar el código (opcional)

    Returns:
        Código generado con validación de sintaxis
    """
    print(f"\n[AI-GENERATE] Generando código: {specification[:50]}...")

    try:
        agent = get_code_generator()
        result = agent.generate_code(
            specification=specification,
            language=language,
            generation_type=generation_type,
            framework=framework,
            output_file=output_file
        )
        return result

    except Exception as e:
        return {"success": False, "error": str(e)}


def ai_generate_api(
    endpoint_description: str,
    method: str = "GET",
    language: str = None,
    framework: str = None,
    include_tests: bool = False,
    output_file: str = None
) -> Dict[str, Any]:
    """
    [CODE-GENERATOR] Genera un endpoint de API REST completo.

    Args:
        endpoint_description: Descripción del endpoint (ej: "listar usuarios con paginación")
        method: HTTP method (GET, POST, PUT, DELETE, PATCH)
        language: Lenguaje (auto-detecta si None)
        framework: Framework (fastapi, express, laravel, spring, gin)
        include_tests: Si debe incluir tests del endpoint
        output_file: Archivo de salida

    Returns:
        Código del endpoint con validaciones y manejo de errores
    """
    print(f"\n[AI-GENERATE] Generando API {method}: {endpoint_description[:50]}...")

    try:
        agent = get_code_generator()
        result = agent.generate_api_endpoint(
            endpoint_spec=endpoint_description,
            method=method,
            language=language,
            framework=framework,
            include_tests=include_tests,
            output_file=output_file
        )
        return result

    except Exception as e:
        return {"success": False, "error": str(e)}


def ai_generate_crud(
    entity_name: str,
    fields: Dict[str, str],
    language: str = None,
    framework: str = None,
    include_soft_delete: bool = True,
    include_pagination: bool = True,
    output_dir: str = None
) -> Dict[str, Any]:
    """
    [CODE-GENERATOR] Genera operaciones CRUD completas para una entidad.

    Args:
        entity_name: Nombre de la entidad (ej: "User", "Product")
        fields: Campos de la entidad {"nombre": "tipo"} (ej: {"name": "string", "price": "float"})
        language: Lenguaje objetivo
        framework: Framework a usar
        include_soft_delete: Incluir borrado lógico
        include_pagination: Incluir paginación en listados
        output_dir: Directorio para guardar archivos

    Returns:
        Código CRUD completo (modelo, repositorio, servicio, controlador)
    """
    print(f"\n[AI-GENERATE] Generando CRUD para: {entity_name}")

    try:
        agent = get_code_generator()
        result = agent.generate_crud(
            entity_name=entity_name,
            fields=fields,
            language=language,
            framework=framework,
            include_soft_delete=include_soft_delete,
            include_pagination=include_pagination,
            output_dir=output_dir
        )
        return result

    except Exception as e:
        return {"success": False, "error": str(e)}


def ai_generate_function(
    name: str,
    description: str,
    parameters: Dict[str, str] = None,
    return_type: str = None,
    language: str = None,
    async_function: bool = False
) -> Dict[str, Any]:
    """
    [CODE-GENERATOR] Genera una función individual.

    Args:
        name: Nombre de la función
        description: Descripción de lo que hace la función
        parameters: Parámetros {"nombre": "tipo"}
        return_type: Tipo de retorno
        language: Lenguaje
        async_function: Si es función asíncrona

    Returns:
        Función generada con docstring y type hints
    """
    print(f"\n[AI-GENERATE] Generando función: {name}")

    try:
        agent = get_code_generator()
        result = agent.generate_function(
            name=name,
            description=description,
            parameters=parameters,
            return_type=return_type,
            language=language,
            async_function=async_function
        )
        return result

    except Exception as e:
        return {"success": False, "error": str(e)}


def ai_generate_class(
    name: str,
    description: str,
    attributes: Dict[str, str] = None,
    methods: List[Dict[str, str]] = None,
    language: str = None,
    parent_class: str = None
) -> Dict[str, Any]:
    """
    [CODE-GENERATOR] Genera una clase completa.

    Args:
        name: Nombre de la clase
        description: Descripción de la clase
        attributes: Atributos {"nombre": "tipo"}
        methods: Lista de métodos [{"name": "x", "description": "y", "params": "z"}]
        language: Lenguaje
        parent_class: Clase padre (herencia)

    Returns:
        Clase generada con constructor, métodos y docstrings
    """
    print(f"\n[AI-GENERATE] Generando clase: {name}")

    try:
        agent = get_code_generator()
        result = agent.generate_class(
            name=name,
            description=description,
            attributes=attributes,
            methods=methods,
            language=language,
            parent_class=parent_class
        )
        return result

    except Exception as e:
        return {"success": False, "error": str(e)}


def ai_refactor_code(
    file_path: str = None,
    code: str = None,
    instructions: str = "Mejora la calidad y legibilidad del código",
    output_file: str = None
) -> Dict[str, Any]:
    """
    [CODE-GENERATOR] Refactoriza código existente.

    Args:
        file_path: Ruta del archivo a refactorizar
        code: Código a refactorizar (alternativa a file_path)
        instructions: Instrucciones específicas de refactorización
        output_file: Archivo de salida (si None, sobreescribe original)

    Returns:
        Código refactorizado con lista de cambios realizados
    """
    print(f"\n[AI-GENERATE] Refactorizando: {file_path or 'código proporcionado'}")

    try:
        agent = get_code_generator()
        result = agent.refactor_code(
            file_path=file_path,
            code=code,
            instructions=instructions,
            output_file=output_file
        )
        return result

    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# AGENT SKILLS - Herramientas importadas de skills.sh
# =============================================================================

def git_safe_workflow(
    action: str,
    message: str = None,
    files: List[str] = None,
    branch: str = None,
    force: bool = False
) -> Dict[str, Any]:
    """
    [SKILL: git-safe-workflow] Operaciones Git seguras para agentes IA.
    Implementa protocolo de seguridad para prevenir operaciones destructivas.

    Args:
        action: Acción a realizar (status, diff, add, commit, branch, log, worktree_info)
        message: Mensaje de commit (solo para action=commit)
        files: Archivos específicos (para add/commit)
        branch: Nombre de rama (para branch/checkout)
        force: Forzar operación (requiere confirmación explícita)
    """
    print(f"\n🔒 [GIT-SAFE] Ejecutando: {action}")

    # Comandos prohibidos por defecto
    FORBIDDEN_COMMANDS = [
        "reset --hard",
        "clean -fd",
        "push --force",
        "push -f",
        "rebase"  # Sin solicitud explícita
    ]

    # Ramas protegidas
    PROTECTED_BRANCHES = ["main", "master", "develop", "production"]

    try:
        # Verificar que estamos en un repositorio Git
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, cwd=os.getcwd()
        )
        if result.returncode != 0:
            return {"success": False, "error": "No es un repositorio Git válido"}

        # Obtener información del repositorio
        root_result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True
        )
        repo_root = root_result.stdout.strip()

        branch_result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True
        )
        current_branch = branch_result.stdout.strip()

        response = {
            "success": True,
            "action": action,
            "repo_root": repo_root,
            "current_branch": current_branch,
            "warnings": []
        }

        if action == "status":
            # Estado seguro del repositorio
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True, text=True
            )

            diff_stat = subprocess.run(
                ["git", "diff", "--stat"],
                capture_output=True, text=True
            )

            response["status"] = {
                "files": status.stdout.strip().split("\n") if status.stdout.strip() else [],
                "diff_summary": diff_stat.stdout.strip(),
                "is_clean": len(status.stdout.strip()) == 0
            }
            status_files = response["status"]["files"]
            status_msg = "limpio" if response["status"]["is_clean"] else f"{len(status_files)} cambios"
            print(f"   📊 Estado: {status_msg}")

        elif action == "diff":
            # Mostrar diferencias
            diff = subprocess.run(
                ["git", "diff", "--stat"] + (files or []),
                capture_output=True, text=True
            )
            staged_diff = subprocess.run(
                ["git", "diff", "--cached", "--stat"],
                capture_output=True, text=True
            )

            response["diff"] = {
                "unstaged": diff.stdout.strip(),
                "staged": staged_diff.stdout.strip()
            }

        elif action == "add":
            # Agregar archivos al staging
            if not files:
                # Usar -u en lugar de -A para evitar agregar archivos nuevos accidentalmente
                add_result = subprocess.run(
                    ["git", "add", "-u"],
                    capture_output=True, text=True
                )
                response["added"] = "Archivos modificados (tracked)"
            else:
                add_result = subprocess.run(
                    ["git", "add"] + files,
                    capture_output=True, text=True
                )
                response["added"] = files

            if add_result.returncode != 0:
                return {"success": False, "error": add_result.stderr}
            print(f"   ✅ Archivos agregados al staging")

        elif action == "commit":
            if not message:
                return {"success": False, "error": "Se requiere mensaje de commit"}

            # Verificar HEAD separado
            head_check = subprocess.run(
                ["git", "symbolic-ref", "-q", "HEAD"],
                capture_output=True, text=True
            )
            if head_check.returncode != 0:
                response["warnings"].append("⚠️ HEAD separado detectado - considera crear una rama primero")
                if not force:
                    return {
                        "success": False,
                        "error": "HEAD separado. Usa force=True o crea una rama primero",
                        "suggestion": "git checkout -b nueva-rama"
                    }

            # Formato Conventional Commits
            if not re.match(r'^(feat|fix|docs|style|refactor|test|chore|perf|ci|build|revert)(\(.+\))?: .+', message):
                response["warnings"].append("⚠️ Mensaje no sigue Conventional Commits (feat|fix|docs|...)")

            commit_result = subprocess.run(
                ["git", "commit", "-m", message],
                capture_output=True, text=True
            )

            if commit_result.returncode != 0:
                return {"success": False, "error": commit_result.stderr}

            response["commit"] = {
                "message": message,
                "output": commit_result.stdout.strip()
            }
            print(f"   ✅ Commit creado: {message[:50]}...")

        elif action == "log":
            # Log seguro
            log_result = subprocess.run(
                ["git", "log", "--oneline", "-10"],
                capture_output=True, text=True
            )
            response["log"] = log_result.stdout.strip().split("\n")

        elif action == "branch":
            if branch:
                # Verificar si es rama protegida
                if branch in PROTECTED_BRANCHES and not force:
                    return {
                        "success": False,
                        "error": f"'{branch}' es rama protegida. Usa force=True si realmente necesitas modificarla",
                        "protected_branches": PROTECTED_BRANCHES
                    }

                # Crear nueva rama
                branch_result = subprocess.run(
                    ["git", "checkout", "-b", branch],
                    capture_output=True, text=True
                )
                if branch_result.returncode != 0:
                    # Intentar checkout si ya existe
                    branch_result = subprocess.run(
                        ["git", "checkout", branch],
                        capture_output=True, text=True
                    )

                response["branch_action"] = f"Cambiado a rama: {branch}"
            else:
                # Listar ramas
                branches = subprocess.run(
                    ["git", "branch", "-a"],
                    capture_output=True, text=True
                )
                response["branches"] = branches.stdout.strip().split("\n")

        elif action == "worktree_info":
            # Información de worktrees
            worktree = subprocess.run(
                ["git", "worktree", "list"],
                capture_output=True, text=True
            )
            response["worktrees"] = worktree.stdout.strip().split("\n")

        elif action == "push":
            # NUNCA push a ramas protegidas sin rama propia
            if current_branch in PROTECTED_BRANCHES and not force:
                return {
                    "success": False,
                    "error": f"No se permite push directo a '{current_branch}'. Crea una rama feature primero.",
                    "suggestion": f"git checkout -b feature/mi-cambio && git push -u origin feature/mi-cambio"
                }

            response["warnings"].append("⚠️ Push solo debe ejecutarse si el usuario lo solicita explícitamente")
            response["push_blocked"] = True
            response["reason"] = "Por seguridad, el push debe ser confirmado manualmente"

        else:
            return {"success": False, "error": f"Acción no reconocida: {action}"}

        return response

    except Exception as e:
        return {"success": False, "error": str(e)}


def security_leak_scan(
    directory: str = ".",
    scan_type: str = "full",
    fix_mode: bool = False
) -> Dict[str, Any]:
    """
    [SKILL: security-leak-guardrails] Escanea secretos y credenciales en el código.
    Detecta API keys, passwords, tokens y otros datos sensibles antes de commit.

    Args:
        directory: Directorio a escanear
        scan_type: Tipo de escaneo (full, staged, quick)
        fix_mode: Si debe sugerir correcciones
    """
    print(f"\n🔐 [SECURITY-SCAN] Escaneando: {directory}")

    # Patrones de secretos comunes
    SECRET_PATTERNS = {
        "api_key": [
            r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?',
            r'(?i)api[_-]?key\s*[=:]\s*["\']([^"\']+)["\']',
        ],
        "aws_credentials": [
            r'(?i)aws[_-]?(access[_-]?key[_-]?id|secret[_-]?access[_-]?key)\s*[=:]\s*["\']?([A-Z0-9]{16,})["\']?',
            r'AKIA[0-9A-Z]{16}',  # AWS Access Key ID
        ],
        "password": [
            r'(?i)(password|passwd|pwd|secret)\s*[=:]\s*["\']([^"\']{8,})["\']',
            r'(?i)(password|passwd|pwd)\s*[=:]\s*["\']?(?![\$\{])([a-zA-Z0-9!@#$%^&*]{8,})["\']?',
        ],
        "private_key": [
            r'-----BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----',
            r'-----BEGIN PGP PRIVATE KEY BLOCK-----',
        ],
        "token": [
            r'(?i)(bearer|token|auth[_-]?token|access[_-]?token)\s*[=:]\s*["\']?([a-zA-Z0-9_\-\.]{20,})["\']?',
            r'ghp_[a-zA-Z0-9]{36}',  # GitHub Personal Access Token
            r'gho_[a-zA-Z0-9]{36}',  # GitHub OAuth Token
            r'github_pat_[a-zA-Z0-9_]{22,}',  # GitHub PAT (new format)
        ],
        "connection_string": [
            r'(?i)(mongodb|mysql|postgresql|redis|amqp)://[^\s"\']+',
            r'(?i)server\s*=\s*[^;]+;\s*database\s*=\s*[^;]+;\s*(user|uid)\s*=',
        ],
        "jwt": [
            r'eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*',  # JWT Token
        ],
        "slack_webhook": [
            r'https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[a-zA-Z0-9]+',
        ],
        "stripe_key": [
            r'sk_live_[a-zA-Z0-9]{24,}',
            r'pk_live_[a-zA-Z0-9]{24,}',
        ],
    }

    # Archivos a ignorar
    IGNORE_PATTERNS = [
        r'\.git/',
        r'node_modules/',
        r'__pycache__/',
        r'\.pyc$',
        r'\.env\.example$',
        r'\.env\.template$',
        r'\.md$',  # Documentación
        r'package-lock\.json$',
        r'yarn\.lock$',
        r'\.min\.js$',
    ]

    # Archivos de alto riesgo
    HIGH_RISK_FILES = [
        '.env',
        '.env.local',
        '.env.production',
        'credentials.json',
        'secrets.json',
        'config.json',
        'settings.py',
        'config.py',
        '.npmrc',
        '.pypirc',
        'id_rsa',
        'id_dsa',
        'id_ecdsa',
        'id_ed25519',
    ]

    try:
        path = Path(directory).resolve()
        if not path.exists():
            return {"success": False, "error": f"Directorio no existe: {directory}"}

        results = {
            "success": True,
            "directory": str(path),
            "scan_type": scan_type,
            "findings": [],
            "high_risk_files": [],
            "statistics": {
                "files_scanned": 0,
                "secrets_found": 0,
                "high_risk_files": 0,
                "by_type": defaultdict(int)
            },
            "recommendations": []
        }

        # Obtener archivos a escanear
        if scan_type == "staged":
            # Solo archivos staged en git
            staged = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                capture_output=True, text=True, cwd=str(path)
            )
            files_to_scan = [path / f for f in staged.stdout.strip().split("\n") if f]
        else:
            # Todos los archivos
            files_to_scan = []
            for ext in ['*.py', '*.js', '*.ts', '*.json', '*.yml', '*.yaml', '*.env*', '*.php', '*.java', '*.go', '*.rb', '*.sh', '*.conf', '*.cfg', '*.ini']:
                files_to_scan.extend(path.rglob(ext))

        for file_path in files_to_scan:
            # Verificar si debe ignorarse
            should_ignore = False
            for pattern in IGNORE_PATTERNS:
                if re.search(pattern, str(file_path)):
                    should_ignore = True
                    break

            if should_ignore:
                continue

            # Verificar archivos de alto riesgo
            if file_path.name in HIGH_RISK_FILES:
                results["high_risk_files"].append(str(file_path))
                results["statistics"]["high_risk_files"] += 1

            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                results["statistics"]["files_scanned"] += 1

                # Buscar patrones de secretos
                for secret_type, patterns in SECRET_PATTERNS.items():
                    for pattern in patterns:
                        matches = re.finditer(pattern, content)
                        for match in matches:
                            line_num = content[:match.start()].count('\n') + 1

                            # Obtener contexto (línea completa)
                            lines = content.split('\n')
                            context_line = lines[line_num - 1] if line_num <= len(lines) else ""

                            # Ofuscar el valor encontrado
                            found_value = match.group(0)
                            masked_value = found_value[:10] + "..." + found_value[-4:] if len(found_value) > 20 else "***REDACTED***"

                            finding = {
                                "file": str(file_path.relative_to(path)),
                                "line": line_num,
                                "type": secret_type,
                                "severity": "HIGH" if secret_type in ["private_key", "aws_credentials", "password"] else "MEDIUM",
                                "masked_value": masked_value,
                                "context": context_line[:100] + "..." if len(context_line) > 100 else context_line
                            }

                            results["findings"].append(finding)
                            results["statistics"]["secrets_found"] += 1
                            results["statistics"]["by_type"][secret_type] += 1

            except Exception as e:
                continue  # Ignorar archivos que no se pueden leer

        # Generar recomendaciones
        if results["statistics"]["secrets_found"] > 0:
            results["recommendations"].extend([
                "🚨 NUNCA commits estos archivos con secretos",
                "Usa variables de entorno o un gestor de secretos",
                "Agrega patrones sensibles a .gitignore",
                "Considera usar git-secrets o gitleaks como pre-commit hook"
            ])

        if results["high_risk_files"]:
            results["recommendations"].append(
                f"⚠️ Archivos de alto riesgo detectados: {', '.join([Path(f).name for f in results['high_risk_files'][:5]])}"
            )

        # Verificar .gitignore
        gitignore_path = path / ".gitignore"
        if gitignore_path.exists():
            gitignore_content = gitignore_path.read_text()
            missing_patterns = []
            for pattern in ['.env', '*.pem', '*.key', 'credentials.json', 'secrets.*']:
                if pattern not in gitignore_content:
                    missing_patterns.append(pattern)

            if missing_patterns:
                results["recommendations"].append(
                    f"Agregar a .gitignore: {', '.join(missing_patterns)}"
                )

        # Resumen
        print(f"   📊 Archivos escaneados: {results['statistics']['files_scanned']}")
        print(f"   🔍 Secretos encontrados: {results['statistics']['secrets_found']}")
        print(f"   ⚠️ Archivos alto riesgo: {results['statistics']['high_risk_files']}")

        if results["statistics"]["secrets_found"] > 0:
            print(f"   🚨 ALERTA: Se encontraron posibles secretos!")

        return results

    except Exception as e:
        return {"success": False, "error": str(e)}


def file_organizer(
    directory: str,
    action: str = "analyze",
    organize_by: str = "type",
    dry_run: bool = True,
    min_age_days: int = None
) -> Dict[str, Any]:
    """
    [SKILL: file-organizer] Organiza archivos y carpetas inteligentemente.
    Detecta duplicados, sugiere estructuras y limpia directorios.

    Args:
        directory: Directorio a organizar
        action: analyze|organize|find_duplicates|cleanup_old
        organize_by: type|date|project (cómo organizar)
        dry_run: Si True, solo muestra cambios sin ejecutar
        min_age_days: Para cleanup_old, archivos más antiguos que N días
    """
    print(f"\n📁 [FILE-ORGANIZER] {action}: {directory}")

    # Categorías de archivos por extensión
    FILE_CATEGORIES = {
        "documents": ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt', '.xls', '.xlsx', '.ppt', '.pptx'],
        "images": ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp', '.ico', '.tiff'],
        "videos": ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'],
        "audio": ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma'],
        "archives": ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2'],
        "code": ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs', '.rb', '.php'],
        "data": ['.json', '.xml', '.csv', '.yaml', '.yml', '.sql', '.db'],
        "config": ['.ini', '.cfg', '.conf', '.env', '.toml'],
    }

    try:
        path = Path(directory).resolve()
        if not path.exists():
            return {"success": False, "error": f"Directorio no existe: {directory}"}

        results = {
            "success": True,
            "directory": str(path),
            "action": action,
            "dry_run": dry_run,
            "statistics": {
                "total_files": 0,
                "total_size_mb": 0,
                "by_category": defaultdict(lambda: {"count": 0, "size_mb": 0}),
                "by_extension": defaultdict(int),
            },
            "proposed_changes": [],
            "duplicates": [],
            "old_files": []
        }

        # Recolectar información de archivos
        all_files = []
        file_hashes = defaultdict(list)  # Para detectar duplicados

        for file_path in path.rglob("*"):
            if file_path.is_file() and not any(p in str(file_path) for p in ['.git', '__pycache__', 'node_modules']):
                try:
                    stat = file_path.stat()
                    file_info = {
                        "path": file_path,
                        "name": file_path.name,
                        "extension": file_path.suffix.lower(),
                        "size_bytes": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime),
                        "category": "other"
                    }

                    # Determinar categoría
                    for category, extensions in FILE_CATEGORIES.items():
                        if file_info["extension"] in extensions:
                            file_info["category"] = category
                            break

                    all_files.append(file_info)
                    results["statistics"]["total_files"] += 1
                    results["statistics"]["total_size_mb"] += stat.st_size / (1024 * 1024)
                    results["statistics"]["by_category"][file_info["category"]]["count"] += 1
                    results["statistics"]["by_category"][file_info["category"]]["size_mb"] += stat.st_size / (1024 * 1024)
                    results["statistics"]["by_extension"][file_info["extension"]] += 1

                    # Calcular hash para archivos pequeños (< 50MB) para detectar duplicados
                    if stat.st_size < 50 * 1024 * 1024 and action in ["analyze", "find_duplicates"]:
                        file_hash = hashlib.md5(file_path.read_bytes()).hexdigest()
                        file_hashes[file_hash].append(file_info)

                except Exception:
                    continue

        if action == "analyze":
            # Análisis general
            results["analysis"] = {
                "total_files": results["statistics"]["total_files"],
                "total_size_mb": round(results["statistics"]["total_size_mb"], 2),
                "categories": dict(results["statistics"]["by_category"]),
                "top_extensions": dict(sorted(
                    results["statistics"]["by_extension"].items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:10]),
                "potential_duplicates": sum(1 for files in file_hashes.values() if len(files) > 1),
                "recommendations": []
            }

            # Recomendaciones
            if results["analysis"]["potential_duplicates"] > 0:
                results["analysis"]["recommendations"].append(
                    f"🔍 {results['analysis']['potential_duplicates']} grupos de posibles duplicados"
                )

            if results["statistics"]["by_category"]["other"]["count"] > results["statistics"]["total_files"] * 0.3:
                results["analysis"]["recommendations"].append(
                    "⚠️ Muchos archivos sin categoría clara - considera revisarlos"
                )

        elif action == "find_duplicates":
            # Encontrar duplicados
            for file_hash, files in file_hashes.items():
                if len(files) > 1:
                    total_wasted = sum(f["size_bytes"] for f in files[1:])
                    results["duplicates"].append({
                        "hash": file_hash[:8],
                        "files": [str(f["path"]) for f in files],
                        "count": len(files),
                        "wasted_mb": round(total_wasted / (1024 * 1024), 2),
                        "keep_suggestion": str(files[0]["path"]),  # Sugerir mantener el primero
                    })

            results["statistics"]["duplicate_groups"] = len(results["duplicates"])
            results["statistics"]["wasted_space_mb"] = round(
                sum(d["wasted_mb"] for d in results["duplicates"]), 2
            )

            print(f"   🔍 Grupos de duplicados: {len(results['duplicates'])}")
            print(f"   💾 Espacio desperdiciado: {results['statistics']['wasted_space_mb']} MB")

        elif action == "organize":
            # Proponer organización
            for file_info in all_files:
                if organize_by == "type":
                    new_dir = path / file_info["category"]
                elif organize_by == "date":
                    year_month = file_info["modified"].strftime("%Y/%Y-%m")
                    new_dir = path / year_month
                else:
                    new_dir = path / file_info["category"]

                new_path = new_dir / file_info["name"]

                if new_path != file_info["path"]:
                    change = {
                        "from": str(file_info["path"]),
                        "to": str(new_path),
                        "category": file_info["category"]
                    }
                    results["proposed_changes"].append(change)

                    if not dry_run:
                        new_dir.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(file_info["path"]), str(new_path))

            results["statistics"]["files_to_move"] = len(results["proposed_changes"])

            if dry_run:
                print(f"   📋 Cambios propuestos: {len(results['proposed_changes'])} archivos")
                print(f"   ℹ️ Modo DRY-RUN: ningún archivo fue movido")
            else:
                print(f"   ✅ Archivos organizados: {len(results['proposed_changes'])}")

        elif action == "cleanup_old":
            # Encontrar archivos antiguos
            if min_age_days is None:
                min_age_days = 180  # 6 meses por defecto

            cutoff_date = datetime.now() - timedelta(days=min_age_days)

            for file_info in all_files:
                if file_info["modified"] < cutoff_date:
                    results["old_files"].append({
                        "path": str(file_info["path"]),
                        "modified": file_info["modified"].isoformat(),
                        "age_days": (datetime.now() - file_info["modified"]).days,
                        "size_mb": round(file_info["size_bytes"] / (1024 * 1024), 2)
                    })

            results["statistics"]["old_files_count"] = len(results["old_files"])
            results["statistics"]["old_files_size_mb"] = round(
                sum(f["size_mb"] for f in results["old_files"]), 2
            )

            print(f"   📅 Archivos > {min_age_days} días: {len(results['old_files'])}")
            print(f"   💾 Espacio recuperable: {results['statistics']['old_files_size_mb']} MB")

        # Convertir defaultdicts a dicts normales para serialización
        results["statistics"]["by_category"] = dict(results["statistics"]["by_category"])
        results["statistics"]["by_extension"] = dict(results["statistics"]["by_extension"])

        return results

    except Exception as e:
        return {"success": False, "error": str(e)}


# Importar timedelta para file_organizer
from datetime import timedelta


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
    "query_memory": query_memory,
    "get_relationship_graph": get_relationship_graph,
    "get_file_trace": get_file_trace,
    "get_trace_hotspots": get_trace_hotspots,
    "generate_trace_report": generate_trace_report,
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
    # Agent Skills (importados de skills.sh)
    "git_safe_workflow": git_safe_workflow,
    "security_leak_scan": security_leak_scan,
    "file_organizer": file_organizer,
    # Code Generator Agent
    "ai_generate_code": ai_generate_code,
    "ai_generate_api": ai_generate_api,
    "ai_generate_crud": ai_generate_crud,
    "ai_generate_function": ai_generate_function,
    "ai_generate_class": ai_generate_class,
    "ai_refactor_code": ai_refactor_code,
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
            "name": "query_memory",
            "description": "Consulta la memoria conversacional del agente. Busca en conversaciones previas, recupera hechos almacenados (preferencias, tech stack, info del proyecto), y obtiene contexto de sesiones anteriores. USA ESTA HERRAMIENTA cuando necesites recordar algo de conversaciones pasadas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Texto a buscar en la memoria (para action=search)"
                    },
                    "action": {
                        "type": "string",
                        "enum": ["search", "facts", "history", "stats", "context"],
                        "description": "search=buscar en conversaciones, facts=obtener hechos almacenados, history=historial de sesión, stats=estadísticas, context=contexto reciente formateado"
                    },
                    "category": {
                        "type": "string",
                        "enum": ["tech_stack", "project_info", "preferences", "workflow", "general"],
                        "description": "Categoría de hechos a filtrar (solo para action=facts)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Máximo de resultados a retornar (default: 5)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_relationship_graph",
            "description": "Devuelve un grafo ligero con relaciones entre archivos, servicios y datos desde el RAG.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scope": {
                        "type": "string",
                        "description": "Filtro opcional por substring de ruta (carpeta o extension)."
                    },
                    "include_external": {
                        "type": "boolean",
                        "description": "Incluir servicios externos/eventos (default: true)."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_file_trace",
            "description": "Devuelve la trazabilidad de un archivo específico: edges entrantes/salientes (depends_on y calls) desde el RAG.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Ruta (relativa o absoluta) del archivo objetivo"
                    },
                    "include_external": {
                        "type": "boolean",
                        "description": "Incluir nodos/edges externos (default: false)."
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_trace_hotspots",
            "description": "Devuelve rankings (hotspots) de archivos con más comunicación (calls) y dependencias (depends_on) en el RAG.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scope": {
                        "type": "string",
                        "description": "Filtro opcional por substring de ruta/carpeta/nombre (null = todo)."
                    },
                    "include_external": {
                        "type": "boolean",
                        "description": "Incluir nodos/edges externos (default: false)."
                    },
                    "top_n": {
                        "type": "integer",
                        "description": "Cantidad máxima de items por ranking (default: 20)."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_trace_report",
            "description": "Genera un reporte Markdown de trazabilidad (hotspots + previews) y lo guarda en el repo (default: TRACEABILITY_REPORT.md).",
            "parameters": {
                "type": "object",
                "properties": {
                    "scope": {
                        "type": "string",
                        "description": "Filtro opcional por substring de ruta/carpeta/nombre (null = todo)."
                    },
                    "include_external": {
                        "type": "boolean",
                        "description": "Incluir nodos/edges externos (default: false)."
                    },
                    "top_n": {
                        "type": "integer",
                        "description": "Top N para rankings (default: 20)."
                    },
                    "output_file": {
                        "type": "string",
                        "description": "Ruta del archivo Markdown a escribir (opcional)."
                    }
                },
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
    },
    # =========================================================================
    # AGENT SKILLS - Herramientas importadas de skills.sh
    # =========================================================================
    {
        "type": "function",
        "function": {
            "name": "git_safe_workflow",
            "description": "🔒 [SKILL: git-safe-workflow] Operaciones Git seguras para agentes IA. Previene comandos destructivos (reset --hard, push --force), protege ramas principales (main/master), verifica HEAD separado, y sigue Conventional Commits. Usa SIEMPRE esta herramienta para operaciones Git en lugar de comandos directos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["status", "diff", "add", "commit", "branch", "log", "worktree_info", "push"],
                        "description": "Acción Git a realizar de forma segura"
                    },
                    "message": {
                        "type": "string",
                        "description": "Mensaje de commit (requerido para action=commit). Debe seguir Conventional Commits: feat|fix|docs|style|refactor|test|chore"
                    },
                    "files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Archivos específicos para add/commit (null = todos los modificados)"
                    },
                    "branch": {
                        "type": "string",
                        "description": "Nombre de rama para crear/cambiar (para action=branch)"
                    },
                    "force": {
                        "type": "boolean",
                        "description": "Forzar operación en rama protegida o HEAD separado (requiere confirmación explícita del usuario)"
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "security_leak_scan",
            "description": "🔐 [SKILL: security-leak-guardrails] Escanea código en busca de secretos y credenciales antes de commit. Detecta API keys, passwords, tokens, private keys, connection strings, JWT, AWS credentials, etc. EJECUTAR SIEMPRE antes de hacer commit para prevenir fugas de datos sensibles.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directorio a escanear (default: directorio actual)"
                    },
                    "scan_type": {
                        "type": "string",
                        "enum": ["full", "staged", "quick"],
                        "description": "Tipo de escaneo: full=todo el proyecto, staged=solo archivos en staging git, quick=archivos comunes"
                    },
                    "fix_mode": {
                        "type": "boolean",
                        "description": "Si debe sugerir correcciones para los problemas encontrados"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "file_organizer",
            "description": "📁 [SKILL: file-organizer] Organiza archivos y carpetas inteligentemente. Analiza estructura, detecta duplicados por hash MD5, sugiere reorganización por tipo/fecha, identifica archivos antiguos. Ideal para limpiar directorios de descargas, proyectos desordenados o preparar archivado.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directorio a organizar (requerido)"
                    },
                    "action": {
                        "type": "string",
                        "enum": ["analyze", "organize", "find_duplicates", "cleanup_old"],
                        "description": "analyze=análisis general, organize=proponer/ejecutar organización, find_duplicates=buscar archivos duplicados, cleanup_old=identificar archivos antiguos"
                    },
                    "organize_by": {
                        "type": "string",
                        "enum": ["type", "date", "project"],
                        "description": "Criterio de organización: type=por tipo de archivo, date=por fecha, project=por proyecto"
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "Si True (default), solo muestra cambios sin ejecutar. False para aplicar cambios reales."
                    },
                    "min_age_days": {
                        "type": "integer",
                        "description": "Para cleanup_old: archivos más antiguos que N días (default: 180 = 6 meses)"
                    }
                },
                "required": ["directory"]
            }
        }
    },
    # =========================================================================
    # CODE GENERATOR AGENT - Generación de código multi-lenguaje
    # =========================================================================
    {
        "type": "function",
        "function": {
            "name": "ai_generate_code",
            "description": "[CODE-GENERATOR] Genera código basado en especificación en lenguaje natural. Soporta Python, JavaScript, TypeScript, PHP, Java, Go. Puede generar funciones, clases, módulos completos. El código generado incluye docstrings, type hints y manejo de errores.",
            "parameters": {
                "type": "object",
                "properties": {
                    "specification": {
                        "type": "string",
                        "description": "Descripción detallada de lo que se quiere generar (ej: 'función que valide emails con regex')"
                    },
                    "language": {
                        "type": "string",
                        "enum": ["python", "javascript", "typescript", "php", "java", "go"],
                        "description": "Lenguaje objetivo (auto-detecta si no se especifica)"
                    },
                    "generation_type": {
                        "type": "string",
                        "enum": ["general", "api", "crud", "refactor"],
                        "description": "Tipo de generación: general=código libre, api=endpoints REST, crud=operaciones CRUD, refactor=mejorar código"
                    },
                    "framework": {
                        "type": "string",
                        "description": "Framework específico (fastapi, django, express, laravel, spring, gin, etc.)"
                    },
                    "output_file": {
                        "type": "string",
                        "description": "Ruta del archivo donde guardar el código generado (opcional)"
                    }
                },
                "required": ["specification"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ai_generate_api",
            "description": "[CODE-GENERATOR] Genera un endpoint de API REST completo con validación, manejo de errores y documentación. Soporta FastAPI, Express, Laravel, Spring, Gin.",
            "parameters": {
                "type": "object",
                "properties": {
                    "endpoint_description": {
                        "type": "string",
                        "description": "Descripción del endpoint (ej: 'endpoint para listar usuarios con paginación y filtros')"
                    },
                    "method": {
                        "type": "string",
                        "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                        "description": "Método HTTP del endpoint"
                    },
                    "language": {
                        "type": "string",
                        "enum": ["python", "javascript", "typescript", "php", "java", "go"],
                        "description": "Lenguaje objetivo"
                    },
                    "framework": {
                        "type": "string",
                        "description": "Framework (fastapi, express, laravel, spring, gin)"
                    },
                    "include_tests": {
                        "type": "boolean",
                        "description": "Si debe incluir tests unitarios para el endpoint"
                    },
                    "output_file": {
                        "type": "string",
                        "description": "Archivo de salida"
                    }
                },
                "required": ["endpoint_description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ai_generate_crud",
            "description": "[CODE-GENERATOR] Genera operaciones CRUD completas: Modelo, Repositorio, Servicio y Controlador. Incluye validaciones, paginación y soft-delete opcional.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_name": {
                        "type": "string",
                        "description": "Nombre de la entidad (ej: 'User', 'Product', 'Order')"
                    },
                    "fields": {
                        "type": "object",
                        "description": "Campos de la entidad como {nombre: tipo} (ej: {\"name\": \"string\", \"price\": \"float\", \"active\": \"boolean\"})"
                    },
                    "language": {
                        "type": "string",
                        "enum": ["python", "javascript", "typescript", "php", "java", "go"],
                        "description": "Lenguaje objetivo"
                    },
                    "framework": {
                        "type": "string",
                        "description": "Framework a usar"
                    },
                    "include_soft_delete": {
                        "type": "boolean",
                        "description": "Incluir borrado lógico con campo deleted_at (default: true)"
                    },
                    "include_pagination": {
                        "type": "boolean",
                        "description": "Incluir paginación en listados (default: true)"
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Directorio donde guardar los archivos generados"
                    }
                },
                "required": ["entity_name", "fields"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ai_generate_function",
            "description": "[CODE-GENERATOR] Genera una función individual con docstring, type hints y manejo de errores.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Nombre de la función"
                    },
                    "description": {
                        "type": "string",
                        "description": "Descripción de lo que hace la función"
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Parámetros como {nombre: tipo} (ej: {\"user_id\": \"int\", \"email\": \"str\"})"
                    },
                    "return_type": {
                        "type": "string",
                        "description": "Tipo de retorno (ej: 'bool', 'List[User]', 'Dict[str, Any]')"
                    },
                    "language": {
                        "type": "string",
                        "enum": ["python", "javascript", "typescript", "php", "java", "go"],
                        "description": "Lenguaje"
                    },
                    "async_function": {
                        "type": "boolean",
                        "description": "Si es función asíncrona (async/await)"
                    }
                },
                "required": ["name", "description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ai_generate_class",
            "description": "[CODE-GENERATOR] Genera una clase completa con constructor, atributos, métodos y docstrings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Nombre de la clase"
                    },
                    "description": {
                        "type": "string",
                        "description": "Descripción de la clase y su propósito"
                    },
                    "attributes": {
                        "type": "object",
                        "description": "Atributos como {nombre: tipo}"
                    },
                    "methods": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "description": {"type": "string"},
                                "params": {"type": "string"}
                            }
                        },
                        "description": "Lista de métodos [{name, description, params}]"
                    },
                    "language": {
                        "type": "string",
                        "enum": ["python", "javascript", "typescript", "php", "java", "go"],
                        "description": "Lenguaje"
                    },
                    "parent_class": {
                        "type": "string",
                        "description": "Clase padre para herencia"
                    }
                },
                "required": ["name", "description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ai_refactor_code",
            "description": "[CODE-GENERATOR] Refactoriza código existente mejorando calidad, legibilidad y aplicando mejores prácticas. Mantiene la funcionalidad original.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Ruta del archivo a refactorizar"
                    },
                    "code": {
                        "type": "string",
                        "description": "Código a refactorizar (alternativa a file_path)"
                    },
                    "instructions": {
                        "type": "string",
                        "description": "Instrucciones específicas de refactorización (ej: 'aplicar SOLID', 'mejorar nombres', 'añadir type hints')"
                    },
                    "output_file": {
                        "type": "string",
                        "description": "Archivo de salida (si no se especifica, sobreescribe el original)"
                    }
                },
                "required": []
            }
        }
    }
]
