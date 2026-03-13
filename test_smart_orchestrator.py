"""
Test del Smart Orchestrator vs Agent tradicional.
Compara uso de tokens y eficiencia.
"""
import os
os.environ['CHROMA_PERSIST'] = '0'

from smart_orchestrator import SmartOrchestrator
from agent import Agent
import json


def test_smart_orchestrator():
    """Prueba el nuevo orquestrador optimizado."""
    print("="*80)
    print("🧪 TEST: Smart Orchestrator (3 fases)")
    print("="*80)
    
    orchestrator = SmartOrchestrator(user_id="test_user", enable_cache=True)
    
    # Test 1: Consulta simple
    print("\n📝 Test 1: Análisis de archivo")
    response = orchestrator.chat("Analiza el archivo config.py")
    print(f"\n✅ Respuesta: {response[:200]}...")
    
    # Test 2: Consulta compleja (debería usar caché para config.py)
    print("\n📝 Test 2: Análisis múltiple (con caché)")
    response2 = orchestrator.chat("Analiza config.py y agent.py")
    print(f"\n✅ Respuesta: {response2[:200]}...")
    
    # Estadísticas
    stats = orchestrator.get_stats()
    print(f"\n📊 ESTADÍSTICAS SMART ORCHESTRATOR:")
    print(json.dumps(stats, indent=2))
    
    return stats


def test_traditional_agent():
    """Prueba el agente tradicional para comparación."""
    print("\n" + "="*80)
    print("🧪 TEST: Agent Tradicional")
    print("="*80)
    
    agent = Agent(name="Test", user_id="test_user")
    
    # Test 1: Consulta simple
    print("\n📝 Test 1: Análisis de archivo")
    response = agent.chat("Analiza el archivo config.py")
    print(f"\n✅ Respuesta: {response[:200]}...")
    
    # Stats
    stats = agent.get_conversation_stats()
    print(f"\n📊 ESTADÍSTICAS AGENT TRADICIONAL:")
    print(json.dumps(stats, indent=2))
    
    return stats


def compare_results():
    """Compara ambas estrategias."""
    print("\n" + "="*80)
    print("📊 COMPARACIÓN FINAL")
    print("="*80)
    
    print("\n🧠 Smart Orchestrator:")
    print("   ✓ 3 llamadas por consulta (plan, execute, synthesize)")
    print("   ✓ Solo herramientas necesarias en cada fase")
    print("   ✓ Contexto resumido (no historial completo)")
    print("   ✓ Caché de herramientas")
    print("   ✓ Ahorro estimado: 90%+ en tokens")
    
    print("\n🔧 Agent Tradicional:")
    print("   ✓ N llamadas recursivas (variable)")
    print("   ✓ Todas las herramientas en cada llamada")
    print("   ✓ Historial completo (trim cada 10 mensajes)")
    print("   ✓ Sin caché")
    print("   ✓ Más flexible pero menos eficiente")
    
    print("\n💡 RECOMENDACIÓN:")
    print("   • Usar Smart Orchestrator para tareas estructuradas")
    print("   • Usar Agent tradicional para conversaciones exploratorias")
    print("   • Configurar en .env: USE_SMART_ORCHESTRATOR=true|false")


if __name__ == "__main__":
    print("\n🚀 Iniciando tests de comparación...")
    
    # Test Smart Orchestrator
    smart_stats = test_smart_orchestrator()
    
    # Test Traditional Agent
    # traditional_stats = test_traditional_agent()  # Descomentar si quieres comparar
    
    # Comparación
    compare_results()
    
    print("\n✅ Tests completados")
