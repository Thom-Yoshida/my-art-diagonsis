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
# 🖼 画像軽量化機能
# ---------------------------------------------------------
def resize_image_for_api(image, max_width=1024):
    """AIに送る前に画像をリサイズして通信エラーを防ぐ"""
    width_percent = (max_width / float(image.size[0]))
    if width_percent < 1:
        height_size = int((float(image.size[1]) * float(width_percent)))
        return image.resize((max_width, height_size), Image.Resampling.LANCZOS)
    return image

# ---------------------------------------------------------
# 📊 顧客リスト保存機能 (Google Sheets)
# ---------------------------------------------------------
def save_to_google_sheets(name, email, diagnosis_type):
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
            background-color: #2B2723 !important; color: #D6AE60 !important; transform: translateY(-2px);
        }
        .stTextInput > div > div > input { background-color: #FFFFFF; border: 1px solid #D1C0AF; border-radius: 8px; }
        section[data-testid="stSidebar"] { background-color: #EBEBEB; }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# 📝 PDF生成ロジック
# ---------------------------------------------------------
def draw_organic_shape(c, x, y, size, color):
    c.setFillColor(color)
    c.setStrokeColor(color)
    c.circle(x, y, size, fill=1, stroke=0)

def draw_header(c, title, page_num):
    width, height = landscape(A4)
    c.setFillColor(C_BG_WHITE)
    c.rect(0, 0, width, height, fill=1, stroke=0)
    draw_organic_shape(c, 10*mm, height - 10*mm, 15*mm, C_WARM_BEIGE)
    draw_organic_shape(c, width - 10*mm, 10*mm, 20*mm, C_ACCENT_BLUE)
    c.setFont(FONT_SANS, 9)
    c.setFillColor(C_MAUVE_GRAY)
    c.drawRightString(width - 36*mm, 10*mm, f"{page_num}")

def draw_wrapped_text(c, text, x, y, font, size, max_width, leading):
    c.setFont(font, size)
    text_obj = c.beginText(x, y)
    text_obj.setFont(font, size)
    text_obj.setLeading(leading)
    char_limit = int(max_width / (size * 0.9))
    if char_limit < 1: char_limit = 1
    
    for line in text.split('\n'):
        if len(line) == 0:
            text_obj.textLine("")
            continue
        for i in range(0, len(line), char_limit):
            text_obj.textLine(line[i:i+char_limit])
    c.drawText(text_obj)

def draw_slider(c, x, y, width_mm, left_text, right_text, value):
    bar_width = width_mm * mm
    c.setFont(FONT_SERIF, 10)
    c.setFillColor(C_MAIN_SHADOW)
    c.drawRightString(x - 5*mm, y - 1*mm, left_text)
    c.drawString(x + bar_width + 5*mm, y - 1*mm, right_text)
    c.setStrokeColor(C_MAUVE_GRAY)
    c.setLineWidth(0.5)
    c.line(x, y, x + bar_width, y)
    c.line(x, y, x + 1.5*mm, y + 1.5*mm)
    c.line(x, y, x + 1.5*mm, y - 1.5*mm)
    c.line(x + bar_width, y, x + bar_width - 1.5*mm, y + 1.5*mm)
    c.line(x + bar_width, y, x + bar_width - 1.5*mm, y - 1.5*mm)
    dot_x = x + (value / 100) * bar_width
    c.setFillColor(C_FOREST_TEAL)
    c.circle(dot_x, y, 1.8*mm, fill=1, stroke=0)
    c.setStrokeColor(C_WARM_BEIGE)
    c.line(x + bar_width/2, y - 1*mm, x + bar_width/2, y + 1*mm)

def create_pdf(json_data, quiz_summary):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)
    MARGIN_X = width * 0.12 
    CONTENT_WIDTH = width - (MARGIN_X * 2)
    
    # -----------------------------------------------
    # P1. 表紙
    # -----------------------------------------------
    bg_drawn = False
    try:
        c.drawImage("cover.jpg", 0, 0, width=width, height=height, preserveAspectRatio=True, anchor='c')
        bg_drawn = True
    except Exception:
        draw_header(c, "", 1)
    text_color = C_TEXT_WHITE if bg_drawn else C_MAIN_SHADOW
    
    c.setFont(FONT_SERIF, 40)
    c.setFillColor(text_color)
    catchphrase = json_data.get('catchphrase', '無題')
    c.drawCentredString(width/2, height/2 + 5*mm, catchphrase)
    c.setFont(FONT_SANS, 14)
    c.setFillColor(text_color)
    c.drawCentredString(width/2, height/2 - 15*mm, "Worldview Analysis Report")
    date_str = datetime.datetime.now().strftime("%Y.%m.%d")
    c.setFont(FONT_SERIF, 10)
    c.setFillColor(text_color)
    c.drawCentredString(width/2, 20*mm, f"Designed by ThomYoshida AI | {date_str}")
    c.showPage()

    # -----------------------------------------------
    # P2. キーワード対比 (12個ずつ)
    # -----------------------------------------------
    draw_header(c, "", 2)
    c.setFont(FONT_SANS, 12)
    c.setFillColor(C_ACCENT_BLUE)
    c.drawString(MARGIN_X, height - 25*mm, "01. KEYWORD CONTRAST")
    c.setFont(FONT_SERIF, 30)
    c.setFillColor(C_MUTE_AMBER)
    c.drawCentredString(width/2, height/2, "▶︎")
    
    # 左側
    c.setFont(FONT_SERIF, 20)
    c.setFillColor(C_MAIN_SHADOW)
    c.drawCentredString(width/3, height - 45*mm, "PAST / ORIGIN")
    c.setStrokeColor(C_MAUVE_GRAY)
    c.line(width/3 - 30*mm, height - 50*mm, width/3 + 30*mm, height - 50*mm)
    
    past_kws = json_data.get('twelve_past_keywords', [])
    c.setFont(FONT_SANS, 11) # 数が増えたので少し小さく
    c.setFillColor(C_MAUVE_GRAY)
    start_y = height - 60*mm
    gap_y = 9*mm
    for kw in past_kws[:12]: # 最大12個
        c.drawCentredString(width/3, start_y, kw)
        start_y -= gap_y

    # 右側
    c.setFont(FONT_SERIF, 20)
    c.setFillColor(C_FOREST_TEAL)
    c.drawCentredString(width*2/3, height - 45*mm, "FUTURE / VISION")
    c.setStrokeColor(C_FOREST_TEAL)
    c.line(width*2/3 - 30*mm, height - 50*mm, width*2/3 + 30*mm, height - 50*mm)
    
    future_kws = json_data.get('twelve_future_keywords', [])
    c.setFont(FONT_SANS, 11)
    c.setFillColor(C_MAIN_SHADOW)
    start_y = height - 60*mm
    for kw in future_kws[:12]:
        c.drawCentredString(width*2/3, start_y, kw)
        start_y -= gap_y
    c.showPage()

    # -----------------------------------------------
    # P3. 数式 (The Formula)
    # -----------------------------------------------
    draw_header(c, "", 3)
    c.setFont(FONT_SANS, 12)
    c.setFillColor(C_ACCENT_BLUE)
    c.drawString(MARGIN_X, height - 25*mm, "02. THE FORMULA")
    
    formula = json_data.get('formula', {})
    center_y = height/2 + 35*mm
    desc_y = height/2 + 5*mm
    x1 = MARGIN_X + (CONTENT_WIDTH * 0.15)
    x2 = width / 2
    x3 = width - MARGIN_X - (CONTENT_WIDTH * 0.15)
    
    circle_r = 16*mm
    c.setStrokeColor(C_FOREST_TEAL)
    c.setLineWidth(1)
    c.circle(x1, center_y, circle_r, fill=0, stroke=1)
    c.circle(x2, center_y, circle_r, fill=0, stroke=1)
    c.circle(x3, center_y, circle_r, fill=0, stroke=1)

    c.setFont(FONT_SERIF, 14)
    c.setFillColor(C_MAIN_SHADOW)
    c.drawCentredString(x1, center_y + 6*mm, "Values")
    c.setFont(FONT_SANS, 11)
    c.setFillColor(C_FOREST_TEAL)
    c.drawCentredString(x1, center_y - 4*mm, formula.get('values', {}).get('word', '---'))

    c.setFont(FONT_SERIF, 14)
    c.setFillColor(C_MAIN_SHADOW)
    c.drawCentredString(x2, center_y + 6*mm, "Strengths")
    c.setFont(FONT_SANS, 11)
    c.setFillColor(C_FOREST_TEAL)
    c.drawCentredString(x2, center_y - 4*mm, formula.get('strengths', {}).get('word', '---'))

    c.setFont(FONT_SERIF, 14)
    c.setFillColor(C_MAIN_SHADOW)
    c.drawCentredString(x3, center_y + 6*mm, "Interests")
    c.setFont(FONT_SANS, 11)
    c.setFillColor(C_FOREST_TEAL)
    # 具体的なジャンルなどを表示するため、少し文字が長くなる可能性がある
    draw_wrapped_text(c, formula.get('interests', {}).get('word', '---'), x3 - 15*mm, center_y - 2*mm, FONT_SANS, 10, 30*mm, 10)

    c.setFont(FONT_SERIF, 24)
    c.setFillColor(C_MUTE_AMBER)
    c.drawCentredString((x1+x2)/2, center_y, "×")
    c.drawCentredString((x2+x3)/2, center_y, "×")

    c.setFillColor(C_MAUVE_GRAY)
    draw_wrapped_text(c, formula.get('values', {}).get('detail', ''), x1 - 30*mm, desc_y, FONT_SERIF, 9, 60*mm, 12)
    draw_wrapped_text(c, formula.get('strengths', {}).get('detail', ''), x2 - 30*mm, desc_y, FONT_SERIF, 9, 60*mm, 12)
    draw_wrapped_text(c, formula.get('interests', {}).get('detail', ''), x3 - 30*mm, desc_y, FONT_SERIF, 9, 60*mm, 12)

    c.setFont(FONT_SERIF, 40)
    c.setFillColor(C_MUTE_AMBER)
    c.drawCentredString(width/2, desc_y - 40*mm, "||")
    c.setFont(FONT_SERIF, 32)
    c.setFillColor(C_MAIN_SHADOW)
    c.drawCentredString(width/2, desc_y - 60*mm, json_data.get('catchphrase', '世界観'))
    c.showPage()

    # -----------------------------------------------
    # P4. チャート
    # -----------------------------------------------
    draw_header(c, "", 4)
    c.setFont(FONT_SANS, 12)
    c.setFillColor(C_ACCENT_BLUE)
    c.drawString(MARGIN_X, height - 25*mm, "03. SENSE BALANCE")
    
    metrics = json_data.get('sense_metrics', [])
    left_col_x = MARGIN_X + 25*mm   
    right_col_x = (width / 2) + 25*mm 
    start_y = height - 50*mm
    gap_y = 22*mm        
    slider_width = 45
    
    for i, metric in enumerate(metrics[:10]):
        if i < 5:
            x_pos = left_col_x
            y_pos = start_y - (i * gap_y)
        else:
            x_pos = right_col_x
            y_pos = start_y - ((i - 5) * gap_y)
        draw_slider(c, x_pos, y_pos, slider_width, metric.get('left', ''), metric.get('right', ''), metric.get('value', 50))
        
    c.setFont(FONT_SANS, 10)
    c.setFillColor(C_MAIN_SHADOW)
    current_features = json_data.get('current_worldview', {}).get('features', '')
    draw_wrapped_text(c, "分析結果：\n" + current_features, MARGIN_X, 35*mm, FONT_SERIF, 11, 85*mm, 16)
    c.showPage()

    # -----------------------------------------------
    # P5. ロードマップ
    # -----------------------------------------------
    draw_header(c, "", 5)
    c.setFont(FONT_SANS, 12)
    c.setFillColor(C_ACCENT_BLUE)
    c.drawString(MARGIN_X, height - 25*mm, "04. FUTURE ROADMAP")
    
    roadmap_points = json_data.get('roadmap_steps', [])
    y_pos = height - 50*mm
    num_x = MARGIN_X + 10*mm
    text_x = MARGIN_X + 40*mm
    line_end = width - MARGIN_X
    
    for i, point in enumerate(roadmap_points):
        c.setFont(FONT_SANS, 36)
        c.setFillColor(C_WARM_BEIGE)
        step_num = f"0{i+1}"
        c.drawString(num_x, y_pos - 5*mm, step_num)
        title = point.get('title', '')
        c.setFont(FONT_SERIF, 14)
        c.setFillColor(C_MAIN_SHADOW)
        c.drawString(text_x, y_pos, title)
        desc = point.get('detail', '')
        c.setFont(FONT_SANS, 10)
        c.setFillColor(C_MAUVE_GRAY)
        draw_wrapped_text(c, desc, text_x, y_pos - 6*mm, FONT_SANS, 9, CONTENT_WIDTH - 40*mm, 12)
        c.setStrokeColor(C_ACCENT_BLUE)
        c.setLineWidth(1)
        c.line(text_x, y_pos - 25*mm, line_end, y_pos - 25*mm)
        y_pos -= 45*mm
    c.showPage()

    # -----------------------------------------------
    # P6. アーキタイプ (NEW) - 偉人・アーティスト
    # -----------------------------------------------
    draw_header(c, "", 6)
    c.setFont(FONT_SANS, 12)
    c.setFillColor(C_ACCENT_BLUE)
    c.drawString(MARGIN_X, height - 25*mm, "05. SOUL ARCHETYPE")

    c.setFont(FONT_SERIF, 20)
    c.setFillColor(C_MAIN_SHADOW)
    c.drawString(MARGIN_X, height - 40*mm, "あなたを過去の偉人・作家に例えるなら")

    archetypes = json_data.get('artist_archetypes', [])
    y_pos = height - 60*mm
    
    for i, arch in enumerate(archetypes[:3]):
        # 名前
        name = arch.get('name', '')
        c.setFont(FONT_SERIF, 16)
        c.setFillColor(C_FOREST_TEAL)
        c.drawString(MARGIN_X + 5*mm, y_pos, f"◆ {name}")
        
        # 解説
        desc = arch.get('detail', '')
        c.setFont(FONT_SANS, 10)
        c.setFillColor(C_MAUVE_GRAY)
        draw_wrapped_text(c, desc, MARGIN_X + 10*mm, y_pos - 8*mm, FONT_SERIF, 10, CONTENT_WIDTH - 20*mm, 14)
        
        # 区切り線
        if i < 2:
            c.setStrokeColor(C_WARM_BEIGE)
            c.setLineWidth(0.5)
            c.line(MARGIN_X + 5*mm, y_pos - 30*mm, width - MARGIN_X - 5*mm, y_pos - 30*mm)
        
        y_pos -= 40*mm

    c.showPage()
    
    # -----------------------------------------------
    # P7. 提案 (Next Vision)
    # -----------------------------------------------
    end_bg_drawn = False
    try:
        c.drawImage("ending.jpg", 0, 0, width=width, height=height, preserveAspectRatio=True, anchor='c')
        end_bg_drawn = True
    except Exception:
        draw_header(c, "", 7)

    text_color_end = C_TEXT_WHITE if end_bg_drawn else C_MAIN_SHADOW
    title_color_end = C_TEXT_WHITE if end_bg_drawn else C_ACCENT_BLUE
    
    c.setFont(FONT_SERIF, 20)
    c.setFillColor(text_color_end)
    c.drawString(MARGIN_X, height - 35*mm, "Next Vision -次への鍵-")
    
    proposals = json_data.get('final_proposals', [])
    y_pos = height - 55*mm
    
    for i, prop in enumerate(proposals):
        point_title = prop.get('point', '')
        c.setFont(FONT_SANS, 14)
        c.setFillColor(title_color_end)
        c.drawString(MARGIN_X + 5*mm, y_pos, f"◆ {point_title}")
        y_pos -= 8*mm
        detail_text = prop.get('detail', '')
        c.setFillColor(text_color_end)
        
        # 25文字程度で改行するための幅設定
        draw_wrapped_text(c, detail_text, MARGIN_X + 8*mm, y_pos, FONT_SERIF, 10, 110*mm, 14)
        y_pos -= 35*mm

    quote_data = json_data.get('inspiring_quote', {})
    quote_text = quote_data.get('text', '')
    quote_author = quote_data.get('author', '')
    if quote_text:
        c.setStrokeColor(C_WARM_BEIGE)
        c.setLineWidth(0.5)
        c.line(MARGIN_X, 50*mm, width - MARGIN_X, 50*mm)
        c.setFont(FONT_SERIF, 14)
        c.setFillColor(text_color_end)
        c.drawCentredString(width/2, 40*mm, f"“ {quote_text} ”")
        c.setFont(FONT_SANS, 10)
        c.setFillColor(C_MUTE_AMBER if end_bg_drawn else C_ACCENT_BLUE)
        c.drawCentredString(width/2, 32*mm, f"- {quote_author}")

    c.setFillColor(C_FOREST_TEAL)
    c.circle(width - MARGIN_X, 22*mm, 3*mm, fill=1, stroke=0)
    c.setFont(FONT_SANS, 8)
    c.drawCentredString(width - MARGIN_X, 14*mm, "Visionary")
    c.showPage()

    c.save()
    buffer.seek(0)
    return buffer

# --- クイズデータ ---
QUIZ_DATA = [
    {"q": "Q1. 制作を始めるきっかけは？", "opts": ["内から湧き出る衝動・感情", "外部の要請や明確なコンセプト"], "type_a": "内から湧き出る衝動・感情"},
    {"q": "Q2. アイデア出しの方法は？", "opts": ["走り書きや落書きから広げる", "マインドマップや箇条書きで整理する"], "type_a": "走り書きや落書きから広げる"},
    {"q": "Q3. 配色を決める時は？", "opts": ["その瞬間の感覚や好み", "色彩理論やターゲット層への効果"], "type_a": "その瞬間の感覚や好み"},
    {"q": "Q4. 作業環境は？", "opts": ["混沌としているが落ち着く", "整理整頓され機能的"], "type_a": "混沌としているが落ち着く"},
    {"q": "Q5. 制作スケジュールは？", "opts": ["気分が乗った時に一気に進める", "毎日決まった時間にコツコツ進める"], "type_a": "気分が乗った時に一気に進める"},
    {"q": "Q6. スランプに陥った時は？", "opts": ["別の刺激（映画・旅）を求める", "原因を分析し、基礎練習などをする"], "type_a": "別の刺激（映画・旅）を求める"},
    {"q": "Q7. 作品の「完成」の判断基準は？", "opts": ["もうこれ以上触れないと感じた時", "予定していた要件を満たした時"], "type_a": "もうこれ以上触れないと感じた時"},
    {"q": "Q8. 他人の評価に対しては？", "opts": ["好き嫌いが分かれても構わない", "多くの人に理解されるか気になる"], "type_a": "好き嫌いが分かれても構わない"},
    {"q": "Q9. 制作中に新しいアイデアが浮かんだら？", "opts": ["予定を変更してでも試す", "今の作品を完成させてから次でやる"], "type_a": "予定を変更してでも試す"},
    {"q": "Q10. 道具や機材へのこだわりは？", "opts": ["使い心地や愛着を重視", "スペックや効率を重視"], "type_a": "使い心地や愛着を重視"},
    {"q": "Q11. 作品を通して伝えたいのは？", "opts": ["自分の内面世界や叫び", "社会へのメッセージや解決策"], "type_a": "自分の内面世界や叫び"},
    {"q": "Q12. ラフスケッチの描き方は？", "opts": ["抽象的な線や形が多い", "具体的な構成や配置図に近い"], "type_a": "抽象的な線や形が多い"},
    {"q": "Q13. 憧れるアーティストは？", "opts": ["破天荒で天才肌の人物", "知的で理論的な人物"], "type_a": "破天荒で天才肌の人物"},
    {"q": "Q14. 締め切りに対する姿勢は？", "opts": ["ギリギリまで粘ってクオリティを上げたい", "余裕を持って早めに終わらせたい"], "type_a": "ギリギリまで粘ってクオリティを上げたい"},
    {"q": "Q15. チーム制作については？", "opts": ["自分のペースが乱れるので苦手", "役割分担できて効率的なので好き"], "type_a": "自分のペースが乱れるので苦手"},
    {"q": "Q16. 過去の自分の作品を見ると？", "opts": ["その時の感情が蘇る", "技術的な未熟さが気になる"], "type_a": "その時の感情が蘇る"},
    {"q": "Q17. 新しい技術を学ぶ動機は？", "opts": ["表現したいものが作れるようになるから", "仕事の幅が広がりそうだから"], "type_a": "表現したいものが作れるようになるから"},
    {"q": "Q18. 制作中のBGMは？", "opts": ["感情を高める曲を大音量で", "集中を妨げない環境音や無音"], "type_a": "感情を高める曲を大音量で"},
    {"q": "Q19. タイトルの付け方は？", "opts": ["詩的・抽象的", "説明的・具体的"], "type_a": "詩的・抽象的"},
    {"q": "Q20. SNSでの発信は？", "opts": ["作品の世界観だけを見せたい", "制作過程や思考もシェアしたい"], "type_a": "作品の世界観だけを見せたい"},
    {"q": "Q21. 批評を受けた時の反応は？", "opts": ["感情的に反発してしまうことがある", "冷静に改善点として受け止める"], "type_a": "感情的に反発してしまうことがある"},
    {"q": "Q22. 自分の作風を一言で言うなら？", "opts": ["エモーショナル・感覚的", "ロジカル・機能的"], "type_a": "エモーショナル・感覚的"},
    {"q": "Q23. 目標設定の方法は？", "opts": ["大きな夢やビジョンを描く", "具体的な数値やステップを決める"], "type_a": "大きな夢やビジョンを描く"},
    {"q": "Q24. 情報収集のスタイルは？", "opts": ["直感的に気になったものを深掘り", "体系的に幅広くチェック"], "type_a": "直感的に気になったものを深掘り"},
    {"q": "Q25. 失敗作の扱いは？", "opts": ["勢いで捨ててしまう", "分析のために取っておく"], "type_a": "勢いで捨ててしまう"},
    {"q": "Q26. 影響を受けやすいのは？", "opts": ["自然、音楽、夢などの体験", "本、論文、ニュースなどの情報"], "type_a": "自然、音楽、夢などの体験"},
    {"q": "Q27. 制作において重要なのは？", "opts": ["「何を描くか」（主題）", "「どう描くか」（構成・技術）"], "type_a": "「何を描くか」（主題）"},
    {"q": "Q28. 複雑な問題に直面したら？", "opts": ["直感を信じて突破する", "要素を分解して解決する"], "type_a": "直感を信じて突破する"},
    {"q": "Q29. 完璧主義についてどう思う？", "opts": ["完成しなくても魂がこもっていればいい", "細部まで完璧でないと気が済まない"], "type_a": "完成しなくても魂がこもっていればいい"},
    {"q": "Q30. あなたにとってアートとは？", "opts": ["生きることそのもの", "社会貢献や仕事の手段"], "type_a": "生きることそのもの"},
]

# --- Streamlit アプリ本体 ---

st.set_page_config(page_title="世界観 総合診断ツール（β版）", layout="wide") 
apply_custom_css()

# ▼▼▼ 起動画面に cover.jpg を表示 ▼▼▼
try:
    st.image("cover.jpg", use_column_width=True)
except Exception:
    pass 

st.title("世界観 総合診断ツール（β版）")
st.write("「センス」を科学し、あなたの「世界観」を体系化する。")

if 'step' not in st.session_state:
    st.session_state.step = 1
if 'quiz_result' not in st.session_state:
    st.session_state.quiz_result = None
if 'quiz_score_percent' not in st.session_state:
    st.session_state.quiz_score_percent = 0

if st.session_state.step == 1:
    st.header("01. SENSE CHECK")
    st.markdown("##### 📝 基本情報（任意）")
    col_input1, col_input2 = st.columns(2)
    with col_input1:
        user_name_input = st.text_input("お名前", key="user_name")
    with col_input2:
        user_email_input = st.text_input("メールアドレス", key="user_email")
    st.write("直感で回答。あなたの創作の源泉を探る。")

    with st.form(key='quiz_form'):
        answers = []
        for i, item in enumerate(QUIZ_DATA):
            ans = st.radio(item["q"], item["opts"], key=f"q{i}", horizontal=True)
            answers.append((ans, item["type_a"]))
        st.write("---")
        submit_button = st.form_submit_button(label="診断する")

    if submit_button:
        score_a = 0
        for ans, type_a_val in answers:
            if ans == type_a_val:
                score_a += 1
        percent = int((score_a / 30) * 100)
        st.session_state.quiz_score_percent = percent
        if score_a >= 20: st.session_state.quiz_result = f"直感・情熱型 (情熱度: {percent}%)"
        elif score_a >= 16: st.session_state.quiz_result = f"バランス型・直感寄り (情熱度: {percent}%)"
        elif score_a >= 11: st.session_state.quiz_result = f"バランス型・論理寄り (情熱度: {percent}%)"
        else: st.session_state.quiz_result = f"論理・構築型 (情熱度: {percent}%)"
        st.session_state.step = 2
        st.rerun()

elif st.session_state.step == 2:
    st.header("02. VISION INTEGRATION")
    st.success(f"TYPE: **{st.session_state.quiz_result}**")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Current Work (過去作品)")
        past_files = st.file_uploader("Upload max 3 images", type=["jpg", "png", "jpeg"], accept_multiple_files=True, key="past")
    with col2:
        st.subheader("Ideal Vision (未来の理想)")
        future_files = st.file_uploader("Upload max 3 images", type=["jpg", "png", "jpeg"], accept_multiple_files=True, key="future")

    if past_files and future_files:
        if len(past_files) > 3 or len(future_files) > 3:
             st.warning("画像は各3枚まで。")
        else:
            if st.button("診断結果を作成する"):
                past_images = [resize_image_for_api(Image.open(f)) for f in past_files]
                future_images = [resize_image_for_api(Image.open(f)) for f in future_files]

                prompt = f"""
                あなたはThomYoshidaという、クリエイターに寄り添うアートディレクターです。
                ユーザーの「性格」「過去作品」「未来の理想」を分析し、
                PDF生成用のデータをJSON形式で作成してください。

                【トーン】
                ・偏差値55の高校3年生レベルのわかりやすい言葉。
                ・主語（私は〜など）は無し。体言止めを多用。
                ・「具体的なアイデア」を重視する。

                【入力情報】
                性格タイプ: {st.session_state.quiz_result}
                (前半画像: 現在 / 後半画像: 理想)

                【出力JSONフォーマット】
                {{
                    "catchphrase": "世界観を一言で表すキャッチコピー（15文字以内）",
                    "twelve_past_keywords": ["過去1", "過去2", "過去3", "過去4", "過去5", "過去6", "過去7", "過去8", "過去9", "過去10", "過去11", "過去12"],
                    "twelve_future_keywords": ["未来1", "未来2", "未来3", "未来4", "未来5", "未来6", "未来7", "未来8", "未来9", "未来10", "未来11", "未来12"],
                    "formula": {{
                        "values": {{ "word": "価値観ワード", "detail": "詳細（40文字）" }},
                        "strengths": {{ "word": "得意表現ワード", "detail": "詳細（40文字）" }},
                        "interests": {{ "word": "好きなこと（具体的なジャンルや物）", "detail": "詳細（40文字）" }}
                    }},
                    "sense_metrics": [
                        {{ "left": "シンプル", "right": "カオス", "value": 0-100 }},
                        {{ "left": "具象", "right": "抽象", "value": 0-100 }},
                        {{ "left": "静寂", "right": "躍動", "value": 0-100 }},
                        {{ "left": "論理", "right": "直感", "value": 0-100 }},
                        {{ "left": "伝統", "right": "革新", "value": 0-100 }},
                        {{ "left": "内省", "right": "発信", "value": 0-100 }},
                        {{ "left": "儚さ", "right": "永続", "value": 0-100 }},
                        {{ "left": "感情", "right": "理性", "value": 0-100 }},
                        {{ "left": "日常", "right": "幻想", "value": 0-100 }},
                        {{ "left": "繊細", "right": "大胆", "value": 0-100 }}
                    ],
                    "current_worldview": {{ "features": "現在の特徴分析（100文字程度）" }},
                    "roadmap_steps": [
                        {{ "title": "STEP 1: 認識", "detail": "現状の課題と、それをどう捉えるかのアドバイス（60文字）" }},
                        {{ "title": "STEP 2: 拡張", "detail": "具体的なインプットや試すべき手法の提案（例：〇〇という映画を見る、〇〇素材を使うなど）（80文字）" }},
                        {{ "title": "STEP 3: 到達", "detail": "最終的なスタイルの具体イメージ（80文字）" }}
                    ],
                    "artist_archetypes": [
                        {{ "name": "人物名1", "detail": "なぜその人物に近いのかの解説（60文字程度）" }},
                        {{ "name": "人物名2", "detail": "なぜその人物に近いのかの解説（60文字程度）" }},
                        {{ "name": "人物名3", "detail": "なぜその人物に近いのかの解説（60文字程度）" }}
                    ],
                    "final_proposals": [
                        {{ "point": "具体的な作品アイデア案1", "detail": "テーマ、素材、表現方法などの具体的なアイデア例（参考レベルで）（100文字程度）" }},
                        {{ "point": "具体的な作品アイデア案2", "detail": "テーマ、素材、表現方法などの具体的なアイデア例（参考レベルで）（100文字程度）" }},
                        {{ "point": "具体的な作品アイデア案3", "detail": "テーマ、素材、表現方法などの具体的なアイデア例（参考レベルで）（100文字程度）" }}
                    ],
                    "inspiring_quote": {{
                        "text": "このユーザーの価値観と診断結果に最も響く、クリエイターや哲学者の名言",
                        "author": "その名言の著者名"
                    }}
                }}
                """
                
                contents = [prompt] + past_images + future_images

                try:
                    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
                    with st.spinner("世界観を統合中..."):
                        response = client.models.generate_content(
                            model='gemini-flash-latest',
                            contents=contents,
                            config=types.GenerateContentConfig(response_mime_type="application/json")
                        )
                        data = json.loads(response.text)
                        
                        pdf_file = create_pdf(data, st.session_state.quiz_result)
                        
                        st.balloons()
                        st.success("診断が完了しました。レポートを受け取ってください。")

                        st.download_button(
                            label="📥 診断レポートをダウンロードする",
                            data=pdf_file,
                            file_name="Visionary_Analysis_Report.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )
                        
                        # --- リスト保存 ---
                        if "user_name" in st.session_state and "user_email" in st.session_state:
                             if st.session_state.user_name and st.session_state.user_email:
                                 save_to_google_sheets(
                                     st.session_state.user_name,
                                     st.session_state.user_email,
                                     st.session_state.quiz_result
                                 )

                        # --- メール送信 ---
                        if "user_email" in st.session_state and st.session_state.user_email:
                            email_status = send_email_with_pdf(st.session_state.user_email, pdf_buffer=pdf_file)
                            if email_status:
                                st.success(f"📧 {st.session_state.user_email} にもレポートを送信しました。")

                except Exception as e:
                    st.error(f"Error: {e}")

    elif st.button("最初からやり直す"):
         st.session_state.step = 1
         st.session_state.quiz_result = None
         st.rerun()
