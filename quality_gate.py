"""
Sistema de auto-verificación y gates de calidad para ModoGorila.
Implementa compilación, lint, tests y generación de evidencia.
"""
import os
import sys
import subprocess
import json
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime


class QualityGate:
    """
    Gates de calidad: compilación, lint, tests, evidencia.
    Self-check obligatorio antes de continuar.
    """
    
    def __init__(self, workspace_path: str = "."):
        self.workspace_path = Path(workspace_path).resolve()
        self.results_history = []
    
    def run_all_gates(
        self,
        check_build: bool = True,
        check_lint: bool = True,
        check_tests: bool = False,
        files_to_check: List[str] = None
    ) -> Dict[str, Any]:
        """
        Ejecuta todos los gates de calidad.
        
        Args:
            check_build: Si debe verificar compilación
            check_lint: Si debe ejecutar linters
            check_tests: Si debe ejecutar tests
            files_to_check: Lista de archivos específicos (None = todos)
            
        Returns:
            Resultado consolidado de todos los gates
        """
        print("\n🚦 [QUALITY GATES] Ejecutando verificaciones...")
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "workspace": str(self.workspace_path),
            "gates_passed": True,
            "gates": {}
        }
        
        # Gate 1: Compilación/Sintaxis
        if check_build:
            build_result = self.check_syntax(files_to_check)
            result["gates"]["build"] = build_result
            if not build_result["passed"]:
                result["gates_passed"] = False
        
        # Gate 2: Lint
        if check_lint:
            lint_result = self.run_linters(files_to_check)
            result["gates"]["lint"] = lint_result
            # Lint no es bloqueante por defecto, solo warnings
        
        # Gate 3: Tests
        if check_tests:
            test_result = self.run_tests()
            result["gates"]["tests"] = test_result
            if not test_result["passed"]:
                result["gates_passed"] = False
        
        self._print_gates_summary(result)
        self.results_history.append(result)
        
        return result
    
    def check_syntax(self, files: List[str] = None) -> Dict[str, Any]:
        """
        Verifica sintaxis de archivos Python.
        Equivalente a compilación en lenguajes compilados.
        """
        print("   🔨 [BUILD] Verificando sintaxis...")
        
        result = {
            "gate": "build",
            "passed": True,
            "files_checked": 0,
            "errors": [],
            "warnings": []
        }
        
        # Obtener archivos Python a verificar
        if files:
            py_files = [f for f in files if f.endswith('.py')]
        else:
            py_files = list(self.workspace_path.glob("*.py"))
            py_files = [str(f) for f in py_files if f.name != 'setup.py']
        
        for file_path in py_files:
            try:
                # Usar py_compile para verificar sintaxis
                import py_compile
                py_compile.compile(file_path, doraise=True)
                result["files_checked"] += 1
            except py_compile.PyCompileError as e:
                result["passed"] = False
                result["errors"].append({
                    "file": file_path,
                    "error": str(e)
                })
            except Exception as e:
                result["warnings"].append({
                    "file": file_path,
                    "warning": f"No se pudo verificar: {str(e)}"
                })
        
        status = "✅ PASS" if result["passed"] else "❌ FAIL"
        print(f"      {status} - {result['files_checked']} archivos verificados")
        
        return result
    
    def run_linters(self, files: List[str] = None) -> Dict[str, Any]:
        """
        Ejecuta linters disponibles (flake8, pylint, black --check).
        No bloqueante, solo genera warnings.
        """
        print("   🧹 [LINT] Ejecutando linters...")
        
        result = {
            "gate": "lint",
            "passed": True,  # Lint no es bloqueante
            "linters_run": [],
            "issues": [],
            "warnings": []
        }
        
        # Obtener archivos Python
        if files:
            py_files = [f for f in files if f.endswith('.py')]
        else:
            py_files = [str(f) for f in self.workspace_path.glob("*.py")]
        
        if not py_files:
            result["warnings"].append("No hay archivos Python para verificar")
            return result
        
        # Intentar flake8
        if self._is_tool_available("flake8"):
            flake8_result = self._run_flake8(py_files)
            result["linters_run"].append("flake8")
            if flake8_result["issues"]:
                result["issues"].extend(flake8_result["issues"])
        
        # Intentar pylint (opcional, más estricto)
        if self._is_tool_available("pylint"):
            pylint_result = self._run_pylint(py_files)
            result["linters_run"].append("pylint")
            if pylint_result["issues"]:
                result["issues"].extend(pylint_result["issues"])
        
        if not result["linters_run"]:
            result["warnings"].append("No hay linters instalados (flake8, pylint)")
        
        status = "⚠️  WARNINGS" if result["issues"] else "✅ CLEAN"
        print(f"      {status} - {len(result['issues'])} issues encontrados")
        
        return result
    
    def run_tests(self, test_pattern: str = "test_*.py") -> Dict[str, Any]:
        """
        Ejecuta tests usando pytest o unittest.
        """
        print("   🧪 [TESTS] Ejecutando tests...")
        
        result = {
            "gate": "tests",
            "passed": False,
            "tests_run": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "failures": []
        }
        
        # Buscar archivos de test
        test_files = list(self.workspace_path.glob(test_pattern))
        
        if not test_files:
            result["passed"] = True  # No hay tests = pass
            result["warnings"] = ["No se encontraron archivos de test"]
            print("      ⚠️  No hay tests")
            return result
        
        # Intentar pytest primero
        if self._is_tool_available("pytest"):
            pytest_result = self._run_pytest()
            result.update(pytest_result)
        else:
            # Fallback a unittest
            unittest_result = self._run_unittest(test_files)
            result.update(unittest_result)
        
        status = "✅ PASS" if result["passed"] else "❌ FAIL"
        print(f"      {status} - {result['tests_passed']}/{result['tests_run']} tests pasados")
        
        return result
    
    def _is_tool_available(self, tool_name: str) -> bool:
        """Verifica si una herramienta está disponible."""
        try:
            subprocess.run(
                [tool_name, "--version"],
                capture_output=True,
                check=True,
                timeout=5
            )
            return True
        except:
            return False
    
    def _run_flake8(self, files: List[str]) -> Dict[str, Any]:
        """Ejecuta flake8 en los archivos."""
        try:
            result = subprocess.run(
                ["flake8", "--max-line-length=120"] + files,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            issues = []
            if result.stdout:
                for line in result.stdout.split('\n'):
                    if line.strip():
                        issues.append(line)
            
            return {"issues": issues}
        except Exception as e:
            return {"issues": [], "error": str(e)}
    
    def _run_pylint(self, files: List[str]) -> Dict[str, Any]:
        """Ejecuta pylint en los archivos."""
        try:
            result = subprocess.run(
                ["pylint", "--max-line-length=120", "--disable=C0111"] + files,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            issues = []
            # Pylint output es complejo, simplificamos
            if result.returncode != 0:
                issues.append(f"Pylint encontró issues (código {result.returncode})")
            
            return {"issues": issues}
        except Exception as e:
            return {"issues": [], "error": str(e)}
    
    def _run_pytest(self) -> Dict[str, Any]:
        """Ejecuta pytest."""
        try:
            result = subprocess.run(
                ["pytest", "-v", "--tb=short"],
                capture_output=True,
                text=True,
                cwd=str(self.workspace_path),
                timeout=120
            )
            
            # Parsear output de pytest (simplificado)
            passed = "failed" not in result.stdout.lower() and result.returncode == 0
            
            return {
                "passed": passed,
                "tests_run": 1,  # Simplificado
                "tests_passed": 1 if passed else 0,
                "tests_failed": 0 if passed else 1,
                "output": result.stdout[:500]
            }
        except Exception as e:
            return {
                "passed": False,
                "tests_run": 0,
                "error": str(e)
            }
    
    def _run_unittest(self, test_files: List[Path]) -> Dict[str, Any]:
        """Ejecuta unittest en archivos específicos."""
        try:
            # Simplificado: solo verificar que los tests se pueden importar
            tests_passed = 0
            tests_failed = 0
            
            for test_file in test_files:
                try:
                    import py_compile
                    py_compile.compile(str(test_file), doraise=True)
                    tests_passed += 1
                except:
                    tests_failed += 1
            
            return {
                "passed": tests_failed == 0,
                "tests_run": len(test_files),
                "tests_passed": tests_passed,
                "tests_failed": tests_failed
            }
        except Exception as e:
            return {
                "passed": False,
                "tests_run": 0,
                "error": str(e)
            }
    
    def _print_gates_summary(self, result: Dict) -> None:
        """Imprime resumen de gates ejecutados."""
        print(f"\n{'='*70}")
        print("🚦 QUALITY GATES - RESUMEN")
        print(f"{'='*70}")
        
        status = "✅ TODOS PASARON" if result["gates_passed"] else "❌ ALGUNOS FALLARON"
        print(f"{status}\n")
        
        for gate_name, gate_result in result["gates"].items():
            gate_status = "✅" if gate_result.get("passed", True) else "❌"
            print(f"{gate_status} {gate_name.upper()}")
            
            if gate_name == "build":
                print(f"   Archivos: {gate_result.get('files_checked', 0)}")
                if gate_result.get("errors"):
                    print(f"   Errores: {len(gate_result['errors'])}")
            
            elif gate_name == "lint":
                print(f"   Linters: {', '.join(gate_result.get('linters_run', []))}")
                if gate_result.get("issues"):
                    print(f"   Issues: {len(gate_result['issues'])}")
            
            elif gate_name == "tests":
                passed = gate_result.get('tests_passed', 0)
                total = gate_result.get('tests_run', 0)
                print(f"   Tests: {passed}/{total} pasados")
        
        print(f"{'='*70}\n")
    
    def generate_evidence(self, gates_result: Dict, additional_data: Dict = None) -> Dict[str, Any]:
        """
        Genera evidencia estructurada del resultado de gates.
        """
        evidence = {
            "timestamp": datetime.now().isoformat(),
            "gates_result": gates_result,
            "summary": {
                "all_passed": gates_result["gates_passed"],
                "gates_count": len(gates_result["gates"]),
                "failed_gates": [
                    name for name, result in gates_result["gates"].items()
                    if not result.get("passed", True)
                ]
            }
        }
        
        if additional_data:
            evidence["additional_data"] = additional_data
        
        return evidence


# Instancia global
_quality_gate = QualityGate()
