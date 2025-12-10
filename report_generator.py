"""
Generador de reportes y dashboards.
Crea reportes HTML, análisis de deuda técnica y exportaciones.
"""
import env_loader  # Cargar .env PRIMERO
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from openai import OpenAI

from config import ANALYZER_MODEL


class ReportGenerator:
    """Genera reportes y dashboards a partir del análisis."""
    
    def __init__(self, rag_storage=None):
        """Inicializa el generador con una instancia compartida de RAG."""
        self.client = OpenAI()
        self.model = ANALYZER_MODEL
        if rag_storage is None:
            from rag_storage_chroma import RAGStorage
            rag_storage = RAGStorage()
        self.rag = rag_storage
    
    def generate_html_dashboard(self, directory: str, output_file: str = None) -> Dict[str, Any]:
        """
        Genera un dashboard HTML interactivo del proyecto.
        
        Args:
            directory: Directorio del proyecto
            output_file: Archivo HTML de salida
            
        Returns:
            Resultado de la generación
        """
        print(f"📊 Generando dashboard HTML para: {directory}")
        
        try:
            # Obtener estadísticas del RAG
            stats = self.rag.get_statistics()
            
            if stats.get("total_documents", 0) == 0:
                return {"error": "No hay archivos analizados. Primero analiza el directorio."}
            
            # Generar HTML
            html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - {Path(directory).name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #333; }}
        .card {{ background: white; padding: 20px; margin: 10px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }}
        .stat {{ background: #4CAF50; color: white; padding: 15px; border-radius: 5px; text-align: center; }}
        .stat h3 {{ margin: 0; font-size: 32px; }}
        .stat p {{ margin: 5px 0 0 0; font-size: 14px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #4CAF50; color: white; }}
        .timestamp {{ color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Dashboard del Proyecto</h1>
        <p class="timestamp">Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <div class="card">
            <h2>📈 Estadísticas Generales</h2>
            <div class="stats">
                <div class="stat">
                    <h3>{stats['total_documents']}</h3>
                    <p>Archivos Analizados</p>
                </div>
                <div class="stat" style="background: #2196F3;">
                    <h3>{sum(stats.get('by_type', {}).values())}</h3>
                    <p>Total de Tipos</p>
                </div>
            </div>
        </div>
        
        <div class="card">
            <h2>📁 Distribución por Tipo</h2>
            <table>
                <tr>
                    <th>Tipo</th>
                    <th>Cantidad</th>
                </tr>
                {"".join(f"<tr><td>{t.title()}</td><td>{c}</td></tr>" for t, c in stats.get('by_type', {}).items())}
            </table>
        </div>
        
        <div class="card">
            <h2>ℹ️ Información del Sistema</h2>
            <p><strong>Directorio:</strong> {directory}</p>
            <p><strong>Creado:</strong> {stats.get('created', 'N/A')}</p>
            <p><strong>Última actualización:</strong> {stats.get('last_updated', 'N/A')}</p>
        </div>
    </div>
</body>
</html>"""
            
            # Guardar archivo
            if not output_file:
                output_file = f"{Path(directory).name}_dashboard.html"
            
            output_path = Path(output_file)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            return {
                "success": True,
                "output_file": str(output_path),
                "size_bytes": output_path.stat().st_size,
                "message": f"Dashboard generado: {output_path.name}"
            }
        
        except Exception as e:
            return {"error": str(e)}
    
    def technical_debt_report(self, directory: str) -> Dict[str, Any]:
        """
        Genera reporte de deuda técnica del proyecto.
        
        Args:
            directory: Directorio del proyecto
            
        Returns:
            Reporte de deuda técnica
        """
        print(f"⚠️ Analizando deuda técnica en: {directory}")
        
        # Obtener todos los archivos del RAG
        files = self.rag.list_all_files()
        dir_files = [f for f in files if directory in f]
        
        if not dir_files:
            return {"error": "No hay archivos analizados en este directorio"}
        
        # Analizar con LLM
        analyses = [self.rag.get_analysis(f) for f in dir_files[:20]]  # Limitar a 20
        
        prompt = f"""Analiza estos archivos y genera un reporte de deuda técnica:

{json.dumps(analyses, indent=2)[:10000]}

Identifica:
1. Código duplicado
2. Funciones muy largas o complejas
3. Falta de documentación
4. Code smells
5. Problemas de arquitectura
6. Mejoras de seguridad

Responde en formato JSON:
{{
  "overall_score": "A|B|C|D|F",
  "technical_debt_level": "low|medium|high|critical",
  "issues": [
    {{
      "category": "duplicación|complejidad|docs|seguridad",
      "severity": "high|medium|low",
      "file": "archivo",
      "description": "descripción",
      "recommendation": "cómo arreglarlo"
    }}
  ],
  "summary": "Resumen ejecutivo",
  "priorities": ["prioridad1", "prioridad2"],
  "estimated_effort": "horas de esfuerzo estimadas"
}}
"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Eres un arquitecto de software experto. Identificas deuda técnica y proporcionas recomendaciones accionables."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            result["directory"] = directory
            result["files_analyzed"] = len(dir_files)
            result["success"] = True
            
            print(f"✅ Deuda técnica: {result['technical_debt_level']}")
            return result
        
        except Exception as e:
            return {"error": str(e)}
