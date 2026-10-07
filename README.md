# Volt

A small Windows app that rolls a bunch of everyday tools into one: an autoclicker, macros, a text expander, clipboard history, quick notes, text tools, screenshots, a color picker, keyboard cursor control and timers. It sits in the tray and you mostly use it through hotkeys or the quick palette (Ctrl+Alt+Space).

## What's in it

**Automate**

- Autoclicker. Clicks per second, minute or hour, or an exact interval. Random timing variation, click sequences and drags, stop after N clicks or seconds, and window failsafes (only click in one window, never in a blocklisted app, stop when focus changes).
- Macros. Record keyboard and mouse input, edit the steps, replay with a hotkey. Repeat, loop or change the speed. Keys are sent as scan codes, so they work in most games.
- Snippets. Type `;sig` anywhere and it turns into your signature. Supports `{date}`, `{time}`, `{clipboard}` and `{cursor}`.

**Productivity**

- Clipboard history with search, pins and 25 "copy as" transforms (case, Base64, JSON, hashes and so on). Copies from password managers are skipped.
- Notes that save as you type.
- Text tools: the same transforms, plus UUID, password and timestamp generators.
- Timers, alarms and a stopwatch. Running timers survive a restart.

**Screen**

- Screen capture. Drag a region and it goes to the clipboard and a PNG. You can pin a capture so it floats on top of everything.
- Color picker with a magnifier. Copies HEX, RGB or HSL.
- Nudge. Move the cursor or the active window pixel by pixel from the keyboard, and jump the cursor to saved spots.

The palette ties it together. Press Ctrl+Alt+Space in any app and start typing: run a macro, paste an old clipboard entry, start a timer (`timer 10m`), save a note (`note: call dentist`), do some math, snap a window to half the screen.

## Download

Get `Volt.exe` from the [releases page](https://github.com/lljzzz/volt/releases). It's one portable file with no installer, for Windows 10 or 11 (64-bit).

The exe isn't code-signed, so SmartScreen will probably warn you the first time. Click More info, then Run anyway. Some antivirus tools also flag it because it simulates keyboard and mouse input, which is kind of the point of an autoclicker. Volt has no network code at all, and the source is right here if you want to check.

## Running from source

You need Python 3.10 or newer.

```
git clone https://github.com/lljzzz/volt.git
cd volt
pip install -r requirements.txt
python main.py
```

Or run `run.bat`, which sets up a virtual environment the first time.

## Building the exe

```
build.bat          single file: dist\Volt.exe
build.bat fast     folder build: dist\Volt\Volt.exe (starts faster)
```

The build settings are in `Volt.spec`. It leaves out the parts of Qt that Volt doesn't use, which keeps the exe around 26 MB.

## Default hotkeys

| Action | Keys |
|---|---|
| Quick palette | Ctrl+Alt+Space |
| Stop everything | Ctrl+Shift+M |
| Autoclicker on/off | Ctrl+Y |
| Paste as plain text | Ctrl+Shift+V |
| Capture a region | Ctrl+Shift+X |
| Pick a color | Ctrl+Alt+C |
| Nudge the cursor | Ctrl+Alt+Arrows (add Shift for bigger steps) |
| Move the active window | Win+Alt+Arrows (add Shift to resize) |

You can change all of them. Settings has a table of every hotkey with clashes marked. By default a Volt hotkey isn't passed on to the app you're in, so Ctrl+Y won't also trigger redo.

## Your data

Volt never connects to the internet. Everything is saved as JSON in `%APPDATA%\Volt` (or in the project folder when you run from source). If you want it all next to the exe, say on a USB stick, put an empty file named `portable` beside `Volt.exe`.

## A note on games

Plenty of online games don't allow autoclickers or macros. Check the rules before you use Volt with one. If an account gets banned, that's on whoever ran the macro, not the tool.

## Project layout

```
main.py         main window, tray, navigation
core/           the engines: hotkeys, clicker, macros, snippets, clipboard, timers
ui/             one file per page, plus shared widgets and styles
assets/         small images the app uses (icon, checkmarks, arrows)
```

## License

MIT, see [LICENSE](LICENSE). What changed in each version is in [CHANGELOG.md](CHANGELOG.md).
