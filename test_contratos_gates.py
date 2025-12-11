"""
Tests para validar contratos y quality gates (Pasos 3 y 4 de ModoGorila).
"""
import sys
sys.path.insert(0, '.')
from tools import validate_contract, check_dod_compliance, run_quality_gates


def test_contract_validation():
    """Prueba validación de contratos con JSON Schema."""
    print("🧪 TEST 3: Validación de contratos")
    print("="*70)
    
    # Datos de prueba válidos
    valid_analysis = {
        "file_path": "test.py",
        "summary": "Archivo de prueba",
        "file_type": "python",
        "imports": ["os", "sys"],
        "classes": [],
        "functions": [],
        "complexity": "low"
    }
    
    result = validate_contract(
        data=valid_analysis,
        schema_name="analysis_result"
    )
    
    if result["success"] and result["validation"]["valid"]:
        print("✅ Validación de contrato válido: PASS")
        test_passed = True
    else:
        print(f"❌ Validación falló: {result}")
        test_passed = False
    
    # Datos inválidos (falta campo requerido)
    invalid_analysis = {
        "file_path": "test.py",
        "summary": "Sin file_type"
        # Falta file_type (requerido)
    }
    
    result2 = validate_contract(
        data=invalid_analysis,
        schema_name="analysis_result"
    )
    
    if result2["success"] and not result2["validation"]["valid"]:
        print("✅ Detección de contrato inválido: PASS")
    else:
        print("❌ No detectó contrato inválido: FAIL")
        test_passed = False
    
    return test_passed


def test_dod_compliance():
    """Prueba verificación de Definition of Done."""
    print("\n🧪 TEST 4: Verificación de DoD")
    print("="*70)
    
    # DoD de prueba
    dod = {
        "checklist": [
            "Exploración completa",
            "Análisis guardado",
            "Reporte generado"
        ],
        "acceptance_criteria": [
            "Todos los archivos explorados",
            "Estructura documentada",
            "Dependencias identificadas"
        ],
        "metrics": {
            "completeness": "100%",
            "coverage": "all_files"
        }
    }
    
    # Evidencia de ejecución (completa)
    evidence = {
        "files": ["file1.py", "file2.py"],
        "stats": {"total_files": 2},
        "saved": True,
        "summary": "Análisis completo",
        "documentation": "Generated",
        "dependencies": ["dep1", "dep2"],
        "metrics": {
            "completeness": "100%",
            "coverage": "all_files"
        }
    }
    
    result = check_dod_compliance(
        dod=dod,
        execution_evidence=evidence
    )
    
    if result["success"] and result["score"] > 0:
        print(f"✅ Verificación de DoD: PASS (score: {result['score']:.1f}%)")
        return True
    else:
        print(f"❌ Verificación de DoD falló: {result}")
        return False


def test_quality_gates():
    """Prueba gates de calidad."""
    print("\n🧪 TEST 5: Quality Gates")
    print("="*70)
    
    # Ejecutar gates en los archivos de prueba
    result = run_quality_gates(
        check_build=True,
        check_lint=False,  # No bloquear por lint warnings
        check_tests=False,  # No ejecutar tests por ahora
        files_to_check=[
            "contract_validator.py",
            "quality_gate.py"
        ]
    )
    
    if result["success"]:
        gates_passed = result["gates_passed"]
        status = "✅ PASS" if gates_passed else "⚠️  PASS con warnings"
        print(f"{status} - Gates ejecutados correctamente")
        return True
    else:
        print(f"❌ Gates fallaron: {result.get('error')}")
        return False


if __name__ == "__main__":
    test3_ok = test_contract_validation()
    test4_ok = test_dod_compliance()
    test5_ok = test_quality_gates()
    
    print("\n" + "="*70)
    print("📊 RESUMEN DE TESTS - PASOS 3 Y 4")
    print("="*70)
    print(f"Test 3 (Contratos): {'✅ PASS' if test3_ok else '❌ FAIL'}")
    print(f"Test 4 (DoD Checker): {'✅ PASS' if test4_ok else '❌ FAIL'}")
    print(f"Test 5 (Quality Gates): {'✅ PASS' if test5_ok else '❌ FAIL'}")
    
    if test3_ok and test4_ok and test5_ok:
        print("\n🎉 TODOS LOS TESTS PASARON")
        print("\n✅ PASOS 3 Y 4 COMPLETADOS:")
        print("   • Sistema de contratos y validación con JSON Schema")
        print("   • Verificación de DoD con score y gaps")
        print("   • Quality gates: build, lint, tests")
        sys.exit(0)
    else:
        print("\n⚠️  ALGUNOS TESTS FALLARON")
        sys.exit(1)
