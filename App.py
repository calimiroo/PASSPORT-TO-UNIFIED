import streamlit as st
import pandas as pd
import time
import tempfile
import os
import sys
import asyncio
import logging

# --- إعدادات النظام لضمان التوافق ---
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

# --- Session State Management ---
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
if 'single_res' not in st.session_state:
    st.session_state.single_res = None

# --- Login Logic ---
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

# --- Helper Functions ---
def format_time(seconds):
    seconds = int(seconds)
    return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"

def color_status(val):
    if val == 'Found': return 'background-color: #90EE90'
    if val == 'Not Found': return 'background-color: #FFCCCB'
    return 'background-color: #FFA500'

# --- الدالة الأساسية (محرك البحث المستقر جداً بدون أي محاولات تسريع) ---
async def search_single_passport_playwright(passport_no, nationality, target_url):
    async with async_playwright() as p:
        # تشغيل المتصفح بإعدادات كاملة لضمان عمل كافة نصوص الموقع
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu"])
        try:
            context = await browser.new_context(
                viewport={'width': 1366, 'height': 768},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            # الانتظار حتى سكون الشبكة تماماً (مهم جداً لموقع ICP)
            await page.goto(target_url, wait_until="networkidle", timeout=60000)
            
            # إغلاق النوافذ المنبثقة إذا ظهرت
            try: await page.click("button:has-text('I Got It')", timeout=5000)
            except: pass

            # 1. اختيار الفئة 4 (File Type)
            await page.wait_for_selector("input[value='4']", state="visible")
            await page.click("input[value='4']")
            
            # 2. نوع الجواز (تأخير بسيط لمحاكاة الكتابة البشرية)
            try:
                await page.locator("//label[contains(.,'Passport Type')]/following::div[1]").click()
                await page.keyboard.type("ORDINARY PASSPORT", delay=100)
                await page.keyboard.press("Enter")
            except: pass
            
            # 3. إدخال رقم الجواز
            await page.fill("input#passportNo", passport_no)
            
            # 4. تصفير الجنسية السابقة
            try:
                await page.locator('div[name="currentNationality"] button[ng-if="showClear"]').click(force=True, timeout=3000)
            except: pass
            
            await page.keyboard.press("Tab")
            unified_number = "Not Found"
            
            # 5. خطة استخراج النتيجة عبر مراقبة استجابة الـ API (الخطة الأصلية)
            try:
                # نراقب الاستجابة قبل أن نضغط Enter على الجنسية
                async with page.expect_response("**/checkValidateLeavePermitRequest**", timeout=20000) as response_info:
                    await page.locator("//label[contains(.,'Nationality')]/following::div[contains(@class,'ui-select-container')][1]").click()
                    await page.keyboard.type(nationality, delay=100)
                    await page.keyboard.press("Enter")
                    
                    response = await response_info.value
                    if response.status == 200:
                        json_data = await response.json()
                        raw_unified = json_data.get("unifiedNumber")
                        if raw_unified:
                            unified_number = str(raw_unified).strip()
            except: pass
            
            await browser.close()
            return unified_number
        except Exception:
            await browser.close()
            return "ERROR"

# --- Batch Processing Function ---
async def run_batch_serial(df, url, status_area, progress_bar, table_area):
    start_session_time = time.time()
    total_records = len(df)
    records = df.to_dict('records')

    for i in range(st.session_state.current_index, total_records):
        if st.session_state.run_state != 'running':
            break

        row = records[i]
        p_num = str(row['Passport Number']).strip()
        nat = str(row['Nationality']).strip().upper()
        
        # تنفيذ البحث
        res = await search_single_passport_playwright(p_num, nat, url)
        status_val = "Found" if res not in ["Not Found", "ERROR"] else res
        
        # تحديث عداد النتائج
        if status_val == "Found":
            st.session_state.found_counter += 1
        
        # تخزين النتيجة
        st.session_state.batch_results.append({
            "Passport Number": p_num,
            "Nationality": nat,
            "Unified Number": res,
            "Status": status_val
        })
        
        st.session_state.current_index = i + 1
        
        # حساب الإحصائيات (بالتنسيق المطلوب)
        elapsed_now = st.session_state.accumulated_time + (time.time() - start_session_time)
        success_rate = (st.session_state.found_counter / st.session_state.current_index) * 100
        
        # عرض الإحصائيات مدمجة في سطر واحد
        status_area.markdown(f"""
        ### 🔄 Processing {st.session_state.current_index}/{total_records}: **{p_num}** ({nat})
        **⏱️ Time Elapsed:** `{format_time(elapsed_now)}` | **✅ Found / Total:** `{st.session_state.found_counter}/{total_records}` | **📈 Success Rate:** `{success_rate:.1f}%`
        """)
        
        progress_bar.progress(st.session_state.current_index / total_records)

        # تحديث جدول النتائج داخل القائمة المنسدلة
        with table_area:
            current_results_df = pd.DataFrame(st.session_state.batch_results)
            st.dataframe(current_results_df.style.applymap(color_status, subset=['Status']), use_container_width=True, height=300)
        
        # انتظار بسيط بين الطلبات لراحة الخادم
        await asyncio.sleep(1)

    st.session_state.accumulated_time += (time.time() - start_session_time)
    if st.session_state.current_index >= total_records:
        st.session_state.run_state = 'finished'

# --- UI Interface ---
tab1, tab2 = st.tabs(["Individual Search", "Batch Processing"])

with tab1:
    st.subheader("🔍 Single Passport Lookup")
    c1, c2 = st.columns(2)
    p_in = c1.text_input("Passport Number", key="single_p")
    n_in = c2.selectbox("Nationality", countries, key="single_n")
    if st.button("🔍 Search Individual"):
        if p_in and n_in:
            with st.spinner("Searching..."):
                target = "https://smartservices.icp.gov.ae/echannels/web/client/guest/index.html#/leavePermit/588/step1?administrativeRegionId=1&withException=false"
                res = asyncio.run(search_single_passport_playwright(p_in.strip(), n_in.strip().upper(), target))
                st.session_state.single_res = res
            st.rerun()
    if st.session_state.single_res:
        if st.session_state.single_res in ["Not Found", "ERROR"]:
            st.error(f"Status: {st.session_state.single_res}")
        else:
            st.success(f"Unified Number Found: {st.session_state.single_res}")

with tab2:
    st.subheader("📊 Excel Batch Processing")
    uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])
    
    if uploaded_file:
        df = pd.read_excel(uploaded_file)
        
        # 1. جدول معاينة الملف المرفوع (مخفي ومنسدل افتراضياً)
        with st.expander("📂 Preview Uploaded File Data (Click to expand)", expanded=False):
            st.dataframe(df, use_container_width=True)

        st.markdown("---")
        # أزرار التحكم في التشغيل
        col_start, col_pause, col_reset = st.columns(3)
        
        if col_start.button("🚀 Start New Batch"):
            st.session_state.run_state = 'running'
            st.session_state.batch_results = []
            st.session_state.current_index = 0
            st.session_state.found_counter = 0
            st.session_state.accumulated_time = 0.0
            st.rerun()

        if st.session_state.run_state == 'running':
            if col_pause.button("⏸️ Pause Processing"):
                st.session_state.run_state = 'paused'
                st.rerun()
        elif st.session_state.run_state == 'paused':
            if col_pause.button("▶️ Resume Processing"):
                st.session_state.run_state = 'running'
                st.rerun()

        if col_reset.button("⏹️ Stop & Reset"):
            st.session_state.run_state = 'idle'
            st.rerun()

        st.markdown("---")
        # منطقة الإحصائيات المدمجة
        status_area = st.empty()
        progress_bar = st.progress(st.session_state.current_index / len(df) if len(df) > 0 else 0)
        
        # 2. جدول النتائج الحية (مخفي ومنسدل افتراضياً)
        with st.expander("📋 View Live Search Results (Click to expand)", expanded=False):
            table_area = st.empty()
            if st.session_state.batch_results:
                res_df = pd.DataFrame(st.session_state.batch_results)
                table_area.dataframe(res_df.style.applymap(color_status, subset=['Status']), use_container_width=True)

        # منطق المعالجة الفعلي
        if st.session_state.run_state == 'running':
            target_url = "https://smartservices.icp.gov.ae/echannels/web/client/guest/index.html#/leavePermit/588/step1?administrativeRegionId=1&withException=false"
            asyncio.run(run_batch_serial(df, target_url, status_area, progress_bar, table_area))
            
            if st.session_state.run_state == 'finished':
                st.success("Batch Processing Finished! 🎉")
                st.balloons()
        
        elif st.session_state.run_state != 'running':
            # عرض الحالة الحالية عند التوقف أو النهاية
            msg = "Ready" if st.session_state.run_state == 'idle' else "Paused" if st.session_state.run_state == 'paused' else "Completed"
            curr_rate = (st.session_state.found_counter / st.session_state.current_index * 100) if st.session_state.current_index > 0 else 0
            status_area.markdown(f"### Status: {msg}\n**⏱️ Time Elapsed:** `{format_time(st.session_state.accumulated_time)}` | **✅ Found / Total:** `{st.session_state.found_counter}/{len(df)}` | **📈 Success Rate:** `{curr_rate:.1f}%` ")

        # زر تحميل ملف النتائج النهائي
        if st.session_state.batch_results:
            final_df = pd.DataFrame(st.session_state.batch_results)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
                final_df.to_excel(tmp.name, index=False)
                with open(tmp.name, "rb") as f:
                    st.download_button("📥 Download Final Results Excel", data=f, file_name="ICP_Search_Results.xlsx")
