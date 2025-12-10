"""
Script para compilar el agente a ejecutable .exe con PyInstaller
"""
import os
import sys
import shutil
from pathlib import Path

print("=" * 80)
print("🔨 COMPILADOR DE AGENTE A EJECUTABLE")
print("=" * 80)

# Verificar que estamos en el directorio correcto
if not Path("main.py").exists():
    print("❌ Error: Ejecuta este script desde la raíz del proyecto")
    sys.exit(1)

# Verificar que PyInstaller está instalado
try:
    import PyInstaller
    print(f"✅ PyInstaller {PyInstaller.__version__} instalado")
except ImportError:
    print("❌ PyInstaller no está instalado")
    print("   Ejecuta: pip install pyinstaller")
    sys.exit(1)

print("\n📋 OPCIONES DE COMPILACIÓN:")
print("1. Ejecutable + carpeta de dependencias (RÁPIDO, ~50 MB)")
print("2. Ejecutable único todo-en-uno (LENTO, ~150 MB)")
print("3. Cancelar")

opcion = input("\nSelecciona opción (1-3): ").strip()

if opcion == "3":
    print("❌ Cancelado")
    sys.exit(0)

# Preparar comando PyInstaller
cmd_base = [
    "pyinstaller",
    "--name=Agente",
    "--icon=NONE",  # Puedes agregar un .ico si tienes
    "--clean",
    "--noconfirm",
]

# Agregar archivos de datos necesarios
cmd_base.extend([
    "--add-data=.env.example;.",
    "--add-data=README.md;.",
    "--add-data=MEMORIA_CONVERSACIONAL.md;.",
    "--hidden-import=chromadb",
    "--hidden-import=openai",
    "--hidden-import=tiktoken",
    "--collect-all=chromadb",
    "--collect-all=openai",
])

if opcion == "1":
    print("\n🔨 Compilando ejecutable + carpeta...")
    # Múltiples archivos (más rápido)
    cmd_base.append("main.py")
elif opcion == "2":
    print("\n🔨 Compilando ejecutable único...")
    # Un solo archivo (más lento pero portátil)
    cmd_base.extend(["--onefile", "main.py"])
else:
    print("❌ Opción inválida")
    sys.exit(1)

# Ejecutar PyInstaller
print(f"\n⚙️ Ejecutando: {' '.join(cmd_base)}\n")
import subprocess

# Usar pyinstaller desde el entorno virtual
pyinstaller_path = Path(__file__).parent / "env" / "Scripts" / "pyinstaller.exe"
if not pyinstaller_path.exists():
    print("❌ Error: pyinstaller.exe no encontrado en env/Scripts/")
    sys.exit(1)

cmd_base[0] = str(pyinstaller_path)
result = subprocess.run(cmd_base)

if result.returncode != 0:
    print("\n❌ Error al compilar")
    sys.exit(1)

print("\n" + "=" * 80)
print("✅ COMPILACIÓN EXITOSA")
print("=" * 80)

# Mostrar ubicación del ejecutable
if opcion == "1":
    exe_path = Path("dist/Agente/Agente.exe")
    print(f"\n📦 Ejecutable: {exe_path.absolute()}")
    print("\n📂 ARCHIVOS NECESARIOS:")
    print(f"   • Carpeta completa: dist/Agente/")
    print(f"   • Incluye: Agente.exe + dependencias")
    print(f"\n💡 Para distribuir: Comprime toda la carpeta 'dist/Agente/'")
else:
    exe_path = Path("dist/Agente.exe")
    print(f"\n📦 Ejecutable: {exe_path.absolute()}")
    print(f"\n💡 Archivo único, puedes moverlo donde quieras")

# Copiar archivos de configuración necesarios
print("\n⚙️ Copiando archivos de configuración...")
dist_dir = Path("dist/Agente" if opcion == "1" else "dist")

# Crear .env.example en dist
if not (dist_dir / ".env.example").exists():
    shutil.copy(".env.example", dist_dir / ".env.example")
    print("   ✅ .env.example copiado")

print("\n" + "=" * 80)
print("📋 INSTRUCCIONES DE USO:")
print("=" * 80)
print("\n1. Copia tu archivo .env (con OPENAI_API_KEY) junto al ejecutable")
print("2. Ejecuta Agente.exe")
print("3. Las carpetas rag_storage/ y memory_storage/ se crearán automáticamente")
print("\n⚠️ IMPORTANTE:")
print("   • El .env con tu API key NO se incluye por seguridad")
print("   • Debes crearlo manualmente o copiar el tuyo")
print(f"\n📏 Tamaño aproximado: {exe_path.stat().st_size / 1024 / 1024:.1f} MB")
