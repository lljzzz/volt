# Changelog

## 0.7

A big one: three new tools, a reworked UI and a long list of fixes.

New

- Notes, Text tools and Screen capture pages.
- Timers can be paused, take durations like `1h30` or an alarm time, keep running across restarts, and there's a stopwatch.
- The color picker has a magnifier and HSL output.
- The palette pastes straight into the app you were in (Shift+Enter only copies), remembers recent commands, and understands `note: ...` and `timer 10m`.
- Hotkeys are swallowed so they don't also do something in the app you're using. You can turn this off in Settings.
- Modifiers must match exactly now, so Ctrl+Y no longer fires on Ctrl+Shift+Y.
- Hotkey clashes are pointed out as soon as you set one. Esc cancels a hotkey capture, Backspace clears it.
- The window can be resized and maximized and remembers where it was. New sidebar with status badges, dashboard tiles, and shortcuts (Ctrl+1 to 9 for pages, Ctrl+K for the palette, Ctrl+F to search).
- Start minimized, portable mode, and a log file for the exe.
- New installs use Ctrl+Alt+Space for the palette, since Ctrl+Shift+P clashes with VS Code.

Fixed

- The Start button on the Autoclicker page was nearly invisible.
- Stopping a macro or the clicker halfway could leave keys or the mouse button held down.
- Clicking Stop while recording left a mouse-down at the end of the macro.
- Paste as plain text could keep pasting while Shift was held.
- Punctuation, F13 to F24, numpad operators, media keys and letters like å, ä and ö were skipped during macro playback.
- Stopping and starting the clicker quickly could leave two click loops running, and mouse shake slowly dragged the cursor off target.
- Snippets kept matching after you clicked somewhere else, and multi-line snippets pressed Enter in chat apps. AltGr characters work in triggers now.
- A key release Windows never reported (after Win+L or a UAC prompt) could set off hotkeys later.
- Anchors and the screen grid landed in the wrong place on scaled displays.
- A crash while saving could wipe the config. Saves are atomic now, and a config that won't load is kept aside instead of being replaced.
- Opening Volt twice ran two copies, so every hotkey fired twice.
- The window was taller than a 1080p screen and couldn't be resized.

Under the hood

- pywin32 is no longer needed, the 1 ms timer is only active while something is clicking or playing, and the exe went from about 46 MB to 26 MB.

## 0.6

- Dashboard switches to arm or disarm each tool's hotkeys.
- Table of every hotkey in Settings, with conflicts marked.
- Record sequence points with F7 and F8.
- Clicker can stop when focus changes and skip blocklisted windows.
- Duplicate a macro.

## 0.5

- Window nudge with snap presets in the palette.
- Color picker with a global hotkey and swatch history.
- Timers.
- Calculator in the palette.
- Export and import all settings.

## 0.4

- Nudge: move the cursor by exact pixel steps, plus anchors.
- Spinbox arrows render properly.

## 0.3

- Command palette.
- Clipboard transforms and paste as plain text.
- `build.bat` for a portable exe; the exe keeps its config in `%APPDATA%\Volt`.

## 0.2

- Snippets (text expander).
- Clipboard history with pins.
- Pin Volt on top.
- Keep the PC awake.
