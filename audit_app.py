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
                    val = pd.to_numeric(str(row[cr_col]).replace(',', ''), errors='coerce') or 0.0
                    cr_amt = val if val >= 0 else 0.0
                    dr_amt = abs(val) if val < 0 else 0.0
                if cr_amt == 0 and dr_amt == 0:
                    continue
                cat = classify_bank_narration(desc_val) if dr_amt > 0 else "DEPOSIT / INFLOW"
                all_txns.append({'Bank_Account': f.name, 'Date': str(row[date_col]) if date_col else "-", 'UTR': utrs[0] if utrs else "NO_UTR", 'Credit_Inflow': cr_amt, 'Debit_Outflow': dr_amt, 'Category': cat, 'Narration': desc_val[:120]})
        elif fname.endswith('.pdf'):
            reader = pypdf.PdfReader(f)
            for page in reader.pages:
                for line in page.extract_text().split('\n'):
                    utrs = extract_utrs(line)
                    if utrs:
                        nums = [float(x.replace(',', '')) for x in re.findall(r'\b\d{1,3}(?:,\d{3})*(?:\.\d{2})?\b', line) if len(x.replace(',','').split('.')[0]) < 9 and x != utrs[0]]
                        amt = nums[0] if nums else 0.0
                        all_txns.append({'Bank_Account': f.name, 'Date': '-', 'UTR': utrs[0], 'Credit_Inflow': amt, 'Debit_Outflow': amt, 'Category': classify_bank_narration(line), 'Narration': line.strip()[:120]})
    return pd.DataFrame(all_txns) if all_txns else pd.DataFrame(columns=['Bank_Account', 'Date', 'UTR', 'Credit_Inflow', 'Debit_Outflow', 'Category', 'Narration'])

# --- MAIN NAVIGATION TABS ---
main_tabs = [
    "⚡ 1. Live Time-Range Audit & Watchdog",
    "📂 2. Bulk 3-Way File Audit (PDF/Excel/ZIP)",
    "🔍 3. Global UTR Radar & Master Search",
    "📱 4. Live Devices & QR Limit Monitor"
]
if st.session_state.auth_role == "SUPER_ADMIN":
    main_tabs.append("👑 5. Super Admin Control Center")

tabs = st.tabs(main_tabs)

