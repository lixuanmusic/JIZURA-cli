import json

from cli.jobs import (
    append_job, output_dir, output_name, should_skip, write_blob,
)


def test_theme_names_cover_all_keys():
    from cli.jobs import THEME_NAMES
    assert set(THEME_NAMES) == {'lyricpv', 'kinetic', 'wa', 'horror', 'pop', 'ballad', None}
    assert THEME_NAMES[None] == '不指定'


def test_output_name_and_sanitize():
    assert output_name("A - x", "pop") == "A - x_流行.mp4"
    assert "/" not in output_name("a/b:c", None) and ":" not in output_name("a/b:c", None)
    assert output_name("歌", None) == "歌_不指定.mp4"


def test_output_dir_is_sibling(tmp_path):
    inp = tmp_path / "raw"
    inp.mkdir()
    assert output_dir(str(inp)) == str(tmp_path / "output")
    assert (tmp_path / "output").is_dir()


def test_append_and_skip(tmp_path):
    append_job(str(tmp_path), {"seed": 1})
    append_job(str(tmp_path), {"seed": 2})
    assert [r["seed"] for r in json.load(open(tmp_path / "jobs.json"))] == [1, 2]
    p = tmp_path / "v.mp4"
    write_blob(str(p), b"abc")
    assert p.read_bytes() == b"abc" and not (tmp_path / "v.mp4.part").exists()
    assert should_skip(str(p), force=False) and not should_skip(str(p), force=True)
    assert not should_skip(str(tmp_path / "nope.mp4"), force=False)
