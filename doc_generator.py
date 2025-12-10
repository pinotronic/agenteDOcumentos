"""
Generador de documentación automática en Markdown con diagramas UML Mermaid.
"""
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime


class DocumentationGenerator:
    """Genera documentación en Markdown a partir del análisis almacenado en RAG."""
    
    def __init__(self, rag_storage=None):
        """Inicializa el generador con una instancia compartida de RAG."""
        if rag_storage is None:
            from rag_storage_chroma import RAGStorage
            rag_storage = RAGStorage()
        self.rag = rag_storage
    
    def generate_documentation(
        self, 
        directory: str, 
        output_file: str = None,
        include_diagrams: bool = True
    ) -> Dict[str, Any]:
        """
        Genera documentación completa para un directorio.
        
        Args:
            directory: Directorio a documentar
            output_file: Archivo de salida (opcional)
            include_diagrams: Si incluir diagramas UML
            
        Returns:
            Resultado de la operación
        """
        try:
            # Obtener todos los archivos del directorio desde RAG
            all_files = self.rag.list_all_files()
            dir_path = Path(directory).resolve()
            
            # Filtrar archivos del directorio específico
            relevant_files = [
                f for f in all_files 
                if Path(f).resolve().is_relative_to(dir_path)
            ]
            
            if not relevant_files:
                return {
                    "error": f"No se encontraron archivos analizados para el directorio: {directory}",
                    "suggestion": "Primero analiza el directorio con analyze_directory"
                }
            
            # Cargar análisis de cada archivo
            analyses = []
            for file_path in relevant_files:
                doc = self.rag.get_analysis(file_path)
                if doc:
                    analyses.append(doc)
            
            # Generar contenido Markdown
            markdown = self._generate_markdown(
                directory=directory,
                analyses=analyses,
                include_diagrams=include_diagrams
            )
            
            # Determinar archivo de salida
            if not output_file:
                dir_name = Path(directory).name or "documentation"
                output_file = f"{dir_name}_documentation.md"
            
            # Escribir archivo
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(markdown)
            
            return {
                "success": True,
                "output_file": str(output_path),
                "files_documented": len(analyses),
                "size_bytes": output_path.stat().st_size,
                "message": f"Documentación generada exitosamente: {output_path.name}"
            }
        
        except Exception as e:
            return {"error": str(e)}
    
    def _generate_markdown(
        self, 
        directory: str, 
        analyses: List[Dict[str, Any]],
        include_diagrams: bool
    ) -> str:
        """Genera el contenido Markdown completo."""
        
        lines = []
        
        # Encabezado principal
        dir_name = Path(directory).name or "Proyecto"
        lines.append(f"# Documentación del Proyecto: {dir_name}\n")
        lines.append(f"**Generado:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append(f"**Directorio:** `{directory}`\n")
        lines.append(f"**Archivos analizados:** {len(analyses)}\n")
        lines.append("---\n\n")
        
        # Tabla de contenidos
        lines.append("## 📑 Tabla de Contenidos\n\n")
        lines.append("- [Resumen General](#resumen-general)\n")
        
        if include_diagrams:
            lines.append("- [Diagrama de Arquitectura](#diagrama-de-arquitectura)\n")
        
        lines.append("- [Archivos del Proyecto](#archivos-del-proyecto)\n")
        
        # Agrupar por tipo
        by_type = {}
        for analysis in analyses:
            file_type = analysis.get("file_type", "unknown")
            if file_type not in by_type:
                by_type[file_type] = []
            by_type[file_type].append(analysis)
        
        for file_type in sorted(by_type.keys()):
            type_name = file_type.title()
            anchor = file_type.lower().replace(" ", "-")
            lines.append(f"  - [{type_name}](#{anchor})\n")
        
        lines.append("\n---\n\n")
        
        # Resumen General
        lines.append("## 📊 Resumen General\n\n")
        
        stats = self._generate_statistics(analyses)
        lines.append(f"- **Total de archivos:** {stats['total_files']}\n")
        lines.append(f"- **Total de funciones:** {stats['total_functions']}\n")
        lines.append(f"- **Total de clases:** {stats['total_classes']}\n")
        lines.append(f"- **Líneas de código (aprox):** {stats['total_lines']}\n\n")
        
        lines.append("### Distribución por tipo\n\n")
        for file_type, count in sorted(stats['by_type'].items()):
            lines.append(f"- **{file_type.title()}:** {count} archivo(s)\n")
        
        lines.append("\n")
        
        # Diagrama de arquitectura si se solicita
        if include_diagrams:
            lines.append("---\n\n")
            lines.append("## 🏗️ Diagrama de Arquitectura\n\n")
            diagram = self._generate_architecture_diagram(analyses)
            lines.append(diagram)
            lines.append("\n")
        
        # Archivos del proyecto
        lines.append("---\n\n")
        lines.append("## 📁 Archivos del Proyecto\n\n")
        
        # Documentar cada tipo
        for file_type in sorted(by_type.keys()):
            type_name = file_type.title()
            anchor = file_type.lower().replace(" ", "-")
            
            lines.append(f"### {type_name}\n\n")
            
            for analysis in sorted(by_type[file_type], key=lambda x: x.get('file_path', '')):
                file_doc = self._document_file(analysis, include_diagrams)
                lines.append(file_doc)
                lines.append("\n")
        
        return "".join(lines)
    
    def _generate_statistics(self, analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Genera estadísticas del proyecto."""
        stats = {
            'total_files': len(analyses),
            'total_functions': 0,
            'total_classes': 0,
            'total_lines': 0,
            'by_type': {}
        }
        
        for analysis in analyses:
            doc_analysis = analysis.get('analysis', {})
            
            # Contar funciones y clases
            stats['total_functions'] += len(doc_analysis.get('functions', []))
            stats['total_classes'] += len(doc_analysis.get('classes', []))
            
            # Contar por tipo
            file_type = analysis.get('file_type', 'unknown')
            stats['by_type'][file_type] = stats['by_type'].get(file_type, 0) + 1
        
        return stats
    
    def _generate_architecture_diagram(self, analyses: List[Dict[str, Any]]) -> str:
        """Genera un diagrama Mermaid de la arquitectura."""
        lines = ["```mermaid\n"]
        lines.append("graph TD\n")
        lines.append("    %% Diagrama de arquitectura del proyecto\n\n")
        
        # Agrupar por tipo
        by_type = {}
        for analysis in analyses:
            file_type = analysis.get("file_type", "unknown")
            if file_type not in by_type:
                by_type[file_type] = []
            by_type[file_type].append(analysis)
        
        # Crear nodos por tipo
        for idx, (file_type, files) in enumerate(sorted(by_type.items())):
            type_id = f"TYPE{idx}"
            type_name = file_type.title()
            lines.append(f"    {type_id}[📦 {type_name}]\n")
            
            # Mostrar algunos archivos principales
            for file_idx, analysis in enumerate(files[:5]):  # Limitar a 5 por tipo
                file_name = Path(analysis.get('file_path', '')).name
                file_id = f"{type_id}_F{file_idx}"
                lines.append(f"    {type_id} --> {file_id}[{file_name}]\n")
        
        lines.append("```\n\n")
        return "".join(lines)
    
    def _document_file(self, analysis: Dict[str, Any], include_diagrams: bool) -> str:
        """Documenta un archivo individual."""
        lines = []
        
        file_path = analysis.get('file_path', 'unknown')
        file_name = Path(file_path).name
        doc_analysis = analysis.get('analysis', {})
        
        # Encabezado del archivo
        lines.append(f"#### 📄 {file_name}\n\n")
        lines.append(f"**Ruta:** `{file_path}`\n\n")
        
        # Resumen
        summary = doc_analysis.get('summary', 'Sin descripción')
        lines.append(f"**Descripción:** {summary}\n\n")
        
        # Imports
        imports = doc_analysis.get('imports', [])
        if imports:
            lines.append("**Dependencias:**\n")
            for imp in imports[:10]:  # Limitar a 10
                lines.append(f"- `{imp}`\n")
            if len(imports) > 10:
                lines.append(f"- ... y {len(imports) - 10} más\n")
            lines.append("\n")
        
        # Clases
        classes = doc_analysis.get('classes', [])
        if classes:
            lines.append("**Clases:**\n\n")
            
            for cls in classes:
                cls_name = cls.get('name', 'Unknown')
                bases = cls.get('bases', [])
                docstring = cls.get('docstring', '')
                
                lines.append(f"##### `{cls_name}`")
                if bases:
                    lines.append(f" (hereda de: {', '.join(bases)})")
                lines.append("\n\n")
                
                if docstring:
                    lines.append(f"> {docstring}\n\n")
                
                # Métodos de la clase
                methods = cls.get('methods', [])
                if methods:
                    lines.append("**Métodos:**\n\n")
                    for method in methods:
                        if method.get('is_public', True):
                            signature = method.get('signature', method.get('name', ''))
                            method_doc = method.get('docstring', '')
                            lines.append(f"- `{signature}`")
                            if method_doc:
                                lines.append(f" - {method_doc}")
                            lines.append("\n")
                    lines.append("\n")
            
            # Diagrama de clases si se solicita
            if include_diagrams and len(classes) > 0:
                class_diagram = self._generate_class_diagram(classes, file_name)
                lines.append(class_diagram)
                lines.append("\n")
        
        # Funciones
        functions = doc_analysis.get('functions', [])
        if functions:
            lines.append("**Funciones:**\n\n")
            
            for func in functions:
                signature = func.get('signature', func.get('name', ''))
                docstring = func.get('docstring', '')
                params = func.get('parameters', [])
                return_type = func.get('return_type', '')
                
                lines.append(f"##### `{signature}`\n\n")
                
                if docstring:
                    lines.append(f"> {docstring}\n\n")
                
                if params:
                    lines.append("**Parámetros:**\n")
                    for param in params:
                        param_name = param.get('name', '')
                        param_type = param.get('type', 'Any')
                        param_default = param.get('default')
                        
                        line = f"- `{param_name}` ({param_type})"
                        if param_default is not None:
                            line += f" = `{param_default}`"
                        lines.append(line + "\n")
                    lines.append("\n")
                
                if return_type:
                    lines.append(f"**Retorna:** `{return_type}`\n\n")
        
        # Constantes
        constants = doc_analysis.get('constants', [])
        if constants:
            lines.append("**Constantes:**\n\n")
            for const in constants[:10]:  # Limitar a 10
                const_name = const.get('name', '')
                const_value = const.get('value', '')
                lines.append(f"- `{const_name}` = `{const_value}`\n")
            if len(constants) > 10:
                lines.append(f"- ... y {len(constants) - 10} más\n")
            lines.append("\n")
        
        # Complejidad
        complexity = doc_analysis.get('complexity', '')
        if complexity:
            emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(complexity.lower(), "⚪")
            lines.append(f"**Complejidad:** {emoji} {complexity.title()}\n\n")
        
        lines.append("---\n\n")
        
        return "".join(lines)
    
    def _generate_class_diagram(self, classes: List[Dict[str, Any]], file_name: str) -> str:
        """Genera un diagrama de clases en Mermaid."""
        lines = ["```mermaid\n"]
        lines.append("classDiagram\n")
        lines.append(f"    %% Clases de {file_name}\n\n")
        
        for cls in classes:
            cls_name = cls.get('name', 'Unknown')
            
            # Definir clase
            lines.append(f"    class {cls_name} {{\n")
            
            # Métodos (limitar a los primeros 5)
            methods = cls.get('methods', [])[:5]
            for method in methods:
                method_name = method.get('name', '')
                if method.get('is_public', True):
                    lines.append(f"        +{method_name}()\n")
                else:
                    lines.append(f"        -{method_name}()\n")
            
            if len(cls.get('methods', [])) > 5:
                lines.append(f"        ...\n")
            
            lines.append("    }\n\n")
            
            # Herencias
            bases = cls.get('bases', [])
            for base in bases:
                lines.append(f"    {base} <|-- {cls_name}\n")
        
        lines.append("```\n\n")
        return "".join(lines)
