# Changelog

## 0.8

Mostly fixes, plus a light theme.

New

- Light theme, and a Match Windows option that follows the Windows app mode and switches when it does. There are five accent colors too. It's all under Settings, Appearance.
- A Search button at the top of the sidebar opens the palette and shows its hotkey.
- An optional hotkey to show or hide the Volt window. It's off until you set one in Settings.
- New installs get a short welcome card on the Dashboard.
- Export settings now includes your notes. Importing a backup adds its notes to the ones you have instead of replacing them.
- Timer durations can have decimals (`1.5h`, `2.5m`), and automatic labels read like "1 h 30 min timer".
- The autoclicker's "Only click in this window" box accepts typed text, so it can match part of a title.

Fixed

- Paste as plain text pasted an older clipboard entry, and put it back on the clipboard, when the current copy came from a password manager or wasn't text.
- If the clipboard contained the text `{cursor}`, a snippet using `{clipboard}` moved the caret.
- The snippet editor said the longest trigger wins when one trigger was the start of another, like `;d` and `;date`. Actually the shorter one fires first and the longer one never fires. The warning now says so.
- Snapping a window to a half or a quarter of the screen left a gap of about 7 px at the sides and bottom on Windows 10 and 11.
- Clicking the tray icon while Volt was in front didn't hide it.
- The palette and the capture overlay could open without keyboard focus when the hotkey had no Alt in it.
- Selecting another macro while recording put the recording into the wrong one.
- A key that was already held when recording started left a stray key release in the macro.
- If the window the autoclicker was locked to closed, the dropdown showed a different window than the saved one.
- Empty notes piled up as "Untitled note". A blank note is now removed when you leave it.
- A hand-edited config with a macro missing its name, hotkey or actions could crash Volt at startup. Broken entries are repaired when the config loads.
- Long notices stretched across the screen. They wrap now.
- The clipboard page said "1 entries".

Under the hood

- Running timers no longer restyle the Dashboard and Timers pages twice a second, the color picker grabs the screen once per update instead of twice, and the clipboard list only rebuilds while it's on screen.

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
