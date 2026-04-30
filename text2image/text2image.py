#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文本生成图片（text2image）

用法：
  python text2image.py "一只在樱花树下打太极的熊猫，水墨画风格，高清"
  python text2image.py "sunset over mountains" --output my.png --dir /tmp/images

依赖：pip install requests python-dotenv
配置：在 .env 中设置 OPENAI_API_KEY / OPENAI_API_BASE_URL / IMAGE_MODEL
"""

import argparse
import base64
import json
import mimetypes
import os
import sys
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

# 按优先级查找 .env：当前目录 → 脚本所在目录 → 上级目录
for _p in [Path.cwd(), Path(__file__).parent, Path(__file__).parent.parent]:
    if (_p / ".env").exists():
        load_dotenv(_p / ".env")
        break
else:
    load_dotenv()

# ── 配置 ──────────────────────────────────────────────────────────────────────
_API_KEY  = os.getenv("OPENAI_API_KEY", "")
_BASE_URL = os.getenv("OPENAI_API_BASE_URL", "").rstrip("/")
_MODEL    = os.getenv("IMAGE_MODEL", "doubao-seedream-4-5-251128")
_API_URL  = os.getenv("TEXT2IMAGE_API_URL") or f"{_BASE_URL}/images/generations"


# ── 核心逻辑 ──────────────────────────────────────────────────────────────────

def _generate(prompt: str) -> list[dict]:
    """调用文生图 API，返回原始 data 列表。"""
    headers = {
        "Authorization": f"Bearer {_API_KEY}",
        "Content-Type":  "application/json",
    }
    payload = {"model": _MODEL, "prompt": prompt}
    if not _MODEL.startswith("gpt-image"):
        payload["watermark"] = False

    resp = requests.post(
        _API_URL, headers=headers, json=payload,
        proxies={"http": None, "https": None}, timeout=240,
    )
    resp.raise_for_status()
    return resp.json().get("data", [])


def _save(data: list[dict], out_path: str) -> bool:
    """将 API 返回的图片（URL 或 base64）写入 out_path。"""
    for item in data:
        url = item.get("url", "")
        if url:
            r = requests.get(url, timeout=60, proxies={"http": None, "https": None})
            r.raise_for_status()
            with open(out_path, "wb") as f:
                f.write(r.content)
            return True
    for item in data:
        b64 = item.get("b64_json", "")
        if b64:
            with open(out_path, "wb") as f:
                f.write(base64.b64decode(b64))
            return True
    return False


# ── 对外接口（供 Claude Code skill 调用）─────────────────────────────────────

def skill_main(params: dict) -> dict:
    """
    参数：
      prompt     (str, 必填) 图片描述
      filename   (str, 可选) 输出文件名，默认时间戳.png
      output_dir (str, 可选) 输出目录，默认 ./output_images
    返回：
      {"image_path": "...", "message": "图片生成成功"}
      {"error": "..."}
    """
    params    = params or {}
    prompt    = params.get("prompt", "").strip()
    if not prompt:
        return {"error": "参数 prompt 不能为空"}
    if not _API_KEY:
        return {"error": "未配置 OPENAI_API_KEY，请检查 .env 文件"}

    filename   = params.get("filename") or f"{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
    output_dir = params.get("output_dir") or "output_images"
    os.makedirs(output_dir, exist_ok=True)
    out_path   = os.path.join(output_dir, filename)

    try:
        data = _generate(prompt)
    except requests.HTTPError as e:
        return {"error": f"API 请求失败（HTTP {e.response.status_code}）：{e.response.text[:300]}"}
    except Exception as e:
        return {"error": f"API 调用异常：{e}"}

    if not data:
        return {"error": "API 返回数据为空"}

    try:
        ok = _save(data, out_path)
    except Exception as e:
        return {"error": f"图片保存失败：{e}"}

    if not ok:
        return {"error": "API 返回中未找到有效图片（既无 url 也无 b64_json）"}

    return {"image_path": out_path, "message": "图片生成成功"}


# ── CLI 入口 ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="文本生成图片",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("prompt", nargs="+", help="图片描述（提示词）")
    parser.add_argument("--output", "-o", metavar="FILENAME", help="输出文件名")
    parser.add_argument("--dir",    "-d", metavar="DIR",      help="输出目录（默认 output_images/）")
    args = parser.parse_args()

    params = {"prompt": " ".join(args.prompt)}
    if args.output:
        params["filename"] = args.output
    if args.dir:
        params["output_dir"] = args.dir

    result = skill_main(params)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if "image_path" in result else 1)


if __name__ == "__main__":
    main()
