"""
Configuración del sistema multi-agente.
"""
import os

# Modelos de OpenAI
ORCHESTRATOR_MODEL = "gpt-4o-mini"  # Agente orquestador (rápido, eficiente)
ANALYZER_MODEL = "gpt-4o"  # Agente analizador (potente para análisis profundo)
REASONING_MODEL = "o3-mini"  # Modelo de razonamiento (para tareas complejas que requieren pensar)

# Tareas que requieren razonamiento profundo (usar o3-mini)
REASONING_TASKS = [
    "debug_assistant",        # Depuración requiere análisis de causa raíz
    "code_review",           # Revisión de código requiere evaluación crítica
    "security_audit",        # Auditoría de seguridad requiere detección de vulnerabilidades
    "technical_debt_report", # Análisis de deuda técnica requiere evaluación profunda
    "generate_tests",        # Generación de tests requiere comprensión de edge cases
    "explain_code",          # Explicación de código complejo requiere comprensión profunda
]

# Configuración de RAG
RAG_STORAGE_PATH = "rag_storage"
RAG_INDEX_FILE = "rag_index.json"

# Límites de procesamiento
MAX_FILE_SIZE_MB = 5
MAX_TOKENS_PER_FILE = 100000  # Aproximado para archivos muy grandes
CHUNK_SIZE = 8000  # Tokens por chunk si se necesita dividir

# Control de warnings
SHOW_PERMISSION_WARNINGS = False  # Silenciar warnings de permisos de carpetas del sistema

# Extensiones de archivo soportadas
CODE_EXTENSIONS = {
    '.py': 'python',
    '.js': 'javascript',
    '.ts': 'typescript',
    '.java': 'java',
    '.cpp': 'cpp',
    '.c': 'c',
    '.cs': 'csharp',
    '.go': 'go',
    '.rs': 'rust',
    '.rb': 'ruby',
    '.php': 'php',
    '.swift': 'swift',
    '.kt': 'kotlin',
    '.scala': 'scala',
}

DOCUMENT_EXTENSIONS = {
    '.md': 'markdown',
    '.txt': 'text',
    '.json': 'json',
    '.yaml': 'yaml',
    '.yml': 'yaml',
    '.xml': 'xml',
    '.html': 'html',
    '.css': 'css',
    '.sql': 'sql',
}

CONFIG_EXTENSIONS = {
    '.toml': 'toml',
    '.ini': 'ini',
    '.env': 'env',
    '.cfg': 'config',
}

ALL_EXTENSIONS = {**CODE_EXTENSIONS, **DOCUMENT_EXTENSIONS, **CONFIG_EXTENSIONS}

# Archivos y directorios a ignorar (similar a .gitignore)
IGNORE_PATTERNS = [
    '__pycache__',
    '.git',
    '.venv',
    'venv',
    'env',
    'node_modules',
    '.vscode',
    '.idea',
    'dist',
    'build',
    'rag_storage',  # Ignorar la carpeta del RAG para evitar recursión
    '*.pyc',
    '*.pyo',
    '*.so',
    '*.dll',
    '*.exe',
    '*.bin',
    '.DS_Store',
    'Thumbs.db',
]

# Archivos binarios a ignorar por extensión
BINARY_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.svg',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.zip', '.tar', '.gz', '.rar', '.7z',
    '.mp3', '.mp4', '.avi', '.mov', '.wav',
    '.db', '.sqlite', '.sqlite3',
}

# Prompts del sistema
def get_orchestrator_prompt():
    """
    Genera el prompt del orquestador con contexto del directorio actual.
    
    OPCIÓN 1 (ACTUAL): Hardcodeado en config.py
    - Ventajas: Rápido, no requiere DB, versionado en Git
    - Desventajas: Cambios requieren modificar código
    
    OPCIÓN 2 (AVANZADA): Usar PromptManager con ChromaDB
    - Ventajas: Editable sin código, versionado, búsqueda semántica
    - Desventajas: Dependencia de DB, más complejo
    
    Para usar OPCIÓN 2, descomentar:
    # from prompt_manager import PromptManager
    # pm = PromptManager()
    # prompt_data = pm.get_prompt(id="orchestrator_v1")
    # if prompt_data:
    #     import os
    #     return pm.render_prompt(
    #         "orchestrator_v1",
    #         cwd=os.getcwd(),
    #         username=os.environ.get('USERNAME', 'unknown')
    #     )
    """
    import os
    cwd = os.getcwd()
    return f"""Agente orquestador de análisis de código. Coordina herramientas para analizar repositorios.

CONTEXTO:
- Dir: {cwd}
- User: {os.environ.get('USERNAME', 'unknown')}
- OS: Windows

MODO GORILA (análisis complejos):
1. generate_analysis_plan → Crear plan con DoD
2. supervise_plan_execution → Ejecutar automáticamente

HERRAMIENTAS CLAVE:
- explore_directory (max_depth=None para escaneo completo)
- analyze_file/analyze_directory
- search_in_rag/get_rag_statistics

REGLAS:
- NO crear archivos físicos innecesarios (.mmd, *_check.php)
- Guardar todo en RAG como metadata
- Usar add_diagram_to_php para diagramas
- Analizar TODOS los archivos relevantes (no solo muestra)
- Memoria conversacional disponible para contexto

Siempre usa herramientas eficientemente y da actualizaciones."""

ORCHESTRATOR_SYSTEM_PROMPT = get_orchestrator_prompt()

