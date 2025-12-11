"""
Sistema de commits incrementales para ModoGorila.
Pasos acotados ≤200 líneas, commits automáticos después de cada objetivo cumplido.
"""
import os
import subprocess
import json
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime


class IncrementalCommitter:
    """
    Gestiona commits incrementales siguiendo ModoGorila.
    - Pasos pequeños (≤200 líneas)
    - Commits automáticos con DoD
    - Preparación de PRs estructurados
    """
    
    def __init__(self, workspace_path: str = "."):
        self.workspace_path = Path(workspace_path).resolve()
        self.commit_history = []
    
    def check_git_status(self) -> Dict[str, Any]:
        """
        Verifica el estado del repositorio Git.
        
        Returns:
            Estado de Git con archivos modificados, staged, etc.
        """
        try:
            # Verificar si es un repo git
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                cwd=str(self.workspace_path),
                timeout=10
            )
            
            if result.returncode != 0:
                return {
                    "is_git_repo": False,
                    "error": "No es un repositorio Git"
                }
            
            # Parsear output
            status_lines = result.stdout.strip().split('\n') if result.stdout.strip() else []
            
            modified_files = []
            staged_files = []
            untracked_files = []
            
            for line in status_lines:
                if line:
                    status_code = line[:2]
                    file_path = line[3:]
                    
                    if status_code[0] in ['M', 'A', 'D']:
                        staged_files.append(file_path)
                    elif status_code[1] in ['M', 'D']:
                        modified_files.append(file_path)
                    elif status_code == '??':
                        untracked_files.append(file_path)
            
            return {
                "is_git_repo": True,
                "has_changes": len(modified_files) + len(staged_files) + len(untracked_files) > 0,
                "modified_files": modified_files,
                "staged_files": staged_files,
                "untracked_files": untracked_files,
                "total_changes": len(modified_files) + len(staged_files) + len(untracked_files)
            }
        
        except Exception as e:
            return {
                "is_git_repo": False,
                "error": str(e)
            }
    
    def analyze_change_size(self, file_paths: List[str] = None) -> Dict[str, Any]:
        """
        Analiza el tamaño de los cambios en archivos.
        Verifica si cumple con límite ≤200 líneas.
        
        Args:
            file_paths: Lista de archivos a analizar (None = todos los modificados)
            
        Returns:
            Análisis de tamaño de cambios
        """
        try:
            # Si no se especifican archivos, usar todos los modificados
            if not file_paths:
                status = self.check_git_status()
                file_paths = status.get("modified_files", []) + status.get("staged_files", [])
            
            total_additions = 0
            total_deletions = 0
            files_analyzed = []
            
            for file_path in file_paths:
                # Obtener diff del archivo
                result = subprocess.run(
                    ["git", "diff", "--", file_path],
                    capture_output=True,
                    text=True,
                    cwd=str(self.workspace_path),
                    timeout=10
                )
                
                # Contar líneas agregadas/eliminadas
                additions = result.stdout.count('\n+') - result.stdout.count('\n+++')
                deletions = result.stdout.count('\n-') - result.stdout.count('\n---')
                
                files_analyzed.append({
                    "file": file_path,
                    "additions": additions,
                    "deletions": deletions,
                    "changes": additions + deletions
                })
                
                total_additions += additions
                total_deletions += deletions
            
            total_changes = total_additions + total_deletions
            within_limit = total_changes <= 200
            
            return {
                "total_additions": total_additions,
                "total_deletions": total_deletions,
                "total_changes": total_changes,
                "within_limit": within_limit,
                "limit": 200,
                "files": files_analyzed,
                "recommendation": "✅ OK para commit" if within_limit else "⚠️ Considerar dividir en múltiples commits"
            }
        
        except Exception as e:
            return {
                "error": str(e),
                "total_changes": 0,
                "within_limit": False
            }
    
    def create_commit(
        self,
        message: str,
        files_to_add: List[str] = None,
        include_dod: bool = True,
        dod_data: Dict = None,
        evidence_data: Dict = None
    ) -> Dict[str, Any]:
        """
        Crea un commit con mensaje estructurado según ModoGorila.
        
        Args:
            message: Mensaje base del commit
            files_to_add: Archivos a agregar (None = todos)
            include_dod: Si debe incluir DoD en el mensaje
            dod_data: Datos de DoD para incluir
            evidence_data: Datos de evidencia para incluir
            
        Returns:
            Resultado del commit
        """
        try:
            # Verificar estado
            status = self.check_git_status()
            if not status["is_git_repo"]:
                return {
                    "success": False,
                    "error": "No es un repositorio Git"
                }
            
            if not status["has_changes"]:
                return {
                    "success": False,
                    "error": "No hay cambios para commitear"
                }
            
            # Analizar tamaño de cambios
            change_analysis = self.analyze_change_size(files_to_add)
            
            # Git add
            if files_to_add:
                for file_path in files_to_add:
                    subprocess.run(
                        ["git", "add", file_path],
                        cwd=str(self.workspace_path),
                        check=True,
                        timeout=10
                    )
            else:
                subprocess.run(
                    ["git", "add", "-A"],
                    cwd=str(self.workspace_path),
                    check=True,
                    timeout=10
                )
            
            # Construir mensaje completo
            full_message = self._build_commit_message(
                message,
                include_dod,
                dod_data,
                evidence_data,
                change_analysis
            )
            
            # Git commit
            result = subprocess.run(
                ["git", "commit", "-m", full_message],
                capture_output=True,
                text=True,
                cwd=str(self.workspace_path),
                timeout=30
            )
            
            if result.returncode == 0:
                commit_info = {
                    "success": True,
                    "message": message,
                    "changes": change_analysis,
                    "commit_hash": self._get_last_commit_hash(),
                    "timestamp": datetime.now().isoformat()
                }
                self.commit_history.append(commit_info)
                return commit_info
            else:
                return {
                    "success": False,
                    "error": result.stderr
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _build_commit_message(
        self,
        base_message: str,
        include_dod: bool,
        dod_data: Dict,
        evidence_data: Dict,
        change_analysis: Dict
    ) -> str:
        """Construye mensaje de commit estructurado."""
        lines = [base_message, ""]
        
        # DoD
        if include_dod and dod_data:
            lines.append("✅ DoD Cumplido:")
            checklist = dod_data.get("checklist_status", {})
            for item, status in list(checklist.items())[:5]:
                checkbox = "[x]" if "Done" in status else "[ ]"
                lines.append(f"- {checkbox} {item}")
            lines.append("")
        
        # Estadísticas
        lines.append("📊 Cambios:")
        lines.append(f"- Archivos: {len(change_analysis.get('files', []))}")
        lines.append(f"- Líneas: +{change_analysis.get('total_additions', 0)} -{change_analysis.get('total_deletions', 0)}")
        lines.append(f"- Total: {change_analysis.get('total_changes', 0)} líneas")
        
        # Evidencia
        if evidence_data:
            lines.append("")
            lines.append("✅ Validación:")
            if evidence_data.get("gates_passed") is not None:
                status = "✅" if evidence_data["gates_passed"] else "❌"
                lines.append(f"- Quality Gates: {status}")
            if evidence_data.get("dod_score") is not None:
                lines.append(f"- DoD Score: {evidence_data['dod_score']:.1f}%")
        
        return '\n'.join(lines)
    
    def _get_last_commit_hash(self) -> str:
        """Obtiene el hash del último commit."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                cwd=str(self.workspace_path),
                timeout=5
            )
            return result.stdout.strip()
        except:
            return "unknown"
    
    def prepare_pr_description(
        self,
        pr_title: str,
        commits: List[str] = None,
        dod_summary: Dict = None
    ) -> str:
        """
        Prepara descripción estructurada para Pull Request.
        
        Args:
            pr_title: Título del PR
            commits: Lista de hashes de commits a incluir
            dod_summary: Resumen de DoD cumplido
            
        Returns:
            Descripción en formato Markdown
        """
        lines = [f"# {pr_title}\n"]
        
        # Resumen
        lines.append("## Resumen\n")
        lines.append("Este PR implementa mejoras siguiendo ModoGorila:\n")
        
        # Commits incluidos
        if commits:
            lines.append("## Commits Incluidos\n")
            for commit_hash in commits:
                lines.append(f"- {commit_hash}")
            lines.append("")
        elif self.commit_history:
            lines.append("## Commits Recientes\n")
            for commit_info in self.commit_history[-5:]:
                lines.append(f"- {commit_info.get('commit_hash', 'N/A')}: {commit_info.get('message', 'N/A')}")
            lines.append("")
        
        # DoD
        if dod_summary:
            lines.append("## Definition of Done\n")
            lines.append(f"**Score:** {dod_summary.get('score', 0):.1f}%\n")
            
            if dod_summary.get("checklist_status"):
                lines.append("### Checklist")
                for item, status in dod_summary["checklist_status"].items():
                    checkbox = "[x]" if "Done" in status else "[ ]"
                    lines.append(f"- {checkbox} {item}")
            
            lines.append("")
        
        # Cambios
        lines.append("## Cambios\n")
        if self.commit_history:
            total_changes = sum(c.get("changes", {}).get("total_changes", 0) for c in self.commit_history)
            lines.append(f"- **Total líneas cambiadas:** {total_changes}")
            lines.append(f"- **Commits:** {len(self.commit_history)}")
        
        lines.append("\n## Validación\n")
        lines.append("- [ ] Quality gates pasados")
        lines.append("- [ ] DoD cumplido")
        lines.append("- [ ] Tests ejecutados")
        lines.append("- [ ] Revisión de código completada")
        
        return '\n'.join(lines)


# Instancia global
_incremental_committer = IncrementalCommitter()
