#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import subprocess
import requests
from seleniumbase import SB

# 配置环境变量
EMAIL        = os.environ.get("KATABUMP_EMAIL") or ""
PASSWORD     = os.environ.get("KATABUMP_PASSWORD") or ""
TG_CHAT_ID   = os.environ.get("TG_CHAT_ID") or ""
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN") or ""

BASE_URL = "https://dashboard.katabump.com"

def send_tg_message(status_icon, status_text, time_left=""):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("ℹ️ 未配置 TG_BOT_TOKEN 或 TG_CHAT_ID，跳过 Telegram 推送。")
        return

    local_time = time.gmtime(time.time() + 8 * 3600)
    current_time_str = time.strftime("%Y-%m-%d %H:%M:%S", local_time)

    if '@' in EMAIL:
        name, domain = EMAIL.split('@', 1)
        if len(name) > 4:
            masked_email = f"{name[:2]}****{name[-2:]}@{domain}"
        else:
            masked_email = f"{name}@{domain}"
    else:
        masked_email = EMAIL[:2] + '****'

    text = (
        f"🇫🇷 katabump 续期通知\n\n"
        f"{status_icon} {status_text}\n"
        f"👤 续期账户: {masked_email}\n"
        f"⏱️ 运行时间: {current_time_str}"
    )
    if time_left:
        text += f"\nℹ️ 附加信息: {time_left}"

    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TG_CHAT_ID, "text": text}
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            print("📩 Telegram 通知发送成功！")
        else:
            print(f"⚠️ Telegram 通知发送失败: {r.text}")
    except Exception as e:
        print(f"⚠️ Telegram 通知发送异常: {e}")

# ===== JS注入脚本 (保留给弹窗内的 ALTCHA 验证) =====
_WININFO_JS = """(function(){ return { sx: window.screenX || 0, sy: window.screenY || 0, oh: window.outerHeight, ih: window.innerHeight }; })()"""

_ALTCHA_EXPAND_JS = """
(function() {
    var modal = document.querySelector('div.modal.show') || document;
    var iframes = modal.querySelectorAll('iframe');
    for (var i = 0; i < iframes.length; i++) {
        var r = iframes[i].getBoundingClientRect();
        if (r.width > 0 && r.height > 0) {
            iframes[i].style.width  = '300px';
            iframes[i].style.height = '150px';
            iframes[i].style.minWidth  = '300px';
            iframes[i].style.minHeight = '150px';
            iframes[i].style.visibility = 'visible';
            iframes[i].style.opacity = '1';
            var el = iframes[i];
            for (var j = 0; j < 10; j++) {
                el = el.parentElement;
                if (!el) break;
                el.style.overflow = 'visible';
            }
            var r2 = iframes[i].getBoundingClientRect();
            return { cx: Math.round(r2.x + 30), cy: Math.round(r2.y + r2.height / 2) };
        }
    }
    return null;
})()
"""

_ALTCHA_SOLVED_JS = """
(function(){
    var modal = document.querySelector('div.modal.show') || document;
    var inputs = modal.querySelectorAll('input[type="hidden"]');
    for (var i = 0; i < inputs.length; i++) {
        var n = (inputs[i].name || '').toLowerCase();
        if ((n.includes('altcha') || n.includes('captcha')) && inputs[i].value && inputs[i].value.length > 20) return true;
    }
    var cbs = modal.querySelectorAll('input[type="checkbox"]');
    for (var j = 0; j < cbs.length; j++) {
        if (cbs[j].disabled) return true;
    }
    var w = modal.querySelector('[data-state="verified"],.altcha--verified,.altcha-verified');
    if (w) return true;
    return false;
})()
"""

def _activate_window():
    for cls in ["chrome", "chromium", "Chromium", "Chrome", "google-chrome"]:
        try:
            r = subprocess.run(["xdotool", "search", "--onlyvisible", "--class", cls], capture_output=True, text=True, timeout=3)
            wids = [w for w in r.stdout.strip().split("\n") if w.strip()]
            if wids:
                subprocess.run(["xdotool", "windowactivate", "--sync", wids[0]], timeout=3, stderr=subprocess.DEVNULL)
                time.sleep(0.2)
                return
        except Exception: pass
    try:
        subprocess.run(["xdotool", "getactivewindow", "windowactivate"], timeout=3, stderr=subprocess.DEVNULL)
    except Exception: pass

