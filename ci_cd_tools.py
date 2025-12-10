"""
Herramientas para integración con CI/CD.
Ejecuta linters, tests, validación de builds y checks de deployment.
"""
import env_loader  # Cargar .env PRIMERO
import subprocess
import json
from pathlib import Path
from typing import Dict, Any, List
from openai import OpenAI

from config import ORCHESTRATOR_MODEL


class CICDTools:
    """Herramientas para CI/CD y validación automática."""
    
    def __init__(self):
        self.client = OpenAI()
        self.model = ORCHESTRATOR_MODEL
    
    def run_linters(self, directory: str, linters: List[str] = None) -> Dict[str, Any]:
        """
        Ejecuta linters en el proyecto.
        
        Args:
            directory: Directorio del proyecto
            linters: Lista de linters a ejecutar (ej: ['pylint', 'flake8', 'eslint'])
            
        Returns:
            Resultados de los linters
        """
        print(f"🔍 Ejecutando linters en: {directory}")
        
        if linters is None:
            # Auto-detectar según archivos
            linters = self._detect_linters(directory)
        
        results = {
            "success": True,
            "directory": directory,
            "linters_run": [],
            "issues_found": 0,
            "details": []
        }
        
        for linter in linters:
            print(f"  Ejecutando {linter}...")
            result = self._run_linter(linter, directory)
            results["linters_run"].append(linter)
            results["details"].append(result)
            results["issues_found"] += result.get("issues", 0)
        
        results["status"] = "passed" if results["issues_found"] == 0 else "failed"
        print(f"✅ Linters completados: {results['issues_found']} issues encontrados")
        
        return results
    
    def _detect_linters(self, directory: str) -> List[str]:
        """Detecta qué linters usar según los archivos del proyecto."""
        dir_path = Path(directory)
        linters = []
        
        # Detectar Python
        if list(dir_path.rglob("*.py")):
            linters.extend(["pylint", "flake8"])
        
        # Detectar JavaScript/TypeScript
        if list(dir_path.rglob("*.js")) or list(dir_path.rglob("*.ts")):
            linters.append("eslint")
        
        return linters if linters else ["pylint"]  # Default
    
    def _run_linter(self, linter: str, directory: str) -> Dict[str, Any]:
        """Ejecuta un linter específico."""
        try:
            if linter == "pylint":
                cmd = ["pylint", directory, "--output-format=json"]
            elif linter == "flake8":
                cmd = ["flake8", directory, "--format=json"]
            elif linter == "eslint":
                cmd = ["eslint", directory, "--format=json"]
            else:
                return {"linter": linter, "error": "Linter no soportado"}
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            # Parsear salida
            if result.returncode == 0:
                return {
                    "linter": linter,
                    "status": "passed",
                    "issues": 0,
                    "message": "Sin problemas encontrados"
                }
            else:
                # Intentar parsear JSON si está disponible
                try:
                    output = json.loads(result.stdout) if result.stdout else []
                    return {
                        "linter": linter,
                        "status": "failed",
                        "issues": len(output),
                        "details": output[:10]  # Primeros 10
                    }
                except:
                    return {
                        "linter": linter,
                        "status": "failed",
                        "issues": result.stdout.count("\n"),
                        "output": result.stdout[:500]
                    }
        
        except subprocess.TimeoutExpired:
            return {"linter": linter, "error": "Timeout excedido"}
        except FileNotFoundError:
            return {"linter": linter, "error": f"{linter} no está instalado"}
        except Exception as e:
            return {"linter": linter, "error": str(e)}
    
    def run_tests(self, directory: str, framework: str = None) -> Dict[str, Any]:
        """
        Ejecuta tests del proyecto.
        
        Args:
            directory: Directorio del proyecto
            framework: Framework de testing (pytest, unittest, jest)
            
        Returns:
            Resultados de los tests
        """
        print(f"🧪 Ejecutando tests en: {directory}")
        
        if not framework:
            framework = self._detect_test_framework(directory)
        
        try:
            if framework == "pytest":
                cmd = ["pytest", directory, "-v", "--tb=short"]
            elif framework == "unittest":
                cmd = ["python", "-m", "unittest", "discover", directory]
            elif framework == "jest":
                cmd = ["jest", directory]
            else:
                return {"error": f"Framework {framework} no soportado"}
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=directory
            )
            
            return {
                "success": result.returncode == 0,
                "framework": framework,
                "status": "passed" if result.returncode == 0 else "failed",
                "output": result.stdout,
                "errors": result.stderr if result.returncode != 0 else None
            }
        
        except subprocess.TimeoutExpired:
            return {"error": "Tests excedieron el timeout de 120s"}
        except FileNotFoundError:
            return {"error": f"{framework} no está instalado"}
        except Exception as e:
            return {"error": str(e)}
    
    def _detect_test_framework(self, directory: str) -> str:
        """Detecta el framework de testing usado."""
        dir_path = Path(directory)
        
        # Buscar pytest.ini o pyproject.toml
        if (dir_path / "pytest.ini").exists() or (dir_path / "pyproject.toml").exists():
            return "pytest"
        
        # Buscar package.json con jest
        package_json = dir_path / "package.json"
        if package_json.exists():
            try:
                with open(package_json) as f:
                    data = json.load(f)
                    if "jest" in data.get("devDependencies", {}):
                        return "jest"
            except:
                pass
        
        # Default a pytest para Python
        return "pytest"
    
    def check_build(self, directory: str) -> Dict[str, Any]:
        """
        Valida que el proyecto compile/build correctamente.
        
        Args:
            directory: Directorio del proyecto
            
        Returns:
            Estado del build
        """
        print(f"🔨 Verificando build en: {directory}")
        
        dir_path = Path(directory)
        
        # Detectar tipo de proyecto
        if (dir_path / "setup.py").exists():
            cmd = ["python", "setup.py", "check"]
        elif (dir_path / "pyproject.toml").exists():
            cmd = ["python", "-m", "build", "--wheel", "--no-isolation"]
        elif (dir_path / "package.json").exists():
            cmd = ["npm", "run", "build"]
        elif (dir_path / "Makefile").exists():
            cmd = ["make", "build"]
        else:
            return {"error": "No se encontró configuración de build"}
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=180,
                cwd=directory
            )
            
            return {
                "success": result.returncode == 0,
                "status": "passed" if result.returncode == 0 else "failed",
                "command": " ".join(cmd),
                "output": result.stdout[-1000:] if len(result.stdout) > 1000 else result.stdout,
                "errors": result.stderr if result.returncode != 0 else None
            }
        
        except subprocess.TimeoutExpired:
            return {"error": "Build excedió el timeout de 180s"}
        except Exception as e:
            return {"error": str(e)}
    
    def deployment_check(self, directory: str) -> Dict[str, Any]:
        """
        Verifica que el proyecto esté listo para deployment.
        
        Args:
            directory: Directorio del proyecto
            
        Returns:
            Checklist de deployment
        """
        print(f"🚀 Verificando readiness de deployment: {directory}")
        
        dir_path = Path(directory)
        checks = {
            "success": True,
            "directory": directory,
            "checks": []
        }
        
        # Check 1: README existe
        readme = dir_path / "README.md"
        checks["checks"].append({
            "name": "README.md",
            "status": "passed" if readme.exists() else "failed",
            "critical": False
        })
        
        # Check 2: .gitignore existe
        gitignore = dir_path / ".gitignore"
        checks["checks"].append({
            "name": ".gitignore",
            "status": "passed" if gitignore.exists() else "failed",
            "critical": False
        })
        
        # Check 3: requirements.txt o package.json
        deps = (dir_path / "requirements.txt").exists() or (dir_path / "package.json").exists()
        checks["checks"].append({
            "name": "Archivo de dependencias",
            "status": "passed" if deps else "failed",
            "critical": True
        })
        
        # Check 4: Dockerfile
        dockerfile = dir_path / "Dockerfile"
        checks["checks"].append({
            "name": "Dockerfile",
            "status": "passed" if dockerfile.exists() else "warning",
            "critical": False
        })
        
        # Check 5: Tests existen
        has_tests = bool(list(dir_path.rglob("test_*.py"))) or bool(list(dir_path.rglob("*.test.js")))
        checks["checks"].append({
            "name": "Tests",
            "status": "passed" if has_tests else "warning",
            "critical": True
        })
        
        # Check 6: No secretos en código
        secret_patterns = [".env", "password", "api_key", "secret"]
        found_secrets = []
        for py_file in dir_path.rglob("*.py"):
            try:
                content = py_file.read_text(encoding='utf-8').lower()
                for pattern in secret_patterns:
                    if pattern in content and "=" in content:
                        found_secrets.append(str(py_file))
                        break
            except:
                pass
        
        checks["checks"].append({
            "name": "Seguridad (secretos hardcodeados)",
            "status": "failed" if found_secrets else "passed",
            "critical": True,
            "details": found_secrets[:5] if found_secrets else None
        })
        
        # Determinar estado general
        failed_critical = [c for c in checks["checks"] if c["status"] == "failed" and c.get("critical")]
        if failed_critical:
            checks["success"] = False
            checks["overall_status"] = "not_ready"
        else:
            checks["overall_status"] = "ready"
        
        print(f"✅ Deployment check: {checks['overall_status']}")
        return checks
