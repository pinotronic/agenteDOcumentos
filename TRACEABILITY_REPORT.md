# Traceability Report
- Generated: 2025-12-19T12:35:11
- Scope: Desktop/Agente
- Include external: False
- Storage mode: persistent:rag_storage

## Top Outgoing Calls (Top Talkers)
- 19 — C:\Users\pvargas\Desktop\Agente\tools.py

## Top Incoming Calls (Most Called)
- 1 — C:\Users\pvargas\Desktop\Agente\rag_storage_chroma.py
- 1 — C:\Users\pvargas\Desktop\Agente\code_analyzer.py
- 1 — C:\Users\pvargas\Desktop\Agente\doc_generator.py
- 1 — C:\Users\pvargas\Desktop\Agente\dependency_analyzer.py
- 1 — C:\Users\pvargas\Desktop\Agente\code_generator.py
- 1 — C:\Users\pvargas\Desktop\Agente\code_assistant.py
- 1 — C:\Users\pvargas\Desktop\Agente\external_integrations.py
- 1 — C:\Users\pvargas\Desktop\Agente\report_generator.py
- 1 — C:\Users\pvargas\Desktop\Agente\ci_cd_tools.py
- 1 — C:\Users\pvargas\Desktop\Agente\php_curl_analyzer.py

## Top Outgoing Dependencies
- 19 — C:\Users\pvargas\Desktop\Agente\tools.py
- 13 — C:\Users\pvargas\Desktop\Agente\README.md
- 4 — C:\Users\pvargas\Desktop\Agente\agent.py
- 3 — C:\Users\pvargas\Desktop\Agente\MEMORIA_CONVERSACIONAL.md
- 3 — C:\Users\pvargas\Desktop\Agente\test_contratos_gates.py
- 2 — C:\Users\pvargas\Desktop\Agente\ci_cd_tools.py
- 2 — C:\Users\pvargas\Desktop\Agente\report_generator.py
- 2 — C:\Users\pvargas\Desktop\Agente\test_architect_tools.py
- 1 — C:\Users\pvargas\Desktop\Agente\architect_mode.py
- 1 — C:\Users\pvargas\Desktop\Agente\code_analyzer.py

## Top Incoming Dependencies
- 1 — C:\Users\pvargas\Desktop\Agente\config.py
- 1 — C:\Users\pvargas\Desktop\Agente\rag_storage_chroma.py
- 1 — C:\Users\pvargas\Desktop\Agente\code_analyzer.py
- 1 — C:\Users\pvargas\Desktop\Agente\doc_generator.py
- 1 — C:\Users\pvargas\Desktop\Agente\dependency_analyzer.py
- 1 — C:\Users\pvargas\Desktop\Agente\code_generator.py
- 1 — C:\Users\pvargas\Desktop\Agente\code_assistant.py
- 1 — C:\Users\pvargas\Desktop\Agente\external_integrations.py
- 1 — C:\Users\pvargas\Desktop\Agente\report_generator.py
- 1 — C:\Users\pvargas\Desktop\Agente\ci_cd_tools.py

## File Trace Previews
### C:\Users\pvargas\Desktop\Agente\tools.py
- Outgoing edges: 38
- Incoming edges: 0

**Outgoing calls**
- calls -> C:\Users\pvargas\Desktop\Agente\rag_storage_chroma.py
- calls -> C:\Users\pvargas\Desktop\Agente\code_analyzer.py
- calls -> C:\Users\pvargas\Desktop\Agente\doc_generator.py
- calls -> C:\Users\pvargas\Desktop\Agente\dependency_analyzer.py
- calls -> C:\Users\pvargas\Desktop\Agente\code_generator.py
- calls -> C:\Users\pvargas\Desktop\Agente\code_assistant.py
- calls -> C:\Users\pvargas\Desktop\Agente\external_integrations.py
- calls -> C:\Users\pvargas\Desktop\Agente\report_generator.py
- calls -> C:\Users\pvargas\Desktop\Agente\ci_cd_tools.py
- calls -> C:\Users\pvargas\Desktop\Agente\php_curl_analyzer.py

**Outgoing depends_on**
- depends_on -> C:\Users\pvargas\Desktop\Agente\config.py
- depends_on -> C:\Users\pvargas\Desktop\Agente\rag_storage_chroma.py
- depends_on -> C:\Users\pvargas\Desktop\Agente\code_analyzer.py
- depends_on -> C:\Users\pvargas\Desktop\Agente\doc_generator.py
- depends_on -> C:\Users\pvargas\Desktop\Agente\dependency_analyzer.py
- depends_on -> C:\Users\pvargas\Desktop\Agente\code_generator.py
- depends_on -> C:\Users\pvargas\Desktop\Agente\code_assistant.py
- depends_on -> C:\Users\pvargas\Desktop\Agente\external_integrations.py
- depends_on -> C:\Users\pvargas\Desktop\Agente\report_generator.py
- depends_on -> C:\Users\pvargas\Desktop\Agente\ci_cd_tools.py

