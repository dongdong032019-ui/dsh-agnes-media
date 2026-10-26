# -*- coding: utf-8 -*-
"""
42_agnes_video_poll.py —— 续查已创建的 Agnes 视频任务并下载

用法：
  python 42_agnes_video_poll.py task_xxxx --model agnes-video-2.5-flash
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
OUT_DIR = r"./output/videos"


def out(s):
    sys.stdout.reconfigure(encoding="utf-8")
    print(s, flush=True)


def load_key():
    k = os.environ.get("AGNES_API_KEY", "").strip()
    if k:
        return k
    home = os.environ.get("DSH_HOME") or os.path.join(os.environ.get("APPDATA", ""), "dsh-desktop", "harness")
    cred = os.path.join(home, ".credentials.yaml")
    if os.path.isfile(cred):
        for line in open(cred, "r", encoding="utf-8"):
            s = line.strip()
            if s.startswith("AGNES_API_KEY:"):
                v = s.split(":", 1)[1].strip().strip('"').strip("'")
                if v:
                    return v
    return ""


def get_json(url, key, timeout=60):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + key})
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
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
    return os.path.getsize(dst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video_id")
    ap.add_argument("--model", default="agnes-video-2.5-flash")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--outdir", default=OUT_DIR)
    args = ap.parse_args()

    key = load_key()
    if not key:
        out("[缺少密钥] 未找到 AGNES_API_KEY")
        sys.exit(2)

    q = urllib.parse.urlencode({"video_id": args.video_id, "model_name": args.model})
    url = "%s/agnesapi?%s" % (BASE, q)
    t0, last, attempt = time.time(), None, 0
    while time.time() - t0 < args.timeout:
        c, r = get_json(url, key)
        if c == 429:
            backoff = min(30, 5 * (1 + attempt))
            attempt += 1
            out("[轮询] 429 限流，退避 %ds" % backoff)
            time.sleep(backoff)
            continue
        if c != 200:
            out("[轮询] HTTP %s %s" % (c, json.dumps(r, ensure_ascii=False)[:300]))
            time.sleep(5)
            continue
        st, pg = r.get("status"), r.get("progress")
        if (st, pg) != last:
            out("[轮询] %5.0fs status=%s progress=%s" % (time.time() - t0, st, pg))
            last = (st, pg)
        if st == "completed":
            vurl = r.get("url")
            if not vurl:
                out("[失败] completed 但无 url: " + json.dumps(r, ensure_ascii=False)[:500])
                sys.exit(1)
            os.makedirs(args.outdir, exist_ok=True)
            dst = os.path.join(args.outdir, "agnes_%s_%s.mp4" % (time.strftime("%Y%m%d_%H%M%S"), args.video_id[-8:]))
            n = download(vurl, dst)
            out("[保存] %s (%.2f MB)" % (dst, n / 1024 / 1024))
            out("[完成] 用时 %.0fs  url=%s" % (time.time() - t0, vurl))
            return
        if st == "failed":
            out("[失败] " + json.dumps(r.get("error"), ensure_ascii=False))
            sys.exit(1)
        time.sleep(3.0)
    out("[超时] video_id=%s 稍后再查：%s" % (args.video_id, url))
    sys.exit(3)


if __name__ == "__main__":
    main()

