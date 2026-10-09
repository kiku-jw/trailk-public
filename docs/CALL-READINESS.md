# Local review: call readiness, 2026-10-03

The already published/installed initial implementation is not call-ready: public_sample is its sole cloud source, and both native and stream layers stop at 150 seconds. This review branch has not been pushed or installed. No capture, playback, paid requests, Keychain reads or runtime approval changes were performed.

## Architecture and bounded local changes

Keep the native process-output tap → private Unix pipe → bounded PCM queue → dedicated OpenAI `/v1/realtime/translations` WebSocket → append-only Russian captions. Typed Russian intent uses its separately approved text adapter. Never send/speak a reply automatically.

A future Zoom attempt requires two explicit source-matched schema-v2 approvals: native capture and private-call OpenAI upload. They share a nonempty approval_id, source=zoom, scope=zoom_output, duration (up to 5400 seconds), and expiry (within 24 hours). Native approval explicitly excludes microphone; cloud approval explicitly permits private_call_upload, forbids persist_transcript, and specifies budget_usd. These are approval records, not credentials. The code does not create them, remove STOP or reset the existing attempt ledger.

The existing public approval remains limited to 150 seconds and $0.15. Any AUDIO-DO-NOT-PLAY file overrides all approval fields. An attempt exclusively reserves its full approved budget before reading a key or connecting. A failed attempt still consumes that reservation; no automatic retry, ledger reset, reconnection, source broadening or replay of missed audio. Stop halts capture, stops further appends and drains provider output for at most 8 seconds. Unexpected provider close halts capture with a visible notice. A fresh attempt remains blocked by the one-attempt ledger until a separately reviewed budget/approval workflow exists.

Native and Python duration guards agree. Authorized Zoom silence remains streamed; the old 60-second silence stop remains for the public test. Source disappearance/family change/output-device change/missing buffers/UI heartbeat loss/backlog still stop capture. Caption events are paged in batches of 500. History is bounded by 100,000 events / 12 MiB serialized event bytes; reaching capacity stops the stream and preserves earlier rows. Zoom receipts contain only run/usage/capture metadata; caption text stays in RAM.

## Evidence and limits

37 Python tests pass, including source/expiry/duration/budget/privacy rejection, STOP precedence, one-attempt reservation, private receipt omission, history paging/capacity, 90-minute virtual PCM silence (27,000 × 200 ms), and 90-minute virtual WebSocket append/close/tail lifecycle using one injected mock connection. Seven JS tests pass. Swift capture sources typecheck. A fresh ad-hoc signed app was built in `/tmp/trailk-readiness-reviewed/Trailk.app`, without replacing the installed app.

These tests use synthesized zero PCM and virtual time. They prove client controls and wire orchestration, not actual audio reception, real 90-minute provider support, latency or translation quality. Live WKWebView synthetic lifecycle verification passed all 18 checks, including reading anchor, stable earlier rows, font persistence, manual reply selection, close/Start/Stop and manual local-backend recovery. Its report is stored separately under `/tmp/calm-translate-verification-proof`. The original fixed 1.2-second child-exit check failed once; the test now waits for actual exit state with a 5-second deadline, and the rerun passed. Synthetic native converter tests cover 16/44.1/48 kHz stereo → 24 kHz mono and idempotent Stop without capture.

## Current provider facts, not a promise

[OpenAI model page](https://developers.openai.com/api/docs/models/gpt-realtime-translate) lists $0.034 per audio minute, or $3.06 for 90 minutes of streamed audio at that price, before any separate text usage. Actual billing remains unknown. The reviewed dedicated [translation guide](https://developers.openai.com/api/docs/guides/realtime-translation) requires continuous input including silence and close/drain, and recommends separate speaker tracks. The model and guide do not establish a 90-minute connection guarantee; the generic Realtime session limit must not be treated as a verified translation-endpoint limit. This branch deliberately stops on disconnect instead of claiming seamless rotation.

## Remaining concrete decisions before a real Zoom test

1. New explicit request to resume sound tests; the user's earlier STOP remains in force.
2. Agree on capturing only Zoom output in this new helper, then the separate macOS audio-recording permission for its own identity. No transfer of Transcrybe permission; no screen or microphone permission.
3. Separate informed approval to transmit this specific private test call to OpenAI, with duration and dollar ceiling. Participants/test content must be appropriate for that decision. Use a short staged test before any long real call. No approval files are written by this branch.
4. Explicit review of the local changes and install/build identity. No further push has been authorized.
5. Physical verification: selected Zoom output reaches PCM, other apps and microphone are excluded, output echo/self-speech behavior, AirPods/output-device changes, process loss and permission denial. Mixed Zoom participant output cannot guarantee isolated speaker tracks.
6. Real authorized end-to-end assessment of RU readability, latency, names/numbers, interruptions, provider disconnect and long-session limits. Overnight mock results cannot substitute for this.

Manual text reply still has its own exhausted/disabled current approval ledger and requires a new separate budget decision. No offline ASR/translation model is bundled: an offline-quality translation path is still a separate implementation task.
