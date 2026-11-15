# Volt

Autoclicker, macros, clipboard history and everyday Windows tools in one app. Automate repeated clicks, turn short triggers into full messages, and retrieve text or images you copied earlier. Open a tool from the sidebar or press **Ctrl+Alt+Space** to search from any app.

Free and open source, for Windows 10 and 11. No installer or account required. [See the demos and download Volt](https://lljzzz.github.io/).

![The Volt dashboard with the sidebar of tools, status cards and per-tool hotkey switches](https://lljzzz.github.io/img/dashboard.webp)

## What's in it

**Automate**

- Autoclicker. Clicks per second, minute or hour, or an exact interval. Random timing variation, click sequences and drags, stop after N clicks or seconds, and window failsafes (only click in one window, never in a blocklisted app, stop when focus changes).
- Macros. Record keyboard and mouse input, edit the steps, replay with a hotkey. Repeat, loop or change the speed. Keys are sent as scan codes, so they work in most games.
- Snippets. Type `;sig` anywhere and it turns into your signature. Supports `{date}`, `{time}`, `{clipboard}` and `{cursor}`.

**Productivity**

- Clipboard history with search, pins and 25 "copy as" transforms (case, Base64, JSON, hashes and so on). Copied images and screenshots are kept too, with thumbnails. Copies marked private by password managers are skipped by default.
- Notes that save as you type.
- Text tools: the same transforms, plus UUID, password and timestamp generators.
- Timers, alarms and a stopwatch. Running timers survive a restart.

**Screen**

- Screen capture. Drag a region and it goes to the clipboard and a PNG. You can pin a capture so it floats on top of everything.
- Color picker with a magnifier. Copies HEX, RGB or HSL.
- Nudge. Move the cursor or the active window pixel by pixel from the keyboard, and jump the cursor to saved spots.

The palette ties it together. Press Ctrl+Alt+Space in any app and start typing: run a macro, paste an old clipboard entry, start a timer (`timer 10m`), save a note (`note: call dentist`), do some math, snap a window to half the screen.

<img src="https://lljzzz.github.io/img/palette-demo.png" width="620" alt="The quick palette: typing timer 10m offers a timer, 1299*0.24/12 shows 25.98, image lists copied images, note: buy milk adds a note, and snap lists window snap options">

Choose Dark or Light, or let Volt follow your Windows theme. Five accent colors are available in Settings → Appearance. [Try every combination on the website](https://lljzzz.github.io/#appearance).

![Real Volt controls in Orange, Blue, Teal, Pink and Violet, with Dark and Light examples for each accent](https://lljzzz.github.io/img/accents.webp)

Clipboard history keeps images as well as text. Pick one to see it full size, copy it back, save it as a PNG or float it on top of your other windows.

![The Clipboard page in the light theme with a copied chart selected and shown in the preview, above text entries and a pinned color code](https://lljzzz.github.io/img/clipboard-light.webp)

## Download

Get `Volt.exe` from the [releases page](https://github.com/lljzzz/volt/releases). It's one portable file with no installer, for Windows 10 or 11 (64-bit).

Volt 0.8 is unsigned, so Windows may show an unknown-publisher or SmartScreen warning. See the [download notes](https://lljzzz.github.io/#windows-warning) for details. Each release includes a SHA-256 checksum.

To update, quit Volt from its tray menu, replace `Volt.exe` and reopen it. Keep your data folder; in portable mode, also keep the `portable` marker and `VoltData` folder beside the EXE.

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
| Show or hide Volt | not set |

You can change all of them. Settings has a table of every hotkey with clashes marked. By default a Volt hotkey isn't passed on to the app you're in, so Ctrl+Y won't also trigger redo.

## Your data

Your clipboard, notes and settings stay on your PC. Volt has no accounts, tracking or cloud sync. Settings, notes and clipboard text/metadata are saved as JSON in `%APPDATA%\Volt` (or in the project folder when you run from source). To keep data beside the EXE, put an empty file named `portable` there; Volt then uses the adjacent `VoltData` folder.

Clipboard history stays in memory by default. Pinned images are saved as PNGs in `clipboard_images` inside the data folder. Turning on "Remember history across restarts" also saves unpinned history there; unpinned images larger than 12 MB remain in memory only. Up to 20 unpinned images are kept within a 48 MB PNG-data budget, subject to your overall history-size setting. Pins are kept separately. Screen captures and images you save manually go to the folder you choose.

## Checking changes

Run `python tests/harness.py` with the dependencies installed. It uses an offscreen Qt window, isolated temporary data and simulated input to check the app without changing your settings or sending real clicks and keystrokes. It prints the path to its screenshots and test data.

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
