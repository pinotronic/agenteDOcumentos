"""
Plan Executor - Ejecuta planes del Architect paso a paso.
Rol: Implementador que ejecuta secuencialmente cada objetivo del plan.
"""
import os
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path


class PlanExecutor:
    """
    Ejecuta planes generados por Architect, validando cada paso.
    Registra evidencia y maneja errores con reintentos inteligentes.
    """
    
    def __init__(self, tools_registry: Dict[str, callable]):
        """
        Args:
            tools_registry: Diccionario {nombre_herramienta: función}
        """
        self.tools = tools_registry
        self.execution_log = []
        self.current_step = 0
        self.max_retries = 2
    
    def execute_plan(self, plan: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Ejecuta un plan completo del Architect.
        
        Args:
            plan: Plan generado por Architect con steps y DoD
            context: Contexto adicional (rutas, parámetros)
        
        Returns:
            {
                "success": bool,
                "steps_completed": int,
                "steps_total": int,
                "execution_log": List[Dict],
                "final_dod_status": Dict,
                "evidence": Dict
            }
        """
        print(f"\n{'='*70}")
        print(f"🚀 EJECUTANDO PLAN: {plan.get('objective', 'Sin objetivo')}")
        print(f"{'='*70}")
        
        if not plan.get("execution_steps"):
            return {
                "success": False,
                "error": "Plan sin pasos de ejecución",
                "steps_completed": 0,
                "steps_total": 0
            }
        
        context = context or {}
        steps = plan["execution_steps"]
        self.execution_log = []
        self.current_step = 0
        
        for idx, step in enumerate(steps, 1):
            print(f"\n📍 PASO {idx}/{len(steps)}: {step.get('action', 'Sin acción')}")
            print(f"   Objetivo: {step.get('objective', 'N/A')}")
            
            step_result = self._execute_step(step, context, idx)
            self.execution_log.append(step_result)
            
            if not step_result["success"]:
                print(f"   ❌ Paso {idx} falló: {step_result.get('error')}")
                
                # Verificar si es crítico
                if step.get("critical", False):
                    return self._build_failure_report(idx, len(steps))
                else:
                    print(f"   ⚠️  Paso no crítico, continuando...")
            else:
                print(f"   ✅ Paso {idx} completado")
                self.current_step = idx
        
        # Generar reporte final
        return self._build_success_report(len(steps))
    
    def _execute_step(self, step: Dict[str, Any], context: Dict[str, Any], step_num: int) -> Dict[str, Any]:
        """
        Ejecuta un paso individual del plan.
        """
        tool_name = step.get("tool")
        if not tool_name:
            return {
                "success": False,
                "step_num": step_num,
                "error": "Paso sin herramienta especificada"
            }
        
        if tool_name not in self.tools:
            return {
                "success": False,
                "step_num": step_num,
                "error": f"Herramienta '{tool_name}' no encontrada"
            }
        
        # Preparar parámetros
        params = step.get("parameters", {})
        
        # Sustituir variables de contexto
        params = self._resolve_context_vars(params, context)
        
        # Ejecutar con reintentos
        for attempt in range(self.max_retries):
            try:
                print(f"      🔧 Ejecutando: {tool_name}()")
                tool_func = self.tools[tool_name]
                result = tool_func(**params)
                
                # Verificar éxito
                if isinstance(result, dict):
                    if result.get("success", True):
                        return {
                            "success": True,
                            "step_num": step_num,
                            "tool": tool_name,
                            "result": result,
                            "attempt": attempt + 1
                        }
                    else:
                        # Falló pero devolvió resultado
                        if attempt < self.max_retries - 1:
                            print(f"      🔄 Reintento {attempt + 2}/{self.max_retries}...")
                            continue
                        return {
                            "success": False,
                            "step_num": step_num,
                            "tool": tool_name,
                            "error": result.get("error", "Error desconocido"),
                            "attempts": attempt + 1
                        }
                else:
                    # Resultado no es dict, asumir éxito
                    return {
                        "success": True,
                        "step_num": step_num,
                        "tool": tool_name,
                        "result": result,
                        "attempt": attempt + 1
                    }
            
            except Exception as e:
                if attempt < self.max_retries - 1:
                    print(f"      🔄 Error, reintento {attempt + 2}/{self.max_retries}...")
                    continue
                
                return {
                    "success": False,
                    "step_num": step_num,
                    "tool": tool_name,
                    "error": str(e),
                    "attempts": attempt + 1
                }
        
        # No debería llegar aquí
        return {
            "success": False,
            "step_num": step_num,
            "error": "Reintentos agotados"
        }
    
    def _resolve_context_vars(self, params: Dict, context: Dict) -> Dict:
        """
        Sustituye variables ${var} en parámetros con valores del contexto.
        """
        resolved = {}
        for key, value in params.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                var_name = value[2:-1]
                resolved[key] = context.get(var_name, value)
            else:
                resolved[key] = value
        return resolved
    
    def _build_success_report(self, total_steps: int) -> Dict[str, Any]:
        """Genera reporte de ejecución exitosa."""
        successful = sum(1 for s in self.execution_log if s["success"])
        
        return {
            "success": True,
            "steps_completed": successful,
            "steps_total": total_steps,
            "execution_log": self.execution_log,
            "completion_rate": round((successful / total_steps) * 100, 2),
            "timestamp": datetime.now().isoformat()
        }
    
    def _build_failure_report(self, failed_step: int, total_steps: int) -> Dict[str, Any]:
        """Genera reporte de ejecución fallida."""
        return {
            "success": False,
            "steps_completed": self.current_step,
            "steps_total": total_steps,
            "failed_at_step": failed_step,
            "execution_log": self.execution_log,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_execution_summary(self) -> str:
        """
        Genera resumen legible de la ejecución.
        """
        if not self.execution_log:
            return "No hay ejecuciones registradas"
        
        lines = ["\n📊 RESUMEN DE EJECUCIÓN", "="*70]
        
        for log in self.execution_log:
            step_num = log.get("step_num", "?")
            tool = log.get("tool", "N/A")
            success = "✅" if log["success"] else "❌"
            
            lines.append(f"Paso {step_num}: {success} {tool}")
            
            if not log["success"]:
                error = log.get("error", "Sin detalles")
                lines.append(f"         Error: {error}")
        
        return "\n".join(lines)


def list_directory_recursive(
    directory_path: str,
    extensions: Optional[List[str]] = None,
    max_depth: Optional[int] = None,
    include_hidden: bool = False
) -> Dict[str, Any]:
    """
    Lista TODOS los archivos en un directorio recursivamente.
    
    Args:
        directory_path: Ruta del directorio a escanear
        extensions: Lista de extensiones a filtrar (ej: ['.php', '.py'])
        max_depth: Profundidad máxima (None = ilimitado)
        include_hidden: Incluir archivos/carpetas ocultos
    
    Returns:
        {
            "success": bool,
            "directory": str,
            "total_files": int,
            "total_dirs": int,
            "files_by_extension": Dict[str, int],
            "file_tree": List[Dict],  # [{path, name, size, extension}]
            "error": str (si falla)
        }
    """
    print(f"\n📂 [SCAN] Escaneando directorio: {directory_path}")
    if extensions:
        print(f"   Filtros: {', '.join(extensions)}")
    
    if not os.path.exists(directory_path):
        return {
            "success": False,
            "error": f"Directorio no existe: {directory_path}"
        }
    
    if not os.path.isdir(directory_path):
        return {
            "success": False,
            "error": f"La ruta no es un directorio: {directory_path}"
        }
    
    files_found = []
    dirs_found = []
    files_by_ext = {}
    
    try:
        # Escaneo recursivo
        for root, dirs, files in os.walk(directory_path):
            # Filtrar ocultos si es necesario
            if not include_hidden:
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                files = [f for f in files if not f.startswith('.')]
            
            # Verificar profundidad
            if max_depth is not None:
                depth = root[len(directory_path):].count(os.sep)
                if depth > max_depth:
                    continue
            
            dirs_found.append(root)
            
            for filename in files:
                filepath = os.path.join(root, filename)
                ext = os.path.splitext(filename)[1].lower()
                
                # Filtrar por extensión si se especificó
                if extensions and ext not in extensions:
                    continue
                
                try:
                    size = os.path.getsize(filepath)
                except:
                    size = 0
                
                files_found.append({
                    "path": filepath,
                    "name": filename,
                    "size": size,
                    "extension": ext,
                    "directory": root
                })
                
                # Estadística por extensión
                files_by_ext[ext] = files_by_ext.get(ext, 0) + 1
        
        print(f"   ✅ {len(files_found)} archivos encontrados")
        print(f"   📁 {len(dirs_found)} directorios escaneados")
        
        return {
            "success": True,
            "directory": directory_path,
            "total_files": len(files_found),
            "total_dirs": len(dirs_found),
            "files_by_extension": files_by_ext,
            "file_tree": files_found
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Error al escanear: {str(e)}"
        }
