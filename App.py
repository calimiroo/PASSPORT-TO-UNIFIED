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

# --- Core Search Engine (The version that worked for you) ---
async def search_single_passport_playwright(passport_no, nationality, target_url):
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu"])
            context = await browser.new_context(viewport={'width': 1280, 'height': 800})
            page = await context.new_page()
            page.set_default_timeout(20000)

            await page.goto(target_url, wait_until="networkidle", timeout=60000)
            
            try: await page.click("button:has-text('I Got It')", timeout=2000)
            except: pass

            await page.evaluate("""() => {
                const el = document.querySelector("input[value='4']");
                if (el) { el.click(); el.dispatchEvent(new Event('change', { bubbles: true })); }
            }""")
            
            try:
                await page.locator("//label[contains(.,'Passport Type')]/following::div[1]").click(timeout=5000)
                await page.keyboard.type("ORDINARY PASSPORT", delay=0)
                await page.keyboard.press("Enter")
            except: pass
            
            await page.locator("input#passportNo").fill(passport_no)
            
            try:
                await page.locator('div[name="currentNationality"] button[ng-if="showClear"]').click(force=True, timeout=2000)
            except: pass
            
            await page.keyboard.press("Tab")
            unified_number = "Not Found"
            
            try:
                async with page.expect_response("**/checkValidateLeavePermitRequest**", timeout=10000) as response_info:
                    await page.locator("//label[contains(.,'Nationality')]/following::div[contains(@class,'ui-select-container')][1]").click(timeout=5000)
                    await page.keyboard.type(nationality, delay=0)
                    await page.keyboard.press("Enter")
                    
                    response = await response_info.value
                    if response.status == 200:
                        json_data = await response.json()
                        raw_unified = json_data.get("unifiedNumber")
                        if raw_unified: unified_number = str(raw_unified).strip()
            except: pass
            
            await browser.close()
            return unified_number
        except Exception as e:
            logging.error(f"Error: {e}")
            return "ERROR"

# --- Batch Processing ---
async def run_batch_serial(df, url, status_area, progress_bar, table_area):
    start_time_session = time.time()
    total_records = len(df)
    records = df.to_dict('records')

    for i in range(st.session_state.current_index, total_records):
        if st.session_state.run_state != 'running':
            break

        row = records[i]
        p_num = str(row['Passport Number']).strip()
        nat = str(row['Nationality']).strip().upper()
        
        # Display Stats
        current_elapsed = st.session_state.accumulated_time + (time.time() - start_time_session)
        success_rate = (st.session_state.found_counter / (i + 1)) * 100 if (i+1) > 0 else 0
        
        status_area.markdown(f"### 🔄 Processing {i + 1}/{total_records}: **{p_num}** ({nat})\n"
                             f"**⏱️ Time:** `{format_time(current_elapsed)}` | **✅ Found:** `{st.session_state.found_counter}/{total_records}` | **📈 Rate:** `{success_rate:.1f}%`")
        
        res = await search_single_passport_playwright(p_num, nat, url)
        status_val = "Found" if res not in ["Not Found", "ERROR"] else res
        
        st.session_state.batch_results.append({
            "Passport Number": p_num, "Nationality": nat, "Unified Number": res, "Status": status_val
        })
        
        if status_val == "Found": st.session_state.found_counter += 1
        st.session_state.current_index = i + 1
        progress_bar.progress((i + 1) / total_records)

        with table_area:
            st.dataframe(pd.DataFrame(st.session_state.batch_results).style.applymap(color_status, subset=['Status']), use_container_width=True, height=300)
        
        await asyncio.sleep(0.5)

    st.session_state.accumulated_time += (time.time() - start_time_session)
    if st.session_state.current_index >= total_records:
        st.session_state.run_state = 'finished'

# --- UI Setup ---
tab1, tab2 = st.tabs(["Single Search", "Batch Processing"])

with tab1:
    st.subheader("🔍 Individual Search")
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
        st.write(f"Result: {st.session_state.single_res}")

with tab2:
    st.subheader("📊 Batch Processing Control")
    uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])
    
    if uploaded_file:
        df = pd.read_excel(uploaded_file)
        
        with st.expander("📂 Preview Uploaded File", expanded=False):
            st.dataframe(df, use_container_width=True)

        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        if c1.button("🚀 Start New Batch"):
            st.session_state.run_state, st.session_state.batch_results, st.session_state.current_index, st.session_state.found_counter, st.session_state.accumulated_time = 'running', [], 0, 0, 0.0
            st.rerun()
        
        # Pause / Resume Logic
        if st.session_state.run_state == 'running':
            if c2.button("⏸️ Pause"):
                st.session_state.run_state = 'paused'; st.rerun()
        elif st.session_state.run_state == 'paused':
            if c2.button("▶️ Resume"):
                st.session_state.run_state = 'running'; st.rerun()

        if c3.button("⏹️ Reset"):
            st.session_state.run_state = 'idle'; st.rerun()

        st.markdown("---")
        status_area = st.empty()
        progress_bar = st.progress(st.session_state.current_index / len(df) if len(df)>0 else 0)
        
        with st.expander("📋 View/Hide Live Results Table", expanded=True):
            table_area = st.empty()
            if st.session_state.batch_results:
                table_area.dataframe(pd.DataFrame(st.session_state.batch_results).style.applymap(color_status, subset=['Status']), use_container_width=True)

        if st.session_state.run_state == 'running':
            url = "https://smartservices.icp.gov.ae/echannels/web/client/guest/index.html#/leavePermit/588/step1?administrativeRegionId=1&withException=false"
            asyncio.run(run_batch_serial(df, url, status_area, progress_bar, table_area))
            if st.session_state.run_state == 'finished': st.success("Batch Processing Completed! 🎉")

        if st.session_state.batch_results:
            final_df = pd.DataFrame(st.session_state.batch_results)
            excel_buffer = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
            final_df.to_excel(excel_buffer.name, index=False)
            with open(excel_buffer.name, "rb") as f:
                st.download_button("📥 Download Results", data=f, file_name="ICP_Results.xlsx")
