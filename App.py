import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta

# --------------------------- UTILS ---------------------------

def beep():
    try:
        import winsound
        winsound.Beep(1000, 300)
    except Exception:
        print("\a")

def format_time(seconds):
    seconds = int(seconds)
    return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"

# --------------------------- MOCK EXTRACTORS (Links Only) ---------------------------
# نظرًا لقيود الأمان على المواقع الحكومية، لا يمكن استخراج البيانات تلقائيًا.
# نستخدم دوال تُنشئ روابط مباشرة للمستخدم لفتحها يدويًا.

def search_icp_manual(passport_no, nationality, target_url):
    """
    دالة لعرض رابط فتح صفحة ICP.
    نظرًا لقيود الأمان، نُنشئ رابطًا مباشرًا فقط.
    """
    return {
        "Passport Number": passport_no,
        "Nationality": nationality,
        "Unified Number": "Manual Verification Required",
        "Status": "Link Generated",
        "Verification_Link": target_url
    }

def extract_mohre_single_manual(eid, headless=True, lang_force=True, wait_extra=0):
    """
    دالة لاستخراج معلومات من MOHRE.
    نظرًا لقيود الأمان، نُنشئ رابطًا مباشرًا فقط.
    """
    base_url = "https://backoffice.mohre.gov.ae/mohre.complaints.app/freezoneAnonymous2/ComplaintVerification?lang=en"
    return {
        "EID": eid,
        "FullName": "Manual Verification Required",
        "MobileNumber": "Not Available",
        "Source": "TOOL1-LINK",
        "Verification_Link": base_url
    }

def extract_dcd_single_manual(eid, headless=True, wait_extra=0):
    """
    دالة لاستخراج معلومات من DCD.
    نستخدم رابطًا وهميًا كمثال. قم بتعديله.
    """
    base_url = "https://dcdigitalservices.dubaichamber.com/?lang=en"
    return {
        "EID": eid,
        "FullName": "Manual Verification Required",
        "MobileNumber": "Not Available",
        "Email": "Not Available",
        "Source": "TOOL2-LINK",
        "Verification_Link": base_url
    }

