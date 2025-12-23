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

# カラーパレット (v5.0: 寄り添うような温かみと知性を追加)
COLORS = {
    "bg": "#1E1E1E",        # より深いマットな黒
    "text": "#EAEAEA",      # 目に優しいオフホワイト
    "accent": "#D4AF37",    # 落ち着いたアンティークゴールド
    "sub": "#8FAAB5",       # 知性を感じるブルーグレー
    "forest": "#5F8D8B",    # 癒やしの深緑
    "card": "#2A2A2A",      # カード背景
    "input_bg": "#333333",  # 入力エリア
    "pdf_bg": "#F9F9F7",    # 紙の質感を模した生成り色
    "pdf_text": "#2A2A2A",  # 柔らかい墨色
    "pdf_sub": "#555555"    # グレー
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

# 管理用サイドバー（非表示推奨）
with st.sidebar:
    if st.checkbox("System Access", key="admin_mode"):
        admin_pass = st.text_input("Key", type="password")
        if admin_pass == st.secrets.get("ADMIN_PASSWORD", "admin123"):
            st.success(f"Status: {MODEL_STATUS}")
        else:
            st.stop()

# CSS適用（洗練されたUI）
st.markdown(f"""
<style>
    html, body, [class*="css"] {{
        font-family: "Hiragino Mincho ProN", "Yu Mincho", serif; /* 明朝体で情緒を演出 */
        background-color: {COLORS["bg"]};
        color: {COLORS["text"]};
        line-height: 1.8; /* 読みやすさ重視 */
    }}
    .stApp {{
        background-color: {COLORS["bg"]};
    }}
    h1, h2, h3 {{
        color: {COLORS["text"]} !important;
        font-weight: normal;
        letter-spacing: 0.1em;
    }}
    .stTextInput > div > div > input {{
        background-color: {COLORS["input_bg"]} !important;
        color: #FFF !important;
        border: 1px solid #555;
    }}
    /* ボタンの美学 */
    div.stButton > button {{
        background-color: {COLORS["sub"]};
        color: #1A1A1A;
        font-family: "Hiragino Sans", sans-serif;
        font-weight: bold;
        border: none;
        padding: 12px 30px;
        border-radius: 2px; /* 角を少しだけ丸める */
        letter-spacing: 0.05em;
        transition: all 0.4s ease;
    }}
    div.stButton > button:hover {{
        background-color: {COLORS["accent"]};
        color: #000;
        letter-spacing: 0.1em; /* ホバーで少し広がる演出 */
    }}
    div[data-testid="stForm"] {{
        background-color: {COLORS["card"]};
        padding: 40px;
        border-radius: 4px;
        border: 1px solid #444;
    }}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 1. 診断データ（設問：表現者の葛藤に寄り添う選定）
# ---------------------------------------------------------
QUIZ_DATA = [
    {"q": "Q1. 制作の衝動は、どこから生まれますか？", "opts": ["内側から湧き上がる、言葉にできない感情", "外側からの刺激や、解決すべき課題"], "type_a": "内側から湧き上がる、言葉にできない感情", "axis": "source"},
    {"q": "Q2. アイデアを形にする時、最初にするのは？", "opts": ["ノートの端に、意味のない線を走らせる", "白い紙に、構造やキーワードを書き出す"], "type_a": "ノートの端に、意味のない線を走らせる", "axis": "style"},
    {"q": "Q3. あなたにとって「色」とは？", "opts": ["その瞬間の「気分」や「匂い」に近いもの", "計算された「記号」や「機能」に近いもの"], "type_a": "その瞬間の「気分」や「匂い」に近いもの", "axis": "style"},
    {"q": "Q4. 理想的な制作スペースは？", "opts": ["好きな物に囲まれた、少し混沌とした秘密基地", "ノイズのない、整理整頓された実験室"], "type_a": "好きな物に囲まれた、少し混沌とした秘密基地", "axis": "style"},
    {"q": "Q5. 制作のリズムについて。", "opts": ["波が来た時に一気に。乗らない時は何もしない。", "毎日淡々と。ルーティンを守り積み上げる。"], "type_a": "波が来た時に一気に。乗らない時は何もしない。", "axis": "source"},
    {"q": "Q6. 行き詰まった時、どうしますか？", "opts": ["全く関係ない映画を観たり、旅に出る", "原因を分析し、基礎練習やリサーチに戻る"], "type_a": "全く関係ない映画を観たり、旅に出る", "axis": "source"},
    {"q": "Q7. 作品の「完成」を告げる合図は？", "opts": ["「もうこれ以上触れない」という生理的な感覚", "「予定していた要件を満たした」という論理的な判断"], "type_a": "「もうこれ以上触れない」という生理的な感覚", "axis": "style"},
    {"q": "Q8. 評価に対するスタンスは？", "opts": ["誰にも理解されなくても、自分が愛せればいい", "多くの人に届き、共感されることが喜び"], "type_a": "誰にも理解されなくても、自分が愛せればいい", "axis": "source"},
    {"q": "Q9. 制作中に突然、別のアイデアが降ってきたら？", "opts": ["今の作業を放り出してでも、その光を追いかける", "まずは今の作品を完成させてから、次に着手する"], "type_a": "今の作業を放り出してでも、その光を追いかける", "axis": "style"},
    {"q": "Q10. 道具選びで大切なのは？", "opts": ["手に馴染む感覚や、愛着が湧くかどうか", "スペックの高さや、効率的かどうか"], "type_a": "手に馴染む感覚や、愛着が湧くかどうか", "axis": "style"},
    {"q": "Q11. 作品を通して、何を共有したい？", "opts": ["私の内側にある、言葉にならない「叫び」", "社会に対する、より良い「提案」"], "type_a": "私の内側にある、言葉にならない「叫び」", "axis": "source"},
    {"q": "Q12. ラフスケッチはどんな感じ？", "opts": ["抽象的な線や、雰囲気の断片が多い", "具体的な配置図や、完成予想図に近い"], "type_a": "抽象的な線や、雰囲気の断片が多い", "axis": "style"},
    {"q": "Q13. 惹かれるのはどんなアーティスト？", "opts": ["破天荒で、危うさを秘めた天才肌", "知的で、理論に裏打ちされた構築家"], "type_a": "破天荒で、危うさを秘めた天才肌", "axis": "source"},
    {"q": "Q14. 「締め切り」との付き合い方は？", "opts": ["ギリギリまで粘って、クオリティを上げたい", "余裕を持って終わらせ、安心したい"], "type_a": "ギリギリまで粘って、クオリティを上げたい", "axis": "style"},
    {"q": "Q15. チームでの制作は？", "opts": ["自分のリズムが乱れるので、実は苦手", "役割分担ができるので、効率的で好き"], "type_a": "自分のリズムが乱れるので、実は苦手", "axis": "source"},
    {"q": "Q16. 昔の自分の作品を見ると？", "opts": ["その時の「感情」や「匂い」が蘇る", "技術的な「未熟さ」や「粗」が気になる"], "type_a": "その時の「感情」や「匂い」が蘇る", "axis": "style"},
    {"q": "Q17. 新しい技術を学ぶ理由は？", "opts": ["表現したかった「あのイメージ」に近づけるから", "仕事の幅が広がり、有利になるから"], "type_a": "表現したかった「あのイメージ」に近づけるから", "axis": "source"},
    {"q": "Q18. 制作中のBGMは？", "opts": ["感情を増幅させる曲を、大音量で", "集中を妨げない環境音か、無音"], "type_a": "感情を増幅させる曲を、大音量で", "axis": "style"},
    {"q": "Q19. タイトルの付け方は？", "opts": ["詩的で、余白のある言葉を選ぶ", "中身が伝わる、的確な言葉を選ぶ"], "type_a": "詩的で、余白のある言葉を選ぶ", "axis": "style"},
    {"q": "Q20. SNSで発信したいのは？", "opts": ["完成された「世界観」だけを見せたい", "制作過程や、日々の思考もシェアしたい"], "type_a": "完成された「世界観」だけを見せたい", "axis": "source"},
    {"q": "Q21. 批判的な言葉を受け取ったら？", "opts": ["心が痛み、感情的に反発してしまう", "冷静に分析し、改善点として受け止める"], "type_a": "心が痛み、感情的に反発してしまう", "axis": "source"},
    {"q": "Q22. 自分の作風を一言で言うと？", "opts": ["エモーショナルで、感覚的", "ロジカルで、機能的"], "type_a": "エモーショナルで、感覚的", "axis": "style"},
    {"q": "Q23. 目標の立て方は？", "opts": ["大きな「夢」や「ビジョン」を描く", "具体的な「数値」や「ステップ」を決める"], "type_a": "大きな「夢」や「ビジョン」を描く", "axis": "source"},
    {"q": "Q24. インプットの方法は？", "opts": ["直感的に気になったものを、深く掘り下げる", "体系的に、幅広く情報をチェックする"], "type_a": "直感的に気になったものを、深く掘り下げる", "axis": "style"},
    {"q": "Q25. 失敗作はどうしますか？", "opts": ["見たくないので、勢いで捨ててしまう", "分析のために、大切に保管しておく"], "type_a": "見たくないので、勢いで捨ててしまう", "axis": "style"},
    {"q": "Q26. 影響を受けやすいのは？", "opts": ["自然、音楽、夢などの「体験」", "本、論文、ニュースなどの「情報」"], "type_a": "自然、音楽、夢などの「体験」", "axis": "source"},
    {"q": "Q27. 制作において重要なのは？", "opts": ["「何を」描くか（魂・主題）", "「どう」描くか（技術・構成）"], "type_a": "「何を」描くか（魂・主題）", "axis": "style"},
    {"q": "Q28. 答えのない問題に直面したら？", "opts": ["自分の「直感」を信じて突破する", "要素を「分解」して解決策を探る"], "type_a": "自分の「直感」を信じて突破する", "axis": "style"},
    {"q": "Q29. 完璧主義についてどう思う？", "opts": ["完成していなくても、魂がこもっていればいい", "細部まで完璧でなければ、出す意味がない"], "type_a": "完成していなくても、魂がこもっていればいい", "axis": "style"},
    {"q": "Q30. あなたにとって表現とは？", "opts": ["生きることそのもの。呼吸と同じ。", "社会と関わるための、有効な手段。"], "type_a": "生きることそのもの。呼吸と同じ。", "axis": "source"},
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
    msg['Subject'] = "【Aesthetic Archive】美の公文書をお届けします"
    msg.attach(MIMEText("あなたの美意識の解析結果をお届けします。\n\nThom Yoshida", 'plain'))
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
# 3. PDF生成ロジック（読みやすさ特化：20文字改行）
# ---------------------------------------------------------
def wrap_text_smart(text, max_char_count):
    if not text: return []
    # 読みやすさのための改行ルール
    delimiters = ['、', '。', '！', '？', '」', '）', '…', '・']
    lines = []
    current_line = ""
    for char in text:
        current_line += char
        # 20文字前後で、かつ区切りの良い文字が来たら改行
        if len(current_line) >= max_char_count * 0.9: 
            if char in delimiters:
                lines.append(current_line)
                current_line = ""
                continue
            # 上限を超えたら強制改行
            if len(current_line) >= max_char_count:
                lines.append(current_line)
                current_line = ""
    if current_line: lines.append(current_line)
    return lines

def draw_wrapped_text(c, text, x, y, font, size, max_width_mm, leading, centered=False):
    c.setFont(font, size)
    # 文字幅計算 (日本語等幅フォント前提)
    char_width_mm = size * 0.352 
    # max_width_mm から算出した文字数制限を使用
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
    
    # 20文字程度で改行させるための狭い幅設定 (フォントサイズによるが約80-90mm)
    NARROW_WIDTH_MM = 85 * mm 

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

    # P2: Keywords (整理された世界観)
    draw_header(c, "01. 世界観の座標（原点と未来）", 2)
    c.setFont(FONT_SERIF, 22)
    c.setFillColor(HexColor(COLORS['pdf_sub']))
    c.drawCentredString(width/3, height - 55*mm, "ORIGIN (過去・原点)")
    past_kws = json_data.get('twelve_past_keywords', [])
    y = height - 75*mm
    c.setFont(FONT_SANS, 11)
    for kw in past_kws[:12]:
        c.drawCentredString(width/3, y, f"◇ {kw}")
        y -= 9.5*mm
    
    c.setFont(FONT_SANS, 50)
    c.setFillColor(HexColor(COLORS['accent']))
    c.drawCentredString(width/2, height/2 - 15*mm, "→")

    c.setFont(FONT_SERIF, 30)
    c.setFillColor(HexColor(COLORS['forest']))
    c.drawCentredString(width*2/3, height - 55*mm, "VISION (未来・理想)")
    future_kws = json_data.get('twelve_future_keywords', [])
    y = height - 75*mm
    c.setFont(FONT_SANS, 16)
    c.setFillColor(HexColor(COLORS['pdf_text']))
    for kw in future_kws[:12]:
        c.drawCentredString(width*2/3, y, f"◆ {kw}")
        y -= 9.5*mm
    c.showPage()

    # P3: Formula (整頓された成功法則)
    draw_header(c, "02. あなただけの成功法則", 3)
    formula = json_data.get('formula', {})
    cy = height/2 - 10*mm
    r = 38*mm 
    positions = [
        (width/2 - r*1.55, cy + r*0.8, "価値観 (Values)", formula.get('values', {}).get('word', '')),
        (width/2 + r*1.55, cy + r*0.8, "強み (Strengths)", formula.get('strengths', {}).get('word', '')),
        (width/2, cy - r*1.2, "好き (Interests)", formula.get('interests', {}).get('word', ''))
    ]
    for cx, cy_pos, title, word in positions:
        c.setStrokeColor(HexColor(COLORS['forest']))
        c.setFillColor(HexColor('#FFFFFF'))
        c.setLineWidth(1.5)
        c.circle(cx, cy_pos, r, fill=1, stroke=1)
        c.setFont(FONT_SERIF, 16)
        c.setFillColor(HexColor(COLORS['pdf_sub']))
        c.drawCentredString(cx, cy_pos + 12*mm, title) 
        c.setFont(FONT_SANS, 22)
        c.setFillColor(HexColor(COLORS['pdf_text']))
        # ここも20文字程度で折り返し
        draw_wrapped_text(c, word, cx, cy_pos - 8*mm, FONT_SANS, 22, r*1.6, 28, centered=True)
    
    c.setFont(FONT_SANS, 80)
    c.setFillColor(HexColor(COLORS['accent']))
    c.drawCentredString(width/2, cy + 5*mm, "×")
    
    # キャッチコピー
    c.setFont(FONT_SERIF, 32)
    c.setFillColor(HexColor(COLORS['pdf_text']))
    c.drawCentredString(width/2, height - 40*mm, f"「{json_data.get('catchphrase', '')}」")
    c.showPage()

    # P4: Metrics
    draw_header(c, "03. 感性のバランス", 4)
    metrics = json_data.get('sense_metrics', [])
    y = height - 65*mm
    for i, m in enumerate(metrics[:8]):
        x = MARGIN_X + 25*mm if i < 4 else width/2 + 25*mm
        curr_y = y - (i % 4) * 24*mm
        draw_arrow_slider(c, x, curr_y, 48, m.get('left'), m.get('right'), m.get('value'))
    c.showPage()

    # P5: Role Models (20文字改行・寄り添う解説)
    draw_header(c, "04. 導きとなるロールモデル", 5) 
    archs = json_data.get('artist_archetypes', [])
    y = height - 55*mm
    for i, a in enumerate(archs[:3]):
        c.setFont(FONT_SERIF, 22)
        c.setFillColor(HexColor(COLORS['forest']))
        c.drawString(MARGIN_X, y, f"◆ {a.get('name')}")
        
        c.setFillColor(HexColor(COLORS['pdf_text']))
        # NARROW_WIDTH_MM を使用して約20文字で改行させる
        draw_wrapped_text(c, a.get('detail', ''), MARGIN_X + 8*mm, y - 12*mm, FONT_SANS, 13, NARROW_WIDTH_MM, 20)
        y -= 48*mm
    c.showPage()

    # P6: Roadmap (20文字改行・整理されたステップ)
    draw_header(c, "05. 美意識を磨くステップ", 6)
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
        # NARROW_WIDTH_MM を使用
        draw_wrapped_text(c, step.get('detail', ''), MARGIN_X + 30*mm, y - 12*mm, FONT_SANS, 12, NARROW_WIDTH_MM, 18)
        y -= 45*mm
    c.showPage()

    # P7: Next Vision
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
        # NARROW_WIDTH_MM を使用
        draw_wrapped_text(c, p.get('detail', ''), MARGIN_X + 5*mm, y - 6*mm, FONT_SANS, 11, NARROW_WIDTH_MM, 14)
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
        draw_wrapped_text(c, f"◇ {alt}", x_right, y_alt, FONT_SANS, 14, NARROW_WIDTH_MM, 20)
        y_alt -= 30*mm
    c.showPage()

    # P8: Quote (贈る言葉)
    try:
        # 画像があれば背景にする
        c.drawImage("cover.jpg", 0, 0, width=width, height=height, preserveAspectRatio=False)
        c.setFillColor(HexColor('#111111'))
        c.setFillAlpha(0.6) # 少し濃くして文字を読みやすく
        c.rect(0, 0, width, height, fill=1, stroke=0)
        c.setFillAlpha(1.0)
        TEXT_COLOR_END = HexColor('#F4F4F4')
        ACCENT_COLOR_END = HexColor(COLORS['accent'])
    except:
        draw_header(c, "07. 贈る言葉", 8)
        TEXT_COLOR_END = HexColor(COLORS['pdf_text'])
        ACCENT_COLOR_END = HexColor(COLORS['forest'])

    quote_data = json_data.get('inspiring_quote', {})
    q_text = quote_data.get('text', '')
    q_author = quote_data.get('author', '')

    c.setFillColor(TEXT_COLOR_END)
    # 中央揃えで20文字程度改行
    STRICT_WIDTH_P8 = 180 * mm # 中央配置用に少し広めに取るが、文字サイズ大で調整
    draw_wrapped_text(c, q_text, width/2, height/2 + 20*mm, FONT_SERIF, 26, STRICT_WIDTH_P8, 36, centered=True)
    
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
# 4. Pipeline Main Flow (UI: 寄り添う言葉選び)
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
            line_color=COLORS['accent'], fillcolor='rgba(212, 175, 55, 0.3)'
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
        st.write("あなたの混沌とした世界観を、3つの言葉に整理しました。")
        f = data.get('formula', {})
        st.info(f"**価値観 (Values)**\n\n{f.get('values', {}).get('word')}\n\n*{f.get('values', {}).get('detail')}*")
        st.warning(f"**強み (Strengths)**\n\n{f.get('strengths', {}).get('word')}\n\n*{f.get('strengths', {}).get('detail')}*")
        st.success(f"**好き (Interests)**\n\n{f.get('interests', {}).get('word')}\n\n*{f.get('interests', {}).get('detail')}*")

if 'step' not in st.session_state: st.session_state.step = 1
if 'quiz_result' not in st.session_state: st.session_state.quiz_result = None
if 'uploaded_images' not in st.session_state: st.session_state.uploaded_images = []
if 'axis_scores' not in st.session_state: st.session_state.axis_scores = {"source": 0, "style": 0}

# STEP 1
if st.session_state.step == 1:
    try: st.image("cover.jpg", use_container_width=True)
    except: pass
    st.title("Aesthetic DNA Analysis")
    st.caption("混沌とした思考を、美学へと整理する時間。正解はありません。")
    st.markdown("##### 00. YOUR SPECIALTY")
    specialty = st.text_input("あなたの専門分野・表現媒体（例：写真、建築、言葉）")
    st.markdown("##### 01. SENSE CHECK")
    st.write("直感で選んでください。迷ったら、心がざわつく方へ。")
    with st.form(key='quiz_form'):
        answers = []
        for i, item in enumerate(QUIZ_DATA):
            ans = st.radio(item["q"], item["opts"], key=f"q{i}", horizontal=True, index=None)
            answers.append((ans, item["type_a"], item.get("axis", "style")))
        st.write("---")
        # ボタン名の最適化：没入への誘い
        submit_button = st.form_submit_button(label="美意識の源泉へ潜る")
    
    if submit_button:
        if not specialty: st.warning("専門分野を教えてください。")
        elif any(a[0] is None for a in answers): st.error("すべての問いに、直感で答えてください。")
        else:
            st.session_state.specialty = specialty
            
            # --- 集計ロジック (変更なし) ---
            score_source = 0 
            score_style = 0  
            count_source = 0
            count_style = 0

            for ans, type_a_val, axis in answers:
                if axis == "source":
                    count_source += 1
                    if ans == type_a_val: score_source += 1
                else:
                    count_style += 1
                    if ans == type_a_val: score_style += 1
            
            pct_source = int((score_source / count_source) * 100) if count_source > 0 else 0
            pct_style = int((score_style / count_style) * 100) if count_style > 0 else 0
            
            st.session_state.axis_scores = {"source": pct_source, "style": pct_style}

            # --- アーキタイプ判定 ---
            if pct_source >= 50 and pct_style >= 50:
                archetype = "【深淵の詩人 (The Abyssal Poet)】\n内向的 × 抽象的\n（孤独を愛し、言葉にならない感情を掬い上げる）"
            elif pct_source >= 50 and pct_style < 50:
                archetype = "【静寂の建築家 (The Silent Architect)】\n内向的 × 具体的\n（内なるこだわりを、完璧な技術と静寂で形にする）"
            elif pct_source < 50 and pct_style >= 50:
                archetype = "【太陽の扇動者 (The Solar Agitator)】\n外向的 × 抽象的\n（情熱で大衆を巻き込み、熱狂の渦を生む）"
            else:
                archetype = "【鋼の戦略家 (The Steel Strategist)】\n外向的 × 具体的\n（市場の声を聴き、最適解を導き出す）"
            
            st.session_state.quiz_result = archetype
            st.session_state.step = 2
            st.rerun()

# STEP 2
elif st.session_state.step == 2:
    st.header("02. VISION INTEGRATION")
    st.info(f"Archetype: **{st.session_state.quiz_result}**")
    st.caption("あなたの「原点」と「未来」をつなぎ合わせます。")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### あなたの原点 (Origin)")
        st.caption("過去の作品や、影響を受けた風景など")
        past_files = st.file_uploader("Upload (Max 3)", type=["jpg", "png"], accept_multiple_files=True, key="past")
    with col2:
        st.markdown("#### 未来のビジョン (Vision)")
        st.caption("理想とするイメージや、憧れの景色など")
        future_files = st.file_uploader("Upload (Max 3)", type=["jpg", "png"], accept_multiple_files=True, key="future")
    
    # ボタン名の最適化：接続への誘い
    if st.button("過去と未来を接続（リンク）する"):
        if not past_files:
            st.error("分析精度を高めるため、少なくとも1枚の画像をアップロードしてください。")
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
        st.markdown(f"""<div style="background-color: {COLORS['card']}; padding: 30px; border-radius: 4px; border-left: 4px solid {COLORS['accent']}; text-align: left;"><h3 style="color: {COLORS['accent']}; margin:0;">Analysis Ready</h3><p style="margin-top:10px;">あなたの美意識の構造解析が完了しました。<br>このレポートが、迷いの中にあるあなたの道標となりますように。</p></div><br>""", unsafe_allow_html=True)
        with st.form("lead_capture"):
            col_f1, col_f2 = st.columns(2)
            with col_f1: user_name = st.text_input("Name")
            with col_f2: user_email = st.text_input("Email")
            # ボタン名の最適化：解読への誘い
            submit = st.form_submit_button("Aesthetic DNA を解読する", type="primary")
            if submit:
                if user_name and user_email:
                    st.session_state.user_name = user_name
                    st.session_state.user_email = user_email
                    save_to_google_sheets(user_name, user_email, st.session_state.specialty, st.session_state.quiz_result)
                    st.session_state.step = 4
                    st.rerun()
                else: st.warning("お名前とメールアドレスを入力してください。")

# STEP 4 (AI Execution & PDF Generation)
elif st.session_state.step == 4:
    if "analysis_data" not in st.session_state:
        with st.spinner("Connecting to Visionary Core... 混沌を整理し、美学を編集中..."):
            
            success = False
            
            # --- AI Logic (プロンプト：寄り添い・整理整頓・読みやすさ) ---
            if "GEMINI_API_KEY" in st.secrets:
                prompt_text = f"""
                あなたは世界的なアートディレクターであり、表現者の孤独な心に寄り添うメンター Thom Yoshida です。
                ユーザーの「専門分野」と「アーキタイプ」に基づき、彼らの混沌とした世界観を「整理整頓」し、
                背中を押すような温かい診断レポートJSONを作成してください。

                【ユーザー情報】
                - 専門分野: {st.session_state.specialty}
                - 診断アーキタイプ: {st.session_state.quiz_result}
                
                【必須トーン＆マナー】
                - **寄り添い**: 否定せず、迷いを肯定する。
                - **整理整頓**: 複雑な思考を、シンプルで美しい言葉に要約する。
                - **詩的**: 機能的な言葉ではなく、心に響く言葉を選ぶ。

                【必須出力JSON構造】
                {{
                    "catchphrase": "その人の混沌を一言で美学に変える、詩的なキャッチコピー(15文字以内)",
                    "twelve_past_keywords": ["{st.session_state.quiz_result}の原点にある、ノスタルジックな単語12個"],
                    "twelve_future_keywords": ["{st.session_state.quiz_result}が目指すべき、希望の単語12個"],
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
                        "values": {{"word": "価値観の核", "detail": "なぜそれを大切にすべきか、優しく解説(20文字×2行程度)"}},
                        "strengths": {{"word": "唯一無二の武器", "detail": "その武器がどう世界を変えるか、勇気づける解説(20文字×2行程度)"}},
                        "interests": {{"word": "魂の栄養源", "detail": "どんな時に心が満たされるか、整理した解説(20文字×2行程度)"}}
                    }},
                    "roadmap_steps": [
                        {{"title": "Stepタイトル", "detail": "無理なく進めるための、優しい具体的ステップ(20文字×3行程度)"}} を3つ
                    ],
                    "artist_archetypes": [
                        {{"name": "ロールモデル名", "detail": "その人の生き方がどう参考になるか(20文字×3行程度)"}} を3名
                    ],
                    "final_proposals": [
                        {{"point": "ビジョン要点", "detail": "詳細(20文字×2行程度)"}} を5つ
                    ],
                    "alternative_expressions": [
                        "今の表現に行き詰まった時の、別のアプローチ" を3つ
                    ],
                    "inspiring_quote": {{
                        "text": "迷える表現者の心を救う、偉人の名言（日本語訳）",
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

            # --- Force Completion (Fallback) ---
            if not success:
                st.warning("⚠️ AIサーバーが混雑しているため、デモモードでレポートを生成しました。")
                data = {
                    "catchphrase": "静寂の中で、光を編む。", 
                    "twelve_past_keywords": ["孤独", "雨音", "図書室", "秘密", "灰色", "硝子", "深海", "ノイズ", "記憶", "フィルム", "余白", "迷路"],
                    "twelve_future_keywords": ["共鳴", "灯火", "夜明け", "確信", "透明", "呼吸", "星座", "純度", "解放", "調和", "波紋", "飛翔"],
                    "sense_metrics": [{"left": "Logic", "right": "Emotion", "value": 80}] * 8,
                    "formula": {"values": {"word": "内なる静寂", "detail": "外の喧騒を遮断し、自分の声を聞く時間。それがあなたの創造の源です。"}, "strengths": {"word": "繊細な観察眼", "detail": "他人が見落とす微細な変化に気づく力。それは弱さではなく、最強の武器です。"}, "interests": {"word": "儚いものの美", "detail": "消えゆくもの、移ろうものへの愛着。そこに永遠の価値を見出しています。"}},
                    "roadmap_steps": [{"title": "Step 1: 孤独の確保", "detail": "1日15分、誰とも繋がらない時間を持ってください。"}, {"title": "Step 2: 感情の言語化", "detail": "モヤモヤした感情に、自分だけの名前をつけてみましょう。"}, {"title": "Step 3: 小さな発信", "detail": "完成していなくても、断片を見せるだけで誰かが救われます。"}],
                    "artist_archetypes": [{"name": "ソール・ライター", "detail": "野心を持たず、窓ガラス越しの日常を愛した写真家。静かな視点の参考に。"}],
                    "final_proposals": [{"point": "自分のペースを守る", "detail": "速さよりも深さを大切に。"}],
                    "alternative_expressions": ["写真と言葉", "アンビエント音楽"],
                    "inspiring_quote": {"text": "重要なのは、何を撮るかではなく、何を感じるかだ。", "author": "Andre Kertesz"}
                }

            st.session_state.analysis_data = data
            pdf_buffer = create_pdf(data)
            is_sent = send_email_with_pdf(st.session_state.user_email, pdf_buffer)
            st.session_state.email_sent_status = is_sent
            st.rerun()
    else:
        data = st.session_state.analysis_data
        render_web_result(data)
        st.markdown("### Report Delivered")
        if st.session_state.get("email_sent_status", False):
            st.success(f"📩 {st.session_state.user_email} に美の公文書を送信しました。")
        else:
            st.warning("⚠️ レポート作成完了（メール送信失敗：設定を確認してください）")
        
        pdf_buffer = create_pdf(data)
        # ボタン名の最適化：保存への誘い
        st.download_button("📥 分析レポート（美の公文書）を保存", pdf_buffer, "Aesthetic_Analysis.pdf", "application/pdf")
        
        # ボタン名の最適化：リセットへの誘い
        if st.button("意識をフラットに戻す"):
            st.session_state.clear()
            st.rerun()
