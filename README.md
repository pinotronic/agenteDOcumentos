# Sistema de Análisis de Código Multi-Agente

Sistema avanzado de análisis de código con **47 herramientas**, **selección inteligente de modelos** y **dos estrategias de orquestación** que utilizan tres LLMs especializados y almacenamiento RAG para procesar, entender, mejorar y documentar repositorios de código.

## 🎯 Características Principales

- **Dos Estrategias de Orquestación**:
  - **Smart Orchestrator** (recomendado): Arquitectura de 3 fases que ahorra 90%+ tokens
  - **Agent Tradicional**: Flexible para conversaciones exploratorias
- **Multi-Agente con Selección Inteligente de Modelos**:
  - Orquestador (gpt-4o-mini): Coordinación rápida y eficiente
  - Analizador (gpt-4o): Análisis profundo de código
  - Razonamiento (o3-mini): Tareas complejas que requieren pensamiento crítico
- **47 Herramientas Especializadas** organizadas en 9 categorías
- **RAG Storage**: Base de conocimiento persistente de código analizado
- **Resumen Local de Memoria**: Compresión de contexto con Ollama antes de inyectarlo al prompt
- **Optimización Extrema de Tokens**: Tool selection + TOON format + caché
- **Generación Automática**: Tests, docstrings, Dockerfiles, configuraciones
- **Análisis de Seguridad**: Auditoría de dependencias y CVEs
- **Integración CI/CD**: Linters, tests, validaciones de build
- **Reportes**: Dashboards HTML, deuda técnica, grafos de dependencias

## 🚀 Nuevo: Smart Orchestrator (Arquitectura de 3 Fases)

### Problema del Enfoque Tradicional
```
❌ Cada llamada al LLM envía:
   • 47 herramientas (5,835 tokens)
   • Historial completo (crece indefinidamente)
   • Información redundante en cada iteración
   TOTAL: ~7,831+ tokens por llamada
```

### Solución: Smart Orchestrator
```
✅ Arquitectura de 3 fases:
   1. PLANNER: Analiza y planea (solo nombres de herramientas)
      → ~500 tokens
   
   2. EXECUTOR: Ejecuta con herramientas específicas
      → ~800 tokens (solo 3-5 tools necesarias)
   
   3. SYNTHESIZER: Sintetiza resultados (sin herramientas)
      → ~1,000 tokens
   
   TOTAL: ~2,300 tokens por consulta
   AHORRO: 91.6% 🎉
```

### Ventajas Adicionales
- ⚡ **Caché de herramientas**: Evita re-ejecutar operaciones idénticas
- 🧠 **Contexto resumido**: No reenvía historial completo
- 📦 **Herramientas on-demand**: Solo carga lo necesario
- 🔄 **Ejecución paralela**: Preparado para paralelización (próxima versión)

## 📊 Comparación de Estrategias

| Característica | Smart Orchestrator | Agent Tradicional |
|----------------|-------------------|-------------------|
| Tokens por consulta | ~2,300 | ~7,831 |
| Ahorro | 91.6% | - |
| Caché | ✅ Sí | ❌ No |
| Contexto | Resumido | Completo |
| Herramientas | On-demand | Todas siempre |
| Mejor para | Tareas estructuradas | Conversaciones exploratorias |
| Activar con | `USE_SMART_ORCHESTRATOR=true` | `USE_SMART_ORCHESTRATOR=false` |

## 🧠 Sistema de Selección Inteligente de Modelos

## 🧩 Resumen Local de Memoria

El agente tradicional ahora puede comprimir la memoria recuperada antes de inyectarla al prompt principal. Esto reduce ruido cuando la ventana de contexto es corta.

Flujo:
- Recupera hechos persistentes y mensajes similares desde ChromaDB
- Si Ollama está disponible, genera una memoria compacta con un modelo local
- Si Ollama no está disponible, usa el fallback actual basado en texto recuperado

Variables de entorno:
- `OLLAMA_MEMORY_SUMMARIZER=1` activa o desactiva el resumidor local
- `OLLAMA_BASE_URL=http://127.0.0.1:11434` define el endpoint de Ollama
- `OLLAMA_MEMORY_MODEL=qwen3.5:4b` define el modelo usado para comprimir memoria
- `OLLAMA_TIMEOUT=120` controla el timeout del resumidor local; qwen3.5:4b puede requerir latencia alta en equipos modestos

El sistema selecciona automáticamente el modelo más apropiado según la tarea:

### Tareas con o3-mini (Razonamiento Profundo) 🧠
1. **debug_assistant** - Análisis de causa raíz
2. **code_review** - Evaluación crítica de código
3. **security_audit** - Detección de vulnerabilidades
4. **technical_debt_report** - Evaluación de deuda técnica
5. **generate_tests** - Comprensión de edge cases
6. **explain_code** - Explicación de código complejo

### Tareas con gpt-4o-mini (Orquestación Rápida) ⚙️
- Lectura y escritura de archivos
- Exploración de directorios
- Búsquedas en RAG
- Ejecución de linters/tests
- Generación de documentación básica

**Indicadores en consola:**
- 🧠 = Usando modelo de razonamiento (o3-mini)
- ⚙️ = Usando orquestación rápida (gpt-4o-mini)

## 🏗️ Arquitectura

### Componentes Principales

```
┌─────────────────────────────────────────────────────┐
│                   main.py                           │
│            (Interfaz de Usuario)                    │
└────────────────┬────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│              agent.py                               │
│    (Agente Orquestador con Selección de Modelo)    │
│         Modelo Base: gpt-4o-mini                    │
│         Modelo Razonamiento: o3-mini                │
│  • Coordina el análisis                             │
│  • Selecciona herramientas (32)                     │
│  • Gestiona conversación                            │
│  • Detecta tareas complejas                         │
└────────────────┬────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│              tools.py (32 herramientas)             │
│  📖 Análisis: explore, read, analyze                │
│  ✍️  Escritura: create, write, append, docs, open   │
│  📦 Dependencias: check, audit, graph               │
│  🔧 Generación: tests, docstrings, configs          │
│  💡 Asistencia: explain, debug, review              │
│  🌐 Externas: stackoverflow, api_docs               │
│  📊 Reportes: dashboard, technical_debt             │
│  🚀 CI/CD: linters, tests, build, deployment        │
└─────────┬──────────────────────┬────────────────────┘
          │                      │
          ▼                      ▼
┌──────────────────────┐  ┌──────────────────────┐
│  code_analyzer.py    │  │  rag_storage.py      │
│  (Agente Analizador) │  │  (Base de            │
│  Modelo: GPT-4o      │  │   Conocimiento)      │
│  • Análisis profundo │  │  • Almacenamiento    │
│  • Extracción de     │  │  • Búsqueda          │
│    metadata          │  │  • Indexación        │
│  • JSON estructurado │  │                      │
└──────────────────────┘  └──────────────────────┘
          │                      │
          ▼──────────────────────▼
┌─────────────────────────────────────────────────────┐
│         Módulos Especializados (6)                  │
├─────────────────────────────────────────────────────┤
│  dependency_analyzer.py  • Análisis de deps         │
│  code_generator.py       • Generación de código     │
│  code_assistant.py       • Asistencia interactiva   │
│  external_integrations.py• APIs externas            │
│  report_generator.py     • Dashboards y reportes    │
│  ci_cd_tools.py          • CI/CD automation         │
└─────────────────────────────────────────────────────┘
```

## 📦 Módulos

### `config.py`
Configuración centralizada del sistema:
- Modelos de OpenAI
- Límites de procesamiento
- Extensiones soportadas
- Patrones de ignorar
- Prompts del sistema

### `agent.py` - Agente Orquestador
**Modelo:** GPT-4o-mini (rápido y eficiente)

**Responsabilidades:**
- Interpretar peticiones del usuario
- Seleccionar herramientas apropiadas
- Coordinar análisis de múltiples archivos
- Presentar resultados de forma coherente
- Gestionar el flujo de conversación

### `code_analyzer.py` - Agente Analizador
**Modelo:** GPT-4o (potente para análisis profundo)

**Responsabilidades:**
- Analizar archivos individuales en profundidad
- Extraer funciones, clases, imports, documentación
- Generar contratos de funciones (parámetros, retorno)
- Determinar complejidad del código
- Retornar análisis en formato JSON estructurado

**Formato de salida:**
```json
{
  "summary": "Descripción del archivo",
  "file_type": "python",
  "imports": ["os", "json", "pathlib"],
  "classes": [
    {
      "name": "MiClase",
      "bases": ["BaseClass"],
      "docstring": "Documentación...",
      "methods": [...]
    }
  ],
  "functions": [
    {
      "name": "mi_funcion",
      "signature": "def mi_funcion(param: str) -> bool",
      "parameters": [...],
      "return_type": "bool",
      "docstring": "Descripción..."
    }
  ],
  "constants": [...],
  "complexity": "medium",
  "key_features": [...]
}
```

### `rag_storage.py` - Sistema RAG
**Base de conocimiento persistente**

