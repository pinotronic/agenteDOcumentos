"""
Sistema de almacenamiento RAG con ChromaDB (Vectorial + Rápido).
Reemplazo del sistema JSON por base de datos vectorial para búsquedas semánticas ultra-rápidas.
"""
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import hashlib

import chromadb
from chromadb.config import Settings
from openai import OpenAI

from config import RAG_STORAGE_PATH, RAG_INDEXER_SYSTEM_PROMPT, ANALYZER_MODEL


class RAGStorage:
    """Gestiona el almacenamiento persistente de análisis de código con ChromaDB."""
    
    def __init__(self, storage_path: str = RAG_STORAGE_PATH):
        """
        Inicializa el sistema de almacenamiento RAG con ChromaDB.
        
        Args:
            storage_path: Directorio donde ChromaDB almacenará los vectores
        
        Nota: Usando EphemeralClient por incompatibilidad de ChromaDB 1.3.6 
        con Python 3.13 en Windows (PanicException en rust bindings).
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        
                # Cliente OpenAI para indexaci¢n inteligente
        self.openai_client = OpenAI()

        # Inicializar cliente Chroma con persistencia opcional y fallback seguro
        client_settings = Settings(anonymized_telemetry=False, allow_reset=True)
        persist_flag = os.environ.get("CHROMA_PERSIST", "1").lower() not in {"0", "false", "no"}
        persist_path = os.environ.get("CHROMA_PERSIST_PATH", str(self.storage_path))
        self.storage_mode = "ephemeral"

        if persist_flag:
            try:
                self.client = chromadb.PersistentClient(path=persist_path, settings=client_settings)
                self.storage_mode = f"persistent:{persist_path}"
                print(f"? Usando ChromaDB persistente en {persist_path}")
            except Exception as e:
                # Fallback a memoria para compatibilidad (bug Chroma 1.3.6 en Win+Python 3.13)
                print(f"??  No se pudo iniciar Chroma persistente ({e}); usando modo memoria compatible")
                self.client = chromadb.EphemeralClient(settings=client_settings)
        else:
            print("??  CHROMA_PERSIST desactivado: modo memoria")
            self.client = chromadb.EphemeralClient(settings=client_settings)

# Crear o obtener colección
        self.collection = self.client.get_or_create_collection(
            name="code_analysis",
            metadata={"description": "Análisis de código con embeddings semánticos"}
        )
        
        print(f"✅ RAG con ChromaDB inicializado: {self.collection.count()} documentos")
    
    def _generate_doc_id(self, file_path: str) -> str:
        """Genera un ID único para un archivo basado en su ruta."""
        return hashlib.md5(file_path.encode()).hexdigest()
    
    def evaluate_for_indexing(self, file_path: str, content: str, analysis: Dict[str, Any]) -> Tuple[bool, Optional[Dict]]:
        """
        Evalúa si un fragmento debe ser indexado usando el agente RAG inteligente.
        
        Args:
            file_path: Ruta del archivo
            content: Contenido del archivo (fragmento relevante)
            analysis: Análisis previo del archivo
            
        Returns:
            Tuple (should_index: bool, indexed_data: Dict or None)
        """
        # Preparar prompt con contexto
        user_prompt = f"""
Archivo: {file_path}
Tipo: {analysis.get('file_type', 'desconocido')}

CONTENIDO:
```
{content[:3000]}  # Limitar a 3000 caracteres
```

ANÁLISIS PREVIO:
{json.dumps(analysis, indent=2, ensure_ascii=False)[:2000]}

