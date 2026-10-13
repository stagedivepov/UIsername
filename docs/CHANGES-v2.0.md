# UIsername v2.0

- Added About us in Settings, describing the solo project and its mission to offer a free alternative for username generation/checking. Localized in all seven UI languages.

- Preferences visual changes applied only when language/theme/layout values change.
- Batch checkbox handled once per change instead of input and change duplicating saves.
- Unchanged drafts no longer trigger full reapplication or unnecessary saves.
- Bounded hidden switch inputs prevent focus targets outside their visible controls.
- Settings header/footer remain fixed; body retains its own constrained scrolling.
- Backdrop pointer click closes Settings through its existing validation/save flow.
- Closing guarded against repeated clicks and accidental inside-to-outside drags.

Windows x64 executable compiled with PyInstaller. No automated tests or runtime UI
verification performed for this revision.
