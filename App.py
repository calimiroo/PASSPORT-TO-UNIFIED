import streamlit as st
import pandas as pd
import time
import tempfile
import os
import sys
import asyncio
import logging

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# --- API Key for 2Captcha (اختياري) ---
CAPTCHA_API_KEY = "5d4de2d9ba962a796040bd90b2cac6da"

try:
    from twocaptcha import TwoCaptcha
    TWO_CAPTCHA_AVAILABLE = True
except ImportError:  # <--- مصلح
    TWO_CAPTCHA_AVAILABLE = False

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

# Session State
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'run_state' not in st.session_state:
    st.session_state.run_state = 'stopped'
if 'batch_results' not in st.session_state:
    st.session_state.batch_results = []
if 'start_time_ref' not in st.session_state:
    st.session_state.start_time_ref = None
if 'passport_to_unified' not in st.session_state:
    st.session_state.passport_to_unified = {}
if 'unified_to_passport' not in st.session_state:
    st.session_state.unified_to_passport = {}
if 'single_res' not in st.session_state:
    st.session_state.single_res = None

# Login
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

# Helper Functions
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
        color = '#90EE90'
    elif val == 'Not Found':
        color = '#FFCCCB'
    else:
        color = '#FFA500'
    return f'background-color: {color}'

async def search_single_passport_playwright(passport_no, nationality, target_url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1366, 'height': 768},
                                            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        page = await context.new_page()
        await page.goto(target_url, wait_until="networkidle", timeout=60000)
        try:
            await page.click("button:has-text('I Got It')", timeout=2000)
        except:
            pass
        await page.evaluate("""() => {
            const el = document.querySelector("input[value='4']");
            if (el) { el.click(); el.dispatchEvent(new Event('change', { bubbles: true })); }
        }""")
        try:
            await page.locator("//label[contains(.,'Passport Type')]/following::div[1]").click(timeout=10000)
            await page.keyboard.type("ORDINARY PASSPORT")
            await page.keyboard.press("Enter")
        except:
            pass
        await page.locator("input#passportNo").fill(passport_no)
        try:
            await page.locator('div[name="currentNationality"] button[ng-if="showClear"]').click(force=True, timeout=5000)
        except:
            pass
        await page.keyboard.press("Tab")
        unified_number = "Not Found"
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
            async with page.expect_response("**/checkValidateLeavePermitRequest**", timeout=10000) as response_info:
                await page.locator("//label[contains(.,'Nationality')]/following::div[contains(@class,'ui-select-container')][1]").click(timeout=10000)
                await page.keyboard.type(nationality, delay=50)
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

# Batch Serial with delay (لـ Streamlit Cloud)
async def run_batch_serial(df, url):
    reset_duplicate_trackers()
    results = []
    for index, row in df.iterrows():
        if st.session_state.run_state == 'stopped':
            break
        p_num = str(row['Passport Number']).strip()
        nat = str(row['Nationality']).strip().upper()
        status_text.info(f"Processing {index + 1}/{len(df)}: {p_num}")
        res = await search_single_passport_playwright(p_num, nat, url)
        status_val = "Found" if res not in ["Not Found", "ERROR"] else res if res == "ERROR" else "Not Found"
        results.append({
            "Passport Number": p_num,
            "Nationality": nat,
            "Unified Number": res,
            "Status": status_val
        })
        current_df = pd.DataFrame(results)
        styled_df = current_df.style.map(color_status, subset=['Status'])
        live_table_area.dataframe(styled_df, height=400)
        progress_bar.progress((index + 1) / len(df))
        await asyncio.sleep(10)  # delay 10 ثواني عشان ما يcrash أو يبلوك
    return results

# UI
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
    st.subheader("📊 Batch Processing")
    uploaded_file = st.file_uploader("Upload Excel (Columns: 'Passport Number', 'Nationality')", type=["xlsx"])
    if uploaded_file:
        df = pd.read_excel(uploaded_file)
        st.write(f"Total records: {len(df)}")
        st.dataframe(df.head(10))
        if not all(col in df.columns for col in ['Passport Number', 'Nationality']):
            st.error("Missing columns")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()
            live_table_area = st.empty()
            col1, col2 = st.columns(2)
            if col1.button("Start Batch"):
                st.session_state.run_state = 'running'
                with st.spinner("Running batch (serial with delay for stability)..."):
                    url = "https://smartservices.icp.gov.ae/echannels/web/client/guest/index.html#/leavePermit/588/step1?administrativeRegionId=1&withException=false"
                    results = asyncio.run(run_batch_serial(df, url))
                    st.session_state.batch_results = results
                st.success("Batch completed!")
                st.rerun()
            if col2.button("Stop"):
                st.session_state.run_state = 'stopped'
                st.rerun()
            if st.session_state.batch_results:
                current_df = pd.DataFrame(st.session_state.batch_results)
                styled_df = current_df.style.map(color_status, subset=['Status'])
                live_table_area.dataframe(styled_df, height=400)
                excel_buffer = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
                with pd.ExcelWriter(excel_buffer.name, engine='openpyxl') as writer:
                    current_df.to_excel(writer, index=False)
                with open(excel_buffer.name, "rb") as f:
                    st.download_button("Download Results", data=f, file_name="ICP_Results.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

