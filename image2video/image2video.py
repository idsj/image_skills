#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图生视频（image2video）—— 走 OpenAI 兼容网关（new-api 类）的异步视频任务接口

用法：
  python image2video.py poster.png "晶核缓缓脉动，人物发丝随风飘动"
  python image2video.py a.png "..." --model MiniMax-H3 --duration 4 --resolution 2K
  python image2video.py a.png "..." --last b.png            # 首尾帧（尾帧未实测）
  python image2video.py --resume task_xxx                    # 续查已提交的任务并下载

流程：POST /v1/video/generations 建任务 → 每 10s GET /v1/video/generations/{task_id}
      → SUCCESS 后下载 mp4。task_id 一拿到就打印到 stderr 并追加到 tasks.log，
      脚本中断也能用 --resume 接着查。

配置：.env（当前目录 / 脚本目录 / 上级目录，取先找到的）——
      VIDEO_API_KEY / VIDEO_API_BASE_URL，未填时回退到 OPENAI_API_KEY / OPENAI_API_BASE_URL
依赖：pip install requests pillow python-dotenv
"""
import argparse, base64, io, json, os, re, sys, time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv
from PIL import Image

HERE = Path(__file__).parent
for _p in [Path.cwd(), HERE, HERE.parent]:
    if (_p / ".env").exists():
        load_dotenv(_p / ".env")
        break
else:
    load_dotenv()
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

KEY = os.getenv("VIDEO_API_KEY") or os.getenv("OPENAI_API_KEY", "")
BASE = (os.getenv("VIDEO_API_BASE_URL") or os.getenv("OPENAI_API_BASE_URL", "")).rstrip("/")
TASK_LOG = HERE / "tasks.log"
MAX_SIDE = 2560          # 上传前把长边压到这个以内，避免请求体过大

S = requests.Session()
S.trust_env = False      # 系统代理会干扰网关请求
H = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def data_url(path):
    im = Image.open(path).convert("RGB")
    if max(im.size) > MAX_SIDE:
        r = MAX_SIDE / max(im.size)
        im = im.resize((round(im.width * r), round(im.height * r)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=92)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def build_body(a):
    first = data_url(a.image)
    last = data_url(a.last) if a.last else None
    m = a.model.lower()
    body = {"model": a.model, "prompt": a.prompt, "image": first, "duration": a.duration}
    if m.startswith("minimax"):
        meta = {"first_frame_image": first, "duration": a.duration,
                "resolution": a.resolution or "2K", "prompt_optimizer": False}
        if last:
            meta["last_frame_image"] = last
    elif "seedance" in m:
        meta = {"ratio": "adaptive", "resolution": a.resolution or "1080p", "duration": a.duration,
                "camera_fixed": a.camera_fixed, "generate_audio": True, "watermark": False}
        if last:
            meta["last_frame_image"] = last
    else:
        meta = {"duration": a.duration}
        if a.resolution:
            meta["resolution"] = a.resolution
        if last:
            body["images"] = [first, last]
    body["metadata"] = meta
    return body


def explain(text):
    hints = {
        "model_price_error": "网关后台没给该模型配计费规则，需管理员补配置（不是参数问题）",
        "No available channel": "模型名不对或本分组无通道——用 /v1/models 里的完整 ID（带日期后缀）",
        "does not support duration": "该模型不支持这个时长，按报错里的列表改 --duration",
        "does not support resolution": "该模型不支持这个分辨率，按报错里的列表改 --resolution",
        "Invalid token": "key 无效，检查 .env 的 VIDEO_API_KEY",
    }
    for k, v in hints.items():
        if k in text:
            return v
    return None


def poll(tid, out, timeout):
    t0, last_st = time.time(), None
    while time.time() - t0 < timeout:
        try:
            j = S.get(f"{BASE}/video/generations/{tid}", headers=H, timeout=60).json()
        except Exception as e:
            log(f"  查询出错（继续重试）: {e}")
            time.sleep(10)
            continue
        txt = json.dumps(j, ensure_ascii=False)
        # 任务属于别的 key（换过 key）或 ID 写错时，网关回 task_not_exist 且永远不会变，不能空等；
        # 其他错误（如临时 5xx）可能自愈，记一笔继续重试
        if j.get("code") == "task_not_exist":
            return {"error": "查不到这个任务（task_id 错误，或任务是用别的 key 提交的）",
                    "task_id": tid, "raw": txt[:500]}
        if j.get("error") and not j.get("data"):
            log(f"  查询返回错误（继续重试）: {txt[:200]}")
            time.sleep(10)
            continue
        d = j.get("data") if isinstance(j.get("data"), dict) else j
        st = str(d.get("status") or "").lower()
        if st != last_st:
            log(f"  {time.time()-t0:5.0f}s  status={st}")
            last_st = st
        if st in ("success", "succeeded", "completed"):
            mm = re.search(r'https?://[^"\s]+?\.mp4[^"\s]*', txt) or \
                 re.search(r'"(?:url|video_url|result_url)"\s*:\s*"(https?://[^"]+)"', txt)
            if not mm:
                return {"error": "任务成功但没找到视频地址", "task_id": tid, "raw": txt[:1500]}
            url = mm.group(1) if mm.lastindex else mm.group(0)
            try:
                v = S.get(url, timeout=600)
                v.raise_for_status()
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(v.content)
            except Exception as e:
                # 服务端任务已完成，下载失败不该丢结果：给出地址和续查命令
                return {"error": f"任务已完成但下载失败: {e}", "task_id": tid, "video_url": url,
                        "hint": f"稍后用 --resume {tid} 重新下载（视频链接可能有有效期）"}
            return {"video_path": str(out), "task_id": tid, "quota": d.get("quota"),
                    "elapsed_s": round(time.time() - t0), "message": "视频生成成功"}
        if st in ("failure", "failed", "error", "cancelled"):
            return {"error": "任务失败", "task_id": tid, "raw": txt[:1500]}
        time.sleep(10)
    return {"error": f"等待超时 {timeout}s，可稍后 --resume {tid}", "task_id": tid}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image", nargs="?")
    ap.add_argument("prompt", nargs="?")
    ap.add_argument("--model", default=os.getenv("VIDEO_MODEL", "MiniMax-H3"))
    ap.add_argument("--duration", type=int, default=4)
    ap.add_argument("--resolution", help="MiniMax-H3: 480P/768P/2K；Seedance: 480p/720p/1080p")
    ap.add_argument("--last", help="尾帧图片（可选）")
    ap.add_argument("--camera-fixed", action="store_true", help="Seedance 固定机位")
    ap.add_argument("--output")
    ap.add_argument("--dir", default=str(HERE / "output_videos"))
    ap.add_argument("--resume", metavar="TASK_ID")
    ap.add_argument("--timeout", type=int, default=1800)
    a = ap.parse_args()

    if not KEY or not BASE:
        print(json.dumps({"error": "未配置 VIDEO_API_KEY / VIDEO_API_BASE_URL（.env）"}, ensure_ascii=False))
        sys.exit(1)
    name = a.output or f"i2v_{datetime.now():%Y%m%d_%H%M%S}.mp4"
    out = Path(a.dir) / name
    if out.exists():
        # 不覆盖已有视频：加时间戳后缀另存（在提交前定好，tasks.log 记的就是最终路径）
        out = out.with_name(f"{out.stem}_{datetime.now():%Y%m%d_%H%M%S}{out.suffix}")
        log(f"输出文件已存在，改存为 {out}")

    if a.resume:
        res = poll(a.resume, out, a.timeout)
    else:
        if not (a.image and a.prompt):
            ap.error("需要 <图片路径> <提示词>，或 --resume TASK_ID")
        for p in [a.image] + ([a.last] if a.last else []):
            if not Path(p).exists():
                print(json.dumps({"error": f"图片不存在: {p}"}, ensure_ascii=False))
                sys.exit(1)
        try:
            body = build_body(a)      # 图片损坏/格式不支持时 PIL 会抛异常
        except Exception as e:
            print(json.dumps({"error": f"图片处理失败: {e}"}, ensure_ascii=False))
            sys.exit(1)
        r = S.post(f"{BASE}/video/generations", headers=H, json=body, timeout=180)
        if r.status_code != 200:
            res = {"error": f"建任务失败 HTTP {r.status_code}", "raw": r.text[:1500]}
            h = explain(r.text)
            if h:
                res["hint"] = h
            print(json.dumps(res, ensure_ascii=False))
            sys.exit(1)
        j = r.json()
        data = j.get("data") if isinstance(j.get("data"), dict) else {}
        tid = j.get("task_id") or j.get("id") or data.get("task_id")
        if not tid:
            print(json.dumps({"error": "建任务响应里没有 task_id", "raw": r.text[:1500]},
                             ensure_ascii=False))
            sys.exit(1)
        log(f"task_id={tid}  model={a.model}")
        with open(TASK_LOG, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%F %T}\t{tid}\t{a.model}\t{a.image}\t{out}\n")
        res = poll(tid, out, a.timeout)

    print(json.dumps(res, ensure_ascii=False))
    sys.exit(0 if "video_path" in res else 1)


if __name__ == "__main__":
    main()
