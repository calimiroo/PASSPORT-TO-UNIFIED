import streamlit as st
import pandas as pd
import time
import asyncio
import sys
import os
import subprocess

# --- حيلة لتثبيت متصفح Playwright تلقائياً على السيرفر ---
@st.cache_resource
def install_playwright_browsers():
    try:
        # محاولة تشغيل أمر تثبيت كروميوم
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        return True
    except Exception as e:
        st.error(f"Error installing browsers: {e}")
        return False

# تشغيل التثبيت
install_playwright_browsers()

from playwright.async_api import async_playwright

# --- API Key for 2Captcha ---
CAPTCHA_API_KEY = "5d4de2d9ba962a796040bd90b2cac6da"

# --- قائمة الدول ---
countries = ["India", "Pakistan", "Egypt", "Bangladesh", "Philippines", "Afghanistan", "Jordan", "Syrian Arab Republic"] # اختصار للسرعة

st.set_page_config(page_title="ICP Passport Lookup", layout="wide")
st.title("🔍 ICP Passport Unified Number Lookup")

if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'single_res' not in st.session_state: st.session_state.single_res = None

# --- Login ---
if not st.session_state.authenticated:
    with st.form("login"):
        pwd = st.text_input("Password", type="password")
        if st.form_submit_button("Login") and pwd == "Bilkish":
            st.session_state.authenticated = True
            st.rerun()
    st.stop()

# --- دالة البحث الأساسية المعدلة للسيرفر ---
async def search_logic(passport_no, nationality, context):
    page = await context.new_page()
    target_url = "https://smartservices.icp.gov.ae/echannels/web/client/guest/index.html#/leavePermit/588/step1?administrativeRegionId=1&withException=false"
    try:
        await page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
        # البحث عن خيار Passport Number (رقم 4 في القائمة)
        await page.evaluate("""() => {
            const el = document.querySelector("input[value='4']");
            if (el) { el.click(); el.dispatchEvent(new Event('change', { bubbles: true })); }
        }""")
        await asyncio.sleep(1)
        await page.locator("input#passportNo").fill(passport_no)
        
        # اختيار الجنسية
        await page.locator("//label[contains(.,'Nationality')]/following::div[1]").click()
        await page.keyboard.type(nationality)
        await page.keyboard.press("Enter")
        
        # انتظار الرد من الشبكة
        async with page.expect_response("**/checkValidateLeavePermitRequest**", timeout=15000) as response_info:
            await asyncio.sleep(2) # انتظار بسيط للمعالجة
            response = await response_info.value
            if response.status == 200:
                data = await response.json()
                return str(data.get("unifiedNumber", "Not Found"))
        return "Not Found"
    except Exception as e:
        return f"Error: {str(e)[:50]}"
    finally:
        await page.close()

# --- واجهة المستخدم ---
tab1, tab2 = st.tabs(["Single Search", "Batch Processing"])

with tab1:
    p_in = st.text_input("Passport Number")
    n_in = st.selectbox("Nationality", countries)
    
    if st.button("Search"):
        async def run():
            async with async_playwright() as p:
                # إضافة --no-sandbox و --disable-setuid-sandbox ضروري جداً للينكس
                browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
                context = await browser.new_context()
                res = await search_logic(p_in, n_in, context)
                await browser.close()
                return res
        
        with st.spinner("Searching..."):
            st.session_state.single_res = asyncio.run(run())
        st.rerun()

    if st.session_state.single_res:
        st.info(f"Result: {st.session_state.single_res}")
