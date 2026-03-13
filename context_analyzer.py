"""
Script para analizar cuánto contexto envía el sistema al LLM.
Simula una conversación típica y calcula el uso de tokens.
"""
import os
os.environ['CHROMA_PERSIST'] = '0'  # Desactivar persistencia

import json
from tools import TOOLS
from config import ORCHESTRATOR_SYSTEM_PROMPT
from tool_selector import get_smart_tools


def estimate_tokens(text):
    """Estima tokens: ~4 caracteres por token para texto normal."""
    return len(text) // 4


def simulate_conversation_context():
    """Simula el contexto que se envía en una conversación típica."""
    
    print("=" * 80)
    print("📊 ANÁLISIS DE CONTEXTO ENVIADO AL LLM")
    print("=" * 80)
    print()
    
    # 1. CONTEXTO BASE (siempre presente)
    print("🔹 1. CONTEXTO BASE (presente en cada llamada)")
    print("-" * 80)
    
    system_prompt = ORCHESTRATOR_SYSTEM_PROMPT
    system_tokens = estimate_tokens(system_prompt)
    print(f"   📝 System Prompt:")
    print(f"      • Caracteres: {len(system_prompt):,}")
    print(f"      • Tokens estimados: {system_tokens:,}")
    print()
    
    # 2. HERRAMIENTAS (con y sin selección)
    print("🔹 2. HERRAMIENTAS (función calling)")
    print("-" * 80)
    
    # Sin selección
    all_tools_json = json.dumps(TOOLS, ensure_ascii=False)
    all_tools_tokens = estimate_tokens(all_tools_json)
    print(f"   🛠️  SIN selección inteligente (47 tools):")
    print(f"      • Caracteres: {len(all_tools_json):,}")
    print(f"      • Tokens estimados: {all_tools_tokens:,}")
    print()
    
    # Con selección
    selected_tools = get_smart_tools("analiza este código y genera documentación", TOOLS)
    selected_json = json.dumps(selected_tools, ensure_ascii=False)
    selected_tokens = estimate_tokens(selected_json)
    savings = 100 - (len(selected_json) / len(all_tools_json) * 100)
    print(f"   🎯 CON selección inteligente (~{len(selected_tools)} tools):")
    print(f"      • Caracteres: {len(selected_json):,}")
    print(f"      • Tokens estimados: {selected_tokens:,}")
    print(f"      • Ahorro: {savings:.1f}% ({all_tools_tokens - selected_tokens:,} tokens)")
    print()
    
    # 3. HISTORIAL DE MENSAJES (crece con la conversación)
    print("🔹 3. HISTORIAL DE MENSAJES (crece dinámicamente)")
    print("-" * 80)
    
    # Simular conversación
    messages = [
        {"role": "user", "content": "Analiza el archivo agent.py"},
        {"role": "assistant", "content": None, "tool_calls": [{"id": "call_1", "function": {"name": "analyze_file", "arguments": '{"file_path": "agent.py"}'}}]},
        {"role": "tool", "name": "analyze_file", "content": '{"summary": "Orquestador multi-agente...", "classes": [...], "functions": [...]}' * 50},  # Simular resultado grande
        {"role": "assistant", "content": "El archivo agent.py contiene la clase Agent que orquesta..."},
        {"role": "user", "content": "Ahora analiza config.py"},
        {"role": "assistant", "content": None, "tool_calls": [{"id": "call_2", "function": {"name": "analyze_file", "arguments": '{"file_path": "config.py"}'}}]},
        {"role": "tool", "name": "analyze_file", "content": '{"summary": "Configuración del sistema...", "constants": [...]}' * 30},
        {"role": "assistant", "content": "El archivo config.py define la configuración centralizada..."},
    ]
    
    messages_json = json.dumps(messages, ensure_ascii=False)
    messages_tokens = estimate_tokens(messages_json)
    print(f"   💬 Ejemplo: 2 turnos de conversación (user → tool → assistant):")
    print(f"      • Mensajes totales: {len(messages)}")
    print(f"      • Caracteres: {len(messages_json):,}")
    print(f"      • Tokens estimados: {messages_tokens:,}")
    print()
    
    # Contexto después de limpieza
    trimmed_messages = [messages[0]] + messages[-6:]  # System + últimos 6
    trimmed_json = json.dumps(trimmed_messages, ensure_ascii=False)
    trimmed_tokens = estimate_tokens(trimmed_json)
    print(f"   ✂️  Después de _trim_context (últimos 6 mensajes):")
    print(f"      • Mensajes: {len(trimmed_messages)}")
    print(f"      • Tokens estimados: {trimmed_tokens:,}")
    print(f"      • Reducción: {100 - (trimmed_tokens/messages_tokens*100):.1f}%")
    print()
    
    # 4. TOTALES
    print("🔹 4. TOTAL ENVIADO AL LLM EN UNA LLAMADA")
    print("-" * 80)
    
    # Sin optimizaciones
    total_sin_opt = system_tokens + all_tools_tokens + messages_tokens
    print(f"   ❌ Sin optimizaciones:")
    print(f"      • System Prompt: {system_tokens:,} tokens")
    print(f"      • 47 Herramientas: {all_tools_tokens:,} tokens")
    print(f"      • Historial completo: {messages_tokens:,} tokens")
    print(f"      • TOTAL: {total_sin_opt:,} tokens")
    print()
    
    # Con optimizaciones
    total_con_opt = system_tokens + selected_tokens + trimmed_tokens
    print(f"   ✅ Con optimizaciones (tool selection + trim):")
    print(f"      • System Prompt: {system_tokens:,} tokens")
    print(f"      • ~{len(selected_tools)} Herramientas: {selected_tokens:,} tokens")
    print(f"      • Historial recortado: {trimmed_tokens:,} tokens")
    print(f"      • TOTAL: {total_con_opt:,} tokens")
    print()
    
    ahorro_total = total_sin_opt - total_con_opt
    ahorro_pct = (ahorro_total / total_sin_opt) * 100
    print(f"   💰 Ahorro total: {ahorro_total:,} tokens ({ahorro_pct:.1f}%)")
    print()
    
    # 5. LÍMITES
    print("🔹 5. LÍMITES Y CAPACIDAD")
    print("-" * 80)
    print(f"   • Límite del modelo (gpt-4o-mini): 128,000 tokens")
    print(f"   • Uso actual (con optimizaciones): {total_con_opt:,} tokens")
    print(f"   • Disponible para respuesta: {128000 - total_con_opt:,} tokens")
    print(f"   • Uso del contexto: {(total_con_opt/128000)*100:.1f}%")
    print()
    
    # 6. MEMORIA CONVERSACIONAL (NO SE USA POR DEFECTO)
    print("🔹 6. MEMORIA CONVERSACIONAL PERSISTENTE")
    print("-" * 80)
    print(f"   ⚠️  DESACTIVADA por defecto (_inject_recent_memory hace pass)")
    print(f"   • Se guarda en ChromaDB pero NO se inyecta automáticamente")
    print(f"   • Motivo: Ahorro de tokens")
    print(f"   • Usuario debe pedir contexto explícitamente si lo necesita")
    print()
    
    # 7. FORMATO TOON
    print("🔹 7. OPTIMIZACIÓN ADICIONAL: FORMATO TOON")
    print("-" * 80)
    print(f"   • Los resultados de herramientas se convierten a TOON")
    print(f"   • Ahorro típico: 40-70% vs JSON")
    print(f"   • Se aplica AUTOMÁTICAMENTE en agent.py::process_response()")
    print()
    
    print("=" * 80)
    print("📈 RESUMEN")
    print("=" * 80)
    print(f"• Contexto base mínimo: ~{system_tokens + selected_tokens:,} tokens")
    print(f"• Crece con historial hasta: ~{total_con_opt:,} tokens (ejemplo 2 turnos)")
    print(f"• Se limpia cada 10 mensajes → mantiene últimos 6")
    print(f"• Ahorro con optimizaciones: {ahorro_pct:.1f}%")
    print(f"• Memoria persistente: Guardada pero NO inyectada automáticamente")
    print("=" * 80)


if __name__ == "__main__":
    simulate_conversation_context()
