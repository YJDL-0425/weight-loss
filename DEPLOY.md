# 部署上线步骤（把产品发到网上）

## 第 1 步：Supabase 建表（一次性，5分钟）

1. 打开 https://supabase.com/dashboard 登录
2. 进入你的项目（pgdtcnialoyfbvxcomos）
3. 左侧点 **SQL Editor** → **New query**
4. 把 `supabase_schema.sql` 文件内容**全部粘贴**进去
5. 点 **Run**（右下角绿色按钮）

看到 "Success" 就成功了。

## 第 2 步：本地验证（确认代码连得上云）

```bash
cd C:/Users/13769/pi-cwd-20260813/weight-loss-mvp
streamlit run app.py
```

打开后：
- 录入一条数据 → 保存
- 去 Supabase 的 **Table Editor** 看 `daily_logs` 表里有没有这条数据

有 → 成功，进入第 3 步。

## 第 3 步：传到 GitHub

1. 打开 https://github.com 登录
2. 点右上角 **+** → **New repository**
3. 名字填 `weight-loss`，选 **Private**（私密，重要！因为里面有 API Key）
4. 创建后，在本地执行（把代码推上去）：

```bash
cd C:/Users/13769/pi-cwd-20260813/weight-loss-mvp
git init
git add .
git commit -m "first version"
git branch -M main
git remote add origin https://github.com/你的用户名/weight-loss.git
git push -u origin main
```

## 第 4 步：Streamlit Cloud 部署

1. 打开 https://share.streamlit.io 用 GitHub 登录
2. 点 **Create app** / **New app**
3. 选你的仓库 `weight-loss`，分支 `main`，入口文件 `app.py`
4. 点 **Deploy**
5. 部署完成后，点 **App Settings → Secrets**，填入：

```toml
SUPABASE_URL = "https://pgdtcnialoyfbvxcomos.supabase.co"
SUPABASE_KEY = "sb_publishable__Dm5BiHcX1f1cBtBuSyDEw_0Dxeybby"
DEEPSEEK_API_KEY = "sk-b131f17f965248c69b0458613efa098c"
```

6. 保存后 App 会自动重启

## 第 5 步：拿到网址

部署完成后，Streamlit 会给你一个网址（形如 `https://xxx.streamlit.app`）。

手机、电脑、任何地方打开这个网址就能用，数据都在云端。

---

## ⚠️ 重要提醒

1. **仓库必须 Private**：代码里没存 Key（Key 在 .env 和 Secrets 里，都已 gitignore），但保险起见还是 Private。
2. **当前是单用户版**：没有登录功能，任何人拿到网址都能看到同一份数据。**先自己用，别公开分享网址**。以后要卖钱再加登录。
3. 每次改完代码，本地 `git push`，Streamlit Cloud 会自动重新部署。
