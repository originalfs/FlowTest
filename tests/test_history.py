from localflow.history import Entry, append, read_recent


def make(i: int) -> Entry:
    return Entry(timestamp=1000.0 + i, raw=f"raw {i}", cleaned=f"clean {i}", duration_seconds=1.5)


def test_append_and_read(tmp_path):
    path = tmp_path / "h.jsonl"
    for i in range(3):
        append(make(i), path)
    entries = read_recent(path=path)
    assert [e.cleaned for e in entries] == ["clean 0", "clean 1", "clean 2"]


def test_limit_returns_most_recent(tmp_path):
    path = tmp_path / "h.jsonl"
    for i in range(10):
        append(make(i), path)
    entries = read_recent(limit=2, path=path)
    assert [e.raw for e in entries] == ["raw 8", "raw 9"]


def test_missing_file(tmp_path):
    assert read_recent(path=tmp_path / "nope.jsonl") == []


def test_unicode_preserved(tmp_path):
    path = tmp_path / "h.jsonl"
    e = Entry(timestamp=1.0, raw="héllo wörld", cleaned="héllo wörld", duration_seconds=0.5)
    append(e, path)
    assert read_recent(path=path)[0].raw == "héllo wörld"
