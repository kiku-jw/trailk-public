# Offline application QA, 2026-10-14

The runtime source at PR #1 de38ebf was rebuilt into a fresh, uninstalled macOS app.
The declared pinned build requirements installed in an isolated Python environment.
The frozen backend self-test confirmed Python 3.14.6, verified TLS roots,
websockets 15.0.1 and bundled web assets. Native helper/main compilation and strict
deep signature verification passed. The app bundle is about 40.5 MiB; this is an
ad-hoc signed development artifact, not a notarized release.

The first iconutil conversion failed inside the execution sandbox with Invalid
Iconset. All ten PNG names, dimensions and 8-bit RGBA formats were valid. Approved
macOS conversion of the identical input and a fresh full build succeeded. This
was a tooling restriction rather than a source asset defect. No denial was bypassed.

## Verified scope

- 156 Python tests, 59 JavaScript tests and native PCM/process-scope checks pass.
- Actual frozen localhost backend fresh capture/text gates, wrong token/Host,
  offline mock response and served assets pass; served app/integration/karaoke
  bytes match the working source.
- Actual headless Chromium consumes the frozen assets and local backend. With a
  completed synthetic target, manual replay Stop before stabilization keeps zero
  new T9 cards; explicit Start enables hints again. The selected/edited English,
  numbers and negations match karaoke exactly; Stop pauses reading and stale ticks
  cannot advance it. Natural-end final-hint behavior is also covered by the actual
  app+integration DOM regression.
- Desktop dark and 560px light layouts preserve selected text, stay centered and
  have no horizontal overflow. Screenshots were inspected in the headless viewport.
- A synthetic local profile saves/reloads and clears through the actual UI/backend.
  The in-memory selected answer clears on reload, as expected.
- Parent-pipe EOF stops the frozen child. A deliberate new child starts with gates
  and the cleared profile preserved, then also exits on EOF.
- Actual AppKit/WKWebView verification passed 58 checks on the first run and 59
  on a complete process relaunch. Native Start/Stop, synthetic profile and reader
  state, light/dark/narrow layouts, Close/reopen and deliberate child failure with
  manual recovery passed. Screenshots of the owned app window were inspected.
- An accessibility check in the actual WK window started and paused karaoke;
  button state changed correctly and selected English stayed unchanged.

The native GUI run used a metadata-only QA copy of the already built app, with a
distinct bundle identifier to isolate window preferences. Application code was
not rebuilt or changed for this copy. Existing screen/accessibility permissions
were checked without requesting new permissions. The verification-only preference
suite was backed up and restored exactly; the production profile was not used.
All owned QA app/backend/browser processes exited after the checks.

The application runtime used a new QA-only data root, a nonexistent credential
bridge and CALM_VERIFY_OFFLINE=1. Browser requests were limited to the localhost
origin. The replay data and edited/profile text were synthetic; no real model
probe, user call, capture, microphone or private audio was used. Offline output is
not translation-quality evidence. QA profiles/logs/screenshots are excluded from
Git publication.

## Remaining acceptance scope

The offline native application gate passed. This evidence covers synthetic replay,
UI and process lifecycle; it does not establish real-call translation quality or
device behavior. No installation, release or merge was performed.

A real Zoom smoke of 3–5 minutes needs distinct authorization and a permitted
source. It was not attempted. Long calls, device changes, source-language STT,
diarization and real speech/first-token latency remain unverified or unimplemented
as described in REALTIME-HINT-CONTROL.md.
