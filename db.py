# -*- coding: utf-8 -*-
"""数据库层：Supabase 云数据库（REST API）。

表结构见 supabase_schema.sql（需在 Supabase SQL Editor 里执行一次建表）。
"""
import os

import pandas as pd
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


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


def _check():
    url, key = _cfg()
    if not url or not key:
        raise RuntimeError("Supabase 未配置：请设置 SUPABASE_URL 和 SUPABASE_KEY")


def _get(table, params=None):
    _check()
    url, _ = _cfg()
    r = requests.get(f"{url}/rest/v1/{table}", headers=_headers(), params=params, timeout=25)
    if r.status_code >= 400:
        raise RuntimeError(f"查询 {table} 失败({r.status_code}): {r.text[:300]}")
    return r.json() if r.text else []


def _post(table, data, upsert=False):
    _check()
    url, _ = _cfg()
    headers = _headers()
    if upsert:
        headers["Prefer"] = "resolution=merge-duplicates"
    r = requests.post(f"{url}/rest/v1/{table}", headers=headers, json=data, timeout=25)
    if r.status_code >= 400:
        raise RuntimeError(f"写入 {table} 失败({r.status_code}): {r.text[:300]}")
    return r


def _delete(table, id_val):
    _check()
    url, _ = _cfg()
    r = requests.delete(f"{url}/rest/v1/{table}", headers=_headers(),
                        params={"id": f"eq.{id_val}"}, timeout=25)
    if r.status_code >= 400:
        raise RuntimeError(f"删除失败({r.status_code}): {r.text[:300]}")
    return r


def init_db():
    """Supabase 建表通过 supabase_schema.sql 完成，这里无需操作。"""
    _check()


# ---------- 每日基础数据 ----------

def add_log(date, weight=None, sleep_hours=None, mood=None, note=""):
    _post("daily_logs", {
        "date": str(date),
        "weight": weight,
        "sleep_hours": sleep_hours,
        "mood": mood,
        "note": note,
    }, upsert=True)


def get_logs() -> pd.DataFrame:
    rows = _get("daily_logs", {"select": "*", "order": "date.asc"})
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=["id", "date", "weight", "sleep_hours", "mood", "note", "created_at"])
    elif "date" in df:
        df["date"] = pd.to_datetime(df["date"])
    return df


# ---------- 食物明细 ----------

def add_food_entry(date, name, amount, unit, calories):
    _post("food_entries", {
        "date": str(date),
        "name": name,
        "amount": amount,
        "unit": unit,
        "calories": calories,
    })


def get_food_entries(date=None) -> pd.DataFrame:
    params = {"select": "*", "order": "id.asc"}
    if date:
        params["date"] = f"eq.{date}"
    df = pd.DataFrame(_get("food_entries", params))
    if df.empty:
        df = pd.DataFrame(columns=["id", "date", "name", "amount", "unit", "calories", "created_at"])
    return df


def delete_food_entry(entry_id):
    _delete("food_entries", entry_id)


# ---------- 运动明细 ----------

def add_exercise_entry(date, name, minutes, calories):
    _post("exercise_entries", {
        "date": str(date),
        "name": name,
        "minutes": minutes,
        "calories": calories,
    })


def get_exercise_entries(date=None) -> pd.DataFrame:
    params = {"select": "*", "order": "id.asc"}
    if date:
        params["date"] = f"eq.{date}"
    df = pd.DataFrame(_get("exercise_entries", params))
    if df.empty:
        df = pd.DataFrame(columns=["id", "date", "name", "minutes", "calories", "created_at"])
    return df


def delete_exercise_entry(entry_id):
    _delete("exercise_entries", entry_id)


# ---------- 每日汇总 ----------

def get_daily_summary() -> pd.DataFrame:
    """合并三张表，得到每天一条的汇总。"""
    logs = get_logs()
    foods = get_food_entries()
    exercises = get_exercise_entries()

    if not foods.empty:
        foods["date"] = pd.to_datetime(foods["date"])
        food_sum = foods.groupby("date")["calories"].sum().reset_index().rename(
            columns={"calories": "intake"})
    else:
        food_sum = pd.DataFrame(columns=["date", "intake"])

    if not exercises.empty:
        exercises["date"] = pd.to_datetime(exercises["date"])
        ex_sum = exercises.groupby("date")["calories"].sum().reset_index().rename(
            columns={"calories": "exercise_kcal"})
    else:
        ex_sum = pd.DataFrame(columns=["date", "exercise_kcal"])

    df = logs
    if not food_sum.empty:
        df = df.merge(food_sum, on="date", how="left")
    else:
        df["intake"] = 0
    if not ex_sum.empty:
        df = df.merge(ex_sum, on="date", how="left")
    else:
        df["exercise_kcal"] = 0

    df["intake"] = df["intake"].fillna(0)
    df["exercise_kcal"] = df["exercise_kcal"].fillna(0)
    return df


# ---------- 设置 ----------

def set_setting(key, value):
    _post("settings", {"key": key, "value": str(value)}, upsert=True)


def get_setting(key, default=None):
    rows = _get("settings", {"key": f"eq.{key}", "limit": "1"})
    if rows:
        return rows[0].get("value", default)
    return default


def get_all_settings():
    rows = _get("settings", {"select": "*"})
    return {r["key"]: r["value"] for r in rows}
