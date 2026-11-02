# -*- coding: utf-8 -*-
"""数据库层：Supabase 云数据库（REST API）。

表结构见 supabase_schema.sql（需在 Supabase SQL Editor 里执行一次建表）。

用户隔离：所有表带 user_code 字段，所有业务函数第一个参数为 user，
查询/写入/删除均限定在该编码的数据空间内。
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
    # 优先从 Streamlit Secrets 读（Streamlit Cloud 部署时）
    try:
        import streamlit as st
        if st.secrets.get("SUPABASE_URL"):
            url = st.secrets["SUPABASE_URL"].rstrip("/")
            key = st.secrets.get("SUPABASE_KEY", "")
            return url, key
    except Exception:
        pass
    # 退回到环境变量 / .env（本地运行时）
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


def _post(table, data, upsert=False, on_conflict=None):
    _check()
    url, _ = _cfg()
    headers = _headers()
    params = None
    if upsert:
        headers["Prefer"] = "resolution=merge-duplicates"
        if on_conflict:
            params = {"on_conflict": on_conflict}
    r = requests.post(f"{url}/rest/v1/{table}", headers=headers, json=data,
                      params=params, timeout=25)
    if r.status_code >= 400:
        raise RuntimeError(f"写入 {table} 失败({r.status_code}): {r.text[:300]}")
    return r


def _delete(table, id_val, user=None):
    _check()
    url, _ = _cfg()
    params = {"id": f"eq.{id_val}"}
    if user:
        params["user_code"] = f"eq.{user}"
    r = requests.delete(f"{url}/rest/v1/{table}", headers=_headers(),
                        params=params, timeout=25)
    if r.status_code >= 400:
        raise RuntimeError(f"删除失败({r.status_code}): {r.text[:300]}")
    return r


def init_db():
    """Supabase 建表通过 supabase_schema.sql 完成，这里无需操作。"""
    _check()


# ---------- 每日基础数据 ----------

def add_log(user, date, weight=None, sleep_hours=None, mood=None, note=""):
    _post("daily_logs", {
        "user_code": user,
        "date": str(date),
        "weight": weight,
        "sleep_hours": sleep_hours,
        "mood": mood,
        "note": note,
    }, upsert=True, on_conflict="user_code,date")


def get_logs(user) -> pd.DataFrame:
    rows = _get("daily_logs", {"select": "*", "user_code": f"eq.{user}",
                               "order": "date.asc"})
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=["id", "user_code", "date", "weight", "sleep_hours",
                                   "mood", "note", "created_at"])
    elif "date" in df:
        df["date"] = pd.to_datetime(df["date"])
    return df


# ---------- 食物明细 ----------

def add_food_entry(user, date, name, amount, unit, calories):
    _post("food_entries", {
        "user_code": user,
        "date": str(date),
        "name": name,
        "amount": amount,
        "unit": unit,
        "calories": calories,
    })


def get_food_entries(user, date=None) -> pd.DataFrame:
    params = {"select": "*", "user_code": f"eq.{user}", "order": "id.asc"}
    if date:
        params["date"] = f"eq.{date}"
    df = pd.DataFrame(_get("food_entries", params))
    if df.empty:
        df = pd.DataFrame(columns=["id", "user_code", "date", "name", "amount",
                                   "unit", "calories", "created_at"])
    return df


def delete_food_entry(user, entry_id):
    _delete("food_entries", entry_id, user)


# ---------- 运动明细 ----------

def add_exercise_entry(user, date, name, minutes, calories):
    _post("exercise_entries", {
        "user_code": user,
        "date": str(date),
        "name": name,
        "minutes": minutes,
        "calories": calories,
    })


def get_exercise_entries(user, date=None) -> pd.DataFrame:
    params = {"select": "*", "user_code": f"eq.{user}", "order": "id.asc"}
    if date:
        params["date"] = f"eq.{date}"
    df = pd.DataFrame(_get("exercise_entries", params))
    if df.empty:
        df = pd.DataFrame(columns=["id", "user_code", "date", "name", "minutes",
                                   "calories", "created_at"])
    return df


def delete_exercise_entry(user, entry_id):
    _delete("exercise_entries", entry_id, user)


# ---------- 每日汇总 ----------

def get_daily_summary(user) -> pd.DataFrame:
    """合并三张表，得到每天一条的汇总（仅当前编码的数据）。"""
    logs = get_logs(user)
    foods = get_food_entries(user)
    exercises = get_exercise_entries(user)

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

def set_setting(user, key, value):
    _post("settings", {"user_code": user, "key": key, "value": str(value)},
          upsert=True, on_conflict="user_code,key")


def get_setting(user, key, default=None):
    rows = _get("settings", {"key": f"eq.{key}", "user_code": f"eq.{user}", "limit": "1"})
    if rows:
        return rows[0].get("value", default)
    return default


def get_all_settings(user):
    rows = _get("settings", {"select": "*", "user_code": f"eq.{user}"})
    return {r["key"]: r["value"] for r in rows}
