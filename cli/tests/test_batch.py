import json
import os

from cli.batch import BatchSummary, build_jobs, run_batch
from cli.scan import Pair


def _pair(tmp_path, stem):
    audio = tmp_path / f"{stem}.mp3"
    audio.write_bytes(b"1")
    lyrics = tmp_path / f"{stem}.lrc"
    lyrics.write_text("[00:01.00]hi")
    return Pair(stem, str(audio), str(lyrics), stem, "")


def test_build_jobs_expands_and_skips(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    pairs = [_pair(tmp_path, "A - x"), _pair(tmp_path, "B - y")]
    (out / "A - x_流行.mp4").write_bytes(b"done")   # A 歌的流行版已存在
    jobs = build_jobs(pairs, ['pop', 'ballad'], '3:4', 720, 30, force=False, out_folder=str(out))
    assert sorted(j.stem for j in jobs) == ['A - x', 'B - y', 'B - y']  # 只跳过已存在的 A_流行
    assert all(j.theme_key in ('pop', 'ballad') for j in jobs)
    assert len({j.seed for j in jobs}) == len(jobs)                     # 种子两两不同
    forced = build_jobs(pairs, ['pop'], '3:4', 720, 30, force=True, out_folder=str(out))
    assert len(forced) == 2


class FakeEngine:
    def __init__(self, fail_on=None):
        self.fail_on = fail_on or set()
        self.calls = 0

    def generate(self, job, on_progress=None):
        self.calls += 1
        if job.stem in self.fail_on and job.theme_key == 'pop':
            raise RuntimeError('boom: 损坏的音频')
        if on_progress:
            on_progress(1.0, '完成')
        return b'\x00\x00\x00\x18ftypmp42fake-video-bytes'

    def maybe_reload(self, count):
        pass


def test_run_batch_continues_after_failure(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    pairs = [_pair(tmp_path, "A - x"), _pair(tmp_path, "B - y")]
    jobs = build_jobs(pairs, ['pop', 'ballad'], '3:4', 720, 30, force=False, out_folder=str(out))
    eng = FakeEngine(fail_on={"A - x"})
    s = run_batch(eng, jobs, str(out))
    assert isinstance(s, BatchSummary)
    assert len(s.ok) == 3 and len(s.failed) == 1
    assert 'boom' in s.failed[0][1]
    records = json.load(open(out / "jobs.json"))
    assert [r['status'] for r in records].count('ok') == 3
    assert [r['status'] for r in records].count('failed') == 1
    assert 'boom' in [r for r in records if r['status'] == 'failed'][0]['error']
    written = sorted(f for f in os.listdir(out) if f.endswith('.mp4'))
    assert len(written) == 3 and all((out / f).read_bytes().endswith(b'fake-video-bytes') for f in written)
    assert not [f for f in os.listdir(out) if f.endswith('.part')]     # 无半截文件残留


def test_run_batch_records_seed_and_params(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    jobs = build_jobs([_pair(tmp_path, "S")], ['kinetic'], '9:16', 1080, 60, force=False, out_folder=str(out))
    run_batch(FakeEngine(), jobs, str(out))
    r = json.load(open(out / "jobs.json"))[0]
    assert r['seed'] == jobs[0].seed and r['theme'] == 'kinetic'
    assert r['aspect'] == '9:16' and r['res'] == 1080 and r['fps'] == 60
    assert r['output'].endswith('S_动态文字.mp4')


def test_run_batch_records_timestamp(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    jobs = build_jobs([_pair(tmp_path, "T")], ['wa'], '3:4', 720, 30, force=False, out_folder=str(out))
    run_batch(FakeEngine(), jobs, str(out))
    r = json.load(open(out / "jobs.json"))[0]
    assert 'T' in r['time'] and ':' in r['time']        # ISO 时间戳（spec：jobs.json 记“时间”）


def test_ask_themes_cancel_returns_none():
    """评审 Important#2：checkbox 取消（ask() 返回 None）必须退出，不能死循环。"""
    from cli.jizura_batch import _ask_themes

    class _Box:
        def __init__(self, ret):
            self.ret = ret

        def ask(self):
            return self.ret

    class CancelQ:
        def checkbox(self, *a, **k):
            return _Box(None)

    class EmptyThenPickQ:
        def __init__(self):
            self.calls = 0

        def checkbox(self, *a, **k):
            self.calls += 1
            return _Box([] if self.calls == 1 else ['pop'])

    assert _ask_themes(CancelQ()) is None               # 取消 → None，立即退出
    assert _ask_themes(EmptyThenPickQ()) == ['pop']     # 空选 → 重问一次后选中


def test_skip_notice():
    """评审 Important#4：spec 验收 4 要求跳过有明确提示。"""
    from cli.jizura_batch import skip_notice
    assert '3' in skip_notice(5, 2, jobs_len=7)
    assert skip_notice(4, 2, jobs_len=8) == ''