# --------------------------- LIST OF COUNTRIES (From Original Code) ---------------------------
countries = [
    "Afghanistan", "Albania", "Algeria", "Andorra", "Angola", "Antigua and Barbuda", "Argentina", "Armenia", "Australia", "Austria",
    "Azerbaijan", "Bahamas", "Bahrain", "Bangladesh", "Barbados", "Belarus", "Belgium", "Belize", "Benin", "Bhutan", "Bolivia",
    "Bosnia and Herzegovina", "Botswana", "Brazil", "Bruni", "Bulgaria", "Burkina Faso", "Burundi", "Cabo Verde", "Cambodia",
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

# --------------------------- SESSION STATE MANAGEMENT ---------------------------

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
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
if 'run_state' not in st.session_state:
    st.session_state.run_state = 'idle'

# --------------------------- LOGIN LOGIC ---------------------------

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

# --------------------------- COLOR STYLING FOR DATAFRAME ---------------------------

def color_status(val):
    if val == 'Found': 
        return 'background-color: #90EE90'
    if val == 'Not Found': 
        return 'background-color: #FFCCCB'
    if val == 'Link Generated':
        return 'background-color: #ADD8E6'  # Light blue for manual links
    return 'background-color: #FFA500'

# --------------------------- MAIN APP UI ---------------------------

st.set_page_config(page_title="Unified Verification Tool - Manual", layout="wide")
st.title("🔍 Unified Verification Tool (Manual)")

# --- Tabs for ICP and MOHRE/DCD ---
tab1, tab2 = st.tabs(["ICP Passport Lookup", "MOHRE/DCD EID Lookup"])

# --- ICP Tab ---
with tab1:
    st.subheader("🔍 ICP Passport Unified Number Lookup")
    c1, c2 = st.columns(2)
    p_in = c1.text_input("Passport Number", key="single_p")
    n_in = c2.selectbox("Nationality", countries, key="single_n")
    
    if st.button("🔍 Generate ICP Link"):
        if p_in and n_in:
            with st.spinner("Preparing link..."):
                target_url = "https://smartservices.icp.gov.ae/echannels/web/client/guest/index.html#/leavePermit/588/step1?administrativeRegionId=1&withException=false"
                res = search_icp_manual(p_in.strip(), n_in.strip().upper(), target_url)
                
                st.success(f"✅ Link Generated Successfully")
                st.link_button("🌐 Open ICP Verification Page", target_url, type="primary")
                
                st.info("""
                📌 **Important Notes for ICP:**
                - The site requires **manual input** of Passport Number and Nationality.
                - **Automatic extraction is not possible** due to security measures.
                - Use the link above to open the page and complete the process manually.
                """)
        else:
            st.warning("Please enter both Passport Number and Nationality.")

    # --- ICP Batch ---
    st.subheader("📊 ICP Excel Batch Processing (Links Only)")
    uploaded_icp = st.file_uploader("Upload Excel File for ICP (Columns: 'Passport Number', 'Nationality')", type=["xlsx"], key="icp_upload")
    
    if uploaded_icp:
        try:
            df_icp = pd.read_excel(uploaded_icp)
            required_cols = ['Passport Number', 'Nationality']
            if not all(col in df_icp.columns for col in required_cols):
                st.error(f"Excel file must contain columns: {required_cols}")
                st.stop()
            
            records_icp = df_icp[required_cols].dropna().to_dict('records')
            st.write(f"Found {len(records_icp)} records in the ICP file.")
            
            if st.button("Generate All ICP Links", key="gen_icp"):
                st.success("🔗 Generated ICP Links:")
                for i, record in enumerate(records_icp, 1):
                    passport_no = str(record['Passport Number']).strip()
                    nationality = str(record['Nationality']).strip().upper()
                    st.write(f"{i}. [Open ICP for {passport_no} ({nationality})](https://smartservices.icp.gov.ae/echannels/web/client/guest/index.html#/leavePermit/588/step1?administrativeRegionId=1&withException=false)")
                    
        except Exception as e:
            st.error(f"Error reading ICP file: {e}")

# --- MOHRE/DCD Tab ---
with tab2:
    st.subheader("🔍 MOHRE/DCD Emirates ID Lookup")
    c1_m, c2_m = st.columns([2,1])
    eid_input = c1_m.text_input('Enter Emirates ID (only digits)')
    extractor_mode = c2_m.selectbox(
        'Extractor Mode',
        ['Both (TOOL1 + TOOL2)', 'TOOL1 only', 'TOOL2 only'],
        index=1  # TOOL1 only default
    )

    if c2_m.button('Get Links'):
        if not eid_input or not str(eid_input).strip():
            st.warning('Enter a valid Emirates ID')
        else:
            with st.spinner('Generating links...'):
                start = time.time()
                results = []
                if extractor_mode in ['Both (TOOL1 + TOOL2)', 'TOOL1 only']:
                    res1 = extract_mohre_single_manual(str(eid_input).strip())
                    results.append(res1)
                if extractor_mode in ['Both (TOOL1 + TOOL2)', 'TOOL2 only']:
                    res2 = extract_dcd_single_manual(str(eid_input).strip())
                    results.append(res2)
                
                if not results:
                    st.error('No links generated.')
                else:
                    df = pd.DataFrame(results)
                    st.write('Verification Links:')
                    for _, row in df.iterrows():
                        st.write(f"**{row['Source']} Link:**")
                        st.link_button("🔗 Open Verification Page", row['Verification_Link'], type="secondary")
                    
                    st.dataframe(df)
                    st.success(f'Links ready in {int(time.time()-start)}s')

    # --- MOHRE/DCD Batch ---
    st.subheader("📊 MOHRE/DCD Excel Batch Upload")
    uploaded_mohre = st.file_uploader('Upload .xlsx or .csv file for MOHRE/DCD', type=['xlsx', 'csv'], key="mohre_upload")

    if uploaded_mohre:
        try:
            if uploaded_mohre.name.lower().endswith('.csv'):
                df_in = pd.read_csv(uploaded_mohre, dtype=str)
            else:
                df_in = pd.read_excel(uploaded_mohre, dtype=str)

            possible_cols = [c for c in df_in.columns if c.lower() in ['eid', 'emirates id', 'emiratesid', 'id']]
            if not possible_cols:
                st.warning("Couldn't find an EID column automatically. Please map the column below.")
                col_map = st.selectbox('Map EID column', options=['--select--'] + list(df_in.columns.tolist()), key="mohre_col_map")
                if col_map and col_map != '--select--':
                    eid_series = df_in[col_map].astype(str).str.strip()
                else:
                    st.stop()
            else:
                eid_series = df_in[possible_cols[0]].astype(str).str.strip()

            eids = eid_series.dropna().unique().tolist()
            st.write(f'Total unique EIDs: {len(eids)}')

            if st.button("Generate All MOHRE/DCD Links", key="gen_mohre"):
                st.success("🔗 Generated MOHRE/DCD Links:")
                for i, eid in enumerate(eids, 1):
                    if len(eid) == 15 and eid.isdigit():
                        st.write(f"{i}. [MOHRE - {eid}](https://backoffice.mohre.gov.ae/mohre.complaints.app/freezoneAnonymous2/ComplaintVerification?lang=en)")
                        st.write(f"{i}. [DCD - {eid}](https://dcdigitalservices.dubaichamber.com/?lang=en)")
                    else:
                        st.write(f"{i}. ❌ Invalid EID: `{eid}`")
                        
        except Exception as e:
            st.error(f'Error reading file: {e}')
