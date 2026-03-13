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
import os
import re


class ConversationMemory:
    """Gestiona la memoria de conversaciones usando ChromaDB."""

    def __init__(self, storage_path: str = "memory_storage", user_id: str = "default"):
        """
        Inicializa el sistema de memoria.

        Args:
            storage_path: Directorio para ChromaDB persistente
            user_id: ID del usuario (para multi-usuario)
        """
        self.user_id = user_id
        self.storage_path = os.path.abspath(storage_path)

        # Intentar usar PersistentClient, fallback a EphemeralClient si falla
        self.client = self._create_client()
        
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

        stats = self.get_statistics()
        storage_type = "persistente" if self.is_persistent else "memoria"
        print(f"[MEMORIA] Inicializada ({storage_type}): {stats['total_messages']} msgs, {stats['total_facts']} hechos")

    def _create_client(self):
        """
        Crea cliente ChromaDB con fallback.
        Intenta PersistentClient primero, si falla usa EphemeralClient.
        """
        self.is_persistent = False

        # Intentar cliente persistente
        try:
            os.makedirs(self.storage_path, exist_ok=True)
            client = chromadb.PersistentClient(
                path=self.storage_path,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            self.is_persistent = True
            print(f"[MEMORIA] Usando almacenamiento persistente: {self.storage_path}")
            return client
        except Exception as e:
            print(f"[MEMORIA] PersistentClient falló ({e}), usando memoria volátil")
            return chromadb.EphemeralClient(
                settings=Settings(anonymized_telemetry=False, allow_reset=True)
            )
    
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
        session_id: Optional[str] = None,
        auto_extract_facts: bool = True
    ) -> Dict[str, Any]:
        """
        Guarda un turno completo de conversación (pregunta + respuesta).

        Args:
            user_message: Mensaje del usuario
            assistant_response: Respuesta del asistente
            tool_calls: Llamadas a herramientas realizadas
            session_id: ID de sesión
            auto_extract_facts: Si debe extraer hechos automáticamente

        Returns:
            IDs de los mensajes guardados y hechos extraídos
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

        result = {
            "user": user_id,
            "assistant": assistant_id,
            "session": session_id,
            "facts_extracted": []
        }

        # Extracción automática de hechos
        if auto_extract_facts:
            try:
                result["facts_extracted"] = self.extract_facts_from_conversation(
                    user_message=user_message,
                    assistant_response=assistant_response,
                    tool_results=tool_calls
                )
            except Exception as e:
                print(f"[MEMORIA] Error extrayendo hechos: {e}")

        return result
    
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

        lines = ["INFORMACION CONOCIDA DEL USUARIO:"]
        for cat, facts_list in categories.items():
            lines.append(f"\n{cat.upper()}:")
            for f in facts_list[:5]:  # Máximo 5 por categoría
                lines.append(f"  - {f}")

        return "\n".join(lines)

    def extract_facts_from_conversation(
        self,
        user_message: str,
        assistant_response: str,
        tool_results: Optional[List[Dict]] = None
    ) -> List[str]:
        """
        Extrae automáticamente hechos importantes de una conversación.
        Usa patrones para detectar información relevante sin llamar a LLM.

        Args:
            user_message: Mensaje del usuario
            assistant_response: Respuesta del asistente
            tool_results: Resultados de herramientas ejecutadas

        Returns:
            Lista de IDs de hechos guardados
        """
        extracted_facts = []
        combined_text = f"{user_message}\n{assistant_response}"

        # Patrones para extraer hechos automáticamente
        patterns = {
            "tech_stack": [
                # Menciones directas de tecnologías (más simples y efectivas)
                (r'\b(usa|usando|utiliza|utilizando|con|en)\s+(Django|Flask|FastAPI|React|Vue|Angular|Next\.js|Express|Laravel|Spring|Rails)\b', 0.9),
                (r'\b(Django|Flask|FastAPI|React|Vue|Angular|Next\.js|Express|Laravel|Spring|Rails)\s+(como|para|en el)\s+(backend|frontend|api)', 0.9),
                (r'\b(proyecto|app|aplicacion|sistema)\s+(?:en|con|usa)\s+(Python|PHP|JavaScript|TypeScript|Java|Go|Rust|Ruby)\b', 0.85),
                (r'\b(Python|PHP|JavaScript|TypeScript|Java|Go|Rust|Ruby|C\#|Kotlin|Swift)\s+(?:y|con)\s+(Python|PHP|JavaScript|TypeScript|Java|Go|Rust|Ruby|C\#|Kotlin|Swift)\b', 0.85),
                # Bases de datos
                (r'\b(PostgreSQL|MySQL|MariaDB|MongoDB|Redis|SQLite|Oracle|SQL Server|Elasticsearch|DynamoDB)\b', 0.85),
                # Lenguajes y frameworks mencionados con contexto
                (r'\b(trabajo|desarrollo|programo)\s+(con|en)\s+(\w+)', 0.8),
            ],
            "project_info": [
                # Información del proyecto (más flexible)
                (r'(?:el\s+)?proyecto\s+(?:se\s+llama|es)\s+["\']?([^\"\'\.\,]+)["\']?', 0.9),
                (r'(?:estoy\s+)?(?:trabajando|desarrollando)\s+(?:en|un)\s+([^\.\,]{5,50})', 0.8),
                (r'(?:el\s+)?repositorio\s+(?:es|esta\s+en)\s+([^\s\.\,]+)', 0.85),
                (r'ruta[:\s]+([A-Za-z]:[/\\][^\s\.\,]+|/[^\s\.\,]+)', 0.9),
            ],
            "preferences": [
                # Preferencias del usuario
                (r'(?:yo\s+)?(prefiero|me\s+gusta|quiero|necesito)\s+(?:que\s+)?([^\.\,]{8,60})', 0.7),
                (r'(siempre|normalmente|usualmente)\s+([^\.\,]{8,60})', 0.65),
                (r'no\s+(?:me\s+)?(gusta|quiero|necesito)\s+([^\.\,]{8,60})', 0.7),
            ],
            "workflow": [
                # Flujo de trabajo
                (r'(?:usa|utiliza|ejecuta|activa)\s+(Smart\s*Orchestrator|modo\s+\w+)', 0.9),
                (r'(?:mi\s+)?(?:flujo|proceso|workflow)\s+(?:es|incluye)\s+([^\.\,]+)', 0.8),
            ],
        }

        # Extraer hechos usando patrones
        for category, category_patterns in patterns.items():
            for pattern, confidence in category_patterns:
                matches = re.finditer(pattern, combined_text, re.IGNORECASE)
                for match in matches:
                    # Construir el hecho basado en el match
                    fact_text = match.group(0).strip()
                    if len(fact_text) > 10 and len(fact_text) < 200:
                        # Evitar duplicados verificando similitud
                        existing_facts = self.get_facts(category=category)
                        is_duplicate = any(
                            self._text_similarity(fact_text, f["fact"]) > 0.8
                            for f in existing_facts
                        )

                        if not is_duplicate:
                            fact_id = self.save_fact(
                                fact=fact_text,
                                category=category,
                                confidence=confidence,
                                source="auto_extraction"
                            )
                            extracted_facts.append(fact_id)

        # Extraer información de herramientas ejecutadas
        if tool_results:
            for tool_result in tool_results:
                tool_name = tool_result.get("name", "")

                # Extraer paths de proyectos analizados
                if tool_name in ["explore_directory", "analyze_directory", "read_file"]:
                    content = str(tool_result.get("content", ""))
                    # Detectar rutas de proyectos
                    path_match = re.search(r'["\']((?:[A-Za-z]:)?[/\\][^"\']+)["\']', content)
                    if path_match:
                        project_path = path_match.group(1)
                        fact_id = self.save_fact(
                            fact=f"Proyecto en ruta: {project_path}",
                            category="project_info",
                            confidence=0.95,
                            source=f"tool:{tool_name}"
                        )
                        extracted_facts.append(fact_id)

                # Extraer tecnologías detectadas
                if "detected_frameworks" in str(tool_result) or "detected_languages" in str(tool_result):
                    content = str(tool_result.get("content", ""))
                    frameworks = re.findall(r'detected_frameworks["\']?\s*:\s*\[([^\]]+)\]', content)
                    languages = re.findall(r'detected_languages["\']?\s*:\s*\[([^\]]+)\]', content)

                    for fw_list in frameworks:
                        for fw in re.findall(r'["\']([^"\']+)["\']', fw_list):
                            fact_id = self.save_fact(
                                fact=f"Proyecto usa framework: {fw}",
                                category="tech_stack",
                                confidence=0.95,
                                source=f"tool:{tool_name}"
                            )
                            extracted_facts.append(fact_id)

                    for lang_list in languages:
                        for lang in re.findall(r'["\']([^"\']+)["\']', lang_list):
                            fact_id = self.save_fact(
                                fact=f"Proyecto usa lenguaje: {lang}",
                                category="tech_stack",
                                confidence=0.95,
                                source=f"tool:{tool_name}"
                            )
                            extracted_facts.append(fact_id)

        if extracted_facts:
            print(f"[MEMORIA] Extraidos {len(extracted_facts)} hechos automaticamente")

        return extracted_facts

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calcula similitud simple entre dos textos (Jaccard)."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union)
    
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
                embeddings=[[0.0] * 384],
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