**Funcionalidades:**
- Almacenamiento en JSON de análisis
- Indexación por ruta, tipo, contenido
- Búsqueda por palabra clave
- Búsqueda de funciones específicas
- Búsqueda por tipo de archivo
- Estadísticas del repositorio

**Estructura de almacenamiento:**
```
rag_storage/
├── rag_index.json          # Índice principal
├── abc123def456.json       # Documento 1
├── 789ghi012jkl.json       # Documento 2
└── ...
```

### `tools.py` - Herramientas (32 Herramientas)
Funciones que el agente orquestador puede usar, organizadas en 9 categorías:

#### 📖 Análisis y Lectura (6)
1. **explore_directory**: Explora estructura de directorios
2. **read_file**: Lee contenido de archivos
3. **analyze_file**: Analiza un archivo específico con IA
4. **analyze_directory**: Analiza todos los archivos de un directorio
5. **search_in_rag**: Busca en la base de conocimiento
6. **get_rag_statistics**: Obtiene estadísticas del RAG

#### ✍️ Escritura y Generación (5)
7. **create_file**: Crea nuevos archivos
8. **write_file**: Escribe/sobrescribe archivos
9. **append_to_file**: Agrega contenido a archivos
10. **generate_documentation**: Genera docs MD con diagramas UML Mermaid
11. **open_file_in_editor**: Abre archivos en VS Code para edición manual

#### ✍️ Escritura y Generación (5)
7. **create_file**: Crea nuevos archivos
8. **write_file**: Escribe/sobrescribe archivos
9. **append_to_file**: Agrega contenido a archivos
10. **generate_documentation**: Genera docs MD con diagramas UML Mermaid
11. **open_file_in_editor**: Abre archivos en VS Code para edición manual

#### 📦 Gestión de Dependencias (4)
12. **check_dependencies**: Verifica requirements.txt/package.json
13. **security_audit**: Auditoría de seguridad y CVEs
14. **generate_dependency_graph**: Grafo de dependencias Mermaid
15. **find_outdated_packages**: Encuentra paquetes desactualizados

#### 🔧 Generación de Código (4)
16. **generate_tests**: Genera tests unitarios (pytest/unittest)
17. **generate_docstrings**: Genera docstrings (Google/Numpy style)
18. **generate_config_files**: Genera .gitignore, setup.py, requirements
19. **generate_dockerfile**: Genera Dockerfile optimizado

#### 💡 Asistencia Interactiva (3)
19. **explain_code**: Explica código (niveles: beginner/intermediate/expert)
20. **debug_assistant**: Asiste en depuración y root cause analysis
21. **code_review**: Revisión de código estilo senior developer

#### 🌐 Integraciones Externas (2)
22. **search_stackoverflow**: Busca y resume soluciones de StackOverflow
23. **fetch_api_docs**: Obtiene documentación de APIs con IA

#### 📊 Reportes y Dashboards (2)
24. **generate_html_dashboard**: Dashboard HTML interactivo
25. **technical_debt_report**: Reporte de deuda técnica

#### 🚀 CI/CD y Validación (4)
26. **run_linters**: Ejecuta pylint/flake8/eslint
27. **run_tests**: Ejecuta pytest/unittest/jest
28. **check_build**: Verifica que compile correctamente
29. **deployment_check**: Verifica readiness de deployment

### Módulos Especializados

#### `dependency_analyzer.py`
Análisis de dependencias del proyecto:
- **check_dependencies**: Parsea y verifica requirements.txt/package.json
- **security_audit**: Busca CVEs y vulnerabilidades con LLM
- **generate_dependency_graph**: Genera grafo visual en Mermaid
- **find_outdated_packages**: Identifica versiones desactualizadas

#### `code_generator.py`
Generación automática de código:
- **generate_tests**: Crea tests unitarios con pytest/unittest
- **generate_docstrings**: Genera documentación estilo Google/Numpy
- **generate_config_files**: .gitignore, setup.py, requirements.txt
- **generate_dockerfile**: Dockerfile multi-stage optimizado

#### `code_assistant.py`
Asistencia interactiva con IA:
- **explain_code**: Explica código en 3 niveles (beginner/intermediate/expert)
- **debug_assistant**: Analiza bugs y sugiere soluciones
- **code_review**: Revisión exhaustiva estilo senior developer

#### `external_integrations.py`
Integración con servicios externos:
- **search_stackoverflow**: API de StackOverflow + resumen con LLM
- **fetch_api_docs**: Genera documentación comprensiva de cualquier API

