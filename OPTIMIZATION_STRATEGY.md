# Estrategia de Optimización de Contexto LLM

## 🎯 Objetivo
Reducir drasticamente el contexto enviado al LLM en cada llamada, implementando un enfoque de **planificación inteligente** en lugar de envío masivo de información.

## 📊 Problema Actual

### Análisis del Flujo Actual
```
Usuario: "Analiza este proyecto"
    ↓
┌─────────────────────────────────────────┐
│ LLM recibe EN CADA LLAMADA:             │
├─────────────────────────────────────────┤
│ • System Prompt: ~193 tokens            │
│ • 47 Herramientas: ~5,835 tokens        │  ← ❌ SIEMPRE, incluso si no las usa
│ • Historial completo: ~1,803 tokens    │  ← ❌ Crece indefinidamente
│ TOTAL: ~7,831 tokens                    │
└─────────────────────────────────────────┘
    ↓
LLM piensa: "Necesito explore_directory"
    ↓
Ejecuta herramienta
    ↓
┌─────────────────────────────────────────┐
│ NUEVA LLAMADA con:                      │
├─────────────────────────────────────────┤
│ • System Prompt: ~193 tokens            │
│ • 47 Herramientas: ~5,835 tokens        │  ← ❌ OTRA VEZ!
│ • Historial + resultado: ~3,000 tokens │  ← ❌ Más grande
│ TOTAL: ~9,028 tokens                    │
└─────────────────────────────────────────┘
```

**Problemas:**
1. ❌ Herramientas se envían en CADA llamada (incluso en llamadas recursivas)
2. ❌ Historial completo se reenvía cada vez
3. ❌ No hay separación entre "pensar" y "ejecutar"
4. ❌ El modelo recibe info que ya procesó anteriormente

## 💡 Enfoque Humano vs Enfoque Actual

### Cómo trabaja un humano inteligente:
```
1. Leo la tarea
2. Pienso: "¿Qué necesito?"
3. Busco en mi lista de herramientas las relevantes
4. Planeo los pasos
5. Ejecuto paso 1 con herramienta A
6. Ejecuto paso 2 con herramienta B
7. NO releo toda mi lista de herramientas cada vez
```

### Cómo trabaja el sistema actual:
```
1. Recibe tarea + TODAS las herramientas
2. Piensa con TODO el historial
3. Elige herramienta
4. Ejecuta
5. Recibe resultado + TODAS las herramientas + TODO el historial
6. Repite indefinidamente
```

## ✅ Propuesta: Arquitectura de 3 Fases

### Fase 1: PLANIFICACIÓN (sin herramientas)
```python
Usuario: "Analiza este proyecto y genera documentación"
    ↓
┌─────────────────────────────────────────┐
│ Llamada 1 - PLANNER (sin herramientas) │
├─────────────────────────────────────────┤
│ • System Prompt: "Eres un planificador"│
│ • User query                            │
│ • Lista de NOMBRES de herramientas      │  ← Solo nombres, no schemas completos
│   (47 nombres ≈ 100 tokens)             │
│ TOTAL: ~500 tokens                      │
└─────────────────────────────────────────┘
    ↓
LLM retorna:
{
  "plan": {
    "steps": [
      {"action": "explore_directory", "reason": "..."},
      {"action": "analyze_file", "reason": "..."},
      {"action": "generate_documentation", "reason": "..."}
    ],
    "required_tools": ["explore_directory", "analyze_file", "generate_documentation"]
  }
}
```

### Fase 2: EJECUCIÓN (solo herramientas necesarias)
```python
┌─────────────────────────────────────────┐
│ Llamada 2 - EXECUTOR                    │
├─────────────────────────────────────────┤
│ • System Prompt mínimo                  │
│ • Resumen del plan                      │  ← No historial completo
│ • SOLO 3 herramientas: ~400 tokens      │  ← No 47!
│ TOTAL: ~800 tokens                      │
└─────────────────────────────────────────┘
    ↓
Ejecuta herramientas en paralelo si es posible
    ↓
Retorna resultados en TOON
```

### Fase 3: SÍNTESIS (sin herramientas)
```python
┌─────────────────────────────────────────┐
│ Llamada 3 - SYNTHESIZER                 │
├─────────────────────────────────────────┤
│ • System Prompt: "Sintetiza resultados"│
│ • Resultados de herramientas (TOON)    │
│ • NO herramientas                       │
│ TOTAL: ~1,000 tokens                    │
└─────────────────────────────────────────┘
    ↓
Respuesta final al usuario
```

## 📉 Comparación de Tokens

| Estrategia | Llamada 1 | Llamada 2 | Llamada 3 | Total |
|------------|-----------|-----------|-----------|-------|
| **Actual** | 7,831 | 9,028 | 10,500 | **27,359** |
| **Propuesta** | 500 | 800 | 1,000 | **2,300** |
| **Ahorro** | | | | **91.6%** 🎉 |

## 🛠️ Implementación Propuesta

### 1. Nuevo módulo: `smart_orchestrator.py`

```python
class SmartOrchestrator:
    """
    Orquestador inteligente con 3 fases:
    - Planner: Analiza y planea (sin herramientas completas)
    - Executor: Ejecuta con herramientas específicas
    - Synthesizer: Sintetiza resultados (sin herramientas)
    """
    
    def __init__(self):
        self.planner_client = OpenAI()
        self.executor_client = OpenAI()
        self.tool_registry = TOOL_FUNCTIONS
        self.all_tool_names = [t["function"]["name"] for t in TOOLS]
    
    def chat(self, user_input, context_summary=None):
        """
        Flujo de 3 fases:
        1. Plan (sin herramientas)
        2. Execute (solo herramientas necesarias)
        3. Synthesize (sin herramientas)
        """
        # FASE 1: PLANIFICACIÓN
        plan = self._create_plan(user_input, context_summary)
        
        # FASE 2: EJECUCIÓN
        results = self._execute_plan(plan)
        
        # FASE 3: SÍNTESIS
        response = self._synthesize_results(user_input, plan, results)
        
        return response
```