# ==========================================
# TAB 1: LIVE TIME-RANGE AUDIT & 5M/12H WATCHDOG
# ==========================================
with tabs[0]:
    st.subheader("⏱️ Live Database Time-Range Audit & Missing Debit Watchdog")
    
    t_col1, t_col2, t_col3, t_col4 = st.columns(4)
    today_date = now_ist().date()
    start_d = t_col1.date_input("Start Date", value=today_date)
    start_t = t_col2.time_input("Start Time", value=datetime.strptime("00:00", "%H:%M").time())
    end_d = t_col3.date_input("End Date", value=today_date)
    end_t = t_col4.time_input("End Time", value=datetime.strptime("23:59", "%H:%M").time())

    start_dt_str = datetime.combine(start_d, start_t, tzinfo=IST).isoformat()
    end_dt_str = datetime.combine(end_d, end_t, tzinfo=IST).isoformat()

    query_filter = f"txn_timestamp=gte.{start_dt_str}&txn_timestamp=lte.{end_dt_str}&order=txn_timestamp.desc"
    if selected_view != "ALL":
        query_filter += f"&branch_code=eq.{selected_view}"

    live_txns = sb_get("live_transactions", query_filter)
    df_live = pd.DataFrame(live_txns) if live_txns else pd.DataFrame(columns=['id', 'branch_code', 'source_channel', 'device_code', 'utr', 'amount', 'sender_or_user', 'raw_narration', 'txn_timestamp', 'is_resolved'])

    all_recent_txns = sb_get("live_transactions", "order=txn_timestamp.desc&limit=2000")
    df_all_recent = pd.DataFrame(all_recent_txns) if all_recent_txns else pd.DataFrame()
    
    alerts_5m = []
    alerts_12h = []
    if not df_all_recent.empty:
        if selected_view != "ALL":
            df_all_recent = df_all_recent[df_all_recent['branch_code'] == selected_view]
        wa_matched_utrs = set(df_all_recent[df_all_recent['source_channel'].isin(['WA_GROUP_1', 'WA_GROUP_2'])]['utr'])
        bank_debits = df_all_recent[(df_all_recent['source_channel'] == 'PHONE_BANK_DR') & (df_all_recent['is_resolved'] == False)]
        
        curr_utc = datetime.now(timezone.utc)
        for _, dr in bank_debits.iterrows():
            if dr['utr'] not in wa_matched_utrs:
                try:
                    t_ts = datetime.fromisoformat(dr['txn_timestamp'].replace('Z', '+00:00'))
                    mins_passed = (curr_utc - t_ts).total_seconds() / 60.0
                    if mins_passed >= 720:
                        alerts_12h.append(dr)
                    elif mins_passed >= 5:
                        alerts_5m.append(dr)
                except Exception:
                    pass

    w1, w2, w3, w4 = st.columns(4)
    w1.metric("🚨 12-Hour Escalation Alerts", len(alerts_12h))
    w2.metric("⚠️ 5-Min Missing Slip Alerts", len(alerts_5m))
    w3.metric("📥 Live Bank Credits (In Range)", len(df_live[df_live['source_channel'] == 'PHONE_BANK_CR']) if not df_live.empty else 0)
    w4.metric("📤 Live Bank Debits (In Range)", len(df_live[df_live['source_channel'] == 'PHONE_BANK_DR']) if not df_live.empty else 0)

    if alerts_12h:
        st.error(f"⏰ **12-HOUR UNRESOLVED ESCALATION ({len(alerts_12h)} Entries):** Yeh bank debits 12 ghante se kisi bhi WhatsApp group mein nahi mile!")
        st.dataframe(pd.DataFrame(alerts_12h)[['branch_code', 'device_code', 'utr', 'amount', 'txn_timestamp', 'raw_narration']], use_container_width=True)
    if alerts_5m:
        st.warning(f"🚨 **5-MINUTE MISSING SLIP ALERT ({len(alerts_5m)} Entries):** Bank se paisa kate 5+ minute ho gaye par Group 1 ya Group 2 mein slip nahi aayi!")
        st.dataframe(pd.DataFrame(alerts_5m)[['branch_code', 'device_code', 'utr', 'amount', 'txn_timestamp', 'raw_narration']], use_container_width=True)

    st.markdown("### 📋 Live Captured Entries (Selected Time Window)")
    if df_live.empty:
        st.info("Is time window mein abhi koi live entry database mein nahi aayi hai. Neeche Manual Quick-Test ya Bulk File Upload ka upyog karein.")
    else:
        st.dataframe(df_live[['branch_code', 'source_channel', 'device_code', 'utr', 'amount', 'sender_or_user', 'txn_timestamp', 'raw_narration']], use_container_width=True)

