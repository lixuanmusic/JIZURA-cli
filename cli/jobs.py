"""输出位置、命名、原子写盘与 jobs.json 日志。"""
from __future__ import annotations

import json
import os
import tempfile

THEME_NAMES = {
    'lyricpv': '文字PV',
    'kinetic': '动态文字',
    'wa': '和风',
    'horror': '恐怖',
    'pop': '流行',
    'ballad': '抒情',
    None: '不指定',
}


def output_dir(input_folder: str) -> str:
    """输入文件夹同级的 output/（不存在则创建）。"""
    d = os.path.join(os.path.dirname(os.path.abspath(input_folder).rstrip(os.sep)), 'output')
    os.makedirs(d, exist_ok=True)
    return d


def _sanitize(name: str) -> str:
    return name.replace('/', '_').replace(':', '_')


def output_name(stem: str, theme_key) -> str:
    return f"{_sanitize(stem)}_{THEME_NAMES[theme_key]}.mp4"


def write_blob(path: str, data: bytes) -> None:
    """先写 .part 再原子改名，避免中断留下半截成品。"""
    part = path + '.part'
    with open(part, 'wb') as f:
        f.write(data)
    os.replace(part, path)


def should_skip(path: str, force: bool) -> bool:
    return not force and os.path.exists(path)


def append_job(output_folder: str, record: dict) -> None:
    """追加一条生成记录到 output/jobs.json（读旧数组、tmp+rename 原子写回）。"""
    log = os.path.join(output_folder, 'jobs.json')
    try:
        with open(log, encoding='utf-8') as f:
            jobs = json.load(f)
    except (OSError, ValueError):
        jobs = []
    jobs.append(record)
    fd, tmp = tempfile.mkstemp(dir=output_folder, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(jobs, f, ensure_ascii=False, indent=1)
        os.replace(tmp, log)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
