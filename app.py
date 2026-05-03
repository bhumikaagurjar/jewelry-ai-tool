import streamlit as st
import pandas as pd
import numpy as np
import pickle
import os
import glob
import cloudinary
import cloudinary.uploader
import cloudinary.api
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

# ------------------------------
# 1. GOOGLE SHEETS INTEGRATION
# ------------------------------
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ------------------------------
# 2. PAGE CONFIGURATION (MUST BE FIRST)
# ------------------------------
st.set_page_config(
    page_title="Kanishka Jewellers Pvt Ltd - Design Studio", 
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ------------------------------
# 3. CLOUDINARY CONFIGURATION (USING STREAMLIT SECRETS)
# ------------------------------
try:
    cloudinary.config(
        cloud_name=st.secrets["CLOUDINARY_CLOUD_NAME"],
        api_key=st.secrets["CLOUDINARY_API_KEY"],
        api_secret=st.secrets["CLOUDINARY_API_SECRET"]
    )
    CLOUDINARY_CONFIGURED = True
except Exception:
    CLOUDINARY_CONFIGURED = False
    st.warning("⚠️ Cloudinary is not configured. Images will be saved locally.")

# ------------------------------
# 4. GOOGLE SHEETS CONNECTION
# ------------------------------
@st.cache_resource
def get_google_sheets_connection():
    """Connect to Google Sheets using service account credentials"""
    try:
        # Get credentials from secrets
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # Load credentials from secrets JSON
        creds_dict = {
            "type": st.secrets["GCP_TYPE"],
            "project_id": st.secrets["GCP_PROJECT_ID"],
            "private_key_id": st.secrets["GCP_PRIVATE_KEY_ID"],
            "private_key": st.secrets["GCP_PRIVATE_KEY"],
            "client_email": st.secrets["GCP_CLIENT_EMAIL"],
            "client_id": st.secrets["GCP_CLIENT_ID"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": st.secrets["GCP_CLIENT_X509_CERT_URL"]
        }
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # Open the spreadsheet (create if not exists)
        sheet_name = "Kanishka_Designs"
        try:
            sheet = client.open(sheet_name).sheet1
        except:
            # Create new spreadsheet if not exists
            sheet = client.create(sheet_name).sheet1
            # Add headers
            headers = ['Design_No', 'Design_Name', 'Category', 'Metal_Type', 'Stone_Type', 'Image_URLs', 'Date_Added', 'Status']
            sheet.append_row(headers)
        
        return sheet
    except Exception as e:
        st.error(f"Google Sheets connection failed: {e}")
        return None

# ------------------------------
# 5. GOOGLE SHEETS DATA FUNCTIONS
# ------------------------------
def load_designs_from_sheets(sheet):
    """Load all designs from Google Sheets into DataFrame"""
    try:
        if sheet is None:
            return pd.DataFrame()
        
        records = sheet.get_all_records()
        if records:
            df = pd.DataFrame(records)
            # Ensure required columns exist
            required_cols = ['Design_No', 'Design_Name', 'Category', 'Metal_Type', 'Stone_Type', 'Image_URLs', 'Date_Added', 'Status']
            for col in required_cols:
                if col not in df.columns:
                    df[col] = ""
            return df
        else:
            # Return empty DataFrame with correct columns
            return pd.DataFrame(columns=['Design_No', 'Design_Name', 'Category', 'Metal_Type', 'Stone_Type', 'Image_URLs', 'Date_Added', 'Status'])
    except Exception as e:
        st.error(f"Error loading designs from Google Sheets: {e}")
        return pd.DataFrame()

def save_design_to_sheets(sheet, design_no, design_name, category, metal_type, stone_type, image_urls, status):
    """Save a single design to Google Sheets"""
    try:
        if sheet is None:
            return False
        
        date_added = datetime.now().strftime("%Y-%m-%d")
        # Join multiple image URLs with comma
        urls_str = ','.join(image_urls) if isinstance(image_urls, list) else image_urls
        
        new_row = [design_no, design_name, category, metal_type, stone_type, urls_str, date_added, status]
        sheet.append_row(new_row)
        return True
    except Exception as e:
        st.error(f"Error saving design to Google Sheets: {e}")
        return False

def update_design_in_sheets(sheet, design_no, design_name, category, metal_type, stone_type, image_urls, status):
    """Update an existing design in Google Sheets"""
    try:
        if sheet is None:
            return False
        
        # Find the row
        cells = sheet.findall(design_no)
        if cells:
            row_num = cells[0].row
            urls_str = ','.join(image_urls) if isinstance(image_urls, list) else image_urls
            date_added = datetime.now().strftime("%Y-%m-%d")
            
            # Update row
            sheet.update(f'A{row_num}', [[design_no]])
            sheet.update(f'B{row_num}', [[design_name]])
            sheet.update(f'C{row_num}', [[category]])
            sheet.update(f'D{row_num}', [[metal_type]])
            sheet.update(f'E{row_num}', [[stone_type]])
            sheet.update(f'F{row_num}', [[urls_str]])
            sheet.update(f'G{row_num}', [[date_added]])
            sheet.update(f'H{row_num}', [[status]])
        return True
    except Exception as e:
        st.error(f"Error updating design in Google Sheets: {e}")
        return False

def delete_design_from_sheets(sheet, design_no):
    """Delete a design from Google Sheets"""
    try:
        if sheet is None:
            return False
        
        cells = sheet.findall(design_no)
        if cells:
            row_num = cells[0].row
            sheet.delete_rows(row_num)
        return True
    except Exception as e:
        st.error(f"Error deleting design from Google Sheets: {e}")
        return False

# ------------------------------
# 6. EMAIL & SECURITY CONFIGURATION
# ------------------------------
EMAIL_CONFIG = {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": "kanishkajewellers@gmail.com",
    "sender_password": st.secrets["EMAIL_PASSWORD"] if "EMAIL_PASSWORD" in st.secrets else "your_app_password"
}

PASSWORD_FILE = "excel_data/admin_password.json"
OTP_FILE = "excel_data/otp_storage.json"

# ------------------------------
# 7. THEME & UI INITIALIZATION (DARK THEME ONLY - NO TOGGLE)
# ------------------------------
if 'theme' not in st.session_state:
    st.session_state.theme = "🌙 Dark Theme"
    st.session_state.bg_color = "#1A2634"
    st.session_state.card_bg = "#0F1A24"
    st.session_state.text_color = "#FFFFFF"
    st.session_state.border_color = "#2A3A4A"
    st.session_state.accent_gold = "#D4AF37"
    st.session_state.accent_purple = "#9D7EBD"

# Display logo and header
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    if os.path.exists("header_logo_1764154359.png"):
        st.image("header_logo_1764154359.png", use_container_width=True)
    else:
        st.markdown("<h1 style='text-align: center; color: #D4AF37; font-size: 2.5rem; margin-bottom: 0;'>KANISHKA JEWELLERS</h1>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align: center; color: #FFFFFF; font-size: 1.8rem; margin-top: 0.5rem;'>Kanishka Jewellers Pvt Ltd</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #D4AF37; font-size: 1.2rem;'>✨ AI-Powered Design Studio ✨</p>", unsafe_allow_html=True)

st.markdown("<hr style='border: 1px solid #D4AF37; opacity: 0.3;'>", unsafe_allow_html=True)

# ------------------------------
# 8. HELPER FUNCTIONS
# ------------------------------
def get_base64_logo():
    if os.path.exists("header_logo_1764154359.png"):
        with open("header_logo_1764154359.png", "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""

# Password management
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def load_admin_password():
    if os.path.exists(PASSWORD_FILE):
        with open(PASSWORD_FILE, 'r') as f:
            data = json.load(f)
            return data.get('password', hash_password('admin123'))
    else:
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
        'expires': time.time() + 300
    }
    if os.path.exists(OTP_FILE):
        with open(OTP_FILE, 'r') as f:
            all_otps = json.load(f)
    else:
        all_otps = {}
    current_time = time.time()
    all_otps = {k: v for k, v in all_otps.items() if v.get('expires', 0) > current_time}
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
            del all_otps[otp]
            with open(OTP_FILE, 'w') as f:
                json.dump(all_otps, f)
            return True
    return False

def send_otp_email(email, otp):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG['sender_email']
        msg['To'] = email
        msg['Subject'] = "Password Reset OTP - Kanishka Jewellers"
        body = f"""
        <html>
        <body>
            <h2>Your OTP for password reset is: {otp}</h2>
            <p>This OTP will expire in 5 minutes.</p>
        </body>
        </html>
        """
        msg.attach(MIMEText(body, 'html'))
        server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
        server.starttls()
        server.login(EMAIL_CONFIG['sender_email'], EMAIL_CONFIG['sender_password'])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Failed to send email: {str(e)}")
        return False

# Category colors
CATEGORY_COLORS = {
    "Ring": "#FF6B6B",
    "Necklace": "#4ECDC4",
    "Earring": "#45B7D1",
    "Bracelet": "#96CEB4",
    "Pendant": "#FFE66D",
    "Brooch": "#FF9F1C",
    "Cufflink": "#C77DFF",
    "Other": "#A8A8A8"
}

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

# Create folders
os.makedirs("images", exist_ok=True)
os.makedirs("embeddings", exist_ok=True)
os.makedirs("excel_data", exist_ok=True)
os.makedirs("temp_uploads", exist_ok=True)

# ------------------------------
# 9. CLOUDINARY IMAGE HANDLING FUNCTIONS
# ------------------------------
def upload_to_cloudinary(uploaded_file, design_no, angle_index):
    if not CLOUDINARY_CONFIGURED:
        return None
    try:
        public_id = f"kanishka_designs/{design_no}/angle_{angle_index + 1}"
        upload_result = cloudinary.uploader.upload(
            uploaded_file,
            public_id=public_id,
            folder=f"kanishka_designs/{design_no}",
            overwrite=True
        )
        return {
            'url': upload_result['secure_url'],
            'public_id': upload_result['public_id'],
            'angle': angle_index + 1
        }
    except Exception as e:
        st.error(f"Cloudinary upload failed: {e}")
        return None

def upload_multiple_images(uploaded_files, design_no):
    saved_urls = []
    for i, file in enumerate(uploaded_files[:4]):
        result = upload_to_cloudinary(file, design_no, i)
        if result:
            saved_urls.append(result['url'])
    return saved_urls

def get_cloudinary_url(design_no, angle=1):
    if not CLOUDINARY_CONFIGURED:
        return None
    try:
        public_id = f"kanishka_designs/{design_no}/angle_{angle}"
        url = cloudinary.CloudinaryImage(public_id).build_url()
        return url
    except:
        return None

def get_all_design_images(design_no):
    urls = []
    for angle in range(1, 5):
        url = get_cloudinary_url(design_no, angle)
        if url:
            try:
                response = requests.head(url)
                if response.status_code == 200:
                    urls.append(url)
            except:
                pass
    return urls

def delete_from_cloudinary(design_no):
    if not CLOUDINARY_CONFIGURED:
        return False
    try:
        cloudinary.api.delete_resources_by_prefix(f"kanishka_designs/{design_no}")
        return True
    except Exception as e:
        st.error(f"Cloudinary delete failed: {e}")
        return False

# Local fallback functions
def save_local_images(uploaded_files, design_no):
    saved_files = []
    for i, file in enumerate(uploaded_files[:4]):
        ext = file.name.split('.')[-1]
        filename = f"{design_no}_angle{i+1}.{ext}"
        filepath = os.path.join("images", filename)
        with open(filepath, "wb") as f:
            f.write(file.getbuffer())
        saved_files.append(filepath)
    return saved_files

def load_local_images(design_no):
    images = []
    for ext in ['jpg', 'jpeg', 'png']:
        pattern = os.path.join("images", f"{design_no}_angle*.{ext}")
        images.extend(glob.glob(pattern))
    return sorted(images)

def load_image(design_no, index=0):
    if CLOUDINARY_CONFIGURED:
        urls = get_all_design_images(design_no)
        if urls and index < len(urls):
            return urls[index]
    images = load_local_images(design_no)
    if images and index < len(images):
        return images[index]
    return None

# ------------------------------
# 10. AI & SIMILARITY FUNCTIONS
# ------------------------------
@st.cache_resource
def load_expert_detector():
    if not EXPERT_AVAILABLE:
        return None
    try:
        with st.spinner("🔥 Loading expert AI models..."):
            detector = ExpertJewelryDetector(use_gpu=True)
            return detector
    except Exception as e:
        st.error(f"Expert detector failed to load: {e}")
        return None

@st.cache_data
def load_expert_embeddings():
    embedding_file = "embeddings/expert_embeddings.pkl"
    if os.path.exists(embedding_file):
        with open(embedding_file, 'rb') as f:
            return pickle.load(f)
    return None

def find_similar_designs(query_embedding, embeddings_dict, top_k=8):
    if query_embedding is None or embeddings_dict is None:
        return []
    similarities = []
    for design_name, emb in embeddings_dict.items():
        sim = cosine_similarity([query_embedding], [emb])[0][0]
        similarities.append((design_name, sim))
    similarities.sort(key=lambda x: x[1], reverse=True)
    return similarities[:top_k]

def get_category_color(category):
    return CATEGORY_COLORS.get(category, CATEGORY_COLORS["Other"])

# ------------------------------
# 11. DATA MANAGEMENT (Google Sheets)
# ------------------------------
# Initialize Google Sheets connection and load data
sheet = get_google_sheets_connection()
designs_df = load_designs_from_sheets(sheet)

if 'designs_df' not in st.session_state:
    st.session_state.designs_df = designs_df if not designs_df.empty else pd.DataFrame(columns=['Design_No', 'Design_Name', 'Category', 'Metal_Type', 'Stone_Type', 'Image_URLs', 'Date_Added', 'Status'])

# Initialize session state for categories, metals, stones
if 'categories' not in st.session_state:
    st.session_state.categories = ['Ring', 'Necklace', 'Earring', 'Bracelet', 'Pendant', 'Brooch', 'Cufflink', 'Other']
if 'metal_types' not in st.session_state:
    st.session_state.metal_types = ['Gold', 'Silver', 'Platinum', 'Rose Gold', 'White Gold']
if 'stone_types' not in st.session_state:
    st.session_state.stone_types = ['Diamond', 'Emerald', 'Ruby', 'Sapphire', 'Pearl', 'Opal', 'Jade', 'None', 'Other']
if 'expert_mode' not in st.session_state:
    st.session_state.expert_mode = True if EXPERT_AVAILABLE else False
if 'password_correct' not in st.session_state:
    st.session_state.password_correct = False
if 'forgot_password' not in st.session_state:
    st.session_state.forgot_password = False
if 'otp_sent' not in st.session_state:
    st.session_state.otp_sent = False
if 'otp_verified' not in st.session_state:
    st.session_state.otp_verified = False
if 'generated_otp' not in st.session_state:
    st.session_state.generated_otp = ""

# ------------------------------
# 12. AUTHENTICATION & UI HELPERS
# ------------------------------
def check_password():
    if st.session_state.password_correct:
        return True
    
    with st.sidebar:
        st.markdown("### 🔐 Admin Login")
        if not st.session_state.forgot_password:
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
            st.markdown("#### 🔑 Reset Password")
            if not st.session_state.otp_sent:
                email = st.text_input("Enter your email", key="reset_email")
                if st.button("📧 Send OTP", key="send_otp_btn"):
                    if email:
                        otp = generate_otp()
                        if send_otp_email(email, otp):
                            st.session_state.reset_email = email
                            st.session_state.generated_otp = otp
                            st.session_state.otp_sent = True
                            st.success(f"✅ OTP sent to {email}")
                            st.rerun()
            elif not st.session_state.otp_verified:
                st.info(f"📧 OTP sent to {st.session_state.reset_email}")
                otp_input = st.text_input("Enter OTP", key="otp_input")
                if st.button("✅ Verify OTP", key="verify_otp_btn"):
                    if otp_input == st.session_state.generated_otp:
                        st.session_state.otp_verified = True
                        st.success("✅ OTP verified!")
                        st.rerun()
            else:
                new_password = st.text_input("New password", type="password", key="new_pwd")
                confirm_password = st.text_input("Confirm password", type="password", key="confirm_pwd")
                if st.button("💾 Reset Password", key="reset_pwd_btn"):
                    if new_password and confirm_password and new_password == confirm_password:
                        save_admin_password(new_password)
                        st.success("✅ Password reset successful!")
                        st.session_state.forgot_password = False
                        st.session_state.otp_sent = False
                        st.session_state.otp_verified = False
                        st.session_state.password_correct = True
                        st.rerun()
    return False

def display_contact():
    with st.expander("📞 Contact Information", expanded=False):
        st.markdown(f"""
        <div class="contact-info">
            <div class="contact-item"><span class="contact-icon">📞</span> {COMPANY_PHONE}</div>
            <div class="contact-item"><span class="contact-icon">✉️</span> {COMPANY_EMAIL}</div>
            <div class="contact-item"><span class="contact-icon">🌐</span> {COMPANY_WEBSITE}</div>
        </div>
        """, unsafe_allow_html=True)

# ------------------------------
# 13. MAIN APP
# ------------------------------
def main():
    # Sidebar - NO THEME SELECTOR
    with st.sidebar:
        if os.path.exists("header_logo_1764154359.png"):
            st.image("header_logo_1764154359.png", use_container_width=True)
        
        st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
        
        # Mode selector
        mode = st.radio(
            "Select Mode",
            ["🔍 Main Tool", "⚙️ Admin Panel", "📊 Analytics"],
            index=0,
            key="main_mode_selector"
        )
        st.session_state.admin_mode = (mode == "⚙️ Admin Panel")
        
        st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
        
        # Stats
        st.markdown("### 📊 Quick Stats")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Designs", f"{len(st.session_state.designs_df):,}")
        with col2:
            active_count = len(st.session_state.designs_df[st.session_state.designs_df['Status'] == 'Active'])
            st.metric("Active", f"{active_count:,}")
        
        # AI Mode
        if EXPERT_AVAILABLE:
            st.markdown("### 🔬 AI Mode")
            st.success("🔥 **AI-Powered Detection Active**")
            st.session_state.expert_mode = True
        
        # Database status
        st.markdown("### 💾 Database Status")
        st.success("✅ Data stored in Google Sheets (permanent)")
        
        st.markdown("### 📞 Contact")
        st.caption(f"📱 {COMPANY_PHONE}")
        st.caption(f"✉️ {COMPANY_EMAIL}")
    
    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
    
    # ------------------------------
    # MAIN TOOL MODE
    # ------------------------------
    if not st.session_state.admin_mode and mode == "🔍 Main Tool":
        st.markdown("### 🔍 Visual Search")
        
        search_col1, search_col2, search_col3 = st.columns([1.5, 1.5, 2])
        
        with search_col1:
            st.markdown("**📤 Upload Image**")
            st.markdown('<div class="upload-area">', unsafe_allow_html=True)
            uploaded_file = st.file_uploader("", type=['jpg', 'jpeg', 'png'], key="main_upload", label_visibility="collapsed")
            if uploaded_file:
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded Image", use_container_width=True)
                st.session_state.search_image = image
                if st.button("🔍 Find Similar Designs", key="find_similar_upload_btn", use_container_width=True):
                    st.session_state.search_trigger = True
            st.markdown('</div>', unsafe_allow_html=True)
        
        with search_col2:
            st.markdown("**📋 Paste Image**")
            st.markdown('<div class="upload-area">', unsafe_allow_html=True)
            pasted_file = st.file_uploader("", type=['jpg', 'jpeg', 'png'], key="main_paste", label_visibility="collapsed")
            if pasted_file:
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
                            img_url = load_image(row['Design_No'])
                            cols = st.columns([1,3])
                            with cols[0]:
                                if img_url:
                                    st.image(img_url, width=80)
                            with cols[1]:
                                st.write(f"**{row['Design_No']}**: {row['Design_Name']}")
                                st.caption(f"{row['Category']} | {row['Metal_Type']} | {row['Stone_Type']}")
        
        # Search results
        if 'search_trigger' in st.session_state and st.session_state.search_trigger and st.session_state.search_image:
            st.markdown("### 🎯 Similarity Results")
            if st.session_state.expert_mode and EXPERT_AVAILABLE:
                detector = load_expert_detector()
                embeddings_dict = load_expert_embeddings()
                if detector and embeddings_dict:
                    with st.spinner("🔬 Expert AI analyzing..."):
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
                                        sim_icon = "🔥" if similarity >= 0.8 else "⭐" if similarity >= 0.6 else "💎"
                                        img_url = load_image(design_name)
                                        category_color = get_category_color(design_row.iloc[0]['Category'])
                                        st.markdown(f"""
                                        <div class="design-card">
                                            <h4>{sim_icon} {design_name}</h4>
                                            <p><strong>{design_row.iloc[0]['Design_Name']}</strong></p>
                                        """, unsafe_allow_html=True)
                                        if img_url:
                                            st.image(img_url, use_container_width=True)
                                        st.markdown(f"""
                                            <p>
                                                <span class="category-badge" style="background: {category_color};">{design_row.iloc[0]['Category']}</span>
                                            </p>
                                            <p>Metal: {design_row.iloc[0]['Metal_Type']}<br>Stone: {design_row.iloc[0]['Stone_Type']}</p>
                                            <p class="similarity-high">{sim_icon} {similarity_pct:.1f}% Match</p>
                                        </div>
                                        """, unsafe_allow_html=True)
                            if st.button("🗑️ Clear Results", key="clear_results_btn", use_container_width=True):
                                st.session_state.search_trigger = False
                                st.session_state.search_image = None
                                st.rerun()
                else:
                    st.warning("⚠️ Expert mode requires embeddings. Generate them in sidebar first.")
        
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
                    img_url = load_image(row['Design_No'])
                    category_color = get_category_color(row['Category'])
                    st.markdown(f"""
                    <div class="design-card">
                        <h4>{row['Design_No']}</h4>
                        <p><strong>{row['Design_Name']}</strong></p>
                    """, unsafe_allow_html=True)
                    if img_url:
                        st.image(img_url, use_container_width=True)
                    else:
                        st.caption("🖼️ No image")
                    st.markdown(f"""
                        <p><span class="category-badge" style="background: {category_color};">{row['Category']}</span></p>
                        <p>Metal: {row['Metal_Type']}<br>Stone: {row['Stone_Type']}</p>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("No designs match the selected filters")
    
    # ------------------------------
    # ADMIN PANEL MODE
    # ------------------------------
    elif st.session_state.admin_mode and mode == "⚙️ Admin Panel":
        if check_password():
            st.markdown(f"""
            <div class="admin-panel">
                <h2>⚙️ Admin Panel</h2>
                <p>Manage your design database: Add, Edit, or Delete designs (Max 4 images per design)</p>
            </div>
            """, unsafe_allow_html=True)
            
            tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
                "➕ Add Design", "✏️ Edit Design", "🗑️ Delete Design", "📊 Categories", "🪙 Metals", "🪨 Stones", "📁 Bulk Upload", "🔬 AI Training"
            ])
            
            with tab1:
                st.markdown("### Add New Design (Max 4 Images)")
                col1, col2 = st.columns(2)
                with col1:
                    new_design_no = st.text_input("Design Number *", key="add_design_no")
                    new_design_name = st.text_input("Design Name *", key="add_design_name")
                    new_category = st.selectbox("Category *", st.session_state.categories, key="add_category")
                with col2:
                    new_metal = st.selectbox("Metal Type", st.session_state.metal_types, key="add_metal")
                    new_stone = st.selectbox("Stone Type", st.session_state.stone_types, key="add_stone")
                    new_status = st.selectbox("Status", ["Active", "Inactive"], key="add_status")
                    new_date = datetime.now().strftime("%Y-%m-%d")
                    st.markdown("**Design Images (Max 4)**")
                    new_images = st.file_uploader("Upload up to 4 images", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True, key="add_multiple_images")
                    if new_images:
                        if len(new_images) > 4:
                            st.warning(f"⚠️ You selected {len(new_images)} images. Only the first 4 will be used.")
                        preview_cols = st.columns(min(len(new_images), 4))
                        for idx, img_file in enumerate(new_images[:4]):
                            with preview_cols[idx]:
                                st.image(Image.open(img_file), caption=f"Angle {idx+1}", width=120)
                if st.button("💾 Save Design", key="save_design_btn", use_container_width=True):
                    if new_design_no and new_design_name and new_images:
                        if new_design_no not in st.session_state.designs_df['Design_No'].values:
                            # Upload to Cloudinary
                            if CLOUDINARY_CONFIGURED:
                                image_urls = upload_multiple_images(new_images, new_design_no)
                            else:
                                save_local_images(new_images, new_design_no)
                                image_urls = []
                            
                            # Save to Google Sheets
                            save_design_to_sheets(sheet, new_design_no, new_design_name, new_category, new_metal, new_stone, image_urls, new_status)
                            
                            # Reload data
                            st.session_state.designs_df = load_designs_from_sheets(sheet)
                            
                            st.markdown('<div class="success-msg">✅ Design added successfully!</div>', unsafe_allow_html=True)
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("❌ Design number already exists")
                    else:
                        st.error("❌ Please fill all required fields")
            
            with tab2:
                st.markdown("### Edit Design")
                design_list = st.session_state.designs_df['Design_No'].tolist()
                design_to_edit = st.selectbox("Select Design", design_list, key="edit_design_select")
                if design_to_edit:
                    design_data = st.session_state.designs_df[st.session_state.designs_df['Design_No'] == design_to_edit].iloc[0]
                    st.markdown("**Current Images:**")
                    current_images = get_all_design_images(design_to_edit) if CLOUDINARY_CONFIGURED else load_local_images(design_to_edit)
                    if current_images:
                        img_cols = st.columns(min(len(current_images), 4))
                        for idx, img_url in enumerate(current_images[:4]):
                            with img_cols[idx]:
                                st.image(img_url, caption=f"Angle {idx+1}", width=120)
                    else:
                        st.info("No images uploaded")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        edit_name = st.text_input("Design Name", value=design_data['Design_Name'], key=f"edit_name_{design_to_edit}")
                        edit_category = st.selectbox("Category", st.session_state.categories, index=st.session_state.categories.index(design_data['Category']), key=f"edit_category_{design_to_edit}")
                    with col2:
                        edit_metal = st.selectbox("Metal Type", st.session_state.metal_types, index=st.session_state.metal_types.index(design_data['Metal_Type']), key=f"edit_metal_{design_to_edit}")
                        edit_stone = st.selectbox("Stone Type", st.session_state.stone_types, index=st.session_state.stone_types.index(design_data['Stone_Type']), key=f"edit_stone_{design_to_edit}")
                        edit_status = st.selectbox("Status", ["Active", "Inactive"], index=0 if design_data['Status'] == 'Active' else 1, key=f"edit_status_{design_to_edit}")
                        st.markdown("**Add More Images (optional, max 4 total)**")
                        remaining_slots = max(0, 4 - len(current_images))
                        additional_images = None
                        if remaining_slots > 0:
                            additional_images = st.file_uploader(f"Add up to {remaining_slots} more images", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True, key=f"edit_images_{design_to_edit}")
                    if st.button("💾 Update Design", key=f"update_btn_{design_to_edit}", use_container_width=True):
                        # Update images if new ones added
                        new_image_urls = design_data.get('Image_URLs', '')
                        if additional_images and remaining_slots > 0:
                            if CLOUDINARY_CONFIGURED:
                                new_urls = upload_multiple_images(additional_images[:remaining_slots], design_to_edit)
                                existing_urls = new_image_urls.split(',') if new_image_urls else []
                                new_image_urls = ','.join(existing_urls + new_urls)
                            else:
                                save_local_images(additional_images[:remaining_slots], design_to_edit)
                        
                        # Update in Google Sheets
                        update_design_in_sheets(sheet, design_to_edit, edit_name, edit_category, edit_metal, edit_stone, new_image_urls, edit_status)
                        
                        # Reload data
                        st.session_state.designs_df = load_designs_from_sheets(sheet)
                        
                        st.markdown('<div class="success-msg">✅ Design updated!</div>', unsafe_allow_html=True)
                        time.sleep(2)
                        st.rerun()
            
            with tab3:
                st.markdown("### Delete Design")
                design_list = st.session_state.designs_df['Design_No'].tolist()
                design_to_delete = st.selectbox("Select Design", design_list, key="delete_design_select")
                if design_to_delete:
                    design_data = st.session_state.designs_df[st.session_state.designs_df['Design_No'] == design_to_delete].iloc[0]
                    images = get_all_design_images(design_to_delete) if CLOUDINARY_CONFIGURED else load_local_images(design_to_delete)
                    if images:
                        st.markdown(f"**{len(images)} images found**")
                        img_cols = st.columns(min(len(images), 4))
                        for idx, img_url in enumerate(images[:4]):
                            with img_cols[idx]:
                                st.image(img_url, width=120)
                    st.warning(f"⚠️ You are about to delete: {design_to_delete} - {design_data['Design_Name']}")
                    confirm = st.checkbox("I confirm this deletion", key=f"confirm_delete_{design_to_delete}")
                    if confirm and st.button("🗑️ Permanently Delete", key=f"delete_btn_{design_to_delete}", use_container_width=True):
                        # Delete from Cloudinary
                        if CLOUDINARY_CONFIGURED:
                            delete_from_cloudinary(design_to_delete)
                        else:
                            for img_path in images:
                                if os.path.exists(img_path):
                                    os.remove(img_path)
                        
                        # Delete from Google Sheets
                        delete_design_from_sheets(sheet, design_to_delete)
                        
                        # Reload data
                        st.session_state.designs_df = load_designs_from_sheets(sheet)
                        
                        st.markdown('<div class="success-msg">✅ Design deleted!</div>', unsafe_allow_html=True)
                        time.sleep(2)
                        st.rerun()
            
            with tab4:
                st.markdown("### Manage Categories")
                col1, col2 = st.columns(2)
                with col1:
                    new_cat = st.text_input("New Category", key="new_category_input")
                    if st.button("➕ Add Category", key="add_category_btn"):
                        if new_cat and new_cat not in st.session_state.categories:
                            st.session_state.categories.append(new_cat)
                            CATEGORY_COLORS[new_cat] = "#A8A8A8"
                            st.success(f"✅ Category '{new_cat}' added!")
                            st.rerun()
                with col2:
                    if st.session_state.categories:
                        cat_to_remove = st.selectbox("Select Category", st.session_state.categories, key="remove_category_select")
                        if st.button("❌ Remove Category", key="remove_category_btn"):
                            in_use = len(st.session_state.designs_df[st.session_state.designs_df['Category'] == cat_to_remove]) > 0
                            if in_use:
                                st.error("Cannot remove category with designs assigned")
                            else:
                                st.session_state.categories.remove(cat_to_remove)
                                st.success(f"✅ Category removed!")
                                st.rerun()
            
            # NEW TAB: Manage Metals
            with tab5:
                st.markdown("### Manage Metals")
                st.markdown("Add or remove metal types for your designs")
                
                col1, col2 = st.columns(2)
                with col1:
                    new_metal = st.text_input("New Metal Type", key="new_metal_input")
                    if st.button("➕ Add Metal", key="add_metal_btn"):
                        if new_metal and new_metal not in st.session_state.metal_types:
                            st.session_state.metal_types.append(new_metal)
                            st.success(f"✅ Metal '{new_metal}' added!")
                            st.rerun()
                        elif new_metal in st.session_state.metal_types:
                            st.warning("Metal type already exists")
                        else:
                            st.error("Please enter a metal type")
                
                with col2:
                    if st.session_state.metal_types:
                        removable_metals = [m for m in st.session_state.metal_types]
                        if removable_metals:
                            metal_to_remove = st.selectbox("Select Metal to Remove", removable_metals, key="remove_metal_select")
                            if st.button("❌ Remove Metal", key="remove_metal_btn"):
                                in_use = len(st.session_state.designs_df[st.session_state.designs_df['Metal_Type'] == metal_to_remove]) > 0
                                if in_use:
                                    st.error(f"Cannot remove '{metal_to_remove}' - it is assigned to existing designs")
                                else:
                                    st.session_state.metal_types.remove(metal_to_remove)
                                    st.success(f"✅ Metal '{metal_to_remove}' removed!")
                                    st.rerun()
                        else:
                            st.info("No removable metals")
                    else:
                        st.info("No metals available")
                
                # Display current metals
                st.markdown("### 📋 Current Metal Types")
                st.markdown(", ".join(st.session_state.metal_types))
            
            # Tab 6: Manage Stones
            with tab6:
                st.markdown("### Manage Stones")
                st.markdown("Add or remove stone types for your designs")
                
                col1, col2 = st.columns(2)
                with col1:
                    new_stone = st.text_input("New Stone Type", key="new_stone_input")
                    if st.button("➕ Add Stone", key="add_stone_btn"):
                        if new_stone and new_stone not in st.session_state.stone_types:
                            st.session_state.stone_types.append(new_stone)
                            st.success(f"✅ Stone '{new_stone}' added!")
                            st.rerun()
                        elif new_stone in st.session_state.stone_types:
                            st.warning("Stone type already exists")
                        else:
                            st.error("Please enter a stone type")
                
                with col2:
                    if st.session_state.stone_types:
                        removable_stones = [s for s in st.session_state.stone_types if s != 'None']
                        if removable_stones:
                            stone_to_remove = st.selectbox("Select Stone to Remove", removable_stones, key="remove_stone_select")
                            if st.button("❌ Remove Stone", key="remove_stone_btn"):
                                in_use = len(st.session_state.designs_df[st.session_state.designs_df['Stone_Type'] == stone_to_remove]) > 0
                                if in_use:
                                    st.error(f"Cannot remove '{stone_to_remove}' - it is assigned to existing designs")
                                else:
                                    st.session_state.stone_types.remove(stone_to_remove)
                                    st.success(f"✅ Stone '{stone_to_remove}' removed!")
                                    st.rerun()
                        else:
                            st.info("No removable stones (only 'None' remains)")
                    else:
                        st.info("No stones available")
                
                # Display current stones
                st.markdown("### 📋 Current Stone Types")
                st.markdown(", ".join(st.session_state.stone_types))
            
            with tab7:
                st.markdown("### Bulk Upload Images")
                bulk_images = st.file_uploader("Select multiple images (name as design_angle.jpg)", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True, key="bulk_upload")
                if bulk_images:
                    st.markdown(f"**{len(bulk_images)} images selected**")
                    if st.button("📤 Upload All Images", key="bulk_upload_btn", use_container_width=True):
                        design_groups = {}
                        for img_file in bulk_images:
                            design_no = img_file.name.split('_')[0] if '_' in img_file.name else os.path.splitext(img_file.name)[0]
                            if design_no not in design_groups:
                                design_groups[design_no] = []
                            design_groups[design_no].append(img_file)
                        
                        for design_no, images in design_groups.items():
                            if CLOUDINARY_CONFIGURED:
                                upload_multiple_images(images[:4], design_no)
                            else:
                                save_local_images(images[:4], design_no)
                        st.success(f"✅ {len(bulk_images)} images uploaded!")
                        st.rerun()
            
            with tab8:
                st.markdown("### 🔬 AI Model Training")
                if EXPERT_AVAILABLE:
                    if st.button("🚀 Run Expert Analysis", key="run_expert_btn", use_container_width=True):
                        detector = load_expert_detector()
                        if detector:
                            with st.spinner("🔬 Analyzing all designs..."):
                                detector.process_all_designs("images")
                            st.success("✅ Expert embeddings generated!")
                            st.cache_data.clear()
                            st.rerun()
                else:
                    st.error("expert_detector.py not found")
            
            # Preview current designs
            st.markdown("### 📋 Current Designs")
            display_df = st.session_state.designs_df.copy()
            st.dataframe(display_df[['Design_No', 'Design_Name', 'Category', 'Metal_Type', 'Stone_Type', 'Status']], use_container_width=True, height=300)
    
    # ------------------------------
    # ANALYTICS MODE
    # ------------------------------
    elif mode == "📊 Analytics":
        st.markdown("### 📊 Design Analytics Dashboard")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f'<div class="stat-card"><p>Total Designs</p><p class="stat-number">{len(st.session_state.designs_df):,}</p></div>', unsafe_allow_html=True)
        with col2:
            active = len(st.session_state.designs_df[st.session_state.designs_df['Status'] == 'Active'])
            st.markdown(f'<div class="stat-card"><p>Active Designs</p><p class="stat-number">{active:,}</p></div>', unsafe_allow_html=True)
        with col3:
            img_count = len([f for f in os.listdir("images") if f.endswith(('.jpg', '.jpeg', '.png'))])
            st.markdown(f'<div class="stat-card"><p>Images</p><p class="stat-number">{img_count:,}</p></div>', unsafe_allow_html=True)
        
        # Category Distribution
        st.markdown("#### 📊 Category Distribution")
        cat_counts = st.session_state.designs_df['Category'].value_counts().reset_index()
        cat_counts.columns = ['Category', 'Count']
        if not cat_counts.empty:
            fig = px.bar(cat_counts, x='Category', y='Count', title='Designs by Category', text='Count', color='Count', color_continuous_scale=['#D4AF37', '#5E2A84'])
            fig.update_traces(texttemplate='%{text:,}', textposition='outside')
            fig.update_layout(plot_bgcolor=st.session_state.card_bg, paper_bgcolor=st.session_state.card_bg, font_color=st.session_state.text_color)
            st.plotly_chart(fig, use_container_width=True)
        
        # Metal Type Distribution
        st.markdown("#### 🏷️ Metal Type Distribution")
        metal_counts = st.session_state.designs_df['Metal_Type'].value_counts().reset_index()
        metal_counts.columns = ['Metal', 'Count']
        if not metal_counts.empty:
            fig = px.pie(metal_counts, values='Count', names='Metal', title='Designs by Metal Type', color_discrete_sequence=px.colors.qualitative.Pastel)
            fig.update_traces(textinfo='percent+label', texttemplate='%{label}<br>%{percent} (%{value:,})')
            fig.update_layout(plot_bgcolor=st.session_state.card_bg, paper_bgcolor=st.session_state.card_bg, font_color=st.session_state.text_color)
            st.plotly_chart(fig, use_container_width=True)
        
        # Stone Type Distribution
        st.markdown("#### 💎 Stone Type Distribution")
        stone_counts = st.session_state.designs_df['Stone_Type'].value_counts().reset_index()
        stone_counts.columns = ['Stone', 'Count']
        if not stone_counts.empty:
            fig = px.bar(stone_counts, x='Stone', y='Count', title='Designs by Stone Type', text='Count', color='Count', color_continuous_scale=['#9D7EBD', '#D4AF37'])
            fig.update_traces(texttemplate='%{text:,}', textposition='outside')
            fig.update_layout(plot_bgcolor=st.session_state.card_bg, paper_bgcolor=st.session_state.card_bg, font_color=st.session_state.text_color)
            st.plotly_chart(fig, use_container_width=True)
        
        # Recent additions
        st.markdown("#### 🕒 Recent Additions")
        recent = st.session_state.designs_df.sort_values('Date_Added', ascending=False).head(10)
        st.dataframe(recent[['Design_No', 'Design_Name', 'Category', 'Metal_Type', 'Stone_Type', 'Date_Added']], use_container_width=True)
        
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