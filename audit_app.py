import streamlit as st
import pandas as pd
import re
import io
import zipfile
import pypdf
from PIL import Image

try:
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

# --- PAGE CONFIG & CORPORATE STYLING ---
st.set_page_config(
    page_title="Signature ( by vickyy )",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .main-header {
        background: linear-gradient(90deg, #0f172a 0%, #1e293b 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        color: #ffffff;
        margin-bottom: 1.5rem;
        border-left: 6px solid #38bdf8;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    .main-header h1 {
        margin: 0;
        font-size: 2rem;
        font-weight: 700;
        letter-spacing: 0.5px;
    }
    .main-header p {
        margin: 0.4rem 0 0 0;
        color: #cbd5e1;
        font-size: 0.95rem;
    }
    .login-box {
        max-width: 420px;
        margin: 4rem auto;
        padding: 2.2rem;
        background: #0f172a;
        border-radius: 14px;
        color: white;
        box-shadow: 0 10px 25px rgba(0,0,0,0.25);
        border: 1px solid #334155;
    }
    </style>
""", unsafe_allow_html=True)

# --- AUTHENTICATION SYSTEM ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("""
        <div class="login-box">
            <h2 style="text-align:center; margin-bottom:0.2rem; color:#38bdf8;">🛡️ Signature ( by vickyy )</h2>
            <p style="text-align:center; color:#94a3b8; font-size:0.9rem; margin-bottom:1.5rem;">Executive Audit & Reconciliation Portal</p>
        </div>
    """, unsafe_allow_html=True)
    
    col_l, col_m, col_r = st.columns([1, 1.2, 1])
    with col_m:
        with st.form("login_form"):
            user_id = st.text_input("Admin ID", placeholder="Enter ID")
            password = st.text_input("Password", type="password", placeholder="Enter Password")
            submit = st.form_submit_button("🔐 Secure Login", use_container_width=True, type="primary")
            
            if submit:
                if user_id.strip() == "Vicky9001" and password.strip() == "8890075565":
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("❌ Invalid ID or Password! Please try again.")
    st.stop()

# --- TOP HEADER & LOGOUT ---
h_col1, h_col2 = st.columns([5, 1])
with h_col1:
    st.markdown("""
        <div class="main-header">
            <h1>🛡️ Signature ( by vickyy )</h1>
            <p>3-Way Financial Audit • Panel Deposit & Withdrawal • Multi-Bank & GPay QR • WhatsApp Reconciliation</p>
        </div>
    """, unsafe_allow_html=True)
with h_col2:
    st.write("")
    st.write("")
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

# --- HELPER FUNCTIONS ---
def extract_utrs(text):
    if not text:
        return []
    matches = re.findall(r'\b[0-9]{12}\b', str(text))
    valid_utrs = [m for m in matches if len(set(m)) > 2]
    return list(set(valid_utrs))

def classify_bank_narration(desc):
    d = str(desc).upper()
    charge_keywords = ['CHG', 'CHARGES', 'IMPS FEE', 'NEFT CHG', 'RTGS CHG', 'SMS', 'GST', 'CONSOLIDATED', 'MIN BAL', 'ANNUAL FEE', 'DEBIT CARD FEE', 'TAX']
    cash_keywords = ['ATM', 'CASH WDL', 'ATW', 'NFS', 'SELF', 'CHQ PAID', 'CASH WITHDRAWAL', 'CDM']
    
    if any(k in d for k in charge_keywords):
        return "BANK CHARGES"
    if any(k in d for k in cash_keywords):
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
                    records.append({
                        'Type': panel_type,
                        'Source_File': file.name,
                        'Row_No': m.group(1),
                        'Site': m.group(3),
                        'Username': m.group(4),
                        'Amount': float(m.group(7)),
                        'UTR': utr_clean
                    })
                else:
                    utrs = extract_utrs(line)
                    for u in utrs:
                        nums = [float(x.replace(',', '')) for x in re.findall(r'\b\d{1,3}(?:,\d{3})*(?:\.\d{2})?\b', line) if len(x.replace(',','').split('.')[0]) < 9 and x != u]
                        amt = nums[0] if nums else 0.0
                        records.append({
                            'Type': panel_type,
                            'Source_File': file.name,
                            'Row_No': '-',
                            'Site': '-',
                            'Username': '-',
                            'Amount': amt,
                            'UTR': u
                        })
    if not records:
        return pd.DataFrame(columns=['Type', 'Source_File', 'Row_No', 'Site', 'Username', 'Amount', 'UTR', 'Is_Duplicate'])
    df = pd.DataFrame(records)
    df['Is_Duplicate'] = df.duplicated(subset=['UTR'], keep=False)
    return df

def parse_whatsapp_uploads(uploaded_files, group_label):
    utr_records = []
    if not uploaded_files:
        return pd.DataFrame(columns=['UTR', 'Group', 'Found_In', 'Context', 'Is_Duplicate'])

    def scan_text_content(text_str, source_name):
        for line in text_str.split('\n'):
            for u in extract_utrs(line):
                utr_records.append({
                    'UTR': u,
                    'Group': group_label,
                    'Found_In': f"Chat ({source_name})",
                    'Context': line.strip()[:100]
                })

    def scan_image_bytes(img_bytes, source_name):
        if not OCR_AVAILABLE:
            return
        try:
            image = Image.open(io.BytesIO(img_bytes))
            text = pytesseract.image_to_string(image)
            for u in extract_utrs(text):
                utr_records.append({
                    'UTR': u,
                    'Group': group_label,
                    'Found_In': f"Slip Image ({source_name})",
                    'Context': text.strip()[:100]
                })
        except Exception:
            pass

    for f in uploaded_files:
        fname = f.name.lower()
        if fname.endswith('.zip'):
            with zipfile.ZipFile(f, 'r') as z:
                for z_name in z.namelist():
                    z_lower = z_name.lower()
                    if z_lower.endswith('.txt'):
                        scan_text_content(z.read(z_name).decode('utf-8', errors='ignore'), z_name)
                    elif z_lower.endswith(('.png', '.jpg', '.jpeg', '.webp')):
                        scan_image_bytes(z.read(z_name), z_name)
        elif fname.endswith('.txt'):
            scan_text_content(f.read().decode('utf-8', errors='ignore'), f.name)
        elif fname.endswith(('.png', '.jpg', '.jpeg', '.webp')):
            scan_image_bytes(f.read(), f.name)

    if not utr_records:
        return pd.DataFrame(columns=['UTR', 'Group', 'Found_In', 'Context', 'Is_Duplicate'])
    df = pd.DataFrame(utr_records)
    df['Is_Duplicate'] = df.duplicated(subset=['UTR'], keep=False)
    return df

def parse_bank_statements(files):
    all_txns = []
    for f in files:
        fname = f.name.lower()
        if fname.endswith(('.csv', '.xlsx', '.xls')):
            df = pd.read_csv(f) if fname.endswith('.csv') else pd.read_excel(f)
            df.columns = [str(c).strip().upper() for c in df.columns]
            
            desc_col = next((c for c in df.columns if any(k in c for k in ['NARRATION', 'DESCRIPTION', 'PARTICULARS', 'REMARKS', 'DETAILS', 'TRANSACTION'])), None)
            utr_col = next((c for c in df.columns if any(k in c for k in ['UTR', 'REF', 'REFERENCE', 'CHQ', 'TRAN ID'])), None)
            cr_col = next((c for c in df.columns if any(k in c for k in ['CREDIT', 'CR', 'DEPOSIT', 'INFLOW', 'AMOUNT'])), None)
            dr_col = next((c for c in df.columns if any(k in c for k in ['DEBIT', 'DR', 'WITHDRAWAL', 'OUTFLOW'])), None)
            date_col = next((c for c in df.columns if 'DATE' in c), None)

            for _, row in df.iterrows():
                desc_val = str(row[desc_col]) if desc_col else ""
                utr_raw = str(row[utr_col]) if utr_col else ""
                utrs = extract_utrs(f"{desc_val} {utr_raw}")
                utr_final = utrs[0] if utrs else "NO_UTR"
                
                cr_amt, dr_amt = 0.0, 0.0
                if cr_col and dr_col and cr_col != dr_col:
                    cr_amt = pd.to_numeric(str(row[cr_col]).replace(',', ''), errors='coerce') or 0.0
                    dr_amt = pd.to_numeric(str(row[dr_col]).replace(',', ''), errors='coerce') or 0.0
                elif cr_col:
                    val = pd.to_numeric(str(row[cr_col]).replace(',', ''), errors='coerce') or 0.0
                    if val >= 0:
                        cr_amt = val
                    else:
                        dr_amt = abs(val)
                        
                if cr_amt == 0 and dr_amt == 0:
                    continue
                    
                category = classify_bank_narration(desc_val) if dr_amt > 0 else "DEPOSIT / INFLOW"
                all_txns.append({
                    'Bank_Account': f.name,
                    'Date': str(row[date_col]) if date_col else "-",
                    'UTR': utr_final,
                    'Credit_Inflow': cr_amt,
                    'Debit_Outflow': dr_amt,
                    'Category': category,
                    'Narration': desc_val[:120]
                })
                
        elif fname.endswith('.pdf'):
            reader = pypdf.PdfReader(f)
            for page in reader.pages:
                text = page.extract_text()
                for line in text.split('\n'):
                    utrs = extract_utrs(line)
                    if utrs:
                        nums = [float(x.replace(',', '')) for x in re.findall(r'\b\d{1,3}(?:,\d{3})*(?:\.\d{2})?\b', line) if len(x.replace(',','').split('.')[0]) < 9 and x != utrs[0]]
                        amt = nums[0] if nums else 0.0
                        cat = classify_bank_narration(line)
                        all_txns.append({
                            'Bank_Account': f.name,
                            'Date': '-',
                            'UTR': utrs[0],
                            'Credit_Inflow': amt,
                            'Debit_Outflow': amt,
                            'Category': cat,
                            'Narration': line.strip()[:120]
                        })
                        
    return pd.DataFrame(all_txns) if all_txns else pd.DataFrame(columns=['Bank_Account', 'Date', 'UTR', 'Credit_Inflow', 'Debit_Outflow', 'Category', 'Narration'])

# --- UPLOAD SECTION ---
c1, c2, c3 = st.columns(3)

with c1:
    st.markdown("### 📥 1. Panel Records")
    panel_dep_files = st.file_uploader("Upload Panel DEPOSIT PDF(s)", type=['pdf'], accept_multiple_files=True)
    panel_wdl_files = st.file_uploader("Upload Panel WITHDRAWAL PDF(s)", type=['pdf'], accept_multiple_files=True)

with c2:
    st.markdown("### 🏦 2. Bank & GPay QR")
    bank_files = st.file_uploader("Upload All Bank & GPay QR Statements (Excel / CSV / PDF)", type=['xlsx', 'xls', 'csv', 'pdf'], accept_multiple_files=True)

with c3:
    st.markdown("### 💬 3. WhatsApp Groups (.ZIP)")
    g1_files = st.file_uploader("Group 1: Client Withdrawal Group (.ZIP / .txt)", type=['zip', 'txt', 'png', 'jpg', 'jpeg'], accept_multiple_files=True)
    g2_files = st.file_uploader("Group 2: Bahar Payment / Kharcha (.ZIP / .txt)", type=['zip', 'txt', 'png', 'jpg', 'jpeg'], accept_multiple_files=True)

st.divider()

if st.button("🚀 RUN COMPLETE 3-WAY AUDIT", type="primary", use_container_width=True):
    if not panel_dep_files and not panel_wdl_files and not bank_files:
        st.error("Kam se kam Panel PDF ya Bank Statement upload karein!")
    else:
        with st.spinner("3-Way Reconciliation & Mismatch Analysis chal raha hai..."):
            df_p_dep = parse_panel_pdf(panel_dep_files, "PANEL DEPOSIT") if panel_dep_files else pd.DataFrame(columns=['Type', 'Source_File', 'Row_No', 'Site', 'Username', 'Amount', 'UTR', 'Is_Duplicate'])
            df_p_wdl = parse_panel_pdf(panel_wdl_files, "PANEL WITHDRAWAL") if panel_wdl_files else pd.DataFrame(columns=['Type', 'Source_File', 'Row_No', 'Site', 'Username', 'Amount', 'UTR', 'Is_Duplicate'])
            df_bank = parse_bank_statements(bank_files) if bank_files else pd.DataFrame(columns=['Bank_Account', 'Date', 'UTR', 'Credit_Inflow', 'Debit_Outflow', 'Category', 'Narration'])
            df_g1 = parse_whatsapp_uploads(g1_files, "Group 1 (Withdrawal)")
            df_g2 = parse_whatsapp_uploads(g2_files, "Group 2 (Bahar/Kharcha)")
            
            bank_cr_map = df_bank[df_bank['Credit_Inflow'] > 0].groupby('UTR')['Credit_Inflow'].sum().to_dict()
            bank_dr_map = df_bank[df_bank['Debit_Outflow'] > 0].groupby('UTR')['Debit_Outflow'].sum().to_dict()
            p_dep_utrs = set(df_p_dep['UTR'])
            p_wdl_utrs = set(df_p_wdl['UTR'])
            g1_utrs = set(df_g1['UTR'])
            g2_utrs = set(df_g2['UTR'])
            
            def tag_panel_deposit(row):
                u = row['UTR']
                dup_tag = " | 🔁 DUPLICATE UTR" if row['Is_Duplicate'] else ""
                if u in bank_cr_map:
                    b_amt = bank_cr_map[u]
                    if row['Amount'] > 0 and abs(b_amt - row['Amount']) > 1:
                        return f"🚨 AMOUNT MISMATCH (Panel: ₹{row['Amount']:,.0f} vs Bank: ₹{b_amt:,.0f}){dup_tag}"
                    return f"✅ VERIFIED DEPOSIT{dup_tag}"
                return f"🚨 DEPOSIT FAKE / BANK STATEMENT MISSING{dup_tag}"
                
            if not df_p_dep.empty:
                df_p_dep['Audit_Status'] = df_p_dep.apply(tag_panel_deposit, axis=1)
            df_dep_mismatch = df_p_dep[~df_p_dep['Audit_Status'].str.startswith("✅")].copy() if not df_p_dep.empty else pd.DataFrame()

            def tag_panel_withdrawal(row):
                u = row['UTR']
                dup_tag = " | 🔁 DUPLICATE UTR" if row['Is_Duplicate'] else ""
                in_bank = u in bank_dr_map
                in_g1 = u in g1_utrs
                if in_bank and in_g1:
                    b_amt = bank_dr_map[u]
                    if row['Amount'] > 0 and abs(b_amt - row['Amount']) > 1:
                        return f"🚨 AMOUNT MISMATCH (Panel: ₹{row['Amount']:,.0f} vs Bank: ₹{b_amt:,.0f}){dup_tag}"
                    return f"✅ VERIFIED WITHDRAWAL (3-Way Match){dup_tag}"
                elif in_bank and not in_g1:
                    return f"⚠️ PAID IN BANK BUT MISSING IN WHATSAPP GROUP 1{dup_tag}"
                elif not in_bank and in_g1:
                    return f"⚠️ IN WHATSAPP GROUP 1 BUT BANK STATEMENT MISSING{dup_tag}"
                return f"🚨 WITHDRAWAL FAKE / NOT PAID{dup_tag}"

            if not df_p_wdl.empty:
                df_p_wdl['Audit_Status'] = df_p_wdl.apply(tag_panel_withdrawal, axis=1)
            df_wdl_mismatch = df_p_wdl[~df_p_wdl['Audit_Status'].str.startswith("✅")].copy() if not df_p_wdl.empty else pd.DataFrame()

            def tag_bank_row(row):
                u = row['UTR']
                if row['Category'] == "BANK CHARGES":
                    return "🏦 BANK CHARGES"
                if row['Category'] == "CASH WITHDRAWAL":
                    return "💵 CASH WITHDRAWAL"
                if row['Credit_Inflow'] > 0:
                    if u in p_dep_utrs:
                        return "✅ VERIFIED DEPOSIT (Panel Matched)"
                    return "⚠️ EXTRA BANK CREDIT (Panel Deposit Me Nahi Mila)"
                if row['Debit_Outflow'] > 0:
                    if u in p_wdl_utrs and u in g1_utrs:
                        return "✅ VERIFIED WITHDRAWAL (Panel + Group 1)"
                    elif u in g1_utrs:
                        return "⚠️ IN GROUP 1 BUT PANEL WITHDRAWAL ME NHI H"
                    elif u in g2_utrs:
                        return "✅ BAHAR PAYMENT / KHARCHA (Group 2)"
                    elif u in p_wdl_utrs:
                        return "⚠️ IN PANEL WITHDRAWAL BUT GROUP 1 SLIP MISSING"
                    return "🚨 EXTRA BANK DEBIT (Na Panel Me, Na Kisi Group Me)"
                return "-"

            if not df_bank.empty:
                df_bank['Audit_Status'] = df_bank.apply(tag_bank_row, axis=1)

            df_extra_bank_cr = df_bank[df_bank['Audit_Status'].str.contains("EXTRA BANK CREDIT", na=False)].copy() if not df_bank.empty else pd.DataFrame()
            df_extra_bank_dr = df_bank[df_bank['Audit_Status'].str.contains("EXTRA BANK DEBIT|MISSING|NHI H", na=False)].copy() if not df_bank.empty else pd.DataFrame()
            df_cash = df_bank[df_bank['Category'] == "CASH WITHDRAWAL"].copy() if not df_bank.empty else pd.DataFrame()
            df_charges = df_bank[df_bank['Category'] == "BANK CHARGES"].copy() if not df_bank.empty else pd.DataFrame()

            if not df_bank.empty:
                st.subheader("📊 Bank & QR Account Summary")
                bank_summary = df_bank.groupby('Bank_Account').agg(
                    Total_Transactions=('UTR', 'count'),
                    Total_Credit_Inflow=('Credit_Inflow', 'sum'),
                    Total_Debit_Outflow=('Debit_Outflow', 'sum')
                ).reset_index()
                bank_summary['Net_Balance_Change'] = bank_summary['Total_Credit_Inflow'] - bank_summary['Total_Debit_Outflow']
                st.dataframe(bank_summary, use_container_width=True)

            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("🚨 Deposit Fake / Missing Stmt", len(df_dep_mismatch))
            m2.metric("🚨 Withdrawal Fake / Mismatch", len(df_wdl_mismatch))
            m3.metric("⚠️ Extra Bank Credits", len(df_extra_bank_cr))
            m4.metric("⚠️ Extra Bank Debits", len(df_extra_bank_dr))
            m5.metric("💵 Cash + 🏦 Charges", f"₹ {(df_cash['Debit_Outflow'].sum() + df_charges['Debit_Outflow'].sum()):,.0f}")

            st.subheader("🔍 Instant UTR / Username Search")
            search_q = st.text_input("Kisi bhi UTR (12-digit) ya Client Username ko yahan search karein:", placeholder="e.g. 632418902341 ya rahul123")
            if search_q.strip():
                q = search_q.strip().lower()
                s_dep = df_p_dep[df_p_dep.apply(lambda r: q in str(r.values).lower(), axis=1)] if not df_p_dep.empty else pd.DataFrame()
                s_wdl = df_p_wdl[df_p_wdl.apply(lambda r: q in str(r.values).lower(), axis=1)] if not df_p_wdl.empty else pd.DataFrame()
                s_bnk = df_bank[df_bank.apply(lambda r: q in str(r.values).lower(), axis=1)] if not df_bank.empty else pd.DataFrame()
                s_grp = pd.concat([df_g1, df_g2])[pd.concat([df_g1, df_g2]).apply(lambda r: q in str(r.values).lower(), axis=1)] if (not df_g1.empty or not df_g2.empty) else pd.DataFrame()
                
                st.info(f"Search Results for '{search_q}': Panel Deposit ({len(s_dep)}) | Panel Withdrawal ({len(s_wdl)}) | Bank ({len(s_bnk)}) | WhatsApp ({len(s_grp)})")
                if not s_dep.empty: st.dataframe(s_dep, use_container_width=True)
                if not s_wdl.empty: st.dataframe(s_wdl, use_container_width=True)
                if not s_bnk.empty: st.dataframe(s_bnk, use_
