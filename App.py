import streamlit as st
import pandas as pd
import time
import tempfile
import os
import sys
import asyncio
import logging

# --- إعدادات النظام ---
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# --- استخدم playwright-core ---
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

# --- Session State Initialization ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

# حالة التشغيل: 'idle', 'running', 'paused', 'finished'
if 'run_state' not in st.session_state:
    st.session_state.run_state = 'idle' 

# تخزين النتائج
if 'batch_results' not in st.session_state:
    st.session_state.batch_results = []

# متغيرات التتبع (للاستئناف)
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
if 'single_res' not in st.session_state:
    st.session_state.single_res = None

# --- Login ---
if not st.session_state.authenticated:
    with st.form("login_form"):
        st.subheader("🔐 Protected Access")
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
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def reset_duplicate_trackers():
    st.session_state.passport_to_unified = {}
    st.session_state.unified_to_passport = {}

def get_unique_result(passport_no, unified_str):
    if not unified_str or unified_str == "Not Found":
        return unified_str
    if unified_str in st.session_state.unified_to_passport:
        existing_passport = st.session_state.unified_to_passport[unified_str]
        if existing_passport != passport_no:
            logging.warning(f"Duplicate Unified Number '{unified_str}' for different passport")
            return "Not Found"
    st.session_state.passport_to_unified[passport_no] = unified_str
    st.session_state.unified_to_passport[unified_str] = passport_no
    return unified_str

def color_status(val):
    if val == 'Found':
        color = '#90EE90' # Light Green
    elif val == 'Not Found':
        color = '#FFCCCB' # Light Red
    else:
        color = '#FFA500' # Orange
    return f'background-color: {color}'

