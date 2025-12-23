import streamlit as st
import os
import json
import io
import datetime
import smtplib
import requests
import time
from PIL import Image
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# Google系ライブラリ
import google.generativeai as genai
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# デザイン・可視化
import plotly.graph_objects as go

# PDF生成
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader

# ==========================================
# 0. 初期設定 & システム診断
# ==========================================
st.set_page_config(page_title="Aesthetic DNA Analysis | ThomYoshida", layout="wide") 

# カラーパレット (v4.2: 視認性向上・純黒純白排除)
COLORS = {
    "bg": "#222222",        # 真っ黒ではない深いグレー（背景）
    "text": "#F2F2F2",      # 真っ白ではない明るいグレー（文字）
    "accent": "#D6AE60",    # ゴールド（アクセント）
    "sub": "#A0BACC",       # 視認性を上げたサブカラー（青灰色）
    "forest": "#6FB3B8",    # 視認性を上げたアクセント（緑青色）
    "card": "#333333",      # 背景より少し明るいカード色
    "input_bg": "#404040",  # 入力フォームの背景
    "pdf_bg": "#F5F5F0",    # 生成り色（PDF背景）
    "pdf_text": "#1A1A1A",  # 墨色（PDF文字）
    "pdf_sub": "#555555"    # 濃いグレー（PDFサブ文字）
}

# 日本語フォント自動セットアップ
def setup_japanese_font():
    font_filename = "IPAexGothic.ttf"
    try:
        if os.path.exists(font_filename):
            pdfmetrics.registerFont(TTFont('IPAexGothic', font_filename))
            return 'IPAexGothic', 'IPAexGothic'
        else:
            from reportlab.pdfbase.cidfonts import UnicodeCIDFont
            pdfmetrics.registerFont(UnicodeCIDFont('HeiseiMin-W3'))
            pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5')) 
            return 'HeiseiMin-W3', 'HeiseiKakuGo-W5'
    except:
        return 'Helvetica', 'Helvetica'

FONT_SERIF, FONT_SANS = setup_japanese_font()

# APIキー設定 & 診断
MODEL_STATUS = "Unknown"
AVAILABLE_MODELS = []

if "GEMINI_API_KEY" in st.secrets:
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                AVAILABLE_MODELS.append(m.name)
        MODEL_STATUS = "Connected"
    except Exception as e:
        MODEL_STATUS = f"Error: {str(e)}"

with st.sidebar:
    st.markdown("### 🛠 System Status")
    st.caption(f"Lib Version: {genai.__version__}")
    if MODEL_STATUS == "Connected":
        st.success("API Connected")
    else:
        st.error(f"API Error: {MODEL_STATUS}")
    
    st.markdown("---")
    if st.checkbox("Manager Access", key="admin_mode"):
        admin_pass = st.text_input("Access Key", type="password")
        if admin_pass == st.secrets.get("ADMIN_PASSWORD", "admin123"):
            st.success("Access Granted")
            st.stop()

