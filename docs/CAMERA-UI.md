# Camera-centered UI — 1.3.0, build 7

Stable Russian caption at upper center, separate partial line, English T9 immediately below. No automatic selection, speech or send. Russian meaning is optional; history, other choices, typed intent and settings start folded. Dark default, light/system options, font 18–38, native minimum 540×580. Chosen text and reading position persist across incoming groups, theme and resize; focused/hovered suggestions stay still while reading.

4 October validation: 57 Python tests, 24 JavaScript tests, 35 actual AppKit/WKWebView checks. Includes repeated Start/Stop, settings, local backend recovery, immutable history/reading position, manual selection, themes/contrast, font, narrow resize, and keyboard events dispatched to the product handler. Synthetic data does not measure translation quality. Additional actual-source JS checks verify delayed Stop status/button and prevent reopening capture during shutdown.

One paid public test: Blender Elephants Dream excerpt source seconds 46–110; own player → CATapMuted → production OpenAI streaming adapter → installed 1.3.0 web assets in dedicated WK host. No Zoom/private call/microphone. Captured 68 seconds including silence, one API connection, two text requests, one displayed T9 group, 11 stable rows. Manual answer and paused history stayed unchanged. First partial/committed translation 4.79/5.69 seconds after UI Start; T9 31.20 seconds. Text transports 1.69/2.20 seconds. Speech onset was not independently annotated: these are startup/transport observations. The displayed group was already stale. First completed request produced no displayed group; its response body was not retained, so the cause is not asserted. No quality, hour-long performance or API reconnect claim.

Public test exposed Stop status overwriting during shutdown. Fixed offline afterward: explicit Stop overrides waiting-for-Zoom, disables repeated Stop while closing and blocks reopening native capture. Native checks passed again; no paid rerun. Real screenshot predates this fix and retains the inherited Zoom waiting label despite public-player source.

Historical account balances, spending authorizations and request-cost details are omitted from the public snapshot. Earlier test observations are historical; no live provider verification is claimed by this publication.

Evidence: ../public-acceptance/camera-ui-20261004/ and ../public-acceptance/camera-live-20261004/.
