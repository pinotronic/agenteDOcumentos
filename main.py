"""
Punto de entrada principal para el asistente de análisis de código.
Sistema multi-agente con orquestador y analizador especializado.
"""
# Los módulos cargan .env automáticamente vía env_loader
from agent import Agent


def print_banner():
    """Muestra banner de bienvenida."""
    print("=" * 80)
    print("🤖 SISTEMA DE ANÁLISIS DE CÓDIGO MULTI-AGENTE")
    print("=" * 80)
    print("\n📋 ARQUITECTURA:")
    print("   • Agente Orquestador: Coordina el análisis y usa herramientas")
    print("   • Agente Analizador: Analiza archivos en profundidad (GPT-4o)")
    print("   • RAG Storage: Almacena y busca análisis de código")
    print("\n🧠 ESTRATEGIA DE MODELOS:")
    print("   • gpt-4o-mini: Orquestación rápida y eficiente")
    print("   • o3-mini: Razonamiento profundo para tareas complejas")
    print("   • Tareas con 🧠: debug, code review, security audit, technical debt")
    print("\n🛠️  HERRAMIENTAS DISPONIBLES (32 HERRAMIENTAS):")
    
    print("\n   📖 Análisis y Lectura:")
    print("   • explore_directory - Explora estructura de directorios")
    print("   • read_file - Lee contenido de archivos")
    print("   • analyze_file - Analiza un archivo específico con IA")
    print("   • analyze_directory - Analiza todos los archivos de un directorio")
    print("   • search_in_rag - Busca en la base de conocimiento")
    print("   • get_rag_statistics - Obtiene estadísticas del RAG")
    
    print("\n   ✍️  Escritura y Generación:")
    print("   • create_file - Crea un nuevo archivo")
    print("   • write_file - Escribe/sobrescribe un archivo")
    print("   • append_to_file - Agrega contenido a un archivo")
    print("   • generate_documentation - Genera docs MD con diagramas UML Mermaid")
    print("   • open_file_in_editor - Abre archivos en VS Code para edición manual")
    
    print("\n   📦 Gestión de Dependencias:")
    print("   • check_dependencies - Verifica dependencias (requirements.txt/package.json)")
    print("   • security_audit - Auditoría de seguridad y CVEs")
    print("   • generate_dependency_graph - Grafo de dependencias Mermaid")
    print("   • find_outdated_packages - Encuentra paquetes desactualizados")
    
    print("\n   🔧 Generación de Código:")
    print("   • generate_tests - Genera tests unitarios (pytest/unittest)")
    print("   • generate_docstrings - Genera docstrings (Google/Numpy style)")
    print("   • generate_config_files - Genera .gitignore, setup.py, requirements")
    print("   • generate_dockerfile - Genera Dockerfile optimizado")
    
    print("\n   💡 Asistencia Interactiva:")
    print("   • explain_code - Explica código (niveles: beginner/intermediate/expert)")
    print("   • debug_assistant - Asiste en depuración y root cause analysis")
    print("   • code_review - Revisión de código estilo senior developer")
    
    print("\n   🌐 Integraciones Externas:")
    print("   • search_stackoverflow - Busca y resume soluciones de StackOverflow")
    print("   • fetch_api_docs - Obtiene documentación de APIs con IA")
    
    print("\n   📊 Reportes y Dashboards:")
    print("   • generate_html_dashboard - Dashboard HTML interactivo del proyecto")
    print("   • technical_debt_report - Reporte de deuda técnica y code smells")
    
    print("\n   🚀 CI/CD y Validación:")
    print("   • run_linters - Ejecuta linters (pylint/flake8/eslint)")
    print("   • run_tests - Ejecuta tests (pytest/unittest/jest)")
    print("   • check_build - Verifica que el proyecto compile correctamente")
    print("   • deployment_check - Verifica readiness de deployment")
    
    print("\n💡 EJEMPLOS DE USO:")
    print("   'Explora el directorio C:/Users/mi-usuario/mi-proyecto'")
    print("   'Analiza todos los archivos Python en ./src y genera documentación'")
    print("   'Abre el archivo config.py para que lo edite'")
    print("   'Revisa la seguridad de las dependencias del proyecto actual'")
    print("   'Genera tests para el archivo main.py'")
    print("   'Explica el código de agent.py en nivel experto'")
    print("   'Busca en StackOverflow cómo implementar rate limiting en Flask'")
    print("   'Genera un dashboard HTML del proyecto'")
    print("   'Abre tools.py en el editor para que revise la función analyze_file'")
    print("   'Ejecuta todos los linters y tests del proyecto'")
    
    print("\n⌨️  COMANDOS:")
    print("   • 'salir', 'exit', 'quit' - Terminar")
    print("   • 'reset' - Reiniciar conversación")
    print("   • 'stats' - Ver estadísticas de la sesión")
    print("=" * 80)


