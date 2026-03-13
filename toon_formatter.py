"""
TOON Formatter - Token-Oriented Object Notation
Convierte JSON a formato TOON para reducir tokens ~40-70%
Basado en: https://github.com/toon-format/toon
"""

import json
from typing import Any, List, Dict


def to_toon(data: Any, indent: int = 0) -> str:
    """
    Convierte datos Python/JSON a formato TOON.
    
    Args:
        data: Dato a convertir (dict, list, primitivo)
        indent: Nivel de indentación actual
    
    Returns:
        String en formato TOON
    """
    if data is None:
        return "null"
    
    if isinstance(data, bool):
        return "true" if data else "false"
    
    if isinstance(data, (int, float)):
        return str(data)
    
    if isinstance(data, str):
        # Strings simples sin comillas si no tienen espacios/caracteres especiales
        if _is_simple_string(data):
            return data
        # Strings con espacios o caracteres especiales entre comillas
        return f'"{_escape_string(data)}"'
    
    if isinstance(data, list):
        return _format_array(data, indent)
    
    if isinstance(data, dict):
        return _format_object(data, indent)
    
    return str(data)


def _is_simple_string(s: str) -> bool:
    """Verifica si un string es simple (sin espacios ni caracteres especiales)."""
    if not s or ' ' in s or '\n' in s or '\t' in s:
        return False
    special_chars = ['"', "'", ':', ',', '[', ']', '{', '}']
    return not any(char in s for char in special_chars)


def _escape_string(s: str) -> str:
    """Escapa caracteres especiales en strings."""
    return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\t', '\\t')


def _format_object(obj: Dict, indent: int) -> str:
    """Formatea un diccionario en estilo YAML-like."""
    if not obj:
        return "{}"
    
    spaces = "  " * indent
    lines = []
    
    for key, value in obj.items():
        # Formatear el key
        if _is_simple_string(str(key)):
            formatted_key = str(key)
        else:
            formatted_key = f'"{key}"'
        
        # Formatear el value
        if isinstance(value, (dict, list)) and value:
            # Objetos/arrays anidados van en nueva línea
            formatted_value = to_toon(value, indent + 1)
            if isinstance(value, dict):
                lines.append(f"{spaces}{formatted_key}:")
                for line in formatted_value.split('\n'):
                    if line.strip():
                        lines.append(f"  {line}")
            else:
                lines.append(f"{spaces}{formatted_key}: {formatted_value}")
        else:
            # Valores primitivos en la misma línea
            formatted_value = to_toon(value, indent)
            lines.append(f"{spaces}{formatted_key}: {formatted_value}")
    
    return '\n'.join(lines)


def _format_array(arr: List, indent: int) -> str:
    """
    Formatea un array. Si contiene objetos homogéneos, usa formato tabular.
    Si contiene primitivos o es heterogéneo, usa formato lista.
    """
    if not arr:
        return "[]"
    
    # Verificar si es array de objetos homogéneos (candidato para tabla)
    if _is_homogeneous_object_array(arr):
        return _format_table(arr, indent)
    
    # Array de primitivos o heterogéneo
    if all(isinstance(item, (str, int, float, bool, type(None))) for item in arr):
        # Array simple en una línea
        formatted_items = [to_toon(item, 0) for item in arr]
        return f"[{', '.join(formatted_items)}]"
    
    # Array de objetos no homogéneos o mixto
    spaces = "  " * indent
    lines = ["["]
    for i, item in enumerate(arr):
        formatted_item = to_toon(item, indent + 1)
        comma = "," if i < len(arr) - 1 else ""
        if isinstance(item, (dict, list)) and item:
            # Items complejos en múltiples líneas
            for j, line in enumerate(formatted_item.split('\n')):
                if j == 0:
                    lines.append(f"{spaces}  {line}{comma}")
                else:
                    lines.append(f"{spaces}  {line}")
        else:
            lines.append(f"{spaces}  {formatted_item}{comma}")
    lines.append(f"{spaces}]")
    return '\n'.join(lines)


