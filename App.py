import streamlit as st
import pandas as pd
import time
import tempfile
import os
import sys
import asyncio
import logging

# --- إعدادات النظام لضمان التوافق مع Streamlit Cloud ---
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# --- قائمة الدول ---
countries = [
    "Afghanistan", "Albania", "Algeria", "Andorra", "Angola", "Antigua and Barbuda", "Argentina", "Armenia", "Australia", "Austria",
    "Azerbaijan", "Bahamas", "Bahrain", "Bangladesh", "Barbados", "Belarus", "Belgium", "Belize", "Benin", "Bhutan", "Bolivia",
    "Bosnia and Herzegovina", "Botswana", "Brazil", "Brunei", "Bulgaria", "Burkina Faso", "Burundi", "Cabo Verde", "Cambodia",
    "Cameroon", "Canada", "Central African Republic", "Chad", "Chile", "China", "Colombia", "Comoros", "Congo (Congo-Brazzaville)",
    "Costa Rica", "Côte d'Ivoire", "Croatia", "Cuba", "Cyprus", "Czechia (Czech Republic)", "Democratic Republic of the Congo",
    "Denmark", "Djibouti", "Dominica", "Dominican Republic", "Ecuador", "Egypt", "El Salvador", "Equatorial Guinea", "Eritrea",
    "Estonia", "Eswatini (fmr. \"Swaziland\")", "Ethiopia", "Fiji", "Finland", "France", "Gabon", "Gambia", "Georgia", "Germany",
    "Ghana", "Greece", "Grenada", "Guatemala", "Guinea", "Guinea-Bissau", "Guyana", "Haiti", "Holy See", "Honduras", "Hungary",
    "Iceland", "India", "Indonesia", "Iran", "Iraq", "Ireland", "Israel", "Italy", "Jamaica", "Japan", "Jordan", "Kazakhstan",
    "Kenya", "Kiribati", "Kuwait", "Kyrgyzstan", "Laos", "Latvia", "Lebanon", "Lesotho", "Liberia", "Libya", "Liechtenstein",
    "Lithuania", "Luxembourg", "Madagascar", "Malawi", "Malaysia", "Maldives", "Mali", "Malta", "Marshall Islands", "Mauritania",
    "Mauritius", "Mexico", "Micronesia", "Moldova", "Monaco", "Mongolia", "Montenegro", "Morocco", "Mozambique", "Myanmar (formerly Burma)",
    "Namibia", "Nauru", "Nepal", "Netherlands", "New Zealand", "Nicaragua", "Niger", "Nigeria", "North Korea", "North Macedonia",
    "Norway", "Oman", "Pakistan", "Palau", "Palestine State", "Panama", "Papua New Guinea", "Paraguay", "Peru", "Philippines",
    "Poland", "Portugal", "Qatar", "Romania", "Russia", "Rwanda", "Saint Kitts and Nevis", "Saint Lucia", "Saint Vincent and the Grenadines",
    "Samoa", "San Marino", "Sao Tome and Principe", "Saudi Arabia", "Senegal", "Serbia", "Seychelles", "Sierra Leone", "Singapore",
    "Slovakia", "Slovenia", "Solomon Islands", "Somalia", "South Africa", "South Korea", "South Sudan", "Spain", "Sri Lanka",
    "Sudan", "Suriname", "Sweden", "Switzerland", "Syrian Arab Republic", "Tajikistan", "Tanzania", "Thailand", "Timor-Leste",
    "Togo", "Tonga", "Trinidad and Tobago", "Tunisia", "Turkey", "Turkmenistan", "Tuvalu", "Uganda", "Ukraine", "United Arab Emirates",
    "United Kingdom", "United States of America", "Uruguay", "Uzbekistan", "Vanuatu", "Venezuela", "Vietnam", "Yemen", "Zambia", "Zimbabwe"
]

st.set_page_config(page_title="ICP Passport Lookup", layout="wide")
st.title("🔍 ICP Passport Unified Number Lookup")

# --- Session State ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'run_state' not in st.session_state:
    st.session_state.run_state = 'idle' 
if 'batch_results' not in st.session_state:
    st.session_state.batch_results = []
if 'current_index' not in st.session_state:
    st.session_state.current_index = 0
if 'found_counter' not in st.session_state:
    st.session_state.found_counter = 0
if 'accumulated_time' not in st.session_state:
    st.session_state.accumulated_time = 0.0
if 'passport_to_unified' not in st.session_state:
    st.session_state.passport_to_unified = {}
if 'unified_to_passport' not in st.session_state:
    st.session_state.unified_to_passport = {}

# --- Login ---
if not st.session_state.authenticated:
    with st.form("login_form"):
        pwd_input = st.text_input("Enter Password", type="password")
        if st.form_submit_button("Login"):
            if pwd_input == "Bilkish":
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect Password.")
    st.stop()

# --- Helpers ---
def format_time(seconds):
    seconds = int(seconds)
    return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"

def color_status(val):
    if val == 'Found': return 'background-color: #90EE90'
    if val == 'Not Found': return 'background-color: #FFCCCB'
    return 'background-color: #FFA500'

