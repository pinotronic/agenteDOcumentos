"""
Script de prueba para verificar que open_file_in_editor funciona correctamente
"""
import env_loader
from tools import open_file_in_editor

# Probar con el propio README.md
test_file = r"C:\Users\pvargas\Desktop\Agente\README.md"

print("🧪 Probando open_file_in_editor...")
print(f"Archivo de prueba: {test_file}")
print("-" * 60)

result = open_file_in_editor(test_file)

print("\n📊 Resultado:")
import json
print(json.dumps(result, indent=2, ensure_ascii=False))

if result.get("success"):
    print("\n✅ ¡La función funciona correctamente!")
    print(f"   Método usado: {result.get('method', 'desconocido')}")
else:
    print("\n❌ Error al abrir archivo:")
    print(f"   {result.get('error', 'Error desconocido')}")
