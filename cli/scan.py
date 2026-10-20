"""扫描文件夹，把同名的音频与歌词配成对。"""
from __future__ import annotations

import os
from dataclasses import dataclass

AUDIO_EXTS = ('.mp3', '.m4a', '.wav', '.flac', '.ogg')   # 同名多音频时的优先级顺序
LYRIC_EXTS = ('.lrc', '.txt')


@dataclass
class Pair:
    stem: str
    audio: str
    lyrics: str
    title: str
    artist: str


@dataclass
class ScanResult:
    pairs: list
    unpaired: list


def _split_stem(stem: str):
    """“歌手 - 歌名” 拆成 (title, artist)；没有分隔则 (stem, '')。"""
    if ' - ' in stem:
        artist, title = stem.split(' - ', 1)
        return title, artist
    return stem, ''


def find_pairs(folder: str) -> ScanResult:
    audios, lyrics = {}, {}
    for entry in os.scandir(folder):
        if not entry.is_file():
            continue
        stem, ext = os.path.splitext(entry.name)
        if ext.lower() in AUDIO_EXTS:
            audios.setdefault(stem, []).append(entry.path)
        elif ext.lower() in LYRIC_EXTS:
            lyrics.setdefault(stem, []).append(entry.path)

    chosen_audio, chosen_lyric = {}, {}
    for stem in sorted(set(audios) & set(lyrics)):
        chosen_audio[stem] = min(audios[stem], key=lambda p: AUDIO_EXTS.index(os.path.splitext(p)[1].lower()))
        chosen_lyric[stem] = min(lyrics[stem], key=lambda p: LYRIC_EXTS.index(os.path.splitext(p)[1].lower()))

    # 未配对 = 某一边完全缺席的歌（同名多音频按优先级落选的不算）
    unpaired = sorted(
        os.path.basename(p)
        for stem in set(audios) ^ set(lyrics)
        for p in audios.get(stem, []) + lyrics.get(stem, [])
    )
    pairs = [
        Pair(stem, chosen_audio[stem], chosen_lyric[stem], *_split_stem(stem))
        for stem in sorted(chosen_audio)
    ]
    return ScanResult(pairs, unpaired)
