# -*- coding: utf-8 -*-
import streamlit as st
import sys
import os

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

st.set_page_config(
    page_title="مهاره سيستم - منصة العمليات الموحدة",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 🎨 DESIGN SYSTEM & GLASSMORPHISM STYLES (RTL - CAIRO)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;600;700;900&display=swap');
    
    html, body, [class*="css"], .stApp {
        font-family: 'Cairo', sans-serif !important;
        direction: RTL;
        background-color: #0b0f19 !important;
    }
    
    .stApp {
        background: radial-gradient(circle at 20% 20%, rgba(124, 58, 237, 0.15) 0%, transparent 40%),
                    radial-gradient(circle at 80% 80%, rgba(16, 185, 129, 0.1) 0%, transparent 40%),
                    #0b0f19 !important;
        color: #f1f5f9 !important;
    }
    
    .login-wrapper {
        display: flex;
        justify-content: center;
        align-items: center;
        padding-top: 40px;
        padding-bottom: 20px;
    }
    
    .login-card {
        background: linear-gradient(145deg, rgba(30, 20, 60, 0.7), rgba(15, 23, 42, 0.8));
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(168, 85, 247, 0.3);
        border-radius: 24px;
        padding: 45px 40px;
        max-width: 460px;
        width: 100%;
        text-align: center;
        box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5), 0 0 30px rgba(124, 58, 237, 0.25);
    }
    
    .brand-badge {
        display: inline-block;
        background: linear-gradient(135deg, rgba(124, 58, 237, 0.2), rgba(168, 85, 247, 0.2));
        border: 1px solid rgba(168, 85, 247, 0.4);
        color: #c084fc;
        padding: 6px 16px;
        border-radius: 20px;
        font-size: 13px;
        font-weight: 700;
        margin-bottom: 16px;
    }
    
    .logo-text {
        font-size: 52px;
        font-weight: 900;
        background: linear-gradient(135deg, #c084fc 0%, #a855f7 50%, #7c3aed 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        line-height: 1.1;
    }
    
    .subtitle {
        color: #94a3b8;
        font-size: 16px;
        margin-top: 8px;
        margin-bottom: 20px;
        font-weight: 600;
    }
    
    .purple-divider {
        height: 2px;
        background: linear-gradient(90deg, transparent, #a855f7, #38bdf8, #a855f7, transparent);
        border-radius: 2px;
        margin: 22px 0;
    }
    
    .sector-chips {
        display: flex;
        justify-content: center;
        gap: 12px;
        margin-bottom: 24px;
    }
    
    .chip {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 6px 14px;
        border-radius: 12px;
        font-size: 13px;
        color: #cbd5e1;
    }
    
    .sidebar-logo-card {
        background: linear-gradient(135deg, rgba(124, 58, 237, 0.2), rgba(168, 85, 247, 0.1));
        border: 1px solid rgba(168, 85, 247, 0.3);
        border-radius: 16px;
        padding: 16px;
        text-align: center;
        margin-bottom: 20px;
    }
    
    .sidebar-logo-title {
        font-size: 28px;
        font-weight: 900;
        background: linear-gradient(135deg, #c084fc 0%, #a855f7 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .sidebar-logo-sub {
        font-size: 12px;
        color: #94a3b8;
    }
    
    .footer {
        color: #64748b;
        font-size: 13px;
        margin-top: 24px;
    }
    </style>
""", unsafe_allow_html=True)

# 🔐 AUTHENTICATION GATE
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "sector" not in st.session_state:
    st.session_state.sector = None

if not st.session_state.authenticated:
    col1, col2, col3 = st.columns([1, 1.4, 1])
    with col2:
        st.markdown("""
            <div class="login-wrapper">
                <div class="login-card">
                    <div class="brand-badge">✨ PLATFORM 2026</div>
                    <div class="logo-text">مهاره</div>
                    <div class="subtitle">نظام إدارة عمليات التحصيل الموحد</div>
                    <div class="purple-divider"></div>
                    <div class="sector-chips">
                        <div class="chip">👥 قطاع الأفراد</div>
                        <div class="chip">🏢 قطاع الأعمال</div>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        pwd = st.text_input("كلمة المرور", type="password", label_visibility="collapsed", placeholder="أدخل كلمة المرور لدخول النظام...")
        if st.button("🔓 دخول المنصة", use_container_width=True):
            if pwd in ("333", "افراد", "1234"):
                st.session_state.authenticated = True
                st.session_state.sector = "افراد"
                st.session_state.sector_display = "قطاع الأفراد"
                st.rerun()
            elif pwd in ("444", "اعمال"):
                st.session_state.authenticated = True
                st.session_state.sector = "اعمال"
                st.session_state.sector_display = "قطاع الأعمال"
                st.rerun()
            else:
                st.error("❌ كلمة المرور غير صحيحة. حاول مرة أخرى.")
        
        st.markdown('<div class="footer" style="text-align:center;">شركة مهاره لتحصيل الديون © 2026 جميع الحقوق محفوظة</div>', unsafe_allow_html=True)
    st.stop()

# 🚀 LOGGED IN - SIDEBAR & SYSTEM ROUTING
with st.sidebar:
    st.markdown(f"""
        <div class="sidebar-logo-card">
            <div class="sidebar-logo-title">مهاره</div>
            <div class="sidebar-logo-sub">نظام التحصيل الموحد</div>
            <div style="margin-top:8px;">
                <span class="chip">{'👥 ' if st.session_state.sector == 'افراد' else '🏢 '}{st.session_state.get('sector_display', 'النظام')}</span>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    if st.button("🚪 تسجيل الخروج", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.sector = None
        st.rerun()

# Run the selected sector app
if st.session_state.sector == "افراد":
    import افراد_app
    افراد_app.run_afrad_app()
elif st.session_state.sector == "اعمال":
    import اعمال_app
    اعمال_app.run_aamal_app()
