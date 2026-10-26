# -*- coding: utf-8 -*-
"""
41_agnes_video.py —— Agnes 生视频（异步：创建 + 轮询 + 下载）

用法：
  python 41_agnes_video.py "雨后的未来城市，霓虹倒影，跑车缓行，电影级运镜，自然环境声" --seconds 5 --size 720P --ratio 16:9
  python 41_agnes_video.py "保持主体，改为夜景" --mode keyframe --first https://x/f.png --last https://x/l.png

密钥：环境变量 AGNES_API_KEY → %DSH_HOME%\\.credentials.yaml
计费：720P ¥0.15/秒 ；1080P、1K ¥0.25/秒 ；2K ¥0.35/秒（示例默认 5 秒 720P ≈ ¥0.75）
产物：学习库\\04_产出\\02_视频\\
"""
import os
import sys
import json
import time
import argparse
import urllib.parse
import urllib.request
import urllib.error

BASE = "https://api.agnes-ai.cn"
MODEL = "agnes-video-2.5"
OUT_DIR = r"./output/videos"


def out(s):
    sys.stdout.reconfigure(encoding="utf-8")
    print(s, flush=True)


def load_key():
    k = os.environ.get("AGNES_API_KEY", "").strip()
    if k:
        return k, "env:AGNES_API_KEY"
    home = os.environ.get("DSH_HOME") or os.path.join(os.environ.get("APPDATA", ""), "dsh-desktop", "harness")
    cred = os.path.join(home, ".credentials.yaml")
    if os.path.isfile(cred):
        with open(cred, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if s.startswith("AGNES_API_KEY:"):
                    v = s.split(":", 1)[1].strip().strip('"').strip("'")
                    if v:
                        return v, cred
    return "", None


def http_json(url, key, payload=None, timeout=120):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST" if data else "GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, {"raw": e.read().decode("utf-8", "replace")}
    except Exception as e:
        return -1, {"raw": repr(e)}


def download(url, dst):
    req = urllib.request.Request(url, headers={"User-Agent": "dsh-agnes/1.0"})
    with urllib.request.urlopen(req, timeout=600) as r, open(dst, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    return os.path.getsize(dst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt")
    ap.add_argument("--model", default=MODEL, help="agnes-video-2.5 / agnes-video-2.5-flash")
    ap.add_argument("--mode", default="text", choices=["text", "keyframe", "reference"])
    ap.add_argument("--seconds", default="5")
    ap.add_argument("--size", default="720P", choices=["720P", "1080P", "1K", "2K"])
    ap.add_argument("--ratio", default="16:9", choices=["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"])
    ap.add_argument("--first", default="", help="keyframe 模式首帧 URL")
    ap.add_argument("--last", default="", help="keyframe 模式尾帧 URL")
    ap.add_argument("--image", action="append", default=[], help="reference 模式参考图 URL，可多次")
    ap.add_argument("--timeout", type=int, default=900, help="最长轮询秒数")
    ap.add_argument("--outdir", default=OUT_DIR)
    args = ap.parse_args()

    key, src = load_key()
    if not key:
        out("[缺少密钥] 未找到 AGNES_API_KEY。见 30_set_secret.ps1 用法。")
        sys.exit(2)

    payload = {
        "model": args.model,
        "prompt": args.prompt,
        "mode": args.mode,
        "seconds": str(args.seconds),
        "size": args.size,
        "aspect_ratio": args.ratio,
    }
    if args.mode == "keyframe":
        if args.first:
            payload["first_frame"] = args.first
        if args.last:
            payload["last_frame"] = args.last
        if not (args.first or args.last):
            out("[参数错误] keyframe 模式至少给 --first 或 --last")
            sys.exit(2)
    if args.mode == "reference":
        if not args.image:
            out("[参数错误] reference 模式需要至少一个 --image")
            sys.exit(2)
        payload["images"] = args.image

    out("[密钥] 来源：%s" % src)
    out("[创建] POST %s/v1/videos  model=%s %s %ss %s" % (BASE, args.model, args.size, args.seconds, args.ratio))
    code, resp = http_json(BASE + "/v1/videos", key, payload)
    out("[创建] HTTP %s" % code)
    if code != 200:
        out("[失败] " + json.dumps(resp, ensure_ascii=False)[:1200])
        sys.exit(1)

    vid = resp.get("video_id") or resp.get("id")
    if not vid:
        out("[失败] 响应里没有 video_id：" + json.dumps(resp, ensure_ascii=False)[:800])
        sys.exit(1)
    out("[任务] video_id=%s status=%s" % (vid, resp.get("status")))

    q = urllib.parse.urlencode({"video_id": vid, "model_name": args.model})
    url = "%s/agnesapi?%s" % (BASE, q)
    t0 = time.time()
    last = None
    attempt = 0
    while time.time() - t0 < args.timeout:
        time.sleep(3.0)
        c, r = http_json(url, key, timeout=60)
        if c == 429:
            backoff = min(30, 5 * (1 + attempt))
            attempt += 1
            out("[轮询] 429 限流，退避 %ds" % backoff)
            time.sleep(backoff)
            continue
        if c != 200:
            attempt += 1
            out("[轮询] HTTP %s（继续）" % c)
            time.sleep(5)
            continue
        st = r.get("status")
        pg = r.get("progress")
        if (st, pg) != last:
            out("[轮询] %5.0fs status=%s progress=%s" % (time.time() - t0, st, pg))
            last = (st, pg)
        if st == "completed":
            vurl = r.get("url")
            if not vurl:
                out("[失败] completed 但没有 url：" + json.dumps(r, ensure_ascii=False)[:800])
                sys.exit(1)
            os.makedirs(args.outdir, exist_ok=True)
            dst = os.path.join(args.outdir, "agnes_%s_%s.mp4" % (time.strftime("%Y%m%d_%H%M%S"), vid[-8:]))
            n = download(vurl, dst)
            out("[保存] %s (%.1f MB)" % (dst, n / 1024 / 1024))
            out("[完成] 用时 %.0fs" % (time.time() - t0))
            return
        if st == "failed":
            out("[失败] " + json.dumps(r.get("error"), ensure_ascii=False))
            sys.exit(1)

    out("[超时] %ds 内未完成，video_id=%s 可稍后手动查询：%s" % (args.timeout, vid, url))
    sys.exit(3)


if __name__ == "__main__":
    main()



