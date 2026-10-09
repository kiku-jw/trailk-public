Current fixes are documented in [FRESHNESS-FIXES.md](FRESHNESS-FIXES.md). The scenarios and unchanged >=2 filter described below are historical 1.3.2 measurements.

# Real-world latency research, 4 October 2026

Historical account balances, spending authorizations and request-cost details are omitted from the public snapshot. Earlier test observations are historical; no live provider verification is claimed by this publication.

## Buffer and decision map

| Stage | Current mechanism | Delay/risk | Measurement needed |
| --- | --- | --- | --- |
| CoreAudio IO | Scoped process tap; callback on userInitiated serial queue | Actual device callback interval not logged; native watchdog 250ms is health checking, not audio batching | mach_absolute_time IO begin/end, frame count, converter/write duration |
| Conversion/pipe | AVAudioConverter 24kHz mono PCM16, prime none; nonblocking UNIX write | No intentional sleep; write/conversion failure stops; OS pipe can still buffer | Numeric bytes, sequence, callback/receiver timestamps, no raw audio |
| Receiver/chunk | recv up to 9600 bytes; accumulate exactly 4800 samples | **200ms audio per frame**, initial accumulation 0–200ms | Frame sample range and ready timestamp |
| Local frame queue | 5 frames public/legacy; **50 frames budget-limited Zoom** | 1s/10s capacity; a full queue stops, does not silently drop/replay | Queue depth AND age of oldest frame, p50/p95/max |
| Async sender | to_thread(next_frame), send immediately; 0.5s empty timeout | 0.5s is not a fixed per-frame wait; WS send timeout 5s; slow sends grow age | Dequeue, send begin/end, bytes/unique frame seq |
| Provider receive | Concurrent async receive, max_queue 16 messages; output audio parsed then discarded | Message count is not a time bound; output audio length varies | Event type/count/bytes and receive time; no audio payload logging |
| Transcript delivery | Backend append-only event list; UI poll after 300ms plus HTTP time | Expected observer lag 0–~300ms when idle; 500 events per poll | Backend event_seq/receive, poll return, actual draft DOM update |
| Caption/history | Current partial separate; punctuation or ~120-character wrapping appends stable rows | Wrapped/period-delimited row is **not provider final**; decimal/abbreviation ambiguity | App row commit reason, fragment provenance, exact DOM render |
| T9 context | Last six app thoughts, bounded 2400 chars; completed revision only | >=6 chars; punctuation split can be premature, continuation without punctuation waits | App segment stabilized, reason, revision, length; not provider-final label |
| T9 eligibility | 600ms punctuation, 1600ms quiet fragment; tick every 250ms | 0–250ms scheduler quantization; 12s global cooldown often dominates after supersession | Separate stabilization/debounce, busy, dedup, cooldown waits |
| Text API | blocking Responses, stream=false; complete structured result + validation | Currently waits for all EN/RU options; first byte/first EN not measured | TTFT, first COMPLETE EN, complete EN+RU, full JSON, provider terminal status |
| Acceptance/display | >=2 neutral options if empty intent, reject new completed revision; manual choice stable | No stale render; can starve during continuous thought changes | Neutral-count/rejection category, old/new revision, display decision and select time |

