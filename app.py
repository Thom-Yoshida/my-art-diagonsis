import streamlit as st
import os
import json
import io
import datetime
import smtplib
import requests
import time # ★追加：待機処理用
from PIL import Image
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# Google系ライブラリ
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from google import genai
from google.genai import types

# デザイン・可視化
import plotly.graph_objects as go

# PDF生成
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader

# ---------------------------------------------------------
# 0. 初期設定 & セキュリティ
# ---------------------------------------------------------
st.set_page_config(page_title="Visionary Analysis | ThomYoshida", layout="wide") 

# デザイン定義 (COLORS - 世界観研究所グレー v3.1)
COLORS = {
    "bg": "#2A2A2A", "text": "#E8E8E8", "accent": "#D6AE60", 
    "sub": "#8BA6B0", "forest": "#5F9EA0", "card": "#383838",    
    "pdf_bg": "#FAFAF8", "pdf_text": "#2C2C2C", "pdf_sub": "#666666"
}

# フォント登録
try:
    pdfmetrics.registerFont(UnicodeCIDFont('HeiseiMin-W3')) 
    pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5')) 
    FONT_SERIF = 'HeiseiMin-W3'
    FONT_SANS = 'HeiseiKakuGo-W5'
except:
    FONT_SERIF = 'Helvetica'
    FONT_SANS = 'Helvetica'

# APIキー設定
if "GEMINI_API_KEY" in st.secrets:
    os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]

# パスワード認証機能
def check_password():
    if "password_correct" not in st.session_state: st.session_state.password_correct = False
    if "APP_PASSWORD" not in st.secrets: return True
    if st.session_state.password_correct: return True
    st.markdown("### 🔒 Restricted Access")
    password_input = st.text_input("Enter Passcode", type="password")
    if password_input:
        if password_input == st.secrets["APP_PASSWORD"]:
            st.session_state.password_correct = True
            st.rerun()
        else: st.error("Invalid Passcode")
    st.stop()

check_password()

# ---------------------------------------------------------
# 1. 診断データ
# ---------------------------------------------------------
QUIZ_DATA = [
    {"q": "Q1. 制作を始めるきっかけは？", "opts": ["内から湧き出る衝動・感情", "外部の要請や明確なコンセプト"], "type_a": "内から湧き出る衝動・感情"},
    {"q": "Q2. アイデア出しの方法は？", "opts": ["走り書きや落書きから広げる", "マインドマップや箇条書きで整理する"], "type_a": "走り書きや落書きから広げる"},
    # ... (省略：Q3〜Q30は変更なし。以前のコードと同じ内容が入っている前提) ...
    # ※長くなるため省略しますが、実装時はここもQ30まで記述してください
]
# ★動作確認用のため、ここでのQUIZ_DATAは省略せずに前回のコードをそのまま使ってください。
# もし貼り付けが面倒な場合は、前回のコードのQUIZ_DATA部分だけ残して他を書き換えてください。
# ここではスペース節約のため省略表記にしています。

