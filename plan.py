# -*- coding: utf-8 -*-
"""目标计划 + 每日能量评估 + 目标进度跟踪。"""
import pandas as pd

ACTIVITY_LEVELS = {
    "久坐（几乎不运动）": 1.2,
    "轻度活动（每周1-3次运动）": 1.375,
    "中度活动（每周3-5次运动）": 1.55,
    "高强度（每周6-7次运动）": 1.725,
}

KCAL_PER_KG_FAT = 7700  # 减 1kg 脂肪约需 7700 kcal 热量缺口


def _bmr(weight, height, age, gender):
    """Mifflin-St Jeor 基础代谢公式。"""
    if gender == "男":
        return 10 * weight + 6.25 * height - 5 * age + 5
    return 10 * weight + 6.25 * height - 5 * age - 161


def _clean(v):
    """把 NaN / None 统一成 None。"""
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


# ---------- 目标计划 ----------

def weight_loss_plan(start_weight, target_weight, days=45, gender="男",
                     height=170, age=30, activity="久坐（几乎不运动）"):
    """返回 dict，包含计算数值 + 建议文本。"""
    r = {}
    r["start"] = start_weight
    r["target"] = target_weight
    r["days"] = days
    r["total_to_lose"] = round(start_weight - target_weight, 1)

    bmr = _bmr(start_weight, height, age, gender)
    tdee = bmr * ACTIVITY_LEVELS.get(activity, 1.2)
    r["bmr"] = round(bmr)
    r["tdee"] = round(tdee)
    r["floor"] = 1200 if gender == "女" else 1500

    bmi_target = target_weight / ((height / 100) ** 2)
    r["bmi_target"] = round(bmi_target, 1)
    r["too_thin"] = bmi_target < 18.5

    to_lose = r["total_to_lose"]

    if to_lose <= 0:
        r["mode"] = "maintain"
        r["is_unrealistic"] = False
        r["aggressive"] = False
        r["below_floor"] = False
        r["warning"] = None
        r["daily_intake"] = round(tdee)
        r["weekly_loss"] = 0.0
        r["protein_g"] = round(start_weight * 1.6)
        return r

    r["mode"] = "loss"
    deficit_needed = to_lose * KCAL_PER_KG_FAT / days
    weekly_loss = to_lose / days * 7
    r["deficit_needed"] = round(deficit_needed)
    r["weekly_loss"] = round(weekly_loss, 2)

    r["is_unrealistic"] = False
    r["aggressive"] = False
    r["below_floor"] = False

    if weekly_loss > 1.5:
        r["is_unrealistic"] = True
        max_safe_loss = 1000 * days / KCAL_PER_KG_FAT
        r["realistic_loss"] = round(max_safe_loss, 1)
        r["suggested_days"] = round(to_lose * KCAL_PER_KG_FAT / 1000)
        r["warning"] = (
            f"⚠️ 目标过于激进：{days} 天要减 {to_lose}kg（每周 {weekly_loss:.2f}kg），"
            f"远超健康上限（每周≤1kg）。会大量流失肌肉、代谢下降、极易反弹。"
        )
        r["daily_intake"] = r["floor"]
        r["protein_g"] = round(start_weight * 1.8)
        return r

    daily_intake = tdee - deficit_needed

    if weekly_loss > 1.0:
        r["aggressive"] = True
        r["warning"] = (
            f"⚠️ 目标偏激进：每周减 {weekly_loss:.2f}kg，接近健康上限。"
            f"务必保证蛋白质和睡眠，否则肌肉流失、容易反弹。"
        )
    else:
        r["warning"] = None

    if daily_intake < r["floor"]:
        r["below_floor"] = True
        daily_intake = r["floor"]

    r["daily_intake"] = round(daily_intake)
    r["protein_g"] = round(start_weight * 1.8)
    return r


