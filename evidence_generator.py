"""
Generador de Evidencia estructurada para ModoGorila.
Genera diffs, bloques de archivo, reportes de build/lint/test, DoD checklist, métricas.
"""
import json
import difflib
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path


class EvidenceGenerator:
    """
    Genera evidencia estructurada de cambios, ejecuciones y validaciones.
    Formato estándar para documentar cada paso del proceso.
    """
    
    def __init__(self):
        self.evidence_history = []
    
    def generate_unified_diff(
        self,
        file_path: str,
        original_content: str,
        modified_content: str
    ) -> Dict[str, Any]:
        """
        Genera un unified diff entre contenido original y modificado.
        
        Args:
            file_path: Ruta del archivo
            original_content: Contenido original
            modified_content: Contenido modificado
            
        Returns:
            Diff en formato unificado con estadísticas
        """
        original_lines = original_content.splitlines(keepends=True)
        modified_lines = modified_content.splitlines(keepends=True)
        
        diff = list(difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm=''
        ))
        
        # Calcular estadísticas
        additions = sum(1 for line in diff if line.startswith('+') and not line.startswith('+++'))
        deletions = sum(1 for line in diff if line.startswith('-') and not line.startswith('---'))
        
        return {
            "file_path": file_path,
            "format": "unified_diff",
            "diff_lines": diff,
            "diff_text": '\n'.join(diff),
            "stats": {
                "additions": additions,
                "deletions": deletions,
                "changes": additions + deletions
            }
        }
    
    def generate_file_block(
        self,
        file_path: str,
        content: str,
        start_line: int = None,
        end_line: int = None
    ) -> Dict[str, Any]:
        """
        Genera un bloque de archivo completo o parcial.
        Útil cuando unified diff no es viable.
        
        Args:
            file_path: Ruta del archivo
            content: Contenido completo del archivo
            start_line: Línea inicial (None = desde inicio)
            end_line: Línea final (None = hasta final)
            
        Returns:
            Bloque de archivo con metadatos
        """
        lines = content.splitlines()
        
        if start_line is not None and end_line is not None:
            selected_lines = lines[start_line-1:end_line]
        else:
            selected_lines = lines
        
        return {
            "file_path": file_path,
            "format": "file_block",
            "content": '\n'.join(selected_lines),
            "line_range": {
                "start": start_line or 1,
                "end": end_line or len(lines)
            },
            "stats": {
                "total_lines": len(selected_lines),
                "file_size": len(content)
            }
        }
    
    def generate_execution_evidence(
        self,
        step_title: str,
        gates_result: Dict = None,
        dod_result: Dict = None,
        validation_result: Dict = None,
        custom_data: Dict = None
    ) -> Dict[str, Any]:
        """
        Genera evidencia completa de ejecución de un paso.
        
        Args:
            step_title: Título del paso ejecutado
            gates_result: Resultado de quality gates
            dod_result: Resultado de verificación de DoD
            validation_result: Resultado de validación de contratos
            custom_data: Datos adicionales personalizados
            
        Returns:
            Evidencia estructurada completa
        """
        evidence = {
            "timestamp": datetime.now().isoformat(),
            "step_title": step_title,
            "evidence_type": "execution",
            "summary": {}
        }
        
        # Quality Gates
        if gates_result:
            evidence["quality_gates"] = {
                "all_passed": gates_result.get("gates_passed", False),
                "gates": gates_result.get("gates", {}),
                "summary": self._summarize_gates(gates_result)
            }
            evidence["summary"]["gates_passed"] = gates_result.get("gates_passed", False)
        
        # DoD Compliance
        if dod_result:
            evidence["dod_compliance"] = {
                "satisfied": dod_result.get("dod_satisfied", False),
                "score": dod_result.get("score", 0),
                "checklist": dod_result.get("checklist_status", {}),
                "criteria": dod_result.get("criteria_status", {}),
                "gaps": dod_result.get("gaps", [])
            }
            evidence["summary"]["dod_satisfied"] = dod_result.get("dod_satisfied", False)
            evidence["summary"]["dod_score"] = dod_result.get("score", 0)
        
        # Contract Validation
        if validation_result:
            evidence["contract_validation"] = {
                "valid": validation_result.get("valid", False),
                "schema_name": validation_result.get("schema_name"),
                "errors": validation_result.get("error")
            }
            evidence["summary"]["contract_valid"] = validation_result.get("valid", False)
        
        # Custom data
        if custom_data:
            evidence["custom_data"] = custom_data
        
        self.evidence_history.append(evidence)
        return evidence
    
    def generate_dod_checklist_report(
        self,
        dod: Dict[str, Any],
        status: Dict[str, Any]
    ) -> str:
        """
        Genera un reporte visual de DoD checklist en formato Markdown.
        
        Args:
            dod: Definition of Done original
            status: Estado actual de cumplimiento
            
        Returns:
            Reporte en formato Markdown
        """
        report_lines = ["# Definition of Done - Checklist\n"]
        report_lines.append(f"**Timestamp:** {datetime.now().isoformat()}\n")
        report_lines.append(f"**Score:** {status.get('score', 0):.1f}%\n")
        report_lines.append(f"**Status:** {'✅ SATISFIED' if status.get('dod_satisfied') else '❌ NOT SATISFIED'}\n")
        
        # Checklist
        if "checklist_status" in status:
            report_lines.append("\n## Checklist\n")
            for item, item_status in status["checklist_status"].items():
                checkbox = "[x]" if "Done" in item_status else "[ ]"
                report_lines.append(f"- {checkbox} {item}")
        
        # Acceptance Criteria
        if "criteria_status" in status:
            report_lines.append("\n## Acceptance Criteria\n")
            for criterion, criterion_status in status["criteria_status"].items():
                checkbox = "[x]" if "Met" in criterion_status else "[ ]"
                report_lines.append(f"- {checkbox} {criterion}")
        
        # Gaps
        if status.get("gaps"):
            report_lines.append("\n## Gaps\n")
            for gap in status["gaps"]:
                report_lines.append(f"- ⚠️  {gap}")
        
        # Metrics
        if "metrics_status" in status:
            report_lines.append("\n## Metrics\n")
            report_lines.append("| Metric | Target | Actual | Status |")
            report_lines.append("|--------|--------|--------|--------|")
            for metric_name, metric_data in status["metrics_status"].items():
                status_icon = "✅" if metric_data.get("met") else "❌"
                report_lines.append(
                    f"| {metric_name} | {metric_data.get('target')} | "
                    f"{metric_data.get('actual')} | {status_icon} |"
                )
        
        return '\n'.join(report_lines)
    
    def generate_metrics_summary(
        self,
        execution_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Genera resumen de métricas de ejecución.
        
        Args:
            execution_data: Datos de ejecución con estadísticas
            
        Returns:
            Métricas consolidadas
        """
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "execution": {},
            "quality": {},
            "coverage": {}
        }
        
        # Métricas de ejecución
        if "duration" in execution_data:
            metrics["execution"]["duration_seconds"] = execution_data["duration"]
        
        if "files_processed" in execution_data:
            metrics["execution"]["files_processed"] = execution_data["files_processed"]
        
        if "lines_changed" in execution_data:
            metrics["execution"]["lines_changed"] = execution_data["lines_changed"]
        
        # Métricas de calidad
        if "gates_passed" in execution_data:
            metrics["quality"]["gates_passed"] = execution_data["gates_passed"]
        
        if "tests_passed" in execution_data:
            metrics["quality"]["tests_passed"] = execution_data["tests_passed"]
            metrics["quality"]["tests_total"] = execution_data.get("tests_total", 0)
        
        if "dod_score" in execution_data:
            metrics["quality"]["dod_score"] = execution_data["dod_score"]
        
        # Métricas de cobertura
        if "code_coverage" in execution_data:
            metrics["coverage"]["code_percentage"] = execution_data["code_coverage"]
        
        return metrics
    
    def _summarize_gates(self, gates_result: Dict) -> str:
        """Genera resumen textual de gates."""
        gates = gates_result.get("gates", {})
        passed_count = sum(1 for g in gates.values() if g.get("passed", True))
        total_count = len(gates)
        
        return f"{passed_count}/{total_count} gates passed"
    
    def export_evidence_to_markdown(
        self,
        evidence: Dict[str, Any],
        output_file: str = None
    ) -> str:
        """
        Exporta evidencia completa a formato Markdown.
        
        Args:
            evidence: Evidencia generada
            output_file: Archivo de salida (opcional)
            
        Returns:
            Contenido Markdown
        """
        lines = []
        lines.append(f"# Evidencia de Ejecución\n")
        lines.append(f"**Paso:** {evidence.get('step_title', 'N/A')}\n")
        lines.append(f"**Timestamp:** {evidence.get('timestamp')}\n")
        
        # Summary
        if "summary" in evidence:
            lines.append("\n## Resumen\n")
            for key, value in evidence["summary"].items():
                lines.append(f"- **{key}:** {value}")
        
        # Quality Gates
        if "quality_gates" in evidence:
            qg = evidence["quality_gates"]
            lines.append("\n## Quality Gates\n")
            lines.append(f"**Status:** {'✅ PASSED' if qg['all_passed'] else '❌ FAILED'}\n")
            lines.append(f"**Summary:** {qg.get('summary', 'N/A')}\n")
        
        # DoD Compliance
        if "dod_compliance" in evidence:
            dod = evidence["dod_compliance"]
            lines.append("\n## DoD Compliance\n")
            lines.append(f"**Satisfied:** {'✅ YES' if dod['satisfied'] else '❌ NO'}\n")
            lines.append(f"**Score:** {dod['score']:.1f}%\n")
            
            if dod.get("gaps"):
                lines.append("\n**Gaps:**")
                for gap in dod["gaps"]:
                    lines.append(f"- {gap}")
        
        # Contract Validation
        if "contract_validation" in evidence:
            cv = evidence["contract_validation"]
            lines.append("\n## Contract Validation\n")
            lines.append(f"**Valid:** {'✅ YES' if cv['valid'] else '❌ NO'}\n")
            if cv.get("errors"):
                lines.append(f"**Error:** {cv['errors']}\n")
        
        markdown_content = '\n'.join(lines)
        
        # Guardar a archivo si se especifica
        if output_file:
            Path(output_file).write_text(markdown_content, encoding='utf-8')
        
        return markdown_content


# Instancia global
_evidence_generator = EvidenceGenerator()