200ms append frames and transmitting silence agree with the dedicated [translation client events](https://developers.openai.com/api/reference/resources/realtime/translation-client-events). Sending 20ms frames cannot reduce this engine frame: the server buffers short chunks. Dropping silence removes real-world pauses from model time. Translation configuration supports output language, input transcription and noise reduction; standard Realtime turn_detection/delay/custom-prompt options must not be copied into this protocol.

[Translation server events](https://developers.openai.com/api/reference/resources/realtime/translation-server-events) describe append-only word fragments, including fragments ending mid-word. elapsed_ms is alignment metadata in 200ms increments and can repeat. Use event_id for dedup; elapsed_ms is neither event ID nor wall-clock receipt time. There is no documented per-phrase final/done event in that schema. The app's punctuation/quiet stabilization is our inference.

## Actual-code offline probes

Scripts and JSON outputs: ../public-acceptance/latency-research-20261004/. They exercise the installed implementation with synthetic PCM/RU arrivals, controlled clocks and a 2000ms mock response. They do not measure real translation accuracy or latency.

Queue probe: the first complete audio frame is ready at 0.20s. A 2s sender stall in the Zoom queue produces a 1.8s-old first queued frame; an 8s stall produces 7.8s age. Overflow stops at the sixth public frame (~1.2s) or 51st Zoom frame (~10.2s). That proves possible accumulation, not that any previous real test incurred it. Local feed p95 was below 1ms in these short probes; native conversion/network were not measured. Shrinking the queue could stop a call more frequently and would not by itself accelerate provider processing. Preserve silence and fail-closed ordering.

| Scenario | Current observation with 2s mock API | Implication |
| --- | --- | --- |
| `Вы готовы?` | Dispatch 750ms, result 2750ms | Short accepted app question; real response may still fail neutrality |
| `Где?` | No segment, no request | Remaining 6-character cutoff blocks a meaningful tiny question; do not silently retune before evaluation |
| Ongoing partial after completed question | First reply remains current to that completed thought | A partial alone cannot prove semantic freshness if it begins a negation/correction |
| New completed question at 1.5s during request | Old result discarded; fresh result at 14.75s | **13.25s after replacement**: cooldown dominates, not 600ms debounce |
| 2.4s in-phrase quiet, then self-correction | Quiet fragment first committed; old response discarded; fresh at 15.75s | A speech pause can precede correction; same cooldown penalty |
| Decimal `3.` then `5 доллара.` | Two app thoughts; obsolete request discarded; fresh at 14.75s | Punctuation at delta boundary is not safe semantic finality |
| Complete thoughts every 800ms for 20s | Two obsolete requests discarded; first result 26.75s | Strict freshness avoids false answers but continuous speech can starve display |
| Continuous unpunctuated speech for 20s | First request 21s, result 23s | Quiet-required fragment path intentionally waits; no per-delta paid calls |
| Repeated completed question | Another request after 15s because bounded context now includes repetition | Current dedup is whole-context, not semantic question dedup |

## What exactly caused neutrality rejection

The real after-run's first /api/text outcome was 400 with the specific neutrality-filter error. The source predicate requires at least two retained options whose English ends in ASCII `?`, begins `Please `, or ends `, please`. Therefore that valid two/three-option result retained **zero or one** qualifying English options. Its response text was not retained: exact sentences or a claim that they specifically asserted readiness cannot be recovered.

Offline examples confirm: one question plus `Yes, I am ready.` rejects; two syntactically questioning phrases missing question marks reject; two questions pass; a declarative plus two allowed questions/requests keeps two. The predicate is syntactic, not a proof of semantic neutrality or correct RU meaning. The new empty-intent prompt requests its required forms, but has not had a paid recheck. Future diagnostics should log only input option count, retained count, format categories and result state, never a private response body. Keep the semantic prompts and local filter; do not speed up by accepting `Yes, I...` fragments.

## Correct timing boundaries

Previous 2.16s (speech end → RU observed in a 300ms poll), 2.34s (internal app-segment mark → T9 render) and 4.26s (speech end → T9 observed) do not share identical boundaries. They overlap observation gaps; **2.16 + 2.34 must not be represented as a decomposition of 4.26**. The same applies to the old values. These are separately labelled observations, not causal stage attribution or a zero-latency claim.

Use one host monotonic basis in the next public test. Python on this Mac reports `mach_absolute_time()` for time.monotonic; Swift can record mach_absolute_time with its timebase. Correlate WK performance.now to that host basis using several localhost ping round trips, retaining the minimum-RTT offset/uncertainty. Tag utterance_id, frame sequence/sample bounds, app_segment_id and request_id. Every event gets host-monotonic timestamp or a correlated client timestamp with explicit uncertainty. Acoustic onset/end, receive and actual DOM mutation must identify the same utterance. Do not use cloud_bytes/48000 (latest sent position at receipt) as the translated word's origin.

The next fixture should include two seconds of initial silence after tap readiness and identical fixed stop time for both variants. That reduces startup/source-reset ambiguity and avoids stopping one variant earlier merely because it displayed more groups. Record CPU load, sender age, API TTFT and actual usable render. Report competing CPU load explicitly; do not infer clean performance measurements from a busy host.

## Prioritized experiments, not production changes yet

1. **Same-model streaming and app-segment timing**, after installation (now complete). The [Responses streaming guide](https://developers.openai.com/api/docs/guides/streaming-responses) exposes output_text.delta and terminal completed/error events; [latency guidance](https://developers.openai.com/api/docs/guides/latency-optimization) supports measuring earlier output. Compare blocking complete JSON with streaming, marking first completed EN string, first completed EN+RU pair, the minimum validated neutral group, and terminal completion separately. Measure 600ms vs 200–300ms ONLY for an unambiguous completed short question in shadow first. A fragment, open JSON string, one unchecked option, unverified RU meaning or stale revision is not a usable answer. Preserve existing >=2 neutral-option and successful-terminal guards unless a separately reviewed experimental contract justifies earlier promotion. Parser must handle escapes, fragmented Unicode, refusal, incomplete output, Stop and supersession. One request per app segment/coalesced newest question, no partial-trigger spam. Existing cooldown is measured separately: under an interrupted response it can overwhelm all first-token gains.
2. **Source EN transcript → T9 while RU continues**, a later A/B if independently approved. Dedicated translation supports input.transcription and input_transcript.delta. It may bypass the RU→EN context round trip, but its segmentation/finality is still not guaranteed and its route/cost must be evaluated separately. Do not silently enable gpt-realtime-whisper or an extra ASR. Keep existing call/data scope and obtain the needed cost decision before dispatch.

Initial public subset: short questions including `Where?`, an in-phrase pause, self-correction/negation, numbers and one interruption. Begin with offline/shadow fixtures; do not send 50–60 API requests or speculate on every delta. Reserve before dispatch under the approved test total; old sums are irrevocable. No model switch, new quality threshold, transport rewrite or paid experiment was added by this research.
