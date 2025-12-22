import streamlit as st
import os
import json
import io
import datetime
import smtplib
from PIL import Image
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# Google系ライブラリ
from google import genai
from google.genai import types
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# デザイン・可視化
import plotly.graph_objects as go

# PDF生成
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor

# ---------------------------------------------------------
# 0. 初期設定 & セキュリティ
# ---------------------------------------------------------
st.set_page_config(page_title="Visionary Analysis | ThomYoshida", layout="wide") 

# デザイン定義 (COLORS)
COLORS = {
    "bg": "#1E1E1E",
    "text": "#E0E0E0", 
    "accent": "#D6AE60", 
    "sub": "#7A96A0", 
    "forest": "#528574", 
    "card": "#2B2B2B" 
}

# フォント登録（日本語対応）
try:
    pdfmetrics.registerFont(UnicodeCIDFont('HeiseiMin-W3')) 
    pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5')) 
    FONT_SERIF = 'HeiseiMin-W3'
    FONT_SANS = 'HeiseiKakuGo-W5'
except:
    FONT_SERIF = 'Helvetica' # フォールバック
    FONT_SANS = 'Helvetica'

# APIキー設定
if "GEMINI_API_KEY" in st.secrets:
    os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]

# パスワード認証機能
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
    
    # secretsにパスワード設定がなければスキップ
    if "APP_PASSWORD" not in st.secrets:
        return True

    if st.session_state.password_correct:
        return True
    
    st.markdown("### 🔒 Restricted Access")
    password_input = st.text_input("Enter Passcode", type="password")
    if password_input:
        if password_input == st.secrets["APP_PASSWORD"]:
            st.session_state.password_correct = True
            st.rerun()
        else:
            st.error("Invalid Passcode")
    st.stop()

check_password()

# ---------------------------------------------------------
# 1. デザイン & ユーティリティ関数
# ---------------------------------------------------------
def apply_custom_css():
    st.markdown(f"""
    <style>
        .stApp {{ background-color: {COLORS["bg"]}; color: {COLORS["text"]}; }}
        h1, h2, h3, h4 {{ font-family: "Hiragino Mincho ProN", serif !important; color: {COLORS["text"]} !important; }}
        p, div, label, span {{ font-family: "Hiragino Kaku Gothic ProN", sans-serif; color: {COLORS["text"]}; }}
        .stTextInput > div > div > input {{ background-color: #2B2B2B; color: #FFF; border: 1px solid #444; }}
        div.stButton > button {{
            background-color: {COLORS["sub"]}; color: white; border-radius: 4px; border: none;
            padding: 10px 24px; letter-spacing: 0.1em;
        }}
        div.stButton > button:hover {{ background-color: {COLORS["forest"]}; }}
        .stDownloadButton > button {{
            width: 100% !important; background-color: {COLORS["accent"]} !important;
            color: #1E1E1E !important; border: none !important;
            font-weight: bold !important;
        }}
        .streamlit-expanderHeader {{ background-color: {COLORS["card"]}; color: {COLORS["text"]}; }}
        section[data-testid="stSidebar"] {{ background-color: #111; }}
    </style>
    """, unsafe_allow_html=True)

apply_custom_css()

def resize_image_for_api(image, max_width=1024):
    width_percent = (max_width / float(image.size[0]))
    if width_percent < 1:
        height_size = int((float(image.size[1]) * float(width_percent)))
        return image.resize((max_width, height_size), Image.Resampling.LANCZOS)
    return image

# ---------------------------------------------------------
# 2. 外部連携関数 (Sheets & Email)
# ---------------------------------------------------------
def save_to_google_sheets(name, email, diagnosis_type):
    if "gcp_service_account" not in st.secrets: return False
    try:
        # secretsから辞書型として読み込む
        creds_dict = dict(st.secrets["gcp_service_account"])
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # シート名は secrets.toml で指定するか、固定値
        sheet_name = st.secrets.get("SHEET_NAME", "customer_list")
        sheet = client.open(sheet_name).sheet1
        
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([now, name, email, diagnosis_type])
        return True
    except Exception as e:
        print(f"Sheets Error: {e}")
        return False