# CSS適用
st.markdown(f"""
<style>
    html, body, [class*="css"] {{
        font-size: 18px;
        background-color: {COLORS["bg"]};
        color: {COLORS["text"]};
    }}
    .stApp {{
        background-color: {COLORS["bg"]};
        color: {COLORS["text"]};
    }}
    h1, h2, h3, h4 {{
        font-family: "Hiragino Mincho ProN", serif !important;
        color: {COLORS["text"]} !important;
        text-shadow: 0px 0px 1px rgba(0,0,0,0.5);
    }}
    .stTextInput > div > div > input {{
        background-color: {COLORS["input_bg"]} !important;
        color: #FFFFFF !important;
        border: 1px solid #555 !important;
        border-radius: 4px;
    }}
    label {{
        color: {COLORS["sub"]} !important;
        font-weight: bold;
    }}
    div.stButton > button {{
        background-color: {COLORS["sub"]};
        color: #1A1A1A;
        font-weight: bold;
        border: none;
        padding: 10px 24px;
        border-radius: 4px;
        transition: all 0.3s;
    }}
    div.stButton > button:hover {{
        background-color: {COLORS["accent"]};
        color: #000;
        transform: translateY(-2px);
    }}
    div[data-testid="stForm"] {{
        background-color: {COLORS["card"]};
        padding: 20px;
        border-radius: 8px;
        border: 1px solid #444;
    }}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 1. 診断データ（設問内容は変更せず、集計用の軸タグを付与）
# ---------------------------------------------------------
# axis: "source" (Y軸: 内向/外向) or "style" (X軸: 抽象/具体)
QUIZ_DATA = [
    {"q": "Q1. 制作を始めるきっかけは？", "opts": ["内から湧き出る衝動・感情", "外部の要請や明確なコンセプト"], "type_a": "内から湧き出る衝動・感情", "axis": "source"},
    {"q": "Q2. アイデア出しの方法は？", "opts": ["走り書きや落書きから広げる", "マインドマップや箇条書きで整理する"], "type_a": "走り書きや落書きから広げる", "axis": "style"},
    {"q": "Q3. 配色を決める時は？", "opts": ["その瞬間の感覚や好み", "色彩理論やターゲット層への効果"], "type_a": "その瞬間の感覚や好み", "axis": "style"},
    {"q": "Q4. 作業環境は？", "opts": ["混沌としているが落ち着く", "整理整頓され機能的"], "type_a": "混沌としているが落ち着く", "axis": "style"},
    {"q": "Q5. 制作スケジュールは？", "opts": ["気分が乗った時に一気に進める", "毎日決まった時間にコツコツ進める"], "type_a": "気分が乗った時に一気に進める", "axis": "source"},
    {"q": "Q6. スランプに陥った時は？", "opts": ["別の刺激（映画・旅）を求める", "原因を分析し、基礎練習などをする"], "type_a": "別の刺激（映画・旅）を求める", "axis": "source"},
    {"q": "Q7. 作品の「完成」の判断基準は？", "opts": ["もうこれ以上触れないと感じた時", "予定していた要件を満たした時"], "type_a": "もうこれ以上触れないと感じた時", "axis": "style"},
    {"q": "Q8. 他人の評価に対しては？", "opts": ["好き嫌いが分かれても構わない", "多くの人に理解されるか気になる"], "type_a": "好き嫌いが分かれても構わない", "axis": "source"},
    {"q": "Q9. 制作中に新しいアイデアが浮かんだら？", "opts": ["予定を変更してでも試す", "今の作品を完成させてから次でやる"], "type_a": "予定を変更してでも試す", "axis": "style"},
    {"q": "Q10. 道具や機材へのこだわりは？", "opts": ["使い心地や愛着を重視", "スペックや効率を重視"], "type_a": "使い心地や愛着を重視", "axis": "style"},
    {"q": "Q11. 作品を通して伝えたいのは？", "opts": ["自分の内面世界や叫び", "社会へのメッセージや解決策"], "type_a": "自分の内面世界や叫び", "axis": "source"},
    {"q": "Q12. ラフスケッチの描き方は？", "opts": ["抽象的な線や形が多い", "具体的な構成や配置図に近い"], "type_a": "抽象的な線や形が多い", "axis": "style"},
    {"q": "Q13. 憧れるアーティストは？", "opts": ["破天荒で天才肌の人物", "知的で理論的な人物"], "type_a": "破天荒で天才肌の人物", "axis": "source"},
    {"q": "Q14. 締め切りに対する姿勢は？", "opts": ["ギリギリまで粘ってクオリティを上げたい", "余裕を持って早めに終わらせたい"], "type_a": "ギリギリまで粘ってクオリティを上げたい", "axis": "style"},
    {"q": "Q15. チーム制作については？", "opts": ["自分のペースが乱れるので苦手", "役割分担できて効率的なので好き"], "type_a": "自分のペースが乱れるので苦手", "axis": "source"},
    {"q": "Q16. 過去の自分の作品を見ると？", "opts": ["その時の感情が蘇る", "技術的な未熟さが気になる"], "type_a": "その時の感情が蘇る", "axis": "style"},
    {"q": "Q17. 新しい技術を学ぶ動機は？", "opts": ["表現したいものが作れるようになるから", "仕事の幅が広がりそうだから"], "type_a": "表現したいものが作れるようになるから", "axis": "source"},
    {"q": "Q18. 制作中のBGMは？", "opts": ["感情を高める曲を大音量で", "集中を妨げない環境音や無音"], "type_a": "感情を高める曲を大音量で", "axis": "style"},
    {"q": "Q19. タイトルの付け方は？", "opts": ["詩的・抽象的", "説明的・具体的"], "type_a": "詩的・抽象的", "axis": "style"},
    {"q": "Q20. SNSでの発信は？", "opts": ["作品の世界観だけを見せたい", "制作過程や思考もシェアしたい"], "type_a": "作品の世界観だけを見せたい", "axis": "source"},
    {"q": "Q21. 批評を受けた時の反応は？", "opts": ["感情的に反発してしまうことがある", "冷静に改善点として受け止める"], "type_a": "感情的に反発してしまうことがある", "axis": "source"},
    {"q": "Q22. 自分の作風を一言で言うなら？", "opts": ["エモーショナル・感覚的", "ロジカル・機能的"], "type_a": "エモーショナル・感覚的", "axis": "style"},
    {"q": "Q23. 目標設定の方法は？", "opts": ["大きな夢やビジョンを描く", "具体的な数値やステップを決める"], "type_a": "大きな夢やビジョンを描く", "axis": "source"},
    {"q": "Q24. 情報収集のスタイルは？", "opts": ["直感的に気になったものを深掘り", "体系的に幅広くチェック"], "type_a": "直感的に気になったものを深掘り", "axis": "style"},
    {"q": "Q25. 失敗作の扱いは？", "opts": ["勢いで捨ててしまう", "分析のために取っておく"], "type_a": "勢いで捨ててしまう", "axis": "style"},
    {"q": "Q26. 影響を受けやすいのは？", "opts": ["自然、音楽、夢などの体験", "本、論文、ニュースなどの情報"], "type_a": "自然、音楽、夢などの体験", "axis": "source"},
    {"q": "Q27. 制作において重要なのは？", "opts": ["「何を描くか」（主題）", "「どう描くか」（構成・技術）"], "type_a": "「何を描くか」（主題）", "axis": "style"},
    {"q": "Q28. 複雑な問題に直面したら？", "opts": ["直感を信じて突破する", "要素を分解して解決する"], "type_a": "直感を信じて突破する", "axis": "style"},
    {"q": "Q29. 完璧主義についてどう思う？", "opts": ["完成しなくても魂がこもっていればいい", "細部まで完璧でないと気が済まない"], "type_a": "完成しなくても魂がこもっていればいい", "axis": "style"},
    {"q": "Q30. あなたにとってアートとは？", "opts": ["生きることそのもの", "社会貢献や仕事の手段"], "type_a": "生きることそのもの", "axis": "source"},
]

# ---------------------------------------------------------
# 2. ユーティリティ関数
# ---------------------------------------------------------
def resize_image_for_api(image, max_width=1024):
    width_percent = (max_width / float(image.size[0]))
    if width_percent < 1:
        height_size = int((float(image.size[1]) * float(width_percent)))
        return image.resize((max_width, height_size), Image.Resampling.LANCZOS)
    return image

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
    except: return False

def send_email_with_pdf(user_email, pdf_buffer):
    if "GMAIL_ADDRESS" not in st.secrets or "GMAIL_APP_PASSWORD" not in st.secrets: return False
    sender_email = st.secrets["GMAIL_ADDRESS"]
    sender_password = st.secrets["GMAIL_APP_PASSWORD"]
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = user_email
    msg['Subject'] = "【Visionary Report】あなたの美的遺伝子(Aesthetic DNA)分析結果"
    msg.attach(MIMEText("Aesthetic DNA Analysis Report をお届けします。\n\nThom Yoshida", 'plain'))
    pdf_buffer.seek(0)
    part = MIMEApplication(pdf_buffer.read(), Name="Aesthetic_Analysis.pdf")
    part['Content-Disposition'] = 'attachment; filename="Aesthetic_Analysis.pdf"'
    msg.attach(part)
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, [user_email, sender_email], msg.as_string())
        server.quit()
        return True
    except: return False

# ---------------------------------------------------------
# 3. PDF生成ロジック
# ---------------------------------------------------------
def wrap_text_smart(text, max_char_count):
    if not text: return []
    delimiters = ['、', '。', 'て', 'に', 'を', 'は', 'が', 'と', 'へ', 'で', 'や', 'の', 'も', 'し', 'い', 'か', 'ね', 'よ', '！', '？']
    lines = []
    current_line = ""
    for char in text:
        current_line += char
        if len(current_line) >= max_char_count * 0.85: 
            if char in delimiters:
                lines.append(current_line)
                current_line = ""
                continue
            if len(current_line) >= max_char_count + 2:
                lines.append(current_line)
                current_line = ""
    if current_line: lines.append(current_line)
    return lines

def draw_wrapped_text(c, text, x, y, font, size, max_width_mm, leading, centered=False):
    c.setFont(font, size)
    char_width_mm = size * 0.352 * 0.95 
    max_chars = int(max_width_mm / char_width_mm)
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
    
    # P1: COVER
    try:
        c.drawImage("cover.jpg", 0, 0, width=width, height=height, preserveAspectRatio=False)
        c.setFillColor(HexColor('#111111'))
        c.setFillAlpha(0.3)
        c.rect(0, 0, width, height, fill=1, stroke=0)
        c.setFillAlpha(1.0)
        TEXT_COLOR = HexColor('#F4F4F4')
    except:
        c.setFillColor(HexColor(COLORS['pdf_bg']))
        c.rect(0, 0, width, height, fill=1, stroke=0)
        TEXT_COLOR = HexColor(COLORS['pdf_text'])
    c.setFillColor(TEXT_COLOR)
    c.setFont(FONT_SERIF, 52)
    c.drawCentredString(width/2, height/2 + 10*mm, json_data.get('catchphrase', 'Aesthetic DNA Report'))
    c.setFont(FONT_SANS, 18)
    c.drawCentredString(width/2, height/2 - 25*mm, "WORLDVIEW ANALYSIS REPORT")
    c.showPage()

    # P2: 12 Keywords & Triangle
    draw_header(c, "01. 過去と未来の対比", 2)
    c.setFont(FONT_SERIF, 22)
    c.setFillColor(HexColor(COLORS['pdf_sub']))
    c.drawCentredString(width/3, height - 55*mm, "PAST / ORIGIN")
    past_kws = json_data.get('twelve_past_keywords', [])
    y = height - 75*mm
    c.setFont(FONT_SANS, 11)
    for kw in past_kws[:12]:
        c.drawCentredString(width/3, y, f"◇ {kw}")
        y -= 9.5*mm
    
    c.setFont(FONT_SANS, 50)
    c.setFillColor(HexColor(COLORS['accent']))
    c.drawCentredString(width/2, height/2 - 15*mm, "▷")

    c.setFont(FONT_SERIF, 30)
    c.setFillColor(HexColor(COLORS['forest']))
    c.drawCentredString(width*2/3, height - 55*mm, "FUTURE / VISION")
    future_kws = json_data.get('twelve_future_keywords', [])
    y = height - 75*mm
    c.setFont(FONT_SANS, 16)
    c.setFillColor(HexColor(COLORS['pdf_text']))
    for kw in future_kws[:12]:
        c.drawCentredString(width*2/3, y, f"◆ {kw}")
        y -= 9.5*mm
    c.showPage()

    # P3: Center X
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
        draw_wrapped_text(c, word, cx, cy_pos - 8*mm, FONT_SANS, 24, r*1.5, 30, centered=True)
    
    c.setFont(FONT_SANS, 80)
    c.setFillColor(HexColor(COLORS['accent']))
    c.drawCentredString(width/2, cy + 5*mm, "×")

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

    # P5-P8: 20 chars wrapping
    TEXT_WIDTH_20 = 115 * mm 

    # P5
    draw_header(c, "04. おすすめするロールモデル", 5) 
    archs = json_data.get('artist_archetypes', [])
    y = height - 55*mm
    for i, a in enumerate(archs[:3]):
        c.setFont(FONT_SERIF, 22)
        c.setFillColor(HexColor(COLORS['forest']))
        c.drawString(MARGIN_X, y, f"◆ {a.get('name')}")
        c.setFillColor(HexColor(COLORS['pdf_text']))
        draw_wrapped_text(c, a.get('detail', ''), MARGIN_X + 8*mm, y - 12*mm, FONT_SANS, 14, TEXT_WIDTH_20, 20)
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
        draw_wrapped_text(c, step.get('detail', ''), MARGIN_X + 30*mm, y - 12*mm, FONT_SANS, 12, TEXT_WIDTH_20, 18)
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
        draw_wrapped_text(c, p.get('detail', ''), MARGIN_X + 5*mm, y - 6*mm, FONT_SANS, 11, TEXT_WIDTH_20, 14)
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
        draw_wrapped_text(c, f"◇ {alt}", x_right, y_alt, FONT_SANS, 14, TEXT_WIDTH_20, 20)
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
            c.setFillColor(HexColor('#111111')) # 純黒回避
            c.setFillAlpha(0.5)
            c.rect(0, 0, width, height, fill=1, stroke=0)
            c.setFillAlpha(1.0)
            TEXT_COLOR_END = HexColor('#F4F4F4') # 純白回避
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
    STRICT_WIDTH_P8 = 190 * mm
    draw_wrapped_text(c, q_text, width/2, height/2 + 20*mm, FONT_SERIF, 28, STRICT_WIDTH_P8, 36, centered=True)
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

# ==========================================
# 4. Pipeline Main Flow
# ==========================================
def render_web_result(data):
    st.markdown("---")
    st.caption("YOUR AESTHETIC DNA")
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
        st.info(f"**価値観 (Values)**\n\n{f.get('values', {}).get('word')}")
        st.warning(f"**強み (Strengths)**\n\n{f.get('strengths', {}).get('word')}")
        st.success(f"**好き (Interests)**\n\n{f.get('interests', {}).get('word')}")

if 'step' not in st.session_state: st.session_state.step = 1
if 'quiz_result' not in st.session_state: st.session_state.quiz_result = None
if 'uploaded_images' not in st.session_state: st.session_state.uploaded_images = []
if 'axis_scores' not in st.session_state: st.session_state.axis_scores = {"source": 0, "style": 0}

# STEP 1
if st.session_state.step == 1:
    try: st.image("cover.jpg", use_container_width=True)
    except: pass
    st.title("Aesthetic DNA Analysis")
    st.caption("4つの美的領域から、あなたのクリエイティブの遺伝子を解析します。")
    st.markdown("##### 00. YOUR SPECIALTY")
    specialty = st.text_input("あなたの専門分野・表現媒体（例：写真、建築、グラフィック）")
    st.markdown("##### 01. SENSE CHECK")
    st.write("直感で回答してください。あなたの創作の源泉とスタイルを探ります。")
    with st.form(key='quiz_form'):
        answers = []
        for i, item in enumerate(QUIZ_DATA):
            ans = st.radio(item["q"], item["opts"], key=f"q{i}", horizontal=True, index=None)
            answers.append((ans, item["type_a"], item.get("axis", "style"))) # axis情報も取得
        st.write("---")
        submit_button = st.form_submit_button(label="深層へ潜る（診断）")
    
    if submit_button:
        if not specialty: st.warning("専門分野を入力してください。")
        elif any(a[0] is None for a in answers): st.error("すべての質問に回答してください。")
        else:
            st.session_state.specialty = specialty
            
            # --- 新ロジック: 2軸集計 ---
            # source軸: 内向(Inner) = type_a
            # style軸: 抽象(Abstract) = type_a
            score_source = 0 # Max is count of axis='source'
            score_style = 0  # Max is count of axis='style'
            count_source = 0
            count_style = 0

            for ans, type_a_val, axis in answers:
                if axis == "source":
                    count_source += 1
                    if ans == type_a_val: score_source += 1
                else:
                    count_style += 1
                    if ans == type_a_val: score_style += 1
            
            # パーセンテージ計算 (Inner度 / Abstract度)
            pct_source = int((score_source / count_source) * 100) if count_source > 0 else 0
            pct_style = int((score_style / count_style) * 100) if count_style > 0 else 0
            
            st.session_state.axis_scores = {"source": pct_source, "style": pct_style}

            # --- 4つのアーキタイプ判定 ---
            # Inner(Source) >= 50: 内向 / < 50: 外向
            # Abstract(Style) >= 50: 抽象 / < 50: 具体
            
            if pct_source >= 50 and pct_style >= 50:
                archetype = "【深淵の詩人 (The Abyssal Poet)】\n内向的 × 抽象的\n（孤独を愛し、言葉にならない感情を表現する）"
            elif pct_source >= 50 and pct_style < 50:
                archetype = "【静寂の建築家 (The Silent Architect)】\n内向的 × 具体的\n（内なるこだわりを、完璧な技術と論理で形にする）"
            elif pct_source < 50 and pct_style >= 50:
                archetype = "【太陽の扇動者 (The Solar Agitator)】\n外向的 × 抽象的\n（情熱で大衆を巻き込み、熱狂を生む）"
            else:
                archetype = "【鋼の戦略家 (The Steel Strategist)】\n外向的 × 具体的\n（市場のニーズを分析し、最適解を出す）"
            
            st.session_state.quiz_result = archetype
            st.session_state.step = 2
            st.rerun()

# STEP 2
elif st.session_state.step == 2:
    st.header("02. VISION INTEGRATION")
    st.info(f"Archetype: **{st.session_state.quiz_result}**")
    st.caption(f"Inner/Soul: {st.session_state.axis_scores['source']}% | Abstract/Chaos: {st.session_state.axis_scores['style']}%")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Past Works")
        past_files = st.file_uploader("Origin (Max 3)", type=["jpg", "png"], accept_multiple_files=True, key="past")
    with col2:
        st.markdown("#### Future Vision")
        future_files = st.file_uploader("Ideal (Max 3)", type=["jpg", "png"], accept_multiple_files=True, key="future")
    if st.button("次へ進む（レポート作成へ）"):
        if not past_files:
            st.error("分析のために、少なくとも1枚の作品画像をアップロードしてください。")
        else:
            st.session_state.uploaded_images = []
            for f in past_files:
                img = Image.open(f)
                resized_img = resize_image_for_api(img)
                st.session_state.uploaded_images.append(resized_img)
            if future_files:
                for f in future_files:
                    img = Image.open(f)
                    resized_img = resize_image_for_api(img)
                    st.session_state.uploaded_images.append(resized_img)
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
            submit = st.form_submit_button("診断結果を見る", type="primary")
            if submit:
                if user_name and user_email:
                    st.session_state.user_name = user_name
                    st.session_state.user_email = user_email
                    save_to_google_sheets(user_name, user_email, st.session_state.specialty, st.session_state.quiz_result)
                    st.session_state.step = 4
                    st.rerun()
                else: st.warning("情報を入力してください。")

# STEP 4 (AI Execution with Force-Completion)
elif st.session_state.step == 4:
    if "analysis_data" not in st.session_state:
        with st.spinner("Connecting to Visionary Core... Aesthetic DNAを解析中..."):
            
            success = False
            
            # --- AI Logic ---
            if "GEMINI_API_KEY" in st.secrets:
                # Prompt Update: 4つの領域理論をAIに注入
                prompt_text = f"""
                あなたは世界的なアートディレクター Thom Yoshida です。
                ユーザーの「専門分野」と、4つの美的領域マトリクスに基づく「アーキタイプ」を分析し、
                専用の診断レポートJSONを作成してください。

                【ユーザー情報】
                - 専門分野: {st.session_state.specialty}
                - 診断アーキタイプ: {st.session_state.quiz_result}
                - 内向度(Soul): {st.session_state.axis_scores['source']}%
                - 抽象度(Chaos): {st.session_state.axis_scores['style']}%
                
                【アーキタイプ定義（参考）】
                1. 深淵の詩人: 内向×抽象。儚さ、静寂、孤独、ポエジー。
                2. 静寂の建築家: 内向×具体。職人、構造、完璧主義、機能美。
                3. 太陽の扇動者: 外向×抽象。熱狂、エネルギー、カリスマ、拡散。
                4. 鋼の戦略家: 外向×具体。論理、市場、勝利、最適化。

                【必須出力JSON構造】
                {{
                    "catchphrase": "その人のアーキタイプを象徴する、詩的で短いキャッチコピー(15文字以内)",
                    "twelve_past_keywords": ["{st.session_state.quiz_result}に関連する過去/原点ワード12個"],
                    "twelve_future_keywords": ["{st.session_state.quiz_result}が目指すべき未来/進化ワード12個"],
                    "sense_metrics": [
                        {{"left": "Concrete/Logic", "right": "Abstract/Sense", "value": {st.session_state.axis_scores['style']}}}, 
                        {{"left": "Social/Outer", "right": "Inner/Soul", "value": {st.session_state.axis_scores['source']}}},
                        {{"left": "Speed", "right": "Quality", "value": 0〜100の数値}},
                        {{"left": "Simplicity", "right": "Complexity", "value": 0〜100の数値}},
                        {{"left": "Function", "right": "Story", "value": 0〜100の数値}},
                        {{"left": "Tradition", "right": "Innovation", "value": 0〜100の数値}},
                        {{"left": "Realism", "right": "Fantasy", "value": 0〜100の数値}},
                        {{"left": "Light", "right": "Shadow", "value": 0〜100の数値}}
                    ],
                    "formula": {{
                        "values": {{"word": "価値観を一言で", "detail": "そのタイプ特有の価値観の解説"}},
                        "strengths": {{"word": "最大の武器", "detail": "その武器の使い方"}},
                        "interests": {{"word": "魂が震えるもの", "detail": "興味の源泉"}}
                    }},
                    "roadmap_steps": [
                        {{"title": "Stepタイトル", "detail": "そのタイプが成功するための具体的ステップ"}} を3つ
                    ],
                    "artist_archetypes": [
                        {{"name": "ロールモデル名", "detail": "なぜその人が参考になるか"}} を3名
                    ],
                    "final_proposals": [
                        {{"point": "ビジョン要点", "detail": "詳細"}} を5つ
                    ],
                    "alternative_expressions": [
                        "おすすめの別表現手法" を3つ
                    ],
                    "inspiring_quote": {{
                        "text": "その人の魂に響く、実在する偉人の名言（日本語訳）",
                        "author": "著者名"
                    }}
                }}
                """
                
                try:
                    target_model = None
                    if AVAILABLE_MODELS:
                        for m in AVAILABLE_MODELS:
                            if '1.5' in m and 'flash' in m: target_model = m; break
                        if not target_model:
                            for m in AVAILABLE_MODELS:
                                if '1.5' in m and 'pro' in m: target_model = m; break
                        if not target_model: target_model = AVAILABLE_MODELS[0]
                    
                    if target_model:
                        model = genai.GenerativeModel(target_model)
                        contents_vision = [prompt_text] + st.session_state.uploaded_images
                        response = model.generate_content(contents_vision, generation_config={"response_mime_type": "application/json"})
                        data = json.loads(response.text)
                        success = True
                except Exception as e:
                    print(f"AI Generation Error: {e}")

            # --- Force Completion (Safety Net) ---
            if not success:
                st.warning("⚠️ AIサーバーが混雑しているため、デモモードでレポートを生成しました。（エラー回避）")
                data = {
                    "catchphrase": "Visionary Mode", 
                    "twelve_past_keywords": ["Origin", "Noise", "Copy", "Past", "Ego", "Gray", "Blur", "Dust", "Shadow", "Limit", "Wall", "Cage"],
                    "twelve_future_keywords": ["Vision", "Core", "Original", "Future", "Altruism", "Vivid", "Clear", "Star", "Light", "Flow", "Sky", "Wing"],
                    "sense_metrics": [{"left": "Logic", "right": "Emotion", "value": 70}] * 8,
                    "formula": {"values": {"word": "System", "detail": "Fallback Mode"}, "strengths": {"word": "Resilience", "detail": "Backup"}, "interests": {"word": "Safety", "detail": "Secure"}},
                    "roadmap_steps": [{"title": "Step 1", "detail": "Analyze Connection"}, {"title": "Step 2", "detail": "Retry Later"}, {"title": "Step 3", "detail": "Contact Support"}],
                    "artist_archetypes": [{"name": "System Admin", "detail": "Ensures continuity."}],
                    "final_proposals": [{"point": "Check API Key", "detail": "Verify settings."}, {"point": "Check Quota", "detail": "You may have exceeded free tier."}],
                    "alternative_expressions": ["Manual Review", "Direct Contact"],
                    "inspiring_quote": {"text": "Creation is the act of connecting.", "author": "Thom Yoshida"}
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
        st.download_button("📥 診断レポートをダウンロード", pdf_buffer, "Aesthetic_Analysis.pdf", "application/pdf")
        if st.button("最初からやり直す"):
            st.session_state.clear()
            st.rerun()
