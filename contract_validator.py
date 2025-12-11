"""
Sistema de contratos y validación para ModoGorila.
Valida outputs con JSON Schema y verifica cumplimiento de DoD.
"""
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
try:
    from jsonschema import validate, ValidationError, Draft7Validator
except ImportError:
    print("⚠️  jsonschema no disponible, instalando...")
    import subprocess
    subprocess.check_call(['pip', 'install', 'jsonschema'])
    from jsonschema import validate, ValidationError, Draft7Validator


class ContractValidator:
    """
    Valida contratos de datos usando JSON Schema.
    Verifica que los outputs cumplan con las especificaciones.
    """
    
    # Esquemas predefinidos para outputs comunes
    SCHEMAS = {
        "analysis_result": {
            "type": "object",
            "required": ["file_path", "summary", "file_type"],
            "properties": {
                "file_path": {"type": "string"},
                "summary": {"type": "string"},
                "file_type": {"type": "string"},
                "imports": {"type": "array", "items": {"type": "string"}},
                "classes": {"type": "array"},
                "functions": {"type": "array"},
                "complexity": {"type": "string", "enum": ["low", "medium", "high"]}
            }
        },
        "exploration_result": {
            "type": "object",
            "required": ["directory", "files", "stats"],
            "properties": {
                "directory": {"type": "string"},
                "files": {"type": "array"},
                "subdirectories": {"type": "array"},
                "stats": {
                    "type": "object",
                    "required": ["total_files"],
                    "properties": {
                        "total_files": {"type": "integer", "minimum": 0},
                        "by_type": {"type": "object"},
                        "ignored": {"type": "integer", "minimum": 0}
                    }
                }
            }
        },
        "plan_result": {
            "type": "object",
            "required": ["spec_pack", "execution_steps", "dod"],
            "properties": {
                "spec_pack": {
                    "type": "object",
                    "required": ["objectives"],
                    "properties": {
                        "prd": {"type": "string"},
                        "objectives": {"type": "array", "minItems": 1},
                        "assumptions": {"type": "array"},
                        "scope": {"type": "object"}
                    }
                },
                "execution_steps": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "required": ["step_number", "title", "description"],
                        "properties": {
                            "step_number": {"type": "integer", "minimum": 1},
                            "title": {"type": "string"},
                            "description": {"type": "string"}
                        }
                    }
                },
                "dod": {
                    "type": "object",
                    "required": ["acceptance_criteria", "checklist"],
                    "properties": {
                        "acceptance_criteria": {"type": "array", "minItems": 1},
                        "checklist": {"type": "array", "minItems": 1}
                    }
                }
            }
        }
    }
    
    def validate_output(
        self,
        data: Any,
        schema_name: str = None,
        custom_schema: Dict = None
    ) -> Dict[str, Any]:
        """
        Valida un output contra un JSON Schema.
        
        Args:
            data: Datos a validar
            schema_name: Nombre del schema predefinido
            custom_schema: Schema personalizado (si no se usa predefinido)
            
        Returns:
            Resultado de validación con errores si los hay
        """
        if custom_schema:
            schema = custom_schema
        elif schema_name in self.SCHEMAS:
            schema = self.SCHEMAS[schema_name]
        else:
            return {
                "valid": False,
                "error": f"Schema '{schema_name}' no encontrado"
            }
        
        try:
            validate(instance=data, schema=schema)
            return {
                "valid": True,
                "message": "Validación exitosa",
                "schema_name": schema_name or "custom"
            }
        except ValidationError as e:
            return {
                "valid": False,
                "error": str(e.message),
                "path": list(e.path),
                "schema_path": list(e.schema_path)
            }
        except Exception as e:
            return {
                "valid": False,
                "error": f"Error de validación: {str(e)}"
            }
    
    def generate_schema_from_sample(self, sample_data: Dict) -> Dict:
        """
        Genera un JSON Schema básico a partir de datos de ejemplo.
        Útil para crear contratos rápidamente.
        """
        def infer_type(value):
            if isinstance(value, bool):
                return "boolean"
            elif isinstance(value, int):
                return "integer"
            elif isinstance(value, float):
                return "number"
            elif isinstance(value, str):
                return "string"
            elif isinstance(value, list):
                return "array"
            elif isinstance(value, dict):
                return "object"
            else:
                return "string"
        
        def build_schema(data):
            if isinstance(data, dict):
                properties = {}
                required = []
                for key, value in data.items():
                    properties[key] = build_schema(value)
                    required.append(key)
                return {
                    "type": "object",
                    "required": required,
                    "properties": properties
                }
            elif isinstance(data, list) and data:
                return {
                    "type": "array",
                    "items": build_schema(data[0])
                }
            else:
                return {"type": infer_type(data)}
        
        return build_schema(sample_data)


