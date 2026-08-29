#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import subprocess
import requests
import json
from seleniumbase import SB

TG_CHAT_ID   = os.environ.get("TG_CHAT_ID") or ""
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN") or ""
BASE_URL = "https://dashboard.katabump.com"

# ===== 辅助功能 =====
def get_users_from_json():
    users_json = os.environ.get("USERS_JSON", "").strip()
    if not users_json:
        return []
    try:
        parsed = json.loads(users_json)
        if isinstance(parsed, list):
            return parsed
        elif isinstance(parsed, dict) and "users" in parsed:
            return parsed["users"]
        elif isinstance(parsed, dict) and ("username" in parsed or "email" in parsed):
            return [parsed]
    except Exception as e:
        print(f"❌ 解析 USERS_JSON 失败: {e}")
    return []

def send_tg_message(email, status_icon, status_text, time_left=""):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        return

    local_time = time.gmtime(time.time() + 8 * 3600)
    current_time_str = time.strftime("%Y-%m-%d %H:%M:%S", local_time)

    if '@' in email:
        name, domain = email.split('@', 1)
        masked_email = f"{name[:2]}****{name[-2:]}@{domain}" if len(name) > 4 else f"{name}@{domain}"
    else:
        masked_email = email[:2] + '****'

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
        requests.post(url, json=payload, timeout=10)
    except Exception:
        pass

