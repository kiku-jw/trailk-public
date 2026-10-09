# Realtime hint control and reading aid

This branch adds an original implementation of bounded automatic-hint scheduling,
transport cancellation, numeric latency summaries and a reading aid. No external
project code is incorporated. It does not install an application or alter device
permissions, credentials, provider routing or transcript retention.

## Existing audio architecture

The Swift capture helper feeds 24 kHz mono PCM through a Unix socket into a bounded
PCM queue. A dedicated WebSocket worker sends 200 ms frames and receives translated
text concurrently. HTTP text requests run separately, so a slow hint does not stop
audio ingestion or translated-caption updates. Overflows and stale audio stop the
stream rather than replaying obsolete speech. Planned provider-expiry renewal
preserves the approved source and shared budget; unexpected disconnects stop.

Source-language English STT is not enabled (`input_audio_transcription` is absent).
The application consumes translated text. Capture has no own microphone channel,
and mixed Zoom audio does not identify individual speakers. Punctuation and silence
are application segmentation signals, not reliable speaker evidence.

## Automatic hint requests

The backend permits one active automatic hint plus one pending hint. A newer
generation cancels the active job and replaces any pending job. Cancelled pending
work cannot reserve budget or read a credential. The authenticated cancellation
route checks the current audio run and records cancellations that arrive before
submission. Late cancellations for an old generation cannot cancel a newer job.
Stop, capture stop, profile changes and parent shutdown revoke automatic hints.
The run, consent and profile revision are checked before queued work and again
before accepting its result.

The browser aborts its fetch when context changes, automatic suggestions are
disabled, Stop occurs or the page closes. It also sends a metadata-only cancellation
request to the local backend. A bounded replacement remains subject to the existing
debounce, two-dispatch sliding cap and no same-context retry. Server-side cancellation
still protects the result if the browser has already disconnected. A restarted page
seeds its monotonic generation counter from the local clock; a clock rollback can
cause rejection until a new manually started session resets the queue.

Provider HTTP has a 30-second overall control deadline from submission, a 10-second
socket inactivity limit, a 64 KiB response limit, verified TLS, no proxy discovery,
no redirects and no retries. Cancellation shuts down the active socket to wake
blocked header/body reads. Connect is explicit and cancellation/deadline is checked
before sending HTTP headers or a body; a closed connection cannot auto-reopen.
OS DNS resolution and a credential-helper call are not
interruptible Python operations; those can outlive the control deadline, while the
job is revoked and cannot display a result. The application never claims cancellation
undoes an already sent provider request or its billing. Existing reservations are
kept after cancellation, failure and incomplete responses.

Manual typed translations retain their existing display cancellation. They are
not placed in the automatic-hint queue. All text requests share the bounded HTTP
transport, and the adapter retains its one-request lock and approval/budget guards.

## Latency measurements

In-memory windows retain at most 128 numeric observations. The backend exposes
queue waiting time, request lifetime and cancellation counts. The browser records
segment/context readiness to dispatch, request to response, and request to accepted
render. Settings show p50/p95 for accepted request-to-render results and queue state.
Session/mode changes reset the browser window. No conversation text, provider body,
profile or credential is added to these metrics or written to disk.

These are application timings. They do not measure actual speech end, source STT
latency, provider first-token latency, screen paint or a hardware end-to-end latency.
Production LLM output remains a fully validated JSON group (`stream: false`); the
Responses SSE experiment remains disabled. Enabling streaming still requires a
terminal-success protocol and validation before displaying partial choices.

## Karaoke reading aid

An explicitly selected or edited English answer is repeated near the camera with
word highlighting. Original whitespace, punctuation, numbers and negations are
preserved. Play is manual; the default pace is 180 words/minute, with 120/240 choices.
Space pauses and arrow keys or a word click move the position. A new selection or
edit resets the reader; an automatic hint batch does not replace selected English.
Stop in either live or replay mode and page close interrupt reading; hiding the
page pauses without auto-resume.
Stale timer callbacks cannot advance a newly selected answer. The highlight uses
an underline plus the existing light/dark theme colors, without animation.

This is a paced reading aid, not speech-aligned highlighting. It records no audio
and neither sends text to Zoom nor synthesizes speech. Word timestamps, own speech
alignment and a separate overlay window remain future work.

## Verification and remaining work

Offline tests cover newest-pending selection, early/late cancellation races, budget
reservation preservation, actual authenticated local routes, blocked HTTP headers,
idle/dripping bodies, cancellation during connect with zero HTTP bytes, closed-socket
reopen prevention, status/size limits, frontend abort wiring, transcript continuity,
numeric percentile windows, karaoke DOM/model lifecycle and the actual replay
session-button Stop path. Existing native PCM
checks provide deterministic conversion and process-scope evidence only.

GUI, built-app packaging, real Zoom capture, Keychain, microphone, device changes,
long calls and visual camera position were not exercised for this branch. Source STT,
production streaming LLM, reliable diarization, speech-aligned karaoke and true
speech-end-to-display/TTFT measurements remain unimplemented. The draft PR is not
a tested release build.
