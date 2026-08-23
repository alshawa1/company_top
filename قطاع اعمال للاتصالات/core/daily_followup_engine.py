import pandas as pd
import numpy as np
import io
from datetime import date, timedelta
import streamlit as st

def detect_col(df, candidates):
    if df is None or df.empty:
        return None
    cols_lower = {c.strip().lower(): c for c in df.columns}
    for c in candidates:
        if c.strip().lower() in cols_lower:
            return cols_lower[c.strip().lower()]
    for c in candidates:
        for col in df.columns:
            if c.strip() in str(col):
                return col
    return None

def process_daily_followup(df_master, df_dist, df_pay, column_overrides=None):
    """
    Core engine to link Master Portfolio, Distributed Portfolio, and Payments Sheet.
    Adds 'المحافظ' to payments via Debt ID matching, aggregates portfolio metrics,
    and returns DataFrames for portfolio summary, top supervisors, top collectors, and KPI dict.
    """
    if column_overrides is None:
        column_overrides = {}

    # Master Portfolio columns
    m_debt_id = column_overrides.get('m_debt_id') or detect_col(df_master, ["رقم المديونية", "رقم المديوني", "debt_id"])
    m_port    = column_overrides.get('m_port')    or detect_col(df_master, ["المحفظة", "المحافظ", "محفظه", "portfolio"])
    
    # Distributed Portfolio columns
    d_debt_id = column_overrides.get('d_debt_id') or detect_col(df_dist, ["رقم المديونية", "رقم المديوني", "debt_id"])
    d_cid     = column_overrides.get('d_cid')     or detect_col(df_dist, ["رقم الهوية", "رقم هوية", "الهوية", "customer_id", "civil_id"])
    d_amt     = column_overrides.get('d_amt')     or detect_col(df_dist, ["مبلغ المديونية", "مبلغ الميدونيه", "مبلغ الميدونية", "debt_amount", "المديونية"])
    d_port    = column_overrides.get('d_port')    or detect_col(df_dist, ["المحفظة", "المحافظ", "محفظه", "portfolio"])
    d_sup     = column_overrides.get('d_sup')     or detect_col(df_dist, ["المشرف", "اسم المشرف", "supervisor"])
    d_col     = column_overrides.get('d_col')     or detect_col(df_dist, ["المحصل", "اسم المحصل", "collector"])

    # Payments Sheet columns
    p_debt_id = column_overrides.get('p_debt_id') or detect_col(df_pay, ["رقم المديونية", "رقم المديوني", "debt_id"])
    p_amt     = column_overrides.get('p_amt')     or detect_col(df_pay, ["مبلغ السداد", "مبلغ الدفع", "payment_amount", "المبلغ"])
    p_date    = column_overrides.get('p_date')    or detect_col(df_pay, ["تاريخ السداد", "تاريخ الدفع", "payment_date", "التاريخ"])
    p_sup     = column_overrides.get('p_sup')     or detect_col(df_pay, ["المشرف", "اسم المشرف", "supervisor"])
    p_col     = column_overrides.get('p_col')     or detect_col(df_pay, ["اسم المحصل", "المحصل", "collector"])

    # 1. Clean Payments
    df_pay_clean = df_pay.copy()
    if p_amt and p_amt in df_pay_clean.columns:
        df_pay_clean['m_amt'] = pd.to_numeric(df_pay_clean[p_amt], errors='coerce').fillna(0)
    else:
        df_pay_clean['m_amt'] = 0.0

    if p_date and p_date in df_pay_clean.columns:
        df_pay_clean['_pay_date'] = pd.to_datetime(df_pay_clean[p_date], errors='coerce', dayfirst=False)
        if df_pay_clean['_pay_date'].isna().sum() > len(df_pay_clean) * 0.3:
            df_pay_clean['_pay_date'] = pd.to_datetime(df_pay_clean[p_date], errors='coerce', dayfirst=True)
    else:
        df_pay_clean['_pay_date'] = pd.NaT

    # 2. Build debt ID -> Portfolio lookup from Master Portfolio
    debt_to_port = {}
    if m_debt_id and m_port and m_debt_id in df_master.columns and m_port in df_master.columns:
        m_sub = df_master[[m_debt_id, m_port]].dropna()
        debt_to_port = dict(zip(m_sub[m_debt_id].astype(str).str.strip(), m_sub[m_port].astype(str).str.strip()))
    
    # Also fallback to Distributed Portfolio if master doesn't have it
    if d_debt_id and d_port and d_debt_id in df_dist.columns and d_port in df_dist.columns:
        d_sub = df_dist[[d_debt_id, d_port]].dropna()
        for did, prt in zip(d_sub[d_debt_id].astype(str).str.strip(), d_sub[d_port].astype(str).str.strip()):
            if did not in debt_to_port:
                debt_to_port[did] = prt

    # Map portfolio to payments
    if p_debt_id and p_debt_id in df_pay_clean.columns:
        df_pay_clean['المحافظ'] = df_pay_clean[p_debt_id].astype(str).str.strip().map(debt_to_port).fillna('غير محدد')
    else:
        df_pay_clean['المحافظ'] = 'غير محدد'

    # Clean Distributed Portfolio
    df_dist_clean = df_dist.copy()
    if d_amt and d_amt in df_dist_clean.columns:
        df_dist_clean['m_debt'] = pd.to_numeric(df_dist_clean[d_amt], errors='coerce').fillna(0)
    else:
        df_dist_clean['m_debt'] = 0.0

    if d_cid and d_cid in df_dist_clean.columns:
        df_dist_clean['m_cid'] = df_dist_clean[d_cid].astype(str).str.strip()
    else:
        df_dist_clean['m_cid'] = 'N/A'

    if d_port and d_port in df_dist_clean.columns:
        df_dist_clean['m_port'] = df_dist_clean[d_port].astype(str).str.strip()
    else:
        df_dist_clean['m_port'] = 'غير محدد'

    return {
        'df_pay': df_pay_clean,
        'df_dist': df_dist_clean,
        'cols': {
            'm_debt_id': m_debt_id, 'm_port': m_port,
            'd_debt_id': d_debt_id, 'd_cid': d_cid, 'd_amt': d_amt, 'd_port': d_port, 'd_sup': d_sup, 'd_col': d_col,
            'p_debt_id': p_debt_id, 'p_amt': p_amt, 'p_date': p_date, 'p_sup': p_sup, 'p_col': p_col
        }
    }

