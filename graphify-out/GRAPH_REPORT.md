# Graph Report - C:\Users\david\dev\dramalab  (2026-04-08)

## Corpus Check
- Corpus is ~40,684 words - fits in a single context window. You may not need a graph.

## Summary
- 564 nodes · 806 edges · 37 communities detected
- Extraction: 63% EXTRACTED · 37% INFERRED · 0% AMBIGUOUS · INFERRED: 295 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## God Nodes (most connected - your core abstractions)
1. `ProjectState` - 39 edges
2. `MockBackend` - 36 edges
3. `ExperimentRecord` - 35 edges
4. `ClaudeCLIBackend` - 33 edges
5. `ScoreResult` - 32 edges
6. `SequenceInfo` - 31 edges
7. `RoundResult` - 21 edges
8. `TestExtractJson` - 15 edges
9. `ScriptSmithPlugin` - 15 edges
10. `TestScoreResult` - 14 edges

## Surprising Connections (you probably didn't know these)
- `Load dimension weights from weights.json, filtered by mode scope. Returns a` --uses--> `ScoreResult`  [INFERRED]
  C:\Users\david\dev\dramalab\packages\scriptsmith\src\scriptsmith\scorer.py → C:\Users\david\dev\dramalab\packages\scriptsmith\src\scriptsmith\models.py
- `Load veto threshold rules from weights.json. Returns dict mapping dimension` --uses--> `ScoreResult`  [INFERRED]
  C:\Users\david\dev\dramalab\packages\scriptsmith\src\scriptsmith\scorer.py → C:\Users\david\dev\dramalab\packages\scriptsmith\src\scriptsmith\models.py
- `Get ordered dimension names for the given mode from weights.json.` --uses--> `ScoreResult`  [INFERRED]
  C:\Users\david\dev\dramalab\packages\scriptsmith\src\scriptsmith\scorer.py → C:\Users\david\dev\dramalab\packages\scriptsmith\src\scriptsmith\models.py
- `Build placeholder values for score prompt templates.` --uses--> `ScoreResult`  [INFERRED]
  C:\Users\david\dev\dramalab\packages\scriptsmith\src\scriptsmith\scorer.py → C:\Users\david\dev\dramalab\packages\scriptsmith\src\scriptsmith\models.py
- `Score a sequence or synopsis against criteria. Runs `runs` independent eval` --uses--> `ScoreResult`  [INFERRED]
  C:\Users\david\dev\dramalab\packages\scriptsmith\src\scriptsmith\scorer.py → C:\Users\david\dev\dramalab\packages\scriptsmith\src\scriptsmith\models.py

## Communities

### Community 0 - "C: Users"
Cohesion: 0.05
Nodes (56): _format_score(), _print_final_summary(), Execute one micro round on the current sequence., Execute one macro round., Print final loop summary., Re-derive synopsis context with error handling., Determine if the loop should stop., Format a score result for console display. (+48 more)

### Community 1 - "C: Users"
Cohesion: 0.04
Nodes (24): MockBackend, Deterministic backend that cycles through pre-configured responses., TestAdaptCriteria, TestAssignScopes, TestComputeWeight, TestDeriveAll, _init_workspace_with_git(), _make_mock_backend_for_loop() (+16 more)

### Community 2 - "C: Users"
Cohesion: 0.05
Nodes (33): Metadata about a single sequence segment., SequenceInfo, extract_text_from_docx(), find_markers(), group_into_episodes(), merge_into_sequences(), Split a screenplay docx into sequence files in workspace sequences . Return, Scan full text in overlapping windows to discover markers via LLM. (+25 more)

### Community 3 - "C: Users"
Cohesion: 0.06
Nodes (35): ClaudeCLIBackend, _find_claude(), Find the claude CLI executable., Backend that calls Claude Code CLI via subprocess., Lazily resolve claude CLI path (avoids failing at import init time)., Send prompt to Claude CLI, return response text., Send prompt, parse JSON from response. Retry on parse failure., adapt() (+27 more)

### Community 4 - "C: Users"
Cohesion: 0.05
Nodes (33): Result of a single optimization round, sent to frontend via SSE., RoundResult, ScriptSmith plugin adapter for DramaLab Studio., Wrap the scriptsmith package as a DramaLab Studio plugin., Run the optimization loop in a background thread and stream rounds., Signal the loop to stop after the current round., Read and concatenate all current sequences., Export the current workspace to a docx document. (+25 more)