async def search_single_passport_playwright(passport_no, nationality, target_url):
    async with async_playwright() as p:
        # --- إعدادات المتصفح لـ Streamlit Cloud ---
        try:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-setuid-sandbox",
                    "--single-process",
                    "--disable-background-timer-throttling",
                    "--disable-renderer-backgrounding",
                    "--disable-features=VizDisplayCompositor"
                ]
            )
        except Exception as e:
            logging.error(f"Failed to launch browser with special args: {e}")
            try:
                browser = await p.chromium.launch(headless=True)
            except Exception as e2:
                logging.error(f"Failed to launch browser even without args: {e2}")
                try:
                    import subprocess
                    subprocess.run(["playwright", "install", "chromium"], check=True)
                    browser = await p.chromium.launch(headless=True)
                except Exception as e3:
                    logging.error(f"All attempts failed: {e3}")
                    raise e 

        context = await browser.new_context(
            viewport={'width': 1366, 'height': 768},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        # تحسين السرعة: تقليل مهلة الانتظار الافتراضية
        page.set_default_timeout(30000)

        await page.goto(target_url, wait_until="networkidle", timeout=60000)
        
        # محاولة إغلاق زر "I Got It" بسرعة
        try:
            # تقليل مدة الانتظار للزر لأنه إما موجود أو لا
            await page.click("button:has-text('I Got It')", timeout=1500)
        except:
            pass
            
        # اختيار الفئة
        await page.evaluate("""() => {
            const el = document.querySelector("input[value='4']");
            if (el) { el.click(); el.dispatchEvent(new Event('change', { bubbles: true })); }
        }""")
        
        try:
            await page.locator("//label[contains(.,'Passport Type')]/following::div[1]").click(timeout=5000)
            # الكتابة بدون تأخير (delay=0) لتسريع العملية
            await page.keyboard.type("ORDINARY PASSPORT", delay=0)
            await page.keyboard.press("Enter")
        except:
            pass
            
        await page.locator("input#passportNo").fill(passport_no)
        
        try:
            await page.locator('div[name="currentNationality"] button[ng-if="showClear"]').click(force=True, timeout=2000)
        except:
            pass
            
        await page.keyboard.press("Tab")
        unified_number = "Not Found"
        
        try:
            # انتظار التحميل الشبكي
            await page.wait_for_load_state("networkidle", timeout=5000)
            
            async with page.expect_response("**/checkValidateLeavePermitRequest**", timeout=8000) as response_info:
                await page.locator("//label[contains(.,'Nationality')]/following::div[contains(@class,'ui-select-container')][1]").click(timeout=5000)
                # الكتابة بسرعة قصوى
                await page.keyboard.type(nationality, delay=0)
                await page.keyboard.press("Enter")
                
                response = await response_info.value
                if response.status == 200:
                    json_data = await response.json()
                    raw_unified = json_data.get("unifiedNumber")
                    if raw_unified:
                        unified_number = str(raw_unified).strip()
        except Exception as e:
            logging.warning(f"Search error for {passport_no}: {e}")
            
        final_result = get_unique_result(passport_no, unified_number)
        await browser.close()
        return final_result

# --- Batch Processing Function (Resume Capable) ---
async def run_batch_serial(df, url, metric_placeholder, progress_bar, status_text_area, live_table_area):
    
    start_time_session = time.time()
    total_records = len(df)
    
    start_idx = st.session_state.current_index
    records = df.to_dict('records')

    for i in range(start_idx, total_records):
        
        if st.session_state.run_state != 'running':
            break

        row = records[i]
        p_num = str(row['Passport Number']).strip()
        nat = str(row['Nationality']).strip().upper()
        
        # حساب الوقت والنسبة الحالية
        current_session_elapsed = time.time() - start_time_session
        total_elapsed = st.session_state.accumulated_time + current_session_elapsed
        success_rate = (st.session_state.found_counter / (i + 1)) * 100 if (i+1) > 0 else 0
        
        # تحديث منطقة الحالة والإحصائيات معاً
        status_text_area.markdown(f"""
        ### 🔄 Processing {i + 1}/{total_records}: **{p_num}** ({nat})
        ---
        **⏱️ Time:** `{format_time(total_elapsed)}` | **✅ Found:** `{st.session_state.found_counter}/{total_records}` | **📈 Rate:** `{success_rate:.1f}%`
        """)
        
        # تنفيذ البحث
        res = await search_single_passport_playwright(p_num, nat, url)
        status_val = "Found" if res not in ["Not Found", "ERROR"] else res if res == "ERROR" else "Not Found"
        
        result_entry = {
            "Passport Number": p_num,
            "Nationality": nat,
            "Unified Number": res,
            "Status": status_val
        }
        st.session_state.batch_results.append(result_entry)
        
        if status_val == "Found":
            st.session_state.found_counter += 1
        
        st.session_state.current_index = i + 1

        # تحديث الجدول داخل الـ Expander
        current_df = pd.DataFrame(st.session_state.batch_results)
        try:
            styled_df = current_df.style.map(color_status, subset=['Status'])
        except:
            styled_df = current_df.style.applymap(color_status, subset=['Status'])
        live_table_area.dataframe(styled_df, height=300, use_container_width=True)
        
        progress_bar.progress((i + 1) / total_records)
        
        # تسريع الانتقال للحالة التالية (تقليل الانتظار من 2 ثانية إلى 0.5)
        await asyncio.sleep(0.5)

    if st.session_state.current_index == total_records:
        st.session_state.run_state = 'finished'
        st.session_state.accumulated_time += (time.time() - start_time_session)
    else:
        st.session_state.accumulated_time += (time.time() - start_time_session)

# --- UI Layout ---
tab1, tab2 = st.tabs(["Single Search", "Upload Excel File"])

with tab1:
    st.subheader("🔍 Single Person Search")
    c1, c2 = st.columns(2)
    p_in = c1.text_input("Passport Number", key="s_p")
    n_in = c2.selectbox("Nationality", countries, key="s_n")
    if st.button("🔍 Search Now"):
        if p_in and n_in:
            with st.spinner("Searching..."):
                url = "https://smartservices.icp.gov.ae/echannels/web/client/guest/index.html#/leavePermit/588/step1?administrativeRegionId=1&withException=false"
                res = asyncio.run(search_single_passport_playwright(p_in.strip(), n_in.strip().upper(), url))
                st.session_state.single_res = res
            st.rerun()
    if st.session_state.single_res:
        if st.session_state.single_res == "Not Found":
            st.markdown("<h3 style='color:red;'>Not Found</h3>", unsafe_allow_html=True)
        elif st.session_state.single_res == "ERROR":
            st.markdown("<h3 style='color:red;'>Error</h3>", unsafe_allow_html=True)
        else:
            st.markdown(f"<h3 style='color:green;'>Found: {st.session_state.single_res}</h3>", unsafe_allow_html=True)

with tab2:
    st.subheader("📊 Batch Processing Control")
    uploaded_file = st.file_uploader("Upload Excel", type=["xlsx"])
    
    if uploaded_file:
        df = pd.read_excel(uploaded_file)
        
        if not all(col in df.columns for col in ['Passport Number', 'Nationality']):
            st.error("Excel must contain columns: 'Passport Number', 'Nationality'")
        else:
            # --- منطقة العدادات العلوية الثابتة (ملخص) ---
            metric_placeholder = st.empty()
            
            # --- أزرار التحكم ---
            st.markdown("---")
            col_btns = st.columns(4)
            
            if col_btns[0].button("🚀 Start New Batch"):
                st.session_state.run_state = 'running'
                st.session_state.batch_results = []
                st.session_state.current_index = 0
                st.session_state.found_counter = 0
                st.session_state.accumulated_time = 0.0
                reset_duplicate_trackers()
                st.rerun()

            if st.session_state.run_state == 'paused' and st.session_state.current_index < len(df):
                if col_btns[1].button("▶️ Resume"):
                    st.session_state.run_state = 'running'
                    st.rerun()

            if st.session_state.run_state == 'running':
                if col_btns[1].button("⏸️ Pause"):
                    st.session_state.run_state = 'paused'
                    st.rerun()

            if col_btns[2].button("⏹️ Stop/Reset"):
                st.session_state.run_state = 'idle'
                st.rerun()

            # --- منطقة العرض الحية (Status + Progress) ---
            st.markdown("---")
            status_text_area = st.empty() # هنا سيظهر النص والتفاصيل
            progress_bar = st.progress(0)
            
            # تحديث شريط التقدم عند التحميل
            if len(df) > 0:
                progress_bar.progress(st.session_state.current_index / len(df))

            # --- الجدول القابل للإخفاء (Expander) ---
            with st.expander("📋 View/Hide Live Results Table", expanded=False):
                live_table_area = st.empty()
                
                # عرض الجدول إذا كان هناك نتائج
                if st.session_state.batch_results:
                    current_df = pd.DataFrame(st.session_state.batch_results)
                    try:
                        styled_df = current_df.style.map(color_status, subset=['Status'])
                    except:
                        styled_df = current_df.style.applymap(color_status, subset=['Status'])
                    live_table_area.dataframe(styled_df, height=300, use_container_width=True)
                else:
                    live_table_area.info("No results yet.")

            # --- منطق التشغيل الفعلي ---
            if st.session_state.run_state == 'running':
                url = "https://smartservices.icp.gov.ae/echannels/web/client/guest/index.html#/leavePermit/588/step1?administrativeRegionId=1&withException=false"
                
                asyncio.run(run_batch_serial(
                    df, url, metric_placeholder, progress_bar, status_text_area, live_table_area
                ))
                
                if st.session_state.run_state == 'finished':
                    st.success("Batch Processing Completed! 🎉")
                    st.balloons()
                elif st.session_state.run_state == 'paused':
                    st.warning("Paused. Click 'Resume' to continue.")

            # عرض الحالة عند التوقف (Pause/Idle)
            elif st.session_state.run_state != 'running':
                 # عرض آخر حالة معروفة
                 total_elapsed = st.session_state.accumulated_time
                 total_records = len(df)
                 processed = st.session_state.current_index
                 rate = (st.session_state.found_counter / processed * 100) if processed > 0 else 0
                 
                 status_msg = "Ready to start" if st.session_state.run_state == 'idle' else "Paused" if st.session_state.run_state == 'paused' else "Finished"
                 
                 status_text_area.markdown(f"""
                 ### Status: {status_msg}
                 **⏱️ Time:** `{format_time(total_elapsed)}` | **✅ Found:** `{st.session_state.found_counter}/{total_records}` | **📈 Rate:** `{rate:.1f}%`
                 """)

            # --- التحميل ---
            if st.session_state.batch_results:
                final_df = pd.DataFrame(st.session_state.batch_results)
                excel_buffer = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
                with pd.ExcelWriter(excel_buffer.name, engine='openpyxl') as writer:
                    final_df.to_excel(writer, index=False)
                with open(excel_buffer.name, "rb") as f:
                    st.download_button(
                        "📥 Download Results Excel", 
                        data=f, 
                        file_name="ICP_Final_Results.xlsx", 
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
