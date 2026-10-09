# Runtime state and branding

Keep the following identities stable when changing display/repository branding:

- Keychain service `local.calmtranslate.openai`, account `user-entered`.
- Desktop bundle `local.calmtranslate.desktop`, capture bundle `local.calmtranslate.desktop.capture`.
- UserDefaults desktop domain and `Calm Translate` Application Support directory.
- Named window frame autosave and private application-only Keychain pipe.

Only display title, About/menu text, CFBundleName/CFBundleDisplayName, documentation and repository slug should be branded. Renaming a repository is not authorization to rotate credentials, grant OS access, move/delete existing user state or reset budget/STOP decisions. Install/update must verify the destination is the user's own app and preserve its data.

Normal app data: `~/Library/Application Support/Calm Translate`; initialize defaults only if each file does not exist. The source defaults contain no actual user approval, personal timestamps, account usage or credentials. Test mode uses `/tmp/calm-translate-verification-data` and UserDefaults suite `local.calmtranslate.desktop.verification` rather than modifying normal app state.

Neither an original capture permission nor Transcrybe permission transfers to a new helper automatically. Any future helper rebuild or identity change requires reviewing OS access separately; never bypass Gatekeeper/TCC. Captions/replies are session RAM, not an on-disk conversation archive.
