"""
Script de prueba para validar las nuevas funcionalidades de ModoGorila.
"""
import sys
sys.path.insert(0, '.')
from tools import generate_analysis_plan, explore_directory

def test_architect():
    """Prueba la generación de plan con el Arquitecto."""
    print("🧪 TEST 1: Generar plan de análisis")
    print("="*70)
    
    result = generate_analysis_plan(
        repository_path='c:/Users/pvargas/Desktop/Agente',
        user_requirements='Analizar este agente multi-herramienta para entender su arquitectura completa',
        scope='quick'
    )
    
    if result['success']:
        plan = result['plan']
        steps = len(plan.get("execution_steps", []))
        objectives = len(plan.get("spec_pack", {}).get("objectives", []))
        checklist = len(plan.get("dod", {}).get("checklist", []))
        
        print(f"✅ Plan generado con {steps} pasos")
        print(f"✅ Objetivos: {objectives}")
        print(f"✅ DoD: {checklist} items")
        return True
    else:
        print(f"❌ Error: {result.get('error')}")
        return False


def test_deep_exploration():
    """Prueba la exploración profunda sin límites."""
    print("\n🧪 TEST 2: Exploración profunda sin límites")
    print("="*70)
    
    result = explore_directory(
        'c:/Users/pvargas/Desktop/Agente',
        recursive=True,
        max_depth=None,
        analyze_architecture=True
    )
    
    if 'error' not in result:
        stats = result['stats']
        arch = result.get('architecture', {})
        
        print(f"✅ Archivos encontrados: {stats['total_files']}")
        print(f"✅ Profundidad alcanzada: {stats['max_depth_reached']}")
        print(f"✅ Frameworks detectados: {arch.get('detected_frameworks', [])}")
        print(f"✅ Lenguajes: {arch.get('detected_languages', [])}")
        print(f"✅ Entry points: {len(arch.get('entry_points', []))}")
        print(f"✅ Archivos de dependencias: {len(arch.get('dependency_files', []))}")
        return True
    else:
        print(f"❌ Error: {result['error']}")
        return False


if __name__ == "__main__":
    test1_ok = test_architect()
    test2_ok = test_deep_exploration()
    
    print("\n" + "="*70)
    print("📊 RESUMEN DE TESTS")
    print("="*70)
    print(f"Test 1 (Arquitecto): {'✅ PASS' if test1_ok else '❌ FAIL'}")
    print(f"Test 2 (Exploración): {'✅ PASS' if test2_ok else '❌ FAIL'}")
    
    if test1_ok and test2_ok:
        print("\n🎉 TODOS LOS TESTS PASARON")
        sys.exit(0)
    else:
        print("\n⚠️  ALGUNOS TESTS FALLARON")
        sys.exit(1)
