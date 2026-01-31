import streamlit as st
import pandas as pd

st.set_page_config(page_title="ICP / MOHRE / DCD Lookup", layout="wide")
st.title("✅ Unified Verification Tool")

# --- Authentication ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    with st.form("login"):
        pwd = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            if pwd == "Bilkish":  # أو "Hamada" حسب ما تستخدمه
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Wrong password")
    st.stop()

# --- Main UI ---
st.subheader("🔍 Single ID Lookup")

col1, col2 = st.columns(2)
eid = col1.text_input("Emirates ID (15 digits)", max_chars=15)
passport = col2.text_input("Passport Number", max_chars=15)

if st.button("Generate Links"):
    st.success("🔗 Verification Links Ready:")
    
    if eid and len(eid) == 15 and eid.isdigit():
        st.markdown("- **MOHRE**: [Open Verification Page](https://backoffice.mohre.gov.ae/mohre.complaints.app/freezoneAnonymous2/ComplaintVerification?lang=en)")
    
    if passport:
        st.markdown("- **ICP**: [Open Passport Search](https://smartservices.icp.gov.ae/echannels/web/client/guest/index.html#/leavePermit/588/step1?administrativeRegionId=1&withException=false)")
    
    st.info("""
    ⚠️ Note:  
    These sites require **manual input** and **SMS verification**.  
    Automated scraping is blocked by security measures.  
    Use the links above to open the pages and complete the process yourself.
    """)

# --- Batch ---
st.subheader("📊 Batch Upload (Excel)")
uploaded = st.file_uploader("Upload Excel (.xlsx) with columns: 'EID' or 'Passport Number'", type=["xlsx"])
if uploaded:
    try:
        df = pd.read_excel(uploaded)
        cols = [c for c in df.columns if c.lower() in ['eid', 'passport number', 'passport']]
        if not cols:
            st.warning("No supported column found.")
        else:
            st.write(f"Found {len(df)} rows.")
            if st.button("Show Links"):
                for i, val in enumerate(df[cols[0]].dropna(), 1):
                    if len(str(val)) == 15 and str(val).isdigit():
                        st.write(f"{i}. [MOHRE - {val}](https://backoffice.mohre.gov.ae/mohre.complaints.app/freezoneAnonymous2/ComplaintVerification?lang=en)")
                    else:
                        st.write(f"{i}. [ICP - {val}](https://smartservices.icp.gov.ae/echannels/web/client/guest/index.html#/leavePermit/588/step1?administrativeRegionId=1&withException=false)")
    except Exception as e:
        st.error(f"Error: {e}")
