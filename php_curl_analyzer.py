"""
Analizador de archivos PHP para generar comandos curl de prueba.
Extrae parámetros POST/GET y genera comandos curl válidos.
"""
import re
from typing import Dict, List, Optional, Tuple
from pathlib import Path


class PHPCurlAnalyzer:
    """Analiza archivos PHP y genera comandos curl para pruebas."""
    
    def __init__(self, base_url: str = "http://172.16.12.178"):
        """
        Inicializa el analizador.
        
        Args:
            base_url: URL base del servidor (default: http://172.16.12.178)
        """
        self.base_url = base_url
    
    def analyze_php_file(self, file_path: str, content: str) -> Dict:
        """
        Analiza un archivo PHP y extrae información para generar curl.
        
        Args:
            file_path: Ruta del archivo PHP
            content: Contenido del archivo
        
        Returns:
            Dict con url_endpoint, method, parameters, curl_command
        """
        # Extraer parámetros POST
        post_params = self._extract_post_params(content)
        
        # Extraer parámetros GET
        get_params = self._extract_get_params(content)
        
        # Determinar método HTTP
        method = "POST" if post_params else "GET"
        
        # Construir URL del endpoint
        url_endpoint = self._build_endpoint_url(file_path)
        
        # Generar comando curl
        curl_command = self._generate_curl_command(
            url_endpoint, 
            method, 
            post_params, 
            get_params
        )
        
        # Generar ejemplos con valores de prueba
        curl_examples = self._generate_curl_examples(
            url_endpoint,
            method,
            post_params,
            get_params
        )
        
        return {
            "url_endpoint": url_endpoint,
            "method": method,
            "post_parameters": post_params,
            "get_parameters": get_params,
            "curl_command": curl_command,
            "curl_examples": curl_examples,
            "requires_auth": self._check_auth_required(content),
            "has_database": self._check_database_usage(content)
        }
    
    def _extract_post_params(self, content: str) -> List[Dict[str, str]]:
        """Extrae parámetros POST del archivo PHP."""
        params = []
        
        # Patrón para $_POST['parametro']
        post_pattern = r'\$_POST\s*\[\s*[\'"]([^\'"]+)[\'"]\s*\]'
        matches = re.finditer(post_pattern, content)
        
        for match in matches:
            param_name = match.group(1)
            
            # Intentar detectar tipo de dato
            param_type = self._detect_param_type(content, param_name)
            
            # Buscar valor por defecto
            default_value = self._find_default_value(content, param_name)
            
            params.append({
                "name": param_name,
                "type": param_type,
                "default": default_value,
                "required": self._is_required(content, param_name)
            })
        
        # Eliminar duplicados
        seen = set()
        unique_params = []
        for param in params:
            if param["name"] not in seen:
                seen.add(param["name"])
                unique_params.append(param)
        
        return unique_params
    
    def _extract_get_params(self, content: str) -> List[Dict[str, str]]:
        """Extrae parámetros GET del archivo PHP."""
        params = []
        
        # Patrón para $_GET['parametro']
        get_pattern = r'\$_GET\s*\[\s*[\'"]([^\'"]+)[\'"]\s*\]'
        matches = re.finditer(get_pattern, content)
        
        for match in matches:
            param_name = match.group(1)
            param_type = self._detect_param_type(content, param_name)
            default_value = self._find_default_value(content, param_name)
            
            params.append({
                "name": param_name,
                "type": param_type,
                "default": default_value,
                "required": self._is_required(content, param_name)
            })
        
        # Eliminar duplicados
        seen = set()
        unique_params = []
        for param in params:
            if param["name"] not in seen:
                seen.add(param["name"])
                unique_params.append(param)
        
        return unique_params
    
    def _detect_param_type(self, content: str, param_name: str) -> str:
        """Detecta el tipo de dato del parámetro."""
        # Buscar conversiones explícitas
        if re.search(rf'intval\s*\(\s*\$_(?:POST|GET)\s*\[\s*[\'"]?{param_name}', content):
            return "integer"
        if re.search(rf'floatval\s*\(\s*\$_(?:POST|GET)\s*\[\s*[\'"]?{param_name}', content):
            return "float"
        if re.search(rf'strval\s*\(\s*\$_(?:POST|GET)\s*\[\s*[\'"]?{param_name}', content):
            return "string"
        
        # Detectar por nombre común
        if any(keyword in param_name.lower() for keyword in ['fecha', 'date']):
            return "date"
        if any(keyword in param_name.lower() for keyword in ['id', 'numero', 'count']):
            return "integer"
        if any(keyword in param_name.lower() for keyword in ['lat', 'lon', 'lng', 'coord']):
            return "float"
        
        return "string"
    
    def _find_default_value(self, content: str, param_name: str) -> Optional[str]:
        """Busca valor por defecto o ejemplo en el código."""
        # Patrón para encontrar valores por defecto
        default_pattern = rf'\$_(?:POST|GET)\s*\[\s*[\'"]?{param_name}[\'"]?\s*\]\s*\?\?\s*[\'"]?([^\'";\n]+)'
        match = re.search(default_pattern, content)
        if match:
            return match.group(1).strip()
        
        # Buscar en comentarios con ejemplo
        comment_pattern = rf'//.*{param_name}.*[:=]\s*[\'"]?([^\'";\n]+)'
        match = re.search(comment_pattern, content, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        return None
    
    def _is_required(self, content: str, param_name: str) -> bool:
        """Determina si un parámetro es requerido."""
        # Buscar validaciones que indican requerido
        required_patterns = [
            rf'empty\s*\(\s*\$_(?:POST|GET)\s*\[\s*[\'"]?{param_name}',
            rf'isset\s*\(\s*\$_(?:POST|GET)\s*\[\s*[\'"]?{param_name}',
            rf'if\s*\(\s*!\s*\$_(?:POST|GET)\s*\[\s*[\'"]?{param_name}'
        ]
        
        for pattern in required_patterns:
            if re.search(pattern, content):
                return True
        
        return False
    
    def _build_endpoint_url(self, file_path: str) -> str:
        """Construye la URL del endpoint a partir de la ruta del archivo."""
        # Convertir path de Windows a URL
        path = Path(file_path)
        
        # Extraer la parte después de /htdocs/
        if 'htdocs' in path.parts:
            idx = path.parts.index('htdocs')
            relative_parts = path.parts[idx+1:]
            relative_path = '/'.join(relative_parts)
        else:
            relative_path = path.name
        
        # Reemplazar backslashes por forward slashes
        relative_path = relative_path.replace('\\', '/')
        
        # Construir URL completa
        url = f"{self.base_url}/geoproceso/{relative_path}"
        
        return url
    
    def _generate_curl_command(
        self, 
        url: str, 
        method: str, 
        post_params: List[Dict], 
        get_params: List[Dict]
    ) -> str:
        """Genera comando curl básico."""
        if method == "POST":
            # Construir datos POST
            data_parts = []
            for param in post_params:
                example_value = self._get_example_value(param)
                data_parts.append(f'{param["name"]}={example_value}')
            
            data_string = "&".join(data_parts)
            
            return f'curl.exe -X POST -d "{data_string}" {url}'
        else:
            # GET con query string
            if get_params:
                query_parts = []
                for param in get_params:
                    example_value = self._get_example_value(param)
                    query_parts.append(f'{param["name"]}={example_value}')
                
                query_string = "&".join(query_parts)
                return f'curl.exe -X GET "{url}?{query_string}"'
            else:
                return f'curl.exe -X GET {url}'
    
    def _generate_curl_examples(
        self,
        url: str,
        method: str,
        post_params: List[Dict],
        get_params: List[Dict]
    ) -> List[str]:
        """Genera múltiples ejemplos de comandos curl con diferentes valores."""
        examples = []
        
        if method == "POST" and post_params:
            # Ejemplo 1: Con valores de prueba básicos
            data_parts = [f'{p["name"]}={self._get_example_value(p)}' for p in post_params]
            examples.append(f'curl.exe -X POST -d "{" ".join(data_parts)}" {url}')
            
            # Ejemplo 2: Solo parámetros requeridos
            required_params = [p for p in post_params if p.get("required")]
            if required_params:
                data_parts = [f'{p["name"]}={self._get_example_value(p)}' for p in required_params]
                examples.append(f'curl.exe -X POST -d "{" ".join(data_parts)}" {url}')
            
            # Ejemplo 3: Con valores alternativos
            if post_params:
                data_parts = [f'{p["name"]}={self._get_alternative_value(p)}' for p in post_params]
                examples.append(f'curl.exe -X POST -d "{" ".join(data_parts)}" {url}')
        
        elif method == "GET" and get_params:
            # Ejemplo GET con parámetros
            query_parts = [f'{p["name"]}={self._get_example_value(p)}' for p in get_params]
            examples.append(f'curl.exe -X GET "{url}?{"&".join(query_parts)}"')
        else:
            examples.append(f'curl.exe -X GET {url}')
        
        return examples[:3]  # Máximo 3 ejemplos
    
    def _get_example_value(self, param: Dict) -> str:
        """Obtiene un valor de ejemplo para un parámetro."""
        # Si tiene valor por defecto, usarlo
        if param.get("default"):
            return param["default"]
        
        # Según el tipo
        param_type = param.get("type", "string")
        param_name = param["name"].lower()
        
        if param_type == "date":
            return "10/12/2025"
        elif param_type == "integer":
            if "id" in param_name:
                return "1"
            elif "limit" in param_name or "count" in param_name:
                return "10"
            else:
                return "1"
        elif param_type == "float":
            if "lat" in param_name or "cy" in param_name:
                return "-99.1332"
            elif "lon" in param_name or "lng" in param_name or "cx" in param_name:
                return "19.4326"
            else:
                return "0.0"
        else:
            return "test"
    
    def _get_alternative_value(self, param: Dict) -> str:
        """Obtiene un valor alternativo para pruebas."""
        param_type = param.get("type", "string")
        
        if param_type == "date":
            return "01/01/2025"
        elif param_type == "integer":
            return "999"
        elif param_type == "float":
            return "0.0"
        else:
            return "example"
    
    def _check_auth_required(self, content: str) -> bool:
        """Detecta si el endpoint requiere autenticación."""
        auth_patterns = [
            r'session_start',
            r'\$_SESSION',
            r'Authorization',
            r'token',
            r'authenticate'
        ]
        
        for pattern in auth_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        
        return False
    
    def _check_database_usage(self, content: str) -> bool:
        """Detecta si el endpoint usa base de datos."""
        db_patterns = [
            r'pg_connect',
            r'mysqli',
            r'PDO',
            r'SELECT',
            r'INSERT',
            r'UPDATE',
            r'DELETE'
        ]
        
        for pattern in db_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        
        return False
