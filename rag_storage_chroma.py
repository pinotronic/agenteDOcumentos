"""
Sistema de almacenamiento RAG con ChromaDB (Vectorial + Rápido).
Reemplazo del sistema JSON por base de datos vectorial para búsquedas semánticas ultra-rápidas.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import hashlib

import chromadb
from chromadb.config import Settings

from config import RAG_STORAGE_PATH


class RAGStorage:
    """Gestiona el almacenamiento persistente de análisis de código con ChromaDB."""
    
    def __init__(self, storage_path: str = RAG_STORAGE_PATH):
        """
        Inicializa el sistema de almacenamiento RAG con ChromaDB.
        
        Args:
            storage_path: Directorio donde ChromaDB almacenará los vectores
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        
        # Inicializar ChromaDB
        self.client = chromadb.PersistentClient(
            path=str(self.storage_path / "chromadb"),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Crear o obtener colección
        self.collection = self.client.get_or_create_collection(
            name="code_analysis",
            metadata={"description": "Análisis de código con embeddings semánticos"}
        )
        
        print(f"✅ RAG con ChromaDB inicializado: {self.collection.count()} documentos")
    
    def _generate_doc_id(self, file_path: str) -> str:
        """Genera un ID único para un archivo basado en su ruta."""
        return hashlib.md5(file_path.encode()).hexdigest()
    
    def _create_document_text(self, file_path: str, analysis: Dict[str, Any]) -> str:
        """
        Crea el texto del documento para embeddings semánticos.
        Combina toda la información relevante para búsqueda.
        """
        parts = [
            f"FILE: {Path(file_path).name}",
            f"PATH: {file_path}",
            f"TYPE: {analysis.get('file_type', 'unknown')}",
            f"SUMMARY: {analysis.get('summary', '')}",
        ]
        
        # Agregar imports
        if analysis.get('imports'):
            parts.append(f"IMPORTS: {', '.join(analysis['imports'][:20])}")
        
        # Agregar clases
        for cls in analysis.get('classes', [])[:10]:
            parts.append(f"CLASS: {cls.get('name', '')}")
            if cls.get('docstring'):
                parts.append(f"  {cls['docstring'][:200]}")
        
        # Agregar funciones
        for func in analysis.get('functions', [])[:20]:
            parts.append(f"FUNCTION: {func.get('name', '')}")
            if func.get('docstring'):
                parts.append(f"  {func['docstring'][:200]}")
        
        # Agregar features clave
        if analysis.get('key_features'):
            parts.append(f"FEATURES: {', '.join(analysis['key_features'][:10])}")
        
        return "\n".join(parts)
    
    def save_analysis(self, file_path: str, analysis: Dict[str, Any], curl_metadata: Optional[Dict] = None) -> str:
        """
        Guarda el análisis de un archivo en el RAG con ChromaDB.
        
        Args:
            file_path: Ruta del archivo analizado
            analysis: Resultado del análisis (JSON del agente analizador)
            curl_metadata: Metadatos de curl para archivos PHP (opcional)
            
        Returns:
            ID del documento guardado
        """
        doc_id = self._generate_doc_id(file_path)
        
        # Preparar documento completo como metadata
        document_data = {
            "file_path": file_path,
            "file_name": Path(file_path).name,
            "file_type": analysis.get("file_type", "unknown"),
            "analyzed_at": datetime.now().isoformat(),
            "analysis_json": json.dumps(analysis, ensure_ascii=False)
        }
        
        # Agregar metadatos de curl si existen (para archivos PHP)
        if curl_metadata:
            document_data.update({
                "curl_command": curl_metadata.get("curl_command", ""),
                "curl_examples": json.dumps(curl_metadata.get("curl_examples", []), ensure_ascii=False),
                "endpoint_url": curl_metadata.get("url_endpoint", ""),
                "http_method": curl_metadata.get("method", "GET"),
                "post_params": json.dumps(curl_metadata.get("post_parameters", []), ensure_ascii=False),
                "get_params": json.dumps(curl_metadata.get("get_parameters", []), ensure_ascii=False),
                "requires_auth": str(curl_metadata.get("requires_auth", False)),
                "has_database": str(curl_metadata.get("has_database", False))
            })
        
        # Crear texto para embedding
        document_text = self._create_document_text(file_path, analysis)
        
        # Guardar en ChromaDB (upsert para actualizar si existe)
        self.collection.upsert(
            ids=[doc_id],
            documents=[document_text],
            metadatas=[document_data]
        )
        
        print(f"✅ Guardado en RAG (ChromaDB): {file_path} (ID: {doc_id})")
        return doc_id
    
    def get_analysis(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Recupera el análisis de un archivo por su ruta.
        
        Args:
            file_path: Ruta del archivo
            
        Returns:
            Análisis completo o None si no existe
        """
        doc_id = self._generate_doc_id(file_path)
        
        try:
            result = self.collection.get(
                ids=[doc_id],
                include=["metadatas"]
            )
            
            if not result['ids']:
                return None
            
            metadata = result['metadatas'][0]
            
            # Construir documento con TODOS los metadatos disponibles
            doc = {
                "document_id": doc_id,
                "file_path": metadata["file_path"],
                "file_name": metadata["file_name"],
                "file_type": metadata["file_type"],
                "analyzed_at": metadata["analyzed_at"],
                "analysis": json.loads(metadata["analysis_json"])
            }
            
            # Agregar metadatos adicionales si existen (curl, diagramas, etc.)
            for key, value in metadata.items():
                if key not in doc and key != "analysis_json":
                    doc[key] = value
            
            return doc
        except Exception as e:
            print(f"⚠️ Error obteniendo análisis: {e}")
            return None
    
    def search_by_keyword(self, keyword: str, max_results: int = 20) -> List[Dict[str, Any]]:
        """
        Busca documentos con búsqueda semántica (usa embeddings).
        ChromaDB hace búsqueda vectorial automáticamente.
        
        Args:
            keyword: Palabra o frase a buscar
            max_results: Máximo de resultados
            
        Returns:
            Lista de documentos que coinciden
        """
        try:
            results = self.collection.query(
                query_texts=[keyword],
                n_results=min(max_results, self.collection.count()),
                include=["metadatas", "distances"]
            )
            
            documents = []
            for i, metadata in enumerate(results['metadatas'][0]):
                doc_id = results['ids'][0][i]
                documents.append({
                    "document_id": doc_id,
                    "file_path": metadata["file_path"],
                    "file_name": metadata["file_name"],
                    "file_type": metadata["file_type"],
                    "analyzed_at": metadata["analyzed_at"],
                    "relevance_score": 1.0 - results['distances'][0][i],  # Convertir distancia a score
                    "analysis": json.loads(metadata["analysis_json"])
                })
            
            return documents
        except Exception as e:
            print(f"⚠️ Error en búsqueda: {e}")
            return []
    
    def search_by_type(self, file_type: str) -> List[Dict[str, Any]]:
        """
        Busca documentos por tipo de archivo.
        
        Args:
            file_type: Tipo de archivo (python, javascript, php, etc.)
            
        Returns:
            Lista de documentos del tipo especificado
        """
        try:
            results = self.collection.get(
                where={"file_type": file_type},
                include=["metadatas"]
            )
            
            documents = []
            for i, metadata in enumerate(results['metadatas']):
                documents.append({
                    "document_id": results['ids'][i],
                    "file_path": metadata["file_path"],
                    "file_name": metadata["file_name"],
                    "file_type": metadata["file_type"],
                    "analyzed_at": metadata["analyzed_at"],
                    "analysis": json.loads(metadata["analysis_json"])
                })
            
            return documents
        except Exception as e:
            print(f"⚠️ Error en búsqueda por tipo: {e}")
            return []
    
    def search_functions(self, function_name: str) -> List[Dict[str, Any]]:
        """
        Busca archivos que contengan una función específica.
        Usa búsqueda semántica de ChromaDB.
        
        Args:
            function_name: Nombre de la función a buscar
            
        Returns:
            Lista de coincidencias con detalles de la función
        """
        # Búsqueda semántica con ChromaDB
        query = f"FUNCTION: {function_name}"
        documents = self.search_by_keyword(query, max_results=50)
        
        results = []
        for doc in documents:
            analysis = doc.get("analysis", {})
            
            # Buscar en funciones
            for func in analysis.get("functions", []):
                if function_name.lower() in func.get("name", "").lower():
                    results.append({
                        "file_path": doc["file_path"],
                        "function": func,
                        "relevance": doc.get("relevance_score", 0.0)
                    })
            
            # Buscar en métodos de clases
            for cls in analysis.get("classes", []):
                for method in cls.get("methods", []):
                    if function_name.lower() in method.get("name", "").lower():
                        results.append({
                            "file_path": doc["file_path"],
                            "class": cls["name"],
                            "method": method,
                            "relevance": doc.get("relevance_score", 0.0)
                        })
        
        # Ordenar por relevancia
        results.sort(key=lambda x: x.get("relevance", 0.0), reverse=True)
        return results[:20]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas del RAG.
        
        Returns:
            Diccionario con estadísticas
        """
        total_docs = self.collection.count()
        
        # Obtener todos los tipos
        all_docs = self.collection.get(include=["metadatas"])
        types_count = {}
        
        for metadata in all_docs['metadatas']:
            file_type = metadata.get("file_type", "unknown")
            types_count[file_type] = types_count.get(file_type, 0) + 1
        
        return {
            "total_documents": total_docs,
            "by_type": types_count,
            "storage_type": "ChromaDB (Vectorial)",
            "search_type": "Semantic Search with Embeddings"
        }
    
    def update_document_metadata(self, file_path: str, new_metadata: Dict[str, Any]) -> bool:
        """
        Actualiza metadatos de un documento existente sin reanalizar.
        Útil para agregar diagramas, notas, curl commands, etc.
        
        Args:
            file_path: Ruta del archivo
            new_metadata: Diccionario con nuevos campos de metadata (se agregan/actualizan)
            
        Returns:
            True si se actualizó, False si hubo error
        """
        doc_id = self._generate_doc_id(file_path)
        
        try:
            # Obtener metadata actual
            result = self.collection.get(
                ids=[doc_id],
                include=["metadatas", "documents"]
            )
            
            if not result['ids']:
                print(f"⚠️ Documento no encontrado: {file_path}")
                return False
            
            # Combinar metadata existente con nueva
            current_metadata = result['metadatas'][0]
            current_metadata.update(new_metadata)
            
            # Actualizar en ChromaDB
            self.collection.update(
                ids=[doc_id],
                metadatas=[current_metadata]
            )
            
            print(f"✅ Metadata actualizada para: {file_path}")
            return True
            
        except Exception as e:
            print(f"⚠️ Error actualizando metadata: {e}")
            return False
    
    def list_all_files(self) -> List[str]:
        """
        Lista todas las rutas de archivos almacenados.
        
        Returns:
            Lista de rutas de archivos
        """
        try:
            results = self.collection.get(include=["metadatas"])
            return [metadata["file_path"] for metadata in results['metadatas']]
        except Exception as e:
            print(f"⚠️ Error listando archivos: {e}")
            return []
    
    def clear_storage(self):
        """Elimina todos los documentos almacenados. ¡USAR CON PRECAUCIÓN!"""
        try:
            self.client.delete_collection(name="code_analysis")
            self.collection = self.client.create_collection(
                name="code_analysis",
                metadata={"description": "Análisis de código con embeddings semánticos"}
            )
            print("🗑️ Almacenamiento RAG (ChromaDB) limpiado")
        except Exception as e:
            print(f"⚠️ Error limpiando storage: {e}")