def exercise_plan_text():
    return """### 🏃 运动建议（专治"没时间"）

**核心原则：宁短勿断，碎片化 > 一次性。**

1. **有氧（每周累计 150 分钟，随便拆）**
   - 每天快走/慢跑 20-25 分钟
   - 或 15 分钟高强度间歇训练（效果 ≈ 30 分钟慢跑）
   - 或 10 分钟跳绳（约烧 100 kcal）

2. **力量训练（每周 2-3 次，每次 20-30 分钟）**
   - 居家徒手：深蹲、俯卧撑、平板支撑、臀桥

3. **碎片化方案（上班族专属）**
   - 通勤提前一站下车快走、爬楼梯代替电梯
   - 午休散步 15 分钟、每小时起身活动 2 分钟

4. **别小看 NEAT（日常活动消耗）**
   - 多站、多走、多动，一天能多烧 200-300 kcal
"""


def food_plan_text(daily_intake, protein_g):
    protein_kcal = protein_g * 4
    fat_kcal = round(daily_intake * 0.25)
    fat_g = round(fat_kcal / 9)
    carb_kcal = max(0, daily_intake - protein_kcal - fat_kcal)
    carb_g = round(carb_kcal / 4)

    lines = []
    lines.append(f"### 🍚 每日食物摄入建议（约 {daily_intake} kcal）")
    lines.append("")
    lines.append("**三大营养素分配：**")
    lines.append(f"- 蛋白质：约 **{protein_g}g**（{protein_kcal} kcal）—— 保肌肉关键")
    lines.append(f"- 碳水：约 **{carb_g}g**（{carb_kcal} kcal）")
    lines.append(f"- 脂肪：约 **{fat_g}g**（{fat_kcal} kcal）")
    lines.append("")
    lines.append("**用速查表翻译成食物（一天总量）：**")
    lines.append(f"- 主食：约 **{max(1, round(carb_g / 40))} 拳** 米饭/杂粮")
    lines.append(f"- 蛋白质：约 **{max(1, round(protein_g / 25))} 掌** 瘦肉/鱼/蛋")
    lines.append("- 蔬菜：**不限量**（绿叶菜吃到饱）")
    lines.append(f"- 脂肪：约 **{max(1, round(fat_g / 5))} 勺油** + 一小把坚果")
    lines.append("- 🚫 戒掉：奶茶/含糖饮料（一杯 ≈ 400 kcal）")
    lines.append("")
    lines.append(f"**记住这一个数字：{daily_intake} kcal。** 每天摄入尽量不超过它。")
    return "\n".join(lines)


# ---------- 每日能量评估 ----------

def daily_evaluation(row, settings):
    """评估某一天：摄入 vs 总消耗（TDEE + 运动）。row 为 dict（含 intake / exercise_kcal）。"""
    gender = settings.get("gender", "男")
    height = float(_clean(settings.get("height")) or 170)
    age = float(_clean(settings.get("age")) or 30)
    activity = settings.get("activity", "久坐（几乎不运动）")

    weight = _clean(row.get("weight"))
    if not weight:
        weight = float(_clean(settings.get("start_weight")) or 70)

    bmr = _bmr(weight, height, age, gender)
    tdee = bmr * ACTIVITY_LEVELS.get(activity, 1.2)
    exercise_kcal = _clean(row.get("exercise_kcal")) or 0
    intake = _clean(row.get("intake")) or 0
    total_burn = tdee + exercise_kcal
    net = intake - total_burn

    if not intake:
        verdict = "未记录饮食，无法评估"
    elif net <= -500:
        verdict = "热量赤字充足，减脂节奏良好"
    elif net <= -200:
        verdict = "热量赤字正常，稳步减脂"
    elif net < 200:
        verdict = "接近热量平衡，减脂偏慢"
    else:
        verdict = "热量盈余，可能增重"

    return {
        "weight": round(weight, 1),
        "bmr": round(bmr),
        "tdee": round(tdee),
        "exercise_kcal": round(exercise_kcal),
        "total_burn": round(total_burn),
        "intake": round(intake),
        "net": round(net),
        "verdict": verdict,
    }


