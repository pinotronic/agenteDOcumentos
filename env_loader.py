"""
Cargador centralizado de variables de entorno.
Este módulo DEBE ser importado ANTES de cualquier módulo que use OpenAI.
"""
from dotenv import load_dotenv

# Cargar variables de entorno inmediatamente al importar este módulo
load_dotenv()
