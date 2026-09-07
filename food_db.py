# -*- coding: utf-8 -*-
"""食物 & 运动热量数据库（常见中餐/运动，粗略估算用）。"""

# 食物：每单位的估算热量（kcal）
FOODS = {
    # 主食
    "米饭": {"unit": "碗(约150g)", "kcal": 175},
    "杂粮饭": {"unit": "碗(约150g)", "kcal": 180},
    "面条": {"unit": "碗", "kcal": 300},
    "馒头": {"unit": "个", "kcal": 220},
    "包子": {"unit": "个", "kcal": 250},
    "饺子": {"unit": "个", "kcal": 40},
    "全麦面包": {"unit": "片", "kcal": 80},
    "燕麦": {"unit": "碗(40g)", "kcal": 150},
    # 蛋白质
    "鸡蛋": {"unit": "个", "kcal": 70},
    "鸡胸肉": {"unit": "100g", "kcal": 133},
    "鸡腿": {"unit": "个", "kcal": 200},
    "瘦猪肉": {"unit": "100g", "kcal": 140},
    "五花肉": {"unit": "100g", "kcal": 395},
    "牛肉": {"unit": "100g", "kcal": 250},
    "鱼肉": {"unit": "100g", "kcal": 110},
    "虾": {"unit": "100g", "kcal": 90},
    "豆腐": {"unit": "100g", "kcal": 80},
    "牛奶": {"unit": "杯(250ml)", "kcal": 150},
    "酸奶": {"unit": "杯(200g)", "kcal": 150},
    # 蔬菜水果
    "绿叶蔬菜": {"unit": "份(200g)", "kcal": 40},
    "苹果": {"unit": "个", "kcal": 90},
    "香蕉": {"unit": "根", "kcal": 105},
    "橙子": {"unit": "个", "kcal": 60},
    # 零食饮料
    "奶茶": {"unit": "杯", "kcal": 400},
    "可乐": {"unit": "罐(330ml)", "kcal": 140},
    "坚果": {"unit": "把(30g)", "kcal": 160},
    "薯片": {"unit": "包(70g)", "kcal": 380},
    "啤酒": {"unit": "瓶(500ml)", "kcal": 200},
    # 油脂
    "食用油": {"unit": "勺(10g)", "kcal": 90},
}

# 运动：MET 值（代谢当量）
EXERCISES = {
    "散步": 3.0,
    "快走": 4.3,
    "慢跑": 7.0,
    "跑步": 9.8,
    "跳绳": 11.0,
    "骑行": 6.8,
    "游泳": 8.0,
    "力量训练": 5.0,
    "瑜伽": 2.5,
    "爬山": 7.5,
    "球类运动": 7.0,
    "舞蹈": 6.0,
    "爬楼梯": 8.0,
    "高强度间歇训练": 10.0,
}


def food_calories(name, amount):
    """按食物 + 数量估算热量。返回 kcal，未收录则返回 None。"""
    if name not in FOODS:
        return None
    return round(FOODS[name]["kcal"] * amount)


def food_unit(name):
    """返回该食物的计量单位提示。"""
    return FOODS.get(name, {}).get("unit", "")


def exercise_calories(name, minutes, weight):
    """按运动 + 时长 + 体重估算消耗。kcal = MET × 3.5 × 体重kg / 200 × 分钟。"""
    if name not in EXERCISES or not weight or minutes <= 0:
        return 0
    met = EXERCISES[name]
    return round(met * 3.5 * weight / 200 * minutes)
