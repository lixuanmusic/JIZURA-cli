"""LRC 预处理：喂给引擎前滤掉网易云导出的 JSON 元数据行。"""
from __future__ import annotations


def clean_lyrics(path: str) -> str:
    """utf-8-sig 读入；丢弃 strip 后以 `{` 开头的行；其余原样（含空行）。"""
    with open(path, encoding='utf-8-sig') as f:
        rows = f.read().replace('\r\n', '\n').replace('\r', '\n').split('\n')
    kept = [r for r in rows if r.strip() and not r.strip().startswith('{')]
    return '\n'.join(kept) + ('\n' if kept else '')
