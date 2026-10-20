import math
import os
import struct

import pytest

from cli.engine import EngineSession, Job


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def make_wav(path: str, secs: float = 3.0, rate: int = 44100):
    """合成正弦波 PCM16 单声道 wav（测试专用）。"""
    n = int(secs * rate)
    samples = struct.pack(f'<{n}h', *(int(0.5 * 32767 * math.sin(2 * math.pi * 440 * i / rate)) for i in range(n)))
    header = struct.pack('<4sI4s4sIHHIIHH4sI',
                         b'RIFF', 36 + len(samples), b'WAVE', b'fmt ', 16, 1, 1, rate,
                         rate * 2, 2, 16, b'data', len(samples))
    with open(path, 'wb') as f:
        f.write(header + samples)


@pytest.mark.slow
def test_generate_returns_mp4_bytes(tmp_path):
    make_wav(str(tmp_path / 't.wav'))
    (tmp_path / 't.lrc').write_text('[00:00.30]第一行\n[00:01.30]第二行\n', encoding='utf-8')
    progress = []
    eng = EngineSession(REPO_ROOT, str(tmp_path))
    try:
        job = Job(lyrics_path=str(tmp_path / 't.lrc'), audio_path=str(tmp_path / 't.wav'),
                  theme_key='pop', aspect='3:4', res=720, fps=30, seed=12345,
                  title='测试歌', artist='测试歌手')
        data = eng.generate(job, on_progress=lambda p, m: progress.append(p))
    finally:
        eng.close()
    assert data[4:8] == b'ftyp'          # MP4 box 签名
    assert len(data) > 10000
    assert progress and max(progress) > 0.5   # 进度回调真实到达 Python 侧


def test_pipeline_carries_hud_charset_literal():
    """评审 Critical#1：打包页里 HUD_CHARS 在 UI 的 IIFE 内不可达（见 slow 测试的实证），
    管线必须自带字面量，否则 ensureFonts 不含 HUD 字符、成片 HUD 用回退字体。
    实现：HUD_CHARS 以参数传入页内管线（hudChars）。"""
    import inspect

    from cli import engine
    assert engine.HUD_CHARS.startswith('0123456789') and engine.HUD_CHARS.endswith('／ ')
    assert '+ hudChars' in engine._PIPELINE_JS                          # 管线把它拼进 ensureFonts 文本
    assert "'hudChars': HUD_CHARS" in inspect.getsource(engine)         # generate 真实传入


@pytest.mark.slow
def test_hud_chars_unreachable_in_bundled_page(tmp_path):
    """实证部分：真实 index.html 中 typeof HUD_CHARS === 'undefined'。"""
    eng = EngineSession(REPO_ROOT, str(tmp_path))
    try:
        assert eng._page.evaluate("() => typeof HUD_CHARS") == 'undefined'
    finally:
        eng.close()


def test_audio_url_quotes_special_chars():
    from cli.engine import _audio_url
    from urllib.parse import quote
    assert _audio_url('/x/song #1.mp3') == '/input/' + quote('song #1.mp3')
    assert _audio_url('/x/蔡健雅 - 红色高跟鞋.mp3') == '/input/' + quote('蔡健雅 - 红色高跟鞋.mp3')


@pytest.mark.slow
def test_generate_chunked_return(tmp_path, monkeypatch):
    """评审 Important#5：大视频必须分块回传；把块压到 64KB 强制多块，产物仍须完整。"""
    from cli import engine as eng_mod
    monkeypatch.setattr(eng_mod, 'CHUNK_CHARS', 64 * 1024)
    make_wav(str(tmp_path / 't.wav'), secs=3)
    (tmp_path / 't.lrc').write_text('[00:00.30]第一行\n[00:01.30]第二行\n', encoding='utf-8')
    eng = eng_mod.EngineSession(REPO_ROOT, str(tmp_path))
    try:
        job = eng_mod.Job(lyrics_path=str(tmp_path / 't.lrc'), audio_path=str(tmp_path / 't.wav'),
                          theme_key='ballad', aspect='3:4', res=720, fps=30, seed=7,
                          title='t', artist='a', stem='t')
        data = eng.generate(job)
    finally:
        eng.close()
    assert eng_mod._last_chunk_count > 1
    assert data[4:8] == b'ftyp' and len(data) > 10000