def classify_contact_status_series(df, main_col=None, sub_col=None, note_col=None):
    """
    Vectorized classification based primarily on 'الحالة الرئيسية' (Main Status) into:
    - تم التوصل (Contacted)
    - لا يرد ومغلق (No Answer & Closed)
    - عدم توصل - أخرى (Other non-contact)
    """
    n = len(df)
    status_vec = np.full(n, 'عدم توصل - أخرى', dtype=object)

    main_str = df[main_col].astype(str).str.strip().str.lower() if main_col and main_col in df.columns else pd.Series(['']*n)
    sub_str  = df[sub_col].astype(str).str.strip().str.lower()   if sub_col and sub_col in df.columns   else pd.Series(['']*n)
    note_str = df[note_col].astype(str).str.strip().str.lower()  if note_col and note_col in df.columns  else pd.Series(['']*n)

    combined = main_str + " " + sub_str + " " + note_str

    # 1. Combined No Answer & Closed (لا يرد ومغلق)
    no_ans_closed_kw = [
        'لا يرد', 'لايرد', 'ما يرد', 'مايرد', 'لم يرد', 'لا يوجد رد', 'انشغال', 'busy', 'no answer', 'لم يترد', 'ما رد',
        'مغلق', 'مقفل', 'مقطوع', 'خارج الخدمة', 'خارج التغطية', 'غير مستعمل', 'رقم خطأ', 'رقم خاطئ', 'الرقم لا يخص', 'رسالة صوتية', 'بريد صوتي', 'switched off', 'unreachable'
    ]
    pattern_no_ans_closed = '|'.join(no_ans_closed_kw)
    mask_no_ans_closed = combined.str.contains(pattern_no_ans_closed, regex=True, na=False)

    # 2. Contacted (تم التوصل)
    contact_kw = ['وعد', 'سداد', 'رد', 'مهلة', 'مهله', 'موافق', 'اعادة الاتصال', 'إعادة الاتصال', 'عميل متعاون', 'تحدثت', 'تواصلت', 'تم التواصل', 'تم السداد', 'سداد جزئي', 'اعتراض', 'استفسار', 'قسط', 'تسوية']
    pattern_contact = '|'.join(contact_kw)
    mask_contact = combined.str.contains(pattern_contact, regex=True, na=False)

    # Apply precedence: No Answer & Closed -> Contacted
    status_vec[mask_no_ans_closed] = 'لا يرد ومغلق'
    status_vec[mask_contact] = 'تم التوصل'

    return status_vec