class DoDChecker:
    """
    Verifica cumplimiento de Definition of Done.
    Valida que se cumplan todos los criterios de aceptación.
    """
    
    def __init__(self):
        self.checks_history = []
    
    def check_dod(
        self,
        dod: Dict[str, Any],
        execution_evidence: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Verifica que se cumplan los criterios del DoD.
        
        Args:
            dod: Definition of Done con criterios y checklist
            execution_evidence: Evidencia de ejecución con resultados
            
        Returns:
            Reporte de cumplimiento con gaps
        """
        print("\n✅ [DoD CHECKER] Verificando Definition of Done...")
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "dod_satisfied": True,
            "checklist_status": {},
            "criteria_status": {},
            "metrics_status": {},
            "gaps": [],
            "score": 0.0
        }
        
        # Verificar checklist
        checklist = dod.get("checklist", [])
        for item in checklist:
            # Lógica simplificada: buscar evidencia relacionada
            is_done = self._check_checklist_item(item, execution_evidence)
            result["checklist_status"][item] = "✅ Done" if is_done else "⏳ Pending"
            if not is_done:
                result["gaps"].append(f"Checklist: {item}")
                result["dod_satisfied"] = False
        
        # Verificar criterios de aceptación
        criteria = dod.get("acceptance_criteria", [])
        for criterion in criteria:
            is_met = self._check_acceptance_criterion(criterion, execution_evidence)
            result["criteria_status"][criterion] = "✅ Met" if is_met else "❌ Not Met"
            if not is_met:
                result["gaps"].append(f"Criterio: {criterion}")
                result["dod_satisfied"] = False
        
        # Verificar métricas
        metrics = dod.get("metrics", {})
        for metric_name, target_value in metrics.items():
            actual_value = execution_evidence.get("metrics", {}).get(metric_name)
            is_met = actual_value == target_value if actual_value else False
            result["metrics_status"][metric_name] = {
                "target": target_value,
                "actual": actual_value,
                "met": is_met
            }
            if not is_met:
                result["gaps"].append(f"Métrica '{metric_name}': esperado {target_value}, obtenido {actual_value}")
        
        # Calcular score
        total_items = len(checklist) + len(criteria) + len(metrics)
        if total_items > 0:
            done_items = sum([
                1 for status in result["checklist_status"].values() if "Done" in status
            ]) + sum([
                1 for status in result["criteria_status"].values() if "Met" in status
            ]) + sum([
                1 for m in result["metrics_status"].values() if m["met"]
            ])
            result["score"] = (done_items / total_items) * 100
        
        self._print_dod_summary(result)
        self.checks_history.append(result)
        
        return result
    
    def _check_checklist_item(self, item: str, evidence: Dict) -> bool:
        """Verifica si un item del checklist está completo."""
        # Heurística simple: buscar keywords en evidencia
        item_lower = item.lower()
        evidence_str = json.dumps(evidence).lower()
        
        # Palabras clave que indican completitud
        if "exploración completa" in item_lower or "exploration" in item_lower:
            return "files" in evidence and "stats" in evidence
        elif "análisis guardado" in item_lower or "saved" in item_lower:
            return "saved" in evidence_str or "stored" in evidence_str
        elif "reporte generado" in item_lower or "report" in item_lower:
            return "report" in evidence_str or "summary" in evidence_str
        elif "compila" in item_lower or "build" in item_lower:
            return evidence.get("build_status") == "success"
        elif "test" in item_lower:
            return evidence.get("tests_passed", False)
        
        # Default: marcar como pendiente si no hay evidencia clara
        return False
    
    def _check_acceptance_criterion(self, criterion: str, evidence: Dict) -> bool:
        """Verifica si se cumple un criterio de aceptación."""
        criterion_lower = criterion.lower()
        
        # Heurísticas para criterios comunes
        if "todos los archivos" in criterion_lower or "all files" in criterion_lower:
            total_files = evidence.get("stats", {}).get("total_files", 0)
            return total_files > 0
        elif "estructura documentada" in criterion_lower or "structure documented" in criterion_lower:
            return "documentation" in evidence or "summary" in evidence
        elif "dependencias identificadas" in criterion_lower or "dependencies" in criterion_lower:
            return "dependencies" in evidence or "imports" in evidence
        
        return False
    
    def _print_dod_summary(self, result: Dict) -> None:
        """Imprime resumen de verificación de DoD."""
        print(f"\n{'='*70}")
        print("📋 VERIFICACIÓN DE DoD")
        print(f"{'='*70}")
        print(f"✅ DoD Satisfecho: {'SÍ' if result['dod_satisfied'] else 'NO'}")
        print(f"📊 Score: {result['score']:.1f}%")
        
        if result["checklist_status"]:
            print(f"\n📝 CHECKLIST:")
            for item, status in list(result["checklist_status"].items())[:5]:
                print(f"   {status} {item}")
        
        if result["criteria_status"]:
            print(f"\n🎯 CRITERIOS:")
            for criterion, status in list(result["criteria_status"].items())[:5]:
                print(f"   {status} {criterion}")
        
        if result["gaps"]:
            print(f"\n⚠️  GAPS ({len(result['gaps'])}):")
            for gap in result["gaps"][:5]:
                print(f"   • {gap}")
        
        print(f"{'='*70}\n")


# Instancia global para reutilizar
_contract_validator = ContractValidator()
_dod_checker = DoDChecker()