def send_email_with_pdf(user_email, pdf_buffer):
    if "GMAIL_ADDRESS" not in st.secrets or "GMAIL_APP_PASSWORD" not in st.secrets: return False
    sender_email = st.secrets["GMAIL_ADDRESS"]
    sender_password = st.secrets["GMAIL_APP_PASSWORD"]
    
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = user_email
    msg['Subject'] = "【Visionary Report】あなたの世界観診断結果"
    
    body = """
    Visionary Analysis Report をお届けします。
    
    このPDFは、あなたの感性の「標本」です。
    時折見返し、現在地を確認する羅針盤としてお使いください。
    
    Thom Yoshida
    """
    msg.attach(MIMEText(body, 'plain'))
    
    pdf_buffer.seek(0)
    part = MIMEApplication(pdf_buffer.read(), Name="Visionary_Analysis.pdf")
    part['Content-Disposition'] = 'attachment; filename="Visionary_Analysis.pdf"'
    msg.attach(part)
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        # 管理者にもBCCを送る
        recipients = [user_email, sender_email]
        server.sendmail(sender_email, recipients, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Email Error: {e}")
        return False

# ---------------------------------------------------------
# 3. PDF生成ロジック
# ---------------------------------------------------------
def create_pdf(json_data):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)
    
    # 簡易PDF生成（実際は前回の詳細な描画ロジックを入れる）
    c.setFillColor(HexColor('#F5F5F5'))
    c.rect(0, 0, width, height, fill=1, stroke=0)
    
    c.setFillColor(HexColor('#2B2723'))
    c.setFont(FONT_SERIF, 32)
    c.drawCentredString(width/2, height/2 + 10*mm, json_data.get('catchphrase', 'Visionary Report'))
    
    c.setFont(FONT_SANS, 12)
    c.drawCentredString(width/2, height/2 - 10*mm, "Worldview Analysis Report")
    
    c.setFont(FONT_SANS, 10)
    c.drawCentredString(width/2, 20*mm, "Designed by ThomYoshida AI")
    
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

# ---------------------------------------------------------
# 4. Web UI コンポーネント
# ---------------------------------------------------------
def render_web_result(data):
    st.markdown("---")
    st.caption("YOUR SOUL DEFINITION")
    st.title(f"『 {data.get('catchphrase')} 』")
    
    col1, col2 = st.columns([1, 1.5])
    
    with col1:
        st.markdown("### Sense Balance")
        metrics = data.get('sense_metrics', [])
        categories = [m['right'] for m in metrics]
        values = [m['value'] for m in metrics]
        
        if categories:
            categories.append(categories[0])
            values.append(values[0])

        fig = go.Figure(data=go.Scatterpolar(
            r=values, theta=categories, fill='toself',
            line_color=COLORS['accent'], fillcolor='rgba(214, 174, 96, 0.3)'
        ))
        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100], showticklabels=False), bgcolor=COLORS['bg']),
            paper_bgcolor='rgba(0,0,0,0)', showlegend=False,
            margin=dict(l=40, r=40, t=40, b=40),
            font=dict(color=COLORS['text'])
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("### The Formula")
        f = data.get('formula', {})
        st.info(f"**VALUES**\n\n{f.get('values', {}).get('word')}")
        st.warning(f"**STRENGTHS**\n\n{f.get('strengths', {}).get('word')}")
        st.success(f"**INTERESTS**\n\n{f.get('interests', {}).get('word')}")

# ---------------------------------------------------------
# 5. メイン実行フロー (The Pipeline)
# ---------------------------------------------------------
if 'step' not in st.session_state: st.session_state.step = 1
if 'quiz_result' not in st.session_state: st.session_state.quiz_result = None

