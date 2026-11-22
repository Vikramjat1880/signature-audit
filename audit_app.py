import streamlit as st
import pandas as pd
import requests
import re
import io
import zipfile
import pypdf
from PIL import Image
from datetime import datetime, timezone, timedelta

try:
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

# --- CONFIGURATION & SUPABASE CONNECTION ---
SUPABASE_URL = "https://gutxudaauqaegfhqpdlt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imd1dHh1ZGFhdXFhZWdmaHFwZGx0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTUzNjc1NTIsImV4cCI6MjExMDk0MzU1Mn0.M-R-dQFPBTVEfRBDBuZNBNmWUT4tKsgu3FWueHjHxYE"
IST = timezone(timedelta(hours=5, minutes=30))

st.set_page_config(
    page_title="Signature v2.0 ( by vickyy )",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

def sb_get(table, params=""):
    try:
        r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}?{params}", headers=sb_headers(), timeout=10)
        return r.json() if r.status_code == 200 else []
    except Exception:
        return []

def sb_post(table, payload):
    try:
        r = requests.post(f"{SUPABASE_URL}/rest/v1/{table}", json=payload, headers=sb_headers(), timeout=10)
        if r.status_code in (200, 201):
            return True, "OK"
        return False, f"Error {r.status_code}: {r.text}"
    except Exception as e:
        return False, str(e)

def sb_patch(table, filter_query, payload):
    try:
        r = requests.patch(f"{SUPABASE_URL}/rest/v1/{table}?{filter_query}", json=payload, headers=sb_headers(), timeout=10)
        return r.status_code in (200, 204)
    except Exception:
        return False

def log_activity(actor, branch_code, action, details=""):
    sb_post("audit_logs", {
        "actor": actor,
        "branch_code": branch_code,
        "action": action,
        "details": details[:250]
    })

def now_ist():
    return datetime.now(IST)

