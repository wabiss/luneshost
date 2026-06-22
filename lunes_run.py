import os
import time
import json
from playwright.sync_api import sync_playwright

SERVER_URL = os.getenv("LUNES_SERVER_URL")
LUNES_COOKIES = os.getenv("LUNES_COOKIES")

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
            browser.close()
            return

        page = context.new_page()
        print(f"正在访问 Lunes Host 控制面板: {SERVER_URL}")
        page.goto(SERVER_URL)
        
        # 停留 15 秒，确保 Lunes 服务器接收到完整的心跳和登录活跃统计
        page.wait_for_timeout(15000)

        # 保存打卡截图
        page.screenshot(path="lunes_debug_screenshot.png")
        print("已截取登录打卡画面。")

        # 判断是否登录失效
        if "login" in page.url or page.locator("input[type='email']").first.is_visible():
            print("登录失效，请重新用控制台脚本导出凭证并更新 LUNES_COOKIES。")
        else:
            print("✓ 每日登录打卡成功！已成功向 Lunes Host 刷新登录活跃状态。")

        browser.close()

if __name__ == "__main__":
    run()
