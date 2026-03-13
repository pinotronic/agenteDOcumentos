"""
Smart Orchestrator - Arquitectura optimizada de 3 fases.

En lugar de enviar todas las herramientas en cada llamada:
1. PLANNER: Analiza y planea (solo nombres de herramientas)
2. EXECUTOR: Ejecuta con herramientas específicas
3. SYNTHESIZER: Sintetiza resultados

Ahorro estimado: 90%+ en tokens.
"""
import env_loader
import json
from typing import Dict, List, Any, Optional
from openai import OpenAI
from tools import TOOLS, TOOL_FUNCTIONS
from config import ORCHESTRATOR_MODEL, REASONING_MODEL, REASONING_TASKS
from conversation_memory import ConversationMemory
from toon_formatter import format_tool_result, estimate_token_savings
import hashlib


class SmartOrchestrator:
    """
    Orquestador inteligente que minimiza tokens mediante planificación.
    
    Filosofía:
    - Separar "pensar" de "ejecutar"
    - Enviar solo herramientas necesarias
    - Mantener contexto resumido, no completo
    - Cachear resultados para evitar re-ejecución
    """
    
    def __init__(self, user_id="default", enable_cache=True):
        """
        Args:
            user_id: ID del usuario para memoria
            enable_cache: Activar caché de herramientas
        """
        self.client = OpenAI()
        self.tool_registry = TOOL_FUNCTIONS
        self.all_tools = TOOLS
        self.user_id = user_id
        
        # Nombres de herramientas para fase de planeación
        self.tool_names = [t["function"]["name"] for t in TOOLS]
        
        # Memoria
        self.memory = ConversationMemory(user_id=user_id)
        self.session_id = self.memory._get_or_create_session()
        
        # Contexto resumido (no historial completo)
        self.context_summary = None
        
        # Caché de herramientas
        self.enable_cache = enable_cache
        self.tool_cache = {} if enable_cache else None
        
        # Estadísticas
        self.stats = {
            "total_tokens_saved": 0,
            "cache_hits": 0,
            "total_calls": 0
        }
    
    def chat(self, user_input: str) -> str:
        """
        Punto de entrada principal. Implementa flujo de 3 fases.
        
        Args:
            user_input: Consulta del usuario
            
        Returns:
            Respuesta final sintetizada
        """
        self.stats["total_calls"] += 1
        
        print(f"\n{'='*80}")
        print(f"🧠 SMART ORCHESTRATOR - Procesando consulta")
        print(f"{'='*80}")
        
        # FASE 1: PLANIFICACIÓN
        print(f"\n📋 FASE 1: Planificación (sin herramientas completas)")
        plan = self._create_plan(user_input)
        
        if plan.get("error"):
            return f"Error en planificación: {plan['error']}"
        
        print(f"   ✓ Plan creado con {len(plan.get('steps', []))} pasos")
        print(f"   ✓ Herramientas requeridas: {', '.join(plan.get('required_tools', []))}")
        
        # FASE 2: EJECUCIÓN
        print(f"\n⚙️  FASE 2: Ejecución (solo herramientas necesarias)")
        execution_results = self._execute_plan(plan)
        
        print(f"   ✓ Ejecutados {len(execution_results)} pasos")
        
        # FASE 3: SÍNTESIS
        print(f"\n📝 FASE 3: Síntesis (sin herramientas)")
        final_response = self._synthesize_results(user_input, plan, execution_results)
        
        # Actualizar contexto resumido
        self._update_context_summary(user_input, final_response)
        
        # Guardar en memoria persistente
        self._save_to_memory(user_input, final_response, plan, execution_results)
        
        print(f"\n{'='*80}")
        print(f"✅ Procesamiento completado")
        print(f"💾 Tokens ahorrados (estimado): {self.stats['total_tokens_saved']:,}")
        print(f"⚡ Cache hits: {self.stats['cache_hits']}")
        print(f"{'='*80}\n")
        
        return final_response
    
    def _create_plan(self, user_input: str) -> Dict[str, Any]:
        """
        FASE 1: Crea plan de ejecución sin enviar herramientas completas.
        
        Solo envía:
        - System prompt minimalista
        - Contexto resumido (si existe)
        - NOMBRES de herramientas (no schemas)
        - User query
        
        Returns:
            {
                "steps": [{"action": "tool_name", "reason": "...", "args": {...}}],
                "required_tools": ["tool1", "tool2"],
                "execution_order": "sequential|parallel"
            }
        """
        planner_prompt = f"""Eres un planificador de tareas. Tu trabajo es analizar la consulta del usuario y crear un plan de ejecución eficiente.

HERRAMIENTAS DISPONIBLES: {', '.join(self.tool_names)}

CONSULTA DEL USUARIO: {user_input}

{f'CONTEXTO PREVIO: {self.context_summary}' if self.context_summary else ''}

Crea un plan JSON con:
1. Pasos necesarios (secuenciales o paralelos)
2. Herramientas a usar en cada paso
3. Argumentos estimados para cada herramienta

RESPONDE SOLO CON JSON:
{{
    "steps": [
        {{
            "action": "nombre_herramienta",
            "reason": "por qué es necesaria",
            "args": {{"arg1": "valor"}},
            "dependencies": []  // indices de pasos previos necesarios
        }}
    ],
    "required_tools": ["tool1", "tool2"],
    "execution_strategy": "sequential|parallel_where_possible"
}}"""
        
        try:
            response = self.client.chat.completions.create(
                model=ORCHESTRATOR_MODEL,
                messages=[
                    {"role": "system", "content": "Eres un planificador eficiente. Responde SOLO con JSON válido."},
                    {"role": "user", "content": planner_prompt}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            
            plan = json.loads(response.choices[0].message.content)
            
            # Calcular ahorro de tokens (no enviamos schemas completos)
            all_tools_size = len(json.dumps(self.all_tools))
            tool_names_size = len(', '.join(self.tool_names))
            tokens_saved = (all_tools_size - tool_names_size) // 4
            self.stats["total_tokens_saved"] += tokens_saved
            
            return plan
        
        except Exception as e:
            print(f"❌ Error en planificación: {e}")
            return {"error": str(e)}
    
    def _execute_plan(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        FASE 2: Ejecuta el plan con solo las herramientas necesarias.
        
        Optimizaciones:
        - Solo carga schemas de herramientas requeridas
        - Ejecuta en paralelo cuando es posible
        - Usa caché para evitar re-ejecución
        - Convierte resultados a TOON
        """
        steps = plan.get("steps", [])
        required_tools = plan.get("required_tools", [])
        strategy = plan.get("execution_strategy", "sequential")
        
        # Cargar SOLO herramientas necesarias
        selected_tools = self._get_tools_by_names(required_tools)
        
        # Calcular ahorro
        all_tools_size = len(json.dumps(self.all_tools))
        selected_size = len(json.dumps(selected_tools))
        tokens_saved = (all_tools_size - selected_size) // 4
        self.stats["total_tokens_saved"] += tokens_saved
        
        print(f"   📦 Herramientas cargadas: {len(selected_tools)}/{len(self.all_tools)}")
        print(f"   💰 Ahorro: {tokens_saved:,} tokens")
        
        results = []
        
        if strategy == "parallel_where_possible":
            results = self._execute_parallel_where_possible(steps)
        else:
            results = self._execute_sequential(steps)
        
        return results
    
    def _execute_sequential(self, steps: List[Dict]) -> List[Dict[str, Any]]:
        """Ejecuta pasos secuencialmente."""
        results = []
        
        for i, step in enumerate(steps):
            print(f"   → Paso {i+1}/{len(steps)}: {step['action']}")
            
            result = self._execute_single_step(step)
            results.append({
                "step": i,
                "action": step["action"],
                "result": result
            })
        
        return results
    
    def _execute_parallel_where_possible(self, steps: List[Dict]) -> List[Dict[str, Any]]:
        """
        Ejecuta pasos en paralelo cuando no tienen dependencias.
        Por ahora simplificado (secuencial), pero preparado para paralelización.
        """
        # TODO: Implementar ejecución paralela real con ThreadPoolExecutor
        # Por ahora, ejecutar secuencialmente
        return self._execute_sequential(steps)
    
    def _execute_single_step(self, step: Dict) -> Any:
        """
        Ejecuta un paso individual con caché.
        """
        tool_name = step["action"]
        args = step.get("args", {})
        
        # Verificar caché
        if self.enable_cache:
            cache_key = self._get_cache_key(tool_name, args)
            if cache_key in self.tool_cache:
                print(f"      ⚡ Cache hit: {tool_name}")
                self.stats["cache_hits"] += 1
                return self.tool_cache[cache_key]
        
        # Ejecutar herramienta
        if tool_name in self.tool_registry:
            try:
                result = self.tool_registry[tool_name](**args)
                
                # Guardar en caché
                if self.enable_cache:
                    self.tool_cache[cache_key] = result
                
                return result
            except Exception as e:
                error_msg = f"Error ejecutando {tool_name}: {str(e)}"
                print(f"      ❌ {error_msg}")
                return {"error": error_msg}
        else:
            return {"error": f"Herramienta {tool_name} no encontrada"}
    
    def _synthesize_results(
        self,
        user_input: str,
        plan: Dict,
        results: List[Dict]
    ) -> str:
        """
        FASE 3: Sintetiza resultados sin herramientas.
        
        Solo envía:
        - Consulta original
        - Resultados (en TOON)
        - NO herramientas
        """
        # Convertir resultados a TOON para ahorrar tokens
        toon_results = []
        for r in results:
            if r.get("result"):
                toon_result = format_tool_result(r["result"], tool_name=r["action"])
                toon_results.append({
                    "action": r["action"],
                    "result_toon": toon_result[:2000]  # Limitar tamaño
                })
        
        synthesis_prompt = f"""Sintetiza los siguientes resultados en una respuesta coherente para el usuario.

CONSULTA ORIGINAL: {user_input}

PLAN EJECUTADO:
{json.dumps(plan.get('steps', []), indent=2)}

RESULTADOS:
{json.dumps(toon_results, indent=2, ensure_ascii=False)}

Genera una respuesta clara, concisa y útil."""
        
        try:
            response = self.client.chat.completions.create(
                model=ORCHESTRATOR_MODEL,
                messages=[
                    {"role": "system", "content": "Eres un asistente que sintetiza resultados de manera clara y concisa."},
                    {"role": "user", "content": synthesis_prompt}
                ],
                temperature=0.3
            )
            
            return response.choices[0].message.content
        
        except Exception as e:
            print(f"❌ Error en síntesis: {e}")
            return f"Error al sintetizar resultados: {e}"
    
    def _get_tools_by_names(self, tool_names: List[str]) -> List[Dict]:
        """Retorna solo los schemas de las herramientas especificadas."""
        return [
            tool for tool in self.all_tools
            if tool["function"]["name"] in tool_names
        ]
    
    def _get_cache_key(self, tool_name: str, args: Dict) -> str:
        """Genera key de caché para herramienta + argumentos."""
        args_str = json.dumps(args, sort_keys=True)
        return hashlib.md5(f"{tool_name}:{args_str}".encode()).hexdigest()
    
    def _update_context_summary(self, user_input: str, response: str):
        """
        Actualiza resumen de contexto en lugar de mantener historial completo.
        """
        new_turn = f"User: {user_input[:100]}... → Assistant: {response[:100]}..."
        
        if self.context_summary is None:
            self.context_summary = new_turn
        else:
            # Mantener solo últimos 3 turnos resumidos
            self.context_summary = f"{self.context_summary}\n{new_turn}"
            lines = self.context_summary.split('\n')
            if len(lines) > 3:
                self.context_summary = '\n'.join(lines[-3:])
    
    def _save_to_memory(
        self,
        user_input: str,
        response: str,
        plan: Dict,
        results: List[Dict]
    ):
        """Guarda turno en memoria persistente."""
        tool_calls_list = [
            {"name": r["action"], "content": str(r.get("result", ""))[:500]}
            for r in results
        ]
        
        self.memory.save_conversation_turn(
            user_message=user_input,
            assistant_response=response,
            tool_calls=tool_calls_list if tool_calls_list else None,
            session_id=self.session_id,
            metadata={"plan": plan, "stats": self.stats}
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estadísticas de optimización."""
        return {
            **self.stats,
            "cache_size": len(self.tool_cache) if self.tool_cache else 0,
            "cache_hit_rate": (
                self.stats["cache_hits"] / self.stats["total_calls"]
                if self.stats["total_calls"] > 0 else 0
            )
        }
    
    def clear_cache(self):
        """Limpia el caché de herramientas."""
        if self.tool_cache:
            self.tool_cache.clear()
            print("🗑️ Caché limpiado")
    
    def reset(self):
        """Reinicia el orquestador."""
        self.context_summary = None
        self.clear_cache()
        self.stats = {
            "total_tokens_saved": 0,
            "cache_hits": 0,
            "total_calls": 0
        }
        print("🔄 Orquestador reiniciado")
