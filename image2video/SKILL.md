---
name: image2video
description: 图生视频——把一张图片做成几秒的动态视频（可带音轨）。当用户说"让图片动起来""图生视频""把这张图做成视频""image2video"时使用。走 OpenAI 兼容网关（new-api 类）的异步视频任务接口，默认 MiniMax-H3 2K。按次计费、图片会上传第三方。
argument-hint: "<图片路径> \"<动态描述>\" [--model M] [--duration N] [--resolution R]"
allowed-tools: Bash
---

用户想把图片变成视频。参数：**$ARGUMENTS**

## 执行前必须做（不可跳过）

1. **先把提示词展示给用户确认**，确认后再提交——这是按次计费的云端任务。
2. 图片会经网关上传到第三方模型厂商，若图片含敏感/内部内容，提醒用户。

## 提示词怎么写

只描述「动什么」，外观由首帧决定。实测有效的写法：
- 开头锁住：`固定机位，镜头不推拉不平移。画面构图、人物外貌、服装和所有文字全程保持与原图完全一致。只有以下元素在动：…`
- 逐个元素写具体动作（"龙翼轻扇、龙尾微摆"），不要写"让画面生动"这类空话
- 结尾写声音：`环境音：…，无人声无配乐。`（H3 会音画联合生成）

## 执行

```bash
python "${CLAUDE_SKILL_DIR}/image2video.py" "<图片>" "<提示词>" --output 名字.mp4
```

后台运行（`run_in_background`），一般 2~5 分钟。stderr 第一行就是 `task_id=...`，同时追加到
`${CLAUDE_SKILL_DIR}/tasks.log`。**用户问进度时**读输出文件里的 status 行；脚本被中断则：

```bash
python "${CLAUDE_SKILL_DIR}/image2video.py" --resume <task_id> --output 名字.mp4
```

可选参数：`--model`、`--duration`（秒）、`--resolution`、`--last 尾帧图`、`--camera-fixed`（Seedance）、`--dir`。
默认输出到 `${CLAUDE_SKILL_DIR}/output_videos/`。

## 结果处理

stdout 最后一行 JSON：
- 成功 `{"video_path", "task_id", "quota", "elapsed_s"}` → 用 ffmpeg/cv2 抽首/中/末帧**看一眼再汇报**（脸、文字、动作），并报 quota
- 失败 `{"error", "raw", "hint"?}` → 按 hint 说明原因

## 实测事实（new-api 网关，2026-11）

- `MiniMax-H3`：时长只支持 **4~15s**；分辨率只有 **480P / 768P / 2K**（没有 1080P）。2K 出 2176×1440、24fps，约 3 分钟。全身群像的小脸也清晰
- Seedance（`doubao-seedance-*`）：走 `/v1/video/generations` 若报 `model_price_error: no usage expression or meter`，是网关没给这条路由配计费，改参数无用。改走 `/v1/videos` 能提交，但首帧图必须放在 `metadata.content` 里并标 `role: "first_frame"`（顶层 `image` 会被当成参考图 r2v 模式，且该模式不接受 `camera_fixed`）——**本脚本尚未支持这条路径**
- Seedance 输出会过内容审核：画面里有商标名/品牌 logo 会被拒（`OutputVideoSensitiveContentDetected.PolicyViolation`，不扣费）
- 模型名必须用 `/v1/models` 里的**完整 ID**（如带日期后缀），简写会报 `No available channel`
- **任务绑定提交时的 key**：换 key 后查旧 task_id 会回 `task_not_exist`（脚本直接报错退出，不空等）
- 任务列表接口一般要网页登录态，API key 查不了——所以 task_id 必须自己记（脚本已写 tasks.log）
- `--last` 尾帧参数各家字段名未实测（MiniMax 用 `last_frame_image` 是按官方 API 推断）
