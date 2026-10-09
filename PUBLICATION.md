# Public source snapshot

This repository starts with a new history from Trailk 1.5.2 (build 16), local source commit `a931557bdaa73fbc3607a64406512470ebf23ae5`. All 132 original tracked files were read and their working bytes matched the Git index. No earlier Git history or runtime state is transferred.

Publication preparation removes two local user paths, private conversation references and historical account spending details from documentation. The existing licensing scope and third-party notices remain. One regression test now uses a self-contained synthetic fixture instead of reading an external engineering report. Application behavior is unchanged in this initial snapshot; realtime improvements belong to a subsequent branch.

Review included credential-format and secret-literal checks, credential URLs, private network/user-path checks, high-entropy literal review, file-type inventory, configuration/seeds, synthetic fixture provenance, public audio checksum and manual documentation review. No detected provider credentials or private call transcripts are included. Scanner coverage and manual review are finite; this is not a guarantee that every possible secret format can be detected.

Only binary asset: the attributed public speech fixture described in `assets/public/source.json`; its SHA-256 matches that metadata. Copyright holder emails in retained third-party license notices are public attribution and remain intact. Fresh approval seeds deny capture/cloud/text requests and preserve the audio stop. User profiles, receipts, logs, databases, credentials and installed applications are excluded.

Local offline verification: 137 Python tests, 48 JavaScript tests and deterministic native PCM/process-scope checks pass. Provider, Keychain, capture/playback, hardware device changes, display/Spaces behavior and long Zoom calls were not exercised. CI runs the Python and JavaScript checks without provider credentials.
