from cli.scan import find_pairs


def test_pairs_by_stem_and_audio_priority(tmp_path):
    (tmp_path / "A - x.mp3").write_bytes(b"1")
    (tmp_path / "A - x.wav").write_bytes(b"1")
    (tmp_path / "A - x.lrc").write_text("[00:01.00]hi")
    (tmp_path / "B.lrc").write_text("[00:01.00]hi")   # 无音频 → unpaired
    r = find_pairs(str(tmp_path))
    assert [(p.stem, p.audio.endswith(".mp3")) for p in r.pairs] == [("A - x", True)]
    assert r.pairs[0].title == "x" and r.pairs[0].artist == "A"
    assert r.unpaired == ["B.lrc"]


def test_lyrics_prefers_lrc_over_txt(tmp_path):
    (tmp_path / "S.mp3").write_bytes(b"1")
    (tmp_path / "S.txt").write_text("hi")
    (tmp_path / "S.lrc").write_text("[00:01.00]hi")
    r = find_pairs(str(tmp_path))
    assert [p.lyrics.endswith(".lrc") for p in r.pairs] == [True]
    assert r.unpaired == []   # 落选的 .txt 与落选的多音频同理，不算未配对


def test_no_artist_separator_keeps_stem_as_title(tmp_path):
    (tmp_path / "只女的歌.mp3").write_bytes(b"1")
    (tmp_path / "只女的歌.lrc").write_text("[00:01.00]hi")
    r = find_pairs(str(tmp_path))
    assert r.pairs[0].title == "只女的歌" and r.pairs[0].artist == ""


def test_empty_folder(tmp_path):
    assert find_pairs(str(tmp_path)).pairs == []
    assert find_pairs(str(tmp_path)).unpaired == []
