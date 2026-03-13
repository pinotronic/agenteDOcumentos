"""Tests para trazabilidad intra-repo (archivo -> archivo).

Estilo consistente con el repo: tests que imprimen y retornan True/False.
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, '.')

from intra_repo_tracing import detect_intra_repo_dependencies, detect_intra_repo_calls


def test_python_import_resolution():
    print("🧪 TEST: Trazabilidad Python (imports -> paths)")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "pkg").mkdir(parents=True, exist_ok=True)
        (root / "pkg" / "__init__.py").write_text("", encoding="utf-8")

        (root / "pkg" / "b.py").write_text(
            "def hello():\n    return 'ok'\n",
            encoding="utf-8",
        )

        (root / "pkg" / "a.py").write_text(
            "from . import b\n\n"
            "def run():\n"
            "    return b.hello()\n",
            encoding="utf-8",
        )

        a_path = str((root / "pkg" / "a.py").resolve())
        content = (root / "pkg" / "a.py").read_text(encoding="utf-8")

        trace = detect_intra_repo_dependencies(
            file_path=a_path,
            content=content,
            file_type="python",
            repo_root=str(root),
        )

        calls = detect_intra_repo_calls(
            file_path=a_path,
            content=content,
            file_type="python",
            repo_root=str(root),
        )

        expected = str((root / "pkg" / "b.py").resolve())
        print(f"   • Resolved: {trace.resolved_file_paths}")
        print(f"   • Unresolved: {trace.unresolved_refs}")
        print(f"   • Calls: {calls.called_file_paths}")

        if expected in trace.resolved_file_paths and expected in calls.called_file_paths:
            print("✅ Resolvió import y detectó llamada intra-repo")
            return True

        print("❌ No resolvió el import y/o no detectó la llamada")
        return False


def test_js_relative_import_resolution():
    print("\n🧪 TEST: Trazabilidad JS/TS (import/require relativos -> paths)")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "src").mkdir(parents=True, exist_ok=True)

        (root / "src" / "util.js").write_text("export const x = 1;\n", encoding="utf-8")
        (root / "src" / "main.js").write_text(
            "import { x } from './util';\nconsole.log(x);\n",
            encoding="utf-8",
        )

        main_path = str((root / "src" / "main.js").resolve())
        content = (root / "src" / "main.js").read_text(encoding="utf-8")

        trace = detect_intra_repo_dependencies(
            file_path=main_path,
            content=content,
            file_type="javascript",
            repo_root=str(root),
        )

        expected = str((root / "src" / "util.js").resolve())
        print(f"   • Resolved: {trace.resolved_file_paths}")
        print(f"   • Unresolved: {trace.unresolved_refs}")

        if expected in trace.resolved_file_paths:
            print("✅ Resolvió import relativo JS a path local")
            return True

        print("❌ No resolvió el import relativo JS")
        return False


if __name__ == "__main__":
    ok1 = test_python_import_resolution()
    ok2 = test_js_relative_import_resolution()
    sys.exit(0 if (ok1 and ok2) else 1)
