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
        
        # Obtener contexto de conversaciones previas
        context = self.memory.get_recent_context(limit=5)
        facts = self.memory.get_facts_summary()
        
        # Construir prompt del sistema con contexto
        base_prompt = system_prompt or ORCHESTRATOR_SYSTEM_PROMPT
        full_prompt = base_prompt
        
        if facts:
            full_prompt += f"\n\n{facts}"
        
        if context and "Sin conversaciones previas" not in context:
            full_prompt += f"\n\n{context}"
        
        # Inicializar historial de mensajes con prompt especializado
        self.messages = [
            {"role": "system", "content": full_prompt}
        ]
    
    def add_user_message(self, content):
        """Agrega un mensaje del usuario al historial."""
        self.messages.append({"role": "user", "content": content})
    
    def _inject_recent_memory(self):
        """
        Inyecta memoria reciente en el contexto antes de cada solicitud.
        Actualiza el prompt del sistema con los últimos mensajes guardados.
        """
        # Obtener contexto actualizado (últimos 5 mensajes de la sesión)
        context = self.memory.get_recent_context(limit=5, session_id=self.session_id)
        
        # Debug: verificar qué se está recuperando
        print(f"🧠 [DEBUG] Recuperando memoria de sesión: {self.session_id}")
        print(f"🧠 [DEBUG] Contexto obtenido: {context[:100] if context else 'VACÍO'}...")
        
        # Si hay contexto relevante y no está vacío
        if context and "Sin conversaciones previas" not in context and "Sin mensajes" not in context:
            # Verificar si el primer mensaje es el system prompt
            if self.messages and isinstance(self.messages[0], dict) and self.messages[0].get("role") == "system":
                base_prompt = self.messages[0]["content"]
                
                # Remover contexto viejo si existe
                if "📜 CONTEXTO DE CONVERSACIÓN RECIENTE:" in base_prompt:
                    base_prompt = base_prompt.split("📜 CONTEXTO DE CONVERSACIÓN RECIENTE:")[0].rstrip()
                
                # Agregar contexto actualizado
                updated_prompt = f"{base_prompt}\n\n{context}"
                self.messages[0]["content"] = updated_prompt
                print(f"✅ [DEBUG] Memoria inyectada en el prompt del sistema")
        else:
            print(f"⚠️  [DEBUG] No hay contexto para inyectar: {context}")
    
    def get_completion(self, force_reasoning=False):
        """
        Obtiene una respuesta del modelo.
        
        Args:
            force_reasoning: Si True, fuerza el uso del modelo de razonamiento
        """
        # Seleccionar modelo apropiado
        model = REASONING_MODEL if force_reasoning else self.model
        
        return self.client.chat.completions.create(
            model=model,
            messages=self.messages,
            tools=self.tools,
            temperature=0.3  # Temperatura moderada para balance creatividad/precisión
        )
    
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
    
    def process_response(self, response, use_reasoning=False):
        """
        Procesa la respuesta del modelo y maneja llamadas a herramientas.
        Permite múltiples rondas de llamadas a herramientas si es necesario.
        
        Args:
            response: Respuesta del modelo
            use_reasoning: Si True, usa modelo de razonamiento en próxima iteración
            
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
                
                # Limitar tamaño de respuesta para no exceder límites de contexto
                result_str = json.dumps(fn_result, ensure_ascii=False)
                if len(result_str) > 50000:  # ~12k tokens
                    # Si es muy grande, resumir
                    if isinstance(fn_result, dict):
                        # Mantener estructura pero limitar arrays
                        limited_result = {}
                        for key, value in fn_result.items():
                            if isinstance(value, list) and len(value) > 10:
                                limited_result[key] = value[:10] + [f"... (y {len(value) - 10} más)"]
                            else:
                                limited_result[key] = value
                        result_str = json.dumps(limited_result, ensure_ascii=False)
                    else:
                        result_str = result_str[:50000] + "... (resultado truncado)"
                
                # Agregar resultado al historial
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.function.name,
                    "content": result_str
                })
            
            # Obtener respuesta final del modelo (puede llamar más herramientas)
            # Si alguna herramienta requiere razonamiento, usar modelo apropiado
            final_response = self.get_completion(force_reasoning=needs_reasoning)
            return self.process_response(final_response, use_reasoning=needs_reasoning)  # Recursivo
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
        # Inyectar memoria reciente ANTES de procesar
        self._inject_recent_memory()
        
        self.add_user_message(user_input)
        response = self.get_completion()
        assistant_response = self.process_response(response)
        
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