# LocalFlow

A private, fully local voice dictation app — a self-hosted take on
[Wispr Flow](https://wisprflow.ai/). Hold a hotkey, speak, release: your words
appear at the cursor in whatever app has focus. **All processing happens on your
machine. No audio, text, or telemetry ever leaves it.**

## How Wispr Flow works (and what we replaced)

Wispr Flow is a system-wide dictation tool: a global hotkey starts microphone
capture, audio is streamed to **cloud ASR** for transcription, a second
**cloud LLM layer** removes filler words and formats the text, and the result is
injected at your cursor. It has no offline mode — every utterance leaves your
machine. LocalFlow keeps the same pipeline shape but swaps each cloud stage for
a local equivalent:

| Stage            | Wispr Flow (cloud)         | LocalFlow (this repo)                                  |
| ---------------- | -------------------------- | ------------------------------------------------------ |
| Hotkey           | native app, push-to-talk   | `pynput` global listener, push-to-talk or toggle (`hotkey.py`) |
| Audio capture    | native app                 | `sounddevice`, 16 kHz mono (`audio.py`)                |
| Transcription    | cloud ASR                  | **local Whisper** via `faster-whisper` (`transcriber.py`) |
| Cleanup / format | cloud LLM                  | local rules: filler removal, punctuation, capitalization, personal dictionary (`cleanup.py`) |
| Text insertion   | native injection           | simulated typing or clipboard-paste (`inject.py`)      |
| History          | cloud account              | local JSONL file (`history.py`)                        |

## Install

```bash
pip install -e .
```

Requires Python 3.10+, a microphone, and PortAudio
(`brew install portaudio` on macOS, `apt install libportaudio2` on Debian/Ubuntu;
bundled on Windows).

## Use

```bash
localflow download   # one-time: cache the Whisper model, then you can go offline
localflow            # start dictating: hold ctrl+alt+space, speak, release
```

Other commands:

```bash
localflow run --model small --hotkey "ctrl+shift+d" --mode toggle
localflow file recording.wav   # test the pipeline on an audio file, no mic needed
localflow history -n 20        # recent dictations (stored locally)
localflow init                 # write the default config file for editing
```

### Configuration

`localflow init` writes `~/.config/localflow/config.json`
(`%APPDATA%\localflow` on Windows):

```json
{
  "model": "base",
  "hotkey": "ctrl+alt+space",
  "mode": "push_to_talk",
  "injection": "type",
  "language": null,
  "remove_fillers": true,
  "dictionary": { "local flow": "LocalFlow" },
  "save_history": true
}
```

- **model** — `tiny`/`base`/`small`/`medium`/`large-v3`. `base` is a good
  CPU default; `small` is noticeably more accurate if you can spare ~2 GB RAM;
  use `large-v3` with a GPU (`device` picks CUDA automatically).
- **mode** — `push_to_talk` (record while held) or `toggle` (press to
  start/stop).
- **injection** — `type` simulates keystrokes (works everywhere); `paste` goes
  through the clipboard and Ctrl/Cmd+V (much faster for long dictations, and
  restores your previous clipboard afterwards).
- **dictionary** — spoken form → written form, applied case-insensitively on
  word boundaries. Use it for names, jargon, and casing (like Wispr Flow's
  personal dictionary).

### OS permissions

- **macOS** — grant the terminal *Microphone*, *Accessibility*, and *Input
  Monitoring* permissions (System Settings → Privacy & Security).
- **Linux** — works on X11 out of the box; on Wayland, global key grabbing and
  injection depend on the compositor (X11/XWayland is the reliable path).
- **Windows + GPU** — after `pip install nvidia-cublas-cu12 nvidia-cudnn-cu12`,
  the CUDA DLLs live under `venv\Lib\site-packages\nvidia\*\bin` but aren't on
  `PATH`, so `device: cuda` can fail with `Library cublas64_12.dll is not found
  or cannot be loaded`. Either add those folders to `PATH` before running:
  ```cmd
  set PATH=%PATH%;%CD%\venv\Lib\site-packages\nvidia\cublas\bin;%CD%\venv\Lib\site-packages\nvidia\cudnn\bin
  ```
  or just ignore it — LocalFlow catches this specific error and automatically
  falls back to CPU for the rest of the session (see `transcriber.py`).
- **Windows** — no special setup.

## Privacy model

- The only network access, ever, is the **one-time model download** from
  Hugging Face (`localflow download`). After that the app runs fully offline —
  you can verify by yanking the network cable.
- Audio lives in memory only; it is never written to disk.
- Transcripts are saved only to a local file (`~/.local/share/localflow/history.jsonl`),
  and only if `save_history` is true.

## Development

```bash
pip install -e ".[dev]"
pytest
```

The hardware-touching modules (`audio`, `inject`, `hotkey` listener) import
their dependencies lazily, so the pure logic (cleanup, config, history, combo
parsing, hotkey edge detection) is unit-tested without a mic or display server.
