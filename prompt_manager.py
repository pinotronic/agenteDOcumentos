"""
Sistema de gestión de prompts con ChromaDB.
Permite almacenar, versionar y recuperar prompts del sistema de forma dinámica.
"""
import chromadb
from chromadb.config import Settings
from typing import Dict, Optional, List
from datetime import datetime
import json


class PromptManager:
    """Gestiona prompts del sistema usando ChromaDB."""
    
    def __init__(self, storage_path: str = "prompt_storage"):
        """
        Inicializa el gestor de prompts con ChromaDB.
        
        Nota: Usando EphemeralClient por incompatibilidad de ChromaDB 1.3.6 
        con Python 3.13 en Windows.
        """
        # Usar cliente en memoria por compatibilidad con Python 3.13
        self.client = chromadb.EphemeralClient(
            settings=Settings(anonymized_telemetry=False, allow_reset=True)
        )
        
        self.collection = self.client.get_or_create_collection(
            name="system_prompts",
            metadata={"description": "Prompts del sistema versionados"}
        )
        
        # Inicializar con prompts por defecto si está vacío
        if self.collection.count() == 0:
            self._initialize_default_prompts()
    
    def _initialize_default_prompts(self):
        """Carga prompts por defecto en el sistema."""
        import os
        
        default_prompts = [
            {
                "id": "orchestrator_v1",
                "name": "Orquestador",
                "version": "1.0",
                "type": "system",
                "template": """Eres un agente orquestador experto en análisis de código y documentación.
Tu rol es coordinar el análisis de repositorios de código utilizando las herramientas disponibles.

CONTEXTO DE TRABAJO ACTUAL:
- Directorio de trabajo: {cwd}
- Usuario de Windows: {username}
- Sistema operativo: Windows

Responsabilidades:
1. Explorar directorios y seleccionar archivos relevantes
2. Coordinar el análisis de múltiples archivos
3. Gestionar el almacenamiento en RAG
4. Responder consultas sobre el código analizado
5. Cuando el usuario mencione archivos, considera tanto rutas locales como rutas de red

Siempre usa las herramientas de forma eficiente y proporciona actualizaciones de progreso.""",
                "variables": ["cwd", "username"],
                "description": "Prompt principal del agente orquestador",
                "tags": ["orchestrator", "main", "production"]
            },
            {
                "id": "analyzer_v1",
                "name": "Analizador",
                "version": "1.0",
                "type": "system",
                "template": """Eres un agente analizador experto en múltiples lenguajes de programación.
Tu rol es analizar archivos de código y documentación en profundidad.

Para cada archivo, debes extraer:
1. **Resumen general**: Propósito y funcionalidad del archivo
2. **Imports/Dependencias**: Todos los imports y dependencias externas
3. **Clases**: Nombre, herencia, docstring, métodos públicos
4. **Funciones**: Firma completa, parámetros, tipo de retorno, docstring
5. **Constantes/Variables globales**: Nombres y valores si son relevantes
6. **Contratos**: Interfaces, protocolos, tipos definidos
7. **Complejidad**: Estimación (baja/media/alta)

IMPORTANTE: Responde SIEMPRE en formato JSON válido con la estructura definida.""",
                "variables": [],
                "description": "Prompt del agente analizador de código",
                "tags": ["analyzer", "code", "production"]
            },
            {
                "id": "code_review_v1",
                "name": "Revisor de Código",
                "version": "1.0",
                "type": "tool",
                "template": """Eres un desarrollador senior realizando code review.

Analiza el código con estos criterios:
1. **Bugs potenciales**: Errores lógicos, edge cases no manejados
2. **Seguridad**: Vulnerabilidades, validaciones faltantes
3. **Performance**: Ineficiencias, código O(n²) optimizable
4. **Mantenibilidad**: Legibilidad, nombres descriptivos, complejidad
5. **Best Practices**: Patrones recomendados del lenguaje

Formato de respuesta: JSON con severity (critical/high/medium/low).""",
                "variables": [],
                "description": "Prompt para revisiones de código",
                "tags": ["review", "quality", "tool"]
            },
            {
                "id": "debug_assistant_v1",
                "name": "Asistente de Debug",
                "version": "1.0",
                "type": "tool",
                "template": """Eres un experto en debugging y análisis de causa raíz.

Proceso de análisis:
1. **Reproducir**: Entender el problema y sus condiciones
2. **Aislar**: Identificar el punto exacto del fallo
3. **Analizar**: Determinar la causa raíz (no solo síntomas)
4. **Solucionar**: Proponer fixes con explicación
5. **Prevenir**: Sugerir tests para evitar regresiones

Incluye: stack traces, variables involucradas, hipótesis probadas.""",
                "variables": [],
                "description": "Prompt para asistencia en debugging",
                "tags": ["debug", "troubleshooting", "tool"]
            }
        ]
        
        for prompt in default_prompts:
            self.save_prompt(**prompt)
    
    def save_prompt(
        self,
        id: str,
        name: str,
        template: str,
        version: str = "1.0",
        type: str = "system",
        variables: List[str] = None,
        description: str = "",
        tags: List[str] = None
    ):
        """
        Guarda o actualiza un prompt en ChromaDB.
        
        Args:
            id: ID único del prompt
            name: Nombre descriptivo
            template: Template del prompt (puede usar {variables})
            version: Versión del prompt
            type: Tipo (system, tool, user)
            variables: Lista de variables que usa el template
            description: Descripción del propósito
            tags: Etiquetas para búsqueda
        """
        metadata = {
            "name": name,
            "version": version,
            "type": type,
            "variables": json.dumps(variables or []),
            "description": description,
            "tags": json.dumps(tags or []),
            "updated_at": datetime.now().isoformat()
        }
        
        self.collection.upsert(
            ids=[id],
            documents=[template],
            metadatas=[metadata]
        )
    
    def get_prompt(
        self,
        id: Optional[str] = None,
        name: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Optional[Dict]:
        """
        Recupera un prompt por ID, nombre o tags.
        
        Args:
            id: ID del prompt
            name: Nombre del prompt
            tags: Tags para filtrar
            
        Returns:
            Diccionario con el prompt y sus metadatos
        """
        if id:
            results = self.collection.get(ids=[id], include=["documents", "metadatas"])
            if results["ids"]:
                return self._format_result(results, 0)
        
        if name:
            results = self.collection.get(
                where={"name": name},
                include=["documents", "metadatas"]
            )
            if results["ids"]:
                return self._format_result(results, 0)
        
        if tags:
            # Búsqueda semántica por tags
            query = " ".join(tags)
            results = self.collection.query(
                query_texts=[query],
                n_results=1,
                include=["documents", "metadatas"]
            )
            if results["ids"][0]:
                return self._format_result_query(results, 0)
        
        return None
    
    def _format_result(self, results: Dict, index: int) -> Dict:
        """Formatea resultado de get()."""
        metadata = results["metadatas"][index]
        return {
            "id": results["ids"][index],
            "template": results["documents"][index],
            "name": metadata["name"],
            "version": metadata["version"],
            "type": metadata["type"],
            "variables": json.loads(metadata["variables"]),
            "description": metadata["description"],
            "tags": json.loads(metadata["tags"]),
            "updated_at": metadata["updated_at"]
        }
    
    def _format_result_query(self, results: Dict, index: int) -> Dict:
        """Formatea resultado de query()."""
        metadata = results["metadatas"][0][index]
        return {
            "id": results["ids"][0][index],
            "template": results["documents"][0][index],
            "name": metadata["name"],
            "version": metadata["version"],
            "type": metadata["type"],
            "variables": json.loads(metadata["variables"]),
            "description": metadata["description"],
            "tags": json.loads(metadata["tags"]),
            "updated_at": metadata["updated_at"]
        }
    
    def render_prompt(self, id: str, **kwargs) -> str:
        """
        Renderiza un prompt con variables.
        
        Args:
            id: ID del prompt
            **kwargs: Variables para el template
            
        Returns:
            Prompt renderizado con variables reemplazadas
        """
        prompt_data = self.get_prompt(id=id)
        if not prompt_data:
            raise ValueError(f"Prompt con id '{id}' no encontrado")
        
        template = prompt_data["template"]
        return template.format(**kwargs)
    
    def list_prompts(self, type: Optional[str] = None) -> List[Dict]:
        """
        Lista todos los prompts disponibles.
        
        Args:
            type: Filtrar por tipo (system, tool, user)
            
        Returns:
            Lista de prompts con sus metadatos
        """
        if type:
            results = self.collection.get(
                where={"type": type},
                include=["documents", "metadatas"]
            )
        else:
            results = self.collection.get(include=["documents", "metadatas"])
        
        prompts = []
        for i in range(len(results["ids"])):
            prompts.append(self._format_result(results, i))
        
        return prompts
    
    def search_prompts(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Busca prompts por similitud semántica.
        
        Args:
            query: Texto de búsqueda
            limit: Número máximo de resultados
            
        Returns:
            Lista de prompts relevantes
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=limit,
            include=["documents", "metadatas", "distances"]
        )
        
        prompts = []
        for i in range(len(results["ids"][0])):
            prompt = self._format_result_query(results, i)
            prompt["relevance"] = 1.0 - results["distances"][0][i]
            prompts.append(prompt)
        
        return prompts
    
    def get_statistics(self) -> Dict:
        """Obtiene estadísticas del gestor de prompts."""
        all_prompts = self.list_prompts()
        
        types = {}
        for prompt in all_prompts:
            t = prompt["type"]
            types[t] = types.get(t, 0) + 1
        
        return {
            "total_prompts": len(all_prompts),
            "by_type": types,
            "storage": "ChromaDB (Vectorial)"
        }