def main():
    """Función principal que ejecuta el loop de conversación."""
    import os
    
    print_banner()
    
    # Seleccionar estrategia de orquestación
    use_smart = os.getenv("USE_SMART_ORCHESTRATOR", "false").lower() == "true"
    
    if use_smart:
        from smart_orchestrator import SmartOrchestrator
        agent = SmartOrchestrator(user_id="pvargas", enable_cache=True)
        print(f"\n✅ Smart Orchestrator iniciado (3 fases optimizadas)")
        print("   💡 Ahorro estimado: 90%+ en tokens")
        print("   ⚡ Caché activado")
    else:
        agent = Agent(name="Orquestador")
        print(f"\n✅ Agente tradicional iniciado con modelo: {agent.model}")
        print("   💡 Tip: Activa Smart Orchestrator con USE_SMART_ORCHESTRATOR=true en .env")
    
    print("Listo para recibir comandos...\n")
    
    # Loop principal de conversación
    while True:
        try:
            user_input = input("\n👤 Tú: ").strip()
            
            # Validar entrada vacía
            if not user_input:
                continue
            
            # Comandos especiales
            if user_input.lower() in ["salir", "exit", "quit"]:
                print("\n🤖 Orquestador: ¡Análisis finalizado! Hasta luego.")
                break
            
            if user_input.lower() == "reset":
                if hasattr(agent, 'reset'):
                    agent.reset()
                else:
                    agent.reset_conversation()
                continue
            
            if user_input.lower() == "stats":
                if hasattr(agent, 'get_stats'):
                    # Smart Orchestrator
                    stats = agent.get_stats()
                    print(f"\n📊 Estadísticas Smart Orchestrator:")
                    print(f"   Total llamadas: {stats['total_calls']}")
                    print(f"   Cache hits: {stats['cache_hits']}")
                    print(f"   Cache hit rate: {stats['cache_hit_rate']:.1%}")
                    print(f"   Cache size: {stats['cache_size']} entradas")
                    print(f"   Tokens ahorrados: {stats['total_tokens_saved']:,}")
                else:
                    # Agent tradicional
                    stats = agent.get_conversation_stats()
                    print(f"\n📊 Estadísticas de la sesión:")
                    print(f"   • Mensajes totales: {stats['total_messages']}")
                    print(f"   • Mensajes del usuario: {stats['user_messages']}")
                    print(f"   • Llamadas a herramientas: {stats['tool_calls']}")
                    print(f"   • Modelo: {stats['model']}")
                    print(f"\n💾 Memoria persistente:")
                    mem = stats['memory']
                    print(f"   • Total mensajes guardados: {mem['total_messages']}")
                    print(f"   • Total sesiones: {mem['total_sessions']}")
                    print(f"   • Hechos importantes: {mem['total_facts']}")
                    print(f"   • Por rol: {mem['messages_by_role']}")
                continue
            
            # Obtener y mostrar respuesta del agente
            agent_name = getattr(agent, 'name', 'Smart Orchestrator')
            print(f"\n🤖 {agent_name} procesando...\n")
            response = agent.chat(user_input)
            print(f"\n🤖 {agent_name}: {response}")
            
        except KeyboardInterrupt:
            print("\n\n🤖 Orquestador: ¡Análisis interrumpido! Hasta luego.")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("Por favor, intenta de nuevo.")


if __name__ == "__main__":
    main()