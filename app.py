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
from email.header import Header

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

# ---------------------------------------------------------
# 0. 初期設定 & フォント自動セットアップ
# ---------------------------------------------------------
st.set_page_config(page_title="世界観診断 | Visionary Analysis", layout="wide")

# デザイン定義 (COLORS - v5.2 Matte White Tuned)
COLORS = {
    "bg": "#1E1E1E",        
    "text": "#F0F0F0",      
    "accent": "#D6AE60",    
    "sub": "#A0BACC",       
    "forest": "#6FB3B8",    
    "card": "#2D2D2D",      
    "card_hover": "#383838",
    "input_bg": "#404040",  
    "pdf_bg": "#FAFAF8",    
    "pdf_text": "#2C2C2C",
    "pdf_sub": "#555555"
}

# 日本語フォント設定
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

# APIキー設定
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# パスワード認証
def check_password():
    if "password_correct" not in st.session_state: st.session_state.password_correct = False
    if "APP_PASSWORD" not in st.secrets: return True
    if st.session_state.password_correct: return True
    st.markdown("### 🔒 Restricted Access")
    password_input = st.text_input("パスコードを入力してください", type="password")
    if password_input:
        if password_input == st.secrets["APP_PASSWORD"]:
            st.session_state.password_correct = True
            st.rerun()
        else: st.error("パスコードが違います")
    st.stop()

check_password()

