"""
Supervisor LLM - Valida que los planes se ejecuten correctamente.
Rol: QA/Reviewer que verifica cumplimiento y toma decisiones de reintento.
"""
import os
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from openai import OpenAI
import config


class PlanSupervisor:
    """
    LLM Supervisor que valida ejecución de planes y toma decisiones.
    Verifica DoD, analiza fallos, decide reintentos o escalamiento.
    """
    
    def __init__(self, client: OpenAI):
        self.client = client
        self.model = config.ANALYZER_MODEL
        self.max_plan_retries = 2
    
    def validate_execution(
        self,
        original_plan: Dict[str, Any],
        execution_result: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Valida si la ejecución cumplió con el plan y DoD.
        
        Args:
            original_plan: Plan generado por Architect
            execution_result: Resultado de PlanExecutor
            context: Contexto adicional
        
        Returns:
            {
                "validation_passed": bool,
                "dod_compliance": Dict,
                "issues_found": List[str],
                "recommendation": str,  # "approve", "retry", "escalate"
                "retry_plan": Dict (si recommendation == "retry"),
                "reasoning": str
            }
        """
        print(f"\n{'='*70}")
        print("🔍 SUPERVISOR: Validando ejecución del plan")
        print(f"{'='*70}")
        
        # Preparar prompt para el supervisor
        prompt = self._build_validation_prompt(
            original_plan,
            execution_result,
            context
        )
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_supervisor_system_prompt()
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Mostrar resultado
            validation_passed = result.get("validation_passed", False)
            recommendation = result.get("recommendation", "escalate")
            
            print(f"\n{'✅' if validation_passed else '❌'} Validación: {'APROBADA' if validation_passed else 'FALLIDA'}")
            print(f"📋 Recomendación: {recommendation.upper()}")
            
            if result.get("issues_found"):
                print(f"\n⚠️  Problemas detectados:")
                for issue in result["issues_found"]:
                    print(f"   • {issue}")
            
            return result
        
        except Exception as e:
            return {
                "validation_passed": False,
                "error": str(e),
                "recommendation": "escalate",
                "reasoning": f"Error al validar: {str(e)}"
            }
    
    def _get_supervisor_system_prompt(self) -> str:
        """Sistema prompt para el LLM Supervisor."""
        return """Eres un Supervisor de Calidad experto en validación de planes de ejecución.

Tu trabajo es:
1. Comparar el PLAN ORIGINAL con el RESULTADO DE EJECUCIÓN
2. Verificar cumplimiento del Definition of Done (DoD)
3. Identificar discrepancias, pasos fallidos o incompletos
4. Tomar decisiones:
   - "approve": Todo correcto, plan ejecutado exitosamente
   - "retry": Fallos recuperables, generar plan de reintento
   - "escalate": Fallos críticos, informar al usuario

CRITERIOS DE VALIDACIÓN:
✅ APPROVE si:
- Todos los pasos críticos se ejecutaron exitosamente
- El DoD se cumple al 100% o >90% para pasos no críticos
- Los outputs esperados están presentes

🔄 RETRY si:
- Algunos pasos fallaron pero son recuperables
- No se alcanzó el DoD pero puede lograrse con correcciones
- Fallos son técnicos/transitorios (timeouts, permisos temporales)

⚠️ ESCALATE si:
- Pasos críticos fallaron sin forma de recuperar
- Recursos necesarios no existen (archivos, APIs inaccesibles)
- El objetivo original es imposible de cumplir

FORMATO DE RESPUESTA (JSON):
{
    "validation_passed": bool,
    "dod_compliance": {
        "score": float,  // 0-100
        "criteria_met": int,
        "criteria_total": int
    },
    "issues_found": ["lista", "de", "problemas"],
    "recommendation": "approve|retry|escalate",
    "retry_plan": {  // Solo si recommendation == "retry"
        "objective": "Qué corregir",
        "execution_steps": [
            {
                "action": "Acción específica",
                "tool": "nombre_herramienta",
                "parameters": {},
                "critical": bool
            }
        ]
    },
    "reasoning": "Explicación detallada de la decisión"
}

Sé crítico pero práctico. No aprobar parcialmente."""
    
    def _build_validation_prompt(
        self,
        plan: Dict[str, Any],
        execution_result: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Construye el prompt de validación."""
        
        prompt_parts = [
            "# PLAN ORIGINAL",
            json.dumps(plan, indent=2, ensure_ascii=False),
            "",
            "# RESULTADO DE EJECUCIÓN",
            json.dumps(execution_result, indent=2, ensure_ascii=False),
            ""
        ]
        
        if context:
            prompt_parts.extend([
                "# CONTEXTO ADICIONAL",
                json.dumps(context, indent=2, ensure_ascii=False),
                ""
            ])
        
        prompt_parts.append("""
# TAREA
Valida si el plan se ejecutó correctamente:
1. Compara steps ejecutados vs planeados
2. Verifica DoD (Definition of Done)
3. Identifica problemas
4. Recomienda: approve, retry o escalate
5. Si recomiendas retry, genera plan de corrección

Responde en JSON según el formato especificado.""")
        
        return "\n".join(prompt_parts)
    
    def supervise_plan_execution(
        self,
        plan: Dict[str, Any],
        executor,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Ciclo completo: ejecutar → validar → reintentar si es necesario.
        
        Args:
            plan: Plan del Architect
            executor: Instancia de PlanExecutor
            context: Contexto
        
        Returns:
            {
                "final_success": bool,
                "attempts": int,
                "execution_history": List[Dict],
                "validation_result": Dict,
                "user_message": str
            }
        """
        print(f"\n{'='*70}")
        print("👁️  SUPERVISOR: Iniciando supervisión de plan")
        print(f"{'='*70}")
        
        execution_history = []
        
        for attempt in range(self.max_plan_retries + 1):
            print(f"\n🔄 INTENTO {attempt + 1}/{self.max_plan_retries + 1}")
            
            # Ejecutar plan
            exec_result = executor.execute_plan(plan, context)
            execution_history.append(exec_result)
            
            # Validar ejecución
            validation = self.validate_execution(plan, exec_result, context)
            
            recommendation = validation.get("recommendation", "escalate")
            
            if recommendation == "approve":
                return {
                    "final_success": True,
                    "attempts": attempt + 1,
                    "execution_history": execution_history,
                    "validation_result": validation,
                    "user_message": "✅ Plan ejecutado y validado exitosamente"
                }
            
            elif recommendation == "retry" and attempt < self.max_plan_retries:
                print(f"\n🔄 SUPERVISOR: Reintentando con plan corregido...")
                
                # Usar el retry_plan del supervisor
                if validation.get("retry_plan"):
                    plan = validation["retry_plan"]
                else:
                    # Si no hay retry_plan, usar el original
                    print("   ⚠️  No se generó plan de reintento, usando original")
            
            else:
                # Escalate o reintentos agotados
                return {
                    "final_success": False,
                    "attempts": attempt + 1,
                    "execution_history": execution_history,
                    "validation_result": validation,
                    "user_message": self._generate_failure_message(validation, exec_result)
                }
        
        # No debería llegar aquí
        return {
            "final_success": False,
            "attempts": self.max_plan_retries + 1,
            "execution_history": execution_history,
            "user_message": "❌ Reintentos agotados sin éxito"
        }
    
    def _generate_failure_message(
        self,
        validation: Dict[str, Any],
        execution: Dict[str, Any]
    ) -> str:
        """Genera mensaje informativo para el usuario sobre el fallo."""
        
        lines = [
            "❌ No se pudo completar el plan solicitado.",
            "",
            "📋 PROBLEMAS DETECTADOS:"
        ]
        
        issues = validation.get("issues_found", [])
        if issues:
            for issue in issues:
                lines.append(f"   • {issue}")
        else:
            lines.append("   • No se especificaron problemas concretos")
        
        lines.extend([
            "",
            "📊 ESTADÍSTICAS:",
            f"   • Pasos completados: {execution.get('steps_completed', 0)}/{execution.get('steps_total', 0)}",
            f"   • Tasa de éxito: {execution.get('completion_rate', 0):.1f}%"
        ])
        
        reasoning = validation.get("reasoning", "")
        if reasoning:
            lines.extend([
                "",
                "💡 ANÁLISIS DEL SUPERVISOR:",
                f"   {reasoning}"
            ])
        
        return "\n".join(lines)
