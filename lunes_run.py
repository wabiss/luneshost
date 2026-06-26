import os
import time
import json
import urllib.parse
import random
import requests
from playwright.sync_api import sync_playwright

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

def check_is_cf_page(page):
    """检测当前是否仍卡在验证码页面"""
    try:
        child_frames = [f for f in page.frames if f != page.main_frame]
        return len(child_frames) > 0
    except Exception:
        return True

def load_page_with_cf_bypass(page, url):
    """智能页面加载函数：自动等待并利用物理位置模拟点击穿透 Cloudflare 的人机验证"""
    print(f"正在访问页面: {url}")
    page.goto(url)
    page.wait_for_timeout(6000)

    # 包含可能出现的各种 Cloudflare iframe 标志，以 iframe 作为保底
    cf_selectors = [
        "iframe[src*='challenge-platform']",
        "iframe[src*='challenges.cloudflare.com']",
        "iframe"
    ]
    
    iframe_selector = ""
    for _ in range(15):
        for selector in cf_selectors:
            try:
                if page.locator(selector).first.is_visible():
                    iframe_selector = selector
                    break
            except Exception:
                pass
        if iframe_selector:
            break
        page.wait_for_timeout(1000)

    if iframe_selector:
        print(f"⚡ 检测到 Cloudflare 验证盾 iframe 元素 ('{iframe_selector}')！正在尝试过盾...")
        page.wait_for_timeout(3000)
        
        try:
            # 读取绝对物理坐标
            box = page.locator(iframe_selector).first.bounding_box()
            if box:
                print(f"定位到验证盾坐标: x={box['x']:.1f}, y={box['y']:.1f}, w={box['width']:.1f}, h={box['height']:.1f}")
                
                # 理论复选框正中心
                click_x = box["x"] + 35
                click_y = box["y"] + box["height"] / 2
                
                print(f"正在模拟真人鼠标平滑移动至 ({click_x:.1f}, {click_y:.1f}) 并执行物理按压点击...")
                page.mouse.move(click_x, click_y, steps=15)
                page.wait_for_timeout(random.randint(400, 800))
                page.mouse.down()
                page.wait_for_timeout(random.randint(100, 180))
                page.mouse.up()
                page.wait_for_timeout(6000)
        except Exception as e:
            print(f"模拟鼠标点击过程中发生异常: {e}")
    else:
        print("页面未检测到验证盾，或已成功跳过。")
        
    page.wait_for_timeout(3000)

def login_lunes(page, email, password):
    """模拟真人输入账号密码，并物理攻克登录表单下方的嵌入式验证盾"""
    print("正在访问 Lunes Host 登录界面...")
    # 直接进军最真实的登录页，并通过 load_page_with_cf_bypass 过掉可能阻挡在最外层的验证盾
    load_page_with_cf_bypass(page, "https://betadash.lunes.host/login")
    
    # 拍照留档
    page.screenshot(path="lunes_debug_screenshot.png")

    try:
        print("正在定位账号密码输入框并填充...")
        # 1. 精准填充邮箱
        email_input = page.locator("input[type='email']").first
        email_input.wait_for(state="visible", timeout=15000)
        email_input.fill(email)

        # 2. 精准填充密码
        password_input = page.locator("input[type='password']").first
        password_input.fill(password)
        page.wait_for_timeout(1000)

        # 3. 核心大招：自动扫描并检测登录表单下方是否内嵌了验证码（Verify you are human）
        print("正在检测登录表单下方是否存在内嵌验证码...")
        turnstile_frame = None
        for i in range(10):
            child_frames = [f for f in page.frames if f != page.main_frame]
            if len(child_frames) > 0:
                turnstile_frame = child_frames[0]
                break
            page.wait_for_timeout(1000)

        if turnstile_frame:
            print("⚡ 成功捕获到表单下方的嵌入式人机验证码！")
            page.wait_for_timeout(3000)
            try:
                # 穿透影子 DOM，利用 frame_element().bounding_box() 夺取该嵌入验证盾在当前屏幕上的最精确像素坐标
                iframe_handle = turnstile_frame.frame_element()
                box = iframe_handle.bounding_box()
                if box:
                    print(f"✓ 成功获取嵌入验证盾物理坐标: x={box['x']:.1f}, y={box['y']:.1f}, w={box['width']:.1f}, h={box['height']:.1f}")
                    # 复选框黄金中心坐标
                    click_x = box["x"] + 35
                    click_y = box["y"] + box["height"] / 2
                    
                    print(f"正在模拟真人平滑移动至 ({click_x:.1f}, {click_y:.1f}) 并点击勾选人机验证...")
                    page.mouse.move(click_x, click_y, steps=15)
                    page.wait_for_timeout(random.randint(400, 800))
                    page.mouse.down()
                    page.wait_for_timeout(random.randint(100, 180))
                    page.mouse.up()
                    
                    # 给予 8 秒判定时间
                    page.wait_for_timeout(8000)
            except Exception as e:
                print(f"尝试物理点击嵌入验证码时发生异常: {e}")

        # 4. 点击 Continue 按钮提交登录
        submit_btn = page.locator("button:has-text('Continue'), button[type='submit']").first
        if submit_btn.is_visible():
            print("正在点击 Continue 提交表单...")
            submit_btn.click()
            page.wait_for_timeout(10000)

        if "login" in page.url:
            print("❌ 自动登录失败：仍停留在登录页面。")
            return False

        print("✓ 自动登录成功！")
        return True
    except Exception as e:
        print(f"❌ 自动登录过程中发生异常: {e}")
        return False

def run():
    if not SERVER_URL or not LUNES_EMAIL or not LUNES_PASSWORD:
        print("错误: 缺少必要配置 LUNES_SERVER_URL、LUNES_EMAIL 或 LUNES_PASSWORD")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )

        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        page = context.new_page()

        # 全局流量拦截
        def handle_route(route):
            headers = {**route.request.headers}
            headers["sec-ch-ua"] = '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"'
            headers["sec-ch-ua-mobile"] = "?0"
            headers["sec-ch-ua-platform"] = '"Windows"'
            headers["user-agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            route.continue_(headers=headers)

        page.route("**/*", handle_route)

        # 执行自动登录（内置表单内嵌盾自动点击）
        if login_lunes(page, LUNES_EMAIL, LUNES_PASSWORD):
            print(f"正在跳转至目标保活控制面板: {SERVER_URL}")
            page.goto(SERVER_URL)
            
            # 停留 15 秒，确保 Lunes 服务器接收到完整的登录活跃打卡心跳
            page.wait_for_timeout(15000)

            # 保存打卡截图
            page.screenshot(path="lunes_debug_screenshot.png")
            print("已截取登录打卡画面。")

            if "login" in page.url or page.locator("input[type='email']").first.is_visible():
                msg = "❌ <b>Lunes Host 登录失效！</b>\n跳转至面板页面时，发现仍处于登录页面状态。"
                print(msg)
                send_tg_notification(msg, "lunes_debug_screenshot.png")
            else:
                msg = "✅ <b>Lunes Host 每日自动登录打卡成功！</b>\n已通过账号密码模式刷新控制面板活跃状态。"
                print(msg)
                send_tg_notification(msg, "lunes_debug_screenshot.png")
        else:
            page.screenshot(path="lunes_debug_screenshot.png")
            msg = "❌ <b>Lunes Host 运行异常</b>\n使用账号密码执行第一步自动登录时失败。"
            print(msg)
            send_tg_notification(msg, "lunes_debug_screenshot.png")

        browser.close()

if __name__ == "__main__":
    run()