### Community 5 - "C: Users"
Cohesion: 0.06
Nodes (22): Exception, BackendError, BackendProtocol, ensure_dict(), extract_json(), load_prompt(), ScriptSmith Iterative screenplay optimizer., Raised when a backend operation fails. (+14 more)

### Community 6 - "Community 6"
Cohesion: 0.06
Nodes (0): 

### Community 7 - "C: Users"
Cohesion: 0.14
Nodes (16): BaseModel, _get_session(), InitRequest, plugin_export(), plugin_run(), plugin_status(), plugin_stop(), plugin_stream() (+8 more)

### Community 8 - "C: Users"
Cohesion: 0.16
Nodes (16): apply_candidate(), commit_keep(), discard_candidate(), _get_short_hash(), git_init(), _mark_last_experiment_crashed(), If the last history entry is not keep discard, mark it as crashed., Return short hash of HEAD. (+8 more)

### Community 9 - "C: Users"
Cohesion: 0.18
Nodes (14): adapt_criteria(), adapt_criteria_from_text(), _assign_scopes(), _compute_weight(), _generate_criteria_files(), is_raw_evaluation_standard(), Generate criteria.md + weights.json from raw evaluation text. This is the t, Read evaluation standard docx, generate criteria.md + weights.json. (+6 more)

### Community 10 - "C: Users"
Cohesion: 0.13
Nodes (3): _rationale field should be preserved in extraction., extract_json should handle JSON arrays too., TestExtractJson

### Community 11 - "C: Users"
Cohesion: 0.19
Nodes (7): _git_init_workspace(), Initialize git in workspace and commit initial state., Simulate crash backup exists but candidate was written., TestApplyCandidate, TestCommitKeep, TestDiscardCandidate, TestReconcileWorkspace

### Community 12 - "C: Users"
Cohesion: 0.13
Nodes (5): Test with the sample_script.docx fixture., TestExtractText, TestFindMarkers, TestGroupIntoEpisodes, TestMergeIntoSequences

### Community 13 - "C: Users"
Cohesion: 0.24
Nodes (10): _build_prompt_vars(), _dimension_names(), load_veto_rules(), load_weights(), Score a sequence or synopsis against criteria. Runs `runs` independent eval, Load dimension weights from weights.json, filtered by mode scope. Returns a, Load veto threshold rules from weights.json. Returns dict mapping dimension, Get ordered dimension names for the given mode from weights.json. (+2 more)

### Community 14 - "C: Users"
Cohesion: 0.2
Nodes (6): start command should show help., CLI should show help text., test_help(), test_start_help(), TestDeriveCommand, TestStatusCommand

### Community 15 - "C: Users"
Cohesion: 0.25
Nodes (1): TestLoadPrompt

### Community 16 - "C: Users"
Cohesion: 0.33
Nodes (6): derive_all(), _derived_is_fresh(), Check if derived files exist and are recent enough to skip re-derive., Summarize a single sequence, with cache lookup., Regenerate synopsis.md and context.md from sequences. Stage 1 Per-sequence, _summarize_one()

### Community 17 - "C: Users"
Cohesion: 0.29
Nodes (6): Upload a .md file and get text as-is., Reject unsupported file types., Upload a .docx file and get extracted text., test_upload_docx(), test_upload_invalid_type(), test_upload_md()

### Community 18 - "C: Users"
Cohesion: 0.33
Nodes (3): Integration test upload - init - status., Test full flow upload - init - status., test_full_flow()

### Community 19 - "C: Users"
Cohesion: 0.4
Nodes (2): Create a minimal workspace structure for testing., tmp_workspace()

### Community 20 - "C: Users"
Cohesion: 0.4
Nodes (1): TestExportToDocx

### Community 21 - "C: Users"
Cohesion: 0.5
Nodes (3): File upload endpoint., Upload a file and extract text content., upload_file()

### Community 22 - "C: Users"
Cohesion: 0.67
Nodes (2): export_to_docx(), Merge all sequences into a single docx file. Text-level round-trip only — d

