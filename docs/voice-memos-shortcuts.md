# Voice Memos Shortcut Setup

Use Voice Memos as the capture surface and let `siri` pull the finished `.m4a` from the synced macOS Voice Memos store.

## Capture shortcut

Build the shortcut like this:

1. `List`
   - `monde`
   - `reflection`
2. `Choose from List`
3. `Current Date`
4. `Format Date`
   - Suggested format: `yyyyMMdd-HHmmss`
5. `Text`
   - `${Selected Item}__${Formatted Date}`
6. `Create Recording`
   - recording name: the `Text` output above

If you want the simplest possible shortcut, using bare titles is also fine:

- `monde`
- `reflection`

Voice Memos will auto-number duplicates like `monde 2` or `réflection 2`, and the importer still routes them correctly.

## Import behavior

`src/import_voice_memos.py` reads the Voice Memos library at:

- `~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings`

It inspects each new Voice Memo with `ffprobe`, extracts the recording title, normalizes the route prefix, and exports the `.m4a` to:

- `${VOICE_MEMOS_EXPORT_ROOT}/monde/`
- `${VOICE_MEMOS_EXPORT_ROOT}/reflection/`

It also writes a JSON sidecar next to the exported audio with the original title, Voice Memos UUID, source path, and recorded timestamp.

## Cleanup shortcut

If you want the original recording deleted from Voice Memos after a successful export, create a second macOS shortcut and set its name in `VOICE_MEMOS_DELETE_SHORTCUT`.

Suggested shortcut behavior:

1. Shortcut input: `Text`
2. `Search Voice Memos`
   - Name `is` Shortcut Input
   - Sort by `Date`, newest first
   - Limit `1`
3. `Delete Recordings`

`src/import_voice_memos.py` calls it with:

```bash
shortcuts run "$VOICE_MEMOS_DELETE_SHORTCUT" --input-path /tmp/title.txt
```

## Notes

- Export format should stay `.m4a`; it is already what Voice Memos stores and what the rest of the pipeline expects.
- Route matching is accent-insensitive, so `réflection__20260329-181200` still normalizes to `reflection`.
- If `VOICE_MEMOS_DELETE_SHORTCUT` is unset, the importer only exports and leaves the Voice Memo in place.
