# -*- coding: utf-8 -*-
"""减肥数据看板 MVP —— 你的减肥私人数据分析师。

运行：streamlit run app.py
"""
import os

import streamlit as st
import pandas as pd

import db
import charts
import ai_report
import plan
import food_db
import license as license_mod
import photo

st.set_page_config(page_title="减肥数据看板", page_icon="🏃", layout="wide")


def _load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
    # 云端：从 Streamlit secrets 读取
    try:
        for k in ["SUPABASE_URL", "SUPABASE_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY"]:
            if k in st.secrets and k not in os.environ:
                os.environ[k] = str(st.secrets[k])
    except Exception:
        pass


_load_env()
db.init_db()

# ---------- 侧边栏 ----------
with st.sidebar:
    st.title("🏃 减肥数据看板")
    st.caption("你的减肥私人数据分析师")

    st.divider()

    st.subheader("🤖 AI 周报引擎")
    provider = st.selectbox("引擎", ["DeepSeek", "OpenAI"], index=0)
    default_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
    api_key = st.text_input(
        "API Key",
        type="password",
        value=default_key,
        help="已从 .env 自动加载，可修改。",
    )

    st.divider()

    st.subheader("🔒 付费墙（演示）")
    paywall_on = st.toggle("启用付费墙", value=False)
    if paywall_on:
        license_key = st.text_input("License Key", type="password")
        if st.button("验证 License"):
            ok, msg = license_mod.verify_license(license_key)
            if ok:
                st.session_state["unlocked"] = True
                st.success(msg)
            else:
                st.session_state["unlocked"] = False
                st.error(msg)
        unlocked = st.session_state.get("unlocked", False)
    else:
        unlocked = True

    st.divider()
    st.subheader("🔧 连接诊断")
    if st.button("测试 Supabase 连接"):
        try:
            import requests as _rq
            _url = os.environ.get("SUPABASE_URL", "").rstrip("/")
            _key = os.environ.get("SUPABASE_KEY", "")
            _resp = _rq.get(
                f"{_url}/rest/v1/daily_logs?select=*&limit=1",
                headers={"apikey": _key, "Authorization": f"Bearer {_key}"},
                timeout=15,
            )
            st.code(f"URL: {_url}\nKey前缀: {_key[:15]}...\n\nHTTP {_resp.status_code}\n{_resp.text[:600]}")
        except Exception as _e:  # noqa: BLE001
            st.code(f"连接失败：{_e}")
    st.caption("数据现保存在 Supabase 云端。")


def latest_weight():
    logs = db.get_logs()
    w = logs["weight"].dropna()
    if len(w):
        return float(w.iloc[-1])
    try:
        return float(db.get_setting("start_weight") or 70)
    except (TypeError, ValueError):
        return 70.0


# ---------- 主界面 ----------
st.title("减肥数据看板")
st.caption("逐条记录食物和运动 → 系统自动算热量 → 看平衡曲线和缺口")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📝 记录", "🎯 目标计划", "📊 数据看板", "🤖 AI 周报", "📸 变化回放"])