# ==========================================
# TAB 2: BULK 3-WAY FILE AUDIT (1000 MB SUPPORT)
# ==========================================
with tabs[1]:
    st.subheader("📂 Bulk 3-Way File Audit & Database Sync (Up to 1000 MB)")
    c1, c2, c3 = st.columns(3)
    with c1:
        p_dep_files = st.file_uploader("1A. Panel DEPOSIT PDF(s)", type=['pdf'], accept_multiple_files=True, key="b_dep")
        p_wdl_files = st.file_uploader("1B. Panel WITHDRAWAL PDF(s)", type=['pdf'], accept_multiple_files=True, key="b_wdl")
    with c2:
        bank_files = st.file_uploader("2. Bank & GPay QR Statements", type=['xlsx', 'xls', 'csv', 'pdf'], accept_multiple_files=True, key="b_bnk")
    with c3:
        wa_paste_g1 = st.text_area("3A. Live Paste WhatsApp Group 1 (Withdrawal)", height=100, placeholder="WhatsApp Web se chat copy karke yahan paste karein...")
        wa_paste_g2 = st.text_area("3B. Live Paste WhatsApp Group 2 (Kharcha/Bahar)", height=100, placeholder="Group 2 chat ya UTR list paste karein...")

    save_to_cloud = st.checkbox("✅ Audit ke saath-saath in sabhi entries ko Permanent Cloud Database mein bhi save karein", value=True)

    if st.button("🚀 RUN BULK 3-WAY AUDIT", type="primary", use_container_width=True):
        df_p_dep = parse_panel_pdf(p_dep_files, "PANEL DEPOSIT") if p_dep_files else pd.DataFrame(columns=['Type', 'Source_File', 'Site', 'Username', 'Amount', 'UTR', 'Is_Duplicate'])
        df_p_wdl = parse_panel_pdf(p_wdl_files, "PANEL WITHDRAWAL") if p_wdl_files else pd.DataFrame(columns=['Type', 'Source_File', 'Site', 'Username', 'Amount', 'UTR', 'Is_Duplicate'])
        df_bank = parse_bank_statements(bank_files) if bank_files else pd.DataFrame(columns=['Bank_Account', 'Date', 'UTR', 'Credit_Inflow', 'Debit_Outflow', 'Category', 'Narration'])
        
        g1_utrs = set(extract_utrs(wa_paste_g1))
        g2_utrs = set(extract_utrs(wa_paste_g2))

        db_txns = sb_get("live_transactions", "limit=5000")
        for item in db_txns:
            if item['source_channel'] == 'WA_GROUP_1':
                g1_utrs.add(item['utr'])
            elif item['source_channel'] == 'WA_GROUP_2':
                g2_utrs.add(item['utr'])

        bank_cr_map = df_bank[df_bank['Credit_Inflow'] > 0].groupby('UTR')['Credit_Inflow'].sum().to_dict()
        bank_dr_map = df_bank[df_bank['Debit_Outflow'] > 0].groupby('UTR')['Debit_Outflow'].sum().to_dict()

        if not df_p_dep.empty:
            df_p_dep['Status'] = df_p_dep.apply(lambda r: "✅ VERIFIED" if r['UTR'] in bank_cr_map else "🚨 FAKE / BANK MISSING", axis=1)
        if not df_p_wdl.empty:
            df_p_wdl['Status'] = df_p_wdl.apply(lambda r: "✅ 3-WAY VERIFIED" if (r['UTR'] in bank_dr_map and r['UTR'] in g1_utrs) else ("⚠️ GROUP 1 MISSING" if r['UTR'] in bank_dr_map else "🚨 NOT PAID / MISSING"), axis=1)

        if save_to_cloud:
            target_b = selected_view if selected_view != "ALL" else "BR01"
            batch_rows = []
            for u in g1_utrs:
                batch_rows.append({"branch_code": target_b, "source_channel": "WA_GROUP_1", "utr": u, "raw_narration": "Bulk Paste Group 1"})
            for u in g2_utrs:
                batch_rows.append({"branch_code": target_b, "source_channel": "WA_GROUP_2", "utr": u, "raw_narration": "Bulk Paste Group 2"})
            if batch_rows:
                sb_post("live_transactions", batch_rows[:500])
            log_activity(st.session_state.auth_user, target_b, "BULK_AUDIT", f"Ran bulk audit: {len(df_p_dep)} dep, {len(df_p_wdl)} wdl")

        st.success("✅ Audit Complete! (Live WhatsApp Database UTRs bhi automatically match kiye gaye hain)")
        b_tabs = st.tabs(["🚨 Deposit Mismatch", "🚨 Withdrawal Mismatch", "📋 Full Bank Statement"])
        with b_tabs[0]:
            st.dataframe(df_p_dep[df_p_dep['Status'] != "✅ VERIFIED"] if not df_p_dep.empty else pd.DataFrame(), use_container_width=True)
        with b_tabs[1]:
            st.dataframe(df_p_wdl[df_p_wdl['Status'] != "✅ 3-WAY VERIFIED"] if not df_p_wdl.empty else pd.DataFrame(), use_container_width=True)
        with b_tabs[2]:
            st.dataframe(df_bank, use_container_width=True)

