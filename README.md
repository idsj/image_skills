# image_skills

三个独立的 AI 图像技能，支持**命令行直接使用**和**作为 Claude Code 斜杠命令**使用。

- `text2image` — 文本描述 → AI 生成图片
- `image2image` — 参考图片 + 描述 → AI 编辑图片
- `image2video` — 图片 + 动态描述 → 几秒的动态视频（异步任务，默认 MiniMax-H3 2K）

## 环境要求

- Python 3.10+
- 任意 OpenAI 兼容的图像生成 API（如豆包、GPT-Image-2 等）

## 安装

### 方式一：通过 Claude Code 斜杠命令自动安装（推荐）

如果你安装了 [install-skill](https://github.com/idsj/install-skill) 技能，直接在 Claude Code 中运行：

```
/install-skill https://github.com/idsj/image_skills
```

重启 Claude Code 后即可使用文生图和图片编辑能力。

### 方式二：手动克隆

```bash
git clone https://github.com/idsj/image_skills.git image_skills
cd image_skills
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env，填入你的 API Key 和 Base URL
```

## 配置（.env）

```env
OPENAI_API_KEY=sk-your-key-here
OPENAI_API_BASE_URL=https://your-api-host/v1
IMAGE_MODEL=doubao-seedream-4-5-251128
```

---

## 命令行使用

### 文生图

```bash
# 基本用法
python text2image/text2image.py "一只在樱花树下打太极的熊猫，水墨画风格，高清"

# 指定输出文件名和目录
python text2image/text2image.py "sunset over mountains" --output sunset.png --dir ./output
```

### 图片编辑

```bash
# 基本用法
python image2image/image2image.py photo.png "转成水墨画风格"

# 指定输出
python image2image/image2image.py photo.jpg "将背景换成雪山" --output result.png --dir ./output
```

### 图生视频

```bash
# 基本用法（提交后自动轮询，完成即下载 mp4，一般 2~5 分钟）
python image2video/image2video.py poster.png "固定机位，构图不变。人物发丝随风轻飘，云海缓慢流动"

# 指定模型/时长/分辨率
python image2video/image2video.py poster.png "..." --model MiniMax-H3 --duration 4 --resolution 2K

# 脚本中断后续查（task_id 在 stderr 第一行，也记在 image2video/tasks.log）
python image2video/image2video.py --resume task_xxx --output result.mp4
```

需要网关支持 `POST /v1/video/generations` 异步任务接口（new-api 类网关）；按次计费，图片会上传给模型厂商。

输出结果为 JSON：
```json
{"image_path": "output_images/20260430153012.png", "message": "图片生成成功"}
```

---

## 作为 Claude Code 斜杠命令

将技能目录复制到 `~/.claude/skills/`：

```bash
cp -r text2image ~/.claude/skills/text2image
cp -r image2image ~/.claude/skills/image2image
cp -r image2video ~/.claude/skills/image2video
```

重启 Claude Code 后即可使用：

```
/text2image 一只在樱花树下打太极的熊猫，水墨画风格，高清
/image2image output_images/panda.png "将背景替换为雪山"
/image2video output_images/panda.png "熊猫缓缓收势，樱花花瓣飘落"
```

> `.env` 文件放在执行命令时的工作目录，或任意父级目录均可自动识别。

---

## 目录结构

```
image_skills/
├── .env.example
├── requirements.txt
├── README.md
├── text2image/
│   ├── SKILL.md         # Claude Code 斜杠命令定义
│   └── text2image.py    # 核心实现 + CLI 入口
├── image2image/
│   ├── SKILL.md
│   └── image2image.py
└── image2video/
    ├── SKILL.md
    └── image2video.py
```