# ---------------------------------------------------------
# 2. デザイン & ユーティリティ関数
# ---------------------------------------------------------
def apply_custom_css():
    st.markdown(f"""
    <style>
        html, body, [class*="css"] {{ font-size: 18px; }}
        .stApp {{ background-color: {COLORS["bg"]}; color: {COLORS["text"]}; }}
        h1, h2, h3, h4 {{ font-family: "Hiragino Mincho ProN", serif !important; color: {COLORS["text"]} !important; }}
        p, div, label, span, li {{ font-family: "Hiragino Kaku Gothic ProN", sans-serif; color: {COLORS["text"]}; font-size: 1.1rem !important; }}
        .stTextInput > div > div > input {{ background-color: {COLORS["card"]}; color: #FFF; border: 1px solid #555; font-size: 1.1rem; }}
        div.stButton > button {{ background-color: {COLORS["sub"]}; color: white; padding: 12px 28px; font-size: 1.2rem; border: none; border-radius: 4px; }}
        .stDownloadButton > button {{ background-color: {COLORS["accent"]} !important; color: #1E1E1E !important; font-weight: bold !important; font-size: 1.3rem !important; border: none !important; }}
        section[data-testid="stSidebar"] {{ background-color: #1A1A1A; }}
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
# 3. 外部連携関数
# ---------------------------------------------------------
def save_to_google_sheets(name, email, specialty, diagnosis_type):
    if "gcp_service_account" not in st.secrets: return False
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet_name = st.secrets.get("SHEET_NAME", "customer_list")
        sheet = client.open(sheet_name).sheet1
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([now, name, email, specialty, diagnosis_type])
        return True
    except Exception as e:
        print(f"Sheets Error: {e}")
        return False

def load_data_from_sheets():
    if "gcp_service_account" not in st.secrets: return pd.DataFrame()
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet_name = st.secrets.get("SHEET_NAME", "customer_list")
        sheet = client.open(sheet_name).sheet1
        data = sheet.get_all_values()
        if len(data) < 2: return pd.DataFrame()
        headers = data[0]
        rows = data[1:]
        df = pd.DataFrame(rows, columns=headers)
        return df
    except Exception: return pd.DataFrame()

def send_email_with_pdf(user_email, pdf_buffer):
    if "GMAIL_ADDRESS" not in st.secrets or "GMAIL_APP_PASSWORD" not in st.secrets: return False
    sender_email = st.secrets["GMAIL_ADDRESS"]
    sender_password = st.secrets["GMAIL_APP_PASSWORD"]
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = user_email
    msg['Subject'] = "【Visionary Report】あなたの世界観診断結果"
    body = """Visionary Analysis Report をお届けします。\n\nThom Yoshida"""
    msg.attach(MIMEText(body, 'plain'))
    pdf_buffer.seek(0)
    part = MIMEApplication(pdf_buffer.read(), Name="Visionary_Analysis.pdf")
    part['Content-Disposition'] = 'attachment; filename="Visionary_Analysis.pdf"'
    msg.attach(part)
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, [user_email, sender_email], msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Email Error: {e}")
        return False

# ---------------------------------------------------------
# 4. PDF生成ロジック
# ---------------------------------------------------------
# (省略なし：前回のコードと同じロジックを使用)
def wrap_text_smart(text, max_char_count):
    if not text: return []
    delimiters = ['、', '。', 'て', 'に', 'を', 'は', 'が', 'と', 'へ', 'で', 'や', 'の', 'も', 'し', 'い', 'か', 'ね', 'よ', '！', '？']
    lines = []
    current_line = ""
    for char in text:
        current_line += char
        if len(current_line) >= max_char_count * 0.8:
            if char in delimiters:
                lines.append(current_line)
                current_line = ""
                continue
            if len(current_line) >= max_char_count + 2:
                lines.append(current_line)
                current_line = ""
    if current_line: lines.append(current_line)
    return lines

def draw_wrapped_text(c, text, x, y, font, size, max_width, leading, centered=False):
    c.setFont(font, size)
    char_width_mm = size * 0.352 * 0.95
    max_chars = int(max_width / char_width_mm)
    lines = wrap_text_smart(text, max_chars)
    current_y = y
    for line in lines:
        if centered: c.drawCentredString(x, current_y, line)
        else: c.drawString(x, current_y, line)
        current_y -= leading

def draw_header(c, title, page_num):
    width, height = landscape(A4)
    c.setFillColor(HexColor(COLORS['pdf_bg']))
    c.rect(0, 0, width, height, fill=1, stroke=0)
    c.setStrokeColor(HexColor(COLORS['pdf_sub']))
    c.setLineWidth(0.5)
    c.line(10*mm, height - 25*mm, width - 10*mm, height - 25*mm)
    c.setFont(FONT_SANS, 20)
    c.setFillColor(HexColor(COLORS['forest']))
    c.drawString(15*mm, height - 20*mm, title) 
    c.setFont(FONT_SANS, 12)
    c.setFillColor(HexColor(COLORS['pdf_sub']))
    c.drawRightString(width - 15*mm, height - 20*mm, f"{page_num} / 8")

def draw_arrow_slider(c, x, y, width_mm, left_text, right_text, value):
    bar_width = width_mm * mm
    c.setFont(FONT_SERIF, 12)
    c.setFillColor(HexColor(COLORS['pdf_text']))
    c.drawRightString(x - 6*mm, y - 1.5*mm, left_text)
    c.drawString(x + bar_width + 6*mm, y - 1.5*mm, right_text)
    c.setStrokeColor(HexColor(COLORS['pdf_sub']))
    c.setLineWidth(0.8)
    c.line(x, y, x + bar_width, y)
    c.line(x, y, x + 2*mm, y + 1.5*mm)
    c.line(x, y, x + 2*mm, y - 1.5*mm)
    c.line(x + bar_width, y, x + bar_width - 2*mm, y + 1.5*mm)
    c.line(x + bar_width, y, x + bar_width - 2*mm, y - 1.5*mm)
    dot_x = x + (value / 100) * bar_width
    c.setFillColor(HexColor(COLORS['forest']))
    c.circle(dot_x, y, 2.5*mm, fill=1, stroke=1)

def create_pdf(json_data):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)
    MARGIN_X = width * 0.12
    
    # P1
    try:
        c.drawImage("cover.jpg", 0, 0, width=width, height=height, preserveAspectRatio=False)
        c.setFillColor(HexColor('#000000'))
        c.setFillAlpha(0.3)
        c.rect(0, 0, width, height, fill=1, stroke=0)
        c.setFillAlpha(1.0)
        TEXT_COLOR = HexColor('#FFFFFF')
    except:
        c.setFillColor(HexColor(COLORS['pdf_bg']))
        c.rect(0, 0, width, height, fill=1, stroke=0)
        TEXT_COLOR = HexColor(COLORS['pdf_text'])
    c.setFillColor(TEXT_COLOR)
    c.setFont(FONT_SERIF, 52)
    c.drawCentredString(width/2, height/2 + 10*mm, json_data.get('catchphrase', 'Visionary Report'))
    c.setFont(FONT_SANS, 18)
    c.drawCentredString(width/2, height/2 - 25*mm, "WORLDVIEW ANALYSIS REPORT")
    c.setFont(FONT_SERIF, 12)
    c.drawCentredString(width/2, 20*mm, f"Designed by ThomYoshida AI | {datetime.datetime.now().strftime('%Y.%m.%d')}")
    c.showPage()

    # P2
    draw_header(c, "01. 過去と未来の対比", 2)
    c.setFont(FONT_SERIF, 22)
    c.setFillColor(HexColor(COLORS['pdf_sub']))
    c.drawCentredString(width/3, height - 55*mm, "PAST / ORIGIN")
    past_kws = json_data.get('twelve_past_keywords', [])
    y = height - 75*mm
    c.setFont(FONT_SANS, 12)
    for kw in past_kws[:8]:
        c.drawCentredString(width/3, y, f"◇ {kw}")
        y -= 11*mm
    c.setFont(FONT_SERIF, 30)
    c.setFillColor(HexColor(COLORS['forest']))
    c.drawCentredString(width*2/3, height - 55*mm, "FUTURE / VISION")
    future_kws = json_data.get('twelve_future_keywords', [])
    y = height - 75*mm
    c.setFont(FONT_SANS, 16)
    c.setFillColor(HexColor(COLORS['pdf_text']))
    for kw in future_kws[:8]:
        c.drawCentredString(width*2/3, y, f"◆ {kw}")
        y -= 13*mm
    c.showPage()

    # P3
    draw_header(c, "02. 独自の成功法則", 3)
    formula = json_data.get('formula', {})
    cy = height/2 - 10*mm
    r = 38*mm 
    positions = [
        (width/2 - r*1.55, cy + r*0.8, "価値観", formula.get('values', {}).get('word', '')),
        (width/2 + r*1.55, cy + r*0.8, "強み", formula.get('strengths', {}).get('word', '')),
        (width/2, cy - r*1.2, "好き", formula.get('interests', {}).get('word', ''))
    ]
    for cx, cy_pos, title, word in positions:
        c.setStrokeColor(HexColor(COLORS['forest']))
        c.setFillColor(HexColor('#FFFFFF'))
        c.setLineWidth(1.5)
        c.circle(cx, cy_pos, r, fill=1, stroke=1)
        c.setFont(FONT_SERIF, 18)
        c.setFillColor(HexColor(COLORS['pdf_sub']))
        c.drawCentredString(cx, cy_pos + 12*mm, title) 
        c.setFont(FONT_SANS, 24)
        c.setFillColor(HexColor(COLORS['pdf_text']))
        draw_wrapped_text(c, word, cx, cy_pos - 8*mm, FONT_SANS, 24, r*1.7, 30, centered=True)
    c.setFont(FONT_SANS, 44)
    c.setFillColor(HexColor(COLORS['accent']))
    c.drawCentredString(width/2, cy + r*0.8, "×")
    c.drawCentredString(width/2 - r*0.8, cy - r*0.2, "×")
    c.drawCentredString(width/2 + r*0.8, cy - r*0.2, "×")
    c.setFont(FONT_SERIF, 36)
    c.setFillColor(HexColor(COLORS['pdf_text']))
    c.drawCentredString(width/2, height - 40*mm, f"「{json_data.get('catchphrase', '')}」")
    c.showPage()

    # P4
    draw_header(c, "03. 感性のバランス", 4)
    metrics = json_data.get('sense_metrics', [])
    y = height - 65*mm
    for i, m in enumerate(metrics[:8]):
        x = MARGIN_X + 25*mm if i < 4 else width/2 + 25*mm
        curr_y = y - (i % 4) * 24*mm
        draw_arrow_slider(c, x, curr_y, 48, m.get('left'), m.get('right'), m.get('value'))
    c.showPage()

    # P5
    draw_header(c, "04. おすすめするロールモデル", 5) 
    archs = json_data.get('artist_archetypes', [])
    y = height - 55*mm
    for i, a in enumerate(archs[:3]):
        c.setFont(FONT_SERIF, 22)
        c.setFillColor(HexColor(COLORS['forest']))
        c.drawString(MARGIN_X, y, f"◆ {a.get('name')}")
        c.setFillColor(HexColor(COLORS['pdf_text']))
        draw_wrapped_text(c, a.get('detail', ''), MARGIN_X + 8*mm, y - 12*mm, FONT_SANS, 14, width - MARGIN_X*2 - 20*mm, 20)
        y -= 48*mm
    c.showPage()

    # P6
    draw_header(c, "05. 未来へのロードマップ", 6)
    steps = json_data.get('roadmap_steps', [])
    y = height - 65*mm
    for i, step in enumerate(steps):
        c.setFont(FONT_SANS, 40)
        c.setFillColor(HexColor(COLORS['accent']))
        c.drawString(MARGIN_X, y - 5*mm, f"0{i+1}")
        c.setFont(FONT_SERIF, 18)
        c.setFillColor(HexColor(COLORS['pdf_text']))
        c.drawString(MARGIN_X + 30*mm, y, step.get('title', ''))
        c.setFillColor(HexColor(COLORS['pdf_sub']))
        draw_wrapped_text(c, step.get('detail', ''), MARGIN_X + 30*mm, y - 12*mm, FONT_SANS, 12, 125*mm, 18)
        y -= 45*mm
    c.showPage()

    # P7
    draw_header(c, "06. 次なるビジョンと選択肢", 7)
    c.setFont(FONT_SERIF, 20)
    c.setFillColor(HexColor(COLORS['forest']))
    c.drawString(MARGIN_X, height - 45*mm, "Next Vision")
    proposals = json_data.get('final_proposals', [])
    y = height - 60*mm
    for p in proposals[:5]:
        c.setFont(FONT_SANS, 14)
        c.setFillColor(HexColor(COLORS['pdf_text']))
        c.drawString(MARGIN_X, y, f"・{p.get('point')}")
        draw_wrapped_text(c, p.get('detail', ''), MARGIN_X + 5*mm, y - 6*mm, FONT_SANS, 11, width*0.4, 14)
        y -= 24*mm
    x_right = width/2 + 10*mm
    c.setFont(FONT_SERIF, 20)
    c.setFillColor(HexColor(COLORS['forest']))
    c.drawString(x_right, height - 45*mm, "Alternative Expressions")
    alts = json_data.get('alternative_expressions', [])
    y_alt = height - 60*mm
    for alt in alts[:3]:
        c.setFont(FONT_SANS, 14)
        c.setFillColor(HexColor(COLORS['pdf_text']))
        draw_wrapped_text(c, f"◇ {alt}", x_right, y_alt, FONT_SANS, 14, width*0.4, 20)
        y_alt -= 30*mm
    c.showPage()

    # P8
    image_url = "https://images.unsplash.com/photo-1495312040802-a929cd14a6ab?q=80&w=2940&auto=format&fit=crop"
    try:
        response = requests.get(image_url, stream=True, timeout=10)
        if response.status_code == 200:
            img_data = io.BytesIO(response.content)
            pil_img = Image.open(img_data)
            img_reader = ImageReader(pil_img)
            c.drawImage(img_reader, 0, 0, width=width, height=height, preserveAspectRatio=False)
            c.setFillColor(HexColor('#000000'))
            c.setFillAlpha(0.5)
            c.rect(0, 0, width, height, fill=1, stroke=0)
            c.setFillAlpha(1.0)
            TEXT_COLOR_END = HexColor('#FFFFFF')
            ACCENT_COLOR_END = HexColor(COLORS['accent'])
        else: raise Exception
    except:
        draw_header(c, "07. 贈る言葉", 8)
        TEXT_COLOR_END = HexColor(COLORS['pdf_text'])
        ACCENT_COLOR_END = HexColor(COLORS['forest'])

    quote_data = json_data.get('inspiring_quote', {})
    q_text = quote_data.get('text', '')
    q_author = quote_data.get('author', '')

    c.setFillColor(TEXT_COLOR_END)
    draw_wrapped_text(c, q_text, width/2, height/2 + 20*mm, FONT_SERIF, 28, 150*mm, 36, centered=True)
    c.setFont(FONT_SANS, 18)
    c.setFillColor(ACCENT_COLOR_END)
    c.drawCentredString(width/2, height/2 - 35*mm, f"- {q_author}")
    c.setFont(FONT_SANS, 12)
    c.setFillColor(TEXT_COLOR_END)
    c.drawRightString(width - 15*mm, 15*mm, "8 / 8")
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

# ---------------------------------------------------------
# 5. Pipeline & Data
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
        st.info(f"**価値観**\n\n{f.get('values', {}).get('word')}")
        st.warning(f"**強み**\n\n{f.get('strengths', {}).get('word')}")
        st.success(f"**好き**\n\n{f.get('interests', {}).get('word')}")
    st.markdown("### Recommended Alternative Expressions")
    alts = data.get('alternative_expressions', [])
    for alt in alts:
        st.write(f"◇ {alt}")

if 'step' not in st.session_state: st.session_state.step = 1
if 'quiz_result' not in st.session_state: st.session_state.quiz_result = None

# STEP 1
if st.session_state.step == 1:
    try: st.image("cover.jpg", use_container_width=True)
    except: pass
    st.title("Visionary Analysis")
    st.caption("美意識の解像度を上げる、対話型診断ツール")
    st.markdown("##### 00. YOUR SPECIALTY")
    specialty = st.text_input("あなたの専門分野・表現媒体（例：写真、建築、グラフィック）")
    st.markdown("##### 01. SENSE CHECK")
    st.write("直感で回答してください。あなたの創作の源泉を探ります。")
    with st.form(key='quiz_form'):
        answers = []
        for i, item in enumerate(QUIZ_DATA):
            ans = st.radio(item["q"], item["opts"], key=f"q{i}", horizontal=True, index=None)
            answers.append((ans, item["type_a"]))
        st.write("---")
        submit_button = st.form_submit_button(label="PROCEED TO VISION")
    if submit_button:
        if not specialty: st.warning("専門分野を入力してください。")
        elif any(a[0] is None for a in answers): st.error("すべての質問に回答してください。")
        else:
            st.session_state.specialty = specialty
            score_a = 0
            for ans, type_a_val in answers:
                if ans == type_a_val: score_a += 1
            percent = int((score_a / 30) * 100)
            if score_a >= 20: st.session_state.quiz_result = f"直感・情熱型 (情熱度: {percent}%)"
            elif score_a >= 16: st.session_state.quiz_result = f"バランス型・直感寄り (情熱度: {percent}%)"
            elif score_a >= 11: st.session_state.quiz_result = f"バランス型・論理寄り (情熱度: {percent}%)"
            else: st.session_state.quiz_result = f"論理・構築型 (情熱度: {percent}%)"
            st.session_state.step = 2
            st.rerun()

# STEP 2
elif st.session_state.step == 2:
    st.header("02. VISION INTEGRATION")
    st.info(f"Type: **{st.session_state.quiz_result}** / Specialty: **{st.session_state.specialty}**")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Past Works")
        past_files = st.file_uploader("Origin (Max 3)", type=["jpg", "png"], accept_multiple_files=True, key="past")
    with col2:
        st.markdown("#### Future Vision")
        future_files = st.file_uploader("Ideal (Max 3)", type=["jpg", "png"], accept_multiple_files=True, key="future")
    if st.button("NEXT STEP: UNLOCK REPORT"):
        if not past_files: st.error("画像をアップロードしてください。")
        else:
            st.session_state.step = 3
            st.rerun()

# STEP 3
elif st.session_state.step == 3:
    st.header("03. UNLOCK YOUR REPORT")
    with st.container():
        st.markdown(f"""<div style="background-color: {COLORS['card']}; padding: 30px; border-radius: 10px; border: 1px solid {COLORS['accent']}; text-align: center;"><h3 style="color: {COLORS['accent']};">Analysis Ready</h3><p>診断結果レポートを発行します。</p></div><br>""", unsafe_allow_html=True)
        with st.form("lead_capture"):
            col_f1, col_f2 = st.columns(2)
            with col_f1: user_name = st.text_input("Name")
            with col_f2: user_email = st.text_input("Email")
            submit = st.form_submit_button("GENERATE REPORT", type="primary")
            if submit:
                if user_name and user_email:
                    st.session_state.user_name = user_name
                    st.session_state.user_email = user_email
                    save_to_google_sheets(user_name, user_email, st.session_state.specialty, st.session_state.quiz_result)
                    st.session_state.step = 4
                    st.rerun()
                else: st.warning("情報を入力してください。")

# STEP 4 (AI Auto-Generation with Retry Logic)
elif st.session_state.step == 4:
    if "analysis_data" not in st.session_state:
        with st.spinner("Connecting to Visionary Core... AIが世界観を解析中..."):
            
            # APIキーがあればAI生成、なければフォールバック
            if os.environ.get("GEMINI_API_KEY"):
                # ★リトライループの実装 (3回まで)
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
                        
                        prompt = f"""
                        あなたは世界的なアートディレクター Thom Yoshida です。
                        ユーザーの「専門分野」と「診断タイプ」に基づき、その人の世界観を分析し、
                        専用の診断レポートJSONを作成してください。

                        【ユーザー情報】
                        - 専門分野: {st.session_state.specialty}
                        - 診断タイプ: {st.session_state.quiz_result}
                        
                        【必須出力JSON構造】
                        {{
                            "catchphrase": "短いキャッチコピー(15文字以内)",
                            "twelve_past_keywords": ["過去を表す単語12個"],
                            "twelve_future_keywords": ["未来を表す単語12個"],
                            "sense_metrics": [
                                {{"left": "対立軸左", "right": "対立軸右", "value": 0〜100の数値}} を8個
                            ],
                            "formula": {{
                                "values": {{"word": "価値観", "detail": "詳細"}},
                                "strengths": {{"word": "強み", "detail": "詳細"}},
                                "interests": {{"word": "好き", "detail": "詳細"}}
                            }},
                            "roadmap_steps": [
                                {{"title": "Stepタイトル", "detail": "詳細"}} を3つ
                            ],
                            "artist_archetypes": [
                                {{"name": "ロールモデル名", "detail": "なぜその人なのか"}} を3名
                            ],
                            "final_proposals": [
                                {{"point": "ビジョン要点", "detail": "詳細"}} を5つ
                            ],
                            "alternative_expressions": [
                                "おすすめの別表現手法" を3つ
                            ],
                            "inspiring_quote": {{
                                "text": "その人の世界観に最も響く、実在する偉人の名言（日本語訳）",
                                "author": "著者名"
                            }}
                        }}
                        """
                        # ★モデルを gemini-1.5-flash に変更 (Quota対策)
                        response = client.models.generate_content(
                            model='gemini-1.5-flash', 
                            contents=prompt,
                            config=types.GenerateContentConfig(response_mime_type="application/json")
                        )
                        data = json.loads(response.text)
                        break # 成功したらループを抜ける
                        
                    except Exception as e:
                        if "429" in str(e) and attempt < max_retries - 1:
                            time.sleep(10) # 429エラーなら10秒待機
                        elif attempt == max_retries - 1:
                            st.error(f"AI Error (Quota Exceeded): {e}")
                            # ダミーデータへのフォールバック（省略）
                            # 実際の運用ではここにダミーデータを記述してください
                            data = {
                                "catchphrase": "Visionary Mode", "twelve_past_keywords": [], "twelve_future_keywords": [], "sense_metrics": [], "formula": {}, "roadmap_steps": [], "artist_archetypes": [], "final_proposals": [], "alternative_expressions": [], "inspiring_quote": {"text": "Creation is the act of connecting.", "author": "System"}
                            }
            else:
                data = {
                    "catchphrase": "Visionary Mode", "twelve_past_keywords": [], "twelve_future_keywords": [], "sense_metrics": [], "formula": {}, "roadmap_steps": [], "artist_archetypes": [], "final_proposals": [], "alternative_expressions": [], "inspiring_quote": {"text": "API Key Not Found", "author": "System"}
                }

            st.session_state.analysis_data = data
            pdf_buffer = create_pdf(data)
            is_sent = send_email_with_pdf(st.session_state.user_email, pdf_buffer)
            st.session_state.email_sent_status = is_sent
            st.rerun()
    else:
        data = st.session_state.analysis_data
        render_web_result(data)
        st.markdown("### Specimen Delivered")
        if st.session_state.get("email_sent_status", False):
            st.success(f"📩 {st.session_state.user_email} にレポートを送信しました。")
        else:
            st.warning("⚠️ レポート作成完了（メール送信失敗：設定を確認してください）")
        pdf_buffer = create_pdf(data)
        st.download_button("📥 DOWNLOAD REPORT", pdf_buffer, "Visionary_Report.pdf", "application/pdf")
        if st.button("START OVER"):
            st.session_state.clear()
            st.rerun()
