# Multi-Agent Code Analysis System - AI Instructions

## Architecture Overview

This is a **multi-agent orchestration system** with intelligent model selection. Three OpenAI models work together:

- **gpt-4o-mini** (Orchestrator): Fast coordination, tool selection, file operations
- **gpt-4o** (Analyzer): Deep code analysis via `code_analyzer.py` 
- **o3-mini** (Reasoning): Complex tasks requiring critical thinking

### Key Architectural Decisions

**Why Multi-Agent?** Separate concerns: orchestration (fast/cheap) vs. deep analysis (powerful/expensive). The orchestrator in [agent.py](agent.py) delegates to specialized analyzers.

**Model Selection Strategy**: [config.py](config.py) defines `REASONING_TASKS` that auto-trigger o3-mini for: `debug_assistant`, `code_review`, `security_audit`, `technical_debt_report`, `generate_tests`, `explain_code`. All other tasks use gpt-4o-mini.

**RAG Storage**: [rag_storage_chroma.py](rag_storage_chroma.py) uses ChromaDB (vector DB) for semantic search of analyzed code. Falls back to `EphemeralClient` on Windows+Python 3.13 due to Rust binding incompatibility. Use `CHROMA_PERSIST=1` and `CHROMA_PERSIST_PATH` env vars for persistent storage when compatible.

**Tool Selection Optimization**: [tool_selector.py](tool_selector.py) dynamically filters 47 tools down to ~15 relevant ones based on keyword detection, saving 70% token overhead. Prevents hitting 128K context limits.

## Project-Specific Patterns

### Module Responsibilities

**[tools.py](tools.py)** (2477 lines): Monolithic registry of all 47 tool functions. Each tool returns structured data and is registered in `TOOLS` (OpenAI function schemas) and `TOOL_FUNCTIONS` (actual callables). When adding tools, update both dicts.

**[agent.py](agent.py)**: Orchestrator loops: (1) User message → (2) Tool selection → (3) Execute tool via `execute_tool_call()` → (4) Format with TOON → (5) Return to LLM. Memory is **disabled by default** to save tokens—see `_inject_recent_memory()`.

**ModoGorila Workflow**: Contract-driven development via [architect_mode.py](architect_mode.py), [plan_executor.py](plan_executor.py), [plan_supervisor.py](plan_supervisor.py). Architect generates Spec Packs + DoD checklists → Executor runs steps → Supervisor validates. See [test_modogorila.py](test_modogorila.py) for examples.

### Critical Conventions

**TOON Format**: Custom "Token-Oriented Object Notation" in [toon_formatter.py](toon_formatter.py) reduces JSON tokens by 40-70%. Arrays of objects become CSV-like tables. Tool results are auto-converted via `format_tool_result()`.

**ChromaDB Dual Stores**: [rag_storage_chroma.py](rag_storage_chroma.py) stores code analysis, [conversation_memory.py](conversation_memory.py) stores chat history. Both share `EphemeralClient` workaround pattern.

**Config-Driven Ignoring**: [config.py](config.py) defines `IGNORE_PATTERNS` (like `.gitignore`), `BINARY_EXTENSIONS`, `CODE_EXTENSIONS`. The `_should_ignore()` function in [tools.py](tools.py) gates all file operations.

**Tool Categories**: 9 groups in [tool_selector.py](tool_selector.py): `analysis`, `writing`, `dependencies`, `code_generation`, `assistance`, `external`, `reports`, `cicd`, `gorila_mode`. Add new tools to appropriate category for selection logic.

## Development Workflows

### Running the Agent

```powershell
# Activate virtual environment
.\env\Scripts\Activate.ps1

# Run main loop
.\env\Scripts\python.exe main.py
```

Entry point: [main.py](main.py) → prints banner with all 47 tools → initializes `Agent` → loops on user input.

### Testing

Tests use direct function imports, not the agent loop:

```python
from tools import generate_analysis_plan, explore_directory
```

Examples:
- [test_modogorila.py](test_modogorila.py): Architect + deep exploration tests
- [test_executor_supervisor.py](test_executor_supervisor.py): Plan execution validation
- [test_contratos_gates.py](test_contratos_gates.py): Contract/DoD/QualityGate checks
- [test_evidencia_commits.py](test_evidencia_commits.py): Evidence generation + git diffs

### Adding Tools

1. Implement function in appropriate module (e.g., [code_generator.py](code_generator.py))
2. Add OpenAI schema to `TOOLS` array in [tools.py](tools.py)
3. Add callable to `TOOL_FUNCTIONS` dict in [tools.py](tools.py)
4. Add to category in [tool_selector.py](tool_selector.py) with relevant keywords
5. Update [main.py](main.py) banner if it's a user-facing tool
6. If requires reasoning, add to `REASONING_TASKS` in [config.py](config.py)

### Environment Setup

**.env** must contain:
```
OPENAI_API_KEY=sk-...
CHROMA_PERSIST=1  # Optional: enable persistent ChromaDB
CHROMA_PERSIST_PATH=./rag_storage  # Optional: custom path
```

Loaded via [env_loader.py](env_loader.py) (imported first by all modules).

## Integration Points

**VS Code Integration**: `open_file_in_editor` tool in [tools.py](tools.py) uses `code <file>` command to open files in the active VS Code instance.

**StackOverflow API**: [external_integrations.py](external_integrations.py) queries StackOverflow API, then summarizes top answers with GPT-4o.

**PyInstaller Build**: [build_exe.py](build_exe.py) + [Agente.spec](Agente.spec) generate standalone executables. Build artifacts in `build/` and `dist/` (ignored by default).

**PHP/cURL Analysis**: [php_curl_analyzer.py](php_curl_analyzer.py) connects to legacy PHP backend at `http://172.16.12.178` for HTTP request tracing.

## Anti-Patterns & Gotchas

❌ **Don't use memory injection**: `_inject_recent_memory()` in [agent.py](agent.py) is disabled to save tokens. If needed, user must explicitly ask for context.

❌ **Don't modify ChromaDB in Python 3.13**: Use `EphemeralClient` due to Rust binding crashes. Set `CHROMA_PERSIST=0` to avoid misleading persistence.

❌ **Don't exceed 128K tokens**: Tool selection + TOON formatting are critical. Monitor `estimate_token_savings()` output.

✅ **Always validate DoD**: When using ModoGorila, enforce DoD checklists via [contract_validator.py](contract_validator.py) before marking tasks complete.

✅ **Use explore_directory with architecture=True**: [tools.py](tools.py) `explore_directory()` detects frameworks, entry points, dependencies—essential for understanding unfamiliar repos.

## File Structure Conventions

- **Root modules** ([agent.py](agent.py), [tools.py](tools.py), [config.py](config.py)): Core orchestration
- **Specialized modules** (e.g., [dependency_analyzer.py](dependency_analyzer.py)): Category-specific implementations
- **Tests** (`test_*.py`): Direct function imports, no mocking
- **Storage** (`memory_storage/`, `rag_storage/`, `prompt_storage/`): ChromaDB SQLite files + vector data
- **Build** (`build/`, `env/`): Ignored by analysis tools

## References

- [README.md](README.md): Comprehensive architecture + 47-tool documentation
- [MEMORIA_CONVERSACIONAL.md](MEMORIA_CONVERSACIONAL.md): Memory system design notes
- [config.py](config.py): All prompts, limits, extensions, reasoning task list