#### `report_generator.py`
Generación de reportes:
- **generate_html_dashboard**: Dashboard HTML con estadísticas
- **technical_debt_report**: Análisis de deuda técnica, code smells

#### `ci_cd_tools.py`
Herramientas CI/CD:
- **run_linters**: Ejecuta linters automáticamente
- **run_tests**: Corre suite de tests
- **check_build**: Valida compilación del proyecto
- **deployment_check**: Verifica readiness (README, tests, secretos)

#### `doc_generator.py`
Generación de documentación:
- Markdown estructurado
- Diagramas UML con Mermaid
- Resúmenes de clases y funciones
- Arquitectura del proyecto

## 🚀 Uso

### Instalación
```bash
pip install openai python-dotenv requests
```

### Configurar API Key
Crea un archivo `.env`:
```
OPENAI_API_KEY=tu_api_key_aqui
```

### Ejecutar
```bash
python main.py
```

### Ejemplos de Comandos

#### 📖 Análisis Básico
```
Explora el directorio C:/Users/mi-usuario/mi-proyecto
Analiza todos los archivos Python en ./src
Analiza el archivo ./tools.py en profundidad
Busca funciones que contengan la palabra "calculate"
¿Qué archivos Python tengo analizados?
Obtén estadísticas del RAG
```

#### ✍️ Generación de Documentación
```
Genera documentación completa para el directorio actual
Genera documentación con diagramas UML para ./src
Crea un README.md con el resumen del proyecto
Genera un diagrama de clases para los archivos analizados
```

#### 📦 Análisis de Dependencias
```
Verifica las dependencias del proyecto actual
Realiza una auditoría de seguridad de las dependencias
Genera un grafo de dependencias visual
Encuentra qué paquetes están desactualizados
```

#### 🔧 Generación de Código
```
Genera tests unitarios para agent.py usando pytest
Genera docstrings estilo Google para todos los archivos en ./src
Genera un Dockerfile para este proyecto Python
Crea archivos de configuración (.gitignore, setup.py) para el proyecto
```

#### 💡 Asistencia Interactiva
```
Explica el código de agent.py en nivel experto
Ayúdame a depurar el error en main.py: AttributeError en línea 45
Haz una revisión de código completa de tools.py
Explica cómo funciona el sistema RAG para un principiante
```

#### 🌐 Búsqueda Externa
```
Busca en StackOverflow cómo implementar rate limiting en Flask
Obtén documentación completa de la librería requests en Python
Busca las mejores prácticas para testing en pytest
```

#### 📊 Reportes
```
Genera un dashboard HTML del proyecto
Analiza la deuda técnica del directorio ./src
Crea un reporte de code smells y complejidad
```

#### 🚀 CI/CD
```
Ejecuta todos los linters en el proyecto
Corre los tests del proyecto con pytest
Verifica que el proyecto compile correctamente
Verifica si el proyecto está listo para deployment
```

**Ver estadísticas:**
```
Muéstrame estadísticas del RAG
```

## 🎯 Características Clave

### Multi-Agente
- **Orquestador**: Coordina y toma decisiones
- **Analizador**: Realiza análisis profundo especializado

### Inteligente
- Ignora automáticamente archivos binarios
- Respeta patrones tipo `.gitignore`
- Maneja archivos grandes con chunking
- Validación de límites de tamaño

### Persistente
- Almacenamiento RAG en JSON
- Indexación para búsqueda rápida
- Análisis reutilizables

### Escalable
- Procesamiento por lotes
- Progress tracking
- Manejo de errores robusto

## 📊 Tipos de Archivo Soportados

**Código:**
Python, JavaScript, TypeScript, Java, C/C++, C#, Go, Rust, Ruby, PHP, Swift, Kotlin, Scala

**Documentación:**
Markdown, TXT, JSON, YAML, XML, HTML, CSS, SQL

**Configuración:**
TOML, INI, ENV, CFG

## ⚙️ Configuración Avanzada

### Ajustar límites
Edita `config.py`:
```python
MAX_FILE_SIZE_MB = 5
MAX_TOKENS_PER_FILE = 100000
CHUNK_SIZE = 8000
```

### Cambiar modelos
```python
ORCHESTRATOR_MODEL = "gpt-4o-mini"
ANALYZER_MODEL = "gpt-4o"
```

### Agregar extensiones
```python
CODE_EXTENSIONS = {
    '.py': 'python',
    '.rs': 'rust',
    # Agregar más...
}
```

## 🔒 Seguridad

- No almacena código fuente completo en memoria
- Respeta límites de tamaño
- No procesa archivos binarios
- API key en variables de entorno