**Incoming calls**
- (none)

**Incoming depends_on**
- (none)

**Details**
- intra_repo_dependencies_unresolved: ['os', 'json', 'pathlib', 'typing', 'datetime', 'subprocess', 'shutil', 'openai']
- intra_repo_calls_unresolved: ['os', 'Path', 'subprocess', 'OpenAI', 'shutil', 'datetime']
- intra_repo_dependencies_modules: ['config', 'rag_storage_chroma', 'code_analyzer', 'doc_generator', 'dependency_analyzer', 'code_generator', 'code_assistant', 'external_integrations', 'report_generator', 'ci_cd_tools', 'php_curl_analyzer', 'architect_mode', 'contract_validator', 'quality_gate', 'evidence_generator', 'incremental_committer', 'plan_executor', 'plan_supervisor', 'intra_repo_tracing']

### C:\Users\pvargas\Desktop\Agente\rag_storage_chroma.py
- Outgoing edges: 0
- Incoming edges: 2

**Outgoing calls**
- (none)

**Outgoing depends_on**
- (none)

**Incoming calls**
- calls -> C:\Users\pvargas\Desktop\Agente\tools.py

**Incoming depends_on**
- depends_on -> C:\Users\pvargas\Desktop\Agente\tools.py

### C:\Users\pvargas\Desktop\Agente\code_analyzer.py
- Outgoing edges: 1
- Incoming edges: 2

**Outgoing calls**
- (none)

**Outgoing depends_on**
- depends_on -> config

**Incoming calls**
- calls -> C:\Users\pvargas\Desktop\Agente\tools.py

**Incoming depends_on**
- depends_on -> C:\Users\pvargas\Desktop\Agente\tools.py

### C:\Users\pvargas\Desktop\Agente\doc_generator.py
- Outgoing edges: 1
- Incoming edges: 2

**Outgoing calls**
- (none)

**Outgoing depends_on**
- depends_on -> rag_storage_chroma

**Incoming calls**
- calls -> C:\Users\pvargas\Desktop\Agente\tools.py

**Incoming depends_on**
- depends_on -> C:\Users\pvargas\Desktop\Agente\tools.py

### C:\Users\pvargas\Desktop\Agente\dependency_analyzer.py
- Outgoing edges: 1
- Incoming edges: 2

**Outgoing calls**
- (none)

**Outgoing depends_on**
- depends_on -> config

**Incoming calls**
- calls -> C:\Users\pvargas\Desktop\Agente\tools.py

**Incoming depends_on**
- depends_on -> C:\Users\pvargas\Desktop\Agente\tools.py

### C:\Users\pvargas\Desktop\Agente\code_generator.py
- Outgoing edges: 0
- Incoming edges: 2

**Outgoing calls**
- (none)

**Outgoing depends_on**
- (none)

**Incoming calls**
- calls -> C:\Users\pvargas\Desktop\Agente\tools.py

**Incoming depends_on**
- depends_on -> C:\Users\pvargas\Desktop\Agente\tools.py

### C:\Users\pvargas\Desktop\Agente\code_assistant.py
- Outgoing edges: 1
- Incoming edges: 2

**Outgoing calls**
- (none)

**Outgoing depends_on**
- depends_on -> config

**Incoming calls**
- calls -> C:\Users\pvargas\Desktop\Agente\tools.py

**Incoming depends_on**
- depends_on -> C:\Users\pvargas\Desktop\Agente\tools.py

### C:\Users\pvargas\Desktop\Agente\external_integrations.py
- Outgoing edges: 1
- Incoming edges: 2

**Outgoing calls**
- (none)

**Outgoing depends_on**
- depends_on -> config

**Incoming calls**
- calls -> C:\Users\pvargas\Desktop\Agente\tools.py

**Incoming depends_on**
- depends_on -> C:\Users\pvargas\Desktop\Agente\tools.py

### C:\Users\pvargas\Desktop\Agente\report_generator.py
- Outgoing edges: 2
- Incoming edges: 2

**Outgoing calls**
- (none)

**Outgoing depends_on**
- depends_on -> config
- depends_on -> rag_storage_chroma

**Incoming calls**
- calls -> C:\Users\pvargas\Desktop\Agente\tools.py

**Incoming depends_on**
- depends_on -> C:\Users\pvargas\Desktop\Agente\tools.py

### C:\Users\pvargas\Desktop\Agente\ci_cd_tools.py
- Outgoing edges: 2
- Incoming edges: 2

**Outgoing calls**
- (none)

**Outgoing depends_on**
- depends_on -> config
- depends_on -> env_loader

**Incoming calls**
- calls -> C:\Users\pvargas\Desktop\Agente\tools.py

**Incoming depends_on**
- depends_on -> C:\Users\pvargas\Desktop\Agente\tools.py