# ===== Tab 1：记录 =====
with tab1:
    # 快捷日期选择（支持回填过去任意一天）
    if "date_key" not in st.session_state:
        st.session_state["date_key"] = pd.Timestamp.today().date()

    _today = pd.Timestamp.today().date()
    qc = st.columns([1, 1, 1, 3])
    if qc[0].button("📅 今天", use_container_width=True):
        st.session_state["date_key"] = _today
        st.rerun()
    if qc[1].button("📅 昨天", use_container_width=True):
        st.session_state["date_key"] = _today - pd.Timedelta(days=1)
        st.rerun()
    if qc[2].button("📅 前天", use_container_width=True):
        st.session_state["date_key"] = _today - pd.Timedelta(days=2)
        st.rerun()

    day = st.date_input("📅 选择日期（可回填过去任意一天）", key="date_key")
    day_str = str(day)

    if st.session_state.get("flash"):
        st.success(st.session_state["flash"])
        st.session_state["flash"] = ""

    settings = db.get_all_settings()

    # 今日进度
    foods_today = db.get_food_entries(day_str)
    exercises_today = db.get_exercise_entries(day_str)
    intake_today = foods_today["calories"].sum() if not foods_today.empty else 0
    ex_today = exercises_today["calories"].sum() if not exercises_today.empty else 0

    if settings and settings.get("daily_intake_target"):
        tr = plan.today_remaining({"intake": intake_today, "exercise_kcal": ex_today}, settings)
        with st.container(border=True):
            st.subheader("⚡ 今日进度")
            c1, c2, c3 = st.columns(3)
            c1.metric("已摄入", f"{tr['intake']:.0f} kcal")
            c2.metric("目标摄入", f"{tr['target']:.0f} kcal")
            c3.metric("已运动消耗", f"{tr['exercise_kcal']:.0f} kcal")
            st.markdown(tr["advice"])
    else:
        st.info("💡 先去「🎯 目标计划」生成一次计划，这里会显示今日摄入进度。")

    st.divider()

    # ---- 基础数据 ----
    st.subheader("📋 基础数据（每天一条）")
    # 回填当天已保存的数据
    _w, _s, _m, _n = 0.0, 0.0, 3, ""
    _logs = db.get_logs()
    if not _logs.empty:
        _row = _logs[_logs["date"].dt.strftime("%Y-%m-%d") == day_str]
        if not _row.empty:
            r = _row.iloc[0]
            _w = float(r["weight"]) if pd.notna(r["weight"]) else 0.0
            _s = float(r["sleep_hours"]) if pd.notna(r["sleep_hours"]) else 0.0
            _m = int(r["mood"]) if pd.notna(r["mood"]) else 3
            _n = r["note"] if pd.notna(r["note"]) else ""
    with st.form("base_form", clear_on_submit=False):
        c1, c2, c3 = st.columns(3)
        weight = c1.number_input("体重 (kg)", min_value=0.0, max_value=500.0, step=0.1,
                                 value=_w, help="填 0 表示未记录")
        sleep_hours = c2.number_input("睡眠 (小时)", min_value=0.0, max_value=24.0, step=0.5,
                                      value=_s, help="填 0 表示未记录")
        mood = c3.slider("心情 (1-5)", min_value=1, max_value=5, value=_m)
        note = st.text_input("备注（可选）", value=_n)
        submitted = st.form_submit_button("💾 保存基础数据", use_container_width=True)
    if submitted:
        db.add_log(day_str, weight if weight > 0 else None,
                   sleep_hours if sleep_hours > 0 else None, mood, note)
        st.session_state["flash"] = f"已保存 {day_str} 的基础数据"
        st.rerun()

    st.divider()

    # ---- 照片 ----
    st.subheader("📸 当日照片（记录身材变化）")
    ptab_a, ptab_b = st.tabs(["📷 拍照/上传", "👀 查看当天照片"])
    with ptab_a:
        cam = st.camera_input("拍照（手机浏览器可用）")
        uploaded = st.file_uploader("或上传照片", type=["jpg", "jpeg", "png"], key=f"upload_{day_str}")
        img = cam if cam is not None else uploaded
        if img is not None:
            st.image(img, width=200)
            if st.button("💾 保存照片", key=f"save_photo_{day_str}"):
                try:
                    photo.save_photo(day_str, img.getvalue())
                    st.session_state["flash"] = f"已保存 {day_str} 的照片"
                    st.rerun()
                except Exception as e:  # noqa: BLE001
                    st.error(f"照片上传失败：{e}")
    with ptab_b:
        existing = photo.get_photo(day_str)
        if existing:
            st.image(existing, caption=f"{day_str} 的照片", use_container_width=True)
        else:
            st.info("当天还没有照片")

    st.divider()

    # ---- 食物 ----
    st.subheader("🍚 食物（AI 识别，自由描述）")
    if not api_key:
        st.info("未配置 API Key：可用下方「手动添加」，或在左侧侧边栏填 Key 后用 AI 自动识别。")
    food_text = st.text_area(
        "今天吃了什么（自由描述，AI 自动拆分+算热量）",
        placeholder="例如：早餐两个鸡蛋一杯牛奶，午餐一份红烧肉盖浇饭，下午一杯奶茶",
        key="food_text",
    )
    if st.button("🤖 AI 识别并添加", use_container_width=True):
        if not food_text.strip():
            st.warning("请先描述你吃了什么")
        else:
            with st.spinner("AI 识别中..."):
                items, total, err = ai_report.parse_food(food_text, api_key, provider)
            if err:
                st.error(err)
            else:
                for it in items:
                    db.add_food_entry(day_str, it["name"], it["amount"], it["unit"], it["calories"])
                st.session_state["flash"] = f"已识别 {len(items)} 项，合计 {total} kcal"
                st.rerun()

    with st.expander("✍️ 手动添加（AI 失败时备用）"):
        m1, m2, m3 = st.columns(3)
        m_name = m1.text_input("食物名", key="m_name")
        m_kcal = m2.number_input("热量 (kcal)", min_value=0, max_value=5000, value=0, step=50, key="m_kcal")
        m_amt = m3.number_input("数量", min_value=1, max_value=20, value=1, key="m_amt")
        if st.button("手动添加"):
            if m_name.strip() and m_kcal > 0:
                db.add_food_entry(day_str, m_name.strip(), m_amt, "份", m_kcal)
                st.session_state["flash"] = f"已添加 {m_name.strip()} ≈ {m_kcal} kcal"
                st.rerun()
            else:
                st.warning("请填写食物名和热量")

    if not foods_today.empty:
        st.caption(f"当天已记录 {len(foods_today)} 条，合计 {intake_today:.0f} kcal：")
        for _, r in foods_today.iterrows():
            col1, col2 = st.columns([5, 1])
            col1.write(f"· {r['name']} × {r['amount']}{r['unit']} = **{r['calories']:.0f} kcal**")
            if col2.button("删除", key=f"del_food_{r['id']}"):
                db.delete_food_entry(r["id"])
                st.rerun()

    st.divider()

    # ---- 运动 ----
    st.subheader("🏃 运动（逐条添加，自动累加）")
    ec1, ec2, ec3 = st.columns([2, 1, 1])
    ex_name = ec1.selectbox("运动类型", list(food_db.EXERCISES.keys()), key="ex_name")
    ex_minutes = ec2.number_input("时长 (分钟)", min_value=5, max_value=300, value=30, step=5)
    ec3.caption(f"当前体重 {latest_weight():.1f}kg")

    if st.button("➕ 添加运动", use_container_width=True):
        kcal = food_db.exercise_calories(ex_name, ex_minutes, latest_weight())
        db.add_exercise_entry(day_str, ex_name, ex_minutes, kcal)
        st.session_state["flash"] = f"已添加：{ex_name} {ex_minutes} 分钟 ≈ {kcal} kcal"
        st.rerun()

    if not exercises_today.empty:
        st.caption(f"当天已记录 {len(exercises_today)} 条，合计消耗 {ex_today:.0f} kcal：")
        for _, r in exercises_today.iterrows():
            col1, col2 = st.columns([5, 1])
            col1.write(f"· {r['name']} {r['minutes']:.0f} 分钟 = **{r['calories']:.0f} kcal**")
            if col2.button("删除", key=f"del_ex_{r['id']}"):
                db.delete_exercise_entry(r["id"])
                st.rerun()

    st.divider()

    # ---- 今日建议 ----
    st.subheader("💡 今日建议（运动 + 饮食调整）")
    if st.button("🤖 生成今日建议", use_container_width=True):
        food_list = foods_today.to_dict("records") if not foods_today.empty else []
        with st.spinner("生成建议中..."):
            advice = ai_report.daily_advice(food_list, intake_today, ex_today, settings, api_key, provider)
        st.markdown(advice)

