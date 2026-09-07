# -*- coding: utf-8 -*-
"""AI周报：优先调用 LLM，无 Key 时回退到本地规则统计报告（基于热量缺口给建议）。"""
import json
import re

import requests

from charts import detect_anomalies


def _pd_isna(v):
    try:
        import pandas as pd
        return pd.isna(v)
    except Exception:  # noqa: BLE001
        return v is None


def pd_isna(v):
    return _pd_isna(v)


# ---------- LLM 调用 ----------

def _build_prompt(df):
    payload = []
    for _, r in df.iterrows():
        payload.append({
            "日期": r["date"].strftime("%Y-%m-%d"),
            "体重kg": None if pd_isna(r.get("weight")) else round(float(r["weight"]), 1),
            "摄入kcal": None if pd_isna(r.get("intake")) else round(float(r["intake"])),
            "运动消耗kcal": None if pd_isna(r.get("exercise_kcal")) else round(float(r["exercise_kcal"])),
            "睡眠小时": None if pd_isna(r.get("sleep_hours")) else round(float(r["sleep_hours"]), 1),
            "心情1-5": None if pd_isna(r.get("mood")) else int(r["mood"]),
        })
    prompt = f"""你是一位专业的数据减肥教练。以下是用户最近的数据（JSON）：
{json.dumps(payload, ensure_ascii=False)}

请输出以下结构的周报（用中文，语气鼓励但客观）：
1. 【本周总结】体重变化、摄入是否达标、运动量、睡眠质量
2. 【热量缺口分析】根据摄入与运动消耗，判断减脂节奏是否合适
3. 【异常提醒】找出1-3个异常点并解释可能原因
4. 【下周建议】给出3条具体可执行的建议（要具体到数字）
5. 【一句话鼓励】"""
    return prompt


def _call_llm(prompt, api_key, provider):
    if provider == "OpenAI":
        url = "https://api.openai.com/v1/chat/completions"
        model = "gpt-4o-mini"
    else:
        url = "https://api.deepseek.com/chat/completions"
        model = "deepseek-chat"

    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.7},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def estimate_calories(description, api_key=None, provider="DeepSeek"):
    """AI 估算饮食热量（用于食物库没有的、或想文字描述的）。"""
    if not description or not description.strip():
        return None, "请输入你吃了什么的描述。"
    if not api_key or not api_key.strip():
        return None, "未配置 API Key，请从食物库选择或手动输入热量。"

    prompt = f"""你是专业营养师，擅长估算中国常见食物的热量。

请估算以下饮食描述的总热量：
"{description.strip()}"

请严格按以下格式输出（第一行必须是总热量，方便程序提取）：
总热量：XXX kcal
然后换行，用2-4行简要列出每项食物的估算。"""
    try:
        text = _call_llm(prompt, api_key.strip(), provider)
        m = re.search(r"总热量[:：]\s*(\d+)\s*kcal", text, re.IGNORECASE)
        est = int(m.group(1)) if m else None
        return est, text
    except Exception as e:  # noqa: BLE001
        return None, f"⚠️ AI 调用失败：{e}\n\n请从食物库选择或手动输入热量。"


def _extract_json(text):
    """从 LLM 返回中稳健提取 JSON 数组。"""
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]
    return json.loads(text)


def parse_food(text, api_key=None, provider="DeepSeek"):
    """AI 解析饮食描述，拆分每项食物并估算热量。

    返回 (items列表, 总热量, 错误信息或None)。
    """
    if not text or not text.strip():
        return None, 0, "请输入你吃了什么。"
    if not api_key or not api_key.strip():
        return None, 0, "未配置 API Key，请在左侧侧边栏填入。"

    prompt = f"""你是营养师。请分析用户描述的饮食，拆分出每项食物并估算热量。

用户描述：{text.strip()}

请只输出一个 JSON 数组，每个元素格式：
{{"name":"食物名","amount":数量,"unit":"单位","calories":热量kcal整数}}

要求：
1. 拆分出每一项食物（如鸡蛋、米饭、奶茶等），数量要具体
2. calories 是该项食物的总热量，不是每100g
3. 除 JSON 外不要输出任何其他文字"""
    try:
        raw = _call_llm(prompt, api_key.strip(), provider)
        items = _extract_json(raw)
        cleaned = []
        total = 0
        for it in items:
            name = str(it.get("name", "食物")).strip() or "食物"
            amount = float(it.get("amount") or 1)
            unit = str(it.get("unit") or "份").strip() or "份"
            kcal = int(float(it.get("calories") or 0))
            total += kcal
            cleaned.append({"name": name, "amount": amount, "unit": unit, "calories": kcal})
        return cleaned, total, None
    except Exception as e:  # noqa: BLE001
        return None, 0, f"AI 解析失败：{e}"