def _xdotool_click(x: int, y: int):
    _activate_window()
    try:
        subprocess.run(["xdotool", "mousemove", "--sync", str(x), str(y)], timeout=3, stderr=subprocess.DEVNULL)
        time.sleep(0.15)
        subprocess.run(["xdotool", "click", "1"], timeout=2, stderr=subprocess.DEVNULL)
    except Exception:
        os.system(f"xdotool mousemove {x} {y} click 1 2>/dev/null")

# ===== 核心流程 =====

def login(sb) -> bool:
    print(f"🌐 打开登录页面: {BASE_URL}/auth/login")
    sb.uc_open_with_reconnect(BASE_URL + "/auth/login", reconnect_time=8)
    time.sleep(8)

    try:
        sb.wait_for_element('input[type="email"]', timeout=15)
    except Exception:
        try:
            sb.wait_for_element('input[type="Email"]', timeout=5)
        except Exception:
            print("❌ 页面未加载出登录表单")
            sb.save_screenshot("login_load_fail.png")
            return False

    print("🍪 关闭可能的 Cookie 弹窗...")
    try:
        for btn in sb.find_elements("button"):
            if "Accept" in (btn.text or ""):
                btn.click()
                time.sleep(0.5)
                break
    except Exception: pass

    print(f"📧 填写邮箱...")
    sb.type('input[type="email"], input[type="Email"]', EMAIL)
    time.sleep(1)
    
    print("🔑 填写密码...")
    sb.type('input[type="password"]', PASSWORD)
    time.sleep(2)

    print("⏳ 检测 Cloudflare Turnstile 验证框...")
    if sb.is_element_present('iframe[src*="challenges.cloudflare.com"]'):
        print("✅ 发现 Turnstile 组件，启动底层物理模拟点击...")
        try:
            sb.uc_gui_click_captcha()
            time.sleep(4)
        except Exception as e:
            print(f"⚠️ 物理点击警告 (可能已通过): {e}")
    else:
        print("ℹ️ 未发现 Turnstile 组件，可能已静默通过。")

    print("🖱️ 提交表单...")
    try:
        sb.click('//button[contains(translate(., "LOGIN", "login"), "login")]')
    except Exception:
        sb.press_keys('input[type="password"]', '\n')

    print("⏳ 等待登录跳转...")
    for _ in range(15):
        time.sleep(1)
        cur_url = sb.get_current_url().lower()
        if "login" not in cur_url and "dashboard" in cur_url: 
            print("✅ 登录成功！")
            return True

    print("❌ 登录失败，页面未发生有效跳转。")
    sb.save_screenshot("login_failed.png")
    return False

def _read_alert(sb):
    try:
        el = sb.find_element("div.alert", timeout=4)
        return (el.text or "").strip()
    except Exception: return ""

def _goto_server_detail(sb) -> bool:
    print("\n🖥️  正在进入服务器详情页...")
    time.sleep(5)

    alert_text = _read_alert(sb)
    if alert_text and "can't renew" in alert_text.lower():
        send_tg_message("⏳", "未到续期时间", alert_text)
        return False

    selectors = ['a[href*="/servers/edit?id="]', 'td a[href*="/servers/edit"]', 'table a[href*="/servers/edit"]']
    see_link = None
    for sel in selectors:
        try:
            see_link = sb.find_element(sel, timeout=8)
            break
        except Exception: continue

    if see_link is None:
        try:
            for a in sb.find_elements("a"):
                if (a.text or "").strip().lower() == "see":
                    see_link = a
                    break
        except Exception: pass

    if see_link is None:
        sb.save_screenshot("servers_page_fail.png")
        return False

    see_link.click()
    time.sleep(5)
    return True

def _open_renew_modal(sb) -> bool:
    print("\n🔄 查找 Renew 按钮...")
    try:
        renew_btn = sb.find_element('button[data-bs-target="#renew-modal"]', timeout=10)
    except Exception:
        try: renew_btn = sb.find_element('button.btn.btn-outline-primary', timeout=5)
        except Exception: return False

    sb.execute_script("""
        (function(){
            var btn = document.querySelector('button[data-bs-target="#renew-modal"]') || document.querySelector('button.btn.btn-outline-primary');
            if (btn) btn.scrollIntoView({behavior:'smooth',block:'center'});
        })()
    """)
    time.sleep(0.8)
    renew_btn.click()
    time.sleep(3)
    try:
        sb.find_element('div.modal.show', timeout=5)
        return True
    except Exception:
        return False

