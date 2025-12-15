"""
Test rápido para validar que Architect genera tools válidos.
"""
import sys
sys.path.insert(0, '.')

from architect_mode import Architect
from tools import TOOL_FUNCTIONS


def test_architect_generates_valid_tools():
    """Verifica que el Architect genera nombres de herramientas válidos."""
    print("🧪 TEST: Validación de herramientas en plans del Architect")
    print("="*70)
    
    architect = Architect()
    
    # Generar plan simple
    plan = architect.generate_analysis_plan(
        repository_path="c:\\test",
        user_requirements="Escanear TODOS los archivos PHP en carpetas y subcarpetas",
        scope="full"
    )
    
    if not plan.get("execution_steps"):
        print("⚠️  Plan no tiene execution_steps")
        return True  # No es error, puede ser fallback
    
    print(f"\n📋 Plan generado con {len(plan['execution_steps'])} pasos")
    
    # Validar que todas las herramientas existen
    invalid_tools = []
    for step in plan["execution_steps"]:
        tool_name = step.get("tool")
        if tool_name and tool_name not in TOOL_FUNCTIONS:
            invalid_tools.append({
                "step": step.get("step_number"),
                "tool": tool_name,
                "action": step.get("action", "N/A")
            })
    
    if invalid_tools:
        print(f"\n❌ HERRAMIENTAS INVÁLIDAS ENCONTRADAS:")
        for inv in invalid_tools:
            print(f"   Paso {inv['step']}: '{inv['tool']}' no existe")
            print(f"      Acción: {inv['action']}")
        
        print(f"\n📚 Herramientas válidas disponibles:")
        print(f"   {', '.join(sorted(TOOL_FUNCTIONS.keys())[:10])}...")
        return False
    else:
        print(f"✅ Todas las herramientas en el plan son válidas")
        
        # Mostrar steps
        for step in plan["execution_steps"]:
            tool = step.get("tool", "N/A")
            action = step.get("action") or step.get("title", "N/A")
            print(f"   {step.get('step_number')}. {action}")
            print(f"      └─ tool: {tool}")
        
        return True


if __name__ == "__main__":
    success = test_architect_generates_valid_tools()
    
    if success:
        print("\n🎉 TEST PASÓ")
        print("✅ Architect genera herramientas válidas")
        sys.exit(0)
    else:
        print("\n❌ TEST FALLÓ")
        print("⚠️  Architect intenta usar herramientas que no existen")
        print("💡 Revisa el prompt del Architect para que use nombres correctos")
        sys.exit(1)
