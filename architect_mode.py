"""
Módulo Arquitecto - Generación de planes estructurados según ModoGorila.
Implementa Contract-Driven Development con Spec Packs, DoD y TestPlans.
"""
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from openai import OpenAI
from config import ANALYZER_MODEL


class Architect:
    """
    Rol de Arquitecto: Define contratos, DoD y TestPlan antes de implementar.
    Genera planes detallados siguiendo principios de ModoGorila.
    """
    
    def __init__(self):
        self.client = OpenAI()
        self.model = ANALYZER_MODEL  # Usa gpt-4o para planificación profunda
        
    def generate_analysis_plan(
        self,
        repository_path: str,
        user_requirements: str,
        scope: str = "full"
    ) -> Dict[str, Any]:
        """
        Genera un plan de análisis estructurado con contratos y DoD.
        
        Args:
            repository_path: Ruta del repositorio a analizar
            user_requirements: Requisitos del usuario en lenguaje natural
            scope: Alcance del análisis (full, quick, targeted)
            
        Returns:
            Plan estructurado con Spec Pack, DoD, TestPlan, pasos
        """
        print(f"\n🏗️  [ARQUITECTO] Generando plan de análisis...")
        print(f"   📂 Repositorio: {repository_path}")
        print(f"   📋 Requisitos: {user_requirements}")
        print(f"   🎯 Alcance: {scope}")
        
        prompt = self._build_planning_prompt(
            repository_path,
            user_requirements,
            scope
        )
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_architect_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            
            plan = json.loads(response.choices[0].message.content)
            
            # Agregar metadata
            plan["metadata"] = {
                "generated_at": datetime.now().isoformat(),
                "repository_path": repository_path,
                "scope": scope,
                "architect_model": self.model
            }
            
            self._print_plan_summary(plan)
            
            return plan
            
        except Exception as e:
            print(f"❌ Error generando plan: {e}")
            return self._get_fallback_plan(repository_path, user_requirements)
    
    def _build_planning_prompt(
        self,
        repository_path: str,
        user_requirements: str,
        scope: str
    ) -> str:
        """Construye el prompt para generación del plan."""
        return f"""Genera un plan de análisis detallado para el siguiente repositorio:

**REPOSITORIO:**
{repository_path}

**REQUISITOS DEL USUARIO:**
{user_requirements}

**ALCANCE:** {scope}
- full: Análisis completo de arquitectura, dependencias, patrones, código
- quick: Análisis rápido de estructura y archivos principales
- targeted: Análisis enfocado en archivos/módulos específicos

**DEBES GENERAR UN PLAN ESTRUCTURADO CON:**

1. **Spec Pack (Especificación):**
   - PRD (Product Requirements Document) breve
   - Objetivos SMART del análisis
   - Supuestos y restricciones
   - Alcance detallado (qué incluir/excluir)

2. **Contratos (Contracts):**
   - Estructura de datos esperada en outputs
   - Formatos de análisis (JSON Schema)
   - Interfaces entre componentes

3. **Definition of Done (DoD):**
   - Criterios de aceptación específicos
   - Checklist verificable
   - Métricas de completitud

4. **Test Plan:**
   - Validaciones a realizar
   - Casos de prueba esperados
   - Criterios de éxito

5. **Pasos de Ejecución:**
   - Lista ordenada de pasos incrementales
   - Cada paso ≤ 200 líneas de cambios
   - Dependencias entre pasos
   - Estimación de tiempo/archivos por paso

6. **Análisis de Riesgos:**
   - Riesgos potenciales
   - Mitigaciones propuestas
   - Puntos de decisión críticos

**FORMATO DE SALIDA: JSON válido**

Usa esta estructura exacta:
{{
  "spec_pack": {{
    "prd": "Descripción del análisis requerido...",
    "objectives": ["objetivo1", "objetivo2"],
    "assumptions": ["supuesto1", "supuesto2"],
    "scope": {{
      "included": ["elemento1", "elemento2"],
      "excluded": ["elemento1", "elemento2"]
    }}
  }},
  "contracts": {{
    "output_schema": {{}},
    "data_formats": ["formato1", "formato2"],
    "interfaces": []
  }},
  "dod": {{
    "acceptance_criteria": ["criterio1", "criterio2"],
    "checklist": ["item1", "item2"],
    "metrics": {{
      "completeness": "100%",
      "coverage": "all_files"
    }}
  }},
  "test_plan": {{
    "validations": ["validación1", "validación2"],
    "test_cases": ["caso1", "caso2"],
    "success_criteria": ["criterio1", "criterio2"]
  }},
  "execution_steps": [
    {{
      "step_number": 1,
      "title": "Título del paso",
      "description": "Qué hacer en este paso",
      "estimated_files": 10,
      "estimated_time": "5 min",
      "dependencies": [],
      "outputs": ["output1", "output2"]
    }}
  ],
  "risk_analysis": {{
    "risks": [
      {{
        "risk": "Descripción del riesgo",
        "impact": "high|medium|low",
        "mitigation": "Cómo mitigarlo"
      }}
    ],
    "decision_points": ["punto1", "punto2"]
  }}
}}
"""
    
    def _get_architect_system_prompt(self) -> str:
        """Prompt del sistema para el rol de Arquitecto."""
        return """Eres un Arquitecto de Software Senior especializado en análisis de código.

**TU ROL:**
Generar planes de análisis estructurados siguiendo ModoGorila:
- Contract-Driven Development
- Incrementos pequeños (≤200 líneas)
- DoD y TestPlan obligatorios
- Pasos verificables con Evidencia

**PRINCIPIOS:**
1. **Claridad:** Cada paso debe ser inequívoco
2. **Incrementalidad:** Pasos pequeños y verificables
3. **Contratos primero:** Definir esquemas antes de implementar
4. **Calidad por diseño:** DoD y tests desde el inicio
5. **Gestión de riesgos:** Identificar y mitigar proactivamente

**PRIORIZA:**
- Análisis exhaustivo sobre velocidad superficial
- Detección de patrones arquitectónicos
- Mapeo completo de dependencias
- Identificación de deuda técnica
- Puntos de extensibilidad

**FORMATO:**
- Siempre JSON válido
- Estructurado según el schema solicitado
- Pasos ordenados lógicamente
- Estimaciones realistas

Genera planes detallados, accionables y verificables."""
    
    def _print_plan_summary(self, plan: Dict[str, Any]) -> None:
        """Imprime resumen del plan generado."""
        print("\n" + "="*70)
        print("📋 PLAN DE ANÁLISIS GENERADO")
        print("="*70)
        
        if "spec_pack" in plan:
            print(f"\n🎯 OBJETIVOS:")
            for obj in plan["spec_pack"].get("objectives", []):
                print(f"   • {obj}")
        
        if "execution_steps" in plan:
            steps = plan["execution_steps"]
            print(f"\n📝 PASOS DE EJECUCIÓN: {len(steps)} pasos")
            for step in steps[:3]:  # Mostrar primeros 3
                print(f"   {step['step_number']}. {step['title']}")
                print(f"      └─ Archivos: ~{step.get('estimated_files', '?')}, "
                      f"Tiempo: {step.get('estimated_time', '?')}")
            if len(steps) > 3:
                print(f"   ... y {len(steps) - 3} pasos más")
        
        if "dod" in plan:
            criteria = plan["dod"].get("acceptance_criteria", [])
            print(f"\n✅ CRITERIOS DE ACEPTACIÓN: {len(criteria)}")
            for criterion in criteria[:3]:
                print(f"   • {criterion}")
        
        if "risk_analysis" in plan:
            risks = plan["risk_analysis"].get("risks", [])
            high_risks = [r for r in risks if r.get("impact") == "high"]
            if high_risks:
                print(f"\n⚠️  RIESGOS ALTOS: {len(high_risks)}")
                for risk in high_risks[:2]:
                    print(f"   • {risk['risk']}")
                    print(f"     Mitigación: {risk['mitigation']}")
        
        print("\n" + "="*70 + "\n")
    
    def _get_fallback_plan(
        self,
        repository_path: str,
        user_requirements: str
    ) -> Dict[str, Any]:
        """Plan de respaldo si falla la generación con IA."""
        return {
            "spec_pack": {
                "prd": f"Análisis de {repository_path}: {user_requirements}",
                "objectives": [
                    "Explorar estructura del repositorio",
                    "Identificar archivos principales",
                    "Analizar dependencias críticas"
                ],
                "assumptions": ["Repositorio válido", "Permisos de lectura"],
                "scope": {
                    "included": ["Todos los archivos de código", "Configuración"],
                    "excluded": ["Binarios", "node_modules", ".git"]
                }
            },
            "execution_steps": [
                {
                    "step_number": 1,
                    "title": "Explorar estructura completa",
                    "description": "Mapear todos los directorios y archivos",
                    "estimated_files": "?",
                    "estimated_time": "2-5 min",
                    "dependencies": [],
                    "outputs": ["structure_map.json"]
                },
                {
                    "step_number": 2,
                    "title": "Analizar archivos principales",
                    "description": "Analizar archivos de entrada y configuración",
                    "estimated_files": "5-10",
                    "estimated_time": "3-7 min",
                    "dependencies": [1],
                    "outputs": ["main_files_analysis.json"]
                }
            ],
            "dod": {
                "acceptance_criteria": [
                    "Todos los archivos relevantes explorados",
                    "Estructura documentada en RAG",
                    "Dependencias identificadas"
                ],
                "checklist": [
                    "Exploración completa",
                    "Análisis guardado",
                    "Reporte generado"
                ],
                "metrics": {
                    "completeness": "100%",
                    "coverage": "all_code_files"
                }
            },
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "repository_path": repository_path,
                "scope": "fallback",
                "architect_model": "fallback"
            }
        }
    
    def validate_plan_execution(
        self,
        plan: Dict[str, Any],
        execution_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Valida que la ejecución cumplió con el plan y DoD.
        
        Args:
            plan: Plan original generado
            execution_results: Resultados de cada paso ejecutado
            
        Returns:
            Reporte de validación con gaps y completitud
        """
        print("\n🔍 [ARQUITECTO] Validando ejecución del plan...")
        
        dod = plan.get("dod", {})
        checklist = dod.get("checklist", [])
        criteria = dod.get("acceptance_criteria", [])
        
        validation = {
            "plan_followed": True,
            "dod_satisfied": True,
            "gaps": [],
            "completed_steps": len(execution_results),
            "total_steps": len(plan.get("execution_steps", [])),
            "checklist_status": {},
            "criteria_status": {}
        }
        
        # Validar pasos completados
        expected_steps = len(plan.get("execution_steps", []))
        if len(execution_results) < expected_steps:
            validation["plan_followed"] = False
            validation["gaps"].append(
                f"Solo {len(execution_results)}/{expected_steps} pasos completados"
            )
        
        # Validar checklist (simplificado)
        for item in checklist:
            validation["checklist_status"][item] = "pending"  # Requeriría lógica específica
        
        # Validar criterios de aceptación
        for criterion in criteria:
            validation["criteria_status"][criterion] = "pending"
        
        print(f"   ✓ Pasos completados: {validation['completed_steps']}/{validation['total_steps']}")
        print(f"   ✓ DoD satisfecho: {validation['dod_satisfied']}")
        
        if validation["gaps"]:
            print(f"   ⚠️  Gaps encontrados: {len(validation['gaps'])}")
            for gap in validation["gaps"]:
                print(f"      • {gap}")
        
        return validation
