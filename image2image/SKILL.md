---
name: image2image
description: 对已有图片进行 AI 编辑——风格转换、背景替换、局部修改等。当用户说"把这张图改成""转成水墨风格""换个背景"时使用。
argument-hint: "<图片路径> \"<编辑描述>\""
allowed-tools: Bash
---

用户想对图片进行编辑。

参数：**$ARGUMENTS**

格式：`<图片路径> "<编辑描述>"`

## 执行步骤

使用 Bash 工具运行：

```bash
python "${CLAUDE_SKILL_DIR}/image2image.py" $ARGUMENTS
```

## 结果处理

解析输出的 JSON：
- 成功：`{"image_path": "output_images/xxx.png", "message": "图片编辑成功"}` → 告知用户图片路径
- 失败：`{"error": "..."}` → 说明失败原因（如文件不存在、API 错误）

## 可选参数

```bash
python "${CLAUDE_SKILL_DIR}/image2image.py" "图片路径" "编辑描述" --output 文件名.png --dir 输出目录
```
