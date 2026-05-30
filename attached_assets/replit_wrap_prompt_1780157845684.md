# Prompt for Replit: wrap repo / final cleanup for LongMemEval-S semantic-memory blog

Please do a final repo-readiness pass for the LongMemEval-S semantic-memory blog post. Do not launch a new full 500-question run unless explicitly approved. Prioritize small code/metadata fixes, reproducibility, and packaging.

## Goal

Prepare the repo and run artifacts so the blog post can be published without confusing reproduction instructions or unresolved metadata gaps.

## Required no-rerun changes

1. **Add explicit `--retain` CLI aliases.**
   - `analysis.significance` and `analysis.failures` currently expose `--det/--flat/--agentic`, so the retain run is passed through the legacy `--agentic` slot.
   - Add `--retain` as a first-class argument while preserving backward compatibility.
   - Update help text and README examples.
   - Confirm the commands below work:

   ```bash
   ../.pythonlibs/bin/python -m analysis.significance \
       --det full-s-sonnet \
       --flat task18-flat-500 \
       --agentic task18-agentic-500 \
       --retain task19-retain-500

   ../.pythonlibs/bin/python -m analysis.failures \
       --flat task18-flat-500 \
       --retain task19-retain-500
   ```

2. **Add the cleanup-pass tables to the analysis output or README.**
   Please make the following tables reproducible from scripts, not only pasted in the blog:
   - matched-hit subset test: det vs flat where both have `turn_hit=1`;
   - abstention accuracy table;
   - hit=1 wrong-answer triage summary;
   - flat-correct / retain-wrong Borges audit row;
   - write/read cost table;
   - reproduction metadata table.

3. **Persist or document missing cost fields.**
   Existing stores do not record extractor calls/tokens, embedding calls/tokens, or pre-consolidation memory counts. Do not estimate these retroactively.
   - Add “not recorded” to current report output.
   - Add TODO/instrumentation issue for future runs to persist:
     - extractor calls;
     - extractor input tokens;
     - extractor output tokens;
     - embedding calls/tokens;
     - pre-consolidation memory counts;
     - storage size;
     - per-question write-time latency if cold-cache.

4. **Record model alias resolution more explicitly going forward.**
   - The extractor model is currently `gpt-4o-mini` alias only; snapshot is not resolved/recorded.
   - The scaffold parity run recorded `claude-sonnet-4-5` alias while scaffold recorded `claude-sonnet-4-5-20250929`.
   - Add a manifest field for both requested and resolved model IDs whenever the provider exposes it.
   - If provider does not expose resolved snapshot, explicitly record `resolved_model: null` and `resolved_model_unavailable: true`.

5. **Add a stable scaffold-slice manifest.**
   - Record the exact 50 qids or a JSON file plus sha256.
   - Current sorted-id sha256: `e293d7b2239da1e2ff2097ae44138e872cfa95e47a5400c0c9fed5c6dcf5a107`.
   - Include seed 42 and sampling method.

6. **Add visual assets to the repo.**
   Include or regenerate:
   - accuracy ladder;
   - bottleneck flip;
   - assistant retention by type;
   - context cost;
   - matched-hit subset;
   - evidence-present wrong-answer triage;
   - abstention accuracy;
   - architecture diagram: event log → graph projection → extraction → typed memories → retrieval → reader;
   - proposed hybrid retrieval diagram: semantic retrieve → provenance expansion → raw-span anchors → evidence-use operators.

7. **Add a short repo note about the matched prior-substrate comparison.**
   Create a TODO / issue / README section for the future 2×2:
   - earlier deterministic evidence compiler at ~2.5k context;
   - retained semantic memory at ~2.5k context;
   - earlier deterministic evidence compiler at ~9.5k context;
   - retained semantic memory at ~9.5k context.

## Optional, only if cheap and no full rerun

1. **Resolve scaffold alias if possible from provider logs.**
   If there are API/provider logs that prove `pref-extract-s` resolved to `claude-sonnet-4-5-20250929`, add that proof to the manifest or cleanup output. If not, keep the caveat.

2. **Add a smoke test for assistant-retention invariants.**
   - user-turn extraction path unchanged when retention flag changes;
   - assistant-turn extraction uses assistant namespace only when retention is on;
   - retained assistant memory preserves source-turn provenance;
   - quote/list/code/calculation turns are candidates for future raw-span anchoring.

3. **Open a vNext issue for hybrid raw-span fallback.**
   Proposed behavior:
   - retrieve semantic memories;
   - inspect query for quote/list/code/calculation/artifact intent;
   - follow provenance to raw source turn or span;
   - include the raw anchor in the evidence bundle;
   - measure Borges recovery and span-loss reduction.

## Response format

Return:

- a concise summary of changes made;
- exact commands that now reproduce the tables;
- any files added/modified;
- remaining unresolved metadata gaps;
- whether repo is ready to publish.

Do not add new claims that are not backed by existing artifacts.