### 2. Manejo de contexto con resúmenes

En lugar de enviar historial completo:
```python
def _create_context_summary(self, messages):
    """
    Resume el historial en lugar de enviarlo completo.
    
    Antes: ["msg1", "msg2", ..., "msg20"] → 5,000 tokens
    Después: "Resumen: Usuario analizó X, generó Y" → 200 tokens
    """
    if len(messages) <= 3:
        return messages  # Si es corto, enviar completo
    
    # Usar LLM para resumir
    summary_prompt = f"""Resume esta conversación en 3-4 líneas:
    {json.dumps(messages[:-2])}
    """
    
    summary = self._get_summary(summary_prompt)
    recent_messages = messages[-2:]  # Últimos 2
    
    return [
        {"role": "system", "content": f"Contexto previo: {summary}"}
    ] + recent_messages
```

### 3. Herramientas on-demand

```python
def _get_tools_for_plan(self, tool_names):
    """
    Retorna solo los schemas de las herramientas necesarias.
    
    Antes: 47 tools → 5,835 tokens
    Después: 3 tools → 400 tokens
    """
    return [
        tool for tool in TOOLS 
        if tool["function"]["name"] in tool_names
    ]
```

### 4. Parallel tool execution (cuando sea posible)

```python
def _execute_plan(self, plan):
    """
    Ejecuta herramientas en paralelo cuando no hay dependencias.
    """
    results = {}
    
    # Identificar pasos independientes
    parallel_steps = self._identify_parallel_steps(plan["steps"])
    
    for batch in parallel_steps:
        # Ejecutar batch en paralelo
        batch_results = self._execute_parallel(batch)
        results.update(batch_results)
    
    return results
```

## 🎯 Estrategias Adicionales

### A. Tool Preloading para tareas comunes
```python
COMMON_WORKFLOWS = {
    "analyze_project": ["explore_directory", "analyze_file", "generate_documentation"],
    "security_audit": ["check_dependencies", "security_audit", "generate_dependency_graph"],
    "generate_tests": ["analyze_file", "generate_tests", "run_tests"]
}

def get_workflow_tools(workflow_type):
    """Precarga herramientas para workflows comunes."""
    return COMMON_WORKFLOWS.get(workflow_type, [])
```

### B. Caché de resultados de herramientas
```python
class ToolCache:
    """
    Evita re-ejecutar herramientas con mismos parámetros.
    """
    def __init__(self):
        self.cache = {}
    
    def get_or_execute(self, tool_name, args):
        cache_key = f"{tool_name}:{json.dumps(args, sort_keys=True)}"
        
        if cache_key in self.cache:
            print(f"⚡ Cache hit: {tool_name}")
            return self.cache[cache_key]
        
        result = self._execute(tool_name, args)
        self.cache[cache_key] = result
        return result
```

### C. Compresión de resultados antes de envío
```python
def compress_tool_result(result, max_tokens=500):
    """
    Si el resultado es muy largo, resumir usando LLM.
    """
    result_str = format_tool_result(result)  # TOON
    
    if estimate_tokens(result_str) > max_tokens:
        # Resumir con LLM
        summary = summarize_with_llm(result_str, max_tokens)
        return summary
    
    return result_str
```

## 📋 Plan de Implementación

### Fase 1: Implementación básica (1-2 días)
- [ ] Crear `smart_orchestrator.py`
- [ ] Implementar flujo de 3 fases
- [ ] Selector de herramientas por nombre
- [ ] Tests básicos

### Fase 2: Optimizaciones (2-3 días)
- [ ] Sistema de resúmenes de contexto
- [ ] Caché de herramientas
- [ ] Parallel execution
- [ ] Métricas de ahorro de tokens

### Fase 3: Refinamiento (1-2 días)
- [ ] Workflows predefinidos
- [ ] Compresión inteligente de resultados
- [ ] Fallback al sistema antiguo si falla
- [ ] Documentación y ejemplos

## 🔄 Compatibilidad hacia atrás

Para mantener el sistema actual funcionando:
```python
# main.py
USE_SMART_ORCHESTRATOR = os.getenv("USE_SMART_ORCHESTRATOR", "true").lower() == "true"

if USE_SMART_ORCHESTRATOR:
    agent = SmartOrchestrator(user_id="pvargas")
else:
    agent = Agent(user_id="pvargas")  # Sistema legacy
```

## 📊 Métricas de Éxito

Antes vs Después:
- **Tokens por conversación**: 27,359 → 2,300 (91.6% ↓)
- **Llamadas API**: 3-5 → 3 (fijo)
- **Latencia**: Similar o mejor (parallel execution)
- **Costo**: ~$0.02 → ~$0.002 por conversación (90% ↓)

## 🚀 Beneficios Esperados

1. ✅ **91% reducción** en uso de tokens
2. ✅ **Ejecución paralela** de herramientas independientes
3. ✅ **Contexto relevante** en cada fase (no ruido)
4. ✅ **Escalabilidad**: Agregar más herramientas no afecta performance
5. ✅ **Caché**: Evita re-ejecutar operaciones
6. ✅ **Más "humano"**: Planea → Ejecuta → Sintetiza

---

**Próximos pasos**: ¿Implementamos el `smart_orchestrator.py` con esta estrategia?
