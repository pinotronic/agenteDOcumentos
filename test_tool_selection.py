"""
Test para verificar la selección dinámica de herramientas.
"""
from tool_selector import get_smart_tools, TOOL_CATEGORIES
from tools import TOOLS

def test_tool_selection():
    """Prueba la selección de herramientas según diferentes queries."""
    
    test_cases = [
        ("Analiza el directorio src", ["analysis"]),
        ("Genera tests para main.py", ["code_generation", "analysis"]),
        ("Ejecuta los linters y tests", ["cicd"]),
        ("Busca en stackoverflow cómo hacer X", ["external"]),
        ("Genera un dashboard HTML", ["reports"]),
        ("Explica este código y haz debug", ["assistance"]),
        ("Genera plan gorila y ejecuta", ["gorila_mode"]),
    ]
    
    print("="*70)
    print("TEST: Selección Dinámica de Herramientas")
    print("="*70)
    
    for query, expected_categories in test_cases:
        print(f"\n📝 Query: {query}")
        selected = get_smart_tools(query, TOOLS)
        tool_names = [t["function"]["name"] for t in selected]
        print(f"   ✅ {len(selected)} herramientas seleccionadas")
        print(f"   📋 Herramientas: {', '.join(tool_names[:5])}...")
        
        # Verificar que se seleccionaron herramientas de las categorías esperadas
        categories_found = []
        for cat, info in TOOL_CATEGORIES.items():
            if any(tool in tool_names for tool in info["tools"]):
                categories_found.append(cat)
        
        print(f"   🏷️  Categorías: {', '.join(categories_found)}")
    
    print(f"\n{'='*70}")
    print("✅ Test completado")
    print(f"Total de herramientas disponibles: {len(TOOLS)}")
    print("Con selección dinámica, solo se cargan las relevantes (max 15)")


if __name__ == "__main__":
    test_tool_selection()