## 📈 Costos Aproximados

**Orquestador (GPT-4o-mini):**
- Input: $0.15 / 1M tokens
- Output: $0.60 / 1M tokens

**Analizador (GPT-4o):**
- Input: $2.50 / 1M tokens
- Output: $10.00 / 1M tokens

**Estimación:** ~$0.01-0.05 por archivo medio

## 🐛 Solución de Problemas

**Error: API key no configurada**
```bash
# Crear .env con:
OPENAI_API_KEY=sk-...
```

**Error: Archivo muy grande**
- Ajustar `MAX_FILE_SIZE_MB` en `config.py`
- Dividir archivos grandes

**Error: Token limit exceeded**
- El sistema maneja automáticamente archivos grandes
- Verifica `MAX_TOKENS_PER_FILE`

## 🤝 Contribuciones

Este es un sistema modular diseñado para extensión:
- Agregar nuevas herramientas en `tools.py`
- Extender tipos de archivo en `config.py`
- Mejorar prompts del analizador
- Implementar nuevos métodos de búsqueda RAG

## 📝 Licencia

MIT License - Libre para uso personal y comercial

activar el ambiente virtual: .\env\Scripts\Activate.ps1

```bash
   .\env\Scripts\python.exe main.py
   .\env\Scripts\activate.bat
```


## Contexto relacional y persistencia RAG
- Cada analisis ahora incluye `relationships` (dependencias internas, llamadas a servicios, datastores, colas/eventos, endpoints expuestos).
- Nueva herramienta `get_relationship_graph`: devuelve nodos/edges para ver cómo se conectan archivos, servicios y datos.
- ChromaDB puede operar en modo persistente: usa `CHROMA_PERSIST=1` y `CHROMA_PERSIST_PATH` (fallback automático a memoria si hay incompatibilidad en Windows/Python 3.13).

## ⚡ Optimización de Tokens - Selección Dinámica de Herramientas

Para evitar exceder el límite de contexto (128K tokens), el sistema ahora usa **selección inteligente de herramientas**:

- **Problema**: 47 herramientas = ~3,200 tokens solo en definiciones
- **Solución**: Solo carga las herramientas relevantes según tu consulta (máx 15)
- **Beneficio**: Reduce hasta 70% el uso de tokens en herramientas

### Categorías de Herramientas
El sistema detecta palabras clave en tu consulta y selecciona automáticamente:

1. **analysis**: "analiza", "explora", "busca", "estadísticas"
2. **writing**: "crea", "escribe", "genera", "documenta"
3. **dependencies**: "dependencias", "paquetes", "seguridad", "cves"
4. **code_generation**: "tests", "docstrings", "config", "dockerfile"
5. **assistance**: "explica", "debug", "ayuda", "error", "review"
6. **external**: "stackoverflow", "api docs"
7. **reports**: "dashboard", "reporte", "deuda técnica"
8. **cicd**: "linter", "test", "build", "deployment"
9. **gorila_mode**: "plan", "ejecuta plan", "supervisor", "dod"

### Formato TOON - Reducción de Tokens 40-70%
Los resultados de herramientas ahora usan **TOON (Token-Oriented Object Notation)** en lugar de JSON:

**Ventajas:**
- **40-70% menos tokens** que JSON para datos estructurados
- Formato tabular para arrays de objetos homogéneos
- Sin comillas para strings simples
- Indentación YAML-like más compacta

**Ejemplo de conversión:**
```
JSON (145 chars, ~36 tokens):
{
  "name": "agent.py",
  "type": "python", 
  "functions": 15,
  "classes": 3,
  "complexity": "high"
}

TOON (78 chars, ~19 tokens - 47% ahorro):
name: agent.py
type: python
functions: 15
classes: 3
complexity: high
```

**Arrays como tablas:**
```
JSON (285 chars):
[
  {"file": "agent.py", "lines": 450, "funcs": 15},
  {"file": "tools.py", "lines": 320, "funcs": 32},
  {"file": "config.py", "lines": 120, "funcs": 5}
]

TOON (142 chars - 50% ahorro):
[file, lines, funcs]
[agent.py, 450, 15]
[tools.py, 320, 32]
[config.py, 120, 5]
```

El sistema convierte automáticamente todos los resultados de herramientas a TOON y muestra el ahorro de tokens en consola.

### Limpieza Automática de Contexto
- El historial se recorta automáticamente cada 10 mensajes
- Mantiene los 6 mensajes más recientes + prompt del sistema
- La memoria conversacional persistente guarda todo en ChromaDB