def daily_advice(food_items, intake, exercise_kcal, settings, api_key=None, provider="DeepSeek"):
    """基于今日饮食，给出运动建议 + 饮食调整建议。"""
    target = settings.get("daily_intake_target", "1800")
    target_w = settings.get("target_weight", "")
    if food_items:
        food_desc = "、".join(f"{f.get('name','')}{f.get('amount','')}{f.get('unit','')}" for f in food_items)
    else:
        food_desc = "（未记录）"

    if api_key and api_key.strip():
        prompt = f"""你是专业减肥教练。根据今天的数据，给出简洁、可执行的建议。

- 今天摄入：{intake:.0f} kcal（目标 {target} kcal）
- 今天运动消耗：{exercise_kcal:.0f} kcal
- 今天吃的食物：{food_desc}
- 体重目标：{target_w}kg

请分两部分输出：
【运动建议】根据今天热量盈余/赤字情况，今天或明天该怎么运动（具体到分钟和项目）
【饮食调整】今天吃的缺什么该增加（蛋白质/蔬菜/膳食纤维等）、什么该减少

要求：简洁，共3-5条，语气鼓励。"""
        try:
            return _call_llm(prompt, api_key.strip(), provider)
        except Exception:  # noqa: BLE001
            pass  # 回退到规则版
    return rule_daily_advice(intake, exercise_kcal, settings, food_items)


def rule_daily_advice(intake, exercise_kcal, settings, food_items):
    """规则版每日建议（无 API Key 时的回退）。"""
    target = float(settings.get("daily_intake_target") or 1800)
    lines = ["### 运动建议"]
    over = intake - target
    if over > 0:
        min_run = max(5, round(over / 10))
        lines.append(f"- 今天已超出目标 {over:.0f} kcal，建议再运动约 **{min_run} 分钟**（跑步/跳绳）。")
    else:
        lines.append(f"- 今天摄入还有 {target - intake:.0f} kcal 余额，可安排 20-30 分钟快走巩固。")

    lines.append("")
    lines.append("### 饮食调整")
    names = " ".join(str(f.get("name", "")) for f in (food_items or []))
    has_protein = any(k in names for k in ["蛋", "鸡", "牛", "鱼", "虾", "肉", "豆腐", "奶", "豆"])
    has_veg = any(k in names for k in ["菜", "蔬菜", "青菜", "白菜", "西兰花", "番茄", "黄瓜", "生菜"])
    if not has_protein:
        lines.append("- 今天蛋白质可能不足，建议加 1-2 个鸡蛋或一掌鸡胸肉/鱼肉。")
    if not has_veg:
        lines.append("- 蔬菜摄入偏少，建议加一份绿叶蔬菜（热量低又饱腹）。")
    if over > 300:
        lines.append("- 明天减少主食半拳，或用无糖茶代替奶茶/饮料。")
    lines.append("- 每天喝水 2L 以上，有助代谢。")
    return "\n".join(lines)


# ---------- 规则回退报告 ----------

