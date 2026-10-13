# UIsername v8.3

- Settings now includes a shared proxy editor: paste, import .txt, clear, local automatic saving and format counts.
- Proxy use remains optional, restricted to compatible platform checks. Saving the list does not enable proxies.
- Session history adds Archive, Restore and Delete actions and a separate archived section below history.
- Archiving preserves statistics and results. Deleting removes SQLite session results/events atomically and recalculates statistics; exported username files remain available.
- Running sessions cannot be archived or deleted. Deleting asks for confirmation with a second click.
- Database schema 3 migrates existing sessions without resetting user history.
- New controls translated into all seven supported languages.

Build: Windows x64 executable produced with PyInstaller. No automated test suite was run for this revision.