# --- CUSTOM ENTERPRISE UI & LIVE CLOCK ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .main-header {
        background: linear-gradient(90deg, #090d16 0%, #1e293b 100%);
        padding: 1.2rem 1.8rem;
        border-radius: 12px;
        color: #ffffff;
        margin-bottom: 1rem;
        border-left: 6px solid #38bdf8;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    .main-header h1 { margin: 0; font-size: 1.8rem; font-weight: 700; }
    .main-header p { margin: 0.3rem 0 0 0; color: #94a3b8; font-size: 0.9rem; }
    .notice-info { background:#0284c7; color:white; padding:10px 16px; border-radius:8px; font-weight:600; margin-bottom:10px; }
    .notice-warn { background:#d97706; color:white; padding:10px 16px; border-radius:8px; font-weight:600; margin-bottom:10px; }
    .notice-urgent { background:#dc2626; color:white; padding:10px 16px; border-radius:8px; font-weight:700; margin-bottom:10px; }
    .wa-float {
        position: fixed;
        bottom: 22px;
        right: 22px;
        background-color: #25d366;
        color: #ffffff !important;
        padding: 12px 20px;
        border-radius: 50px;
        font-weight: 700;
        font-size: 15px;
        text-decoration: none;
        box-shadow: 0 4px 14px rgba(0,0,0,0.35);
        z-index: 9999;
    }
    .wa-float:hover { background-color: #1ebe5d; }
    </style>
""", unsafe_allow_html=True)

# --- SESSION & ROLE-BASED AUTHENTICATION ---
if "auth_role" not in st.session_state:
    st.session_state.auth_role = None
    st.session_state.auth_user = None
    st.session_state.auth_branch = None
    st.session_state.auth_branch_name = None

if not st.session_state.auth_role:
    st.markdown("""
        <div style="max-width:440px; margin:3rem auto 1rem auto; padding:2rem; background:#0f172a; border-radius:14px; color:white; border:1px solid #334155; text-align:center;">
            <h2 style="color:#38bdf8; margin-bottom:0.2rem;">🛡️ Signature v2.0 ( by vickyy )</h2>
            <p style="color:#94a3b8; font-size:0.9rem;">Enterprise Multi-Branch Payment & Audit Control Room</p>
        </div>
    """, unsafe_allow_html=True)
    col_l, col_m, col_r = st.columns([1, 1.2, 1])
    with col_m:
        with st.form("enterprise_login"):
            uid = st.text_input("Login ID (Super Admin or Branch ID)", placeholder="e.g. Vicky9001 or branch1")
            pwd = st.text_input("Password", type="password", placeholder="Enter Password")
            if st.form_submit_button("🔐 Secure Login", use_container_width=True, type="primary"):
                u_clean, p_clean = uid.strip(), pwd.strip()
                if u_clean == "Vicky9001" and p_clean == "8890075565":
                    st.session_state.auth_role = "SUPER_ADMIN"
                    st.session_state.auth_user = "Vicky9001 (Super Admin)"
                    st.session_state.auth_branch = "ALL"
                    st.session_state.auth_branch_name = "All Branches Master View"
                    log_activity("Vicky9001", "SUPER_ADMIN", "LOGIN", "Super Admin logged in")
                    st.rerun()
                else:
                    branches = sb_get("branches", f"manager_id=eq.{u_clean}&manager_password=eq.{p_clean}")
                    if branches:
                        b = branches[0]
                        if not b.get("is_active", True):
                            st.error("🚫 Yeh Branch Super Admin dwara temporarily LOCK / BLOCK kar di gayi hai!")
                        else:
                            st.session_state.auth_role = "BRANCH_MANAGER"
                            st.session_state.auth_user = f"{b['manager_id']} ({b['branch_name']})"
                            st.session_state.auth_branch = b["branch_code"]
                            st.session_state.auth_branch_name = b["branch_name"]
                            log_activity(b["manager_id"], b["branch_code"], "LOGIN", "Branch Manager logged in")
                            st.rerun()
                    else:
                        st.error("❌ Galat ID ya Password!")
    st.stop()

# --- TOP HEADER & LIVE IST CLOCK ---
current_ist_str = now_ist().strftime("%d %b %Y | %I:%M:%S %p IST")
h1, h2 = st.columns([4.5, 1.5])
with h1:
    st.markdown(f"""
        <div class="main-header">
            <h1>🛡️ Signature v2.0 ( by vickyy )</h1>
            <p>👤 <b>{st.session_state.auth_user}</b> &nbsp;|&nbsp; 🏢 <b>{st.session_state.auth_branch_name}</b> &nbsp;|&nbsp; 🕒 <b>{current_ist_str}</b></p>
        </div>
    """, unsafe_allow_html=True)
with h2:
    st.write("")
    if st.button("🔄 Refresh Live Data", use_container_width=True):
        st.rerun()
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.auth_role = None
        st.rerun()

# --- FETCH ACTIVE BRANCHES & BROADCAST NOTICES ---
all_branches = sb_get("branches", "order=branch_code.asc")
active_branch_code = st.session_state.auth_branch

if st.session_state.auth_role == "SUPER_ADMIN":
    branch_options = {"ALL": "🌐 ALL BRANCHES (Master Consolidated View)"}
    for b in all_branches:
        status_icon = "🟢" if b.get("is_active") else "🔒"
        branch_options[b["branch_code"]] = f"{status_icon} {b['branch_code']} - {b['branch_name']}"
    selected_view = st.selectbox("🏢 Active Branch Control Selector:", options=list(branch_options.keys()), format_func=lambda x: branch_options[x])
else:
    selected_view = active_branch_code

# Display Active Admin Notices
notices = sb_get("admin_notices", "is_active=eq.true&order=created_at.desc")
for n in notices:
    if n["target_branch"] == "ALL" or n["target_branch"] == selected_view:
        css_cls = "notice-urgent" if n["notice_type"] == "URGENT" else ("notice-warn" if n["notice_type"] == "WARNING" else "notice-info")
        st.markdown(f'<div class="{css_cls}">📢 [{n["notice_type"]}] {n["message"]}</div>', unsafe_allow_html=True)

# Floating WhatsApp Support Button for Branch View
if selected_view != "ALL":
    curr_b_list = [b for b in all_branches if b["branch_code"] == selected_view]
    if curr_b_list and curr_b_list[0].get("support_enabled") and curr_b_list[0].get("whatsapp_support_number"):
        wa_num = re.sub(r'[^0-9]', '', curr_b_list[0]["whatsapp_support_number"])
        if len(wa_num) == 10:
            wa_num = "91" + wa_num
        wa_msg = f"Hello Admin, Support needed for {curr_b_list[0]['branch_name']} ({selected_view})"
        st.markdown(f'<a href="https://wa.me/{wa_num}?text={wa_msg.replace(" ", "%20")}" target="_blank" class="wa-float">💬 WhatsApp Support</a>', unsafe_allow_html=True)

# --- PARSING HELPER FUNCTIONS ---
def extract_utrs(text):
    if not text:
        return []
    matches = re.findall(r'\b[0-9]{12}\b', str(text))
    return list(set([m for m in matches if len(set(m)) > 2]))

def classify_bank_narration(desc):
    d = str(desc).upper()
    if any(k in d for k in ['CHG', 'CHARGES', 'IMPS FEE', 'NEFT CHG', 'RTGS CHG', 'SMS', 'GST', 'CONSOLIDATED', 'MIN BAL', 'ANNUAL FEE', 'TAX']):
        return "BANK CHARGES"
    if any(k in d for k in ['ATM', 'CASH WDL', 'ATW', 'NFS', 'SELF', 'CHQ PAID', 'CASH WITHDRAWAL', 'CDM']):
        return "CASH WITHDRAWAL"
    return "REGULAR"

def parse_panel_pdf(uploaded_files, panel_type):
    records = []
    for file in uploaded_files:
        reader = pypdf.PdfReader(file)
        for page in reader.pages:
            text = page.extract_text()
            for line in text.split('\n'):
                m = re.match(r'^(\d+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\d+(?:\.\d+)?)\s+(\S+)\s+([0-9a-zA-Z]+)', line.strip())
                if m:
                    utr_clean = re.sub(r'[^0-9]', '', m.group(9))[:12]
                    records.append({'Type': panel_type, 'Source_File': file.name, 'Site': m.group(3), 'Username': m.group(4), 'Amount': float(m.group(7)), 'UTR': utr_clean})
                else:
                    for u in extract_utrs(line):
                        nums = [float(x.replace(',', '')) for x in re.findall(r'\b\d{1,3}(?:,\d{3})*(?:\.\d{2})?\b', line) if len(x.replace(',','').split('.')[0]) < 9 and x != u]
                        records.append({'Type': panel_type, 'Source_File': file.name, 'Site': '-', 'Username': '-', 'Amount': nums[0] if nums else 0.0, 'UTR': u})
    if not records:
        return pd.DataFrame(columns=['Type', 'Source_File', 'Site', 'Username', 'Amount', 'UTR', 'Is_Duplicate'])
    df = pd.DataFrame(records)
    df['Is_Duplicate'] = df.duplicated(subset=['UTR'], keep=False)
    return df

def parse_bank_statements(files):
    all_txns = []
    for f in files:
        fname = f.name.lower()
        if fname.endswith(('.csv', '.xlsx', '.xls')):
            df = pd.read_csv(f) if fname.endswith('.csv') else pd.read_excel(f)
            df.columns = [str(c).strip().upper() for c in df.columns]
            desc_col = next((c for c in df.columns if any(k in c for k in ['NARRATION', 'DESCRIPTION', 'PARTICULARS', 'REMARKS', 'DETAILS'])), None)
            utr_col = next((c for c in df.columns if any(k in c for k in ['UTR', 'REF', 'REFERENCE', 'CHQ', 'TRAN ID'])), None)
            cr_col = next((c for c in df.columns if any(k in c for k in ['CREDIT', 'CR', 'DEPOSIT', 'INFLOW', 'AMOUNT'])), None)
            dr_col = next((c for c in df.columns if any(k in c for k in ['DEBIT', 'DR', 'WITHDRAWAL', 'OUTFLOW'])), None)
            date_col = next((c for c in df.columns if 'DATE' in c), None)
            for _, row in df.iterrows():
                desc_val = str(row[desc_col]) if desc_col else ""
                utr_raw = str(row[utr_col]) if utr_col else ""
                utrs = extract_utrs(f"{desc_val} {utr_raw}")
                cr_amt, dr_amt = 0.0, 0.0
                if cr_col and dr_col and cr_col != dr_col:
                    cr_amt = pd.to_numeric(str(row[cr_col]).replace(',', ''), errors='coerce') or 0.0
                    dr_amt = pd.to_numeric(str(row[dr_col]).replace(',', ''), errors='coerce') or 0.0
                elif cr_col:
                    val =
