# Quick Reference: Smart Orchestrator vs Agent Tradicional

## 🚀 Quick Start

```bash
# 1. Configurar en .env
USE_SMART_ORCHESTRATOR=true  # o false

# 2. Ejecutar
python main.py

# 3. Ver estadísticas
> stats

# 4. Probar
python test_smart_orchestrator.py
```

## 📊 Comparación Rápida

| | Smart Orchestrator | Agent Tradicional |
|---|---|---|
| **Tokens/consulta** | ~2,300 | ~7,831 |
| **Ahorro** | 91.6% | - |
| **Estrategia** | 3 fases | Recursivo |
| **Herramientas** | On-demand (3-5) | Todas (47) |
| **Contexto** | Resumido | Completo |
| **Caché** | ✅ Sí | ❌ No |
| **Mejor para** | Tareas estructuradas | Exploración |

## 🔄 Flujos

### Smart Orchestrator (3 fases)
```
User Query
    ↓
[1. PLAN]  500 tokens → Plan JSON
    ↓
[2. EXECUTE]  800 tokens → Resultados (TOON)
    ↓
[3. SYNTHESIZE]  1,000 tokens → Respuesta
    ↓
Total: 2,300 tokens ✅
```

### Agent Tradicional (recursivo)
```
User Query
    ↓
[Call 1]  7,831 tokens → Tool call
    ↓
[Call 2]  9,028 tokens → Tool call
    ↓
[Call 3]  10,500 tokens → Response
    ↓
Total: 27,359 tokens ❌
```

## 💡 Casos de Uso

### ✅ Usar Smart Orchestrator:
- ✓ Análisis de proyectos
- ✓ Generación de documentación
- ✓ Auditorías de seguridad
- ✓ Generación de tests
- ✓ Tareas con pasos claros

### ✅ Usar Agent Tradicional:
- ✓ Conversaciones exploratorias
- ✓ Debugging interactivo
- ✓ Code reviews con contexto variable
- ✓ Cuando no sabes qué herramientas necesitas

## 🎯 Archivos Clave

```
smart_orchestrator.py          # Implementación principal
OPTIMIZATION_STRATEGY.md       # Estrategia completa
OPTIMIZATION_SUMMARY.md        # Este resumen
test_smart_orchestrator.py     # Tests
context_analyzer.py            # Análisis de contexto
main.py                        # Soporte para ambas estrategias
.env.example                   # Configuración
```

## 📈 Métricas del Smart Orchestrator

```python
orchestrator.get_stats()
# {
#   "total_calls": 10,
#   "cache_hits": 3,
#   "cache_hit_rate": 0.3,
#   "cache_size": 5,
#   "total_tokens_saved": 45678
# }
```

## 🔧 Comandos Útiles

```bash
# En el chat
stats      # Ver estadísticas
reset      # Reiniciar (limpia caché)
salir      # Salir

# Scripts
python context_analyzer.py           # Analizar contexto
python test_smart_orchestrator.py    # Test completo
```

## 🎓 Diferencias Clave

### Agent Tradicional:
```python
# Envía SIEMPRE:
params = {
    "model": model,
    "messages": self.messages,  # Historial completo
    "tools": self.tools          # 47 herramientas
}
```

### Smart Orchestrator:
```python
# FASE 1 - Solo nombres
planner_call(tool_names=["tool1", "tool2", ...])  # ~100 tokens

# FASE 2 - Solo necesarias
executor_call(tools=selected_tools)  # 3-5 tools, ~400 tokens

# FASE 3 - Sin herramientas
synthesizer_call(results=toon_results)  # Sin tools
```

## 🚀 Próximas Mejoras

- [ ] Ejecución paralela de herramientas
- [ ] Workflows predefinidos
- [ ] Compresión inteligente de resultados
- [ ] Métricas en tiempo real
- [ ] Dashboard web

## 📚 Documentación Completa

Ver [OPTIMIZATION_STRATEGY.md](OPTIMIZATION_STRATEGY.md) para detalles completos.
