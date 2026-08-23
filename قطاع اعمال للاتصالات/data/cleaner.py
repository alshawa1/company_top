import pandas as pd
from utils import date_utils, number_utils

def clean_portfolio(raw_df: pd.DataFrame, column_map: dict) -> pd.DataFrame:
    df = raw_df.copy()
    
    # Strip whitespace for string columns
    for col in df.select_dtypes(['object']).columns:
        df[col] = df[col].apply(lambda x: str(x).strip() if pd.notna(x) else x)
    
    # Map & convert numeric columns to float explicitly
    num_col_keys = ['debt_amount', 'paid_doc', 'remaining_doc', 'mablagh_elmedyonya', 'مبلغ الميدونية', 'مبلغ المديونية', 'السدادات الموثقة', 'متبقي سداد موثق']
    for key in num_col_keys:
        actual_col = column_map.get(key, key)
        if actual_col in df.columns:
            df[actual_col] = pd.to_numeric(
                df[actual_col].astype(str).str.replace(',', '', regex=False).str.extract(r'(-?\d+\.?\d*)')[0],
                errors='coerce'
            ).fillna(0.0)

    # Ensure mapped numeric columns exist & are numeric
    debt_col = column_map.get('debt_amount') or column_map.get('مبلغ الميدونية') or ('مبلغ المديونية' if 'مبلغ المديونية' in df.columns else 'مبلغ الميدونية')
    if debt_col in df.columns:
        df[debt_col] = pd.to_numeric(df[debt_col], errors='coerce').fillna(0.0)
        
    paid_col = column_map.get('paid_doc') or column_map.get('السدادات الموثقة') or 'السدادات الموثقة'
    if paid_col in df.columns:
        df[paid_col] = pd.to_numeric(df[paid_col], errors='coerce').fillna(0.0)
        
    rem_col = column_map.get('remaining_doc') or column_map.get('متبقي سداد موثق') or 'متبقي سداد موثق'
    if rem_col in df.columns:
        df[rem_col] = pd.to_numeric(df[rem_col], errors='coerce').fillna(0.0)

    def get_col(key):
        col_name = column_map.get(key)
        if col_name and col_name in df.columns:
            return df[col_name]
        return pd.Series(dtype=object)

    df['_customer_id'] = get_col('رقم الهوية').apply(lambda x: str(x) if pd.notna(x) else '')
    df['_debt_amount'] = get_col('مبلغ الميدونية').apply(number_utils.clean_float)
    df['_paid_doc'] = get_col('السدادات الموثقة').apply(number_utils.clean_float)
    df['_remaining_doc'] = get_col('متبقي سداد موثق').apply(number_utils.clean_float)
    df['_portfolio'] = get_col('المحافظ').apply(lambda x: str(x) if pd.notna(x) else '')
    df['_collector'] = get_col('المحصل').apply(lambda x: str(x) if pd.notna(x) else '')
    df['_supervisor'] = get_col('المشرف').apply(lambda x: str(x) if pd.notna(x) else '')
    df['_main_status'] = get_col('الحالة الرئيسية').apply(lambda x: str(x) if pd.notna(x) else '')
    df['_sub_status'] = get_col('الحالة الفرعية').apply(lambda x: str(x) if pd.notna(x) else '')
    df['_followup_date'] = get_col('تاريخ المتابعة').apply(date_utils.normalize_date)
    
    return df

def clean_payment_file(raw_df: pd.DataFrame, column_map: dict) -> pd.DataFrame:
    df = raw_df.copy()
    
    def get_col(key):
        col_name = column_map.get(key)
        if col_name and col_name in df.columns:
            return df[col_name]
        return pd.Series(dtype=object)
    
    df['_customer_id'] = get_col('رقم الهوية').apply(lambda x: str(x) if pd.notna(x) else '')
    df['_payment_amount'] = get_col('مبلغ السداد').apply(number_utils.clean_float)
    df['_payment_date'] = get_col('تاريخ السداد').apply(date_utils.normalize_date)
    
    # Also clean actual columns in df
    pay_col = column_map.get('مبلغ السداد', 'مبلغ السداد')
    if pay_col in df.columns:
        df[pay_col] = pd.to_numeric(df[pay_col], errors='coerce').fillna(0.0)

    return df