Evalúa si este fragmento debe indexarse en la base de conocimiento de SIGSAPAL.
Responde en formato JSON según las instrucciones.
"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model=ANALYZER_MODEL,
                messages=[
                    {"role": "system", "content": RAG_INDEXER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            if result.get("should_index"):
                print(f"✅ Relevante para indexar: {result.get('title', file_path)}")
                return True, result
            else:
                print(f"⏭️  No indexado: {result.get('reason', 'No relevante')}")
                return False, None
                
        except Exception as e:
            print(f"⚠️  Error en evaluación de indexación: {e}")
            # En caso de error, indexar por defecto (comportamiento seguro)
            return True, None
    
    def _create_document_text(self, file_path: str, analysis: Dict[str, Any], indexed_data: Optional[Dict] = None) -> str:
        """
        Crea el texto del documento para embeddings semánticos.
        Combina toda la información relevante para búsqueda.
        
        Args:
            file_path: Ruta del archivo
            analysis: Análisis completo del archivo
            indexed_data: Datos de indexación inteligente (si están disponibles)
        """
        # Si hay datos de indexación inteligente, usarlos primero
        if indexed_data and indexed_data.get("should_index"):
            parts = [
                f"FILE: {Path(file_path).name}",
                f"PATH: {file_path}",
                f"TITLE: {indexed_data.get('title', '')}",
                f"SUMMARY: {indexed_data.get('summary', '')}",
                f"MODULE: {indexed_data.get('metadata', {}).get('module', '')}",
                f"TYPE: {indexed_data.get('metadata', {}).get('source_type', '')}",
            ]
            
            # Agregar recursos
            resources = indexed_data.get('metadata', {}).get('resources', [])
            if resources:
                parts.append(f"RESOURCES: {', '.join(resources)}")
            
            # Agregar conceptos clave
            key_concepts = indexed_data.get('key_concepts', [])
            if key_concepts:
                parts.append(f"KEY_CONCEPTS: {', '.join(key_concepts)}")
            
            # Agregar snippet si existe
            if indexed_data.get('code_snippet'):
                parts.append(f"CODE_SNIPPET: {indexed_data['code_snippet'][:500]}")
                
            return "\n".join(parts)
        
        # Fallback al método anterior si no hay indexación inteligente
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
        
        # Incluir relaciones para consultas semanticas (dependencias, servicios, datos)
        relationships = analysis.get("relationships", {})
        if relationships:
            deps = relationships.get("intra_repo_dependencies") or []
            if deps:
                parts.append(f"REL_DEPENDS_ON: {', '.join(deps[:10])}")

            calls_internal = relationships.get("intra_repo_calls") or []
            if calls_internal:
                parts.append(f"REL_CALLS_INTERNAL: {', '.join([str(x) for x in calls_internal[:10]])}")
            for call in (relationships.get("cross_service_calls") or [])[:10]:
                target = call.get("target", "external")
                desc = call.get("description", "")
                parts.append(f"REL_CALLS: {call.get('type', 'svc')} -> {target} {desc}")
            for ds in (relationships.get("datastores") or [])[:10]:
                parts.append(f"REL_DATASTORE: {ds.get('engine', '')} {ds.get('resource', '')} {ds.get('action', '')}")
            for ev in (relationships.get("events_or_queues") or [])[:10]:
                parts.append(f"REL_EVENT: {ev.get('bus', '')}:{ev.get('topic', '')} {ev.get('direction', '')}")
            for ep in (relationships.get("exposed_endpoints") or [])[:10]:
                parts.append(f"REL_EXPOSES: {ep.get('route', '')} {ep.get('method', '')}")

        return "\n".join(parts)
    
    def save_analysis(self, file_path: str, analysis: Dict[str, Any], curl_metadata: Optional[Dict] = None, 
                     content: Optional[str] = None, use_smart_indexing: bool = True) -> Optional[str]:
        """
        Guarda el análisis de un archivo en el RAG con ChromaDB.
        
        Args:
            file_path: Ruta del archivo analizado
            analysis: Resultado del análisis (JSON del agente analizador)
            curl_metadata: Metadatos de curl para archivos PHP (opcional)
            content: Contenido del archivo para evaluación inteligente (opcional)
            use_smart_indexing: Si True, evalúa antes de guardar (por defecto True)
            
        Returns:
            ID del documento guardado o None si no se indexó
        """
        # Evaluación inteligente si está habilitada y hay contenido
        indexed_data = None
        if use_smart_indexing and content:
            should_index, indexed_data = self.evaluate_for_indexing(file_path, content, analysis)
            if not should_index:
                return None
        
        doc_id = self._generate_doc_id(file_path)
        
        # Preparar documento completo como metadata
        document_data = {
            "file_path": file_path,
            "file_name": Path(file_path).name,
            "file_type": analysis.get("file_type", "unknown"),
            "analyzed_at": datetime.now().isoformat(),
            "analysis_json": json.dumps(analysis, ensure_ascii=False)
        }
        
                # Guardar relaciones entre archivos/servicios si existen
        relationships = analysis.get("relationships") or {}
        if relationships:
            document_data["relationships_json"] = json.dumps(relationships, ensure_ascii=False)
        
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
        
        # Agregar datos de indexación inteligente si existen
        if indexed_data:
            document_data.update({
                "indexed_title": indexed_data.get("title", ""),
                "indexed_summary": indexed_data.get("summary", ""),
                "sigsapal_module": indexed_data.get("metadata", {}).get("module", ""),
                "source_type": indexed_data.get("metadata", {}).get("source_type", ""),
                "resources": json.dumps(indexed_data.get("metadata", {}).get("resources", []), ensure_ascii=False),
                "key_concepts": json.dumps(indexed_data.get("key_concepts", []), ensure_ascii=False)
            })
        
        # Crear texto para embedding (pasando indexed_data)
        document_text = self._create_document_text(file_path, analysis, indexed_data)
        
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
    
    def get_relationship_graph(self, file_filter: Optional[str] = None, include_external: bool = True) -> Dict[str, Any]:
        """
        Construye un grafo ligero de relaciones entre archivos, servicios y datos.

        Args:
            file_filter: Substring para filtrar rutas (ej: carpeta o extension)
            include_external: Si incluye nodos externos (servicios/colas)
        """
        try:
            results = self.collection.get(include=["metadatas"])
        except Exception as e:
            return {"success": False, "error": f"Error obteniendo metadatos: {e}"}

        nodes: Dict[str, Dict[str, Any]] = {}
        edges: List[Dict[str, Any]] = []
        seen_edges = set()

        def add_node(node_id: str, label: str, kind: str):
            if not node_id:
                return
            if file_filter and node_id and file_filter.lower() not in node_id.lower():
                return
            if node_id not in nodes:
                nodes[node_id] = {"id": node_id, "label": label or node_id, "type": kind}

        def infer_node_kind_for_dep(dep: str) -> str:
            """Heurística: si parece path a archivo, tratar como file."""
            if not dep:
                return "module"
            d = dep.strip()
            # Paths típicos en Windows o relativos
            if ":\\" in d or "\\" in d or "/" in d:
                return "file"
            # Extensiones comunes
            lower = d.lower()
            if lower.endswith((".py", ".js", ".ts", ".php", ".java", ".cs")):
                return "file"
            return "module"

        for metadata in results.get("metadatas", []):
            src = metadata.get("file_path")
            if not src:
                continue
            if file_filter and file_filter.lower() not in src.lower():
                continue
            add_node(src, metadata.get("file_name", src), "file")

            relationships = None
            rel_json = metadata.get("relationships_json")
            if rel_json:
                try:
                    relationships = json.loads(rel_json)
                except Exception:
                    relationships = None
            if relationships is None:
                try:
                    relationships = json.loads(metadata.get("analysis_json", "{}"))
                except Exception:
                    relationships = {}
                else:
                    relationships = relationships.get("relationships", {}) if isinstance(relationships, dict) else {}

            if not relationships:
                continue

            # Dependencias internas (por nombre de modulo/ruta)
            for dep in relationships.get("intra_repo_dependencies", []) or []:
                target = dep.strip()
                kind = infer_node_kind_for_dep(target)
                label = target.split("/")[-1].split("\\")[-1] if kind == "file" else target
                add_node(target, label, kind)
                edge_key = (src, target, "depends_on")
                if edge_key not in seen_edges:
                    edges.append({"from": src, "to": target, "type": "depends_on"})
                    seen_edges.add(edge_key)

            # Llamadas internas (comunicación) archivo -> archivo
            for called in relationships.get("intra_repo_calls", []) or []:
                target = str(called).strip()
                if not target:
                    continue
                kind = infer_node_kind_for_dep(target)
                label = target.split("/")[-1].split("\\")[-1] if kind == "file" else target
                add_node(target, label, kind)
                edge_key = (src, target, "calls")
                if edge_key not in seen_edges:
                    edges.append({"from": src, "to": target, "type": "calls"})
                    seen_edges.add(edge_key)

            # Servicios externos
            if include_external:
                for call in relationships.get("cross_service_calls", []) or []:
                    target = call.get("target") or call.get("host") or "external_service"
                    target = target.strip()
                    add_node(target, target, "service")
                    edge_key = (src, target, "calls_service")
                    if edge_key not in seen_edges:
                        edges.append({"from": src, "to": target, "type": "calls_service", "method": call.get("method")})
                        seen_edges.add(edge_key)

            # Data stores
            for ds in relationships.get("datastores", []) or []:
                target = ds.get("resource") or ds.get("engine") or "datastore"
                target = target.strip()
                label = f"{ds.get('engine', '')} {target}".strip()
                add_node(target, label, "datastore")
                edge_key = (src, target, "uses_datastore")
                if edge_key not in seen_edges:
                    edges.append({"from": src, "to": target, "type": "uses_datastore", "action": ds.get("action")})
                    seen_edges.add(edge_key)

            # Eventos/colas
            if include_external:
                for ev in relationships.get("events_or_queues", []) or []:
                    target = ev.get("topic") or ev.get("bus") or "event_bus"
                    target = target.strip()
                    add_node(target, target, "event")
                    edge_key = (src, target, ev.get("direction", "event"))
                    if edge_key not in seen_edges:
                        edges.append({"from": src, "to": target, "type": ev.get("direction", "event")})
                        seen_edges.add(edge_key)

            # Endpoints expuestos
            for ep in relationships.get("exposed_endpoints", []) or []:
                route = ep.get("route") or "endpoint"
                node_id = f"{src}:{route}"
                add_node(node_id, route, "endpoint")
                edge_key = (src, node_id, "exposes")
                if edge_key not in seen_edges:
                    edges.append({"from": src, "to": node_id, "type": "exposes", "method": ep.get("method")})
                    seen_edges.add(edge_key)

        return {
            "success": True,
            "nodes": list(nodes.values()),
            "edges": edges,
            "stats": {"nodes": len(nodes), "edges": len(edges)},
            "storage_mode": getattr(self, "storage_mode", "ephemeral")
        }

    def get_file_trace(self, file_path: str, include_external: bool = False) -> Dict[str, Any]:
        """Retorna trazabilidad de comunicación/dependencia para un archivo.

        Incluye:
        - Outgoing: edges desde el archivo hacia otros (depends_on, calls, etc.)
        - Incoming: edges desde otros hacia el archivo
        - Detalles del documento (unresolved refs) si están presentes en relationships
        """
        try:
            target_abs = str(Path(file_path).resolve())
        except Exception:
            target_abs = file_path

        target_norm = target_abs.lower()

        graph = self.get_relationship_graph(file_filter=None, include_external=include_external)
        if not graph.get("success"):
            return graph

        edges = graph.get("edges") or []

        outgoing = [e for e in edges if str(e.get("from", "")).lower() == target_norm]
        incoming = [e for e in edges if str(e.get("to", "")).lower() == target_norm]

        # Fallback: si no matcheó por path completo, intentar por sufijo (nombre de archivo)
        if not outgoing and not incoming:
            suffix = Path(target_abs).name.lower()
            if suffix:
                candidates = [n.get("id") for n in (graph.get("nodes") or []) if str(n.get("id", "")).lower().endswith(suffix)]
                candidates = list(dict.fromkeys([c for c in candidates if c]))
                if len(candidates) == 1:
                    only = candidates[0]
                    target_abs = only
                    target_norm = only.lower()
                    outgoing = [e for e in edges if str(e.get("from", "")).lower() == target_norm]
                    incoming = [e for e in edges if str(e.get("to", "")).lower() == target_norm]

        def group_by_type(edge_list):
            grouped: Dict[str, List[Dict[str, Any]]] = {}
            for e in edge_list:
                t = e.get("type", "unknown")
                grouped.setdefault(t, []).append(e)
            return grouped

        outgoing_grouped = group_by_type(outgoing)
        incoming_grouped = group_by_type(incoming)

        # Extraer relationships detalladas del documento (si existe)
        details: Dict[str, Any] = {}
        doc_id = self._generate_doc_id(target_abs)
        try:
            result = self.collection.get(ids=[doc_id], include=["metadatas"])
            if result.get("ids"):
                metadata = result.get("metadatas", [{}])[0] or {}
                rel = None
                rel_json = metadata.get("relationships_json")
                if rel_json:
                    try:
                        rel = json.loads(rel_json)
                    except Exception:
                        rel = None
                if rel is None:
                    try:
                        analysis_obj = json.loads(metadata.get("analysis_json", "{}"))
                        if isinstance(analysis_obj, dict):
                            rel = analysis_obj.get("relationships") or {}
                    except Exception:
                        rel = {}

                if isinstance(rel, dict):
                    for k in [
                        "intra_repo_dependencies_unresolved",
                        "intra_repo_calls_unresolved",
                        "intra_repo_dependencies_modules",
                        "intra_repo_dependencies_trace_error",
                    ]:
                        if k in rel:
                            details[k] = rel.get(k)
        except Exception:
            pass

        return {
            "success": True,
            "target": target_abs,
            "outgoing": outgoing_grouped,
            "incoming": incoming_grouped,
            "stats": {
                "outgoing_edges": len(outgoing),
                "incoming_edges": len(incoming),
            },
            "details": details,
            "storage_mode": getattr(self, "storage_mode", "ephemeral"),
        }

    def get_trace_hotspots(
        self,
        scope: Optional[str] = None,
        include_external: bool = False,
        top_n: int = 20,
    ) -> Dict[str, Any]:
        """Rankings de trazabilidad (hotspots) para priorizar análisis.

        Args:
            scope: substring para filtrar archivos (por ruta/carpeta/nombre). None = todo.
            include_external: incluye edges a servicios/eventos si True.
            top_n: tamaño máximo de cada ranking.

        Returns:
            Diccionario con rankings:
            - top_outgoing_calls: archivos que más llaman a otros
            - top_incoming_calls: archivos más llamados por otros
            - top_outgoing_depends: archivos con más dependencias
            - top_incoming_depends: archivos más dependidos
        """
        graph = self.get_relationship_graph(file_filter=None, include_external=include_external)
        if not graph.get("success"):
            return graph

        edges = graph.get("edges") or []
        nodes = graph.get("nodes") or []

        scope_l = (scope or "").lower().strip()

        def norm(s: str) -> str:
            return (s or "").lower().replace("\\", "/")

        def in_scope(node_id: str) -> bool:
            if not scope_l:
                return True
            return norm(scope_l) in norm(node_id or "")

        # Solo considerar nodos tipo file y dentro de scope
        file_nodes = {n.get("id") for n in nodes if n.get("type") == "file" and in_scope(n.get("id", ""))}

        # Contadores por archivo
        out_calls: Dict[str, int] = {}
        in_calls: Dict[str, int] = {}
        out_dep: Dict[str, int] = {}
        in_dep: Dict[str, int] = {}

        def bump(d: Dict[str, int], k: str):
            d[k] = d.get(k, 0) + 1

        for e in edges:
            src = e.get("from")
            dst = e.get("to")
            et = e.get("type")
            if not isinstance(src, str) or not isinstance(dst, str):
                continue

            # Filtrar a archivos (y scope)
            if src not in file_nodes:
                continue

            if et == "calls":
                bump(out_calls, src)
                if dst in file_nodes:
                    bump(in_calls, dst)
            elif et == "depends_on":
                bump(out_dep, src)
                if dst in file_nodes:
                    bump(in_dep, dst)

        def top_items(counter: Dict[str, int]) -> List[Dict[str, Any]]:
            items = sorted(counter.items(), key=lambda kv: kv[1], reverse=True)
            out: List[Dict[str, Any]] = []
            for k, v in items[: max(1, int(top_n))]:
                out.append({"file": k, "count": v})
            return out

        return {
            "success": True,
            "scope": scope,
            "include_external": include_external,
            "top_n": top_n,
            "top_outgoing_calls": top_items(out_calls),
            "top_incoming_calls": top_items(in_calls),
            "top_outgoing_depends": top_items(out_dep),
            "top_incoming_depends": top_items(in_dep),
            "storage_mode": getattr(self, "storage_mode", "ephemeral"),
        }

    def generate_trace_report_markdown(
        self,
        scope: Optional[str] = None,
        include_external: bool = False,
        top_n: int = 20,
        per_file_edges_preview: int = 10,
    ) -> str:
        """Genera un reporte Markdown de trazabilidad (hotspots + previews).

        Nota: el reporte se basa en los datos guardados en el RAG; si faltan archivos,
        ejecuta analyze_directory o re-analiza los módulos deseados.
        """
        hotspots = self.get_trace_hotspots(scope=scope, include_external=include_external, top_n=top_n)
        if not hotspots.get("success"):
            return f"# Traceability Report\n\nError: {hotspots.get('error', 'unknown')}\n"

        now = datetime.now().isoformat(timespec="seconds")
        lines: List[str] = []
        lines.append(f"# Traceability Report\n")
        lines.append(f"- Generated: {now}\n")
        lines.append(f"- Scope: {scope or 'ALL'}\n")
        lines.append(f"- Include external: {include_external}\n")
        lines.append(f"- Storage mode: {hotspots.get('storage_mode', 'unknown')}\n\n")

        def section(title: str, items: List[Dict[str, Any]]):
            lines.append(f"## {title}\n")
            if not items:
                lines.append("(no data)\n\n")
                return
            for it in items:
                lines.append(f"- {it.get('count', 0)} — {it.get('file', '')}\n")
            lines.append("\n")

        section("Top Outgoing Calls (Top Talkers)", hotspots.get("top_outgoing_calls") or [])
        section("Top Incoming Calls (Most Called)", hotspots.get("top_incoming_calls") or [])
        section("Top Outgoing Dependencies", hotspots.get("top_outgoing_depends") or [])
        section("Top Incoming Dependencies", hotspots.get("top_incoming_depends") or [])

        # Previews por archivo: tomar los más relevantes (unir outgoing_calls + incoming_calls)
        candidates = []
        for it in (hotspots.get("top_outgoing_calls") or []):
            candidates.append(it.get("file"))
        for it in (hotspots.get("top_incoming_calls") or []):
            candidates.append(it.get("file"))
        # de-dup
        candidates = list(dict.fromkeys([c for c in candidates if isinstance(c, str) and c]))

        if candidates:
            lines.append("## File Trace Previews\n")
            for fp in candidates[: max(1, min(10, len(candidates)))]:
                trace = self.get_file_trace(fp, include_external=include_external)
                if not trace.get("success"):
                    continue
                lines.append(f"### {trace.get('target', fp)}\n")
                stats = trace.get("stats") or {}
                lines.append(f"- Outgoing edges: {stats.get('outgoing_edges', 0)}\n")
                lines.append(f"- Incoming edges: {stats.get('incoming_edges', 0)}\n")

                outgoing = trace.get("outgoing") or {}
                incoming = trace.get("incoming") or {}

                def edge_block(label: str, edge_list: List[Dict[str, Any]]):
                    lines.append(f"\n**{label}**\n")
                    if not edge_list:
                        lines.append("- (none)\n")
                        return
                    for e in edge_list[: max(1, int(per_file_edges_preview))]:
                        lines.append(f"- {e.get('type')} -> {e.get('to') if label.startswith('Outgoing') else e.get('from')}\n")

                edge_block("Outgoing calls", outgoing.get("calls") or [])
                edge_block("Outgoing depends_on", outgoing.get("depends_on") or [])
                edge_block("Incoming calls", incoming.get("calls") or [])
                edge_block("Incoming depends_on", incoming.get("depends_on") or [])

                details = trace.get("details") or {}
                if details:
                    lines.append("\n**Details**\n")
                    for k, v in details.items():
                        lines.append(f"- {k}: {v}\n")
                lines.append("\n")

        return "".join(lines)

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
            "search_type": "Semantic Search with Embeddings",
            "storage_mode": getattr(self, "storage_mode", "ephemeral")
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
