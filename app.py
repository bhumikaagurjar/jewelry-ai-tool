import streamlit as st
import pandas as pd
import numpy as np
import pickle
import os
import glob
from PIL import Image
import torch
import torch.nn as nn
from transformers import AutoImageProcessor, AutoModel, ViTModel
from torchvision import transforms, models
import io
import base64
from datetime import datetime
from sklearn.metrics.pairwise import cosine_similarity
import time
import shutil
import requests
from io import BytesIO
import smtplib
import random
import string
import json
import hashlib
import plotly.express as px
import plotly.graph_objects as go
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Page config - MUST BE FIRST STREAMLIT COMMAND
st.set_page_config(
    page_title="Kanishka Jewellers Pvt Ltd - Design Studio", 
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Email configuration for password reset
EMAIL_CONFIG = {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": "kanishkajewellers@gmail.com",  # Update with your email
    "sender_password": "your_app_password"  # Update with your app password
}

# Password file
PASSWORD_FILE = "excel_data/admin_password.json"
OTP_FILE = "excel_data/otp_storage.json"

# Initialize theme in session state
if 'theme' not in st.session_state:
    st.session_state.theme = "🌙 Dark Theme"
    st.session_state.bg_color = "#1A2634"
    st.session_state.card_bg = "#0F1A24"
    st.session_state.text_color = "#FFFFFF"
    st.session_state.border_color = "#2A3A4A"
    st.session_state.accent_gold = "#D4AF37"
    st.session_state.accent_purple = "#9D7EBD"

# Display logo at center top
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    if os.path.exists("header_logo_1764154359.png"):
        st.image("header_logo_1764154359.png", use_container_width=True)
    else:
        st.markdown("<h1 style='text-align: center; color: #D4AF37; font-size: 2.5rem; margin-bottom: 0; text-shadow: 0 2px 5px rgba(0,0,0,0.3);'>KANISHKA</h1>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center; color: #FFFFFF; font-size: 2.5rem; margin-top: -0.5rem; text-shadow: 0 2px 5px rgba(0,0,0,0.3);'>JEWELLERS</h1>", unsafe_allow_html=True)
    
    # Company Title
    st.markdown("<h2 style='text-align: center; color: #FFFFFF; font-size: 1.8rem; margin-top: 0.5rem; margin-bottom: 0.2rem; font-family: Georgia, serif; text-shadow: 0 2px 4px rgba(0,0,0,0.3);'>Kanishka Jewellers Pvt Ltd</h2>", unsafe_allow_html=True)
    
    # AI-Powered Design Studio line
    st.markdown("<p style='text-align: center; color: #D4AF37; font-size: 1.2rem; margin-bottom: 0.5rem; font-weight: 500; letter-spacing: 1px; text-shadow: 0 2px 4px rgba(0,0,0,0.3);'>✨ AI-Powered Design Studio ✨</p>", unsafe_allow_html=True)

# Add a divider
st.markdown("<hr style='border: 1px solid #D4AF37; opacity: 0.3; box-shadow: 0 2px 5px rgba(0,0,0,0.2);'>", unsafe_allow_html=True)

# Helper function to get base64 encoded logo
def get_base64_logo():
    if os.path.exists("header_logo_1764154359.png"):
        with open("header_logo_1764154359.png", "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""

# Password management functions
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def load_admin_password():
    if os.path.exists(PASSWORD_FILE):
        with open(PASSWORD_FILE, 'r') as f:
            data = json.load(f)
            return data.get('password', hash_password('admin123'))
    else:
        # Create default password
        default_hash = hash_password('admin123')
        with open(PASSWORD_FILE, 'w') as f:
            json.dump({'password': default_hash}, f)
        return default_hash

def save_admin_password(new_password):
    hashed = hash_password(new_password)
    with open(PASSWORD_FILE, 'w') as f:
        json.dump({'password': hashed}, f)
    return hashed

def verify_password(password):
    stored_hash = load_admin_password()
    return hash_password(password) == stored_hash

# OTP functions
def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

def save_otp(email, otp):
    otp_data = {
        'email': email,
        'otp': otp,
        'timestamp': time.time(),
        'expires': time.time() + 300  # 5 minutes expiry
    }
    
    # Load existing OTPs
    if os.path.exists(OTP_FILE):
        with open(OTP_FILE, 'r') as f:
            all_otps = json.load(f)
    else:
        all_otps = {}
    
    # Clean expired OTPs
    current_time = time.time()
    all_otps = {k: v for k, v in all_otps.items() if v.get('expires', 0) > current_time}
    
    # Save new OTP
    all_otps[otp] = otp_data
    
    with open(OTP_FILE, 'w') as f:
        json.dump(all_otps, f)
    
    return otp

def verify_otp(email, otp):
    if not os.path.exists(OTP_FILE):
        return False
    
    with open(OTP_FILE, 'r') as f:
        all_otps = json.load(f)
    
    if otp in all_otps:
        otp_data = all_otps[otp]
        if otp_data['email'] == email and otp_data['expires'] > time.time():
            # Remove used OTP
            del all_otps[otp]
            with open(OTP_FILE, 'w') as f:
                json.dump(all_otps, f)
            return True
    
    return False

def send_otp_email(email, otp):
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG['sender_email']
        msg['To'] = email
        msg['Subject'] = "Password Reset OTP - Kanishka Jewellers"
        
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 10px; padding: 30px; box-shadow: 0 4px 10px rgba(0,0,0,0.1);">
                <div style="text-align: center; margin-bottom: 30px;">
                    <h1 style="color: #D4AF37; margin: 0;">KANISHKA JEWELLERS</h1>
                    <p style="color: #5E2A84; font-size: 1.1rem;">Password Reset Request</p>
                </div>
                
                <p style="color: #333333; font-size: 1rem; line-height: 1.6;">Hello,</p>
                
                <p style="color: #333333; font-size: 1rem; line-height: 1.6;">
                    We received a request to reset your password for the Kanishka Jewellers Design Studio. 
                    Use the OTP below to complete your password reset:
                </p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <div style="background: linear-gradient(135deg, #5E2A84, #D4AF37); padding: 20px; border-radius: 10px;">
                        <h2 style="color: #ffffff; font-size: 2.5rem; letter-spacing: 5px; margin: 0;">{otp}</h2>
                    </div>
                </div>
                
                <p style="color: #333333; font-size: 1rem; line-height: 1.6;">
                    This OTP will expire in <strong>5 minutes</strong>.
                </p>
                
                <p style="color: #333333; font-size: 1rem; line-height: 1.6;">
                    If you didn't request this password reset, please ignore this email.
                </p>
                
                <hr style="border: 1px solid #D4AF37; margin: 30px 0;">
                
                <p style="color: #666666; font-size: 0.9rem; text-align: center;">
                    Kanishka Jewellers Pvt Ltd<br>
                    ✨ AI-Powered Design Studio ✨
                </p>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        # Send email
        server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
        server.starttls()
        server.login(EMAIL_CONFIG['sender_email'], EMAIL_CONFIG['sender_password'])
        server.send_message(msg)
        server.quit()
        
        return True
    except Exception as e:
        st.error(f"Failed to send email: {str(e)}")
        return False

# Category Colors - Different for each category
CATEGORY_COLORS = {
    "Ring": "#FF6B6B",        # Coral Red
    "Necklace": "#4ECDC4",     # Turquoise
    "Earring": "#45B7D1",      # Sky Blue
    "Bracelet": "#96CEB4",     # Sage Green
    "Pendant": "#FFE66D",      # Mustard Yellow
    "Brooch": "#FF9F1C",       # Orange
    "Cufflink": "#C77DFF",     # Light Purple
    "Other": "#A8A8A8"         # Grey
}

# Company Information
COMPANY_NAME = "Kanishka Jewellers Pvt Ltd"
COMPANY_PHONE = "+91 9829194093 and +91 9680434748"
COMPANY_EMAIL = "kanishkajewellers@gmail.com"
COMPANY_WEBSITE = "www.kanishkajewellers.com"

# Import expert detector
try:
    from expert_detector import ExpertJewelryDetector
    EXPERT_AVAILABLE = True
except ImportError:
    EXPERT_AVAILABLE = False
    st.warning("⚠️ expert_detector.py not found. Using standard mode.")

# Create necessary folders
os.makedirs("images", exist_ok=True)
os.makedirs("embeddings", exist_ok=True)
os.makedirs("excel_data", exist_ok=True)
os.makedirs("temp_uploads", exist_ok=True)

# Custom CSS with dynamic theme colors
st.markdown(f"""
<style>
    /* Main background */
    .stApp {{
        background-color: {st.session_state.bg_color};
    }}
    
    /* Main content area */
    .main > div {{
        background-color: {st.session_state.bg_color};
    }}
    
    /* Sidebar styling */
    .css-1d391kg, .css-1wrcr25, section[data-testid="stSidebar"] {{
        background-color: {st.session_state.card_bg} !important;
    }}
    
    /* All text */
    .stMarkdown, p, li, span, .stText, .stCaption, .stAlert {{
        color: {st.session_state.text_color} !important;
    }}
    
    /* Headers */
    h1, h2, h3, h4, h5, h6 {{
        color: {st.session_state.text_color} !important;
    }}
    
    /* Main title styling */
    .main-title {{
        font-size: 2.2rem;
        font-weight: 700;
        color: {st.session_state.text_color};
        text-align: center;
        margin-bottom: 0.2rem;
        font-family: 'Georgia', serif;
    }}
    
    /* Subtitle styling */
    .sub-title {{
        font-size: 1rem;
        color: {st.session_state.accent_gold};
        text-align: center;
        margin-bottom: 1rem;
        font-weight: 500;
    }}
    
    /* Tagline styling */
    .tagline {{
        font-size: 0.9rem;
        color: {st.session_state.accent_gold};
        text-align: center;
        margin-bottom: 1.5rem;
        font-style: italic;
    }}
    
    /* Logo container */
    .logo-container {{
        display: flex;
        justify-content: center;
        align-items: center;
        margin: 0.5rem 0;
    }}
    
    /* Header with gold underline */
    .gold-header {{
        font-size: 1.8rem;
        color: {st.session_state.accent_gold};
        text-align: center;
        position: relative;
        margin-bottom: 2rem;
        font-weight: 600;
    }}
    
    .gold-header::after {{
        content: '';
        position: absolute;
        bottom: -10px;
        left: 50%;
        transform: translateX(-50%);
        width: 100px;
        height: 3px;
        background: linear-gradient(90deg, {st.session_state.accent_gold}, {st.session_state.accent_purple});
    }}
    
    /* Contact info styling */
    .contact-info {{
        background: {st.session_state.card_bg};
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid {st.session_state.accent_gold};
        margin: 0.5rem 0;
        font-size: 0.9rem;
    }}
    
    .contact-item {{
        padding: 0.2rem 0;
        color: {st.session_state.text_color};
    }}
    
    .contact-icon {{
        color: {st.session_state.accent_gold};
        font-weight: bold;
        margin-right: 8px;
    }}
    
    /* Card styling for designs */
    .design-card {{
        background: {st.session_state.card_bg};
        border-radius: 10px;
        padding: 1.2rem;
        box-shadow: 0 5px 15px rgba(0, 0, 0, 0.3);
        transition: all 0.3s ease;
        margin-bottom: 1rem;
        border: 1px solid {st.session_state.border_color};
        position: relative;
        overflow: hidden;
    }}
    
    .design-card::before {{
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, {st.session_state.accent_gold}, {st.session_state.accent_purple});
    }}
    
    .design-card:hover {{
        transform: translateY(-5px);
        box-shadow: 0 10px 25px rgba(212, 175, 55, 0.2);
        border-color: {st.session_state.accent_gold};
    }}
    
    .design-card h4, .design-card p {{
        color: {st.session_state.text_color} !important;
    }}
    
    /* Admin panel styling */
    .admin-panel {{
        background: linear-gradient(135deg, {st.session_state.accent_purple}, {st.session_state.accent_gold});
        padding: 1.5rem;
        border-radius: 10px;
        color: {st.session_state.text_color};
        margin-bottom: 1.5rem;
        animation: slideIn 0.5s ease;
        box-shadow: 0 10px 20px rgba(0,0,0,0.3);
    }}
    
    .admin-panel h2, .admin-panel p {{
        color: {st.session_state.text_color} !important;
    }}
    
    /* Button styling */
    .stButton > button {{
        border-radius: 25px;
        font-weight: 600;
        transition: all 0.3s ease;
        background: linear-gradient(90deg, {st.session_state.accent_purple}, {st.session_state.accent_gold});
        color: {st.session_state.text_color} !important;
        border: none;
        padding: 0.4rem 1.5rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        font-size: 0.9rem;
    }}
    
    .stButton > button:hover {{
        transform: scale(1.05);
        box-shadow: 0 8px 15px rgba(212, 175, 55, 0.3);
    }}
    
    /* Upload area styling */
    .upload-area {{
        border: 2px dashed {st.session_state.accent_gold};
        border-radius: 15px;
        padding: 1.5rem;
        text-align: center;
        background: {st.session_state.card_bg};
        transition: all 0.3s ease;
    }}
    
    .upload-area:hover {{
        border-color: {st.session_state.accent_purple};
        background: {st.session_state.bg_color};
    }}
    
    .upload-area p, .upload-area span {{
        color: {st.session_state.text_color} !important;
    }}
    
    /* File uploader styling */
    .stFileUploader > div > div {{
        background-color: {st.session_state.card_bg} !important;
        border-color: {st.session_state.accent_gold} !important;
        color: {st.session_state.text_color} !important;
    }}
    
    .stFileUploader > div > div:hover {{
        border-color: {st.session_state.accent_purple} !important;
    }}
    
    .stFileUploader > div > div > div {{
        color: {st.session_state.text_color} !important;
    }}
    
    .stFileUploader > div > div > button {{
        background: linear-gradient(90deg, {st.session_state.accent_purple}, {st.session_state.accent_gold}) !important;
        color: {st.session_state.text_color} !important;
        border: none !important;
    }}
    
    /* Success message styling */
    .success-msg {{
        background: linear-gradient(90deg, {st.session_state.accent_purple}, {st.session_state.accent_gold});
        color: {st.session_state.text_color};
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        animation: slideIn 0.5s ease;
        font-weight: 600;
    }}
    
    @keyframes slideIn {{
        from {{
            transform: translateY(-20px);
            opacity: 0;
        }}
        to {{
            transform: translateY(0);
            opacity: 1;
        }}
    }}
    
    @keyframes fadeIn {{
        from {{ opacity: 0; }}
        to {{ opacity: 1; }}
    }}
    
    /* Category badges */
    .category-badge {{
        display: inline-block;
        padding: 0.3rem 1rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-right: 0.3rem;
        margin-bottom: 0.3rem;
        color: #FFFFFF;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }}
    
    /* Similarity percentage styling */
    .similarity-high {{
        color: {st.session_state.accent_gold};
        font-weight: 700;
        font-size: 1.1rem;
    }}
    
    .similarity-medium {{
        color: {st.session_state.accent_purple};
        font-weight: 700;
        font-size: 1.1rem;
    }}
    
    .similarity-low {{
        color: #ef4444;
        font-weight: 700;
        font-size: 1.1rem;
    }}
    
    /* Stats cards */
    .stat-card {{
        background: linear-gradient(135deg, {st.session_state.accent_purple} 0%, {st.session_state.accent_gold} 100%);
        padding: 1rem;
        border-radius: 10px;
        color: {st.session_state.text_color};
        text-align: center;
        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
    }}
    
    .stat-number {{
        font-size: 1.8rem;
        font-weight: 800;
        margin: 0.3rem 0;
        color: {st.session_state.text_color};
    }}
    
    .stat-card p {{
        color: {st.session_state.text_color} !important;
    }}
    
    /* Footer styling */
    .footer {{
        text-align: center;
        padding: 1rem;
        color: {st.session_state.text_color};
        font-size: 0.85rem;
        background: {st.session_state.card_bg};
        border-radius: 10px;
        margin-top: 1.5rem;
        border: 1px solid {st.session_state.border_color};
    }}
    
    .footer p {{
        color: {st.session_state.text_color} !important;
    }}
    
    /* Divider styling */
    .custom-divider {{
        height: 2px;
        background: linear-gradient(90deg, transparent, {st.session_state.accent_gold}, {st.session_state.accent_purple}, {st.session_state.accent_gold}, transparent);
        margin: 1.5rem 0;
        border-radius: 2px;
    }}
    
    /* Input fields */
    .stTextInput > div > div > input {{
        background-color: {st.session_state.card_bg} !important;
        color: {st.session_state.text_color} !important;
        border-color: {st.session_state.border_color} !important;
    }}
    
    .stSelectbox > div > div {{
        background-color: {st.session_state.card_bg} !important;
        color: {st.session_state.text_color} !important;
    }}
    
    .stSelectbox > div > div > div {{
        color: {st.session_state.text_color} !important;
    }}
    
    /* Dataframe styling */
    .stDataFrame {{
        background-color: {st.session_state.card_bg} !important;
        color: {st.session_state.text_color} !important;
    }}
    
    .stDataFrame td, .stDataFrame th {{
        color: {st.session_state.text_color} !important;
    }}
    
    /* Expander styling */
    .streamlit-expanderHeader {{
        background-color: {st.session_state.card_bg} !important;
        color: {st.session_state.text_color} !important;
    }}
    
    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {{
        background-color: {st.session_state.card_bg} !important;
    }}
    
    .stTabs [data-baseweb="tab"] {{
        color: {st.session_state.text_color} !important;
    }}
    
    .stTabs [aria-selected="true"] {{
        color: {st.session_state.accent_gold} !important;
    }}
    
    /* Radio buttons */
    .stRadio > div {{
        color: {st.session_state.text_color} !important;
    }}
    
    /* Checkbox */
    .stCheckbox > div {{
        color: {st.session_state.text_color} !important;
    }}
    
    /* Metric styling */
    [data-testid="stMetricValue"] {{
        color: {st.session_state.accent_gold} !important;
    }}
    
    [data-testid="stMetricLabel"] {{
        color: {st.session_state.text_color} !important;
    }}
    
    /* Plotly chart background */
    .js-plotly-plot {{
        background-color: {st.session_state.card_bg} !important;
    }}
    
    /* ===== MOBILE RESPONSIVE STYLES ===== */
    @media only screen and (max-width: 1200px) {{
        .gallery-col {{
            flex: 0 0 33.33% !important;
            max-width: 33.33% !important;
        }}
    }}
    
    @media only screen and (max-width: 992px) {{
        .gallery-col {{
            flex: 0 0 50% !important;
            max-width: 50% !important;
        }}
        
        .main-title {{
            font-size: 2rem !important;
        }}
    }}
    
    @media only screen and (max-width: 768px) {{
        .stButton > button {{
            width: 100% !important;
            margin: 0.3rem 0 !important;
        }}
        
        .row-widget.stHorizontal {{
            flex-direction: column !important;
        }}
        
        [data-testid="column"] {{
            width: 100% !important;
            min-width: 100% !important;
            padding: 0.3rem 0 !important;
        }}
        
        .gallery-col {{
            flex: 0 0 100% !important;
            max-width: 100% !important;
        }}
        
        h1 {{
            font-size: 1.8rem !important;
        }}
        
        h2 {{
            font-size: 1.5rem !important;
        }}
        
        .logo-container img {{
            max-width: 150px !important;
        }}
        
        .design-card {{
            width: 100% !important;
            margin: 0.5rem 0 !important;
        }}
        
        .stat-card {{
            margin: 0.3rem 0 !important;
        }}
        
        .stTabs [data-baseweb="tab-list"] {{
            flex-wrap: wrap !important;
        }}
        
        .stTabs [data-baseweb="tab"] {{
            width: 100% !important;
            margin: 0.2rem 0 !important;
        }}
        
        img {{
            max-width: 100% !important;
            height: auto !important;
        }}
    }}
    
    @media only screen and (max-width: 576px) {{
        h1 {{
            font-size: 1.5rem !important;
        }}
        
        h2 {{
            font-size: 1.3rem !important;
        }}
        
        .main-title {{
            font-size: 1.5rem !important;
        }}
        
        .logo-container img {{
            max-width: 120px !important;
        }}
    }}
    
    @media only screen and (max-width: 400px) {{
        h1 {{
            font-size: 1.2rem !important;
        }}
        
        .logo-container img {{
            max-width: 100px !important;
        }}
    }}
    
    /* Touch-friendly buttons */
    .stButton > button {{
        min-height: 44px !important;
        touch-action: manipulation !important;
    }}
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'designs_df' not in st.session_state:
    # Check if saved data exists
    data_file = "excel_data/designs.pkl"
    if os.path.exists(data_file):
        st.session_state.designs_df = pd.read_pickle(data_file)
    else:
        # Create sample data with larger numbers for testing
        sample_data = {
            'Design_No': ['R001', 'R002', 'R003', 'R004', 'R005', 'N001', 'N002', 'E001', 'E002', 'B001',
                         'R006', 'R007', 'R008', 'N003', 'N004', 'E003', 'E004', 'B002', 'B003', 'P001'],
            'Design_Name': ['Solitaire Ring', 'Halo Ring', 'Vintage Ring', 'Modern Ring', 'Classic Band', 
                           'Diamond Pendant', 'Gold Chain', 'Stud Earrings', 'Drop Earrings', 'Tennis Bracelet',
                           'Emerald Ring', 'Sapphire Ring', 'Ruby Ring', 'Pearl Necklace', 'Opal Necklace',
                           'Jade Earrings', 'Gold Hoops', 'Diamond Bracelet', 'Gold Bracelet', 'Diamond Brooch'],
            'Category': ['Ring', 'Ring', 'Ring', 'Ring', 'Ring', 'Necklace', 'Necklace', 'Earring', 'Earring', 'Bracelet',
                        'Ring', 'Ring', 'Ring', 'Necklace', 'Necklace', 'Earring', 'Earring', 'Bracelet', 'Bracelet', 'Brooch'],
            'Metal_Type': ['Gold', 'Gold', 'Silver', 'Gold', 'Silver', 'Gold', 'Gold', 'Silver', 'Gold', 'Gold',
                          'Platinum', 'Rose Gold', 'White Gold', 'Gold', 'Silver', 'Gold', 'Gold', 'Platinum', 'Rose Gold', 'Gold'],
            'Stone_Type': ['Diamond', 'Diamond', 'None', 'None', 'None', 'Diamond', 'None', 'Diamond', 'Pearl', 'Diamond',
                          'Emerald', 'Sapphire', 'Ruby', 'Pearl', 'Opal', 'Jade', 'None', 'Diamond', 'None', 'Diamond'],
            'Image_File': ['R001.jpg', 'R002.jpg', 'R003.jpg', 'R004.jpg', 'R005.jpg', 'N001.jpg', 'N002.jpg', 'E001.jpg', 'E002.jpg', 'B001.jpg',
                          'R006.jpg', 'R007.jpg', 'R008.jpg', 'N003.jpg', 'N004.jpg', 'E003.jpg', 'E004.jpg', 'B002.jpg', 'B003.jpg', 'P001.jpg'],
            'Date_Added': [datetime.now().strftime("%Y-%m-%d") for _ in range(20)],
            'Status': ['Active'] * 20
        }
        st.session_state.designs_df = pd.DataFrame(sample_data)
    
    st.session_state.embeddings = None
    st.session_state.model_loaded = False
    st.session_state.categories = ['Ring', 'Necklace', 'Earring', 'Bracelet', 'Pendant', 'Brooch', 'Cufflink', 'Other']
    st.session_state.metal_types = ['Gold', 'Silver', 'Platinum', 'Rose Gold', 'White Gold']
    st.session_state.stone_types = ['Diamond', 'Emerald', 'Ruby', 'Sapphire', 'Pearl', 'Opal', 'Jade', 'None', 'Other']
    st.session_state.similarity_results = None
    st.session_state.search_image = None
    st.session_state.admin_mode = False
    st.session_state.edit_mode = False
    st.session_state.current_edit = None
    st.session_state.image_preview = None
    st.session_state.expert_mode = True if EXPERT_AVAILABLE else False
    st.session_state.password_correct = False
    st.session_state.forgot_password = False
    st.session_state.reset_email = ""
    st.session_state.otp_sent = False
    st.session_state.otp_verified = False
    st.session_state.generated_otp = ""
    # NEW: Track multiple images per design
    st.session_state.design_images = {}

# Function to save data
def save_data():
    data_file = "excel_data/designs.pkl"
    st.session_state.designs_df.to_pickle(data_file)

# MODIFIED: Function to save multiple uploaded images (max 4)
def save_uploaded_images(uploaded_files, design_no):
    saved_files = []
    # Limit to 4 images
    for i, uploaded_file in enumerate(uploaded_files[:4]):
        # Create filename with angle number
        file_extension = uploaded_file.name.split('.')[-1]
        filename = f"{design_no}_angle{i+1}.{file_extension}"
        filepath = os.path.join("images", filename)
        
        # Save image
        with open(filepath, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        saved_files.append(filename)
    
    # Store in session state
    st.session_state.design_images[design_no] = saved_files
    return saved_files

# NEW: Function to load multiple images for a design
def load_design_images(design_no):
    images = []
    # Look for images with pattern design_no_angle*.jpg
    for ext in ['jpg', 'jpeg', 'png']:
        pattern = os.path.join("images", f"{design_no}_angle*.{ext}")
        images.extend(glob.glob(pattern))
    
    return sorted(images)

# MODIFIED: Function to load image for display (returns first image if multiple)
def load_image(design_no, index=0):
    images = load_design_images(design_no)
    if images and index < len(images):
        return images[index]
    
    # Fallback to old method
    for ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp']:
        img_path = os.path.join("images", f"{design_no}.{ext}")
        if os.path.exists(img_path):
            return img_path
    
    # Try with stored filename
    design_row = st.session_state.designs_df[st.session_state.designs_df['Design_No'] == design_no]
    if not design_row.empty:
        img_file = design_row.iloc[0]['Image_File']
        img_path = os.path.join("images", img_file)
        if os.path.exists(img_path):
            return img_path
    
    return None

# Load expert detector
@st.cache_resource
def load_expert_detector():
    """Load the expert-level jewelry detector"""
    if not EXPERT_AVAILABLE:
        return None
    
    try:
        with st.spinner("🔥 Loading expert AI models (this may take a minute)..."):
            detector = ExpertJewelryDetector(use_gpu=True)
            return detector
    except Exception as e:
        st.error(f"❌ Expert detector failed to load: {e}")
        return None

# Load embeddings
@st.cache_data
def load_expert_embeddings():
    """Load expert-level embeddings"""
    embedding_file = "embeddings/expert_embeddings.pkl"
    if os.path.exists(embedding_file):
        with open(embedding_file, 'rb') as f:
            return pickle.load(f)
    return None

# Function to find similar designs
def find_similar_designs(query_embedding, embeddings_dict, top_k=8):
    if query_embedding is None or embeddings_dict is None:
        return []
    
    similarities = []
    for design_name, emb in embeddings_dict.items():
        # Cosine similarity
        sim = cosine_similarity([query_embedding], [emb])[0][0]
        similarities.append((design_name, sim))
    
    # Sort by similarity (highest first)
    similarities.sort(key=lambda x: x[1], reverse=True)
    
    # Return top k
    return similarities[:top_k]

# Get category color
def get_category_color(category):
    return CATEGORY_COLORS.get(category, CATEGORY_COLORS["Other"])

# Get metal badge class
def get_metal_badge(metal):
    if metal.lower() == 'gold':
        return 'metal-gold'
    elif metal.lower() == 'silver':
        return 'metal-silver'
    else:
        return 'metal-gold'

# Authentication with forgot password
def check_password():
    """Returns `True` if the user had the correct password."""
    if st.session_state.password_correct:
        return True
    
    with st.sidebar:
        st.markdown("### 🔐 Admin Login")
        
        if not st.session_state.forgot_password:
            # Normal login
            password = st.text_input("Enter Admin Password", type="password", key="admin_password_input")
            
            col1, col2, col3 = st.columns([1,1,1])
            with col1:
                if st.button("Login", key="admin_login_btn", use_container_width=True):
                    if verify_password(password):
                        st.session_state.password_correct = True
                        st.success("✅ Login successful!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Incorrect password")
            
            with col2:
                if st.button("🔒 Demo", key="demo_mode_btn", use_container_width=True):
                    st.session_state.password_correct = True
                    st.info("🔓 Demo mode - limited access")
                    st.rerun()
            
            with col3:
                if st.button("🔄 Forgot", key="forgot_pwd_btn", use_container_width=True):
                    st.session_state.forgot_password = True
                    st.rerun()
        
        else:
            # Forgot password flow
            st.markdown("#### 🔑 Reset Password")
            
            # Step 1: Email input
            if not st.session_state.otp_sent:
                email = st.text_input("Enter your email", value=st.session_state.reset_email, key="reset_email")
                
                if st.button("📧 Send OTP", key="send_otp_btn", use_container_width=True):
                    if email:
                        otp = generate_otp()
                        if send_otp_email(email, otp):
                            st.session_state.reset_email = email
                            st.session_state.generated_otp = otp
                            st.session_state.otp_sent = True
                            st.success(f"✅ OTP sent to {email}")
                            st.rerun()
                        else:
                            st.error("❌ Failed to send email. Check email configuration.")
                    else:
                        st.error("❌ Please enter email")
            
            # Step 2: OTP verification
            elif not st.session_state.otp_verified:
                st.info(f"📧 OTP sent to {st.session_state.reset_email}")
                otp_input = st.text_input("Enter OTP", key="otp_input")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Verify OTP", key="verify_otp_btn", use_container_width=True):
                        if otp_input == st.session_state.generated_otp:
                            st.session_state.otp_verified = True
                            st.success("✅ OTP verified!")
                            st.rerun()
                        else:
                            st.error("❌ Invalid OTP")
                
                with col2:
                    if st.button("↩️ Back", key="back_to_login", use_container_width=True):
                        st.session_state.forgot_password = False
                        st.session_state.otp_sent = False
                        st.session_state.otp_verified = False
                        st.rerun()
            
            # Step 3: New password
            else:
                new_password = st.text_input("Enter new password", type="password", key="new_pwd")
                confirm_password = st.text_input("Confirm new password", type="password", key="confirm_pwd")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("💾 Reset Password", key="reset_pwd_btn", use_container_width=True):
                        if new_password and confirm_password:
                            if new_password == confirm_password:
                                save_admin_password(new_password)
                                st.success("✅ Password reset successful!")
                                st.session_state.forgot_password = False
                                st.session_state.otp_sent = False
                                st.session_state.otp_verified = False
                                st.session_state.password_correct = True
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("❌ Passwords don't match")
                        else:
                            st.error("❌ Please fill all fields")
                
                with col2:
                    if st.button("↩️ Cancel", key="cancel_reset", use_container_width=True):
                        st.session_state.forgot_password = False
                        st.session_state.otp_sent = False
                        st.session_state.otp_verified = False
                        st.rerun()
    
    return False

# Display contact information
def display_contact():
    with st.expander("📞 Contact Information", expanded=False):
        st.markdown(f"""
        <div class="contact-info">
            <div class="contact-item"><span class="contact-icon">📞</span> {COMPANY_PHONE}</div>
            <div class="contact-item"><span class="contact-icon">✉️</span> {COMPANY_EMAIL}</div>
            <div class="contact-item"><span class="contact-icon">🌐</span> {COMPANY_WEBSITE}</div>
        </div>
        """, unsafe_allow_html=True)

# Main app
def main():
    # Sidebar
    with st.sidebar:
        if os.path.exists("header_logo_1764154359.png"):
            st.image("header_logo_1764154359.png", use_container_width=True)
        else:
            st.markdown(f'<div class="sidebar-header">💎 {COMPANY_NAME}</div>', unsafe_allow_html=True)
        
        # Theme selector
        st.markdown("### 🎨 Theme")
        theme = st.radio(
            "Select Theme",
            ["🌙 Dark Theme", "☀️ Light Theme"],
            index=0 if st.session_state.theme == "🌙 Dark Theme" else 1,
            key="theme_selector",
            horizontal=True
        )
        
        # Update theme if changed
        if theme != st.session_state.theme:
            if theme == "☀️ Light Theme":
                st.session_state.bg_color = "#FFFFFF"
                st.session_state.card_bg = "#F8F8F8"
                st.session_state.text_color = "#333333"
                st.session_state.border_color = "#E0E0E0"
                st.session_state.accent_gold = "#D4AF37"
                st.session_state.accent_purple = "#5E2A84"
            else:
                st.session_state.bg_color = "#1A2634"
                st.session_state.card_bg = "#0F1A24"
                st.session_state.text_color = "#FFFFFF"
                st.session_state.border_color = "#2A3A4A"
                st.session_state.accent_gold = "#D4AF37"
                st.session_state.accent_purple = "#9D7EBD"
            
            st.session_state.theme = theme
            st.rerun()
        
        st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
        
        # Mode selector with icons
        mode = st.radio(
            "Select Mode",
            ["🔍 Main Tool", "⚙️ Admin Panel", "📊 Analytics"],
            index=0,
            key="main_mode_selector"
        )
        
        if mode == "⚙️ Admin Panel":
            st.session_state.admin_mode = True
        else:
            st.session_state.admin_mode = False
        
        st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
        
        # Stats in sidebar
        st.markdown("### 📊 Quick Stats")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Designs", f"{len(st.session_state.designs_df):,}")
        
        with col2:
            active_count = len(st.session_state.designs_df[st.session_state.designs_df['Status'] == 'Active'])
            st.metric("Active", f"{active_count:,}")
        
        # Image count
        image_count = len([f for f in os.listdir("images") if f.endswith(('.jpg', '.jpeg', '.png'))])
        st.metric("Images", f"{image_count:,}")
        
        # AI Mode
        if EXPERT_AVAILABLE:
            st.markdown("### 🔬 AI Mode")
            st.success("🔥 **AI-Powered Detection Active**")
            st.caption("Using multi-model ensemble for shape + pattern + detail analysis")
            st.session_state.expert_mode = True
        else:
            st.session_state.expert_mode = False
        
        # Database status
        st.markdown("### 💾 Database Status")
        if st.session_state.expert_mode and EXPERT_AVAILABLE:
            embeddings_dict = load_expert_embeddings()
            if embeddings_dict:
                st.success(f"✅ Expert embeddings: {len(embeddings_dict):,} designs")
            else:
                st.warning("⚠️ No expert embeddings found")
                
                if st.button("🚀 Generate Expert Embeddings", key="gen_embeddings_btn", use_container_width=True):
                    detector = load_expert_detector()
                    if detector:
                        with st.spinner("🔬 Running expert analysis on all designs..."):
                            detector.process_all_designs("images")
                        st.success("✅ Expert embeddings generated!")
                        st.cache_data.clear()
                        st.rerun()
        else:
            st.info("ℹ️ Using standard mode")
        
        # Contact info in sidebar
        st.markdown("### 📞 Contact")
        st.caption(f"📱 {COMPANY_PHONE}")
        st.caption(f"✉️ {COMPANY_EMAIL}")
        st.caption(f"🌐 {COMPANY_WEBSITE}")
    
    # Custom divider
    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
    
    # MAIN TOOL MODE
    if not st.session_state.admin_mode and mode == "🔍 Main Tool":
        # Search section
        st.markdown("### 🔍 Visual Search")
        
        search_col1, search_col2, search_col3 = st.columns([1.5, 1.5, 2])
        
        with search_col1:
            st.markdown("**📤 Upload Image**")
            st.markdown('<div class="upload-area">', unsafe_allow_html=True)
            uploaded_file = st.file_uploader("", type=['jpg', 'jpeg', 'png'], key="main_upload", label_visibility="collapsed")
            
            if uploaded_file is not None:
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded Image", use_container_width=True)
                temp_path = os.path.join("temp_uploads", "temp_search.jpg")
                image.save(temp_path)
                st.session_state.search_image = image
                
                if st.button("🔍 Find Similar Designs", key="find_similar_upload_btn", use_container_width=True):
                    st.session_state.search_trigger = True
            st.markdown('</div>', unsafe_allow_html=True)
        
        with search_col2:
            st.markdown("**📋 Paste Image**")
            st.markdown('<div class="upload-area">', unsafe_allow_html=True)
            pasted_file = st.file_uploader("", type=['jpg', 'jpeg', 'png'], key="main_paste", label_visibility="collapsed")
            
            if pasted_file is not None:
                pasted_image = Image.open(pasted_file)
                st.image(pasted_image, caption="Pasted Image", use_container_width=True)
                st.session_state.search_image = pasted_image
                
                if st.button("🔍 Search Pasted", key="find_similar_paste_btn", use_container_width=True):
                    st.session_state.search_trigger = True
            st.markdown('</div>', unsafe_allow_html=True)
        
        with search_col3:
            st.markdown("**🔢 Quick Search**")
            search_query = st.text_input("", placeholder="Search by Design No. or Name...", key="quick_search_input", label_visibility="collapsed")
            
            if search_query:
                mask = (st.session_state.designs_df['Design_No'].str.contains(search_query, case=False) | 
                       st.session_state.designs_df['Design_Name'].str.contains(search_query, case=False))
                filtered = st.session_state.designs_df[mask]
                if not filtered.empty:
                    st.success(f"✅ Found {len(filtered):,} designs")
                    
                    with st.expander("View Results"):
                        for _, row in filtered.iterrows():
                            img_path = load_image(row['Design_No'])
                            cols = st.columns([1,3])
                            with cols[0]:
                                if img_path:
                                    st.image(img_path, width=80)
                            with cols[1]:
                                st.write(f"**{row['Design_No']}**: {row['Design_Name']}")
                                st.caption(f"{row['Category']} | {row['Metal_Type']} | {row['Stone_Type']}")
                else:
                    st.warning("No designs found")
        
        # Search results section
        if 'search_trigger' in st.session_state and st.session_state.search_trigger and st.session_state.search_image is not None:
            st.markdown("### 🎯 Similarity Results")
            
            if st.session_state.expert_mode and EXPERT_AVAILABLE:
                detector = load_expert_detector()
                embeddings_dict = load_expert_embeddings()
                
                if detector and embeddings_dict:
                    with st.spinner("🔬 **Expert AI analyzing...**"):
                        query_emb = detector.generate_embedding(st.session_state.search_image)
                        
                        if query_emb is not None:
                            results = find_similar_designs(query_emb, embeddings_dict, top_k=8)
                            
                            st.markdown(f"**Top {len(results)} Similar Designs**")
                            
                            result_cols = st.columns(4)
                            for idx, (design_name, similarity) in enumerate(results):
                                with result_cols[idx % 4]:
                                    design_row = st.session_state.designs_df[st.session_state.designs_df['Design_No'] == design_name]
                                    
                                    if not design_row.empty:
                                        similarity_pct = similarity * 100
                                        
                                        if similarity >= 0.8:
                                            sim_class = "similarity-high"
                                            sim_icon = "🔥"
                                        elif similarity >= 0.6:
                                            sim_class = "similarity-medium"
                                            sim_icon = "⭐"
                                        else:
                                            sim_class = "similarity-low"
                                            sim_icon = "💎"
                                        
                                        img_path = load_image(design_name)
                                        category_color = get_category_color(design_row.iloc[0]['Category'])
                                        
                                        st.markdown(f"""
                                        <div class="design-card">
                                            <h4>{sim_icon} {design_name}</h4>
                                            <p><strong>{design_row.iloc[0]['Design_Name']}</strong></p>
                                        """, unsafe_allow_html=True)
                                        
                                        if img_path:
                                            st.image(img_path, use_container_width=True)
                                        
                                        st.markdown(f"""
                                            <p>
                                                <span class="category-badge" style="background: {category_color};">
                                                    {design_row.iloc[0]['Category']}
                                                </span>
                                            </p>
                                            <p>Metal: {design_row.iloc[0]['Metal_Type']}<br>
                                            Stone: {design_row.iloc[0]['Stone_Type']}</p>
                                            <p class="{sim_class}">{sim_icon} {similarity_pct:.1f}% Match</p>
                                        </div>
                                        """, unsafe_allow_html=True)
                            
                            col1, col2, col3 = st.columns([1,1,1])
                            with col2:
                                if st.button("🗑️ Clear Results", key="clear_results_btn", use_container_width=True):
                                    st.session_state.search_trigger = False
                                    st.session_state.search_image = None
                                    st.rerun()
                else:
                    st.warning("⚠️ Expert mode requires embeddings. Generate them in sidebar first.")
            else:
                st.info("ℹ️ Using standard mode")
        
        # Design Gallery
        st.markdown("### 📋 Design Gallery")
        
        filter_cols = st.columns(3)
        
        with filter_cols[0]:
            category_filter = st.selectbox("Category", ["All"] + st.session_state.categories, key="gallery_category_filter")
        with filter_cols[1]:
            metal_filter = st.selectbox("Metal", ["All"] + st.session_state.metal_types, key="gallery_metal_filter")
        with filter_cols[2]:
            stone_filter = st.selectbox("Stone", ["All"] + st.session_state.stone_types, key="gallery_stone_filter")
        
        filtered_df = st.session_state.designs_df.copy()
        if category_filter != "All":
            filtered_df = filtered_df[filtered_df['Category'] == category_filter]
        if metal_filter != "All":
            filtered_df = filtered_df[filtered_df['Metal_Type'] == metal_filter]
        if stone_filter != "All":
            filtered_df = filtered_df[filtered_df['Stone_Type'] == stone_filter]
        
        st.caption(f"Showing {len(filtered_df):,} designs")
        
        if len(filtered_df) > 0:
            gallery_cols = st.columns(4)
            for idx, (_, row) in enumerate(filtered_df.iterrows()):
                with gallery_cols[idx % 4]:
                    img_path = load_image(row['Design_No'])
                    category_color = get_category_color(row['Category'])
                    
                    st.markdown(f"""
                    <div class="design-card">
                        <h4>{row['Design_No']}</h4>
                        <p><strong>{row['Design_Name']}</strong></p>
                    """, unsafe_allow_html=True)
                    
                    if img_path:
                        st.image(img_path, use_container_width=True)
                    else:
                        st.caption("🖼️ No image")
                    
                    st.markdown(f"""
                        <p>
                            <span class="category-badge" style="background: {category_color};">
                                {row['Category']}
                            </span>
                        </p>
                        <p>Metal: {row['Metal_Type']}<br>
                        Stone: {row['Stone_Type']}</p>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("No designs match the selected filters")
    
    # ADMIN PANEL MODE
    elif st.session_state.admin_mode and mode == "⚙️ Admin Panel":
        if check_password():
            st.markdown(f"""
            <div class="admin-panel">
                <h2>⚙️ Admin Panel</h2>
                <p>Manage your design database: Add, Edit, or Delete designs with images (Max 4 images per design)</p>
            </div>
            """, unsafe_allow_html=True)
            
            tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
                "➕ Add Design", 
                "✏️ Edit Design", 
                "🗑️ Delete Design", 
                "📊 Categories",
                "📁 Bulk Upload",
                "🔬 AI Training"
            ])
            
            with tab1:
                st.markdown("### Add New Design with Multiple Images")
                st.caption("📸 You can upload up to 4 images per design")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    new_design_no = st.text_input("Design Number *", help="Unique identifier for the design", key="add_design_no")
                    new_design_name = st.text_input("Design Name *", help="Display name of the design", key="add_design_name")
                    new_category = st.selectbox("Category *", st.session_state.categories, key="add_category")
                
                with col2:
                    new_metal = st.selectbox("Metal Type", st.session_state.metal_types, key="add_metal")
                    new_stone = st.selectbox("Stone Type", st.session_state.stone_types, key="add_stone")
                    new_status = st.selectbox("Status", ["Active", "Inactive"], key="add_status")
                    new_date = datetime.now().strftime("%Y-%m-%d")
                    
                    # MODIFIED: Multiple image upload with max 4
                    st.markdown("**Design Images * (Max 4 images)**")
                    new_images = st.file_uploader(
                        "Upload up to 4 images (JPG, PNG)", 
                        type=['jpg', 'jpeg', 'png'], 
                        accept_multiple_files=True,
                        key="add_multiple_images"
                    )
                    
                    if new_images:
                        if len(new_images) > 4:
                            st.warning(f"⚠️ You selected {len(new_images)} images. Only the first 4 will be used.")
                        
                        st.markdown(f"**{min(len(new_images), 4)} images will be uploaded**")
                        preview_cols = st.columns(min(len(new_images), 4))
                        for idx, img_file in enumerate(new_images[:4]):
                            with preview_cols[idx]:
                                img = Image.open(img_file)
                                st.image(img, caption=f"Angle {idx+1}", width=120)
                
                if st.button("💾 Save Design", key="save_design_btn", use_container_width=True):
                    if new_design_no and new_design_name and new_images:
                        if new_design_no not in st.session_state.designs_df['Design_No'].values:
                            # Save up to 4 images
                            saved_files = save_uploaded_images(new_images, new_design_no)
                            
                            # Use first image as primary for backward compatibility
                            primary_image = saved_files[0] if saved_files else ""
                            
                            new_row = pd.DataFrame({
                                'Design_No': [new_design_no],
                                'Design_Name': [new_design_name],
                                'Category': [new_category],
                                'Metal_Type': [new_metal],
                                'Stone_Type': [new_stone],
                                'Image_File': [primary_image],
                                'Date_Added': [new_date],
                                'Status': [new_status]
                            })
                            st.session_state.designs_df = pd.concat([st.session_state.designs_df, new_row], ignore_index=True)
                            
                            save_data()
                            
                            st.markdown(f'<div class="success-msg">✅ Design added successfully with {len(saved_files)} images!</div>', unsafe_allow_html=True)
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("❌ Design number already exists")
                    else:
                        st.error("❌ Please fill all required fields (*) and upload at least one image")
            
            with tab2:
                st.markdown("### Edit Design with Multiple Images")
                
                design_list = st.session_state.designs_df['Design_No'].tolist()
                design_to_edit = st.selectbox(
                    "Select Design to Edit",
                    design_list,
                    key="edit_design_select"
                )
                
                if design_to_edit:
                    design_data = st.session_state.designs_df[st.session_state.designs_df['Design_No'] == design_to_edit].iloc[0]
                    
                    # Show current images
                    st.markdown("**Current Images:**")
                    current_images = load_design_images(design_to_edit)
                    
                    if current_images:
                        st.markdown(f"📸 {len(current_images)} images found")
                        img_cols = st.columns(min(len(current_images), 4))
                        for idx, img_path in enumerate(current_images[:4]):
                            with img_cols[idx]:
                                st.image(img_path, caption=f"Angle {idx+1}", width=120)
                    else:
                        st.info("No images uploaded for this design")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        edit_name = st.text_input("Design Name", value=design_data['Design_Name'], key=f"edit_name_{design_to_edit}")
                        edit_category = st.selectbox(
                            "Category", 
                            st.session_state.categories, 
                            index=st.session_state.categories.index(design_data['Category']),
                            key=f"edit_category_{design_to_edit}"
                        )
                    
                    with col2:
                        try:
                            metal_index = st.session_state.metal_types.index(design_data['Metal_Type'])
                        except ValueError:
                            metal_index = 0
                            design_data['Metal_Type'] = 'Gold'
                        
                        edit_metal = st.selectbox(
                            "Metal Type", 
                            st.session_state.metal_types,
                            index=metal_index,
                            key=f"edit_metal_{design_to_edit}"
                        )
                        
                        try:
                            stone_index = st.session_state.stone_types.index(design_data['Stone_Type'])
                        except ValueError:
                            stone_index = 0
                            design_data['Stone_Type'] = st.session_state.stone_types[0]
                        
                        edit_stone = st.selectbox(
                            "Stone Type", 
                            st.session_state.stone_types,
                            index=stone_index,
                            key=f"edit_stone_{design_to_edit}"
                        )
                        
                        edit_status = st.selectbox(
                            "Status", 
                            ["Active", "Inactive"],
                            index=0 if design_data['Status'] == 'Active' else 1,
                            key=f"edit_status_{design_to_edit}"
                        )
                        
                        # MODIFIED: Add more images with limit check
                        st.markdown("**Add More Images (optional, max 4 total)**")
                        current_count = len(current_images)
                        remaining_slots = max(0, 4 - current_count)
                        
                        if remaining_slots > 0:
                            st.caption(f"📸 You can add {remaining_slots} more image(s)")
                            additional_images = st.file_uploader(
                                f"Upload up to {remaining_slots} more images", 
                                type=['jpg', 'jpeg', 'png'], 
                                accept_multiple_files=True,
                                key=f"edit_images_{design_to_edit}"
                            )
                            
                            if additional_images and len(additional_images) > remaining_slots:
                                st.warning(f"⚠️ You can only add {remaining_slots} more images. Extra images will be ignored.")
                        else:
                            st.info("✅ Maximum 4 images already uploaded")
                            additional_images = []
                    
                    if st.button("💾 Update Design", key=f"update_btn_{design_to_edit}", use_container_width=True):
                        idx = st.session_state.designs_df[st.session_state.designs_df['Design_No'] == design_to_edit].index[0]
                        st.session_state.designs_df.at[idx, 'Design_Name'] = edit_name
                        st.session_state.designs_df.at[idx, 'Category'] = edit_category
                        st.session_state.designs_df.at[idx, 'Metal_Type'] = edit_metal
                        st.session_state.designs_df.at[idx, 'Stone_Type'] = edit_stone
                        st.session_state.designs_df.at[idx, 'Status'] = edit_status
                        
                        # Save additional images if uploaded (respecting limit)
                        if additional_images and remaining_slots > 0:
                            # Limit to remaining slots
                            images_to_save = additional_images[:remaining_slots]
                            saved_files = save_uploaded_images(images_to_save, design_to_edit)
                            
                            # Update primary image if this is the first image
                            if not current_images and saved_files:
                                st.session_state.designs_df.at[idx, 'Image_File'] = saved_files[0]
                        
                        save_data()
                        
                        st.markdown('<div class="success-msg">✅ Design updated successfully!</div>', unsafe_allow_html=True)
                        time.sleep(2)
                        st.rerun()
            
            with tab3:
                st.markdown("### Delete Design")
                
                design_list = st.session_state.designs_df['Design_No'].tolist()
                design_to_delete = st.selectbox(
                    "Select Design to Delete",
                    design_list,
                    key="delete_design_select"
                )
                
                if design_to_delete:
                    design_data = st.session_state.designs_df[st.session_state.designs_df['Design_No'] == design_to_delete].iloc[0]
                    
                    # Show all images
                    images = load_design_images(design_to_delete)
                    if images:
                        st.markdown(f"**Design Images ({len(images)} found):**")
                        img_cols = st.columns(min(len(images), 4))
                        for idx, img_path in enumerate(images[:4]):
                            with img_cols[idx]:
                                st.image(img_path, width=120)
                    
                    st.warning(f"⚠️ You are about to delete: {design_to_delete} - {design_data['Design_Name']}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        confirm = st.checkbox("I confirm this deletion", key=f"confirm_delete_{design_to_delete}")
                    with col2:
                        if confirm and st.button("🗑️ Permanently Delete", key=f"delete_btn_{design_to_delete}", use_container_width=True):
                            # Delete all image files
                            for img_path in images:
                                if os.path.exists(img_path):
                                    os.remove(img_path)
                            
                            st.session_state.designs_df = st.session_state.designs_df[
                                st.session_state.designs_df['Design_No'] != design_to_delete
                            ]
                            
                            save_data()
                            
                            st.markdown('<div class="success-msg">✅ Design deleted successfully!</div>', unsafe_allow_html=True)
                            time.sleep(2)
                            st.rerun()
            
            with tab4:
                st.markdown("### Manage Categories")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Add New Category**")
                    new_cat = st.text_input("Category Name", key="new_category_input")
                    if st.button("➕ Add Category", key="add_category_btn"):
                        if new_cat and new_cat not in st.session_state.categories:
                            st.session_state.categories.append(new_cat)
                            CATEGORY_COLORS[new_cat] = "#A8A8A8"
                            st.success(f"✅ Category '{new_cat}' added!")
                            time.sleep(1)
                            st.rerun()
                        elif new_cat in st.session_state.categories:
                            st.warning("Category already exists")
                
                with col2:
                    st.markdown("**Remove Category**")
                    if st.session_state.categories:
                        cat_to_remove = st.selectbox("Select Category", st.session_state.categories, key="remove_category_select")
                        if st.button("❌ Remove Category", key="remove_category_btn"):
                            in_use = len(st.session_state.designs_df[st.session_state.designs_df['Category'] == cat_to_remove]) > 0
                            if in_use:
                                st.error("Cannot remove category that has designs assigned")
                            else:
                                st.session_state.categories.remove(cat_to_remove)
                                st.success(f"✅ Category removed!")
                                st.rerun()
            
            with tab5:
                st.markdown("### Bulk Upload Images")
                st.markdown("Upload multiple images for multiple designs (Max 4 per design)")
                
                bulk_images = st.file_uploader(
                    "Select multiple images (name them as design_angle.jpg)", 
                    type=['jpg', 'jpeg', 'png'], 
                    accept_multiple_files=True,
                    key="bulk_upload"
                )
                
                if bulk_images:
                    st.markdown(f"**{len(bulk_images):,} images selected**")
                    
                    preview_cols = st.columns(4)
                    for idx, img_file in enumerate(bulk_images[:4]):
                        with preview_cols[idx]:
                            img = Image.open(img_file)
                            st.image(img, caption=img_file.name, width=150)
                    
                    if st.button("📤 Upload All Images", key="bulk_upload_btn", use_container_width=True):
                        uploaded_count = 0
                        # Group images by design
                        design_image_groups = {}
                        for img_file in bulk_images:
                            design_no = img_file.name.split('_')[0] if '_' in img_file.name else os.path.splitext(img_file.name)[0]
                            if design_no not in design_image_groups:
                                design_image_groups[design_no] = []
                            design_image_groups[design_no].append(img_file)
                        
                        # Process each design, respecting 4 image limit
                        for design_no, images in design_image_groups.items():
                            # Limit to 4 images per design
                            images_to_save = images[:4]
                            
                            for i, img_file in enumerate(images_to_save):
                                filename = f"{design_no}_angle{i+1}.jpg"
                                filepath = os.path.join("images", filename)
                                
                                # Save image
                                with open(filepath, "wb") as f:
                                    f.write(img_file.getbuffer())
                                
                                uploaded_count += 1
                            
                            # Update design's primary image if design exists
                            if design_no in st.session_state.designs_df['Design_No'].values and images_to_save:
                                idx = st.session_state.designs_df[st.session_state.designs_df['Design_No'] == design_no].index[0]
                                if pd.isna(st.session_state.designs_df.at[idx, 'Image_File']) or st.session_state.designs_df.at[idx, 'Image_File'] == "":
                                    st.session_state.designs_df.at[idx, 'Image_File'] = f"{design_no}_angle1.jpg"
                        
                        save_data()
                        st.markdown(f'<div class="success-msg">✅ {uploaded_count:,} images uploaded successfully! (Max 4 per design)</div>', unsafe_allow_html=True)
                        time.sleep(2)
                        st.rerun()
            
            with tab6:
                st.markdown("### 🔬 AI Model Training")
                st.markdown("Generate expert embeddings for all designs")
                
                if EXPERT_AVAILABLE:
                    st.info("Expert detector will analyze all designs and create embeddings for similarity search.")
                    
                    if st.button("🚀 Run Expert Analysis", key="run_expert_btn", use_container_width=True):
                        detector = load_expert_detector()
                        if detector:
                            with st.spinner("🔬 Analyzing all designs with expert AI..."):
                                detector.process_all_designs("images")
                            st.success("✅ Expert embeddings generated!")
                            st.cache_data.clear()
                            st.rerun()
                else:
                    st.error("expert_detector.py not found. Please ensure it's in the same folder.")
            
            # Preview current designs in admin
            st.markdown("### 📋 Current Designs")
            
            display_df = st.session_state.designs_df.copy()
            display_df['Image_Count'] = display_df['Design_No'].apply(lambda x: len(load_design_images(x)))
            
            st.dataframe(
                display_df[['Design_No', 'Design_Name', 'Category', 'Metal_Type', 'Stone_Type', 'Status', 'Image_Count']],
                use_container_width=True,
                height=300
            )
    
    # ANALYTICS MODE
    elif mode == "📊 Analytics":
        st.markdown("### 📊 Design Analytics Dashboard")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown('<div class="stat-card">', unsafe_allow_html=True)
            st.markdown('<p>Total Designs</p>', unsafe_allow_html=True)
            st.markdown(f'<p class="stat-number">{len(st.session_state.designs_df):,}</p>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="stat-card">', unsafe_allow_html=True)
            st.markdown('<p>Active Designs</p>', unsafe_allow_html=True)
            active = len(st.session_state.designs_df[st.session_state.designs_df['Status'] == 'Active'])
            st.markdown(f'<p class="stat-number">{active:,}</p>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col3:
            st.markdown('<div class="stat-card">', unsafe_allow_html=True)
            st.markdown('<p>Images</p>', unsafe_allow_html=True)
            img_count = len([f for f in os.listdir("images") if f.endswith(('.jpg', '.jpeg', '.png'))])
            st.markdown(f'<p class="stat-number">{img_count:,}</p>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Category Distribution - Enhanced with Plotly
        st.markdown("#### 📊 Category Distribution")
        cat_counts = st.session_state.designs_df['Category'].value_counts().reset_index()
        cat_counts.columns = ['Category', 'Count']
        
        if not cat_counts.empty:
            fig = px.bar(
                cat_counts, 
                x='Category', 
                y='Count',
                title='Designs by Category',
                text='Count',
                color='Count',
                color_continuous_scale=['#D4AF37', '#5E2A84']
            )
            fig.update_traces(texttemplate='%{text:,}', textposition='outside')
            fig.update_layout(
                plot_bgcolor=st.session_state.card_bg,
                paper_bgcolor=st.session_state.card_bg,
                font_color=st.session_state.text_color,
                xaxis=dict(gridcolor='#2A3A4A'),
                yaxis=dict(gridcolor='#2A3A4A')
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Metal Type Distribution
        st.markdown("#### 🏷️ Metal Type Distribution")
        metal_counts = st.session_state.designs_df['Metal_Type'].value_counts().reset_index()
        metal_counts.columns = ['Metal', 'Count']
        
        if not metal_counts.empty:
            fig = px.pie(
                metal_counts, 
                values='Count', 
                names='Metal',
                title='Designs by Metal Type',
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig.update_traces(textinfo='percent+label', texttemplate='%{label}<br>%{percent} (%{value:,})')
            fig.update_layout(
                plot_bgcolor=st.session_state.card_bg,
                paper_bgcolor=st.session_state.card_bg,
                font_color=st.session_state.text_color
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Stone Type Distribution
        st.markdown("#### 💎 Stone Type Distribution")
        stone_counts = st.session_state.designs_df['Stone_Type'].value_counts().reset_index()
        stone_counts.columns = ['Stone', 'Count']
        
        if not stone_counts.empty:
            fig = px.bar(
                stone_counts, 
                x='Stone', 
                y='Count',
                title='Designs by Stone Type',
                text='Count',
                color='Count',
                color_continuous_scale=['#9D7EBD', '#D4AF37']
            )
            fig.update_traces(texttemplate='%{text:,}', textposition='outside')
            fig.update_layout(
                plot_bgcolor=st.session_state.card_bg,
                paper_bgcolor=st.session_state.card_bg,
                font_color=st.session_state.text_color,
                xaxis=dict(gridcolor='#2A3A4A'),
                yaxis=dict(gridcolor='#2A3A4A')
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Recent additions
        st.markdown("#### 🕒 Recent Additions")
        recent = st.session_state.designs_df.sort_values('Date_Added', ascending=False).head(10)
        st.dataframe(recent[['Design_No', 'Design_Name', 'Category', 'Metal_Type', 'Stone_Type', 'Date_Added']], use_container_width=True)
        
        # Display contact information
        display_contact()
    
    # Footer
    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="footer">
        <div style="display: flex; justify-content: center; align-items: center; margin-bottom: 1rem;">
            {"<img src='data:image/png;base64," + get_base64_logo() + "' width='120'>" if os.path.exists("header_logo_1764154359.png") and get_base64_logo() else f"<div class='footer-logo'>💎 {COMPANY_NAME}</div>"}
        </div>
        <p>📱 {COMPANY_PHONE} | ✉️ {COMPANY_EMAIL}</p>
        <p>🌐 {COMPANY_WEBSITE}</p>
        <p style="font-size: 0.8rem;">© {datetime.now().year} {COMPANY_NAME}</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()