# dsh-agnes-media

Two small, dependency-free (stdlib only) Python CLIs that drive **Agnes AI** multimodal endpoints for image and video generation. Built for [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) workflows, but usable anywhere Python 3.10+ runs.

```
40_agnes_image.py       text-to-image / image-to-image / multi-image compose
41_agnes_video.py       text / keyframe / reference video, create + poll + download
42_agnes_video_poll.py  resume polling an existing video task
```

## Why this exists

Agnes exposes two different API shapes:

- images: `POST /v1/images/generations` — synchronous, `model` + `prompt` + `size`, `response_format` must live inside `extra_body`
- videos: `POST /v1/videos` — asynchronous, returns a `video_id`, then `GET /agnesapi?video_id=…&model_name=…` until `status=completed`

Both are easy to get wrong (top-level `response_format` is rejected; the video query needs `model_name` for anything that is not `text` mode). These scripts encode the working shape and add sane retries.

## Configuration

China-region base URL is `https://api.agnes-ai.cn`. The `.com` host answers `401` for keys issued on the China site — that mistake costs an hour, so it is hardcoded.

The key is read from, in order:

1. `AGNES_API_KEY` environment variable
2. `$DSH_HOME/.credentials.yaml` (`AGNES_API_KEY: "sk-…"`)
3. `%APPDATA%/dsh-desktop/harness/.credentials.yaml`

Nothing else is required — no SDK, no `requests`.

## Usage

```bash
# image, 1:1
python 40_agnes_image.py "a cat on a sunny wooden windowsill, shallow depth of field" --ratio 1:1

# image, explicit size + reference image (image-to-image)
python 40_agnes_image.py "switch the background to night, keep the subject" \
  --size 1024x768 --image https://example.com/in.png

# video, 5 s @ 720P, text mode
python 41_agnes_video.py "rainy neon city, a silver car drives past, cinematic" \
  --seconds 5 --size 720P --ratio 16:9

# resume an interrupted video job
python 42_agnes_video_poll.py video_xxx --model agnes-video-2.5-flash
```

Outputs land in `./output/images` and `./output/videos` by default; pass `--outdir` to change it.

## Notes from real use

- Model availability is **account-group dependent**. On a fresh account `agnes-image-2.0-flash` returned `model_not_found` while `agnes-image-2.5-flash` worked; `agnes-video-2.5` returned `403 insufficient_user_quota` while `agnes-video-2.5-flash` was accepted. List what you actually have:

  ```bash
  curl -H "Authorization: Bearer $AGNES_API_KEY" https://api.agnes-ai.cn/v1/models
  ```

- Image generation is free during the current promotion; **video is billed per second** (720P ¥0.15/s, 1080P/1K ¥0.25/s, 2K ¥0.35/s). Default output is a 5 s 720P clip for that reason.
- The polling endpoint rate-limits aggressively. The scripts back off 5 s → 30 s on `429` instead of hammering every 1.5 s.

## License

MIT