def _is_homogeneous_object_array(arr: List) -> bool:
    """Verifica si un array contiene objetos con las mismas keys."""
    if not arr or not all(isinstance(item, dict) for item in arr):
        return False
    
    if len(arr) < 2:
        return False
    
    # Obtener keys del primer objeto
    first_keys = set(arr[0].keys())
    
    # Verificar que todos tengan las mismas keys
    return all(set(item.keys()) == first_keys for item in arr[1:])


def _format_table(arr: List[Dict], indent: int) -> str:
    """
    Formatea un array de objetos homogéneos como tabla.
    Formato:
    [key1, key2, key3]
    [val1, val2, val3]
    [val1, val2, val3]
    """
    if not arr:
        return "[]"
    
    spaces = "  " * indent
    keys = list(arr[0].keys())
    
    lines = []
    
    # Header con keys
    header_items = [f'"{key}"' if not _is_simple_string(key) else key for key in keys]
    lines.append(f"{spaces}[{', '.join(header_items)}]")
    
    # Filas de datos
    for obj in arr:
        row_items = [to_toon(obj.get(key), 0) for key in keys]
        lines.append(f"{spaces}[{', '.join(row_items)}]")
    
    return '\n'.join(lines)


def format_tool_result(result: Any, tool_name: str = None) -> str:
    """
    Formatea el resultado de una herramienta en formato TOON.
    
    Args:
        result: Resultado de la herramienta (cualquier tipo)
        tool_name: Nombre de la herramienta (opcional, para contexto)
    
    Returns:
        String formateado en TOON
    """
    toon_output = to_toon(result)
    
    if tool_name:
        return f"=== {tool_name} ===\n{toon_output}"
    
    return toon_output


def estimate_token_savings(json_str: str) -> Dict[str, Any]:
    """
    Estima el ahorro de tokens al convertir de JSON a TOON.
    
    Args:
        json_str: String JSON original
    
    Returns:
        Dict con estadísticas de ahorro
    """
    try:
        data = json.loads(json_str)
        toon_str = to_toon(data)
        
        json_tokens = len(json_str) // 4  # Aproximación: 1 token ≈ 4 chars
        toon_tokens = len(toon_str) // 4
        
        savings_pct = ((json_tokens - toon_tokens) / json_tokens * 100) if json_tokens > 0 else 0
        
        return {
            "json_length": len(json_str),
            "toon_length": len(toon_str),
            "json_tokens_approx": json_tokens,
            "toon_tokens_approx": toon_tokens,
            "savings_percent": round(savings_pct, 1),
            "tokens_saved": json_tokens - toon_tokens
        }
    except Exception as e:
        return {"error": str(e)}


# Ejemplo de uso
if __name__ == "__main__":
    # Ejemplo 1: Objeto simple
    data1 = {
        "name": "agent.py",
        "type": "python",
        "functions": 5,
        "classes": 2
    }
    print("=== Objeto Simple ===")
    print(to_toon(data1))
    print()
    
    # Ejemplo 2: Array de objetos (tabla)
    data2 = [
        {"file": "agent.py", "lines": 450, "complexity": "high"},
        {"file": "tools.py", "lines": 320, "complexity": "medium"},
        {"file": "config.py", "lines": 120, "complexity": "low"}
    ]
    print("=== Array de Objetos (Tabla) ===")
    print(to_toon(data2))
    print()
    
    # Ejemplo 3: Objeto anidado complejo
    data3 = {
        "summary": "Sistema multi-agente",
        "stats": {
            "files": 15,
            "functions": 87,
            "classes": 23
        },
        "files": [
            {"name": "agent.py", "size": 15000},
            {"name": "tools.py", "size": 12000}
        ]
    }
    print("=== Objeto Anidado ===")
    print(to_toon(data3))
    print()
    
    # Comparación de tokens
    json_str = json.dumps(data3, indent=2)
    stats = estimate_token_savings(json_str)
    print("=== Ahorro de Tokens ===")
    print(f"JSON: {stats['json_length']} chars ≈ {stats['json_tokens_approx']} tokens")
    print(f"TOON: {stats['toon_length']} chars ≈ {stats['toon_tokens_approx']} tokens")
    print(f"Ahorro: {stats['savings_percent']}% ({stats['tokens_saved']} tokens)")