# ---------------------------------------------------------
# 1. デザインCSS
# ---------------------------------------------------------
st.markdown(f"""
<style>
    /* ベース設定 */
    html, body, [class*="css"] {{
        font-size: 18px;
        background-color: {COLORS["bg"]};
        color: {COLORS["text"]};
        font-family: "Hiragino Kaku Gothic ProN", "Meiryo", sans-serif;
    }}
    .stApp {{ background-color: {COLORS["bg"]}; }}
    
    /* 見出し設定 (h1-h5) */
    h1, h2, h3, h4, h5 {{
        font-family: "Hiragino Mincho ProN", serif !important;
        color: {COLORS["text"]} !important;
        letter-spacing: 0.05em;
    }}

    .stMarkdown p {{
        color: {COLORS["text"]} !important;
        opacity: 0.95;
    }}
    .stTextInput label, .stSelectbox label {{
        color: {COLORS["text"]} !important;
        font-size: 1.0rem !important;
        font-weight: normal !important;
        opacity: 0.95;
    }}
    .stTextInput div[data-testid="stMarkdownContainer"] p {{
         color: {COLORS["text"]} !important;
    }}

    /* 設問エリア */
    .stRadio label p {{
        font-size: 1.3rem !important;
        font-weight: 600 !important;
        color: {COLORS["accent"]} !important;
        margin-bottom: 10px;
    }}

    /* 選択肢カード */
    div[role="radiogroup"] > label {{
        background-color: {COLORS["card"]};
        padding: 15px 20px;
        border-radius: 10px;
        margin-bottom: 12px;
        border: 1px solid #555;
        transition: all 0.3s ease;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }}
    div[role="radiogroup"] > label:hover {{
        border-color: {COLORS["accent"]};
        background-color: {COLORS["card_hover"]};
        transform: translateX(5px);
    }}
    div[role="radiogroup"] > label p {{
        color: #FFFFFF !important;
        font-size: 1.1rem !important;
        font-weight: 400 !important;
        margin: 0 !important;
    }}

    /* 入力フォーム */
    .stTextInput > div > div > input, .stSelectbox > div > div > div {{
        background-color: {COLORS["input_bg"]} !important;
        color: #FFFFFF !important; 
        border: 1px solid #666 !important;
        font-size: 1.1rem;
    }}
    
    /* ボタン */
    div.stButton > button {{
        background-color: {COLORS["sub"]};
        color: #1A1A1A;
        font-weight: bold;
        border: none;
        padding: 12px 30px;
        border-radius: 6px;
        font-size: 1.1rem;
    }}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. 診断データ
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
# 3. ユーティリティ関数
# ---------------------------------------------------------
def resize_image_for_api(image, max_width=1024):
    width_percent = (max_width / float(image.size[0]))
    if width_percent < 1:
        height_size = int((float(image.size[1]) * float(width_percent)))
        return image.resize((max_width, height_size), Image.Resampling.LANCZOS)
    return image

def save_to_google_sheets(name, age, region, email, specialty, diagnosis_type):
    if "gcp_service_account" not in st.secrets:
        return False, "Secretsにgcp_service_accountの設定がありません"
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        if "type" not in creds_dict:
             try:
                 creds_dict = json.loads(st.secrets["gcp_service_account"])
             except: pass

        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        sheet_name = st.secrets.get("SHEET_NAME", "customer_list")
        sheet = client.open(sheet_name).sheet1
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([now, name, age, region, email, specialty, diagnosis_type])
        return True, None
    except Exception as e:
        return False, str(e)

def send_email_with_pdf(user_email, pdf_buffer):
    if "GMAIL_ADDRESS" not in st.secrets or "GMAIL_PASSWORD" not in st.secrets:
        return False, "設定エラー: secrets.toml に GMAIL_ADDRESS または GMAIL_PASSWORD がありません。"
        
    sender_email = str(st.secrets["GMAIL_ADDRESS"]).strip().replace('\xa0', '').replace('\u3000', ' ')
    sender_password = str(st.secrets["GMAIL_PASSWORD"]).strip().replace('\xa0', '').replace('\u3000', ' ')
    user_email = str(user_email).strip().replace('\xa0', '').replace('\u3000', ' ')
    
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = user_email
    msg['Subject'] = Header("【世界観診断レポート】あなたの診断結果をお届けします", 'utf-8')
    
    body = f"""{st.session_state.get('user_name', 'クリエイター')} 様

世界観 研究所のThom Yoshidaです。
診断をご利用いただき、ありがとうございます。

AIと私の視点で分析した「美の設計図（PDF）」を添付いたしました。
まずは、ご自身の「現在地」と「未来」のギャップを確認してください。

もし、レポートにある「理想の世界観」を
最短で、かつ論理的に実装したいなら、
私が直接指導する以下のサロンがお役に立つかもしれません。

▼ 招待制・世界観 研究所 オンラインサロン【 II. Atelier（アトリエ）】
https://www.street-academy.com/subscription/services/3794?conversion_name=direct_message&tracking_code=d09de3445c9cd6725ecac969e0f06d76
※ レポートを見た方限定の案内です。

あなたの「好き」が、世界を照らすことを願っています。

Thom Yoshida"""
    
    body = body.replace('\u00a0', ' ').replace('\xa0', ' ')
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    
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
        return True, None 
    except Exception as e:
        return False, str(e)

# ---------------------------------------------------------
# 4. PDF生成ロジック
# ---------------------------------------------------------

def wrap_text_smart(text, max_char_count=15):
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

def draw_wrapped_text(c, text, x, y, font, size, width_limit_mm, leading, centered=False):
    c.setFont(font, size)
    lines = wrap_text_smart(text, max_char_count=15)
    current_y = y
    for line in lines:
        if centered: c.drawCentredString(x, current_y, line)
        else: c.drawString(x, current_y, line)
        current_y -= leading

def draw_header(c, title, page_num):
    width, height = landscape(A4)
    MARGIN_X = width * 0.17 
    c.setFillColor(HexColor(COLORS['pdf_bg']))
    c.rect(0, 0, width, height, fill=1, stroke=0)
    c.setStrokeColor(HexColor(COLORS['pdf_sub']))
    c.setLineWidth(0.5)
    c.line(MARGIN_X, height - 25*mm, width - MARGIN_X, height - 25*mm)
    
    c.setFont(FONT_SANS, 20)
    c.setFillColor(HexColor(COLORS['forest']))
    c.drawString(MARGIN_X, height - 20*mm, title) 
    
    c.setFont(FONT_SANS, 12)
    c.setFillColor(HexColor(COLORS['pdf_sub']))
    c.drawRightString(width - MARGIN_X, height - 20*mm, f"{page_num} / 8")

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

def create_pdf(json_data, user_name="Guest"):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)
    
    MARGIN_X = width * 0.12
    CONTENT_WIDTH = width - (MARGIN_X * 2)
    
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
    
    # キャッチコピー
    c.setFont(FONT_SERIF, 52)
    c.drawCentredString(width/2, height/2 + 10*mm, json_data.get('catchphrase', 'Visionary Report'))
    
    # ユーザー名（追加箇所）
    c.setFont(FONT_SERIF, 24)
    c.drawCentredString(width/2, height/2 - 8*mm, f"{user_name} 様")
    
    # サブタイトル
    c.setFont(FONT_SANS, 18)
    c.drawCentredString(width/2, height/2 - 25*mm, "WORLDVIEW ANALYSIS REPORT")
    
    c.setFont(FONT_SERIF, 12)
    c.drawCentredString(width/2, 20*mm, f"Designed by ThomYoshida AI | {datetime.datetime.now().strftime('%Y.%m.%d')}")
    c.showPage()

    # P2: KEYWORDS
    draw_header(c, "01. あなたを作る「原点」と「未来」", 2)
    c.setFont(FONT_SERIF, 22)
    c.setFillColor(HexColor(COLORS['pdf_sub']))
    c.drawCentredString(width/3, height - 55*mm, "原点 / 現在")
    
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
    c.drawCentredString(width*2/3, height - 55*mm, "未来 / 理想")
    
    future_kws = json_data.get('twelve_future_keywords', [])
    y = height - 75*mm
    c.setFont(FONT_SANS, 16)
    c.setFillColor(HexColor(COLORS['pdf_text']))
    for kw in future_kws[:12]:
        c.drawCentredString(width*2/3, y, f"◆ {kw}")
        y -= 9.5*mm
    c.showPage()

    # P3: FORMULA
    draw_header(c, "02. あなただけの成功方程式", 3)
    formula = json_data.get('formula', {})
    cy = height/2 - 10*mm
    r = 38*mm 
    positions = [
        (width/2 - r*1.55, cy + r*0.8, "大切にしたいこと", formula.get('values', {}).get('word', '')),
        (width/2 + r*1.55, cy + r*0.8, "得意なこと", formula.get('strengths', {}).get('word', '')),
        (width/2, cy - r*1.2, "好きなこと", formula.get('interests', {}).get('word', ''))
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
        draw_wrapped_text(c, word, cx, cy_pos - 8*mm, FONT_SANS, 24, 135*mm, 30, centered=True)
    
    c.setFont(FONT_SANS, 80)
    c.setFillColor(HexColor(COLORS['accent']))
    c.drawCentredString(width/2, cy + 5*mm, "×")

    c.setFont(FONT_SERIF, 36)
    c.setFillColor(HexColor(COLORS['pdf_text']))
    c.drawCentredString(width/2, height - 40*mm, f"「{json_data.get('catchphrase', '')}」")
    c.showPage()

    # P4: SENSE BALANCE
    draw_header(c, "03. 感性のバランス", 4)
    metrics = json_data.get('sense_metrics', [])
    y = height - 65*mm
    for i, m in enumerate(metrics[:8]):
        x = MARGIN_X + 25*mm if i < 4 else width/2 + 25*mm
        curr_y = y - (i % 4) * 24*mm
        draw_arrow_slider(c, x, curr_y, 48, m.get('left'), m.get('right'), m.get('value'))
    c.showPage()

    # P5: ROLE MODELS
    draw_header(c, "04. お手本にしたい人物", 5) 
    archs = json_data.get('artist_archetypes', [])
    y = height - 55*mm
    for i, a in enumerate(archs[:3]):
        c.setFont(FONT_SERIF, 22)
        c.setFillColor(HexColor(COLORS['forest']))
        c.drawString(MARGIN_X, y, f"◆ {a.get('name')}")
        c.setFillColor(HexColor(COLORS['pdf_text']))
        draw_wrapped_text(c, a.get('detail', ''), MARGIN_X + 8*mm, y - 12*mm, FONT_SANS, 14, 135*mm, 20)
        y -= 48*mm
    c.showPage()

    # P6: ROADMAP
    draw_header(c, "05. 未来への道のり", 6)
    steps = json_data.get('roadmap_steps', [])
    y = height - 65*mm
    
    for i, step in enumerate(steps):
        # 番号
        c.setFont(FONT_SANS, 40)
        c.setFillColor(HexColor(COLORS['accent']))
        c.drawString(MARGIN_X, y - 5*mm, f"0{i+1}")
        
        # タイトル
        TITLE_X = MARGIN_X + 25*mm
        c.setFont(FONT_SERIF, 18)
        c.setFillColor(HexColor(COLORS['pdf_text']))
        c.drawString(TITLE_X, y, step.get('title', ''))
        
        # 解説（タイトルの真下に配置、15文字改行）
        c.setFillColor(HexColor(COLORS['pdf_sub']))
        draw_wrapped_text(c, step.get('detail', ''), TITLE_X, y - 8*mm, FONT_SANS, 12, 135*mm, 18)
        
        y -= 45*mm
    c.showPage()

    # P7: VISION & ALTERNATIVES
    draw_header(c, "06. 次なるビジョンと表現", 7)
    COL_WIDTH = (CONTENT_WIDTH - 10*mm) / 2
    
    # Left
    c.setFont(FONT_SERIF, 20)
    c.setFillColor(HexColor(COLORS['forest']))
    c.drawString(MARGIN_X, height - 45*mm, "Next Vision")
    proposals = json_data.get('final_proposals', [])
    y = height - 60*mm
    for p in proposals[:5]:
        c.setFont(FONT_SANS, 14)
        c.setFillColor(HexColor(COLORS['pdf_text']))
        c.drawString(MARGIN_X, y, f"・{p.get('point')}")
        draw_wrapped_text(c, p.get('detail', ''), MARGIN_X + 5*mm, y - 8*mm, FONT_SANS, 11, 135*mm, 14)
        y -= 24*mm
        
    # Right
    RIGHT_START_X = width/2 + 10*mm # Center + 10mm
    c.setFont(FONT_SERIF, 20)
    c.setFillColor(HexColor(COLORS['forest']))
    c.drawString(RIGHT_START_X, height - 45*mm, "Other Expressions")
    alts = json_data.get('alternative_expressions', [])
    y_alt = height - 60*mm
    for alt in alts[:3]:
        c.setFont(FONT_SANS, 14)
        c.setFillColor(HexColor(COLORS['pdf_text']))
        draw_wrapped_text(c, f"◇ {alt}", RIGHT_START_X, y_alt, FONT_SANS, 14, 135*mm, 20)
        y_alt -= 30*mm
    
    c.showPage()

    # P8: MESSAGE
    image_url = "https://images.unsplash.com/photo-1495312040802-a929cd14a6ab?q=80&w=2940&auto=format&fit=crop"
    try:
        response = requests.get(image_url, stream=True, timeout=10)
        if response.status_code == 200:
            img_data = io.BytesIO(response.content)
            pil_img = Image.open(img_data)
            img_reader = ImageReader(pil_img)
            c.drawImage(img_reader, 0, 0, width=width, height=height, preserveAspectRatio=False)
            c.setFillColor(HexColor('#111111'))
            c.setFillAlpha(0.5)
            c.rect(0, 0, width, height, fill=1, stroke=0)
            c.setFillAlpha(1.0)
            TEXT_COLOR_END = HexColor('#F4F4F4')
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
    # 名言を中央配置、15文字改行、余白十分
    draw_wrapped_text(c, q_text, width/2, height/2 + 25*mm, FONT_SERIF, 28, 135*mm, 42, centered=True)
    c.setFont(FONT_SANS, 18)
    c.setFillColor(ACCENT_COLOR_END)
    c.drawCentredString(width/2, height/2 - 45*mm, f"- {q_author}")
    c.setFont(FONT_SANS, 12)
    c.setFillColor(TEXT_COLOR_END)
    c.drawRightString(width - MARGIN_X, 15*mm, "8 / 8")
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

# ==========================================
# 5. Pipeline Main Flow
# ==========================================
def render_web_result(data):
    st.markdown("---")
    st.caption("診断結果")
    st.title(f"『 {data.get('catchphrase')} 』")
    col1, col2 = st.columns([1, 1.5])
    with col1:
        st.markdown("### 感性のバランス")
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
        st.markdown("### 成功の方程式")
        f = data.get('formula', {})
        st.info(f"**大切にしたいこと**\n\n{f.get('values', {}).get('word')}")
        st.warning(f"**得意なこと**\n\n{f.get('strengths', {}).get('word')}")
        st.success(f"**好きなこと**\n\n{f.get('interests', {}).get('word')}")

if 'step' not in st.session_state: st.session_state.step = 1
if 'quiz_result' not in st.session_state: st.session_state.quiz_result = None
if 'uploaded_images' not in st.session_state: st.session_state.uploaded_images = []

# STEP 1
if st.session_state.step == 1:
    try: st.image("cover.jpg", use_container_width=True)
    except: pass
    st.title("世界観診断 | Visionary Analysis")
    st.caption("あなたの感性と才能を言語化する、クリエイティブ診断ツール")
    
    # === 修正箇所：視認性を高めたカスタムデザイン枠 ===
    st.markdown(f"""
    <div style="
        background-color: {COLORS['card']};
        border: 1px solid {COLORS['accent']};
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 25px;
        color: {COLORS['text']};
    ">
        <h4 style="color: {COLORS['accent']}; margin-top: 0; margin-bottom: 10px;">
            📝 事前にご用意いただくもの
        </h4>
        <p style="font-size: 1rem; line-height: 1.6;">
            診断の後半で、AIによる画像解析を行います。以下の画像をお手元にご準備の上、スタートしてください。
        </p>
        <ul style="margin-bottom: 0;">
            <li><b>現在地（原点）</b>: あなたの代表作、または今好きな写真（1〜3枚）</li>
            <li><b>理想（未来）</b>: これから目指したい世界観の画像（1〜3枚）</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    # ==================================
    
    st.markdown("##### 00. 得意＆好きな表現（※１つに絞ると精度が上がります）")
    specialty = st.text_input("例：写真、映像、絵画、身体表現（ダンス）、造形、デザイン、演技、など視覚的にわかるもの")
    
    st.markdown("##### 01. 感性チェック")
    st.write("直感で回答してください。あなたの創作の源泉を探ります。")
    with st.form(key='quiz_form'):
        answers = []
        for i, item in enumerate(QUIZ_DATA):
            ans = st.radio(
