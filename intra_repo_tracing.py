"""Trazabilidad intra-repo (archivo -> archivo).

Objetivo: enriquecer el RAG con dependencias deterministas entre archivos del repo,
principalmente a partir de imports/includes (no depende del LLM).

Diseño:
- Python: parse AST para import/from-import (incluye imports relativos) y resuelve a paths del repo.
- JS/TS: regex simple para import/require (solo relativos).
- PHP: regex simple para include/require (solo relativos).

Nota: esto NO intenta construir un call-graph exacto a nivel de función.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Set, Tuple


@dataclass(frozen=True)
class IntraRepoTrace:
    resolved_file_paths: List[str]
    unresolved_refs: List[str]


@dataclass(frozen=True)
class IntraRepoCallTrace:
    """Llamadas detectadas desde un archivo hacia otros archivos del repo."""

    called_file_paths: List[str]
    unresolved_call_refs: List[str]


_JS_EXTS = [".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"]


def detect_intra_repo_dependencies(
    *,
    file_path: str,
    content: str,
    file_type: str,
    repo_root: Optional[str] = None,
    max_edges: int = 50,
) -> IntraRepoTrace:
    """Detecta dependencias intra-repo para un archivo.

    Args:
        file_path: Ruta absoluta del archivo fuente.
        content: Contenido del archivo.
        file_type: Tipo ("python", "javascript", "typescript", "php", etc.).
        repo_root: Raíz del repo; por defecto `Path.cwd()`.
        max_edges: Máximo de dependencias resueltas a devolver.

    Returns:
        IntraRepoTrace con paths resueltos y refs no resueltas.
    """
    root = Path(repo_root).resolve() if repo_root else Path.cwd().resolve()
    src = Path(file_path).resolve()

    resolved: List[str] = []
    unresolved: List[str] = []
    seen: Set[str] = set()

    def add_resolved(p: Optional[Path]):
        if not p:
            return
        try:
            ap = str(p.resolve())
        except Exception:
            ap = str(p)
        if ap == str(src):
            return
        if ap not in seen:
            seen.add(ap)
            resolved.append(ap)

    def add_unresolved(ref: str):
        ref = (ref or "").strip()
        if not ref:
            return
        if ref not in unresolved:
            unresolved.append(ref)

    ft = (file_type or "").lower()

    if ft == "python" or src.suffix.lower() == ".py":
        _python_trace(src, content, root, add_resolved, add_unresolved)
    elif ft in {"javascript", "typescript"} or src.suffix.lower() in _JS_EXTS:
        _js_ts_trace(src, content, root, add_resolved, add_unresolved)
    elif ft == "php" or src.suffix.lower() == ".php":
        _php_trace(src, content, root, add_resolved, add_unresolved)

    if len(resolved) > max_edges:
        resolved = resolved[:max_edges]

    return IntraRepoTrace(resolved_file_paths=resolved, unresolved_refs=unresolved)


def detect_intra_repo_calls(
    *,
    file_path: str,
    content: str,
    file_type: str,
    repo_root: Optional[str] = None,
    max_edges: int = 50,
) -> IntraRepoCallTrace:
    """Detecta llamadas intra-repo (comunicación) desde un archivo.

    Implementación inicial enfocada en Python:
    - Resuelve alias de imports a paths del repo.
    - Encuentra `Call` donde el callee base coincide con un alias importado.
    - Emite edges file->file (targets resueltos).
    """
    root = Path(repo_root).resolve() if repo_root else Path.cwd().resolve()
    src = Path(file_path).resolve()

    called: List[str] = []
    unresolved: List[str] = []
    seen: Set[str] = set()

    def add_called(p: Optional[Path]):
        if not p:
            return
        try:
            ap = str(p.resolve())
        except Exception:
            ap = str(p)
        if ap == str(src):
            return
        if ap not in seen:
            seen.add(ap)
            called.append(ap)

    def add_unresolved(ref: str):
        ref = (ref or "").strip()
        if not ref:
            return
        if ref not in unresolved:
            unresolved.append(ref)

    ft = (file_type or "").lower()
    if ft == "python" or src.suffix.lower() == ".py":
        _python_calls_trace(src, content, root, add_called, add_unresolved)

    if len(called) > max_edges:
        called = called[:max_edges]

    return IntraRepoCallTrace(called_file_paths=called, unresolved_call_refs=unresolved)


def _resolve_module_to_path(root: Path, module: str) -> Optional[Path]:
    if not module:
        return None

    parts = [p for p in module.split(".") if p]
    if not parts:
        return None

    candidate_file = root.joinpath(*parts).with_suffix(".py")
    if candidate_file.exists():
        return candidate_file

    candidate_pkg = root.joinpath(*parts, "__init__.py")
    if candidate_pkg.exists():
        return candidate_pkg

    return None


def _resolve_relative_module_to_path(base_dir: Path, module: str) -> Optional[Path]:
    # base_dir ya viene ajustado con el level.
    if module:
        parts = [p for p in module.split(".") if p]
        if parts:
            candidate_file = base_dir.joinpath(*parts).with_suffix(".py")
            if candidate_file.exists():
                return candidate_file

            candidate_pkg = base_dir.joinpath(*parts, "__init__.py")
            if candidate_pkg.exists():
                return candidate_pkg

            return None
    return None


def _python_trace(
    src: Path,
    content: str,
    root: Path,
    add_resolved,
    add_unresolved,
) -> None:
    try:
        tree = ast.parse(content)
    except Exception as e:
        add_unresolved(f"python_parse_error:{type(e).__name__}")
        return

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name
                p = _resolve_module_to_path(root, mod)
                if p:
                    add_resolved(p)
                else:
                    add_unresolved(mod)

        elif isinstance(node, ast.ImportFrom):
            level = int(getattr(node, "level", 0) or 0)
            module = node.module or ""

            if level > 0:
                # level=1 => mismo paquete (no sube). level=2 => sube 1.
                base_dir = src.parent
                for _ in range(max(level - 1, 0)):
                    base_dir = base_dir.parent

                # Caso: from .foo import bar  (module="foo")
                if module:
                    p = _resolve_relative_module_to_path(base_dir, module)
                    if p:
                        add_resolved(p)
                    else:
                        add_unresolved(f".{'.' * (level - 1)}{module}")
                    continue

                # Caso: from . import foo  (module=None, names=[foo])
                for alias in node.names:
                    name_mod = alias.name
                    p = _resolve_relative_module_to_path(base_dir, name_mod)
                    if p:
                        add_resolved(p)
                    else:
                        add_unresolved(f".{'.' * (level - 1)}{name_mod}")

            else:
                # Import absoluto: from a.b import c => depende de a.b
                if module:
                    p = _resolve_module_to_path(root, module)
                    if p:
                        add_resolved(p)
                    else:
                        add_unresolved(module)


def _python_calls_trace(
    src: Path,
    content: str,
    root: Path,
    add_called,
    add_unresolved,
) -> None:
    try:
        tree = ast.parse(content)
    except Exception as e:
        add_unresolved(f"python_parse_error:{type(e).__name__}")
        return

    # alias -> Path (módulo) si se puede resolver
    alias_to_path: dict[str, Optional[Path]] = {}

    def resolve_import_target(module: str, level: int = 0, names: Optional[List[str]] = None) -> Optional[Path]:
        if level > 0:
            base_dir = src.parent
            for _ in range(max(level - 1, 0)):
                base_dir = base_dir.parent

            if module:
                return _resolve_relative_module_to_path(base_dir, module)

            # from . import x => usar el nombre
            if names:
                for n in names:
                    p = _resolve_relative_module_to_path(base_dir, n)
                    if p:
                        return p
            return None

        # absoluto
        if module:
            return _resolve_module_to_path(root, module)
        return None

    # 1) construir alias map desde imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name
                asname = alias.asname or mod.split(".")[0]
                alias_to_path[asname] = _resolve_module_to_path(root, mod) or _resolve_module_to_path(root, mod.split(".")[0])

        elif isinstance(node, ast.ImportFrom):
            level = int(getattr(node, "level", 0) or 0)
            module = node.module or ""
            imported_names = [a.name for a in node.names]
            target_path = resolve_import_target(module, level=level, names=imported_names)

            for a in node.names:
                asname = a.asname or a.name
                # Para `from x import y`, mapear y -> x (archivo del módulo) si existe.
                alias_to_path[asname] = target_path

    # 2) detectar calls
    def call_base_name(func_expr: ast.AST) -> Optional[str]:
        if isinstance(func_expr, ast.Name):
            return func_expr.id
        if isinstance(func_expr, ast.Attribute):
            cur = func_expr
            while isinstance(cur, ast.Attribute):
                cur = cur.value
            if isinstance(cur, ast.Name):
                return cur.id
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            base = call_base_name(node.func)
            if not base:
                continue
            if base in alias_to_path and alias_to_path[base]:
                add_called(alias_to_path[base])
            elif base in alias_to_path and not alias_to_path[base]:
                add_unresolved(base)


_JS_IMPORT_RE = re.compile(
    r"(?:^|\n)\s*(?:import\s+[^;\n]*?\s+from\s+|export\s+[^;\n]*?\s+from\s+)['\"](?P<path>[^'\"]+)['\"]",
    re.MULTILINE,
)
_JS_REQUIRE_RE = re.compile(
    r"(?:require\(|import\()\s*['\"](?P<path>[^'\"]+)['\"]\s*\)?",
    re.MULTILINE,
)


def _resolve_relative_path(base_dir: Path, rel: str, root: Path) -> Optional[Path]:
    rel = (rel or "").strip()
    if not rel or not rel.startswith("."):
        return None

    candidate = (base_dir / rel).resolve()

    # Si apunta directo a archivo existente
    if candidate.exists() and candidate.is_file():
        # Mantener sólo si cae dentro del repo_root
        try:
            candidate.relative_to(root)
        except Exception:
            return None
        return candidate

    # Si no hay extensión, probar extensiones típicas
    if candidate.suffix == "":
        for ext in _JS_EXTS + [".py", ".php"]:
            p = candidate.with_suffix(ext)
            if p.exists() and p.is_file():
                try:
                    p.relative_to(root)
                except Exception:
                    continue
                return p

        # index.*
        for ext in _JS_EXTS:
            p = candidate / ("index" + ext)
            if p.exists() and p.is_file():
                try:
                    p.relative_to(root)
                except Exception:
                    continue
                return p

    return None


def _js_ts_trace(
    src: Path,
    content: str,
    root: Path,
    add_resolved,
    add_unresolved,
) -> None:
    base_dir = src.parent

    for m in _JS_IMPORT_RE.finditer(content):
        rel = m.group("path")
        p = _resolve_relative_path(base_dir, rel, root)
        if p:
            add_resolved(p)
        else:
            if rel.startswith("."):
                add_unresolved(rel)

    for m in _JS_REQUIRE_RE.finditer(content):
        rel = m.group("path")
        p = _resolve_relative_path(base_dir, rel, root)
        if p:
            add_resolved(p)
        else:
            if rel.startswith("."):
                add_unresolved(rel)


_PHP_INCLUDE_RE = re.compile(
    r"(?:include|include_once|require|require_once)\s*\(?\s*['\"](?P<path>[^'\"]+)['\"]\s*\)?\s*;",
    re.IGNORECASE,
)


def _php_trace(
    src: Path,
    content: str,
    root: Path,
    add_resolved,
    add_unresolved,
) -> None:
    base_dir = src.parent
    for m in _PHP_INCLUDE_RE.finditer(content):
        rel = m.group("path")
        p = _resolve_relative_path(base_dir, rel, root)
        if p:
            add_resolved(p)
        else:
            if rel.startswith("."):
                add_unresolved(rel)
