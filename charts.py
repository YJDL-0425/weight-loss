# -*- coding: utf-8 -*-
"""图表层：Plotly 可视化 + 异常检测。"""
import pandas as pd
import plotly.graph_objects as go

BLUE = "#2B5BD7"
GREEN = "#0B6E4F"
RED = "#C0392B"


def weight_chart(df):
    """体重趋势图 + 7日移动平均线。"""
    d = df.dropna(subset=["weight"]).sort_values("date").copy()
    if d.empty:
        return None
    d["ma7"] = d["weight"].rolling(7, min_periods=1).mean()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=d["date"], y=d["weight"], mode="lines+markers",
        name="每日体重", line=dict(color=BLUE, width=2),
    ))
    fig.add_trace(go.Scatter(
        x=d["date"], y=d["ma7"], mode="lines",
        name="7日均线", line=dict(color=GREEN, width=2, dash="dash"),
    ))
    fig.update_layout(
        title="体重趋势（7日均线过滤波动）",
        template="plotly_white", height=380,
        yaxis_title="体重 (kg)", xaxis_title="日期",
        legend=dict(orientation="h", y=1.1),
    )
    return fig


def calories_chart(df):
    d = df.dropna(subset=["calories"]).sort_values("date")
    if d.empty:
        return None
    fig = go.Figure(go.Bar(
        x=d["date"], y=d["calories"], name="摄入热量",
        marker_color=BLUE,
    ))
    fig.update_layout(
        title="每日摄入热量", template="plotly_white", height=300,
        yaxis_title="热量 (kcal)", xaxis_title="日期",
    )
    return fig


def sleep_chart(df):
    d = df.dropna(subset=["sleep_hours"]).sort_values("date")
    if d.empty:
        return None
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=d["date"], y=d["sleep_hours"], name="睡眠时长",
        marker_color=GREEN,
    ))
    fig.add_hline(y=7, line_dash="dash", line_color=RED,
                  annotation_text="目标7小时", annotation_position="top left")
    fig.update_layout(
        title="每日睡眠", template="plotly_white", height=300,
        yaxis_title="睡眠 (小时)", xaxis_title="日期",
    )
    return fig


def mood_chart(df):
    d = df.dropna(subset=["mood"]).sort_values("date")
    if d.empty:
        return None
    fig = go.Figure(go.Scatter(
        x=d["date"], y=d["mood"], mode="lines+markers",
        name="心情", line=dict(color=GREEN, width=2),
    ))
    fig.update_yaxes(range=[0.5, 5.5], dtick=1)
    fig.update_layout(
        title="心情趋势（1-5）", template="plotly_white", height=300,
        yaxis_title="心情", xaxis_title="日期",
    )
    return fig


def detect_anomalies(df, threshold=0.5):
    """体重偏离7日均线超过 threshold kg 记为异常点。"""
    d = df.dropna(subset=["weight"]).sort_values("date").copy()
    if len(d) < 3:
        return []
    d["ma7"] = d["weight"].rolling(7, min_periods=1).mean()
    d["diff"] = (d["weight"] - d["ma7"]).abs()
    anomalies = d[d["diff"] > threshold]
    return anomalies[["date", "weight", "ma7", "diff"]].to_dict("records")


def energy_balance_chart(eval_df):
    """每日摄入 vs 总消耗 对比图。"""
    if eval_df is None or eval_df.empty:
        return None
    fig = go.Figure()
    fig.add_trace(go.Bar(x=eval_df["date"], y=eval_df["intake"],
                         name="摄入", marker_color=BLUE))
    fig.add_trace(go.Bar(x=eval_df["date"], y=eval_df["total_burn"],
                         name="总消耗", marker_color=GREEN))
    fig.update_layout(
        title="每日摄入 vs 总消耗（总消耗 = 基础代谢 + 运动）",
        template="plotly_white", height=320, barmode="group",
        yaxis_title="kcal", xaxis_title="日期",
        legend=dict(orientation="h", y=1.15),
    )
    return fig


def balance_curve(eval_df):
    """平衡曲线：每日净热量（负=赤字减脂，正=盈余增重）。"""
    if eval_df is None or eval_df.empty:
        return None
    colors = [GREEN if v <= 0 else RED for v in eval_df["net"]]
    fig = go.Figure(go.Bar(
        x=eval_df["date"], y=eval_df["net"],
        marker_color=colors, name="净热量",
    ))
    fig.add_hline(y=0, line_color="#333333", line_width=1)
    fig.update_layout(
        title="每日净热量平衡曲线（绿=减脂赤字，红=增重盈余）",
        template="plotly_white", height=340,
        yaxis_title="净热量 (kcal)", xaxis_title="日期",
        showlegend=False,
    )
    return fig
