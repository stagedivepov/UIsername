# UIsername v8.6

- App-styled cancellation dialog: Continue or Confirm cancellation.
- Shared by standard checks, advanced generation and Identity Checker.
- Confirmation enabled by default, including a one-time migration for older settings;
  users can keep using the existing confirmation preference.
- Settings speed control uses integer milliseconds, 0 to 600,000, with quick presets.
- Existing stored seconds convert transparently to milliseconds in the UI.
- Advanced local generation now observes the interval and uses interruptible waits.
- Platform minimum delays and batch pacing preserved. Changes apply to the next run.
- All new UI strings translated into all seven supported languages.

Windows x64 executable compiled with PyInstaller. No automated tests or runtime UI
verification performed for this revision.