# ==========================================
# TAB 3: GLOBAL UTR RADAR & MASTER SEARCH
# ==========================================
with tabs[2]:
    st.subheader("🔍 Global UTR Radar (Cross-Branch Fraud Detector & Master History)")
    u_search = st.text_input("12-Digit UTR ya Username daalein (Poore System ki Sabhi Branches mein search hoga):", placeholder="e.g. 632418902341")
    if u_search.strip():
        q = u_search.strip()
        hits = sb_get("live_transactions", f"utr=ilike.*{q}*&order=txn_timestamp.asc")
        if not hits:
            st.warning(f"UTR '{q}' abhi tak kisi bhi branch ke database mein nahi mila hai.")
        else:
            df_hits = pd.DataFrame(hits)
            unique_branches = df_hits['branch_code'].nunique()
            if unique_branches > 1:
                st.error(f"🚨 **CROSS-BRANCH FRAUD ALERT!** Yeh UTR **{unique_branches} alag-alag branches** ({', '.join(df_hits['branch_code'].unique())}) mein use hua hai!")
            else:
                st.success(f"✅ Yeh UTR **{df_hits['branch_code'].iloc[0]}** mein कुल **{len(df_hits)} baar** record hua hai:")
            st.dataframe(df_hits[['branch_code', 'source_channel', 'device_code', 'utr', 'amount', 'sender_or_user', 'txn_timestamp', 'raw_narration']], use_container_width=True)

# ==========================================
# TAB 4: LIVE DEVICES & QR LIMIT MONITOR
# ==========================================
with tabs[3]:
    st.subheader("📱 Live Android Phones & Bank/QR Limit Monitor")
    dev_query = "order=branch_code.asc" if selected_view == "ALL" else f"branch_code=eq.{selected_view}&order=device_name.asc"
    devices_list = sb_get("devices", dev_query)
    if not devices_list:
        st.info("Abhi koi device registered nahi hai. Super Admin Control Center se '+ Add New Device' jodein.")
    else:
        curr_utc = datetime.now(timezone.utc)
        dev_rows = []
        for d in devices_list:
            try:
                ls = datetime.fromisoformat(d['last_seen'].replace('Z', '+00:00'))
                diff_min = (curr_utc - ls).total_seconds() / 60.0
                status = "🟢 ONLINE" if diff_min <= 5 else f"🔴 OFFLINE ({int(diff_min)}m ago)"
            except Exception:
                status = "🟡 WAITING FIRST PING"
            dev_rows.append({
                "Status": status,
                "Branch": d['branch_code'],
                "Device Name": d['device_name'],
                "Device Code (App Key)": d['device_code'],
                "Account Type": d['account_type'],
                "Daily Limit (₹)": d['daily_limit'],
                "Battery": f"{d.get('battery_level', 100)}%",
                "Active": "✅" if d.get('is_active') else "🔒 LOCKED"
            })
        st.dataframe(pd.DataFrame(dev_rows), use_container_width=True)

