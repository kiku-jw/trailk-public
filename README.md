# Trailk

**Live conversation translation.**

A local macOS window for readable English → Russian captions and preparing your own Russian thought as simple spoken English. Stable committed lines, a separate current block, adjustable font, reading pause/follow, manual English selection/editing and paired suggestions. Automatic T9 drafts are offered for human choice; no automatic selection, sending to Zoom or speech synthesis.

This source snapshot uses a Swift AppKit/WKWebView host, a frozen Python localhost child and a separately gated native capture helper. macOS 26+, Apple Silicon, Xcode command-line tools for building. Python, verified TLS roots and WebSocket dependencies are embedded in the resulting app; Terminal and a browser are not required to use the built app. Real long-duration Zoom translation remains unverified. Offline replay/mock is a UI test, not translation-quality evidence.

## Build

```sh
python3 -m venv .build-env
.build-env/bin/python -m pip install -r requirements-build.txt
CALM_BUILD_STAGE=/tmp/calm-translate-fresh ./build.sh
```

Build output is `Trailk.app` inside the selected fresh stage. The script refuses to overwrite an existing stage app. Code is signed ad-hoc locally; no notarization/account, publication or security-setting change occurs. Dependencies come from pinned PyPI packages. The public test audio and third-party notices are included.

The Keychain helper can be compiled from `keychain/KeychainBridge.swift`. For a local build that must preserve an already approved helper's exact binary/signature, pass an explicitly chosen existing helper path with `CALM_KEYCHAIN_HELPER=/absolute/path/keychain-bridge`. The builder only copies that binary; it never reads a Keychain item. A freshly compiled helper may require a future user-controlled OS access confirmation. Do not automatically re-save, delete or request an existing key.

Copy the built app to `~/Applications` using Finder, without replacing an unrelated app. The source snapshot does not modify an installed application automatically. See docs/STATE-AND-IDENTITY.md for stable identities and runtime state.

## Offline checks

```sh
.build-env/bin/python -m unittest discover -s tests -v
.build-env/bin/python -m py_compile src/*.py
node --check assets/web/app.js
node --check assets/web/integration.js
node --test tests/*.test.js
swiftc src/capture/CaptureCore.swift tests/native_core.swift -o /tmp/calm-native-core-check
/tmp/calm-native-core-check
```

Python tests use temporary directories, local loopback and mock transport; no provider or Keychain reads. Native core checks exercise deterministic PCM conversion and process-scope policy without capture/playback. Node is needed only for optional development syntax checks, not app use.

A deliberate `--verify-lifecycle` app launch uses a separate verification data directory/preferences suite and synthetic fixtures. The test can inspect the live WKWebView, append synthetic bursts, verify font/reading position, choose/edit mock replies, close/reopen and manually recover from own backend failure. A second launch with `--expect-persisted-settings` checks the verification suite persisted font 34 across processes. Output: `/tmp/calm-translate-verification-proof`. These flags do not launch capture or call providers; run them only for development. Background WebKit timers can throttle, so synthetic burst tests do not measure streaming latency.

## Default safety/state

Fresh source installs seed generic disabled approvals and an audio STOP. No provider request or capture starts at app launch. Existing runtime approvals/budgets/STOP are never overwritten by seed initialization. A zero fresh reservation ledger is not an API permission; separate explicit consent is required before any key/network operation. Attempts reserve conservative limits before key/network and are not automatically refunded/reconciled with estimates. Actual billing is separate.

Font/mode/follow and window position persist. Captions, typed intent and selected English stay in RAM and are cleared on a new window. Close stops the app's own child; reopening starts a new local server. Quit/host failure stops it through parent-pipe EOF. A process lock prevents duplicate app instances. The app rejects external navigation and WebKit media permissions.

Optional OpenAI translation uses the dedicated Realtime translations WebSocket with 24 kHz mono PCM, bounded input, text deltas and close/drain. It is not ordinary chat-proxy compatibility. Typed intent uses separately gated Responses JSON output. Neither starts on launch. This public snapshot contains the existing 1.5.2 source (build 16), based on the audited local commit `a931557bdaa73fbc3607a64406512470ebf23ae5`, with a fresh public history. Camera-centered captions, automatic manual-choice T9 suggestions, editable local personal context, optional explicitly approved unlimited spending, and existing quality guards are included. Source-language transcription, microphone capture and multispeaker diarization are not enabled. Unexpected audio disconnects stop capture without replay; planned provider-expiry renewal uses the same approved source and shared budget. Production hints return a fully validated JSON group; the SSE experiment remains disabled. Real long-duration Zoom and device-change behavior are unverified.

Only source, tests, public/synthetic fixtures and required third-party notices are included. Runtime approvals, user profiles, receipts, transcripts, logs, databases, credentials and the old Git history are excluded. Historical engineering documents are version-specific; account spending details and local user paths have been removed. Test affiliations, identities and conversation text are synthetic fixtures, not user settings.

See LICENSE-NOTICE.md and assets/PROVENANCE.md. No project-wide open-source license is selected for original code in this snapshot. Third-party terms remain intact.

Naming research and its limits: docs/NAME-RESEARCH.md.

Historical 1.3.4 notes: camera-centered dark/light interface, completed-segment freshness and approved estimated text reserve. See [latest reply context](docs/LATEST-REPLY-CONTEXT.md), [freshness fixes](docs/FRESHNESS-FIXES.md), [latency evidence](docs/LATENCY.md), [camera UI](docs/CAMERA-UI.md) and [budget policy](docs/MONETARY-UX.md).

[Real-world latency research and offline scenario matrix](docs/REAL-WORLD-LATENCY.md).