def rule_based_report(df, settings=None):
    """基于热量缺口生成周报。df 为每日汇总（含 intake / exercise_kcal）。"""
    settings = settings or {}
    if df.empty:
        return "暂无数据，请先录入数据。"

    df = df.sort_values("date").copy()
    w = df["weight"].dropna()
    intake = df["intake"].dropna()
    exercise = df["exercise_kcal"].dropna()
    sleep = df["sleep_hours"].dropna()
    mood = df["mood"].dropna()
    n = len(df)

    target = 0.0
    try:
        target = float(settings.get("daily_intake_target") or 0)
    except (TypeError, ValueError):
        target = 0.0

    lines = []
    lines.append("### 1. 本周总结")
    if len(w) >= 2:
        change = w.iloc[-1] - w.iloc[0]
        arrow = "减" if change < 0 else "增"
        lines.append(f"- 体重从 {w.iloc[0]:.1f}kg → {w.iloc[-1]:.1f}kg，累计{arrow} {abs(change):.1f}kg（记录 {n} 天）。")
    else:
        lines.append(f"- 已记录 {n} 天，体重数据不足，建议坚持每天空腹称重。")
    if len(intake):
        lines.append(f"- 平均摄入 {intake.mean():.0f} kcal/天" + (f"（目标 {target:.0f} kcal）" if target > 0 else "") + "。")
    if len(exercise):
        lines.append(f"- 平均运动消耗 {exercise.mean():.0f} kcal/天。")
    if len(sleep):
        lines.append(f"- 平均睡眠 {sleep.mean():.1f} 小时/天。")

    lines.append("")
    lines.append("### 2. 热量缺口分析")
    if target > 0 and len(intake):
        avg_intake = intake.mean()
        if avg_intake <= target:
            lines.append(f"- 平均摄入 {avg_intake:.0f} kcal ≤ 目标 {target:.0f} kcal，摄入控制良好 ✅")
        elif avg_intake <= target + 300:
            lines.append(f"- 平均摄入 {avg_intake:.0f} kcal，超出目标约 {avg_intake - target:.0f} kcal，轻微超标 ⚠️")
        else:
            lines.append(f"- 平均摄入 {avg_intake:.0f} kcal，超出目标约 {avg_intake - target:.0f} kcal，缺口不足 ❌")
    if len(exercise) and exercise.mean() < 100:
        lines.append("- 运动消耗偏低（<100 kcal/天），建议每天至少快走 20 分钟。")
    elif len(exercise):
        lines.append("- 运动消耗不错，继续保持。")

    lines.append("")
    lines.append("### 3. 异常提醒")
    anomalies = detect_anomalies(df)
    if anomalies:
        for a in anomalies:
            lines.append(f"- {a['date'].strftime('%m-%d')} 体重 {a['weight']:.1f}kg，偏离7日均线 {a['diff']:.1f}kg。")
    else:
        lines.append("- 本周未发现明显异常波动。")

    lines.append("")
    lines.append("### 4. 下周建议")
    if target > 0 and len(intake):
        avg_intake = intake.mean()
        if avg_intake > target:
            lines.append(f"- 下周把每日摄入降到 {max(1200, target):.0f} kcal 以内（当前平均 {avg_intake:.0f} kcal）。")
        else:
            lines.append(f"- 继续把每日摄入控制在 {target:.0f} kcal 以内。")
    else:
        lines.append("- 先在「目标计划」生成计划，明确每日摄入目标。")
    if len(exercise) and exercise.mean() < 100:
        lines.append("- 每周至少 3 次、每次 20 分钟以上运动，优先快走/慢跑。")
    if len(sleep) and sleep.mean() < 7:
        lines.append("- 睡眠不足 7 小时，优先补觉，睡眠差会直接拖慢减脂。")
    lines.append("- 坚持每天同一时间空腹称重，减少数据噪声。")

    lines.append("")
    lines.append("### 5. 一句话鼓励")
    lines.append("> 数据不会说谎，坚持下去，趋势会替你说话。💪")
    return "\n".join(lines)


# ---------- 统一入口 ----------

def generate_report(df, api_key=None, provider="DeepSeek", settings=None):
    """生成周报。有 Key 走 LLM，无 Key 走规则回退。"""
    if api_key and api_key.strip():
        try:
            return _call_llm(_build_prompt(df), api_key.strip(), provider)
        except Exception as e:  # noqa: BLE001
            return (f"⚠️ AI 调用失败，已回退到本地统计报告。\n\n错误信息：{e}\n\n---\n\n"
                    + rule_based_report(df, settings))
    return rule_based_report(df, settings)