# --- محرك البحث المصلح ---
async def search_single_passport_playwright(passport_no, nationality, target_url):
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu"])
            context = await browser.new_context(viewport={'width': 1280, 'height': 800})
            page = await context.new_page()
            
            # زيادة مهلة الانتظار الافتراضية لتجنب الـ Timeout
            page.set_default_timeout(15000) 

            await page.goto(target_url, wait_until="domcontentloaded", timeout=40000)
            
            # إغلاق النوافذ المنبثقة إذا ظهرت
            try: await page.click("button:has-text('I Got It')", timeout=2000)
            except: pass

            # اختيار نوع البحث (انتظار حتى يصبح العنصر متاحاً)
            input_selector = "input[value='4']"
            await page.wait_for_selector(input_selector, state="visible")
            await page.click(input_selector)
            
            # تعبئة البيانات بذكاء
            try:
                # انتظار ظهور خانة نوع الجواز
                await page.wait_for_selector("//label[contains(.,'Passport Type')]", timeout=5000)
                await page.locator("//label[contains(.,'Passport Type')]/following::div[1]").click()
                await page.keyboard.type("ORDINARY PASSPORT", delay=0)
                await page.keyboard.press("Enter")
            except: pass

            # انتظار ظهور خانة رقم الجواز قبل الكتابة (حل المشكلة التي واجهتها)
            await page.wait_for_selector("input#passportNo", state="visible", timeout=5000)
            await page.fill("input#passportNo", passport_no)

            # مسح الجنسية السابقة إن وجدت
            try: await page.locator('div[name="currentNationality"] button[ng-if="showClear"]').click(timeout=1000)
            except: pass

            await page.keyboard.press("Tab")
            
            unified_number = "Not Found"
            # تنفيذ البحث ومراقبة الشبكة
            try:
                async with page.expect_response("**/checkValidateLeavePermitRequest**", timeout=10000) as response_info:
                    await page.locator("//label[contains(.,'Nationality')]/following::div[contains(@class,'ui-select-container')][1]").click()
                    await page.keyboard.type(nationality, delay=0)
                    await page.keyboard.press("Enter")
                    
                    response = await response_info.value
                    if response.status == 200:
                        data = await response.json()
                        raw_val = data.get("unifiedNumber")
                        if raw_val: unified_number = str(raw_val).strip()
            except: pass
            
            await browser.close()
            return unified_number
        except Exception as e:
            return "ERROR"

# --- Batch Processing ---
async def run_batch_serial(df, url, status_area, progress_bar, table_area):
    start_time = time.time()
    total = len(df)
    records = df.to_dict('records')

    for i in range(st.session_state.current_index, total):
        if st.session_state.run_state != 'running': break

        row = records[i]
        p_num, nat = str(row['Passport Number']).strip(), str(row['Nationality']).strip().upper()
        
        # عرض الإحصائيات
        elapsed = st.session_state.accumulated_time + (time.time() - start_time)
        rate = (st.session_state.found_counter / (i + 1)) * 100 if (i+1) > 0 else 0
        status_area.markdown(f"### 🔄 Processing {i+1}/{total}: **{p_num}**\n**⏱️ Time:** `{format_time(elapsed)}` | **✅ Found:** `{st.session_state.found_counter}` | **📈 Rate:** `{rate:.1f}%`")
        
        res = await search_single_passport_playwright(p_num, nat, url)
        status_val = "Found" if res not in ["Not Found", "ERROR"] else res
        
        st.session_state.batch_results.append({
            "Passport Number": p_num, "Nationality": nat, "Unified Number": res, "Status": status_val
        })
        
        if status_val == "Found": st.session_state.found_counter += 1
        st.session_state.current_index = i + 1
        progress_bar.progress((i + 1) / total)

        with table_area:
            st.dataframe(pd.DataFrame(st.session_state.batch_results).style.applymap(color_status, subset=['Status']), use_container_width=True, height=300)
        
        await asyncio.sleep(0.5)

    st.session_state.accumulated_time += (time.time() - start_time)
    if st.session_state.current_index >= total: st.session_state.run_state = 'finished'

# --- UI ---
tab1, tab2 = st.tabs(["Search", "Batch"])

with tab2:
    file = st.file_uploader("Upload Excel", type=["xlsx"])
    if file:
        df = pd.read_excel(file)
        with st.expander("📂 Preview File"): st.dataframe(df, use_container_width=True)

        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        if c1.button("🚀 Start"):
            st.session_state.run_state, st.session_state.current_index, st.session_state.found_counter, st.session_state.batch_results, st.session_state.accumulated_time = 'running', 0, 0, [], 0.0
            st.rerun()
        if st.session_state.run_state == 'running' and c2.button("⏸️ Pause"):
            st.session_state.run_state = 'paused'; st.rerun()
        if st.session_state.run_state == 'paused' and c2.button("▶️ Resume"):
            st.session_state.run_state = 'running'; st.rerun()
        if c3.button("⏹️ Reset"):
            st.session_state.run_state = 'idle'; st.rerun()

        status_area = st.empty()
        progress_bar = st.progress(st.session_state.current_index / len(df) if len(df)>0 else 0)
        
        with st.expander("📋 Results Table", expanded=True):
            table_area = st.empty()
            if st.session_state.batch_results:
                table_area.dataframe(pd.DataFrame(st.session_state.batch_results).style.applymap(color_status, subset=['Status']), use_container_width=True)

        if st.session_state.run_state == 'running':
            url = "https://smartservices.icp.gov.ae/echannels/web/client/guest/index.html#/leavePermit/588/step1?administrativeRegionId=1&withException=false"
            asyncio.run(run_batch_serial(df, url, status_area, progress_bar, table_area))
            if st.session_state.run_state == 'finished': st.success("Done!")

        if st.session_state.batch_results:
            st.download_button("📥 Download Excel", data=tempfile.NamedTemporaryFile(suffix='.xlsx').name, file_name="Results.xlsx")
