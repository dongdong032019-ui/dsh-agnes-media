# -*- coding: utf-8 -*-
"""
40_agnes_image.py —— Agnes 生图（文生图 / 图生图）

用法：
  python 40_agnes_image.py "一只橘猫坐在窗前，晨光，浅景深" --ratio 1:1
  python 40_agnes_image.py "把背景换成夜景，保留人物" --image https://x/a.png --size 1024x768

密钥来源（按优先级）：环境变量 AGNES_API_KEY → %DSH_HOME%\\.credentials.yaml 的 AGNES_API_KEY
产物：学习库\\04_产出\\01_图片\\
"""
import os
import sys
import json
import time
import argparse
import urllib.request
import urllib.error

BASE = "https://api.agnes-ai.cn"
MODEL = "agnes-image-2.5-flash"
OUT_DIR = r"./output/images"

RATIO_SIZE = {
    "1:1": "1024x1024",
    "4:3": "1024x768",
    "3:4": "768x1024",
    "16:9": "1280x720",
    "9:16": "720x1280",
    "3:2": "1024x683",
    "2:3": "683x1024",
}


def out(s):
    sys.stdout.reconfigure(encoding="utf-8")
    print(s, flush=True)


def load_key():
    k = os.environ.get("AGNES_API_KEY", "").strip()
    if k:
        return k, "env:AGNES_API_KEY"
    home = os.environ.get("DSH_HOME") or os.path.join(
        os.environ.get("APPDATA", ""), "dsh-desktop", "harness"
    )
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


def post_json(url, payload, key, timeout=360):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        return e.code, {"raw": body}
    except Exception as e:  # 网络层
        return -1, {"raw": repr(e)}


def download(url, dst):
    req = urllib.request.Request(url, headers={"User-Agent": "dsh-agnes/1.0"})
    with urllib.request.urlopen(req, timeout=300) as r, open(dst, "wb") as f:
        f.write(r.read())
    return os.path.getsize(dst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt")
    ap.add_argument("--model", default=MODEL, help="agnes-image-2.5-flash / 2.1-flash（2.0 不在本账号分组）")
    ap.add_argument("--ratio", default="1:1", choices=sorted(RATIO_SIZE.keys()))
    ap.add_argument("--size", default="", help="直接指定像素尺寸，优先于 --ratio")
    ap.add_argument("--image", action="append", default=[], help="图生图参考图 URL 或 data URI，可多次")
    ap.add_argument("--outdir", default=OUT_DIR)
    args = ap.parse_args()

    key, src = load_key()
    if not key:
        out("[缺少密钥] 未找到 AGNES_API_KEY。设置方法：")
        out(r'  pwsh -File 30_set_secret.ps1 -Name AGNES_API_KEY -Value "你的key"')
        out("  或先 setx AGNES_API_KEY \"你的key\" 后重开终端")
        sys.exit(2)

    size = args.size or RATIO_SIZE[args.ratio]
    payload = {
        "model": args.model,
        "prompt": args.prompt,
        "size": size,
        "extra_body": {"response_format": "url"},
    }
    if args.image:
        payload["extra_body"]["image"] = args.image

    out("[密钥] 来源：%s" % src)
    out("[请求] %s/v1/images/generations  model=%s size=%s images=%d" % (BASE, args.model, size, len(args.image)))
    t0 = time.time()
    code, resp = post_json(BASE + "/v1/images/generations", payload, key)
    dt = time.time() - t0
    out("[响应] HTTP %s  用时 %.1fs" % (code, dt))

    data = resp.get("data") or []
    if code != 200 or not data:
        out("[失败] 原始响应：" + json.dumps(resp, ensure_ascii=False)[:1500])
        if code == 401:
            out("提示：401 多为域名/密钥问题——本脚本已使用 api.agnes-ai.cn（中国站），请核对 key 是否中国站签发。")
        sys.exit(1)

    os.makedirs(args.outdir, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    saved = []
    for i, item in enumerate(data, 1):
        url = item.get("url")
        b64 = item.get("b64_json")
        if url:
            dst = os.path.join(args.outdir, "agnes_%s_%d.png" % (stamp, i))
            n = download(url, dst)
            saved.append(dst)
            out("[保存] %s (%.1f KB)" % (dst, n / 1024))
        elif b64:
            import base64
            dst = os.path.join(args.outdir, "agnes_%s_%d.png" % (stamp, i))
            with open(dst, "wb") as f:
                f.write(base64.b64decode(b64))
            saved.append(dst)
            out("[保存] %s (base64)" % dst)
        else:
            out("[警告] 第 %d 条无 url/b64_json" % i)

    out("[完成] %d 张 -> %s" % (len(saved), args.outdir))


if __name__ == "__main__":
    main()


