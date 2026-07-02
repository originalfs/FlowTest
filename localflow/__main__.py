"""Command-line interface for LocalFlow."""

from __future__ import annotations

import argparse
import sys

from .config import Config, config_path, load_config, save_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="localflow",
        description="Private, fully local voice dictation. No cloud, ever.",
    )
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="start dictation (default)")
    run_p.add_argument("--model", help="whisper model override (tiny/base/small/medium/large-v3)")
    run_p.add_argument("--hotkey", help='hotkey override, e.g. "ctrl+alt+space"')
    run_p.add_argument("--mode", choices=("push_to_talk", "toggle"))

    file_p = sub.add_parser("file", help="transcribe an audio file (pipeline test, no mic needed)")
    file_p.add_argument("path")
    file_p.add_argument("--model")

    sub.add_parser("download", help="pre-download the whisper model, then you can go offline")
    sub.add_parser("init", help="write the default config file for editing")

    hist_p = sub.add_parser("history", help="show recent dictations")
    hist_p.add_argument("-n", type=int, default=10)

    args = parser.parse_args(argv)
    command = args.command or "run"
    cfg = load_config()

    if command == "init":
        path = save_config(cfg)
        print(f"wrote {path}")
        return 0

    if command == "history":
        from . import history

        entries = history.read_recent(limit=args.n)
        if not entries:
            print("no history yet")
        for e in entries:
            print(f"[{e.duration_seconds:5.1f}s] {e.cleaned}")
        return 0

    if command == "download":
        from .transcriber import Transcriber

        print(f"downloading/caching model {cfg.model!r}...")
        Transcriber(model=cfg.model, device=cfg.device, compute_type=cfg.compute_type).load()
        print("done — the model is cached locally; transcription now works offline")
        return 0

    if command == "file":
        from .cleanup import clean
        from .transcriber import Transcriber

        t = Transcriber(
            model=args.model or cfg.model,
            device=cfg.device,
            compute_type=cfg.compute_type,
            language=cfg.language,
        )
        raw = t.transcribe(args.path)
        print(clean(
            raw,
            remove_filler_words=cfg.remove_fillers,
            dictionary=cfg.dictionary,
            capitalize=cfg.capitalize_sentences,
        ))
        return 0

    # run
    if getattr(args, "model", None):
        cfg.model = args.model
    if getattr(args, "hotkey", None):
        cfg.hotkey = args.hotkey
    if getattr(args, "mode", None):
        cfg.mode = args.mode
    cfg.validate()

    from .app import App

    App(cfg).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
