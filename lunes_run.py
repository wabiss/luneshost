import os
import time
import json
import urllib.parse
import requests
# 引入 SeleniumBase 高级过盾包
from seleniumbase import SB

SERVER_URL = os.getenv("LUNES_SERVER_URL")
LUNES_EMAIL = os.getenv("LUNES_EMAIL")
LUNES_PASSWORD = os.getenv("LUNES_PASSWORD")

def send_tg_notification(message, photo_path=None):
    """发送结果和截图至 Telegram"""
    token = os.getenv("TG_BOT_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")
    if not token or not chat_id:
        print("未配置 TG 机器人变量，跳过发送 TG 推送。")
        return

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

    if photo_path and os.path.exists(photo_path):
        try:
            url = f"https://api.telegram.org/bot{token}/sendPhoto"
            with open(photo_path, "rb") as f:
                files = {"photo": f}
                data = {"chat_id": chat_id, "caption": "Lunes Host 实时画面"}
                requests.post(url, data=data, files=files)
            print("TG 截图发送成功。")
        except Exception as e:
            print(f"发送 TG 截图异常: {e}")

def run():
    if not SERVER_URL or not LUNES_EMAIL or not LUNES_PASSWORD:
        print("错误: 缺少必要配置 LUNES_SERVER_URL、LUNES_EMAIL 或 LUNES_PASSWORD")
        return

    # 1. 启动 SeleniumBase 并开启 UC 模式与 Xvfb 虚拟系统桌面
    with SB(uc=True, xvfb=True) as sb:
        print("正在打开 Lunes Host 登录界面...")
        # 使用 UC 专属重连模式访问，能极大缓解首屏 Cloudflare 阻断
        sb.uc_open_with_reconnect("https://betadash.lunes.host/login", reconnect_time=8)
        sb.sleep(5)

        # 2. 核心大招：自动寻找并执行系统物理级点击，过掉最外层的 Cloudflare 人机验证盾
        sb.save_screenshot("lunes_debug_screenshot.png")
        try:
            print("正在检测并调用系统级 PyAutoGUI 驱动，物理点击最外层 Cloudflare 验证盾...")
            sb.uc_gui_click_captcha()
            sb.sleep(10)
            sb.save_screenshot("lunes_debug_screenshot.png")
        except Exception as e:
            print(f"验证盾点击结束或已被跳过: {e}")

        # 3. 填充表单
        try:
            print("正在定位账号密码输入框并填充...")
            # 阻塞式等待邮箱输入框渲染
            sb.wait_for_element_visible("input[type='email']", timeout=15)
            sb.update_text("input[type='email']", LUNES_EMAIL)
            
            # 填充密码
            sb.update_text("input[type='password']", LUNES_PASSWORD)
            sb.sleep(1)

            # 4. 点击“记住我”长效 Token
            if sb.is_element_visible("input[type='checkbox']"):
                sb.click("input[type='checkbox']")
                print("已成功勾选记住我。")

            # 5. 核心大招 2：自动检测并物理点击登录表单下方内嵌的验证盾
            try:
                print("正在检测并物理点击登录表单下方内嵌的验证盾...")
                sb.uc_gui_click_captcha()
                sb.sleep(5)
            except Exception as e:
                print(f"表单内嵌验证盾处理完成: {e}")

            # 6. 点击 Continue 按钮提交登录
            # 包含 Continue 或 Zaloguj 等常见的提交文字
            submit_btn_selector = "button:contains('Continue'), button:contains('Zaloguj'), button[type='submit']"
            if sb.is_element_visible(submit_btn_selector):
                print("正在点击 Continue 提交表单...")
                sb.click(submit_btn_selector)
                sb.sleep(10) # 等待登录跳转
        except Exception as e:
            print(f"❌ 登录表单填充或提交过程中发生异常: {e}")
            sb.save_screenshot("lunes_debug_screenshot.png")
            send_tg_notification(f"❌ <b>Lunes Host 运行异常</b>\n执行自动填表登录时失败: {e}", "lunes_debug_screenshot.png")
            return

        # 7. 验证登录状态并跳转至保活目标页
        current_url = sb.get_current_url()
        if "login" in current_url or sb.is_element_visible("input[type='email']"):
            print("❌ 自动登录失败：仍停留在登录页面。")
            sb.save_screenshot("lunes_debug_screenshot.png")
            send_tg_notification("❌ <b>Lunes Host 自动登录失败</b>\n未能成功进入后台系统。", "lunes_debug_screenshot.png")
            return

        print(f"✓ 登录成功！正在跳转至目标保活控制面板: {SERVER_URL}")
        sb.open(SERVER_URL)
        
        # 停留 15 秒，确保 Lunes 服务器接收到完整的打卡活跃心跳
        sb.sleep(15)

        # 保存打卡完成截图
        sb.save_screenshot("lunes_debug_screenshot.png")
        print("已截取登录打卡画面。")

        if "login" in sb.get_current_url() or sb.is_element_visible("input[type='email']"):
            msg = "❌ <b>Lunes Host 登录失效！</b>\n跳转至面板页面时，发现状态退回到了未登录状态。"
            print(msg)
            send_tg_notification(msg, "lunes_debug_screenshot.png")
        else:
            msg = "✅ <b>Lunes Host 每日自动登录打卡成功！</b>\n已通过账号密码 + 物理双重过盾机制刷新控制面板活跃状态。"
            print(msg)
            send_tg_notification(msg, "lunes_debug_screenshot.png")

        # 自动由 with 语句关闭浏览器生命周期

if __name__ == "__main__":
    run()
