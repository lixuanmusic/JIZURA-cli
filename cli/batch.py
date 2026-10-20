"""批处理核心：把 歌×主题 展开成任务列表，逐条生成，失败不中断。"""
from __future__ import annotations

import os
import random
from dataclasses import dataclass
from datetime import datetime

from .engine import Job
from .jobs import append_job, output_name, should_skip, write_blob


def build_jobs(pairs, themes, aspect, res, fps, force, out_folder):
    """歌 × 主题 → Job 列表；同名输出已存在且未 force 的跳过；种子随机且两两不同。"""
    jobs, seeds = [], set()
    for pair in pairs:
        for theme in themes:
            out_path = os.path.join(out_folder, output_name(pair.stem, theme))
            if should_skip(out_path, force):
                continue
            seed = random.randrange(1, 2 ** 31)
            while seed in seeds:
                seed = random.randrange(1, 2 ** 31)
            seeds.add(seed)
            jobs.append(Job(lyrics_path=pair.lyrics, audio_path=pair.audio, theme_key=theme,
                            aspect=aspect, res=res, fps=fps, seed=seed,
                            title=pair.title, artist=pair.artist, stem=pair.stem))
    return jobs


@dataclass
class BatchSummary:
    ok: list
    failed: list               # [(Job, 错误信息)]


def run_batch(engine, jobs, output_folder, on_progress=None):
    """串行生成；单条失败记录后继续；成功才写盘并记 jobs.json。"""
    ok, failed = [], []
    total = len(jobs)
    for idx, job in enumerate(jobs, 1):
        out_path = os.path.join(output_folder, output_name(job.stem, job.theme_key))
        record = {
            'time': datetime.now().isoformat(timespec='seconds'),
            'seed': job.seed, 'theme': job.theme_key, 'aspect': job.aspect,
            'res': job.res, 'fps': job.fps, 'output': os.path.basename(out_path),
            'audio': os.path.basename(job.audio_path), 'lyrics': os.path.basename(job.lyrics_path),
            'title': job.title, 'artist': job.artist,
        }
        try:
            data = engine.generate(job, on_progress=(lambda p, m: on_progress(job, idx, total, p, m))
                                   if on_progress else None)
            write_blob(out_path, data)
            append_job(output_folder, dict(record, status='ok'))
            ok.append(job)
        except Exception as e:                     # 单条失败不中断整批
            part = out_path + '.part'
            if os.path.exists(part):
                os.unlink(part)
            append_job(output_folder, dict(record, status='failed', error=str(e)))
            failed.append((job, str(e)))
        engine.maybe_reload(idx)
    return BatchSummary(ok, failed)