# ===== Tab 2：目标计划 =====
with tab2:
    st.subheader("目标计划：算算你该吃多少、怎么练")
    st.caption("输入起始体重和目标体重，自动算每日热量 + 运动建议；目标太离谱会直接警告。")

    df_now = db.get_logs()
    latest_w = None
    if not df_now.empty:
        w_now = df_now["weight"].dropna()
        if len(w_now):
            latest_w = float(w_now.iloc[-1])

    c1, c2 = st.columns(2)
    start_w = c1.number_input("起始体重 (kg)", min_value=20.0, max_value=300.0,
                              value=latest_w if latest_w else 70.0, step=0.1)
    target_w = c2.number_input("目标体重 (kg)", min_value=20.0, max_value=300.0,
                               value=(latest_w - 5.0) if latest_w else 65.0, step=0.1)
    days = st.slider("目标天数", min_value=14, max_value=180, value=45)

    with st.expander("⚙️ 身体参数（影响热量计算，建议填写）"):
        g1, g2, g3, g4 = st.columns(4)
        gender = g1.selectbox("性别", ["男", "女"])
        height = g2.number_input("身高 (cm)", min_value=120, max_value=220, value=170)
        age = g3.number_input("年龄", min_value=15, max_value=80, value=30)
        activity = g4.selectbox("活动量", list(plan.ACTIVITY_LEVELS.keys()))

    if st.button("🎯 生成计划", type="primary", use_container_width=True):
        r = plan.weight_loss_plan(start_w, target_w, days, gender, height, age, activity)

        db.set_setting("gender", gender)
        db.set_setting("height", height)
        db.set_setting("age", age)
        db.set_setting("activity", activity)
        db.set_setting("start_weight", start_w)
        db.set_setting("target_weight", target_w)
        db.set_setting("days", days)
        db.set_setting("daily_intake_target", r["daily_intake"])

        if r.get("mode") == "maintain":
            st.info(f"目标体重（{target_w}kg）≥ 起始体重（{start_w}kg），减脂计划不适用。"
                    f"维持体重建议每日摄入约 {r['daily_intake']} kcal。")
        else:
            if r.get("is_unrealistic"):
                st.error(r["warning"])
                st.error(
                    f"📉 现实参考：{days} 天最多健康减约 **{r['realistic_loss']}kg**（每周≤1kg）。\n\n"
                    f"两个改法选一个：\n"
                    f"① 把天数延长到 **{r['suggested_days']} 天**；\n"
                    f"② 把目标体重上调到 **{round(start_w - r['realistic_loss'], 1)}kg** 左右。"
                )
            elif r.get("aggressive"):
                st.warning(r["warning"])
            elif r.get("below_floor"):
                st.warning(f"计算出的摄入已低于健康底线 {r['floor']} kcal，已按 {r['floor']} kcal 计算。")

            if r.get("too_thin"):
                st.warning(f"⚠️ 目标体重 BMI 约 {r['bmi_target']}，已低于 18.5（偏瘦），建议谨慎。")

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("基础代谢 BMR", f"{r['bmr']} kcal")
            m2.metric("每日消耗 TDEE", f"{r['tdee']} kcal")
            m3.metric("建议每日摄入", f"{r['daily_intake']} kcal")
            show_loss = min(r['weekly_loss'], 1.0) if r['weekly_loss'] > 0 else 0.0
            m4.metric("预计每周减", f"{show_loss:.2f} kg")

            st.divider()
            st.markdown(plan.exercise_plan_text())
            st.divider()
            st.markdown(plan.food_plan_text(r["daily_intake"], r["protein_g"]))