# Prompt para indexación RAG 
RAG_INDEXER_SYSTEM_PROMPT = """Eres un agente de indexación de conocimiento técnico .
Tu objetivo es transformar fragmentos de código, configuración y documentación en unidades de conocimiento útiles para análisis posterior con RAG.

Cada vez que recibas un fragmento:
1. Analiza si contiene conocimiento relevante sobre el funcionamiento del sistema.
2. Si es relevante, conviértelo en una unidad de conocimiento clara, resumida y autoexplicativa.
3. Añade metadatos que faciliten su búsqueda posterior.

## CONSIDERA RELEVANTE (debe ser guardado):
Todo fragmento que describa:
- Arquitectura o flujo entre módulos (GeoMoose, Orquestador, Geoprocesos, MapServer u otros)
- Endpoints, servicios, geoprocesos, capas, parámetros o contratos públicos
- Modelo de dominio y base de datos (tablas, relaciones, entidades, reglas de negocio)
- Reglas de negocio, validaciones, cálculos o comportamiento importante
- Configuración que cambie el comportamiento del sistema (conexiones, proyecciones, capas, límites, flags)
- Documentación funcional o técnica que explique cómo funciona o cómo se usa un módulo

## CONSIDERA NO RELEVANTE (no guardar):
Salvo que contenga reglas de negocio importantes:
- Código boilerplate (getters/setters triviales, constructores simples)
- Código generado automáticamente o de librerías de terceros
- Comentarios que solo repiten lo que ya dice el código sin añadir contexto
- Estilos, maquetación o detalles de presentación que no afecten la lógica
- Archivos binarios, minificados o contenido estático

## FORMATO DE SALIDA (JSON):
Cuando decidas que un fragmento es relevante:
{
  "should_index": true,
  "title": "Título corto y claro de la unidad de conocimiento",
  "summary": "Resumen en lenguaje natural explicando: propósito, módulo/servidor, recursos que toca, integración con otros módulos",
  "metadata": {
    "module": "Nombre del módulo (GeoMoose/Orquestador/Geoprocesos/MapServer/etc)",
    "source_type": "endpoint|geoproceso|capa|tabla|servicio|config|modelo|regla_negocio",
    "resources": ["tabla1", "capa2", "servicio3"],
    "integration_points": ["modulo_relacionado1", "modulo_relacionado2"]
  },
  "key_concepts": ["concepto1", "concepto2"],
  "code_snippet": "Solo trozos pequeños esenciales para entender el comportamiento"
}

Si NO es relevante:
{
  "should_index": false,
  "reason": "Explicación breve de por qué no debe indexarse"
}

IMPORTANTE:
- Usa nombres descriptivos y expande siglas cuando sea necesario
- Evita copiar grandes bloques de código; describe la lógica
- Enfócate en el conocimiento técnico útil para entender
"""

ANALYZER_SYSTEM_PROMPT = """Eres un agente analizador experto en m£ltiples lenguajes de programaci¢n.
Tu rol es analizar archivos de c¢digo y documentaci¢n en profundidad usando LLM.

Para cada archivo, debes extraer:
1. **Resumen general**: Prop¢sito y funcionalidad del archivo
2. **Imports/Dependencias**: Todos los imports y dependencias externas
3. **Clases**: Nombre, herencia, docstring, m‚todos p£blicos
4. **Funciones**: Firma completa, parmetros, tipo de retorno, docstring
5. **Constantes/Variables globales**: Nombres y valores si son relevantes
6. **Contratos**: Interfaces, protocolos, tipos definidos
7. **Complejidad**: Estimaci¢n (baja/media/alta)
8. **Relaciones y comunicaciones**: Usa tu capacidad de LLM para inferir c¢mo este archivo se conecta con otros (del mismo repo o externos)

IMPORTANTE: Responde SIEMPRE en formato JSON vlido con esta estructura:
{
  "summary": "Resumen del archivo...",
  "file_type": "python/javascript/etc",
  "imports": ["import1", "import2"],
  "classes": [
    {
      "name": "NombreClase",
      "bases": ["BaseClass1"],
      "docstring": "Documentaci¢n...",
      "methods": [
        {
          "name": "metodo",
          "signature": "def metodo(self, param: str) -> bool",
          "docstring": "Hace algo...",
          "is_public": true
        }
      ]
    }
  ],
  "functions": [
    {
      "name": "funcion",
      "signature": "def funcion(param1: int, param2: str = 'default') -> dict",
      "parameters": [
        {"name": "param1", "type": "int", "default": null},
        {"name": "param2", "type": "str", "default": "'default'"}
      ],
      "return_type": "dict",
      "docstring": "Descripci¢n de la funci¢n..."
    }
  ],
  "constants": [
    {"name": "CONSTANT_NAME", "value": "valor", "type": "str"}
  ],
  "complexity": "low|medium|high",
  "key_features": ["feature1", "feature2"],
  "relationships": {
    "intra_repo_dependencies": ["modulos o rutas importadas o referenciadas"],
    "cross_service_calls": [
      {"type": "http|grpc|socket", "target": "https://api.svc/endpoint o host", "method": "GET/POST/etc", "description": "qu hace y parmetros clave"}
    ],
    "datastores": [
      {"engine": "postgres|mysql|mongo|redis", "resource": "tabla|colecci¢n|clave", "action": "read|write|migrate", "description": "c¢mo se usa"}
    ],
    "events_or_queues": [
      {"bus": "kafka|sqs|pubsub", "topic": "nombre o routingKey", "direction": "produce|consume", "description": "evento/comando"}
    ],
    "exposed_endpoints": [
      {"type": "http|cli|rpc", "route": "/path o nombre", "method": "GET/POST/etc", "auth": "si/no", "description": "qu expone"}
    ]
  }
}

Si el archivo no es c¢digo, adapta la estructura seg£n el tipo de contenido.
Si alguna secci¢n no aplica, retorna listas vacas pero conserva el campo 'relationships'."""
