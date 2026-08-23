import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
import sys
from datetime import date, timedelta
import io

sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config(page_title="التقرير اليومي - فولو اب", page_icon="📈", layout="wide")

# ══════════════════════════════════════════════════════
#  CSS احترافي
# ══════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;900&display=swap');

html, body, [class*="css"], .stApp {
    font-family: 'Cairo', sans-serif !important;
    direction: rtl !important;
    text-align: right !important;
}
.stApp { background: linear-gradient(135deg, #0a0f1e 0%, #0d1b2a 100%) !important; }

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d1b2a 0%, #091525 100%) !important;
    border-left: 1px solid rgba(0,200,150,0.25) !important;
}

[data-testid="metric-container"] {
    background: linear-gradient(135deg, rgba(0,200,150,0.08), rgba(0,150,255,0.06)) !important;
    border: 1px solid rgba(0,200,150,0.3) !important;
    border-radius: 16px !important;
    padding: 20px !important;
    transition: transform 0.2s, box-shadow 0.2s;
}
[data-testid="metric-container"]:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 30px rgba(0,200,150,0.2) !important;
}
[data-testid="stMetricValue"] { color: #00e5a0 !important; font-weight: 900 !important; font-size: 26px !important; }
[data-testid="stMetricLabel"] { color: #6ee7b7 !important; font-size: 13px !important; }
[data-testid="stMetricDelta"] { font-size: 13px !important; }

.stDownloadButton > button {
    background: linear-gradient(135deg, #005f4b 0%, #00b887 100%) !important;
    color: white !important; border: none !important;
    border-radius: 12px !important; font-weight: 700 !important;
    font-size: 15px !important; padding: 12px 28px !important;
    box-shadow: 0 4px 20px rgba(0,200,150,0.35) !important;
    transition: all 0.25s !important;
}
.stDownloadButton > button:hover { transform: translateY(-2px) !important; box-shadow: 0 8px 30px rgba(0,200,150,0.5) !important; }

.report-card {
    background: linear-gradient(135deg, rgba(0,200,150,0.07), rgba(0,100,255,0.05));
    border: 1px solid rgba(0,200,150,0.25);
    border-radius: 18px;
    padding: 24px;
    margin: 12px 0;
}
.section-header {
    background: linear-gradient(90deg, rgba(0,200,150,0.15), transparent);
    border-right: 4px solid #00e5a0;
    padding: 10px 16px;
    border-radius: 8px;
    color: #00e5a0;
    font-size: 18px;
    font-weight: 700;
    margin: 20px 0 12px 0;
}
.badge-portfolio {
    display: inline-block;
    background: rgba(0,200,150,0.15);
    border: 1px solid rgba(0,200,150,0.4);
    color: #00e5a0;
    border-radius: 20px;
    padding: 4px 12px;
    font-size: 13px;
    font-weight: 600;
    margin: 3px;
}
hr { border-color: rgba(0,200,150,0.2) !important; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
#  Header
# ══════════════════════════════════════════════════════
st.markdown("""
<div style="text-align:center; padding: 30px 0 10px 0;">
    <div style="font-size:48px;">📈</div>
    <h1 style="color:#00e5a0; font-weight:900; margin:8px 0 4px 0; font-size:32px;">
        التقرير اليومي — فولو اب
    </h1>
    <p style="color:#6ee7b7; font-size:15px;">
        ربط المحفظة المجمعة × المحفظة الموزعة × السدادات — تحليل شامل بالشارتس والسلايسرز
    </p>
    <div style="height:3px; background:linear-gradient(90deg,transparent,#00e5a0,transparent); margin:16px auto; width:60%;"></div>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
#  رفع الملفات الثلاثة
# ══════════════════════════════════════════════════════
st.markdown('<div class="section-header">📂 رفع الملفات الثلاثة</div>', unsafe_allow_html=True)

col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    st.markdown("**📋 المحفظة المجمعة** *(مطلوبة — تحتوي رقم المديونية)*")
    master_file = st.file_uploader("المحفظة المجمعة", type=["xlsx","xls"], key="daily_master", label_visibility="collapsed")
with col_f2:
    st.markdown("**📊 المحفظة الموزعة** *(مطلوبة — تحتوي أسماء المحافظ)*")
    dist_file   = st.file_uploader("المحفظة الموزعة",  type=["xlsx","xls"], key="daily_dist",   label_visibility="collapsed")
with col_f3:
    st.markdown("**💳 شيت السدادات** *(مطلوب — تحتوي مبلغ السداد)*")
    pay_file    = st.file_uploader("شيت السدادات",     type=["xlsx","xls"], key="daily_pay",    label_visibility="collapsed")

if not master_file or not dist_file or not pay_file:
    st.info("📌 ارفع الملفات الثلاثة للبدء في التحليل.")
    st.stop()

# ══════════════════════════════════════════════════════
#  قراءة الملفات
# ══════════════════════════════════════════════════════
@st.cache_data(show_spinner="⏳ جاري قراءة الملفات...")
def read_excel(file_bytes, fname):
    return pd.read_excel(io.BytesIO(file_bytes), dtype=str)

master_bytes = master_file.getvalue()
dist_bytes   = dist_file.getvalue()
pay_bytes    = pay_file.getvalue()

df_master = read_excel(master_bytes, master_file.name)
df_dist   = read_excel(dist_bytes,   dist_file.name)
df_pay    = read_excel(pay_bytes,    pay_file.name)

# ══════════════════════════════════════════════════════
#  اكتشاف الأعمدة الأساسية تلقائياً
# ══════════════════════════════════════════════════════
def detect_col(df, candidates):
    cols_lower = {c.strip().lower(): c for c in df.columns}
    for c in candidates:
        if c.strip().lower() in cols_lower:
            return cols_lower[c.strip().lower()]
    # partial match
    for c in candidates:
        for col in df.columns:
            if c.strip() in col:
                return col
    return None

# المحفظة المجمعة
MASTER_DEBT_ID   = detect_col(df_master, ["رقم المديونية","رقم المديوني","debt_id"])
MASTER_CID       = detect_col(df_master, ["رقم الهوية","رقم هوية","الهوية","customer_id"])
MASTER_DEBT_AMT  = detect_col(df_master, ["مبلغ المديونية","مبلغ الميدونيه","مبلغ الميدونية","debt_amount"])
MASTER_PORTFOLIO = detect_col(df_master, ["المحفظة","المحافظ","محفظه","portfolio"])
MASTER_SUP       = detect_col(df_master, ["المشرف","اسم المشرف","supervisor"])
MASTER_COL       = detect_col(df_master, ["المحصل","اسم المحصل","collector"])

# المحفظة الموزعة
DIST_DEBT_ID   = detect_col(df_dist, ["رقم المديونية","رقم المديوني","debt_id"])
DIST_CID       = detect_col(df_dist, ["رقم الهوية","رقم هوية","الهوية","customer_id"])
DIST_DEBT_AMT  = detect_col(df_dist, ["مبلغ المديونية","مبلغ الميدونيه","مبلغ الميدونية","debt_amount"])
DIST_PORTFOLIO = detect_col(df_dist, ["المحفظة","المحافظ","محفظه","portfolio"])
DIST_SUP       = detect_col(df_dist, ["المشرف","اسم المشرف","supervisor"])
DIST_COL       = detect_col(df_dist, ["المحصل","اسم المحصل","collector"])

# السدادات
PAY_DEBT_ID  = detect_col(df_pay, ["رقم المديونية","رقم المديوني","debt_id"])
PAY_CID      = detect_col(df_pay, ["رقم الهوية","رقم هوية","الهوية","customer_id"])
PAY_AMOUNT   = detect_col(df_pay, ["مبلغ السداد","مبلغ الدفع","payment_amount","المبلغ"])
PAY_DATE     = detect_col(df_pay, ["تاريخ السداد","تاريخ الدفع","payment_date","التاريخ"])
PAY_SUP      = detect_col(df_pay, ["المشرف","اسم المشرف","supervisor"])
PAY_COL      = detect_col(df_pay, ["اسم المحصل","المحصل","collector"])

# ── عرض الأعمدة المكتشفة ──
with st.expander("🔍 الأعمدة المكتشفة تلقائياً (انقر للتحقق أو التعديل)", expanded=False):
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**📋 المحفظة المجمعة:**")
        MASTER_DEBT_ID  = st.selectbox("رقم المديونية", df_master.columns.tolist(), index=df_master.columns.tolist().index(MASTER_DEBT_ID) if MASTER_DEBT_ID else 0, key="m_debt_id")
        MASTER_CID      = st.selectbox("رقم الهوية",    df_master.columns.tolist(), index=df_master.columns.tolist().index(MASTER_CID) if MASTER_CID else 0,     key="m_cid")
        MASTER_PORTFOLIO= st.selectbox("المحفظة",       df_master.columns.tolist(), index=df_master.columns.tolist().index(MASTER_PORTFOLIO) if MASTER_PORTFOLIO else 0, key="m_port")
    with c2:
        st.markdown("**📊 المحفظة الموزعة:**")
        DIST_DEBT_ID   = st.selectbox("رقم المديونية",  df_dist.columns.tolist(), index=df_dist.columns.tolist().index(DIST_DEBT_ID) if DIST_DEBT_ID else 0,  key="d_debt_id")
        DIST_CID       = st.selectbox("رقم الهوية",     df_dist.columns.tolist(), index=df_dist.columns.tolist().index(DIST_CID) if DIST_CID else 0,       key="d_cid")
        DIST_PORTFOLIO = st.selectbox("المحفظة",        df_dist.columns.tolist(), index=df_dist.columns.tolist().index(DIST_PORTFOLIO) if DIST_PORTFOLIO else 0,  key="d_port")
        DIST_DEBT_AMT  = st.selectbox("مبلغ المديونية", df_dist.columns.tolist(), index=df_dist.columns.tolist().index(DIST_DEBT_AMT) if DIST_DEBT_AMT else 0,  key="d_debt_amt")
        DIST_SUP       = st.selectbox("المشرف",         df_dist.columns.tolist(), index=df_dist.columns.tolist().index(DIST_SUP) if DIST_SUP else 0,        key="d_sup")
        DIST_COL       = st.selectbox("المحصل",         df_dist.columns.tolist(), index=df_dist.columns.tolist().index(DIST_COL) if DIST_COL else 0,        key="d_col")
    with c3:
        st.markdown("**💳 السدادات:**")
        PAY_DEBT_ID = st.selectbox("رقم المديونية",  df_pay.columns.tolist(), index=df_pay.columns.tolist().index(PAY_DEBT_ID) if PAY_DEBT_ID else 0,  key="p_debt_id")
        PAY_AMOUNT  = st.selectbox("مبلغ السداد",    df_pay.columns.tolist(), index=df_pay.columns.tolist().index(PAY_AMOUNT) if PAY_AMOUNT else 0,   key="p_amount")
        PAY_DATE    = st.selectbox("تاريخ السداد",   df_pay.columns.tolist(), index=df_pay.columns.tolist().index(PAY_DATE) if PAY_DATE else 0,     key="p_date")
        PAY_SUP     = st.selectbox("المشرف",         df_pay.columns.tolist(), index=df_pay.columns.tolist().index(PAY_SUP) if PAY_SUP else 0,      key="p_sup")
        PAY_COL     = st.selectbox("اسم المحصل",     df_pay.columns.tolist(), index=df_pay.columns.tolist().index(PAY_COL) if PAY_COL else 0,      key="p_col")

st.markdown("---")

# ══════════════════════════════════════════════════════
#  دوال مساعدة لتنظيف الأرقام والمعرفات
# ══════════════════════════════════════════════════════
def to_clean_num(series):
    if series is None:
        return pd.Series(dtype=float)
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors='coerce').fillna(0.0)
    return pd.to_numeric(
        series.astype(str).str.replace(',', '', regex=False).str.replace(' ', '', regex=False).str.replace('﷼', '', regex=False),
        errors='coerce'
    ).fillna(0.0)

def clean_id(val):
    if pd.isna(val):
        return ''
    s = str(val).strip()
    if s.endswith('.0'):
        s = s[:-2]
    return s

# ══════════════════════════════════════════════════════
#  معالجة البيانات
# ══════════════════════════════════════════════════════
with st.spinner("🔄 جاري ربط الملفات الثلاثة وتحليل البيانات بدقة..."):

    # ── 1. تنظيف السدادات ──
    df_pay_clean = df_pay.copy()
    df_pay_clean[PAY_AMOUNT] = to_clean_num(df_pay_clean[PAY_AMOUNT])
    if PAY_DATE:
        df_pay_clean['_pay_date'] = pd.to_datetime(df_pay_clean[PAY_DATE], errors='coerce', dayfirst=False)
        # fallback dayfirst
        bad = df_pay_clean['_pay_date'].isna()
        if bad.sum() > len(df_pay_clean) * 0.3:
            df_pay_clean['_pay_date'] = pd.to_datetime(df_pay_clean[PAY_DATE], errors='coerce', dayfirst=True)
    else:
        df_pay_clean['_pay_date'] = pd.NaT

    # ── 2. إضافة عمود المحفظة للسدادات من المحفظة المجمعة ثم الموزعة ──
    debt_to_portfolio = {}
    if MASTER_DEBT_ID and MASTER_PORTFOLIO and MASTER_DEBT_ID in df_master.columns and MASTER_PORTFOLIO in df_master.columns:
        for _, row in df_master.iterrows():
            k = clean_id(row[MASTER_DEBT_ID])
            v = str(row[MASTER_PORTFOLIO]).strip()
            if k and pd.notna(v) and v not in ('', 'nan', 'None'):
                debt_to_portfolio[k] = v

    if DIST_DEBT_ID and DIST_PORTFOLIO and DIST_DEBT_ID in df_dist.columns and DIST_PORTFOLIO in df_dist.columns:
        for _, row in df_dist.iterrows():
            k = clean_id(row[DIST_DEBT_ID])
            v = str(row[DIST_PORTFOLIO]).strip()
            if k and k not in debt_to_portfolio and pd.notna(v) and v not in ('', 'nan', 'None'):
                debt_to_portfolio[k] = v

    df_pay_clean['_portfolio'] = df_pay_clean[PAY_DEBT_ID].apply(clean_id).map(debt_to_portfolio).fillna('غير محدد')

    # ── 3. تنظيف المحفظة الموزعة ──
    df_dist_clean = df_dist.copy()
    if DIST_DEBT_AMT:
        df_dist_clean[DIST_DEBT_AMT] = to_clean_num(df_dist_clean[DIST_DEBT_AMT])
    if DIST_CID:
        df_dist_clean[DIST_CID] = df_dist_clean[DIST_CID].apply(clean_id)
    if DIST_PORTFOLIO:
        df_dist_clean[DIST_PORTFOLIO] = df_dist_clean[DIST_PORTFOLIO].astype(str).str.strip()

    # ── 4. قائمة المحافظ الموجودة في المحفظة الموزعة ──
    portfolios_in_dist = sorted(df_dist_clean[DIST_PORTFOLIO].dropna().unique().tolist()) if DIST_PORTFOLIO else []

    # ── 5. تاريخ اليوم ──
    today = pd.Timestamp.today().normalize()
    yesterday = today - timedelta(days=1)

# ══════════════════════════════════════════════════════
#  سلايسر المحافظ والمشرفين
# ══════════════════════════════════════════════════════
st.markdown('<div class="section-header">🎛️ سلايسر — تصفية حسب المحفظة والمشرفين</div>', unsafe_allow_html=True)

all_ports = portfolios_in_dist if portfolios_in_dist else sorted(df_pay_clean['_portfolio'].unique().tolist())

# قائمة المشرفين في كلا الملفين
dist_sups = df_dist_clean[DIST_SUP].dropna().unique().tolist() if DIST_SUP and DIST_SUP in df_dist_clean.columns else []
pay_sups  = df_pay_clean[PAY_SUP].dropna().unique().tolist() if PAY_SUP and PAY_SUP in df_pay_clean.columns else []
all_sups  = sorted(list(set([str(s).strip() for s in (dist_sups + pay_sups) if str(s).strip() and str(s).strip() not in ['nan', 'None']])))

col_sl1, col_sl2, col_date = st.columns([2, 2, 1])
with col_sl1:
    selected_ports = st.multiselect(
        "📂 اختر المحفظة/المحافظ (اتركه فارغاً للكل):",
        options=all_ports,
        default=[],
        key="port_slicer"
    )
with col_sl2:
    selected_sups = st.multiselect(
        "👥 اختر المشرف/المشرفين (اتركه فارغاً للكل):",
        options=all_sups,
        default=[],
        key="sup_slicer"
    )
with col_date:
    report_date = st.date_input("📅 تاريخ التقرير:", value=date.today(), key="report_date")
    today = pd.Timestamp(report_date)
    yesterday = today - timedelta(days=1)

# تطبيق الفلاتر
df_pay_filtered = df_pay_clean.copy()
df_dist_filtered = df_dist_clean.copy()

if selected_ports:
    df_pay_filtered = df_pay_filtered[df_pay_filtered['_portfolio'].isin(selected_ports)]
    if DIST_PORTFOLIO and DIST_PORTFOLIO in df_dist_filtered.columns:
        df_dist_filtered = df_dist_filtered[df_dist_filtered[DIST_PORTFOLIO].isin(selected_ports)]

if selected_sups:
    if PAY_SUP and PAY_SUP in df_pay_filtered.columns:
        df_pay_filtered = df_pay_filtered[df_pay_filtered[PAY_SUP].astype(str).str.strip().isin(selected_sups)]
    if DIST_SUP and DIST_SUP in df_dist_filtered.columns:
        df_dist_filtered = df_dist_filtered[df_dist_filtered[DIST_SUP].astype(str).str.strip().isin(selected_sups)]

# عرض الـ badges للمحافظ والمشرفين
ports_to_show = selected_ports if selected_ports else all_ports[:10]
sups_to_show  = selected_sups if selected_sups else all_sups[:10]
p_badges = " ".join([f'<span class="badge-portfolio">📂 {p}</span>' for p in ports_to_show])
s_badges = " ".join([f'<span class="badge-portfolio" style="border-color:#0015ff; color:#a0c4ff;">👥 {s}</span>' for s in sups_to_show])
st.markdown(f'<div style="margin:8px 0;">{p_badges} {s_badges}</div>', unsafe_allow_html=True)

st.markdown("---")

# ══════════════════════════════════════════════════════
#  حساب وحالات التوصل وعدم التوصل (لا يرد ومغلق)
# ══════════════════════════════════════════════════════
try:
    from core.daily_followup_engine import classify_contact_status_series
except Exception:
    try:
        from STC_System.core.daily_followup_engine import classify_contact_status_series
    except Exception:
        import sys as _sys, os as _os
        _root = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), "..", ".."))
        if _root not in _sys.path:
            _sys.path.insert(0, _root)
        from core.daily_followup_engine import classify_contact_status_series

main_status_col = detect_col(df_dist_filtered, ["الحالة الرئيسية", "الحالة المتبعة", "main_status"])
sub_status_col  = detect_col(df_dist_filtered, ["الحالة الفرعية", "sub_status"])
note_status_col = detect_col(df_dist_filtered, ["المتابعة", "الملاحظات", "الملاحظة", "ملاحظة", "followup"])

df_dist_filtered['حالة_التوصل'] = classify_contact_status_series(
    df_dist_filtered, main_col=main_status_col, sub_col=sub_status_col, note_col=note_status_col
)

cnt_contacted     = (df_dist_filtered['حالة_التوصل'] == 'تم التوصل').sum()
cnt_no_ans_closed = (df_dist_filtered['حالة_التوصل'] == 'لا يرد ومغلق').sum()
cnt_other         = (df_dist_filtered['حالة_التوصل'] == 'عدم توصل - أخرى').sum()
cnt_total         = len(df_dist_filtered)
cnt_rate          = (cnt_contacted / cnt_total * 100) if cnt_total > 0 else 0.0
cnt_no_ans_pct    = (cnt_no_ans_closed / cnt_total * 100) if cnt_total > 0 else 0.0

# جدول تحليل التوصل حسب المحفظة
if DIST_PORTFOLIO and DIST_PORTFOLIO in df_dist_filtered.columns:
    contact_by_port = df_dist_filtered.groupby([DIST_PORTFOLIO, 'حالة_التوصل']).size().unstack(fill_value=0).reset_index()
    contact_by_port.columns.name = None
    
    for req_col in ['تم التوصل', 'لا يرد ومغلق', 'عدم توصل - أخرى']:
        if req_col not in contact_by_port.columns:
            contact_by_port[req_col] = 0

    contact_by_port.rename(columns={DIST_PORTFOLIO: 'المحفظة'}, inplace=True)
    contact_by_port['إجمالي العملاء'] = contact_by_port['تم التوصل'] + contact_by_port['لا يرد ومغلق'] + contact_by_port['عدم توصل - أخرى']
    
    contact_by_port['نسبة تم التوصل %'] = contact_by_port.apply(
        lambda r: round(r['تم التوصل'] / r['إجمالي العملاء'] * 100, 1) if r['إجمالي العملاء'] > 0 else 0.0, axis=1
    )
    contact_by_port['نسبة لا يرد ومغلق %'] = contact_by_port.apply(
        lambda r: round(r['لا يرد ومغلق'] / r['إجمالي العملاء'] * 100, 1) if r['إجمالي العملاء'] > 0 else 0.0, axis=1
    )

    contact_cols_order = ['المحفظة', 'إجمالي العملاء', 'تم التوصل', 'نسبة تم التوصل %', 'لا يرد ومغلق', 'نسبة لا يرد ومغلق %', 'عدم توصل - أخرى']
    contact_by_port = contact_by_port[[c for c in contact_cols_order if c in contact_by_port.columns]].sort_values('تم التوصل', ascending=False)

    cnt_tot_row = {
        'المحفظة': '📊 الإجمالي',
        'إجمالي العملاء': contact_by_port['إجمالي العملاء'].sum(),
        'تم التوصل': contact_by_port['تم التوصل'].sum(),
        'نسبة تم التوصل %': round(contact_by_port['تم التوصل'].sum() / contact_by_port['إجمالي العملاء'].sum() * 100, 1) if contact_by_port['إجمالي العملاء'].sum() > 0 else 0.0,
        'لا يرد ومغلق': contact_by_port['لا يرد ومغلق'].sum(),
        'نسبة لا يرد ومغلق %': round(contact_by_port['لا يرد ومغلق'].sum() / contact_by_port['إجمالي العملاء'].sum() * 100, 1) if contact_by_port['إجمالي العملاء'].sum() > 0 else 0.0,
        'عدم توصل - أخرى': contact_by_port['عدم توصل - أخرى'].sum(),
    }
    contact_table_display = pd.concat([contact_by_port, pd.DataFrame([cnt_tot_row])], ignore_index=True)
else:
    contact_table_display = pd.DataFrame()

# ══════════════════════════════════════════════════════
#  حساب ملخص المحافظ الرئيسي
# ══════════════════════════════════════════════════════
port_col_name = DIST_PORTFOLIO if DIST_PORTFOLIO else '_portfolio'

if DIST_PORTFOLIO and DIST_CID and DIST_DEBT_AMT:
    dist_summary = df_dist_filtered.groupby(DIST_PORTFOLIO).agg(
        عدد_العملاء=(DIST_CID, 'nunique'),
        اجمالي_المديونية=(DIST_DEBT_AMT, 'sum')
    ).reset_index()
    dist_summary.columns = ['المحفظة', 'عدد العملاء', 'إجمالي المديونية']
else:
    dist_summary = pd.DataFrame(columns=['المحفظة', 'عدد العملاء', 'إجمالي المديونية'])

pay_by_port = df_pay_filtered.groupby('_portfolio').agg(
    اجمالي_التحصيل=(PAY_AMOUNT, 'sum')
).reset_index()
pay_by_port.columns = ['المحفظة', 'إجمالي التحصيل']

if PAY_DATE:
    today_pay = df_pay_filtered[df_pay_filtered['_pay_date'].dt.normalize() == today].groupby('_portfolio')[PAY_AMOUNT].sum().reset_index()
    today_pay.columns = ['المحفظة', 'التحصيل اليومي (اليوم)']
    yest_pay = df_pay_filtered[df_pay_filtered['_pay_date'].dt.normalize() == yesterday].groupby('_portfolio')[PAY_AMOUNT].sum().reset_index()
    yest_pay.columns = ['المحفظة', 'التحصيل اليومي (أمس)']
else:
    today_pay = pd.DataFrame(columns=['المحفظة', 'التحصيل اليومي (اليوم)'])
    yest_pay  = pd.DataFrame(columns=['المحفظة', 'التحصيل اليومي (أمس)'])

port_table = dist_summary.merge(pay_by_port, on='المحفظة', how='outer')
port_table = port_table.merge(today_pay, on='المحفظة', how='left')
port_table = port_table.merge(yest_pay,  on='المحفظة', how='left')
port_table = port_table.fillna(0)

port_table['نسبة التحصيل %'] = port_table.apply(
    lambda r: round(r['إجمالي التحصيل'] / r['إجمالي المديونية'] * 100, 1) if r.get('إجمالي المديونية', 0) > 0 else 0.0, axis=1
)

cols_order = ['المحفظة', 'عدد العملاء', 'إجمالي المديونية', 'إجمالي التحصيل',
              'التحصيل اليومي (اليوم)', 'التحصيل اليومي (أمس)', 'نسبة التحصيل %']
cols_order = [c for c in cols_order if c in port_table.columns]
port_table = port_table[cols_order].sort_values('إجمالي التحصيل', ascending=False)

total_row = {}
for col in cols_order:
    if col == 'المحفظة':
        total_row[col] = '📊 الإجمالي'
    elif col == 'نسبة التحصيل %':
        total_debt_all = port_table['إجمالي المديونية'].sum() if 'إجمالي المديونية' in port_table.columns else 0
        total_coll_all = port_table['إجمالي التحصيل'].sum() if 'إجمالي التحصيل' in port_table.columns else 0
        total_row[col] = round(total_coll_all / total_debt_all * 100, 1) if total_debt_all > 0 else 0.0
    else:
        total_row[col] = port_table[col].sum() if pd.api.types.is_numeric_dtype(port_table[col]) else ''

port_table_display = pd.concat([port_table, pd.DataFrame([total_row])], ignore_index=True)

# ── Top Download Button ──
try:
    from core.daily_excel_writer import generate_styled_daily_excel
except Exception:
    try:
        from STC_System.core.daily_excel_writer import generate_styled_daily_excel
    except Exception:
        import sys as _sys, os as _os
        _root = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), "..", ".."))
        if _root not in _sys.path:
            _sys.path.insert(0, _root)
        from core.daily_excel_writer import generate_styled_daily_excel

# Preparing DataFrames for Supervisors & Collectors
sup_col = PAY_SUP or DIST_SUP
if sup_col and sup_col in df_pay_filtered.columns:
    sup_df = df_pay_filtered.groupby(sup_col)[PAY_AMOUNT].sum().reset_index()
    sup_df.columns = ['المشرف', 'إجمالي التحصيل']
    sup_df = sup_df.sort_values('إجمالي التحصيل', ascending=False).reset_index(drop=True)
    sup_df.index = sup_df.index + 1
    sup_df['الترتيب'] = sup_df.index
    sup_tot = sup_df['إجمالي التحصيل'].sum()
    sup_df['المعدل %'] = (sup_df['إجمالي التحصيل'] / sup_tot * 100) if sup_tot > 0 else 0
    sup_df['#'] = sup_df['الترتيب'].apply(lambda i: {1: '🥇', 2: '🥈', 3: '🥉'}.get(i, f'#{i}'))
else:
    sup_df = pd.DataFrame()

col_col = PAY_COL or DIST_COL
if col_col and col_col in df_pay_filtered.columns:
    col_df = df_pay_filtered.groupby(col_col)[PAY_AMOUNT].sum().reset_index()
    col_df.columns = ['المحصل', 'إجمالي التحصيل']
    col_df = col_df.sort_values('إجمالي التحصيل', ascending=False).reset_index(drop=True)
    col_df.index = col_df.index + 1
    col_df['الترتيب'] = col_df.index
    col_tot = col_df['إجمالي التحصيل'].sum()
    col_df['المعدل %'] = (col_df['إجمالي التحصيل'] / col_tot * 100) if col_tot > 0 else 0
    col_df['#'] = col_df['الترتيب'].apply(lambda i: {1: '🥇', 2: '🥈', 3: '🥉', 4: '🏅', 5: '🏅'}.get(i, f'#{i}'))
else:
    col_df = pd.DataFrame()

# Build Excel Bytes
try:
    excel_report_bytes = generate_styled_daily_excel(
        port_table_display, sup_df, col_df, df_pay_filtered, report_date, contact_table=contact_table_display
    )
except Exception:
    output_buf = io.BytesIO()
    with pd.ExcelWriter(output_buf, engine='xlsxwriter') as wr:
        port_table_display.to_excel(wr, sheet_name='ملخص المحافظ', index=False)
        if not sup_df.empty:
            sup_df.to_excel(wr, sheet_name='أفضل المشرفين', index=False)
        if not col_df.empty:
            col_df.to_excel(wr, sheet_name='أفضل المحصلين', index=False)
        if contact_table_display is not None and not contact_table_display.empty:
            contact_table_display.to_excel(wr, sheet_name='حالات التوصل', index=False)
        df_pay_filtered.to_excel(wr, sheet_name='السدادات التفصيلية', index=False)
    excel_report_bytes = output_buf.getvalue()

st.markdown('<div class="section-header">📥 تحميل التقرير الشامل والشارتس (علوي)</div>', unsafe_allow_html=True)
c_dl_top1, c_dl_top2 = st.columns(2)

with c_dl_top1:
    st.download_button(
        label="📥 تحميل التقرير المنسق كاملاً (Excel مع الشارتس والتواصل ورتب المحصلين)",
        data=excel_report_bytes,
        file_name=f"التقرير_اليومي_فولو_اب_{report_date}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True,
        key="dl_top_excel_styled"
    )
with c_dl_top2:
    csv_data = port_table_display.to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        label="📊 تحميل ملخص المحافظ (CSV)",
        data=csv_data.encode('utf-8-sig'),
        file_name=f"ملخص_المحافظ_{report_date}.csv",
        mime="text/csv",
        use_container_width=True,
        key="dl_top_csv"
    )

# ══════════════════════════════════════════════════════
#  حساب KPIs الرئيسية
# ══════════════════════════════════════════════════════
total_collection = df_pay_filtered[PAY_AMOUNT].sum() if PAY_AMOUNT and PAY_AMOUNT in df_pay_filtered.columns else 0.0
today_collection = df_pay_filtered[df_pay_filtered['_pay_date'].dt.normalize() == today][PAY_AMOUNT].sum() if PAY_DATE and '_pay_date' in df_pay_filtered.columns else 0.0
yesterday_collection = df_pay_filtered[df_pay_filtered['_pay_date'].dt.normalize() == yesterday][PAY_AMOUNT].sum() if PAY_DATE and '_pay_date' in df_pay_filtered.columns else 0.0
total_debt = df_dist_filtered[DIST_DEBT_AMT].sum() if DIST_DEBT_AMT and DIST_DEBT_AMT in df_dist_filtered.columns else 0.0
total_customers = df_dist_filtered[DIST_CID].nunique() if DIST_CID and DIST_CID in df_dist_filtered.columns else len(df_dist_filtered)
collection_rate = (total_collection / total_debt * 100) if total_debt > 0 else 0.0
daily_delta = today_collection - yesterday_collection

st.markdown('<div class="section-header">📊 مؤشرات الأداء الرئيسية (KPIs)</div>', unsafe_allow_html=True)

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("👥 إجمالي العملاء",      f"{total_customers:,}")
k2.metric("💰 إجمالي المديونية",    f"{total_debt:,.0f} ﷼")
k3.metric("💵 إجمالي التحصيل",     f"{total_collection:,.0f} ﷼")
k4.metric("📅 تحصيل اليوم",        f"{today_collection:,.0f} ﷼", delta=f"{daily_delta:+,.0f} ﷼ عن أمس")
k5.metric("📈 نسبة التحصيل",       f"{collection_rate:.1f}%")
k6.metric("💳 عدد عمليات السداد",  f"{len(df_pay_filtered):,}")

st.markdown("---")

# ── Section: Contact Status KPIs & Summary ──
st.markdown('<div class="section-header">📞 مؤشرات وحالات التوصل وعدم التوصل (لا يرد ومغلق)</div>', unsafe_allow_html=True)

ck1, ck2, ck3 = st.columns(3)
ck1.metric("📞 تم التوصل", f"{cnt_contacted:,}", delta=f"{cnt_rate:.1f}% من الإجمالي")
ck2.metric("📵 لا يرد ومغلق", f"{cnt_no_ans_closed:,}", delta=f"{cnt_no_ans_pct:.1f}% من الإجمالي")
ck3.metric("📈 نسبة التوصل الإجمالية", f"{cnt_rate:.1f}%")

if not contact_table_display.empty:
    st.markdown("##### 📋 جدول تحليل حالات التوصل وعدم التوصل حسب المحفظة:")
    st.dataframe(
        contact_table_display.style.format({
            'إجمالي العملاء': '{:,.0f}',
            'تم التوصل': '{:,.0f}',
            'نسبة تم التوصل %': '{:.1f}%',
            'لا يرد ومغلق': '{:,.0f}',
            'نسبة لا يرد ومغلق %': '{:.1f}%',
            'عدم توصل - أخرى': '{:,.0f}'
        }),
        use_container_width=True, hide_index=True
    )

st.markdown("---")

# ══════════════════════════════════════════════════════
#  الجدول الأول: ملخص المحافظ
# ══════════════════════════════════════════════════════
st.markdown('<div class="section-header">📋 الجدول الأول: ملخص الأداء حسب المحفظة</div>', unsafe_allow_html=True)

# تنسيق
def format_port_table(df):
    fmt = {}
    for c in df.columns:
        if 'مديونية' in c or 'تحصيل' in c:
            fmt[c] = '{:,.0f}'
        elif '%' in c:
            fmt[c] = '{:.1f}%'
        elif 'عملاء' in c:
            fmt[c] = '{:,.0f}'
    return df.style.format(fmt, na_rep='0')

st.dataframe(format_port_table(port_table_display), use_container_width=True, hide_index=True, height=min(400, (len(port_table_display)+1)*38+40))

st.markdown("---")

# ══════════════════════════════════════════════════════
#  الشارتس
# ══════════════════════════════════════════════════════
st.markdown('<div class="section-header">📊 شارتس التحليل البياني</div>', unsafe_allow_html=True)

try:
    import plotly.express as px
    import plotly.graph_objects as go

    chart_df = port_table[port_table['المحفظة'] != '📊 الإجمالي'].copy()

    ch1, ch2 = st.columns(2)
    with ch1:
        if 'إجمالي التحصيل' in chart_df.columns and not chart_df.empty:
            fig1 = px.bar(
                chart_df.sort_values('إجمالي التحصيل', ascending=True),
                x='إجمالي التحصيل', y='المحفظة', orientation='h',
                title='💰 إجمالي التحصيل حسب المحفظة',
                color='إجمالي التحصيل',
                color_continuous_scale='Teal',
                text='إجمالي التحصيل'
            )
            fig1.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
            fig1.update_layout(
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                font_color='#a0e4cb', title_font_color='#00e5a0',
                showlegend=False, height=380
            )
            st.plotly_chart(fig1, use_container_width=True)

    with ch2:
        if 'نسبة التحصيل %' in chart_df.columns and not chart_df.empty:
            fig2 = px.bar(
                chart_df.sort_values('نسبة التحصيل %', ascending=False),
                x='المحفظة', y='نسبة التحصيل %',
                title='📈 نسبة التحصيل % حسب المحفظة',
                color='نسبة التحصيل %',
                color_continuous_scale='Viridis',
                text='نسبة التحصيل %'
            )
            fig2.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
            fig2.update_layout(
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                font_color='#a0e4cb', title_font_color='#00e5a0',
                showlegend=False, height=380
            )
            st.plotly_chart(fig2, use_container_width=True)

    # شارت الدونات للعملاء
    if 'عدد العملاء' in chart_df.columns and chart_df['عدد العملاء'].sum() > 0:
        ch3, ch4 = st.columns(2)
        with ch3:
            fig3 = px.pie(
                chart_df[chart_df['عدد العملاء'] > 0],
                names='المحفظة', values='عدد العملاء',
                title='👥 توزيع العملاء على المحافظ',
                hole=0.45,
                color_discrete_sequence=px.colors.sequential.Teal
            )
            fig3.update_layout(
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                font_color='#a0e4cb', title_font_color='#00e5a0', height=380
            )
            st.plotly_chart(fig3, use_container_width=True)

        with ch4:
            # شارت مقارنة المديونية vs التحصيل
            if 'إجمالي المديونية' in chart_df.columns and 'إجمالي التحصيل' in chart_df.columns:
                fig4 = go.Figure()
                fig4.add_trace(go.Bar(name='المديونية', x=chart_df['المحفظة'], y=chart_df['إجمالي المديونية'],
                                      marker_color='rgba(0,150,200,0.7)'))
                fig4.add_trace(go.Bar(name='التحصيل',  x=chart_df['المحفظة'], y=chart_df['إجمالي التحصيل'],
                                      marker_color='rgba(0,220,150,0.85)'))
                fig4.update_layout(
                    barmode='group', title='⚖️ المديونية مقابل التحصيل',
                    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                    font_color='#a0e4cb', title_font_color='#00e5a0',
                    legend=dict(font=dict(color='#a0e4cb')), height=380
                )
                st.plotly_chart(fig4, use_container_width=True)

except ImportError:
    st.warning("⚠️ مكتبة plotly غير مثبتة — سيتم عرض البيانات بدون شارتس بصرية.")

st.markdown("---")

# ══════════════════════════════════════════════════════
#  الجدول الثاني: أفضل المشرفين والمحصلين
# ══════════════════════════════════════════════════════
st.markdown('<div class="section-header">🏆 الجدول الثاني: ترتيب أفضل المشرفين وأفضل 5 محصلين</div>', unsafe_allow_html=True)

# Preparing DataFrames for Supervisors & Collectors
sup_col = PAY_SUP or DIST_SUP
if sup_col and sup_col in df_pay_filtered.columns:
    sup_df = df_pay_filtered.groupby(sup_col)[PAY_AMOUNT].sum().reset_index()
    sup_df.columns = ['المشرف', 'إجمالي التحصيل']
    sup_df = sup_df.sort_values('إجمالي التحصيل', ascending=False).reset_index(drop=True)
    sup_df.index = sup_df.index + 1
    sup_df['الترتيب'] = sup_df.index
    sup_tot = sup_df['إجمالي التحصيل'].sum()
    sup_df['المعدل %'] = (sup_df['إجمالي التحصيل'] / sup_tot * 100) if sup_tot > 0 else 0
    sup_df['#'] = sup_df['الترتيب'].apply(lambda i: {1: '🥇', 2: '🥈', 3: '🥉'}.get(i, f'#{i}'))
else:
    sup_df = pd.DataFrame()

col_col = PAY_COL or DIST_COL
if col_col and col_col in df_pay_filtered.columns:
    col_df = df_pay_filtered.groupby(col_col)[PAY_AMOUNT].sum().reset_index()
    col_df.columns = ['المحصل', 'إجمالي التحصيل']
    col_df = col_df.sort_values('إجمالي التحصيل', ascending=False).reset_index(drop=True)
    col_df.index = col_df.index + 1
    col_df['الترتيب'] = col_df.index
    col_tot = col_df['إجمالي التحصيل'].sum()
    col_df['المعدل %'] = (col_df['إجمالي التحصيل'] / col_tot * 100) if col_tot > 0 else 0
    col_df['#'] = col_df['الترتيب'].apply(lambda i: {1: '🥇', 2: '🥈', 3: '🥉', 4: '🏅', 5: '🏅'}.get(i, f'#{i}'))
else:
    col_df = pd.DataFrame()



tab1, tab2 = st.tabs(["👤 أفضل المشرفين", "⭐ أفضل 5 محصلين (Top 5 Collectors)"])

with tab1:
    if not sup_df.empty:
        try:
            st.dataframe(
                sup_df_show.style.format({'إجمالي التحصيل': '{:,.0f} ﷼', 'المعدل %': '{:.1f}%'})
                                 .background_gradient(subset=['إجمالي التحصيل'], cmap='Greens'),
                use_container_width=True, hide_index=True
            )
        except Exception:
            st.dataframe(
                sup_df_show.style.format({'إجمالي التحصيل': '{:,.0f} ﷼', 'المعدل %': '{:.1f}%'}),
                use_container_width=True, hide_index=True
            )

        try:
            fig_sup = px.bar(
                sup_df.head(10).sort_values('إجمالي التحصيل'),
                x='إجمالي التحصيل', y='المشرف', orientation='h',
                title='🏅 أفضل المشرفين في التحصيل',
                color='إجمالي التحصيل', color_continuous_scale='Teal',
                text='إجمالي التحصيل'
            )
            fig_sup.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
            fig_sup.update_layout(
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                font_color='#a0e4cb', title_font_color='#00e5a0',
                showlegend=False, height=min(450, len(sup_df.head(10))*45+80)
            )
            st.plotly_chart(fig_sup, use_container_width=True)
        except:
            pass
    else:
        st.info("⚠️ لم يتم اكتشاف عمود المشرف في السدادات.")

with tab2:
    if not col_df.empty:
        st.markdown("### ⭐ قائمة أفضل 5 محصلين أداءً في التحصيل (Top 5 Collectors):")
        top5_cols_show = col_df[['#', 'المحصل', 'إجمالي التحصيل', 'المعدل %']].head(5)

        try:
            st.dataframe(
                top5_cols_show.style.format({'إجمالي التحصيل': '{:,.0f} ﷼', 'المعدل %': '{:.1f}%'})
                                    .background_gradient(subset=['إجمالي التحصيل'], cmap='Greens'),
                use_container_width=True, hide_index=True
            )
        except Exception:
            st.dataframe(
                top5_cols_show.style.format({'إجمالي التحصيل': '{:,.0f} ﷼', 'المعدل %': '{:.1f}%'}),
                use_container_width=True, hide_index=True
            )

        try:
            fig_col = px.bar(
                col_df.head(5).sort_values('إجمالي التحصيل'),
                x='إجمالي التحصيل', y='المحصل', orientation='h',
                title='⭐ ترتيب أفضل 5 محصلين (Top 5 Collectors)',
                color='إجمالي التحصيل', color_continuous_scale='Viridis',
                text='إجمالي التحصيل'
            )
            fig_col.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
            fig_col.update_layout(
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                font_color='#a0e4cb', title_font_color='#00e5a0',
                showlegend=False, height=320
            )
            st.plotly_chart(fig_col, use_container_width=True)
        except:
            pass
    else:
        st.info("⚠️ لم يتم اكتشاف عمود المحصل في السدادات.")

st.markdown("---")

# ══════════════════════════════════════════════════════
#  تصدير التقرير السفلي
# ══════════════════════════════════════════════════════
st.markdown('<div class="section-header">📥 تصدير التقرير الكامل والشارتس (سفلي)</div>', unsafe_allow_html=True)

c_dl1, c_dl2 = st.columns(2)
with c_dl1:
    st.download_button(
        label="📥 تحميل التقرير المنسق كاملاً (Excel مع الشارتس وأفضل 5 محصلين)",
        data=excel_report_bytes,
        file_name=f"التقرير_اليومي_فولو_اب_{report_date}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True,
        key="dl_bottom_excel_styled"
    )
with c_dl2:
    st.download_button(
        label="📊 تحميل ملخص المحافظ (CSV)",
        data=csv_data.encode('utf-8-sig'),
        file_name=f"ملخص_المحافظ_{report_date}.csv",
        mime="text/csv",
        use_container_width=True,
        key="dl_bottom_csv"
    )

st.markdown(f"""
<div style="text-align:center; margin-top:30px; color:#2d6a4f; font-size:12px;">
    📈 التقرير اليومي — فولو اب | تاريخ التقرير: {report_date} | نظام مهاره للتحصيل
</div>
""", unsafe_allow_html=True)

