# -*- coding: utf-8 -*-
"""照片管理：上传到 Supabase 云存储，并生成变化动画 GIF。"""
import io
import os

import requests
from PIL import Image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BUCKET = "photos"


def _load_env():
    env_path = os.path.join(BASE_DIR, ".env")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())


_load_env()


def _cfg():
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_KEY", "")
    return url, key


def _headers(content_type="application/json"):
    _, key = _cfg()
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": content_type,
    }


def _public_url(path):
    url, _ = _cfg()
    return f"{url}/storage/v1/object/public/{BUCKET}/{path}"


def save_photo(date_str, image_bytes):
    """上传某天照片到云存储（同一天重复上传会覆盖）。"""
    url, _ = _cfg()
    if not url:
        raise RuntimeError("Supabase 未配置")

    img = Image.open(io.BytesIO(image_bytes))
    img = img.convert("RGB")
    img.thumbnail((1200, 1200))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)

    path = f"{date_str}.jpg"
    r = requests.post(
        f"{url}/storage/v1/object/{BUCKET}/{path}",
        headers=_headers("image/jpeg"),
        data=buf.getvalue(),
        timeout=40,
    )
    if r.status_code >= 300:
        raise RuntimeError(f"照片上传失败({r.status_code}): {r.text[:200]}")
    return _public_url(path)


def get_photo(date_str):
    """返回某天照片的公网 URL，不存在则返回 None。"""
    url, _ = _cfg()
    if not url:
        return None
    public_url = _public_url(f"{date_str}.jpg")
    try:
        r = requests.head(public_url, timeout=15)
        if r.status_code == 200:
            return public_url
    except Exception:  # noqa: BLE001
        pass
    return None


def list_photos():
    """返回按日期升序的照片列表 [{date, path}]。"""
    url, _ = _cfg()
    if not url:
        return []
    r = requests.post(
        f"{url}/storage/v1/object/list/{BUCKET}",
        headers=_headers("application/json"),
        json={"prefix": "", "limit": 500, "offset": 0},
        timeout=25,
    )
    if r.status_code >= 300:
        return []
    result = []
    for it in (r.json() or []):
        name = it.get("name", "")
        if name.lower().endswith((".jpg", ".jpeg", ".png")):
            date_str = os.path.splitext(name)[0]
            result.append({"date": date_str, "path": _public_url(name)})
    result.sort(key=lambda x: x["date"])
    return result


def make_gif(photos, output_path=None, duration=400, width=500):
    """下载照片序列，合成动画 GIF。photos 为 [{date, path}]。"""
    if len(photos) < 2:
        return None

    frames = []
    target_w = width
    target_h = None
    for p in photos:
        r = requests.get(p["path"], timeout=40)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        if target_h is None:
            target_h = max(1, int(img.size[1] * width / img.size[0]))
        frames.append(img.resize((target_w, target_h)))

    # 输出到内存，返回字节（避免云端写文件）
    buf = io.BytesIO()
    frames[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0,
        optimize=True,
    )
    buf.seek(0)
    return buf