# ==========================================
# TAB 5: SUPER ADMIN CONTROL CENTER
# ==========================================
if st.session_state.auth_role == "SUPER_ADMIN":
    with tabs[4]:
        st.subheader("👑 Super Admin Master Control Center")
        sa1, sa2 = st.columns(2)
        
        with sa1:
            st.markdown("#### 🏢 1. Add New Branch")
            with st.form("add_branch_form"):
                b_code = st.text_input("Branch Code (Unique)", placeholder="e.g. BR02")
                b_name = st.text_input("Branch Name", placeholder="e.g. Jaipur Branch 2")
                m_id = st.text_input("Manager Login ID", placeholder="e.g. branch2")
                m_pwd = st.text_input("Manager Password", placeholder="e.g. 987654")
                wa_sup = st.text_input("WhatsApp Support Number", placeholder="e.g. 919876543210")
                if st.form_submit_button("➕ Create Branch", type="primary"):
                    if b_code and b_name and m_id and m_pwd:
                        ok, msg = sb_post("branches", {"branch_code": b_code.strip().upper(), "branch_name": b_name.strip(), "manager_id": m_id.strip(), "manager_password": m_pwd.strip(), "whatsapp_support_number": wa_sup.strip(), "support_enabled": True, "is_active": True})
                        if ok:
                            st.success(f"✅ Branch {b_name} ban gayi!")
                            st.rerun()
                        else:
                            st.error(f"⚠️ {msg}")

            st.markdown("#### 📱 2. Add New Phone / Listener Device")
            with st.form("add_device_form"):
                d_branch = st.selectbox("Select Branch", [b['branch_code'] for b in all_branches] if all_branches else ["BR01"])
                d_name = st.text_input("Device / Account Name", placeholder="e.g. HDFC-QR-1 ya SBI-Main")
                d_code = st.text_input("Unique Device Code (Phone App me dalne ke liye)", placeholder="e.g. DEV-HDFC-01")
                d_limit = st.number_input("Daily Receiving Limit (₹)", value=500000, step=50000)
                if st.form_submit_button("➕ Register Device", type="primary"):
                    if d_name and d_code:
                        ok, msg = sb_post("devices", {"branch_code": d_branch, "device_name": d_name.strip(), "device_code": d_code.strip().upper(), "daily_limit": d_limit, "is_active": True})
                        if ok:
                            st.success(f"✅ Device {d_name} register ho gaya!")
                            st.rerun()
                        else:
                            st.error(f"⚠️ {msg}")

        with sa2:
            st.markdown("#### 📢 3. Broadcast Live Notice / Ticker")
            with st.form("notice_form"):
                n_target = st.selectbox("Target Branch", ["ALL"] + [b['branch_code'] for b in all_branches])
                n_type = st.selectbox("Alert Level", ["INFO", "WARNING", "URGENT"])
                n_msg = st.text_input("Notice Message", placeholder="e.g. HDFC-1 QR limit full hone wali hai, SBI-2 chalu karein!")
                if st.form_submit_button("📣 Publish Live Notice", type="primary"):
                    if n_msg.strip():
                        ok, msg = sb_post("admin_notices", {"target_branch": n_target, "notice_type": n_type, "message": n_msg.strip(), "is_active": True})
                        if ok:
                            st.success("✅ Notice sabhi selected branches par live ho gaya!")
                            st.rerun()
                        else:
                            st.error(f"⚠️ {msg}")
            if st.button("🗑️ Clear All Active Notices"):
                sb_patch("admin_notices", "is_active=eq.true", {"is_active": False})
                st.rerun()

            st.markdown("#### 💬 4. WhatsApp Support & Branch Lock Control")
            if all_branches:
                edit_b = st.selectbox("Select Branch to Manage:", [b['branch_code'] for b in all_branches], key="manage_b")
                curr_obj = next(b for b in all_branches if b['branch_code'] == edit_b)
                new_wa = st.text_input("WhatsApp Support Number:", value=curr_obj.get('whatsapp_support_number', ''))
                sup_on = st.checkbox("Show Floating WhatsApp Button", value=curr_obj.get('support_enabled', True))
                b_active = st.checkbox("Branch Active (Uncheck to Kill-Switch / Lock Branch)", value=curr_obj.get('is_active', True))
                if st.button("💾 Save Branch Settings"):
                    sb_patch("branches", f"branch_code=eq.{edit_b}", {"whatsapp_support_number": new_wa.strip(), "support_enabled": sup_on, "is_active": b_active})
                    st.success("✅ Settings update ho gayi!")
                    st.rerun()

        st.markdown("#### 🛡️ Security & Activity Audit Log")
        logs = sb_get("audit_logs", "order=created_at.desc&limit=30")
        if logs:
            st.dataframe(pd.DataFrame(logs)[['created_at', 'actor', 'branch_code', 'action', 'details']], use_container_width=True)
