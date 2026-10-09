# Completed-segment T9 and measured latency — 4 October 2026

The old ledger ignored a 10-character complete question (`Вы слышали?`). It also changed the reply version on every partial delta, even if the completed context was unchanged. Finally, it explicitly allowed a superseded response to render when it returned within eight seconds. Those three mechanisms contributed to late/stale suggestions. The earlier 31.2-second startup had dispatches at ~16.6 and ~28.8 seconds: the 12-second throttle explains the second wait, but the first response body was not retained and its rejection cause is not claimed.

Now the scheduler versions only completed translated thoughts, includes short meaningful questions (six characters), waits 600ms after punctuation rather than 1600ms, and rejects every response superseded by another completed thought. A continuing partial does not invalidate the latest completed thought. Unpunctuated fragments still require 1600ms quiet and never settle while speech activity remains high. Context remains bounded to six observed segments/2400 characters; the prompt focuses on the last meaningful topic. No selected answer is evidence of speech. The 12-second dispatch interval, one inflight request, context deduplication, no same-context retry and Stop cancellation remain.

An obsolete unselected main reply becomes unavailable. A manually selected answer remains editable and unchanged. Fresh options restore selection. Hover/focus holds reading text; leaving/blur permits the new option to appear. Historical choices remain explicitly labelled as older context.

Optional memory-only numeric stage tracing records segment completion, debounce/stabilization eligibility, rate-limit wait, dispatch, response, rejection category, freshness discard and render. It contains lengths/revisions/times rather than conversation text. Only the public test host enables tracing. The test dialogue has separate 10ms acoustic onset/end annotations; the native player clock and UI performance clock are correlated. UI observations are every 300ms, so hundredths are not precision guarantees.

## Offline comparison

Replaying identical public deltas with a controlled 1700ms mock response produced two stale renders with old scheduling. New scheduling had zero stale renders; first fresh result at 7.95s vs no fresh old result. New segment stabilization dispatched at 6.25s; requiring full silence delayed it to 7.25s. These are synthetic behavior measurements, not cloud/translation quality. New logic recognized more completed segments (four vs two attempts over 70s), still bounded by the unchanged 12-second interval.

## Two public real comparisons

Identical authored English dialogue was locally synthesized with macOS Samantha; only the existing test player's process was captured with CATapMuted. No microphone, Zoom, private audio, screen, browser or new permissions. One connection per variant and two text requests per variant, with no retries.

For `Which path is safer?`:

| Measured stage | Before | After |
| --- | ---: | ---: |
| Acoustic speech onset → recognizable partial | 3.02s | 2.72s |
| Acoustic speech end → committed RU | 2.46s | 2.16s |
| Completed RU segment → fresh T9 render | 3.84s | 2.34s |
| Acoustic speech end → usable T9 observed | 6.06s | 4.26s |

The ~0.30s translation difference is within one UI polling interval and reflects provider variation; no ASR/audio algorithm changed. T9 improvement combines the shorter stabilization and different transport latency (2.06s vs 1.66s). One sample is not a statistical speed claim.

The first very short question `Are you ready?` produced no translation in baseline. The new run translated it, but its first reply was rejected by the unchanged neutrality filter. Thus baseline showed two groups, new showed one. That is a material limitation, not a successful answer for every utterance. Both variants showed only fresh groups at render and preserved the manually selected answer/paused history. Later groups can naturally become stale as the next completed thought arrives. The final translation also showed wording variation/error (`Какое измерение...`); this does not establish translation accuracy.

After those two real tests, the empty-intent prompt was strengthened to require every option to be a question ending in `?` or a neutral `Please...` request, matching the unchanged filter. No personal readiness is inferred. This final prompt and the later estimated-budget policy are offline-tested only; there was no third paid run.

Historical account balances, spending authorizations and request-cost details are omitted from the public snapshot. Earlier test observations are historical; no live provider verification is claimed by this publication.
