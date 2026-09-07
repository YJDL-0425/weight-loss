# -*- coding: utf-8 -*-
"""付费墙（Gumroad License 验证）。

MVP 阶段默认关闭（app.py 侧边栏有开关演示）。
真正上线卖钱时，把 product_permalink 换成你的产品地址即可。
"""
import requests


def verify_license(key, product_permalink="your-product"):
    """调用 Gumroad API 验证 License Key。返回 (是否有效, 提示信息)。"""
    if not key or not key.strip():
        return False, "请输入 License Key"
    try:
        r = requests.post(
            "https://api.gumroad.com/v2/licenses/verify",
            data={
                "product_permalink": product_permalink,
                "license_key": key.strip(),
                "increment_uses_count": "false",
            },
            timeout=15,
        )
        data = r.json()
        if data.get("success"):
            purchase = data.get("purchase", {})
            if purchase.get("refunded") or purchase.get("chargebacked"):
                return False, "该 License 已退款，无效"
            return True, "验证通过"
        return False, data.get("message", "验证失败")
    except Exception as e:  # noqa: BLE001
        return False, f"验证出错：{e}"
