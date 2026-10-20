# JIZURA 批量生成 CLI — Builder Check 评审报告

日期：2026-10-21
对象：docs/BATCH_CLI_DESIGN.md
方法：按 superpowers/brainstorming/builder-check-prompt.md，以实现者视角逐条核实技术断言（读源码 + 在无头 Chromium 中实测），报告实现前仍需回答的问题。

## 核实方式

除静态读码外，用临时 venv 安装 Playwright（chromium-headless-shell 156.0.8078.4），本地 HTTP 服务真实的 index.html，跑通了设计描述的完整管线：

- fetch 音频 → `J.analyzeAudio`（158.5s 的 mp3，290ms 解码分析，BPM 148.9）
- `J.defaultProject()` → 设 LRC 歌词/aspect/res/fps → `J.omakase(project, J.rng(种子), 主题)` → merge 回 project → `J.plan(project, audioInfo)`
- `J.ensureFonts(...)`（在线 570ms）→ `J.exportMP4({plan, project, audio: audioInfo, quality:'high'})`
- 结果：45.2MB / 158.5s / 1280x720@24 / H.264 High + AAC，墙钟 89 秒，零 page error。同种子两次 `J.plan` 的 cut 结构逐项一致。

**结论：设计描述的管线在无头 Chromium 中端到端可行，核心断言全部实测通过。** 以下为细目与遗留问题。

## 一、技术断言核实

### 成立的断言（附证据）

1. **`J.THEMES` 位置与主题集合**：src/08b_omakase.js:45-52，key 为 lyricpv/kinetic/wa/horror/pop/ballad，"不指定主题"= 不传 themeId（08b_omakase.js:55 第三参默认 null）。✔
2. **parseLyrics 认行级时间戳、毫秒精度**：src/08_planner.js:61 `\\[(\\d+):(\\d+(?:[.:]\\d+)?)\\]`，parseFloat 接任意小数位。`[ti:][ar:][al:][by:][offset:]` 元数据行入 meta 不渲染（:57-58）。✔
3. **网易云 JSON 行会被当歌词渲染**：src/08_planner.js:53-89 无任何 `{` 过滤；`{"t":ms,"c":[...]}` 行会成为无时间戳的普通歌词行。测试数据 10 个 lrc 全部含此类行（每文件 2~21 行）。CLI 侧过滤的决策正确且必要。✔
4. **`J.omakase(project, rnd, themeId)` 签名**：src/08b_omakase.js:55。✔
5. **种子可追溯（结构级）**：omakase 返回的 patch 含 `seed: Math.floor(rnd()*1e9)`（08b_omakase.js:124）→ `project.seed` → planner 全程用 `J.rng(J.h(project.seed,...))`（08_planner.js:294,322,331,471），planner 无 `Math.random`。实测同种子两次 plan 输出一致。引擎自带 mulberry32：`J.rng = seed => {...}`（src/01_util.js:56），CLI 直接可用。✔
6. **`J.plan(project, audio)`**：src/08_planner.js:268，audio 取 `audio.beats`（:295）。✔
7. **`J.exportMP4({plan, project, audio, onProgress})`**：src/11_export.js:141-142，还有 quality/signal/range/file 参数；onProgress(p, text) 每帧比率（:198）。返回 `{blob, size, codec, audio, ...}`。✔
8. **`J.analyzeAudio(file)` 接受 File**：src/10_audio.js:7（`file.arrayBuffer()`）。fetch→blob→`new File()` 实测可用；无头下 AudioContext/decodeAudioData 正常。✔
9. **index.html 单文件、`J` 全局暴露**：`const J = (window.J = window.J || {})`（src/01_util.js:5；打包产物 index.html:793 同文）；index.html 无本地外部资源引用（仅外链与 Google Fonts）。`page.evaluate` 直接用 `J.*` 成立（dev/smoke_all.py:25 先例 + 本次实测）。✔
10. **无头 Chromium 编码能力**：实测 H.264 High/Main/Baseline、VP9、AV1 的 `VideoEncoder.isConfigSupported` 全部 true；**AAC（mp4a.40.2）与 Opus 音频编码均 supported，且端到端导出真实产出了 H.264+AAC 的 MP4**。"音乐嵌入"可行。✔
11. **`document.hidden === false`（无头）**：11_export.js:195 的"页面隐藏时编码器停转"保护不会误触发。✔
12. **离线字体回退**：Google Fonts 懒加载带 5 秒超时（src/02_fonts.js:90），`document.fonts.load` 全部 `.catch(()=>null)`（:115,:126），离线时静默落到本地回退字体栈（index.html:977-978）。"可接受降级"成立。✔
13. **smoke_all.py 先例**：dev/smoke_all.py:55-63 确为 Playwright + 本地 HTTP + evaluate 全局 J。✔
14. **配对规则的现实依据**：测试数据确有 mp3+wav 并存（"Ariana Grande - hate that i made you love me"、"阿冗 - 与我无关"），及孤立 `_1.wav`；song-0001..0010 子目录与 songs_index.json 存在，"不递归"决策与之相容。✔
15. **wav 解码**：实测 `J.analyzeAudio` 通路解码 240s wav 成功；flac/ogg/mp3 的 canPlayType 均非空。✔