# ===== Tab 3：看板 =====
with tab3:
    summary = db.get_daily_summary()
    if summary.empty:
        st.info("暂无数据，请先在「记录」页录入。")
    else:
        settings = db.get_all_settings()

        w = summary["weight"].dropna()
        intake_s = summary["intake"]
        sleep = summary["sleep_hours"].dropna()

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("记录天数", len(summary))
        if len(w) >= 2:
            m2.metric("体重变化", f"{w.iloc[-1] - w.iloc[0]:+.1f} kg",
                      delta=f"{w.iloc[-1] - w.iloc[0]:+.1f} kg", delta_color="inverse")
        else:
            m2.metric("体重变化", "数据不足")
        m3.metric("平均摄入", f"{intake_s.mean():.0f} kcal" if intake_s.sum() > 0 else "未记录")
        m4.metric("平均睡眠", f"{sleep.mean():.1f} h" if len(sleep) else "未记录")

        st.divider()

        # ---- 目标进度 ----
        if settings.get("target_weight"):
            gt = plan.goal_tracking(summary, settings)
            if gt:
                st.subheader("🎯 目标进度")
                g1, g2, g3, g4 = st.columns(4)
                g1.metric("起始", f"{gt['start']} kg")
                g2.metric("当前", f"{gt['current']} kg",
                          delta=f"{gt['lost_so_far']:+.1f} kg", delta_color="inverse")
                g3.metric("目标", f"{gt['target']} kg")
                g4.metric("预计最终", f"{gt['projected']} kg")
                if gt["on_track"]:
                    st.success(f"✅ 按当前趋势，预计 {gt['days']} 天后体重约 {gt['projected']}kg，"
                               f"可达成目标 {gt['target']}kg。")
                else:
                    st.warning(f"⚠️ 按当前趋势，预计 {gt['days']} 天后体重约 {gt['projected']}kg，"
                               f"无法达成目标 {gt['target']}kg，还差 {gt['projected'] - gt['target']:.1f}kg。"
                               f"建议加大运动量或再降低摄入。")
                st.divider()

        # ---- 每日能量评估 ----
        if settings.get("gender"):
            st.subheader("⚡ 每日能量评估")
            ev_df = plan.evaluate_all_days(summary, settings)
            latest = ev_df.iloc[-1] if len(ev_df) else None
            if latest is not None and latest["intake"] > 0:
                e1, e2, e3, e4 = st.columns(4)
                e1.metric("今日摄入", f"{latest['intake']:.0f} kcal")
                e2.metric("运动消耗", f"{latest['exercise_kcal']:.0f} kcal")
                e3.metric("总消耗", f"{latest['total_burn']:.0f} kcal")
                e4.metric("净热量", f"{latest['net']:+.0f} kcal",
                          delta=f"{latest['net']:+.0f} kcal", delta_color="inverse")
                if latest["net"] <= 0:
                    st.success(latest["verdict"])
                else:
                    st.warning(latest["verdict"])

            # 平衡曲线
            fig_b = charts.balance_curve(ev_df)
            if fig_b:
                st.plotly_chart(fig_b, use_container_width=True)
            fig_e = charts.energy_balance_chart(ev_df)
            if fig_e:
                st.plotly_chart(fig_e, use_container_width=True)
        else:
            st.info("先在「🎯 目标计划」生成一次计划，这里会显示每日能量评估和平衡曲线。")

        st.divider()

        # ---- 基础图表 ----
        fig_w = charts.weight_chart(summary)
        if fig_w:
            st.plotly_chart(fig_w, use_container_width=True)

        c_left, c_right = st.columns(2)
        with c_left:
            fig_s = charts.sleep_chart(summary)
            if fig_s:
                st.plotly_chart(fig_s, use_container_width=True)
        with c_right:
            fig_m = charts.mood_chart(summary)
            if fig_m:
                st.plotly_chart(fig_m, use_container_width=True)

        anomalies = charts.detect_anomalies(summary)
        if anomalies:
            st.warning("⚠️ 检测到体重异常波动：")
            for a in anomalies:
                st.markdown(f"- **{a['date'].strftime('%m-%d')}**：{a['weight']:.1f}kg，偏离7日均线 {a['diff']:.1f}kg")

