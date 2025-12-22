import streamlit as st
import os
import json
import io
import datetime
import smtplib
import requests # 追加：外部画像取得用
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
from reportlab.lib.utils import ImageReader # 追加：PIL画像をPDFに埋め込む用

# ---------------------------------------------------------
# 0. 初期設定 & セキュリティ
# ---------------------------------------------------------
st.set_page_config(page_title="Visionary Analysis | ThomYoshida", layout="wide") 

# デザイン定義 (COLORS - 世界観研究所グレー v2.1)
# より洗練された、深みのあるチャコールグレー系に変更
COLORS = {
    "bg": "#2A2A2A",      # メイン背景：少し温かみのある深いグレー
    "text": "#E8E8E8",    # 文字色：真っ白すぎないオフホワイト
    "accent": "#D6AE60",  # アクセント：落ち着いたゴールド
    "sub": "#8BA6B0",     # サブカラー：スモーキーなブルーグレー
    "forest": "#5F9EA0",  # フォレスト：深みのある青緑
    "card": "#383838",    # カード背景：メインより少し明るいグレー
    "pdf_bg": "#FAFAF8",  # PDF背景：紙の質感を感じるオフホワイト
    "pdf_text": "#2C2C2C",# PDF文字：真っ黒ではない墨色
    "pdf_sub": "#888888"  # PDFサブ：ミディアムグレー
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
# 1. 診断データ (30 Questions)
# ---------------------------------------------------------
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

# ---------------------------------------------------------
# 2. デザイン & ユーティリティ関数
# ---------------------------------------------------------
# CSSで全体の文字サイズを調整
def apply_custom_css():
    st.markdown(f"""
    <style>
        /* 全体の基本フォントサイズをアップ */
        html, body, [class*="css"] {{
            font-size: 18px; 
        }}
        .stApp {{ background-color: {COLORS["bg"]}; color: {COLORS["text"]}; }}
        
        /* 見出しサイズの調整 */
        h1 {{ font-size: 3.2rem !important; font-family: "Hiragino Mincho ProN", serif !important; color: {COLORS["text"]} !important; }}
        h2 {{ font-size: 2.4rem !important; font-family: "Hiragino Mincho ProN", serif !important; color: {COLORS["text"]} !important; }}
        h3 {{ font-size: 2.0rem !important; font-family: "Hiragino Mincho ProN", serif !important; color: {COLORS["text"]} !important; }}
        h4 {{ font-size: 1.6rem !important; font-family: "Hiragino Mincho ProN", serif !important; color: {COLORS["text"]} !important; }}
        h5 {{ font-size: 1.4rem !important; font-family: "Hiragino Mincho ProN", serif !important; color: {COLORS["text"]} !important; }}
        
        /* 本文フォント */
        p, div, label, span, li {{ font-family: "Hiragino Kaku Gothic ProN", sans-serif; color: {COLORS["text"]}; font-size: 1.1rem !important; }}
        
        /* 入力フォーム */
        .stTextInput > div > div > input {{ background-color: {COLORS["card"]}; color: #FFF; border: 1px solid #555; font-size: 1.1rem; }}
        
        /* ボタン */
        div.stButton > button {{
            background-color: {COLORS["sub"]}; color: white; border-radius: 4px; border: none;
            padding: 12px 28px; letter-spacing: 0.1em; transition: all 0.3s; font-size: 1.2rem;
        }}
        div.stButton > button:hover {{ background-color: {COLORS["forest"]}; transform: translateY(-2px); }}
        .stDownloadButton > button {{
            width: 100% !important; background-color: {COLORS["accent"]} !important;
            color: #1E1E1E !important; border: none !important; font-weight: bold !important; font-size: 1.3rem !important;
        }}
        
        /* その他コンポーネント */
        .streamlit-expanderHeader {{ background-color: {COLORS["card"]}; color: {COLORS["text"]}; font-size: 1.2rem; }}
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
# 3. 外部連携関数 (Sheets & Email)
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
    except Exception as e:
        return pd.DataFrame()

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
        recipients = [user_email, sender_email]
        server.sendmail(sender_email, recipients, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Email Error: {e}")
        return False

# ---------------------------------------------------------
# 4. PDF生成ロジック (Design Layer - High Visibility Mode)
# ---------------------------------------------------------

# Helper: テキストラップ
def wrap_text_smart(text, max_char_count):
    if not text: return []
    delimiters = ['、', '。', 'て', 'に', 'を', 'は', 'が', 'と', 'へ', 'で', 'や', 'の', 'も', 'し', 'い', 'か', 'ね', 'よ']
    lines = []
    current_line = ""
    i = 0
    while i < len(text):
        char = text[i]
        current_line += char
        i += 1
        if len(current_line) >= max_char_count * 0.9:
            if char in delimiters:
                lines.append(current_line)
                current_line = ""
                continue
            if len(current_line) >= max_char_count:
                lines.append(current_line)
                current_line = ""
    if current_line: lines.append(current_line)
    return lines

def draw_wrapped_text(c, text, x, y, font, size, max_width, leading, centered=False):
    c.setFont(font, size)
    char_width_mm = size * 0.352 * 0.9 
    max_chars = int(max_width / char_width_mm)
    lines = wrap_text_smart(text, max_chars)
    current_y = y
    for line in lines:
        if centered:
            c.drawCentredString(x, current_y, line)
        else:
            c.drawString(x, current_y, line)
        current_y -= leading

# Helper: ヘッダー（文字サイズUP）
def draw_header(c, title, page_num):
    width, height = landscape(A4)
    c.setFillColor(HexColor(COLORS['pdf_bg']))
    c.rect(0, 0, width, height, fill=1, stroke=0)
    c.setStrokeColor(HexColor(COLORS['pdf_sub']))
    c.setLineWidth(0.5)
    c.line(10*mm, height - 25*mm, width - 10*mm, height - 25*mm)
    c.setFont(FONT_SANS, 20) # Title Size UP
    c.setFillColor(HexColor(COLORS['forest']))
    c.drawString(15*mm, height - 20*mm, title.upper())
    c.setFont(FONT_SANS, 12) # Page Num Size UP
    c.setFillColor(HexColor(COLORS['pdf_sub']))
    c.drawRightString(width - 15*mm, height - 20*mm, f"{page_num} / 8")

# Helper: 矢印付きスライダー（文字サイズUP）
def draw_arrow_slider(c, x, y, width_mm, left_text, right_text, value):
    bar_width = width_mm * mm
    c.setFont(FONT_SERIF, 12) # Label Size UP
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
    c.circle(dot_x, y, 2.5*mm, fill=1, stroke=1) # Dot Size UP

# --- PDF生成メイン関数 ---
def create_pdf(json_data):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)
    MARGIN_X = width * 0.12
    
    # ================= P1. COVER (文字サイズUP) =================
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
    c.setFont(FONT_SERIF, 52) # Title UP
    c.drawCentredString(width/2, height/2 + 10*mm, json_data.get('catchphrase', 'Visionary Report'))
    c.setFont(FONT_SANS, 18) # Subtitle UP
    c.drawCentredString(width/2, height/2 - 25*mm, "WORLDVIEW ANALYSIS REPORT")
    c.setFont(FONT_SERIF, 12) # Credit UP
    c.drawCentredString(width/2, 20*mm, f"Designed by ThomYoshida AI | {datetime.datetime.now().strftime('%Y.%m.%d')}")
    c.showPage()

    # ================= P2. KEYWORD CONTRAST (文字サイズUP) =================
    draw_header(c, "01. Keyword Contrast", 2)
    
    # Past
    c.setFont(FONT_SERIF, 22) # Heading UP
    c.setFillColor(HexColor(COLORS['pdf_sub']))
    c.drawCentredString(width/3, height - 55*mm, "PAST / ORIGIN")
    past_kws = json_data.get('twelve_past_keywords', [])
    y = height - 75*mm
    c.setFont(FONT_SANS, 12) # Text UP
    for kw in past_kws[:8]:
        c.drawCentredString(width/3, y, f"◇ {kw}")
        y -= 11*mm

    # Future (強調＆サイズUP)
    c.setFont(FONT_SERIF, 30) # Heading 強調UP
    c.setFillColor(HexColor(COLORS['forest']))
    c.drawCentredString(width*2/3, height - 55*mm, "FUTURE / VISION")
    future_kws = json_data.get('twelve_future_keywords', [])
    y = height - 75*mm
    c.setFont(FONT_SANS, 16) # Text 強調UP
    c.setFillColor(HexColor(COLORS['pdf_text']))
    for kw in future_kws[:8]:
        c.drawCentredString(width*2/3, y, f"◆ {kw}")
        y -= 13*mm
    c.showPage()

    # ================= P3. THE FORMULA (文字サイズUP) =================
    draw_header(c, "02. The Formula", 3)
    formula = json_data.get('formula', {})
    cy = height/2 - 5*mm
    r = 42*mm # Radius UP
    
    positions = [
        (width/2 - r*1.4, cy + r*0.8, "価値観", formula.get('values', {}).get('word', '')),
        (width/2 + r*1.4, cy + r*0.8, "強み", formula.get('strengths', {}).get('word', '')),
        (width/2, cy - r*1.2, "興味", formula.get('interests', {}).get('word', ''))
    ]
    
    for cx, cy_pos, title, word in positions:
        c.setStrokeColor(HexColor(COLORS['forest']))
        c.setFillColor(HexColor('#FFFFFF'))
        c.setLineWidth(1.5)
        c.circle(cx, cy_pos, r, fill=1, stroke=1)
        c.setFont(FONT_SERIF, 16) # Title UP
        c.setFillColor(HexColor(COLORS['pdf_sub']))
        c.drawCentredString(cx, cy_pos + 18*mm, title)
        c.setFont(FONT_SANS, 22) # Word UP
        c.setFillColor(HexColor(COLORS['pdf_text']))
        c.drawCentredString(cx, cy_pos - 5*mm, word)

    c.setFont(FONT_SANS, 44) # X Mark UP
    c.setFillColor(HexColor(COLORS['accent']))
    c.drawCentredString(width/2, cy + r*0.8, "×")
    c.drawCentredString(width/2 - r*0.7, cy - r*0.2, "×")
    c.drawCentredString(width/2 + r*0.7, cy - r*0.2, "×")

    c.setFont(FONT_SERIF, 36) # Catchphrase UP
    c.setFillColor(HexColor(COLORS['pdf_text']))
    c.drawCentredString(width/2, height - 40*mm, f"「{json_data.get('catchphrase', '')}」")
    c.showPage()

    # ================= P4. SENSE BALANCE (文字サイズUP) =================
    draw_header(c, "03. Sense Balance", 4)
    metrics = json_data.get('sense_metrics', [])
    y = height - 65*mm
    for i, m in enumerate(metrics[:8]):
        x = MARGIN_X + 25*mm if i < 4 else width/2 + 25*mm
        curr_y = y - (i % 4) * 24*mm
        draw_arrow_slider(c, x, curr_y, 48, m.get('left'), m.get('right'), m.get('value'))
    c.showPage()

    # ================= P5. SOUL ARCHETYPE (文字サイズUP) =================
    draw_header(c, "04. Soul Archetype", 5)
    archs = json_data.get('artist_archetypes', [])
    y = height - 55*mm
    for i, a in enumerate(archs[:3]):
        c.setFont(FONT_SERIF, 20) # Name UP
        c.setFillColor(HexColor(COLORS['forest']))
        c.drawString(MARGIN_X, y, f"◆ {a.get('name')}")
        c.setFillColor(HexColor(COLORS['pdf_text']))
        draw_wrapped_text(c, a.get('detail', ''), MARGIN_X + 8*mm, y - 10*mm, FONT_SANS, 12, width - MARGIN_X*2 - 20*mm, 18) # Text UP
        y -= 48*mm
    c.showPage()

    # ================= P6. FUTURE ROADMAP (文字サイズUP) =================
    draw_header(c, "05. Future Roadmap", 6)
    steps = json_data.get('roadmap_steps', [])
    y = height - 65*mm
    for i, step in enumerate(steps):
        c.setFont(FONT_SANS, 40) # Number UP
        c.setFillColor(HexColor(COLORS['accent']))
        c.drawString(MARGIN_X, y - 5*mm, f"0{i+1}")
        c.setFont(FONT_SERIF, 18) # Title UP
        c.setFillColor(HexColor(COLORS['pdf_text']))
        c.drawString(MARGIN_X + 30*mm, y, step.get('title', ''))
        c.setFillColor(HexColor(COLORS['pdf_sub']))
        draw_wrapped_text(c, step.get('detail', ''), MARGIN_X + 30*mm, y - 12*mm, FONT_SANS, 12, 125*mm, 18) # Text UP
        y -= 45*mm
    c.showPage()

    # ================= P7. NEXT VISION & ALTERNATIVES (文字サイズUP) =================
    draw_header(c, "06. Next Vision & Alternatives", 7)
    
    # Next Vision
    c.setFont(FONT_SERIF, 20) # Heading UP
    c.setFillColor(HexColor(COLORS['forest']))
    c.drawString(MARGIN_X, height - 55*mm, "Next Vision")
    proposals = json_data.get('final_proposals', [])
    y = height - 70*mm
    for p in proposals[:2]:
        c.setFont(FONT_SANS, 14) # Point UP
        c.setFillColor(HexColor(COLORS['pdf_text']))
        c.drawString(MARGIN_X, y, f"・{p.get('point')}")
        draw_wrapped_text(c, p.get('detail', ''), MARGIN_X + 5*mm, y - 6*mm, FONT_SANS, 11, 150*mm, 15) # Detail UP
        y -= 28*mm
        
    # Alternative Expressions
    c.setFont(FONT_SERIF, 20) # Heading UP
    c.setFillColor(HexColor(COLORS['forest']))
    c.drawString(MARGIN_X, y - 20*mm, "Recommended Alternative Expressions")
    alts = json_data.get('alternative_expressions', [])
    y_alt = y - 38*mm
    for alt in alts[:3]:
        c.setFont(FONT_SANS, 14) # Text UP
        c.setFillColor(HexColor(COLORS['pdf_text']))
        c.drawString(MARGIN_X, y_alt, f"◇ {alt}")
        y_alt -= 14*mm
    c.showPage()

    # ================= P8. THE MESSAGE (External Image + Quote) =================
    # ODANからの引用を想定した、Unsplashの高画質画像URL（抽象・建築・光）
    image_url = "https://images.unsplash.com/photo-1495312040802-a929cd14a6ab?q=80&w=2940&auto=format&fit=crop&ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D"
    
    bg_drawn = False
    try:
        # 外部URLから画像をメモリ上に取得
        response = requests.get(image_url, stream=True, timeout=10)
        if response.status_code == 200:
            img_data = io.BytesIO(response.content)
            pil_img = Image.open(img_data)
            img_reader = ImageReader(pil_img) # ReportLab用に変換

            # 描画
            c.drawImage(img_reader, 0, 0, width=width, height=height, preserveAspectRatio=False)
            c.setFillColor(HexColor('#000000'))
            c.setFillAlpha(0.5) # フィルターを少し濃くして文字を強調
            c.rect(0, 0, width, height, fill=1, stroke=0)
            c.setFillAlpha(1.0)
            bg_drawn = True
            TEXT_COLOR_END = HexColor('#FFFFFF')
            ACCENT_COLOR_END = HexColor(COLORS['accent'])
        else: raise Exception("Image download failed")
            
    except Exception as e:
        print(f"P8 Image Error: {e}")
        draw_header(c, "07. The Message", 8)
        TEXT_COLOR_END = HexColor(COLORS['pdf_text'])
        ACCENT_COLOR_END = HexColor(COLORS['forest'])

    quote_data = json_data.get('inspiring_quote', {})
    q_text = quote_data.get('text', '')
    q_author = quote_data.get('author', '')

    # 名言を中央に配置 (文字サイズUP)
    c.setFillColor(TEXT_COLOR_END)
    draw_wrapped_text(c, q_text, width/2, height/2 + 20*mm, FONT_SERIF, 28, width*0.75, 36, centered=True) # Quote Size UP
    
    c.setFont(FONT_SANS, 18) # Author Size UP
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
# 5. Web UI & Pipeline
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
        st.success(f"**興味**\n\n{f.get('interests', {}).get('word')}")
        
    # Web上にもおすすめ表現を表示
    st.markdown("### Recommended Alternative Expressions")
    alts = data.get('alternative_expressions', [])
    for alt in alts:
        st.write(f"◇ {alt}")

# --- Pipeline ---
if 'step' not in st.session_state: st.session_state.step = 1
if 'quiz_result' not in st.session_state: st.session_state.quiz_result = None

# STEP 1: Specialty & Quiz
if st.session_state.step == 1:
    try: st.image("cover.jpg", use_container_width=True)
    except: pass
    st.title("Visionary Analysis")
    st.caption("美意識の解像度を上げる、対話型診断ツール")
    
    # 専門分野入力 (New!)
    st.markdown("##### 00. YOUR SPECIALTY")
    specialty = st.text_input("あなたの専門分野・表現媒体を教えてください（例：写真、建築、グラフィックなど）")

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
        if not specialty:
            st.warning("専門分野を入力してください。")
        elif any(a[0] is None for a in answers):
            st.error("すべての質問に回答してください。")
        else:
            st.session_state.specialty = specialty # 保存
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

# STEP 2: UPLOAD
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
        if not past_files: st.error("分析のために画像をアップロードしてください。")
        else:
            st.session_state.step = 3
            st.rerun()

# STEP 3: LEAD CAPTURE
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

# STEP 4: GENERATE & DISPLAY
elif st.session_state.step == 4:
    if "analysis_data" not in st.session_state:
        with st.spinner("Connecting to Visionary Core..."):
            # ▼▼▼ ダミーデータ更新（8ページ構成に対応） ▼▼▼
            data = {
                "catchphrase": "静寂の青き建築家",
                "twelve_past_keywords": ["混沌", "模倣", "ノイズ", "迷い", "多弁", "装飾", "迎合", "未熟"],
                "twelve_future_keywords": ["静寂", "本質", "余白", "確信", "沈黙", "構造", "孤高", "洗練"],
                "sense_metrics": [
                    {"left": "具象", "right": "抽象", "value": 80}, {"left": "感情", "right": "論理", "value": 60},
                    {"left": "喧騒", "right": "静寂", "value": 90}, {"left": "伝統", "right": "革新", "value": 40},
                    {"left": "儚さ", "right": "永続", "value": 70}, {"left": "日常", "right": "幻想", "value": 75},
                    {"left": "繊細", "right": "大胆", "value": 50}, {"left": "内向", "right": "外交", "value": 30}
                ],
                "formula": {
                    "values": {"word": "静謐", "detail": "ノイズのない世界"},
                    "strengths": {"word": "構図力", "detail": "黄金比への理解"},
                    "interests": {"word": "構造物", "detail": "コンクリート建築"}
                },
                "roadmap_steps": [
                    {"title": "余白の再定義", "detail": "画面の8割を余白にする勇気を持つことから始める。"},
                    {"title": "光の指向性", "detail": "拡散光ではなく、意図的なサイドライトを用いてドラマを作る。"},
                    {"title": "シリーズ化", "detail": "単写真ではなく、3枚1組の組写真として物語を構成する。"}
                ],
                "artist_archetypes": [ # 3名追加
                    {"name": "アンドレアス・グルスキー", "detail": "俯瞰的な視点と、幾何学的な構造美を追求する姿勢が共鳴。"},
                    {"name": "杉本博司", "detail": "時間と光を概念的に捉え、静寂を表現するアプローチ。"},
                    {"name": "ル・コルビュジエ", "detail": "機能性と美しさを統合し、モダニズムの基礎を築いた思考。"}
                ],
                "final_proposals": [
                    {"point": "無機質な被写体選び", "detail": "植物などの有機物ではなく、ビルや階段などの構造物を撮る。"},
                    {"point": "彩度を落とす", "detail": "色は情報のノイズになり得るため、彩度を-20%する。"}
                ],
                "alternative_expressions": [ # おすすめの別表現 (New!)
                    "モノクロームフィルム写真での建築撮影",
                    "環境音を用いたサウンドインスタレーション",
                    "ミニマルなタイポグラフィによるポスター制作"
                ],
                "inspiring_quote": {
                    "text": "完璧とは、付け加えるものが何もないときではなく、取り除くものが何もないときに達成される。",
                    "author": "サン＝テグジュペリ"
                }
            }
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