# ===== JS 注入变量 =====
_WININFO_JS = """(function(){ return { sx: window.screenX || 0, sy: window.screenY || 0, oh: window.outerHeight, ih: window.innerHeight }; })()"""
_ALTCHA_EXPAND_JS = """
(function() {
    var modal = document.querySelector('div.modal.show') || document;
    var iframes = modal.querySelectorAll('iframe');
    for (var i = 0; i < iframes.length; i++) {
        var r = iframes[i].getBoundingClientRect();
        if (r.width > 0 && r.height > 0) {
            iframes[i].style.width  = '300px'; iframes[i].style.height = '150px';
            iframes[i].style.minWidth  = '300px'; iframes[i].style.minHeight = '150px';
            iframes[i].style.visibility = 'visible'; iframes[i].style.opacity = '1';
            var el = iframes[i];
            for (var j = 0; j < 10; j++) { el = el.parentElement; if (!el) break; el.style.overflow = 'visible'; }
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
    for (var j = 0; j < cbs.length; j++) if (cbs[j].disabled) return true;
    if (modal.querySelector('[data-state="verified"],.altcha--verified,.altcha-verified')) return true;
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
def handle_turnstile(sb) -> bool:
    print("⏳ 正在等待 Cloudflare 验证码加载...")
    ts_found = False
    for _ in range(12):
        if sb.is_element_present('iframe[src*="challenges.cloudflare.com"]'):
            ts_found = True
            break
        time.sleep(1)
        
    if not ts_found:
        print("ℹ️ 未发现 Turnstile 组件，可能已静默通过。")
        return True
        
    print("✅ 发现 Turnstile 组件，等待其初始化...")
    time.sleep(3)
    
    solved_js = """
    var i = document.querySelector('input[name="cf-turnstile-response"]');
    return !!(i && i.value && i.value.length > 20);
    """
    
    if sb.execute_script(solved_js):
        print("✅ Turnstile 已静默通过。")
        return True
        
    for attempt in range(4):
        print(f"🖱️ 第 {attempt + 1} 次启动底层物理模拟点击...")
        try:
            sb.execute_script("""
                document.querySelectorAll('iframe').forEach(f => {
                    if(f.src.includes('challenges.cloudflare.com')){
                        f.style.width='300px'; f.style.height='65px'; 
                        f.style.visibility='visible'; f.style.opacity='1';
                    }
                });
            """)
            time.sleep(0.5)
            sb.uc_gui_click_captcha()
        except Exception as e:
            print(f"⚠️ 物理点击警告: {e}")
            
        for _ in range(12):
            time.sleep(1)
            if sb.execute_script(solved_js):
                print("✅ Turnstile 验证通过！")
                return True
    
    print("❌ 多次尝试物理点击均未通过验证。")
    return False

def login(sb, email, password) -> bool:
    print(f"\n🌐 打开登录页面: {BASE_URL}/auth/login")
    sb.uc_open_with_reconnect(BASE_URL + "/auth/login", reconnect_time=8)
    time.sleep(8)

    if not email or not password:
        print("❌ 致命错误：当前账号密码为空！")
        return False

    try:
        sb.wait_for_element('input[name="email"]', timeout=15)
    except Exception:
        print("❌ 页面未加载出登录表单")
        sb.save_screenshot(f"{email}_login_load_fail.png")
        return False

    print("🍪 关闭可能的 Cookie 弹窗...")
    try:
        for btn in sb.find_elements("button"):
            if "Accept" in (btn.text or ""):
                btn.click()
                time.sleep(0.5)
                break
    except Exception: pass

    print(f"📧 填写邮箱: {email}")
    email_sel = 'input[name="email"]'
    sb.click(email_sel)
    sb.clear(email_sel)
    sb.type(email_sel, email)
    
    print("🔑 填写密码...")
    pwd_sel = 'input[name="password"]'
    sb.click(pwd_sel)
    sb.clear(pwd_sel)
    sb.type(pwd_sel, password)
    time.sleep(1)

    entered_email = sb.get_value(email_sel)
    if not entered_email or len(entered_email) < 2:
        print("⚠️ 原生输入失败，启用 JS 强力赋值兜底...")
        safe_email = email.replace('"', '\\"')
        safe_pwd = password.replace('"', '\\"')
        sb.execute_script(f'''
            var em = document.querySelector('input[name="email"]');
            var pw = document.querySelector('input[name="password"]');
            if(em) {{ em.value = "{safe_email}"; em.dispatchEvent(new Event('input', {{bubbles:true}})); }}
            if(pw) {{ pw.value = "{safe_pwd}"; pw.dispatchEvent(new Event('input', {{bubbles:true}})); }}
        ''')
        time.sleep(1)

    if not handle_turnstile(sb):
        sb.save_screenshot(f"{email}_turnstile_fail.png")

    print("🖱️ 提交表单...")
    try:
        sb.click('button[type="submit"]')
    except Exception:
        sb.press_keys(pwd_sel, '\n')

    print("⏳ 等待登录跳转...")
    for _ in range(15):
        time.sleep(1)
        cur_url = sb.get_current_url().lower()
        if "login" not in cur_url and "dashboard" in cur_url: 
            print("✅ 登录成功！")
            return True

    print("❌ 登录失败，页面未发生有效跳转。")
    sb.save_screenshot(f"{email}_login_failed.png")
    return False

def _read_alert(sb):
    try:
        el = sb.find_element("div.alert", timeout=4)
        return (el.text or "").strip()
    except Exception: return ""

def _goto_server_detail(sb, email) -> bool:
    print("\n🖥️  正在进入服务器详情页...")
    time.sleep(5)

    alert_text = _read_alert(sb)
    if alert_text and "can't renew" in alert_text.lower():
        send_tg_message(email, "⏳", "未到续期时间", alert_text)
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
        sb.save_screenshot(f"{email}_servers_page_fail.png")
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

def _check_renew_result(sb, email):
    print("\n📋 检查续期结果...")
    alert_text = _read_alert(sb)
    if not alert_text:
        time.sleep(3)
        alert_text = _read_alert(sb)

    if alert_text:
        low = alert_text.lower()
        if "can't renew" in low or "unable" in low:
            send_tg_message(email, "⏳", "未到续期时间", alert_text)
        elif any(kw in low for kw in ("renewed", "success", "extended")):
            send_tg_message(email, "✅", "续期成功", alert_text)
            print("【日志标志】续期成功") # 给 YAML 的 grep 使用
        else:
            send_tg_message(email, "ℹ️", "续期操作已执行", alert_text)
    else:
        send_tg_message(email, "ℹ️", "续期操作已执行", "未检测到明确提示")

def renew_server(sb, email):
    if not _goto_server_detail(sb, email): return
    if not _open_renew_modal(sb): return

    altcha_ok = _solve_altcha(sb)
    if not altcha_ok:
        print("⚠️ ALTCHA 验证未通过，尝试强制提交...")

    _submit_renew(sb)
    _check_renew_result(sb, email)

def main():
    print("#" * 25)
    print("   katabump 多账号自动续期")
    print("#" * 25)

    users = get_users_from_json()
    if not users:
        print("❌ 未在 USERS_JSON 中读取到任何账号信息。")
        return

    IS_PROXY = os.environ.get("IS_PROXY", "false").lower() == "true"
    proxy_str = os.environ.get("PROXY_SERVER", "").strip() or "http://127.0.0.1:1081"
    sb_kwargs = {"uc": True, "headless": False}

    if IS_PROXY:
        sb_kwargs["proxy"] = proxy_str
    
    with SB(**sb_kwargs) as sb:
        for idx, user in enumerate(users):
            email = user.get("username") or user.get("email") or ""
            password = user.get("password") or ""
            
            print(f"\n[{idx+1}/{len(users)}] 开始处理账号: {email}")
            
            # 关键：清除上一个账号的会话 Cookie
            sb.delete_all_cookies() 
            
            if login(sb, email, password):
                renew_server(sb, email)
            else:
                send_tg_message(email, "❌", "登录失败", "详情请查看截图")

if __name__ == "__main__":
    main()
