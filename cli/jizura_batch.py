#!/usr/bin/env python3
"""JIZURA 批量生成向导：每首歌 × 每个选中主题各出一个 MP4。

用法：python3 cli/jizura_batch.py [--force]
依赖：pip install playwright questionary rich && playwright install chromium
"""
from __future__ import annotations

import os
import sys

# 允许 python3 cli/jizura_batch.py 直跑（也支持 python3 -m cli.jizura_batch）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli.batch import build_jobs, run_batch
from cli.engine import EngineSession
from cli.jobs import THEME_NAMES, output_dir
from cli.scan import find_pairs

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

ASPECTS = ['16:9', '9:16', '4:3', '3:4', '1:1', '4:5', '21:9']
RESOLUTIONS = [('720p', 720), ('1080p', 1080), ('2K', 1440), ('4K', 2160)]
FPS_OPTIONS = [24, 30, 60]
# 用户指定的默认档位
DEFAULT_ASPECT, DEFAULT_RES, DEFAULT_FPS = '3:4', 720, 30


def _pick_pairs(path):
    """输入可以是文件夹或单个文件；单个文件时只取它所在的那一对。"""
    if os.path.isfile(path):
        folder = os.path.dirname(os.path.abspath(path)) or '.'
        r = find_pairs(folder)
        target = os.path.abspath(path)
        r.pairs = [p for p in r.pairs if p.audio == target or p.lyrics == target]
        r.unpaired = [] if r.pairs else r.unpaired
        return folder, r
    return path, find_pairs(path)


def _ask_themes(questionary):
    """多选主题：取消（None）立即返回 None；空选重问。choices 用 (标题, 值) 元组形式。"""
    while True:
        res = questionary.checkbox(
            '选择主题（空格多选，回车确认）',
            choices=[(name, key) for key, name in THEME_NAMES.items()],
        ).ask()
        if res is None:
            return None
        if res:
            return res


def skip_notice(pairs_count, themes_count, jobs_len):
    """被 --force 之外的原因（同名已存在）跳过的任务数提示；无跳过返回空串。"""
    skipped = pairs_count * themes_count - jobs_len
    if skipped <= 0:
        return ''
    return f'已跳过 {skipped} 个已存在的输出（--force 重新生成）'


def main(argv=None):
    import questionary
    from rich.console import Console
    from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn

    argv = sys.argv[1:] if argv is None else argv
    force = '--force' in argv
    console = Console()

    path = questionary.path('输入文件或文件夹路径：').ask()
    if not path:
        return 1
    folder, scan = _pick_pairs(os.path.expanduser(path.strip('\'"')))
    console.print(f'识别到 [bold]{len(scan.pairs)}[/bold] 对音频+歌词'
                  + (f'，未配对 {len(scan.unpaired)} 个：{", ".join(scan.unpaired)}' if scan.unpaired else ''))
    if not scan.pairs:
        console.print('[red]没有可用的配对，退出。[/red]')
        return 1

    themes = _ask_themes(questionary)
    if themes is None:
        return 1

    aspect = questionary.select('画面比例：', choices=ASPECTS, default=DEFAULT_ASPECT).ask()
    default_res_label = next(t for t, v in RESOLUTIONS if v == DEFAULT_RES)
    res = questionary.select('分辨率：', choices=[t for t, _ in RESOLUTIONS],
                             default=default_res_label).ask()
    fps = questionary.select('FPS：', choices=[str(f) for f in FPS_OPTIONS],
                             default=str(DEFAULT_FPS)).ask()
    if aspect is None or res is None or fps is None:
        return 1
    res_val = dict((t, v) for t, v in RESOLUTIONS)[res]
    fps_val = int(fps)

    out_folder = output_dir(folder)
    jobs = build_jobs(scan.pairs, themes, aspect, res_val, fps_val, force=force, out_folder=out_folder)
    theme_label = '、'.join(THEME_NAMES[t] for t in themes)
    notice = skip_notice(len(scan.pairs), len(themes), jobs_len=len(jobs))
    if notice:
        console.print('[yellow]' + notice + '[/yellow]')
    if not questionary.confirm(
            f'{len(scan.pairs)} 首歌 × {len(themes)} 个主题（{theme_label}）= {len(jobs)} 个视频，'
            f'{aspect} / {res} / {fps_val}fps\n输出到 {out_folder}。开始生成？', default=True).ask():
        return 1

    console.print('[dim]启动无头浏览器加载引擎…（首次需联网加载字体）[/dim]')
    with Progress(TextColumn('{task.fields[label]}'), BarColumn(),
                  TextColumn('{task.percentage:>3.0f}%'), TimeElapsedColumn(), console=console) as prog:
        task = prog.add_task('', total=None, label='准备中…')

        def on_progress(job, idx, total, p, msg):
            prog.update(task, completed=p * 100, total=100,
                        label=f'[{idx}/{total}] {job.stem}·{THEME_NAMES[job.theme_key]} {msg}')

        eng = EngineSession(REPO_ROOT, folder)
        try:
            summary = run_batch(eng, jobs, out_folder, on_progress=on_progress)
        except KeyboardInterrupt:
            eng.close()
            console.print('[yellow]已中断。之前完成的输出保留在[/yellow]' + out_folder)
            return 130
        eng.close()

    console.print(f'[green]完成 {len(summary.ok)} 个[/green]'
                  + (f'，[red]失败 {len(summary.failed)} 个[/red]' if summary.failed else ''))
    for job, err in summary.failed:
        console.print(f'  [red]✗ {job.stem}·{THEME_NAMES[job.theme_key]}[/red]：{err}')
    console.print(f'输出目录：{out_folder}（生成记录见 jobs.json）')
    return 0 if not summary.failed else 2


if __name__ == '__main__':
    sys.exit(main())
