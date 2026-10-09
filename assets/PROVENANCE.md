# Third-party provenance

- Native capture source is an original implementation informed by AudioCap's process-scoped CoreAudio lifecycle pattern. Reference: https://github.com/insidegui/AudioCap at commit 6f609e8ad1b1e11fa0e8edbe91864cb099f00de3. Copyright (c) 2024 Guilherme Rambo, BSD two-clause license retained in AudioCap-LICENSE.txt. Source and binary distributions must retain the applicable notice; the bundled helper includes it.
- Public offline audio: Leo Varadkar and Houses of the Oireachtas, 14 June 2017. https://commons.wikimedia.org/wiki/File:Leo_Varadkar%27s_first_speech_as_Taoiseach_elect.opus ; CC BY 4.0, https://creativecommons.org/licenses/by/4.0/. Changes: source interval 01:00–03:30, mono 24 kHz PCM16. Original metadata/hash: public/source.json. The file is a public test fixture, not a user meeting recording.
- CPython: PSF license and included third-party terms in ThirdParty/Python-LICENSE.txt.
- websockets 15.0.1: BSD three-clause license; certifi 2025.11.12: MPL 2.0. Their original notices are retained under ThirdParty/.
- PyInstaller 6.22.2: original GPL terms and bootloader exception are retained under ThirdParty/pyinstaller-6.22.2.dist-info/. Build-tool dependency notices are also retained. The exception governs embedding the bootloader; this snapshot does not claim to relicense PyInstaller itself.
- System frameworks (AppKit, WebKit, CoreAudio, AVFoundation, Security) are provided by macOS; no Apple SDK framework implementation is copied into this repository.
- Remote OpenAI models are optional hosted services, not bundled open-source weights. No provider keys or transcripts are distributed. Paid transport and audio are disabled by default and require separate authorization.

Sokuji, Mimi and other projects were research references only; no AGPL implementation or external model weights are bundled in this source snapshot. Do not interpret research citations as copied source or a project-wide license grant.