def _solve_altcha(sb) -> bool:
    print("\n🔐 处理 ALTCHA 人机验证...")
    time.sleep(2)
    if sb.execute_script(_ALTCHA_SOLVED_JS): return True

    coords = None
    try: coords = sb.execute_script(_ALTCHA_EXPAND_JS)
    except Exception: pass

    for attempt in range(3):
        if sb.execute_script(_ALTCHA_SOLVED_JS): return True

        if coords:
            try: wi = sb.execute_script(_WININFO_JS)
            except Exception: wi = {"sx": 0, "sy": 0, "oh": 800, "ih": 768}
            bar = wi["oh"] - wi["ih"]
            ax  = coords["cx"] + wi["sx"]
            ay  = coords["cy"] + wi["sy"] + bar
            _xdotool_click(ax, ay)
        
        try:
            iframes = sb.find_elements('div.modal.show iframe')
            for iframe in iframes: iframe.click()
        except Exception: pass

        sb.execute_script("""
            (function(){
                var modal = document.querySelector('div.modal.show');
                if (!modal) return;
                var iframes = modal.querySelectorAll('iframe');
                for (var i = 0; i < iframes.length; i++) { iframes[i].click(); iframes[i].dispatchEvent(new MouseEvent('click', {bubbles:true})); }
                var cbs = modal.querySelectorAll('input[type="checkbox"]');
                for (var k = 0; k < cbs.length; k++) { if (!cbs[k].disabled) { cbs[k].click(); cbs[k].dispatchEvent(new MouseEvent('click', {bubbles:true})); } }
            })()
        """)

        for _ in range(8):
            time.sleep(1)
            if sb.execute_script(_ALTCHA_SOLVED_JS): return True

        try:
            new_coords = sb.execute_script(_ALTCHA_EXPAND_JS)
            if new_coords: coords = new_coords
        except Exception: pass

    return False

def _submit_renew(sb):
    print("🖱️  点击模态框中的 Renew 按钮...")
    try:
        submit = sb.find_element('div.modal-footer button.btn.btn-primary', timeout=10)
        submit.click()
    except Exception:
        sb.execute_script("""
            (function(){
                var m = document.querySelector('button.btn.btn-primary');
                if (!m) return;
                var bs = m.querySelectorAll('button');
                for (var i = 0; i < bs.length; i++) if (/renew/i.test(bs[i].textContent)) bs[i].click();
            })()
        """)
    time.sleep(8)

def _check_renew_result(sb):
    print("\n📋 检查续期结果...")
    alert_text = _read_alert(sb)
    if not alert_text:
        time.sleep(3)
        alert_text = _read_alert(sb)

    if alert_text:
        low = alert_text.lower()
        if "can't renew" in low or "unable" in low:
            send_tg_message("⏳", "未到续期时间", alert_text)
        elif any(kw in low for kw in ("renewed", "success", "extended")):
            send_tg_message("✅", "续期成功", alert_text)
        else:
            send_tg_message("ℹ️", "续期操作已执行", alert_text)
    else:
        send_tg_message("ℹ️", "续期操作已执行", "未检测到明确提示")

def renew_server(sb):
    if not _goto_server_detail(sb): return
    if not _open_renew_modal(sb): return

    altcha_ok = _solve_altcha(sb)
    if not altcha_ok:
        print("⚠️ ALTCHA 验证未通过，尝试强制提交...")

    _submit_renew(sb)
    _check_renew_result(sb)

def main():
    IS_PROXY = os.environ.get("IS_PROXY", "false").lower() == "true"
    proxy_str = os.environ.get("PROXY_SERVER", "").strip() or "http://127.0.0.1:1081"
    sb_kwargs = {"uc": True, "headless": False}

    if IS_PROXY:
        sb_kwargs["proxy"] = proxy_str
    
    with SB(**sb_kwargs) as sb:
        if login(sb):
            renew_server(sb)
        else:
            send_tg_message("❌", "登录失败", "详情请查看截图")

if __name__ == "__main__":
    main()
