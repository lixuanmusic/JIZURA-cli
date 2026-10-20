from cli.lrc import clean_lyrics


def test_drops_netease_json_keeps_rest(tmp_path):
    f = tmp_path / "t.lrc"
    f.write_text('﻿{"t":0,"c":[{"tx":"作词: "}]}\n[00:22.297]该怎么去形容你最贴切\n\n', encoding="utf-8")
    out = clean_lyrics(str(f))
    assert out == "[00:22.297]该怎么去形容你最贴切\n"


def test_keeps_ordinary_lines_verbatim(tmp_path):
    f = tmp_path / "t.lrc"
    text = "[00:01.00]夜明けの色を/覚えてる\n[00:05.00]*透明*\n[ti:歌名]\n[00:09.00]行末!\n"
    f.write_text(text, encoding="utf-8")
    assert clean_lyrics(str(f)) == text   # 引擎语法（/ * ! [ti:]）不在 CLI 的清洗范围


def test_indented_json_line_also_dropped(tmp_path):
    f = tmp_path / "t.lrc"
    f.write_text('  {"t":1000,"c":[]}\n[00:01.00]hi\n', encoding="utf-8")
    assert clean_lyrics(str(f)) == "[00:01.00]hi\n"
