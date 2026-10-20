from urllib.request import urlopen

import pytest

from cli.server import serve, shutdown


def test_serves_repo_and_input(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "index.html").write_text("<html>")
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "a.mp3").write_bytes(b"ID3xxx")
    (inp / "子 目录").mkdir()
    (inp / "子 目录" / "歌.lrc").write_text("hi", encoding="utf-8")
    base = serve(str(repo), str(inp))
    try:
        assert urlopen(base + "/index.html").read() == b"<html>"
        assert urlopen(base + "/input/a.mp3").read() == b"ID3xxx"
        r = urlopen(base + "/input/%E5%AD%90%20%E7%9B%AE%E5%BD%95/%E6%AD%8C.lrc")
        assert r.read().decode("utf-8") == "hi"
        with pytest.raises(Exception):
            urlopen(base + "/input/missing.mp3")
    finally:
        shutdown()


def test_rejects_path_escape(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "secret.txt").write_text("s")
    inp = tmp_path / "in"
    inp.mkdir()
    base = serve(str(repo), str(inp))
    try:
        with pytest.raises(Exception):
            urlopen(base + "/input/../repo/secret.txt")
    finally:
        shutdown()