# ===== Tab 4：AI 周报 =====
with tab4:
    if not unlocked:
        st.warning("🔒 该功能需要付费解锁。请在左侧输入 License Key。")
    else:
        summary = db.get_daily_summary()
        if summary.empty:
            st.info("暂无数据，先录入至少 1 天数据。")
        else:
            st.subheader("生成 AI 周报")
            st.caption(f"当前共 {len(summary)} 天数据，周报基于最近 7 天生成。")
            if st.button("📄 生成本周报告", type="primary"):
                recent = summary.sort_values("date").tail(7)
                with st.spinner("正在生成报告..."):
                    report = ai_report.generate_report(recent, api_key, provider,
                                                       db.get_all_settings())
                st.markdown("---")
                st.markdown(report)

# ===== Tab 5：变化回放 =====
with tab5:
    st.subheader("📸 变化回放")
    st.caption("每天拍照积累，挑战结束时用动画播放你的变化过程。")
    photos = photo.list_photos()
    if not photos:
        st.info("还没有照片。去「📝 记录」页每天拍照上传，积累起来就能看变化了。")
    else:
        st.caption(f"已上传 {len(photos)} 张照片（{photos[0]['date']} ~ {photos[-1]['date']}）")

        st.subheader("🔍 逐张查看")
        dates = [p["date"] for p in photos]
        idx = st.slider("拖动查看", 0, len(photos) - 1, len(photos) - 1)
        st.image(photos[idx]["path"], caption=dates[idx], use_container_width=True)

        st.divider()

        st.subheader("🎬 动画回放")
        if len(photos) < 2:
            st.info("至少 2 张照片才能生成动画。")
        else:
            speed = st.slider("播放速度（每帧毫秒）", 100, 1000, 400, step=50,
                              help="数值越小播放越快")
            if st.button("🎬 生成变化动画", type="primary"):
                with st.spinner("正在生成动画..."):
                    try:
                        gif_buf = photo.make_gif(photos, duration=speed)
                    except Exception as e:  # noqa: BLE001
                        gif_buf = None
                        st.error(f"生成动画失败：{e}")
                if gif_buf:
                    st.success("动画已生成，循环播放中：")
                    st.image(gif_buf, caption="你的变化过程", use_container_width=True)