# --- STEP 1: QUIZ ---
if st.session_state.step == 1:
    try:
        st.image("cover.jpg", use_container_width=True)
    except: pass
    
    st.title("Visionary Analysis")
    st.caption("美意識の解像度を上げる、対話型診断ツール")
    
    st.markdown("##### 01. SENSE CHECK")
    q1 = st.radio("Q. あなたが作品を作る動機は？", ["内なる衝動の解放", "社会的な問題解決", "美しさの追求"], horizontal=True)
    
    st.write("---")
    if st.button("PROCEED TO VISION"):
        if q1 == "内なる衝動の解放": st.session_state.quiz_result = "直感・情熱型"
        elif q1 == "社会的な問題解決": st.session_state.quiz_result = "論理・構築型"
        else: st.session_state.quiz_result = "美的・審美型"
        st.session_state.step = 2
        st.rerun()

# --- STEP 2: UPLOAD ---
elif st.session_state.step == 2:
    st.header("02. VISION INTEGRATION")
    st.info(f"Your Type: **{st.session_state.quiz_result}**")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Past Works")
        past_files = st.file_uploader("Origin", type=["jpg", "png"], accept_multiple_files=True, key="past")
    with col2:
        st.markdown("#### Future Vision")
        future_files = st.file_uploader("Ideal", type=["jpg", "png"], accept_multiple_files=True, key="future")

    if st.button("NEXT STEP: UNLOCK REPORT"):
        if not past_files:
            st.error("分析のために画像をアップロードしてください。")
        else:
            st.session_state.step = 3
            st.rerun()

# --- STEP 3: LEAD CAPTURE ---
elif st.session_state.step == 3:
    st.header("03. UNLOCK YOUR REPORT")
    
    with st.container():
        st.markdown(f"""
        <div style="background-color: {COLORS['card']}; padding: 30px; border-radius: 10px; border: 1px solid {COLORS['accent']}; text-align: center;">
            <h3 style="color: {COLORS['accent']};">Analysis Ready</h3>
            <p>分析準備が整いました。レポートを発行するために情報を入力してください。</p>
        </div><br>
        """, unsafe_allow_html=True)
        
        with st.form("lead_capture"):
            col_f1, col_f2 = st.columns(2)
            with col_f1: user_name = st.text_input("Name")
            with col_f2: user_email = st.text_input("Email")
            
            submit = st.form_submit_button("GENERATE REPORT", type="primary")
            
            if submit:
                if user_name and user_email:
                    st.session_state.user_name = user_name
                    st.session_state.user_email = user_email
                    save_to_google_sheets(user_name, user_email, st.session_state.quiz_result)
                    st.session_state.step = 4
                    st.rerun()
                else:
                    st.warning("情報を入力してください。")

# --- STEP 4: GENERATE & DISPLAY ---
elif st.session_state.step == 4:
    if "analysis_data" not in st.session_state:
        with st.spinner("Connecting to Visionary Core..."):
            
            # --- ここでGemini APIを実行 ---
            # デモ用ダミーデータ（実際はAPIで生成）
            data = {
                "catchphrase": "静寂の青き建築家",
                "sense_metrics": [
                    {"right": "抽象", "value": 80}, {"right": "論理", "value": 60},
                    {"right": "静寂", "value": 90}, {"right": "革新", "value": 40},
                    {"right": "永続", "value": 70}
                ],
                "formula": {
                    "values": {"word": "静謐"},
                    "strengths": {"word": "構図力"},
                    "interests": {"word": "建築"}
                }
            }
            # ---------------------------
            
            st.session_state.analysis_data = data
            pdf_buffer = create_pdf(data)
            send_email_with_pdf(st.session_state.user_email, pdf_buffer)
            st.rerun()
            
    else:
        data = st.session_state.analysis_data
        render_web_result(data)
        
        st.markdown("### Specimen Delivered")
        st.success(f"📩 {st.session_state.user_email} にレポートを送信しました。")
        
        pdf_buffer = create_pdf(data)
        st.download_button("📥 DOWNLOAD REPORT", pdf_buffer, "Visionary_Report.pdf", "application/pdf")
        
        if st.button("START OVER"):
            st.session_state.clear()
            st.rerun()