### 站不住或表述有误/有歧义的断言

1. **主题名不是中文**：`J.THEMES[*].name` 为日文——'文字PV'、'キネティック'、'和風'、'ホラー'、'ポップ'、'バラード'（08b_omakase.js:45-52；实测确认）。设计第 34 行与第 48 行"命名 `主文件名_主题中文名.mp4`"意味着 CLI 需自带 key→中文名映射（设计列过中文名：文字PV/动态文字/和风/恐怖/流行/抒情，照抄即可，但须知道引擎不会给你中文名）。
2. **管线缺了 `ensureFonts` 步骤**：设计"生成管线"4 步里没有它。网页版在导出前必做 `await J.ensureFonts(歌词+title+artist+HUD_CHARS, J.fontsOfPlan(plan))`（src/12_ui.js:1434；HUD_CHARS 定义在 12_ui.js:9）。跳过则文字测量/渲染用回退字体，布局可能错位，且 Google Fonts（unicode-range 分包）根本不会加载。实测在线耗时约 570ms。**照抄此步是必要条件。**
3. **`omakase` 的返回值必须 merge 回 project**：08b_omakase.js:60 内部 `project = Object.assign({}, project, switches)` 是副本操作，函数返回 patch；UI 的用法是 `Object.assign(S.project, r)`（12_ui.js:1119-1120）。设计只写"J.omakase(project, rnd, themeId) 在主题内随机"，照字面只调用不合并会得到默认样式的视频。
4. **`exportMP4` 的 `audio` 参数必须是 `J.analyzeAudio` 的返回值，不是 File**：encodeMP4 用 `audio.buffer`（11_export.js:168,208）；传 File 时 `audio.buffer` 为 undefined，编码器协商直接跳过（`if (audio && audio.buffer ...)`），**静默产出无声 MP4**（返回值 `audioWanted:false`，引擎不报错）。设计第 2 步与第 4 步之间的这个传参关系必须写清。
5. **"种子与全部参数可追溯"的精度**：渲染层有 5 处 `Math.random`（src/09_render.js:24,41,45,48,50，纸纹理/噪点颗粒），同种子重跑结构、时机、配色完全一致，但帧内纹理噪点不逐字节相同。可追溯性成立到"结构级"，不是"逐比特"。
6. **"9 对平铺的 lrc+mp3"数量有误**：实际 10 对（精卫、Ariana、Drake、KATSEYE、Taylor、sombr、蔡健雅、阿YueYue、阿冗、陈粒）。不影响方案，影响验收时的对账。
7. **Playwright"已有先例"≠环境就绪**：dev/package.json 只有 acorn，本机各 Python 环境均无 playwright 模块（浏览器缓存里有旧版 chromium-1208）。CLI 的 README 必须写清 `pip install playwright && playwright install chromium`（本次实测下载 headless shell 约 99MB）。smoke_all.py 本身也不含 HTTP server（外部另起），"起本地 HTTP 服务"要 CLI 自带。

## 二、设计没回答的问题

### 只有用户能答（按重要性排序）

1. **默认分辨率/FPS 与耗时预期**。实测 720p24 全曲（158.5s）编码约 85 秒（≈2.2× 实时）。外推：1080p24 ≈ 5 分钟/首、1080p60 ≈ 13 分钟/首、4K 更久（无头下编码可能落到软件路径）。10 首 × 6 主题 = 60 条时，1080p24 全量约 5 小时。**向导的默认档位选什么、能否接受整批通宵跑**，直接决定默认参数与进度/汇总的呈现方式。
2. **输出目录写进 `data/raw/output/` 是否可接受**。设计定"输入路径旁的 output/ 子目录"，而测试数据目录属于用户另一套数据管线（内含 songs_index.json、song-XXXX/ 结构）。往里面新增 output/ 与 jobs.json 是否污染那套管线，只有用户能定；若不接受，需指定默认输出根（如 `~/Movies/jizura_batch/` 或让向导每次询问）。
3. **种子的语义：仅记录，还是必须可重放**。设计只说 jobs.json 记种子"可读"。是否需要 `--seed`/按记录重跑同一条的能力（影响 CLI 参数设计与测试方式）。
4. **画质（画質）档位**。网页版有 標準/高/最高（index.html outQuality；11_export.js:37-41 三档码率），向导流程只有比例/分辨率/FPS。默认 high 可以，但"最高"对收藏级输出有意义——要不要暴露这一步（或 `--quality` 参数）。
5. **单条失败要不要自动重试**（如换一个种子再试一次）。设计定"记录后继续"；自动重试一次能救回偶发编码失败，但也会改变失败语义。

