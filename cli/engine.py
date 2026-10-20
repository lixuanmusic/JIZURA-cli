"""无头 Chrome 驱动 JIZURA 引擎：加载 index.html，按主题生成一个 MP4。"""
from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import quote

from .server import serve

# src/12_ui.js:9 的字面量照抄：打包后的 index.html 里 HUD_CHARS 在 UI 的 IIFE 作用域内，
# evaluate 注入的脚本不可见（评审实证），ensureFonts 的文本必须自带这份字符集，
# 否则 Google Fonts 不加载 HUD 用的子集，成片里时间码/counter/bpm 以回退字体渲染。
HUD_CHARS = '0123456789:./-_()【】・No.LYRICRECUNTITLEDXYlinebpminterlude—─／ '

CHUNK_CHARS = 4 * 1024 * 1024     # base64 分块回传，避免 2K/4K 大视频单次 evaluate 超限

# 页内管线：分析音频 → 主题随机 → 字体 → plan → 导出 MP4 → 分块 base64 回传。
# 关键约束（docs/BATCH_CLI_DESIGN.md）：exportMP4 的 audio 必须传 analyzeAudio 的
# 返回值（传 File 会静默无声）；omakase 返回补丁须合并回 project；导出前 ensureFonts。
_PIPELINE_JS = """
async (args) => {
  const { audioUrl, audioName, lyrics, title, artist, themeKey, aspect, res, fps, seed,
          hudChars, chunkChars } = args;
  const resp = await fetch(audioUrl);
  if (!resp.ok) throw new Error('fetch audio failed: ' + resp.status);
  const audioInfo = await J.analyzeAudio(new File([await resp.arrayBuffer()], audioName));

  let project = J.defaultProject();
  Object.assign(project, { lyrics, title, artist, aspect, res, fps,
                           quality: 'high', includeAudio: true, lang: 'auto' });
  Object.assign(project, J.omakase(project, J.rng(seed), themeKey));

  const plan = J.plan(project, audioInfo);
  await J.ensureFonts(project.lyrics + (project.title || '') + (project.artist || '') + hudChars,
                      J.fontsOfPlan(plan));

  const r = await J.exportMP4({ plan, project, audio: audioInfo, quality: 'high',
    onProgress: (p, m) => { try { window.__jzProgress(p, m); } catch (e) {} } });

  const dataUrl = await new Promise((resolve, reject) => {
    const fr = new FileReader();
    fr.onload = () => resolve(fr.result);
    fr.onerror = () => reject(fr.error);
    fr.readAsDataURL(r.blob);
  });
  const b64 = dataUrl.slice(dataUrl.indexOf(',') + 1);
  const nChunks = Math.ceil(b64.length / chunkChars);
  for (let i = 0; i < b64.length; i += chunkChars) window.__jzData(b64.slice(i, i + chunkChars));
  return nChunks;
}
"""

_last_chunk_count = 0     # 供测试断言分块路径真的走了多块


def _audio_url(audio_path: str) -> str:
    return '/input/' + quote(os.path.basename(audio_path))


@dataclass
class Job:
    lyrics_path: str
    audio_path: str
    theme_key: object          # J.THEMES key 或 None（不指定）
    aspect: str
    res: int
    fps: int
    seed: int
    title: str = ''
    artist: str = ''
    stem: str = ''             # 主文件名（run_batch 派生输出路径用；引擎不读）


class EngineSession:
    """一次无头会话：加载 index.html，可串行生成多条，每 10 条 reload 一次防内存增长。"""

    def __init__(self, repo_root: str, input_root: str):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._base = serve(repo_root, input_root)
        self._browser = self._pw.chromium.launch()
        self._page = self._browser.new_page()
        self._progress_cb = None
        self._chunks = []
        self._page.expose_function('__jzProgress', self._on_progress)
        self._page.expose_function('__jzData', self._on_data)
        self._page.goto(self._base + '/index.html')
        # 谓词必须返回布尔值：以函数引用（J.omakase 等）结尾会被 Playwright 当作谓词再调用一次
        self._page.wait_for_function(
            "window.J && typeof J.exportMP4 === 'function' && typeof J.omakase === 'function'",
            timeout=60000)

    def _on_progress(self, p, msg=''):
        if self._progress_cb:
            self._progress_cb(p, msg)

    def _on_data(self, b64chunk):
        self._chunks.append(b64chunk)

    def generate(self, job: Job, on_progress=None) -> bytes:
        """跑完一条任务，返回 MP4 字节。"""
        import base64
        from .lrc import clean_lyrics
        global _last_chunk_count
        self._progress_cb = on_progress
        self._chunks = []
        try:
            n_chunks = self._page.evaluate(
                _PIPELINE_JS,
                {'audioUrl': _audio_url(job.audio_path),
                 'audioName': os.path.basename(job.audio_path),
                 'lyrics': clean_lyrics(job.lyrics_path),
                 'title': job.title, 'artist': job.artist,
                 'themeKey': job.theme_key, 'aspect': job.aspect,
                 'res': job.res, 'fps': job.fps, 'seed': job.seed,
                 'hudChars': HUD_CHARS, 'chunkChars': CHUNK_CHARS},
            )
            assert int(n_chunks) == len(self._chunks), \
                f'chunk mismatch: page {n_chunks} vs python {len(self._chunks)}'
        finally:
            self._progress_cb = None
        _last_chunk_count = len(self._chunks)
        return base64.b64decode(''.join(self._chunks))

    def maybe_reload(self, count: int):
        if count and count % 10 == 0:
            self._page.reload()
            self._page.wait_for_function(
                "window.J && typeof J.exportMP4 === 'function'", timeout=60000)

    def close(self):
        try:
            self._browser.close()
        finally:
            self._pw.stop()