### Community 23 - "Community 23"
Cohesion: 1.0
Nodes (0): 

### Community 24 - "Community 24"
Cohesion: 1.0
Nodes (0): 

### Community 25 - "C: Users"
Cohesion: 1.0
Nodes (1): Compute median scores from multiple independent scoring runs. Args

### Community 26 - "C: Users"
Cohesion: 1.0
Nodes (1): Weighted score normalized to 0-100 scale.

### Community 27 - "C: Users"
Cohesion: 1.0
Nodes (1): Return the dimension with the lowest score.

### Community 28 - "C: Users"
Cohesion: 1.0
Nodes (1): Return the dimension with the lowest weighted score. Falls back to weak

### Community 29 - "C: Users"
Cohesion: 1.0
Nodes (1): Change in weighted score (normalized to 100).

### Community 30 - "C: Users"
Cohesion: 1.0
Nodes (1): Create a default state for the given mode.

### Community 31 - "C: Users"
Cohesion: 1.0
Nodes (1): Convert a ScriptSmith experiment record to RoundResult.

### Community 32 - "Community 32"
Cohesion: 1.0
Nodes (0): 

### Community 33 - "Community 33"
Cohesion: 1.0
Nodes (0): 

### Community 34 - "Community 34"
Cohesion: 1.0
Nodes (0): 

### Community 35 - "Community 35"
Cohesion: 1.0
Nodes (0): 

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (0): 

## Knowledge Gaps
- **66 isolated node(s):** `ScriptSmith Iterative screenplay optimizer.`, `Detect whether text is a raw evaluation standard (not criteria.md). Returns`, `Extract plain text from a .docx file.`, `Assign macro micro scopes to dimensions by index.`, `Compute weight coefficient from original max score. Equal weight = 1.0. Hig` (+61 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 23`** (2 nodes): `layout.tsx`, `RootLayout()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24`** (2 nodes): `utils.ts`, `cn()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `C: Users`** (1 nodes): `Compute median scores from multiple independent scoring runs. Args`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `C: Users`** (1 nodes): `Weighted score normalized to 0-100 scale.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `C: Users`** (1 nodes): `Return the dimension with the lowest score.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `C: Users`** (1 nodes): `Return the dimension with the lowest weighted score. Falls back to weak`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `C: Users`** (1 nodes): `Change in weighted score (normalized to 100).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `C: Users`** (1 nodes): `Create a default state for the given mode.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `C: Users`** (1 nodes): `Convert a ScriptSmith experiment record to RoundResult.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 32`** (1 nodes): `next-env.d.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 33`** (1 nodes): `next.config.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 34`** (1 nodes): `postcss.config.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 35`** (1 nodes): `tailwind.config.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (1 nodes): `index.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MockBackend` connect `C: Users` to `C: Users`, `C: Users`, `C: Users`?**
  _High betweenness centrality (0.323) - this node is a cross-community bridge._
- **Why does `ClaudeCLIBackend` connect `C: Users` to `C: Users`, `C: Users`?**
  _High betweenness centrality (0.261) - this node is a cross-community bridge._
- **Why does `ProjectState` connect `C: Users` to `C: Users`, `C: Users`?**
  _High betweenness centrality (0.186) - this node is a cross-community bridge._
- **Are the 36 inferred relationships involving `ProjectState` (e.g. with `Re-derive synopsis context with error handling.` and `Determine if the loop should stop.`) actually correct?**
  _`ProjectState` has 36 INFERRED edges - model-reasoned connections that need verification._
- **Are the 31 inferred relationships involving `MockBackend` (e.g. with `TestAssignScopes` and `TestComputeWeight`) actually correct?**
  _`MockBackend` has 31 INFERRED edges - model-reasoned connections that need verification._
- **Are the 32 inferred relationships involving `ExperimentRecord` (e.g. with `Re-derive synopsis context with error handling.` and `Determine if the loop should stop.`) actually correct?**
  _`ExperimentRecord` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 27 inferred relationships involving `ClaudeCLIBackend` (e.g. with `Create the Claude CLI backend.` and `Resolve workspace path, defaulting to cwd.`) actually correct?**
  _`ClaudeCLIBackend` has 27 INFERRED edges - model-reasoned connections that need verification._