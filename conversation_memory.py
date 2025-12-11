"""
Sistema de Memoria Conversacional con ChromaDB.
Almacena y recupera contexto de conversaciones previas para continuidad entre sesiones.
"""
import chromadb
from chromadb.config import Settings
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
import hashlib


class ConversationMemory:
    """Gestiona la memoria de conversaciones usando ChromaDB."""
    
    def __init__(self, storage_path: str = "memory_storage", user_id: str = "default"):
        """
        Inicializa el sistema de memoria.
        
        Args:
            storage_path: Directorio para ChromaDB
            user_id: ID del usuario (para multi-usuario)
        
        Nota: Usando EphemeralClient por incompatibilidad de ChromaDB 1.3.6 
        con Python 3.13 en Windows.
        """
        self.user_id = user_id
        # Usar cliente en memoria por compatibilidad con Python 3.13
        self.client = chromadb.EphemeralClient(
            settings=Settings(anonymized_telemetry=False, allow_reset=True)
        )
        
        # Colección para mensajes de conversación
        self.messages_collection = self.client.get_or_create_collection(
            name="conversation_messages",
            metadata={"description": "Historial de mensajes con embeddings"}
        )
        
        # Colección para contexto de sesiones
        self.sessions_collection = self.client.get_or_create_collection(
            name="conversation_sessions",
            metadata={"description": "Metadatos de sesiones"}
        )
        
        # Colección para hechos importantes
        self.facts_collection = self.client.get_or_create_collection(
            name="user_facts",
            metadata={"description": "Hechos importantes del usuario"}
        )
        
        print(f"💾 Memoria inicializada: {self.get_statistics()['total_messages']} mensajes")
    
    def save_message(
        self,
        role: str,
        content: str,
        session_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Guarda un mensaje en la memoria.
        
        Args:
            role: user, assistant, system, tool
            content: Contenido del mensaje
            session_id: ID de sesión (auto-generado si None)
            metadata: Metadatos adicionales (tokens, model, etc.)
        
        Returns:
            ID del mensaje guardado
        """
        if session_id is None:
            session_id = self._get_or_create_session()
        
        message_id = hashlib.md5(
            f"{session_id}_{datetime.now().isoformat()}_{role}".encode()
        ).hexdigest()
        
        message_metadata = {
            "user_id": self.user_id,
            "session_id": session_id,
            "role": role,
            "timestamp": datetime.now().isoformat(),
            "content_length": len(content),
            **(metadata or {})
        }
        
        self.messages_collection.upsert(
            ids=[message_id],
            documents=[content],
            metadatas=[message_metadata]
        )
        
        return message_id
    
    def save_conversation_turn(
        self,
        user_message: str,
        assistant_response: str,
        tool_calls: Optional[List[Dict]] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Guarda un turno completo de conversación (pregunta + respuesta).
        
        Args:
            user_message: Mensaje del usuario
            assistant_response: Respuesta del asistente
            tool_calls: Llamadas a herramientas realizadas
            session_id: ID de sesión
        
        Returns:
            IDs de los mensajes guardados
        """
        if session_id is None:
            session_id = self._get_or_create_session()
        
        user_id = self.save_message("user", user_message, session_id)
        
        # Guardar tool calls si existen
        if tool_calls:
            for tool_call in tool_calls:
                self.save_message(
                    "tool",
                    json.dumps(tool_call, ensure_ascii=False),
                    session_id,
                    {"tool_name": tool_call.get("name")}
                )
        
        assistant_id = self.save_message("assistant", assistant_response, session_id)
        
        return {"user": user_id, "assistant": assistant_id, "session": session_id}
    
    def search_similar_conversations(
        self,
        query: str,
        limit: int = 5,
        role_filter: Optional[str] = None
    ) -> List[Dict]:
        """
        Busca conversaciones similares por contenido semántico.
        
        Args:
            query: Texto de búsqueda
            limit: Número máximo de resultados
            role_filter: Filtrar por rol (user, assistant)
        
        Returns:
            Lista de mensajes relevantes con contexto
        """
        where_filter = {"user_id": self.user_id}
        if role_filter:
            where_filter = {
                "$and": [
                    {"user_id": self.user_id},
                    {"role": role_filter}
                ]
            }
        
        results = self.messages_collection.query(
            query_texts=[query],
            n_results=limit,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )
        
        messages = []
        for i in range(len(results["ids"][0])):
            metadata = results["metadatas"][0][i]
            messages.append({
                "id": results["ids"][0][i],
                "content": results["documents"][0][i],
                "role": metadata["role"],
                "session_id": metadata["session_id"],
                "timestamp": metadata["timestamp"],
                "relevance": 1.0 - results["distances"][0][i]
            })
        
        return messages
    
    def get_session_history(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Obtiene todo el historial de una sesión.
        
        Args:
            session_id: ID de la sesión
            limit: Limitar a los últimos N mensajes
        
        Returns:
            Lista de mensajes en orden cronológico
        """
        results = self.messages_collection.get(
            where={
                "$and": [
                    {"user_id": self.user_id},
                    {"session_id": session_id}
                ]
            },
            include=["documents", "metadatas"]
        )
        
        messages = []
        for i in range(len(results["ids"])):
            metadata = results["metadatas"][i]
            messages.append({
                "id": results["ids"][i],
                "content": results["documents"][i],
                "role": metadata["role"],
                "timestamp": metadata["timestamp"]
            })
        
        # Ordenar por timestamp
        messages.sort(key=lambda x: x["timestamp"])
        
        if limit:
            messages = messages[-limit:]
        
        return messages
    
    def get_recent_context(
        self,
        limit: int = 10,
        session_id: Optional[str] = None
    ) -> str:
        """
        Obtiene contexto reciente formateado para el prompt.
        
        Args:
            limit: Número de mensajes recientes
            session_id: Sesión específica (None = última sesión)
        
        Returns:
            String con contexto formateado
        """
        if session_id is None:
            session_id = self._get_latest_session()
        
        if not session_id:
            return "Sin conversaciones previas."
        
        messages = self.get_session_history(session_id, limit=limit)
        
        if not messages:
            return "Sin mensajes en esta sesión."
        
        context_lines = ["📜 CONTEXTO DE CONVERSACIÓN RECIENTE:"]
        context_lines.append("─" * 60)
        
        for msg in messages:
            role_icon = {"user": "👤", "assistant": "🤖", "tool": "⚙️"}.get(msg["role"], "•")
            timestamp = msg["timestamp"].split("T")[1][:8]  # HH:MM:SS
            content = msg["content"][:200] + "..." if len(msg["content"]) > 200 else msg["content"]
            context_lines.append(f"{role_icon} [{timestamp}] {content}")
        
        context_lines.append("─" * 60)
        return "\n".join(context_lines)
    
    def save_fact(
        self,
        fact: str,
        category: str = "general",
        confidence: float = 1.0,
        source: str = "conversation"
    ) -> str:
        """
        Guarda un hecho importante sobre el usuario/proyecto.
        
        Args:
            fact: Hecho a guardar (ej: "Usuario trabaja con PHP y PostgreSQL")
            category: Categoría (tech_stack, preferences, project_info)
            confidence: Confianza en el hecho (0.0 - 1.0)
            source: De dónde se extrajo el hecho
        
        Returns:
            ID del hecho guardado
        """
        fact_id = hashlib.md5(fact.encode()).hexdigest()
        
        metadata = {
            "user_id": self.user_id,
            "category": category,
            "confidence": confidence,
            "source": source,
            "timestamp": datetime.now().isoformat()
        }
        
        self.facts_collection.upsert(
            ids=[fact_id],
            documents=[fact],
            metadatas=[metadata]
        )
        
        return fact_id
    
    def get_facts(
        self,
        category: Optional[str] = None,
        min_confidence: float = 0.5
    ) -> List[Dict]:
        """
        Obtiene hechos guardados sobre el usuario.
        
        Args:
            category: Filtrar por categoría
            min_confidence: Confianza mínima
        
        Returns:
            Lista de hechos
        """
        where_filter = {"user_id": self.user_id}
        if category:
            where_filter = {
                "$and": [
                    {"user_id": self.user_id},
                    {"category": category}
                ]
            }
        
        results = self.facts_collection.get(
            where=where_filter,
            include=["documents", "metadatas"]
        )
        
        facts = []
        for i in range(len(results["ids"])):
            metadata = results["metadatas"][i]
            if float(metadata.get("confidence", 0)) >= min_confidence:
                facts.append({
                    "id": results["ids"][i],
                    "fact": results["documents"][i],
                    "category": metadata["category"],
                    "confidence": float(metadata["confidence"]),
                    "timestamp": metadata["timestamp"]
                })
        
        return facts
    
    def get_facts_summary(self) -> str:
        """Obtiene resumen de hechos importantes para incluir en prompts."""
        facts = self.get_facts(min_confidence=0.7)
        
        if not facts:
            return ""
        
        categories = {}
        for fact in facts:
            cat = fact["category"]
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(fact["fact"])
        
        lines = ["📌 INFORMACIÓN CONOCIDA DEL USUARIO:"]
        for cat, facts_list in categories.items():
            lines.append(f"\n{cat.upper()}:")
            for f in facts_list[:5]:  # Máximo 5 por categoría
                lines.append(f"  • {f}")
        
        return "\n".join(lines)
    
    def _get_or_create_session(self) -> str:
        """Obtiene o crea una sesión para el día actual."""
        session_id = f"{self.user_id}_{datetime.now().strftime('%Y%m%d')}"
        
        # Verificar si ya existe
        existing = self.sessions_collection.get(ids=[session_id])
        
        if not existing["ids"]:
            # Crear nueva sesión
            self.sessions_collection.upsert(
                ids=[session_id],
                documents=[f"Sesión del {datetime.now().strftime('%d/%m/%Y')}"],
                metadatas=[{
                    "user_id": self.user_id,
                    "date": datetime.now().strftime('%Y-%m-%d'),
                    "created_at": datetime.now().isoformat()
                }]
            )
        
        return session_id
    
    def _get_latest_session(self) -> Optional[str]:
        """Obtiene el ID de la sesión más reciente."""
        results = self.sessions_collection.get(
            where={"user_id": self.user_id},
            include=["metadatas"]
        )
        
        if not results["ids"]:
            return None
        
        # Ordenar por created_at y obtener el más reciente
        sessions = list(zip(results["ids"], results["metadatas"]))
        sessions.sort(key=lambda x: x[1].get("created_at", ""), reverse=True)
        
        return sessions[0][0] if sessions else None
    
    def get_statistics(self) -> Dict[str, Any]:
        """Obtiene estadísticas de la memoria."""
        total_messages = self.messages_collection.count()
        total_sessions = self.sessions_collection.count()
        total_facts = self.facts_collection.count()
        
        # Contar por rol
        roles = {}
        all_messages = self.messages_collection.get(
            where={"user_id": self.user_id},
            include=["metadatas"]
        )
        for metadata in all_messages["metadatas"]:
            role = metadata.get("role", "unknown")
            roles[role] = roles.get(role, 0) + 1
        
        return {
            "user_id": self.user_id,
            "total_messages": total_messages,
            "total_sessions": total_sessions,
            "total_facts": total_facts,
            "messages_by_role": roles,
            "storage": "ChromaDB (Vectorial)"
        }
    
    def clear_old_sessions(self, days_to_keep: int = 30):
        """
        Elimina sesiones antiguas para mantener la DB limpia.
        
        Args:
            days_to_keep: Días de historial a mantener
        """
        from datetime import timedelta
        cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).isoformat()
        
        # TODO: Implementar eliminación por fecha
        # ChromaDB no soporta delete con where < fecha directamente
        # Requiere obtener IDs y eliminar manualmente
        pass
