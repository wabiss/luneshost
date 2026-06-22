import os
import time
import json
import requests
from playwright.sync_api import sync_playwright

SERVER_URL = os.getenv("LUNES_SERVER_URL")
LUNES_COOKIES = os.getenv("LUNES_COOKIES")

def send_tg_notification(message, photo_path=None):
    """发送结果和运行截图至 Telegram"""
    token = os.getenv("TG_BOT_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")
    if not token or not chat_id:
        print("未配置 TG 机器人变量，跳过发送 TG 推送。")
        return

    # 1. 发送文字通知
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        requests.post(url, json=payload)
        print("TG 状态通知发送成功。")
    except Exception as e:
        print(f"发送 TG 消息异常: {e}")

    # 2. 发送截图照片
    if photo_path and os.path.exists(photo_path):
        try:
            url = f"https://api.telegram.org/bot{token}/sendPhoto"
            with open(photo_path, "rb") as f:
                files = {"photo": f}
                data = {"chat_id": chat_id, "caption": "运行实时画面"}
                requests.post(url, data=data, files=files)
            print("TG 实时截图发送成功。")
        except Exception as e:
            print(f"发送 TG 截图异常: {e}")

def run():
    if not SERVER_URL or not LUNES_COOKIES:
        print("错误: 缺少 LUNES_SERVER_URL 或 LUNES_COOKIES 环境变量")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        try:
            raw_data = json.loads(LUNES_COOKIES)
            cookies_to_add = []
            local_storage_to_add = {}

            if isinstance(raw_data, list):
                print("检测到纯 Cookie 格式数据...")
                cookies_to_add = raw_data
            elif isinstance(raw_data, dict):
                print("检测到合并格式数据...")
                cookies_to_add = raw_data.get("cookies", [])
                local_storage_to_add = raw_data.get("localStorage", {})
            else:
                raise ValueError("未知的数据格式")

            # 1. 注入 Cookies
            formatted_cookies = []
            for c in cookies_to_add:
                fc = {
                    "name": c["name"],
                    "value": c["value"],
                    "domain": c["domain"],
                    "path": c.get("path", "/")
                }
                if "expirationDate" in c:
                    fc["expires"] = int(c["expirationDate"])
                if "secure" in c:
                    fc["secure"] = c["secure"]
                if "httpOnly" in c:
                    fc["httpOnly"] = c["httpOnly"]
                if "sameSite" in c:
                    ss = str(c["sameSite"]).lower()
                    if ss in ["no_restriction", "none"]:
                        fc["sameSite"] = "None"
                    elif ss == "lax":
                        fc["sameSite"] = "Lax"
                    elif ss == "strict":
                        fc["sameSite"] = "Strict"
                formatted_cookies.append(fc)
            
            context.add_cookies(formatted_cookies)
            print("Cookie 注入成功！")

            # 2. 注入 LocalStorage
            if local_storage_to_add:
                init_script = ""
                for k, v in local_storage_to_add.items():
                    escaped_k = k.replace('\\', '\\\\').replace("'", "\\'")
                    escaped_v = v.replace('\\', '\\\\').replace("'", "\\'")
                    init_script += f"window.localStorage.setItem('{escaped_k}', '{escaped_v}');\n"
                
                context.add_init_script(init_script)
                print("LocalStorage 注入设置成功！")

        except Exception as e:
            print(f"凭证解析/注入失败: {e}")
            send_tg_notification(f"❌ <b>Lunes Host 运行异常</b>\n解析注入凭证失败: {e}")
            browser.close()
            return

        page = context.new_page()
        print(f"正在访问 Lunes Host 控制面板: {SERVER_URL}")
        page.goto(SERVER_URL)
        
        # 停留 15 秒确保完成登录记录
        page.wait_for_timeout(15000)

        # 保存截图作为打卡凭证
        page.screenshot(path="lunes_debug_screenshot.png")

        # 判断是否登录失效并推送 TG
        if "login" in page.url or page.locator("input[type='email']").first.is_visible():
            msg = "❌ <b>Lunes Host 登录失效！</b>\n请在浏览器控制台重新运行脚本生成 LUNES_COOKIES。"
            print(msg)
            send_tg_notification(msg, "lunes_debug_screenshot.png")
        else:
            msg = "✅ <b>Lunes Host 每日打卡保活成功！</b>\n已成功刷新活跃会话状态。"
            print(msg)
            send_tg_notification(msg, "lunes_debug_screenshot.png")

        browser.close()

if __name__ == "__main__":
    run()