def evaluate_all_days(summary_df, settings):
    """对每日汇总做逐日评估，返回含 date / net 列的 DataFrame。"""
    rows = []
    for _, r in summary_df.iterrows():
        d = r.to_dict()
        ev = daily_evaluation(d, settings)
        ev["date"] = r["date"]
        rows.append(ev)
    return pd.DataFrame(rows)


def today_remaining(row, settings):
    """基于目标，给出今天还应该做什么。row 为当日汇总（dict）。"""
    target = float(_clean(settings.get("daily_intake_target")) or 0)
    intake = _clean(row.get("intake")) or 0
    exercise = _clean(row.get("exercise_kcal")) or 0

    result = {
        "target": round(target),
        "intake": round(intake),
        "exercise_kcal": round(exercise),
        "remaining_eat": None,
        "advice": "",
    }

    if target <= 0:
        result["advice"] = "先在「🎯 目标计划」生成一次计划，才能计算今天的摄入目标。"
        return result

    remaining_eat = target - intake
    result["remaining_eat"] = round(remaining_eat)
    if remaining_eat >= 0:
        foods, leftover = suggest_foods(remaining_eat)
        result["advice"] = f"今天还可以再吃约 **{remaining_eat:.0f} kcal**（目标 {target:.0f} kcal）。"
        if foods:
            result["advice"] += "\n\n推荐这样吃：\n" + "\n".join(f"- {f}" for f in foods)
            if leftover > 0:
                result["advice"] += f"\n- （合计约 {round(remaining_eat - leftover)} kcal，剩 {leftover} kcal 可忽略）"
    else:
        over = -remaining_eat
        min_run = max(5, round(over / 10))
        result["advice"] = (f"已超出目标 **{over:.0f} kcal**，"
                            f"建议再运动约 **{min_run} 分钟**（跑步/跳绳）来抵消。")
    return result


def suggest_foods(kcal):
    """根据剩余热量，建议具体食物和量（规则版，蛋白质优先）。"""
    pool = [
        ("鸡胸肉 1掌(约130g)", 170, "protein"),
        ("鸡蛋 1个", 70, "protein"),
        ("豆腐 100g", 80, "protein"),
        ("牛奶/酸奶 1杯", 150, "protein"),
        ("绿叶蔬菜 1份(200g)", 40, "veg"),
        ("杂粮饭 1拳(约150g)", 175, "carb"),
        ("苹果 1个", 90, "fruit"),
        ("香蕉 1根", 105, "fruit"),
    ]
    picked = []
    remaining = kcal
    # 顺序：蛋白质 → 蔬菜 → 主食 → 水果，尽量凑满
    for tag in ["protein", "veg", "carb", "fruit"]:
        for name, c, t in pool:
            if t == tag and remaining >= c:
                picked.append(f"{name}（约{c} kcal）")
                remaining -= c
                if remaining < 40:
                    return picked, round(remaining)
    return picked, round(remaining)


def goal_tracking(summary_df, settings):
    """目标进度：按当前趋势，预计能否在截止日前达标。"""
    start = float(_clean(settings.get("start_weight")) or 0)
    target = float(_clean(settings.get("target_weight")) or 0)
    days = int(float(_clean(settings.get("days")) or 45))

    w = summary_df["weight"].dropna()
    if start <= 0 or target <= 0 or len(w) < 2:
        return None

    current = float(w.iloc[-1])
    total_to_lose = start - target
    lost_so_far = start - current
    elapsed = len(w) - 1

    if total_to_lose <= 0:
        return None

    if elapsed > 0:
        daily_rate = (current - start) / elapsed
        # 限制在合理范围（每周最多减1.4kg≈每天0.2kg），避免数据少时外推失真
        daily_rate = max(-0.2, min(0.2, daily_rate))
        remaining = max(0, days - elapsed)
        projected = current + daily_rate * remaining
    else:
        projected = current

    return {
        "start": round(start, 1),
        "target": round(target, 1),
        "current": round(current, 1),
        "lost_so_far": round(lost_so_far, 1),
        "total_to_lose": round(total_to_lose, 1),
        "elapsed": elapsed,
        "days": days,
        "projected": round(projected, 1),
        "on_track": projected <= target,
    }
