import streamlit as st
import pandas as pd
import time
import tempfile
import os
import sys
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# --- API Key for 2Captcha ---
CAPTCHA_API_KEY = "5d4de2d9ba962a796040bd90b2cac6da"

# --- مكتبة 2Captcha ---
try:
    from twocaptcha import TwoCaptcha
    TWO_CAPTCHA_AVAILABLE = True
except ImportError:
    TWO_CAPTCHA_AVAILABLE = False
    logging.warning("twocaptcha not installed. CAPTCHA solving will be skipped.")

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

logging.basicConfig(level=logging.INFO)

st.set_page_config(page_title="ICP Passport Lookup", layout="wide")
st.title("🔍 ICP Passport Unified Number Lookup")

# --- Session State Management ---
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'batch_results' not in st.session_state: st.session_state.batch_results = []
if 'passport_to_unified' not in st.session_state: st.session_state.passport_to_unified = {}
if 'unified_to_passport' not in st.session_state: st.session_state.unified_to_passport = {}
if 'single_res' not in st.session_state: st.session_state.single_res = None
if 'concurrency_level' not in st.session_state: st.session_state.concurrency_level = 5

# --- Login ---
if not st.session_state.authenticated:
    with st.form("login_form"):
        pwd_input = st.text_input("Enter Password", type="password")
        if st.form_submit_button("Login"):
            if pwd_input == "Bilkish":
                st.session_state.authenticated = True
                st.rerun()
            else: st.error("Incorrect Password.")
    st.stop()

# --- Helper Functions ---
def format_time(seconds):
    return str(pd.Timedelta(seconds=int(seconds)))

def reset_duplicate_trackers():
    st.session_state.passport_to_unified = {}
    st.session_state.unified_to_passport = {}

def get_unique_result(passport_no, unified_str):
    if not unified_str or unified_str == "Not Found": return unified_str
    if unified_str in st.session_state.unified_to_passport:
        existing_passport = st.session_state.unified_to_passport[unified_str]
        if existing_passport != passport_no: return "Not Found"
    st.session_state.passport_to_unified[passport_no] = unified_str
    st.session_state.unified_to_passport[unified_str] = passport_no
    return unified_str

def color_status(val):
    if val == 'Found': color = '#90EE90'
    elif val == 'Not Found': color = '#FFCCCB'
    else: color = '#FFA500'
    return f'background-color: {color}'

async def solve_captcha(page):
    if not TWO_CAPTCHA_AVAILABLE: return False
    solver = TwoCaptcha(CAPTCHA_API_KEY)
    try:
        if await page.locator("div.g-recaptcha").is_visible(timeout=5000):
            sitekey = await page.locator("div.g-recaptcha").get_attribute("data-sitekey", timeout=5000)
            result = solver.recaptcha(sitekey=sitekey, url=page.url)
            await page.evaluate(f'document.getElementById("g-recaptcha-response").value = "{result["code"]}";')
            return True
    except: pass
    return False

async def search_single_passport_playwright(passport_no, nationality, target_url, context):
    page = await context.new_page()
    try:
        await page.goto(target_url, wait_until="networkidle", timeout=60000)
        await solve_captcha(page)
        try: await page.click("button:has-text('I Got It')", timeout=2000)
        except: pass
        await page.evaluate("""() => {
            const el = document.querySelector("input[value='4']");
            if (el) { el.click(); el.dispatchEvent(new Event('change', { bubbles: true })); }
        }""")
        try:
            await page.locator("//label[contains(.,'Passport Type')]/following::div[1]").click(timeout=10000)
            await page.keyboard.type("ORDINARY PASSPORT")
            await page.keyboard.press("Enter")
        except: pass
        await page.locator("input#passportNo").fill(passport_no)
        try: await page.locator('div[name="currentNationality"] button[ng-if="showClear"]').click(force=True, timeout=5000)
        except: pass
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
                    if raw_unified: unified_number = str(raw_unified).strip()
        except: pass
        final_result = get_unique_result(passport_no, unified_number)
        await page.close()
        return final_result
    except:
        await page.close()
        return "ERROR"

# --- UI Tabs ---
tab1, tab2 = st.tabs(["Single Search", "Upload Excel File"])

with tab1:
    st.subheader("🔍 Single Person Search")
    c1, c2 = st.columns(2)
    p_in = c1.text_input("Passport Number", key="s_p")
    n_in = c2.selectbox("Nationality (Country Name)", countries, key="s_n")

    if st.button("🔍 Search Now"):
        if p_in and n_in:
            with st.spinner("Searching..."):
                async def run_single():
                    async with async_playwright() as p:
                        browser = await p.chromium.launch(headless=True)
                        context = await browser.new_context()
                        url = "https://smartservices.icp.gov.ae/echannels/web/client/guest/index.html#/leavePermit/588/step1?administrativeRegionId=1&withException=false"
                        res = await search_single_passport_playwright(p_in.strip(), n_in.strip().upper(), url, context)
                        await browser.close()
                        return res
                st.session_state.single_res = asyncio.run(run_single())
            st.rerun()

    if st.session_state.single_res:
        res = st.session_state.single_res
        st.subheader("Result:")
        if res == "Not Found": st.error("Not Found")
        elif res == "ERROR": st.warning("Error Occurred")
        else: st.success(f"Found Unified Number: {res}")

with tab2:
    st.subheader("📊 Batch Processing")
    uploaded_file = st.file_uploader("Upload Excel", type=["xlsx"])
    if uploaded_file:
        df = pd.read_excel(uploaded_file)
        st.write(f"Total records: {len(df)}")
        concurrency = st.slider("Concurrency Level", 1, 10, st.session_state.concurrency_level)
        
        if st.button("🚀 Start Batch Search"):
            reset_duplicate_trackers()
            progress_bar = st.progress(0)
            stats_area = st.empty()
            live_table_area = st.empty()
            start_time = time.time()
            
            async def run_batch():
                results = [None] * len(df)
                completed, found = 0, 0
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    context = await browser.new_context()
                    semaphore = asyncio.Semaphore(concurrency)
                    url = "https://smartservices.icp.gov.ae/echannels/web/client/guest/index.html#/leavePermit/588/step1?administrativeRegionId=1&withException=false"
                    
                    async def worker(index, row):
                        nonlocal completed, found
                        async with semaphore:
                            p_num = str(row['Passport Number']).strip()
                            nat = str(row['Nationality']).strip().upper()
                            res = await search_single_passport_playwright(p_num, nat, url, context)
                            status = "Found" if res not in ["Not Found", "ERROR"] else res
                            if status == "Found": found += 1
                            results[index] = {"Passport Number": p_num, "Nationality": nat, "Unified Number": res, "Status": status}
                            completed += 1
                            progress_bar.progress(completed/len(df))
                            stats_area.markdown(f"**Completed:** {completed}/{len(df)} | **Found:** {found} | **Time:** {format_time(time.time()-start_time)}")
                            live_table_area.dataframe(pd.DataFrame([r for r in results if r]).style.map(color_status, subset=['Status']), use_container_width=True)

                    await asyncio.gather(*[worker(i, row) for i, row in df.iterrows()])
                    await browser.close()
                return results

            st.session_state.batch_results = asyncio.run(run_batch())
            st.success("Batch Completed!")

        if st.session_state.batch_results:
            final_df = pd.DataFrame(st.session_state.batch_results)
            st.download_button("📥 Download Results (CSV)", final_df.to_csv(index=False), "Results.csv")

# --- Sidebar ---
st.sidebar.markdown("""
### 🚨 Important!
If you see browser errors, run:
```bash
playwright install chromium