### 实现者可自行决定（列出以免遗漏，不必问）

1. omakase patch 的 `Object.assign` 合并（照 12_ui.js:1120）。
2. 导出前 `J.ensureFonts` + `HUD_CHARS` 常量照抄（12_ui.js:9,1434）。
3. `audio` 传 analyzeAudio 返回值；File 由 CLI 侧另持（fetch 的 blob 即可）。
4. HTTP server 形态：`http.server` + 自定义 handler 把 `/input/` 映射到输入目录（index.html 无本地依赖，只需能取到它本身）。
5. LRC 读取编码：utf-8-sig（实测均 UTF-8；BOM 容忍无害），GBK fallback 可不做。
6. 页面复用策略：整批共用一个 page（省每次 ~2s 加载），每条任务重建 project；或每 N 条 reload 防缓存膨胀。
7. title/artist 来源：测试 lrc 均无 `[ti:]/[ar:]`（实测 0 个文件含），从文件名 `艺人 - 标题` 拆分，拆不出就留空（无 title card）。
8. 主题 key→中文文件名的映射表（设计已给中文名）。
9. jobs.json 用 JSONL 追加（崩溃安全）或数组 JSON 原子重写。
10. Ctrl-C：向页面传 AbortSignal（exportMP4 支持 `signal`，11_export.js:142），中断后当前文件作废并记录。
11. 采集 pageerror/console.error 进失败记录（smoke_all.py 先例）。
12. 同主题跨歌曲每条独立种子（从全局种子派生：`hash(总种子, 歌, 主题)`）。
13. `timing.snap` 已默认 true（08_planner.js:34），无需设置；`themeId` 字段不必设（直接传第三参）。

## 三、其他风险

1. **批量总时长**：见问题 1 的实测外推。进度展示（整体序号 + 每条帧进度）技术上顺滑（onProgress 每帧回调），但用户对总时长的心理预期需要在确认摘要里显式给出（如"预计 3 小时"）。
2. **批内视觉不一致**：若跑到中途网络断掉，前几条用 Google Fonts、后面落本地回退字体，同批主题相同的两条看起来不同。可在开跑前做一次字体探活并在断网时提示。
3. **长跑内存**：一页连跑 60 条，`J.glyphs`/`J.metrics` 缓存与已解码 AudioBuffer 的积累未见上限（02_fonts.js:132-135 有 clear 但按需调用）。缓解：每 N 条 reload 页面。
4. **m4a（AAC in MP4）解码未实测**：测试数据无 m4a 样本；canPlayType('audio/aac') 返回 "probably"，风险低。首次遇到 m4a 输入时注意 analyzeAudio 是否抛错（抛错则按设计的失败流程记录）。
5. **歌词中的引擎语法字符**：`*强调*`、`/` 断句、`|` note、行尾 `!`、`[間奏 N]` 会被 parseLyrics 重新解释（08_planner.js:63-84）。与网页版行为一致，但批量无人工预览，某行被意外断句只能成片后才发现。可考虑 CLI 侧对含这些字符的行打警告（不改内容）。
6. **离线时 fonts.googleapis.com 拖延**：每个 family 的 stylesheet 附带 5 秒超时（02_fonts.js:90），多 family 最坏叠加数十秒；可接受但值得在进度上显示"字体加载中"。
7. **对现有 app 的影响为零（核实通过）**：CLI 只读式加载 index.html；`J.saveSong`/IndexedDB 只在 UI 的 loadAudioFile 里调用（12_ui.js:1843），CLI 走 `J.analyzeAudio` 不落任何浏览器持久化。repo 文件零改动（新增 `cli/`）满足反目标约束。
8. **磁盘**：本次核查往 `~/Library/Caches/ms-playwright` 下载了 chromium_headless_shell-1248（约 100MB，保留可供 CLI 直接使用）；60 条 1080p 高画质输出预计 60 × 40-80MB ≈ 2.5-5GB，确认摘要里应提示剩余磁盘空间。

## 附：实测环境与方法（可复现）

- macOS（darwin 25.5），Python 3.13 venv + playwright（chromium-headless-shell 156.0.8078.4，Playwright 默认 headless 即此二进制）。
- `python -m http.server` 服务 index.html 与 `/input/`（符号链接指向测试数据目录，只读）。
- 探测脚本与端到端脚本已用完删除；对仓库与测试数据零写入。
