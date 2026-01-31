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

def search_single_passport_manual(passport_no, nationality, target_url):
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

# --------------------------- LIST OF COUNTRIES ---------------------------
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

# --------------------------- STREAMLIT APP ---------------------------

st.set_page_config(page_title="ICP Passport Lookup - Manual", layout="wide")
st.title("🔍 ICP Passport Unified Number Lookup (Manual)")

# --- Session State Management ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'batch_results' not in st.session_state:
    st.session_state.batch_results = []

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

# --- UI Interface ---
tab1, tab2 = st.tabs(["Individual Search", "Batch Processing"])

target_url = "https://smartservices.icp.gov.ae/echannels/web/client/guest/index.html#/leavePermit/588/step1?administrativeRegionId=1&withException=false"

with tab1:
    st.subheader("🔍 Single Passport Lookup")
    c1, c2 = st.columns(2)
    p_in = c1.text_input("Passport Number", key="single_p")
    n_in = c2.selectbox("Nationality", countries, key="single_n")
    if st.button("🔍 Open ICP Page"):
        if p_in and n_in:
            with st.spinner("Preparing link..."):
                res = search_single_passport_manual(p_in.strip(), n_in.strip().upper(), target_url)
                
                st.success(f"✅ Link Generated Successfully")
                st.link_button("🌐 Open ICP Verification Page", target_url, type="primary")
                
                st.info("""
                📌 **Important Notes:**
                - The site requires **manual input** of Passport Number and Nationality.
                - **Automatic extraction is not possible** due to security measures.
                - Use the link above to open the page and complete the process manually.
                """)
        else:
            st.warning("Please enter both Passport Number and Nationality.")

with tab2:
    st.subheader("📊 Excel Batch Processing (Links Only)")
    uploaded_file = st.file_uploader("Upload Excel File (Columns: 'Passport Number', 'Nationality')", type=["xlsx"])
    
    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)
            required_cols = ['Passport Number', 'Nationality']
            if not all(col in df.columns for col in required_cols):
                st.error(f"Excel file must contain columns: {required_cols}")
                st.stop()
            
            records = df[required_cols].dropna().to_dict('records')
            st.write(f"Found {len(records)} records in the file.")
            
            if st.button("Generate All ICP Links"):
                st.success("🔗 Generated Links:")
                for i, record in enumerate(records, 1):
                    passport_no = str(record['Passport Number']).strip()
                    nationality = str(record['Nationality']).strip().upper()
                    st.write(f"{i}. [Open ICP for {passport_no} ({nationality})]({target_url})")
                    
        except Exception as e:
            st.error(f"Error reading file: {e}")
