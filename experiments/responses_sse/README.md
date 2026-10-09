# Disabled Responses SSE prototype

This isolated experiment is not imported, activated or packaged by Trailk. The installed app remains 1.4.1. It uses only `https://api.openai.com/v1/responses` and the fixed `gpt-5.4-mini-2026-03-17` model; a test proves the request body matches the existing production body except `stream: true`. `DisabledPrototype` defaults to disabled, refusing before key IPC, ledger reservation or transport. No CLI enables live calls, and no production route, preference or flag was added.

The implementation has incremental strict UTF-8/SSE framing, bounded JSON buffers, actual JSON-object decoding (not brace regexes), exact EN/RU/kind validation using the production guards, identity/sequence checks, stream refusal/failure/incomplete handling, no resend, retained attempt reserve and manual-selection preservation. Fully parsed pairs are staged only in RAM and are never sent to a renderer. It returns public options only after a valid full JSON group and successful matching `response.completed` terminal. No partial JSON repair or raw string display exists. Diagnostic traces contain stage/time/index, not conversation or draft text.

## Explicit contract decision

Pair-local checks: schema/field types and length, Unicode validity, allowed kind, unknown factual/biographical/time/payment boundary, echo/old-topic checks and exact EN/RU pair presence. These are lexical checks, not proof of faithful meaning or model accuracy.

Whole-response checks that forbid early publication under the current contract:

1. Successful terminal status, no refusal/incomplete/error, matching response/item/model identity. A closed first pair does not prove this future terminal.
2. Entire JSON root and every option's structure. A valid first pair followed by an invalid second pair is currently rejected as a whole.
3. Full array count of 1–3, retained valid option set, deduplication and final presentation order. No arbitrary completed object prefix substitutes for the full response contract.
4. Stop and current completed-context revision at publication. These can change while the remaining response arrives.

A literal early first-pair display would require an explicitly different product contract: independent pair acceptance rather than whole-response success, plus a UI treatment for late failures which cannot retract words already read. The user has not asked us to silently remove these checks. Therefore this prototype is kept disabled. With all existing barriers preserved, its first publishable pair and complete group become available together. An extra paid test would not establish an early-display gain, so none was run.

## Offline evidence

```sh
cd publication-stage
python3 -m unittest discover -s tests -p test_responses_sse_prototype.py -v
cd ..
python3 public-acceptance/sse-prototype-20261004/replay_recorded.py
```

28 prototype tests exercise byte-by-byte UTF-8/CRLF, split JSON/string/escaped quotes/Unicode surrogate pairs, braces inside strings, optional transport [DONE] (never a substitute for response.completed), bounded input, malformed root/duplicate keys, wrong identity/sequence, late refusal/failure/incomplete, disconnect even after output_text.done, Stop/topic change within a single SSE chunk, selection preservation, usage accounting, reservation-before-key, budget refusal, no retry/no refund and disabled production integration.

The recorded four PUBLIC real JSON responses were reframed as **synthetic SSE**, with exact current production validation. All 12 actual EN/RU/kind pairs were retained, selected EN unchanged, zero options published before terminal. A late-refusal counterexample stages the good first hearing pairs, then clears them without displaying any. This is protocol/offline validation, not a real SSE provider compatibility or speed measurement. Blocking urllib read may wait for its next chunk/20-second timeout after cancellation; logical publication is cancelled immediately at the next event check, but real network cancellation latency is unmeasured.

Baseline real speech-end→first usable/group times remain 6.764 / 4.459 / 5.618 / 5.467 s (the prior 1.4.0 public run). The quote fix in installed 1.4.1 saves 1.75 s only in controlled recorded replay; no new live speed claim is made here. Useful actual hearing alternatives remain “Yes, I hear you.” / “No, I don’t hear you.”; unknown total gets “I’m not sure—please check the total.”; the redundant final online clarification remains disclosed.

Historical account balances and spending authorizations are omitted from this public snapshot. This experiment remains disabled and its tests use fake transport without provider calls.

Official event definitions checked in the preceding step: [streaming guide](https://developers.openai.com/api/docs/guides/streaming-responses), [streaming event reference](https://developers.openai.com/api/reference/resources/responses/streaming-events). text deltas/done are not a completion signal for an individual object inside our options array.
