"""
Clase Agent que encapsula la lógica del asistente orquestador con OpenAI.
Este agente coordina el análisis de repositorios usando herramientas especializadas.
"""
import env_loader  # Cargar .env PRIMERO
import json
from openai import OpenAI
from tools import TOOLS, TOOL_FUNCTIONS
from config import ORCHESTRATOR_MODEL, ORCHESTRATOR_SYSTEM_PROMPT, REASONING_MODEL, REASONING_TASKS
from conversation_memory import ConversationMemory
from memory_summarizer import MemorySummarizer
from tool_selector import get_smart_tools
from toon_formatter import format_tool_result, estimate_token_savings


class Agent:
    def __init__(self, name="Orquestador", model=None, system_prompt=None, user_id="pvargas"):
        """
        Inicializa el agente orquestador.
        
        Args:
            name: Nombre del agente
            model: Modelo de OpenAI a usar (default: usa ORCHESTRATOR_MODEL de config)
            system_prompt: Prompt del sistema personalizado
            user_id: ID del usuario para memoria persistente
        """
        self.name = name
        self.model = model or ORCHESTRATOR_MODEL
        self.client = OpenAI()
        self.tools = TOOLS
        self.tool_functions = TOOL_FUNCTIONS
        
        # Inicializar memoria conversacional
        self.memory = ConversationMemory(user_id=user_id)
        self.session_id = self.memory._get_or_create_session()
        self.memory_summarizer = MemorySummarizer()
        
        # NO agregar contexto previo al inicio para ahorrar tokens
        # El usuario puede solicitar contexto explícitamente si lo necesita
        base_prompt = system_prompt or ORCHESTRATOR_SYSTEM_PROMPT
        
        # Inicializar historial de mensajes con prompt compacto
        self.messages = [
            {"role": "system", "content": base_prompt}
        ]
    
    def add_user_message(self, content):
        """Agrega un mensaje del usuario al historial."""
        self.messages.append({"role": "user", "content": content})
    
    def _inject_recent_memory(self, user_query: str = None, max_tokens: int = 1500):
        """
        Inyecta memoria relevante en el contexto antes de cada solicitud.
        Usa búsqueda semántica para encontrar información relevante.

        Args:
            user_query: Query actual del usuario para búsqueda semántica
            max_tokens: Máximo de tokens aproximados a inyectar (~4 chars = 1 token)
        """
        memory_context = []
        chars_used = 0
        max_chars = max_tokens * 4  # Aproximación: 4 chars ~ 1 token
        similar_messages = []

        # 1. Inyectar hechos conocidos (compacto, alta prioridad)
        facts_summary = self.memory.get_facts_summary()

        # 2. Buscar conversaciones similares si hay query
        if user_query:
            try:
                similar_messages = self.memory.search_similar_conversations(
                    query=user_query,
                    limit=3,
                    role_filter="assistant"  # Buscar en respuestas anteriores
                )
            except Exception as e:
                print(f"[MEMORIA] Error buscando contexto similar: {e}")

        summarized_context = self.memory_summarizer.summarize_memory(
            user_query=user_query,
            facts_summary=facts_summary,
            similar_messages=similar_messages,
            max_chars=max_chars,
        )

        if summarized_context:
            memory_context.append(summarized_context)
            chars_used = len(summarized_context)
        else:
            if facts_summary and len(facts_summary) < max_chars * 0.3:
                memory_context.append(facts_summary)
                chars_used += len(facts_summary)

            if similar_messages and chars_used < max_chars * 0.7:
                relevant_context = ["\nCONTEXTO RELACIONADO PREVIO:"]
                for msg in similar_messages:
                    if msg.get("relevance", 0) > 0.5:
                        content = msg.get("content", "")[:300]
                        if chars_used + len(content) < max_chars:
                            relevant_context.append(f"- {content}")
                            chars_used += len(content)

                if len(relevant_context) > 1:
                    memory_context.append("\n".join(relevant_context))

        # 3. Inyectar en el system prompt si hay contenido
        if len(self.messages) > 0 and self.messages[0]["role"] == "system":
            base_prompt = self.messages[0]["content"]
            if "\n\n---MEMORIA---" in base_prompt:
                base_prompt = base_prompt.split("\n\n---MEMORIA---")[0]

            if memory_context:
                combined_context = "\n\n".join(memory_context)
                self.messages[0]["content"] = f"{base_prompt}\n\n---MEMORIA---\n{combined_context}\n---FIN MEMORIA---"
                print(f"[MEMORIA] Contexto inyectado: ~{chars_used // 4} tokens")
            else:
                self.messages[0]["content"] = base_prompt
    
    def get_completion(self, force_reasoning=False, user_query=None):
        """
        Obtiene una respuesta del modelo.
        
        Args:
            force_reasoning: Si True, fuerza el uso del modelo de razonamiento
            user_query: Query del usuario para selección inteligente de herramientas
        """
        # Seleccionar modelo apropiado
        model = REASONING_MODEL if force_reasoning else self.model
        
        # Selección dinámica de herramientas según la query
        tools_to_use = self.tools
        if user_query:
            tools_to_use = get_smart_tools(user_query, self.tools)
        
        # Modelos de razonamiento (o3-mini) no soportan temperature
        params = {
            "model": model,
            "messages": self.messages,
            "tools": tools_to_use
        }
        
        # Solo agregar temperature si NO es un modelo de razonamiento
        if model != REASONING_MODEL:
            params["temperature"] = 0.3
        
        return self.client.chat.completions.create(**params)
    
    def execute_tool_call(self, tool_call):
        """
        Ejecuta una llamada a herramienta.
        
        Args:
            tool_call: Objeto de llamada a herramienta de OpenAI
            
        Returns:
            Resultado de la función ejecutada
        """
        fn_name = tool_call.function.name
        args = json.loads(tool_call.function.arguments)
        
        # Detectar si requiere razonamiento profundo
        requires_reasoning = fn_name in REASONING_TASKS
        model_indicator = "🧠" if requires_reasoning else "⚙️"
        
        print(f"\n{model_indicator} {self.name} ejecutando: {fn_name}")
        if requires_reasoning:
            print(f"   💭 Usando modelo de razonamiento: {REASONING_MODEL}")
        print(f"   Argumentos: {json.dumps(args, ensure_ascii=False, indent=2)}")
        
        # Ejecutar la función
        if fn_name in self.tool_functions:
            try:
                result = self.tool_functions[fn_name](**args)
                return result
            except Exception as e:
                error_msg = f"Error ejecutando {fn_name}: {str(e)}"
                print(f"❌ {error_msg}")
                return {"error": error_msg}
        else:
            return {"error": f"Función {fn_name} no encontrada"}
    
    def process_response(self, response, use_reasoning=False, user_query=None):
        """
        Procesa la respuesta del modelo y maneja llamadas a herramientas.
        Permite múltiples rondas de llamadas a herramientas si es necesario.
        
        Args:
            response: Respuesta del modelo
            use_reasoning: Si True, usa modelo de razonamiento en próxima iteración
            user_query: Query del usuario para selección de herramientas
            
        Returns:
            Mensaje final del asistente
        """
        assistant_message = response.choices[0].message
        
        # Convertir a diccionario para mantener consistencia
        message_dict = {
            "role": "assistant",
            "content": assistant_message.content
        }
        if assistant_message.tool_calls:
            message_dict["tool_calls"] = assistant_message.tool_calls
        
        self.messages.append(message_dict)
        
        # Verificar si hay llamadas a herramientas
        if assistant_message.tool_calls:
            # Determinar si alguna herramienta requiere razonamiento
            needs_reasoning = any(
                tc.function.name in REASONING_TASKS 
                for tc in assistant_message.tool_calls
            )
            
            # Ejecutar cada herramienta llamada
            for tool_call in assistant_message.tool_calls:
                fn_result = self.execute_tool_call(tool_call)
                fn_name = tool_call.function.name
                
                # Convertir resultado a formato TOON (ahorro de 40-70% de tokens)
                try:
                    toon_result = format_tool_result(fn_result, tool_name=fn_name)
                    
                    # Limitar tamaño DESPUÉS de conversión TOON
                    max_result_chars = 15000  # Incrementado porque TOON es más eficiente
                    
                    if len(toon_result) > max_result_chars:
                        # Si aún es muy grande después de TOON, truncar con mensaje
                        toon_result = toon_result[:max_result_chars] + "\n... [Resultado truncado - solicita paginación si necesitas más]"
                    
                    result_str = toon_result
                    
                    # Debug: mostrar ahorro de tokens
                    if isinstance(fn_result, (dict, list)):
                        json_str = json.dumps(fn_result, ensure_ascii=False)
                        savings = estimate_token_savings(json_str)
                        if savings.get("savings_percent", 0) > 0:
                            print(f"   📊 Ahorro TOON: {savings['savings_percent']}% ({savings['tokens_saved']} tokens)")
                
                except Exception as e:
                    # Fallback a JSON si TOON falla
                    print(f"⚠️ Error convirtiendo a TOON: {e}, usando JSON")
                    result_str = json.dumps(fn_result, ensure_ascii=False)
                    max_result_chars = 10000
                    if len(result_str) > max_result_chars:
                        result_str = result_str[:max_result_chars] + "\n... [Resultado truncado]"
                
                # Agregar resultado al historial
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.function.name,
                    "content": result_str
                })
            
            # Obtener respuesta final del modelo (puede llamar más herramientas)
            # Si alguna herramienta requiere razonamiento, usar modelo apropiado
            final_response = self.get_completion(force_reasoning=needs_reasoning, user_query=user_query)
            return self.process_response(final_response, use_reasoning=needs_reasoning, user_query=user_query)  # Recursivo
        else:
            # Respuesta directa sin herramientas
            return assistant_message.content
    
    def chat(self, user_input):
        """
        Método principal para interactuar con el agente.
        Ahora guarda turnos en memoria persistente.

        Args:
            user_input: Entrada del usuario

        Returns:
            Respuesta del asistente
        """
        # Limpiar contexto AGRESIVAMENTE si está muy largo
        if len(self.messages) > 10:
            self._trim_context(max_messages=6)  # Solo últimos 6 mensajes

        # Inyectar memoria relevante basada en la query actual
        self._inject_recent_memory(user_query=user_input, max_tokens=1500)

        self.add_user_message(user_input)
        response = self.get_completion(user_query=user_input)
        assistant_response = self.process_response(response, user_query=user_input)
        
        # Guardar turno completo en memoria
        tool_calls_list = []
        for msg in self.messages:
            # Verificar que msg es un diccionario
            if isinstance(msg, dict) and msg.get("role") == "tool":
                tool_calls_list.append({
                    "name": msg.get("name"),
                    "content": str(msg.get("content", ""))[:500]  # Truncar para no saturar
                })
        
        self.memory.save_conversation_turn(
            user_message=user_input,
            assistant_response=assistant_response,
            tool_calls=tool_calls_list if tool_calls_list else None,
            session_id=self.session_id
        )
        
        return assistant_response
    
    def reset_conversation(self):
        """Reinicia la conversación manteniendo solo el prompt del sistema."""
        system_message = self.messages[0]
        self.messages = [system_message]
        print("🔄 Conversación reiniciada")
    
    def _trim_context(self, max_messages=10):
        """Limita el contexto manteniendo solo los mensajes más recientes."""
        if len(self.messages) > max_messages + 1:  # +1 por el system prompt
            system_msg = self.messages[0]
            recent_messages = self.messages[-(max_messages):]
            self.messages = [system_msg] + recent_messages
            print(f"✂️ Contexto recortado a {len(self.messages)} mensajes")
    
    def get_conversation_stats(self):
        """Obtiene estadísticas de la conversación actual y memoria persistente."""
        tool_calls = sum(1 for msg in self.messages if isinstance(msg, dict) and msg.get("role") == "tool")
        user_messages = sum(1 for msg in self.messages if isinstance(msg, dict) and msg.get("role") == "user")
        
        # Incluir estadísticas de memoria
        memory_stats = self.memory.get_statistics()
        
        return {
            "total_messages": len(self.messages),
            "user_messages": user_messages,
            "tool_calls": tool_calls,
            "model": self.model,
            "memory": memory_stats
        }