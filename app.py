import streamlit as st
import os
from google import genai
from google.genai import types
from PIL import Image
import json
import io
import datetime
import pandas as pd
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# PDF生成用ライブラリ
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor

# ---------------------------------------------------------
# ▼▼▼ セキュリティ対応版: APIキーの設定 ▼▼▼
if "GEMINI_API_KEY" in st.secrets:
    os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
else:
    user_api_key = st.sidebar.text_input("Gemini APIキーを入力してください", type="password")
    if user_api_key:
        os.environ["GEMINI_API_KEY"] = user_api_key
    else:
        st.warning("⚠️ APIキー未設定：サイドバーにキーを入力するか、管理画面でSecretsを設定してください。")
        st.stop()

# ==========================================
# 🔒 セキュリティ: パスワード認証機能
# ==========================================
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
    if st.session_state.password_correct:
        return True
    
    if "APP_PASSWORD" not in st.secrets:
        return True

    st.header("🔒 ログインが必要です")
    password_input = st.text_input("パスワードを入力してください", type="password")
    
    if password_input:
        if password_input == st.secrets["APP_PASSWORD"]:
            st.session_state.password_correct = True
            st.rerun()
        else:
            st.error("パスワードが間違っています")
    st.stop()

check_password()

# ---------------------------------------------------------
# 🖼 画像軽量化機能 (タイムアウト対策)
# ---------------------------------------------------------
def resize_image_for_api(image, max_width=1024):
    """AIに送る前に画像をリサイズして通信エラーを防ぐ"""
    width_percent = (max_width / float(image.size[0]))
    if width_percent < 1: # 指定より大きい場合のみ縮小
        height_size = int((float(image.size[1]) * float(width_percent)))
        return image.resize((max_width, height_size), Image.Resampling.LANCZOS)
    return image

# ---------------------------------------------------------
# 📊 顧客リスト保存機能 (Google Sheets)
# ---------------------------------------------------------
def save_to_google_sheets(name, email, diagnosis_type):
    """Googleスプレッドシートに顧客情報を追記する"""
    if "gcp_service_account" not in st.secrets:
        return False

    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
        client = gspread.authorize(creds)
        sheet = client.open("customer_list").sheet1
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([now, name, email, diagnosis_type])
        return True
    except Exception as e:
        st.error(f"リスト保存エラー: {e}")
        return False

# ---------------------------------------------------------
# 📧 メール送信機能
# ---------------------------------------------------------
def send_email_with_pdf(user_email, pdf_buffer):
    if "GMAIL_ADDRESS" not in st.secrets or "GMAIL_APP_PASSWORD" not in st.secrets:
        return False
    sender_email = st.secrets["GMAIL_ADDRESS"]
    sender_password = st.secrets["GMAIL_APP_PASSWORD"]
    organizer_email = "thomyoshida@gmail.com"
    recipients = [organizer_email]
    if user_email:
        recipients.append(user_email)
    subject = "【世界観診断結果】Visionary Analysis Report"
    body = """
    世界観診断にご参加いただきありがとうございます。
    あなたの診断結果レポート（PDF）を添付いたしました。
    
    Visionary Analysis Tool by ThomYoshida
    """
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = ", ".join(recipients)
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    pdf_buffer.seek(0)
    part = MIMEApplication(pdf_buffer.read(), Name="Visionary_Analysis.pdf")
    part['Content-Disposition'] = 'attachment; filename="Visionary_Analysis.pdf"'
    msg.attach(part)
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipients, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        st.error(f"メール送信エラー: {e}")
        return False

# ---------------------------------------------------------
# 🎨 デザイン・配色設定
# ---------------------------------------------------------
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiMin-W3')) 
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5')) 
FONT_SERIF = 'HeiseiMin-W3'
FONT_SANS = 'HeiseiKakuGo-W5'

C_MAIN_SHADOW = HexColor('#2B2723')
C_BG_WHITE    = HexColor('#F5F5F5')
C_ACCENT_BLUE = HexColor('#7A96A0')
C_WARM_BEIGE  = HexColor('#D1C0AF')
C_MAUVE_GRAY  = HexColor('#A39E99')
C_FOREST_TEAL = HexColor('#528574')
C_MUTE_AMBER  = HexColor('#D6AE60')
C_TEXT_WHITE  = HexColor('#FFFFFF')

# ==========================================
# 🖌️ Web UI カスタムCSS
# ==========================================
def apply_custom_css():
    st.markdown("""
    <style>
        .stApp { background-color: #F5F5F5; color: #2B2723; }
        h1, h2, h3 { font-family: "Hiragino Mincho ProN", serif !important; color: #2B2723 !important; }
        p, div, label { font-family: "Hiragino Kaku Gothic ProN", sans-serif; color: #2B2723; }
        div.stButton > button {
            background-color: #7A96A0; color: white; border-radius: 24px; border: none;
            padding: 10px 24px; transition: all 0.3s ease;
        }
        div.stButton > button:hover { background-color: #528574; }
        .stDownloadButton > button {
            width: 100% !important; height: 80px !important; font-size: 24px !important;
            font-weight: bold !important; background-color: #528574 !important;
            color: #FFFFFF !important; border-radius: 12px !important;
            border: 2px solid #2B2723 !important;
            box-shadow: 0 4px 10px rgba(0,0,0,0.2) !important;
        }
        .stDownloadButton > button:hover {
            background-color: #2
