# 1.4.1: remove reproducible local delay after a quoted question

Read-only analysis of the recorded 1.4.0 public run, on its calibrated monotonic clock:

| Source | Speech end → full RU visible | Full RU → app commit | Commit → T9 dispatch | Dispatch → first validated option | Validated → group shown | Total |
|---|---:|---:|---:|---:|---:|---:|
| Can you hear me? | 1.689 s | 2.521 s | 0 s | 2.552 s | 0.002 s | 6.764 s |
| Short pause? | 2.170 s | 0 s | 0.918 s | 1.370 s | 0.001 s | 4.459 s |
| Fifteen or fifty? | 2.393 s | 0 s | 1.305 s | 1.918 s | 0.002 s | 5.618 s |
| Meet online instead | 3.147 s | 0 s | 0.742 s | 1.576 s | 0.002 s | 5.467 s |

Full RU visibility means the caption delta containing the last character of the exact latest RU context has reached the UI. First validated option means the test host records the successful /api/text response after the app validates its entire group. 1.4.0 was not Responses-streaming: no token or individual-object completion timestamps exist. No hypothetical time saving is inferred from character fractions. Clock/annotation uncertainty is about 11 ms, not absolute linguistic forced alignment. First partial RU can precede speech end, which is expected for streaming translation.

The average largest stage is speech end → full incoming RU (~2.35 s); text transport/generation/validation averages ~1.85 s. The first question has an additional avoidable local 2.521 s: its actual delta ended `?»`, which sentencePrefix rejected because `»` was not whitespace. Quiet-only fallback also depended on local audio pause/settle eligibility. The 2.521 s is not pure provider processing or a configured fixed timeout.

The small fix retains closing quotes/brackets with sentence-ending punctuation, then uses the existing 600 ms stabilization. It changes neither the meaning nor content sent, provider/model, request budget or scheduler limits. Split decimals remain protected. Adjacent letters after the closing delimiter do not count as a boundary. Incoming history remains append-only; this is still an app sentence boundary, not a provider final utterance guarantee.

Controlled-clock offline replay of the same recorded caption deltas and full actual model pairs shows the first group 1.750 s earlier; the other three groups, exact contexts, all 12 pairs and selected English are unchanged. Recorded text delays are held fixed as mocks, the 250 ms scheduler is simulated, and actual legacy quiet-commit eligibility is replayed. Other UI/backend polling is not fully simulated, so this is not a new cloud latency measurement or exact reproduction of every baseline dispatch. The prior useful hearing options are Yes, I hear you. / No, I don’t hear you. / Could you speak a little louder? The unknown amount still gets uncertainty/checking, never a guessed number. The redundant final online clarification remains a disclosed quality limitation. No additional paid run is needed to establish this local parsing bug; the end-to-end live improvement remains unmeasured.

## Early complete-option streaming decision

The [official streaming guide](https://developers.openai.com/api/docs/guides/streaming-responses) and [event reference](https://developers.openai.com/api/reference/resources/responses/streaming-events) provide text deltas/done, completed responses and refusal/incomplete lifecycle. They do not provide a completion event for each object inside our options array. A shadow probe of four recorded results demonstrates that a complete isolated EN+RU+kind pair passes the current local checks, while an unfinished group JSON is rejected. These lexical checks are not semantic proof.

Early publication is feasible as a separate transport/lifecycle change: incremental SSE and JSON parsing, bounded complete-pair validation, request/revision identity, terminal error handling, cancellation and incremental browser delivery. The current whole-body POST endpoint cannot publish the first pair before the response finishes. A later refusal/incomplete stream cannot undo words already read. Waiting for whole successful JSON preserves the existing terminal-success contract; selecting one option after it completes does not save the measured text-generation time. Therefore no partial/unchecked phrase or new SSE architecture is shipped in 1.4.1.

Recorded stage/replay feasibility reports are historical external engineering evidence and are not bundled in this public snapshot. No new paid requests were made by publication preparation.
