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
from tool_selector import get_smart_tools


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
    
    def _inject_recent_memory(self):
        """
        Inyecta memoria reciente en el contexto antes de cada solicitud.
        DESACTIVADO TEMPORALMENTE para ahorrar tokens.
        """
        # Desactivado: la memoria consume demasiados tokens
        # Si el usuario necesita contexto, puede pedirlo explícitamente
        pass
    
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
                
                # Limitar tamaño de respuesta AGRESIVAMENTE para no exceder límites de contexto
                result_str = json.dumps(fn_result, ensure_ascii=False)
                max_result_chars = 10000  # ~2.5K tokens máximo por resultado
                
                if len(result_str) > max_result_chars:
                    # Si es muy grande, resumir agresivamente
                    if isinstance(fn_result, dict):
                        # Mantener estructura pero limitar arrays drasticamente
                        limited_result = {}
                        for key, value in fn_result.items():
                            if isinstance(value, list):
                                # Solo primeros 3 elementos
                                if len(value) > 3:
                                    limited_result[key] = value[:3] + [f"[... {len(value) - 3} elementos más truncados]"]
                                else:
                                    limited_result[key] = value
                            elif isinstance(value, str) and len(value) > 500:
                                # Truncar strings largos
                                limited_result[key] = value[:500] + "..."
                            else:
                                limited_result[key] = value
                        result_str = json.dumps(limited_result, ensure_ascii=False)[:max_result_chars]
                    else:
                        result_str = result_str[:max_result_chars] + "\n... [Resultado truncado para limitar tokens]"
                
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
        
        # NO inyectar memoria (desactivado para ahorrar tokens)
        # self._inject_recent_memory()
        
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