"""
Sistema de selección dinámica de herramientas para evitar exceder límites de contexto.
Selecciona solo las herramientas relevantes según la intención del usuario.
"""
from typing import List, Dict, Any


# Categorías de herramientas con palabras clave
TOOL_CATEGORIES = {
    "analysis": {
        "keywords": ["analiza", "explora", "lee", "busca", "estadísticas", "inspecciona", "revisa"],
        "tools": [
            "explore_directory", "read_file", "analyze_file", 
            "analyze_directory", "search_in_rag", "get_rag_statistics",
            "get_relationship_graph"
        ]
    },
    "writing": {
        "keywords": ["crea", "escribe", "genera", "documenta", "agrega", "append", "abre editor"],
        "tools": [
            "create_file", "write_file", "append_to_file",
            "generate_documentation", "open_file_in_editor"
        ]
    },
    "dependencies": {
        "keywords": ["dependencias", "paquetes", "requirements", "seguridad", "cves", "audit", "grafo"],
        "tools": [
            "check_dependencies", "security_audit",
            "generate_dependency_graph", "find_outdated_packages"
        ]
    },
    "code_generation": {
        "keywords": ["tests", "docstrings", "config", "dockerfile", "pytest", "unittest"],
        "tools": [
            "generate_tests", "generate_docstrings",
            "generate_config_files", "generate_dockerfile"
        ]
    },
    "assistance": {
        "keywords": ["explica", "debug", "ayuda", "error", "review", "revisión"],
        "tools": [
            "explain_code", "debug_assistant", "code_review"
        ]
    },
    "external": {
        "keywords": ["stackoverflow", "api", "docs", "documentación externa"],
        "tools": [
            "search_stackoverflow", "fetch_api_docs"
        ]
    },
    "reports": {
        "keywords": ["dashboard", "reporte", "deuda técnica", "html"],
        "tools": [
            "generate_html_dashboard", "technical_debt_report"
        ]
    },
    "cicd": {
        "keywords": ["linter", "test", "build", "deployment", "ci/cd", "pytest", "flake8"],
        "tools": [
            "run_linters", "run_tests", "check_build", "deployment_check"
        ]
    },
    "php_tools": {
        "keywords": ["php", "curl", "endpoint", "test endpoint"],
        "tools": [
            "add_diagram_to_php", "add_curl_test_to_php",
            "test_php_endpoint", "batch_add_curl_to_php_files"
        ]
    },
    "gorila_mode": {
        "keywords": ["plan", "gorila", "ejecuta plan", "supervisor", "contract", "dod", "quality", "evidencia", "commit"],
        "tools": [
            "generate_analysis_plan", "execute_plan", "supervise_plan_execution",
            "validate_contract", "check_dod_compliance", "run_quality_gates",
            "generate_execution_evidence", "generate_unified_diff",
            "create_incremental_commit", "check_git_status",
            "list_directory_recursive"
        ]
    },
    "utility": {
        "keywords": ["lista", "archivos", "directorio"],
        "tools": ["list_files_in_dir"]
    }
}

# Herramientas básicas que siempre se incluyen (núcleo esencial)
CORE_TOOLS = [
    "explore_directory",
    "read_file",
    "analyze_file",
    "search_in_rag",
    "get_rag_statistics"
]


def select_relevant_tools(user_query: str, all_tools: List[Dict], max_tools: int = 15) -> List[Dict]:
    """
    Selecciona las herramientas más relevantes según la consulta del usuario.
    
    Args:
        user_query: Consulta del usuario en texto
        all_tools: Lista completa de herramientas disponibles
        max_tools: Máximo de herramientas a incluir
        
    Returns:
        Lista filtrada de herramientas relevantes
    """
    query_lower = user_query.lower()
    
    # 1. Identificar categorías relevantes
    relevant_categories = []
    for category, info in TOOL_CATEGORIES.items():
        if any(keyword in query_lower for keyword in info["keywords"]):
            relevant_categories.append(category)
    
    # 2. Si no hay coincidencias claras, usar análisis como default
    if not relevant_categories:
        relevant_categories = ["analysis", "assistance"]
    
    # 3. Recopilar herramientas de categorías relevantes
    selected_tool_names = set(CORE_TOOLS)  # Siempre incluir herramientas core
    
    for category in relevant_categories:
        selected_tool_names.update(TOOL_CATEGORIES[category]["tools"])
    
    # 4. Filtrar la lista de herramientas
    selected_tools = []
    tool_lookup = {tool["function"]["name"]: tool for tool in all_tools}
    
    for tool_name in selected_tool_names:
        if tool_name in tool_lookup:
            selected_tools.append(tool_lookup[tool_name])
    
    # 5. Limitar número de herramientas
    if len(selected_tools) > max_tools:
        # Priorizar herramientas core
        core_tools_selected = [t for t in selected_tools if t["function"]["name"] in CORE_TOOLS]
        other_tools = [t for t in selected_tools if t["function"]["name"] not in CORE_TOOLS]
        selected_tools = core_tools_selected + other_tools[:max_tools - len(core_tools_selected)]
    
    print(f"🔧 Herramientas seleccionadas: {len(selected_tools)}/{len(all_tools)}")
    print(f"   Categorías activas: {', '.join(relevant_categories)}")
    
    return selected_tools


def get_smart_tools(user_query: str, all_tools: List[Dict]) -> List[Dict]:
    """
    Wrapper principal para obtener herramientas inteligentes.
    
    Args:
        user_query: Consulta del usuario
        all_tools: Todas las herramientas disponibles
        
    Returns:
        Herramientas seleccionadas inteligentemente
    """
    return select_relevant_tools(user_query, all_tools, max_tools=15)
