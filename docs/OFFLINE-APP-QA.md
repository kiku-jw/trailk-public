# Offline application QA, 2026-10-14

The source based on PR #1 a82b6a0 was rebuilt into a fresh, uninstalled macOS app.
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

The application runtime used a new QA-only data root, a nonexistent credential
bridge and CALM_VERIFY_OFFLINE=1. Browser requests were limited to the localhost
origin. The replay data and edited/profile text were synthetic; no real model
probe, user call, capture, microphone or private audio was used. Offline output is
not translation-quality evidence. QA profiles/logs/screenshots are excluded from
Git publication.

## Remaining acceptance gate

Chromium/DOM checks do not prove AppKit/WKWebView behavior. A coordinated Mac GUI
window with no competing user activity is still required for the actual native
verification lifecycle, camera layout/reader, Stop, Close and recovery. The current
native verification command opens a real window; it was not run during the shared
GUI restriction. No installation, release or merge was performed.

A real Zoom smoke of 3–5 minutes needs distinct authorization and a permitted
source. It was not attempted. Long calls, device changes, source-language STT,
diarization and real speech/first-token latency remain unverified or unimplemented
as described in REALTIME-HINT-CONTROL.md.
