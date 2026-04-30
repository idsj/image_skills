---
name: text2image
description: 根据文字描述生成 AI 图片并保存到本地。当用户说"帮我画""生成一张图""文生图"等时使用。
argument-hint: "<图片描述提示词>"
allowed-tools: Bash
---

用户想要生成一张图片，描述为：

**$ARGUMENTS**

## 执行步骤

使用 Bash 工具运行（将描述词替换为用户实际输入）：

```bash
python "${CLAUDE_SKILL_DIR}/text2image.py" "$ARGUMENTS"
```

## 结果处理

解析输出的 JSON：
- 成功：`{"image_path": "output_images/xxx.png", "message": "图片生成成功"}` → 告知用户图片路径
- 失败：`{"error": "..."}` → 说明失败原因

## 可选参数

```bash
python "${CLAUDE_SKILL_DIR}/text2image.py" "描述词" --output 文件名.png --dir 输出目录
```
