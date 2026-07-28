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
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

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
st.set_page_config(page_title="世界観診断 | Visionary Analysis", layout="centered")

# デザイン定義 (COLORS - Brand-Core Aligned v6.0)
COLORS = {
    "bg": "#2B2723",         # --ink
    "text": "#F5F5F5",       # --off-white
    "accent": "#D6AE60",     # --gold
    "sub": "#7A96A0",        # --blue
    "forest": "#D1C0AF",     # --beige（変数名は維持・値のみ変更）
    "card": "#332D27",
    "card_hover": "#3D362F",
    "input_bg": "#3A342E",
    "pdf_bg": "#FAFAF8",
    "pdf_text": "#2C2C2C",
    "pdf_sub": "#555555",
    "button_active": "#D6AE60",
    "button_text_active": "#2B2723"
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

# ---------------------------------------------------------
# 1. デザインCSS（視認性強化・フローティングボタン版）
# ---------------------------------------------------------
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Zen+Old+Mincho:wght@400;500;600;700&display=swap');

    /* ベース設定 */
    html, body, [class*="css"] {{
        font-size: 18px;
        background-color: {COLORS["bg"]};
        color: {COLORS["text"]};
        font-family: "Zen Old Mincho", "Hiragino Mincho ProN", "Hiragino Kaku Gothic ProN", "Meiryo", serif;
    }}
    .stApp {{ background-color: {COLORS["bg"]}; }}
    
    /* 見出し設定 */
    h1, h2, h3, h4, h5 {{
        font-family: "Zen Old Mincho", "Hiragino Mincho ProN", serif !important;
        color: {COLORS["text"]} !important;
        letter-spacing: 0.05em;
    }}

    /* テキストカラー調整 */
    .stMarkdown p, .stTextInput label, .stSelectbox label, .stRadio label {{
        color: {COLORS["text"]} !important;
        opacity: 0.95;
    }}
    
    /* ラジオボタンのパネル化CSS */
    div[role="radiogroup"] {{
        background-color: transparent;
        border: none;
    }}
    div[role="radiogroup"] > label {{
        background-color: {COLORS["card"]} !important;
        padding: 15px 20px !important;
        border-radius: 8px !important;
        margin-bottom: 10px !important;
        border: 1px solid #6b6259 !important;
        transition: all 0.2s ease !important;
        cursor: pointer !important;
        display: flex !important;
        align-items: center !important;
        width: 100% !important;
    }}
    div[role="radiogroup"] > label:hover {{
        background-color: {COLORS["card_hover"]} !important;
        border-color: {COLORS["accent"]} !important;
        transform: translateY(-2px);
    }}
    div[role="radiogroup"] > label[data-baseweb="radio"] {{
        background-color: {COLORS["button_active"]} !important;
        border-color: {COLORS["button_active"]} !important;
    }}
    /* 選択された時のテキスト色調整 */
    div[role="radiogroup"] > label[data-baseweb="radio"] div[data-testid="stMarkdownContainer"] p {{
        color: {COLORS["button_text_active"]} !important;
    }}

    div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p {{
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        margin: 0 !important;
        padding-left: 5px;
    }}

    /* ─────────────────────────────────────────
       選択肢の視認性強化（包括的な上書き）
       Streamlitの内部DOM構造の差異に依存しないよう、
       ラベル内の全てのテキスト要素に対して明示的に
       高コントラストの文字色を強制する。
       ───────────────────────────────────────── */
    div[role="radiogroup"] label,
    div[role="radiogroup"] label p,
    div[role="radiogroup"] label span,
    div[role="radiogroup"] label div {{
        color: {COLORS["text"]} !important;
    }}
    div[role="radiogroup"] > label[data-baseweb="radio"] p,
    div[role="radiogroup"] > label[data-baseweb="radio"] span,
    div[role="radiogroup"] > label[data-baseweb="radio"] div {{
        color: {COLORS["button_text_active"]} !important;
        font-weight: 700 !important;
    }}
    /* ラジオの丸アイコン自体の視認性（未選択時のリング色） */
    div[role="radiogroup"] label div[data-baseweb="radio"] > div:first-child {{
        border-color: {COLORS["sub"]} !important;
        background-color: transparent !important;
    }}
    /* selectbox（プルダウン）本体・ポップアップ双方の文字色 */
    div[data-baseweb="select"] * {{
        color: {COLORS["text"]} !important;
    }}
    ul[data-baseweb="menu"] {{
        background-color: {COLORS["card"]} !important;
    }}
    ul[data-baseweb="menu"] li {{
        color: {COLORS["text"]} !important;
    }}
    ul[data-baseweb="menu"] li:hover {{
        background-color: {COLORS["card_hover"]} !important;
    }}

    /* Domain選択エリアの装飾 */
    .domain-box {{
        background-color: {COLORS["card"]};
        border: 1px solid {COLORS["forest"]};
        border-radius: 12px;
        padding: 25px;
        margin-bottom: 30px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }}
    .domain-title {{
        color: {COLORS["forest"]};
        font-size: 1.3rem;
        font-weight: bold;
        margin-bottom: 10px;
        border-bottom: 1px solid #555;
        padding-bottom: 10px;
    }}

    /* 入力フォーム */
    .stTextInput > div > div > input, .stSelectbox > div > div > div {{
        background-color: {COLORS["input_bg"]} !important;
        color: {COLORS["text"]} !important; 
        border: 1px solid #666 !important;
    }}
    
    /* ボタン */
    div.stButton > button {{
        background-color: {COLORS["accent"]};
        color: {COLORS["bg"]};
        font-weight: bold;
        border: none;
        padding: 15px 30px;
        border-radius: 8px;
        font-size: 1.2rem;
        width: 100%;
        margin-top: 20px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.5);
    }}
    div.stButton > button:hover {{
        background-color: {COLORS["text"]};
        color: {COLORS["bg"]};
        box-shadow: 0 6px 14px rgba(0,0,0,0.7);
    }}

    /* --- 浮き上がるボタン（Floating CTA） --- */
    .floating-cta {{
        position: fixed;
        bottom: 30px;
        right: 30px;
        background: linear-gradient(135deg, #D6AE60 0%, #F4D03F 100%); 
        color: {COLORS["bg"]} !important;
        padding: 18px 30px;
        border-radius: 50px;
        box-shadow: 0 10px 25px rgba(214, 174, 96, 0.4); 
        text-decoration: none;
        font-weight: bold;
        font-size: 1.1rem;
        z-index: 9999; 
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
        display: flex;
        align-items: center;
        gap: 10px;
        border: 1px solid rgba(255,255,255,0.2);
    }}
    
    .floating-cta:hover {{
        transform: translateY(-5px) scale(1.05);
        box-shadow: 0 15px 35px rgba(214, 174, 96, 0.6);
        color: {COLORS["bg"]} !important;
    }}

    /* スマホ用メディアクエリ */
    @media (max-width: 640px) {{
        html, body, [class*="css"] {{
            font-size: 16px !important;
        }}
        h1 {{
            font-size: 1.8rem !important;
        }}
        div[role="radiogroup"] > label {{
            padding: 12px 15px !important;
        }}
        .floating-cta {{
            bottom: 20px;
            right: 20px;
            padding: 15px 25px;
            font-size: 0.95rem;
        }}
    }}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. 定義データ
# ---------------------------------------------------------

# 領域定義（階層構造データ）
DOMAIN_HIERARCHY = {
    "📸 写真・カメラ (Optics)": {
        "description": "レンズ越しに「光」と「一瞬」を切り取る表現",
        "sub_categories": [
            "人物を撮る (ポートレート・宣材)",
            "服・ブランドを撮る (ファッション・ルックブック)",
            "景色・街を撮る (風景・スナップ・建築写真)",
            "モノ・商品を撮る (物撮り・テーブルフォト)",
            "作品として撮る (アート・抽象写真)",
            "日常を残す (家族・子供・ウェディング)"
        ]
    },
    "🎥 映像・動画 (Timeline)": {
        "description": "時間の流れを編集し、「物語」を紡ぐ表現",
        "sub_categories": [
            "音楽を描く (MV・ミュージックビデオ)",
            "映画・ドラマを作る (シネマティック・自主制作)",
            "日常・記録を残す (Vlog・ドキュメンタリー)",
            "異世界を作る (CG・アニメーション・モーショングラフィックス)",
            "短く伝える (リール・TikTok・広告動画)",
            "演出・構成をする (映像監督・演出家)"
        ]
    },
    "🎨 絵・デザイン・食・住 (Matter)": {
        "description": "色や素材を使って、無から「空間」や「体験」を生み出す表現",
        "sub_categories": [
            "体験・画面を作る (Webデザイン・UI/UX・LP)",
            "装い・身体装飾 (衣装・ヘアメイク・ネイル・ボディペイント)",
            "平面のデザイン (グラフィック・ロゴ・広告)",
            "素材・立体 (プロダクト・工芸・テキスタイル)",
            "空間のデザイン (建築・インテリア・舞台美術)",
            "食・香りの表現 (料理人・パティシエ・バリスタ・調香師)" 
        ]
    },
    "💃 身体・演技・音 (Somatic)": {
        "description": "自分自身の「身体」や「声」を媒体とする表現",
        "sub_categories": [
            "役を演じる (俳優・役者・キャスト)",
            "被写体になる (モデル・インフルエンサー)",
            "身体で表現する (ダンス・舞踏・パフォーマー)",
            "音・声を奏でる (音楽家・DJ・声優・ナレーター)"
        ]
    },
    "✒️ 言葉・論理・ビジネス (Context)": {
        "description": "言葉・論理・概念で、「意味」や「仕組み」を定義する表現",
        "sub_categories": [
            "仕組みを構築する (SE・エンジニア・研究者・医師)", 
            "全体を導く (ディレクション・経営者・起業家)", 
            "文章を書く (執筆・脚本・コピーライティング)",
            "価値を作る (ブランディング・事業開発)",
            "世界観を広める (広報・SNS運用・マーケティング)"
        ]
    }
}

# 診断用質問
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

# --- Drive Upload Function ---
def upload_to_drive(pdf_buffer, filename):
    if "gcp_service_account" not in st.secrets or "DRIVE_FOLDER_ID" not in st.secrets:
        return None
    
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        if "type" not in creds_dict:
             try:
                 creds_dict = json.loads(st.secrets["gcp_service_account"])
             except: pass

        scope = ['https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        
        service = build('drive', 'v3', credentials=creds)
        
        file_metadata = {
            'name': filename,
            'parents': [st.secrets["DRIVE_FOLDER_ID"]]
        }
        
        media = MediaIoBaseUpload(pdf_buffer, mimetype='application/pdf')
        
        file = service.files().create(
            body=file_metadata, 
            media_body=media, 
            fields='id, webViewLink'
        ).execute()
        
        return file.get('webViewLink')
        
    except Exception as e:
        print(f"Drive Upload Error: {e}")
        return None

# --- 修正：列ズレ防止のため、管理用空白列を追加 ---
def save_to_google_sheets(name, age, region, email, specialty, diagnosis_type, free_answers, drive_link):
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
        sheet = client.open(sheet_name).worksheet("customer_list")
        
        delta = datetime.timedelta(hours=9)
        jst = datetime.timezone(delta, 'JST')
        now = datetime.datetime.now(jst).strftime("%Y/%m/%d")
        
        fav_movie = free_answers.get("movie", "")
        fav_color = free_answers.get("color", "")
        last_supper = free_answers.get("food", "")
        
        # （前略）
        row_data = [
            now,             # A: Date
            name,            # B: Name
            age,             # C: Age
            region,          # D: Region
            email,           # E: Email
            specialty,       # F: Specialty
            diagnosis_type,  # G: Pattern
            "TRUE",          # H: Check
            "5_Visionary",   # I: Segment
            "配信中",         # J: Status
            "",              # K: Day1
            "",              # L: Day3
            "",              # M: Day5 (★ここを追加！)
            "",              # N: Day7
            "",              # O: Log
            fav_movie,       # P: Movie (列が右にズレます)
            fav_color,       # Q: Color
            last_supper,     # R: Food
            drive_link       # S: Drive Link
        ]
        # （後略）
        sheet.append_row(row_data)
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
    msg['Subject'] = Header("【世界観診断】あなたの「美的DNA」分析レポートをお届けします", 'utf-8')
    
    body = f"""{st.session_state.get('user_name', '表現者')} 様

世界観 研究所のThom Yoshidaです。

あなたの作品と回答から生成された
「美的DNA解析レポート（PDF）」をお届けします。

独自の分析アルゴリズムの結果、あなたの内側に眠る
「{st.session_state.analysis_data.get('catchphrase', '未知なるアーキタイプ')}」の片鱗が見えてきました。

もし、レポートにある「理想の世界観」を
一人で探求することに限界を感じているのなら。

私が主宰する研究所のドアを叩いてください。
そこには、あなたと同じように「光と影」に魅せられた
研究員たちが待っています。

▼ 【招待制】世界観 研究所 オンラインサロン
https://www.street-academy.com/subscription/services/3794?conversion_name=direct_message&tracking_code=d09de3445c9cd6725ecac969e0f06d76
※ このメールを受け取った方だけの特別な案内です。

あなたの「好き」が、世界をそっと照らすことを願って。

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
    limit = 25 if width_limit_mm == 135 else 15
    lines = wrap_text_smart(text, max_char_count=limit)
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
    
    catchphrase_text = json_data.get('catchphrase', 'Visionary Report')
    c.setFont(FONT_SERIF, 42)
    
    title_lines = wrap_text_smart(catchphrase_text, max_char_count=15)
    leading = 20 * mm 
    total_height = (len(title_lines) - 1) * leading
    start_y = (height / 2) + 10*mm + (total_height / 2) 
    
    current_y = start_y
    for line in title_lines:
        c.drawCentredString(width/2, current_y, line)
        current_y -= leading
    
    c.setFont(FONT_SERIF, 24)
    c.drawCentredString(width/2, height/2 - 15*mm - (total_height/2), f"{user_name} 様")
    
    c.setFont(FONT_SANS, 18)
    c.drawCentredString(width/2, height/2 - 32*mm - (total_height/2), "WORLDVIEW ANALYSIS REPORT")
    
    c.setFont(FONT_SERIF, 12)
    c.drawCentredString(width/2, 20*mm, f"Designed by ThomYoshida Laboratory | {datetime.datetime.now().strftime('%Y.%m.%d')}")
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
        c.setFillColor(HexColor(COLORS['pdf_bg']))
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

    c.setFont(FONT_SERIF, 24)
    c.setFillColor(HexColor(COLORS['pdf_text']))
    
    title_lines_p3 = wrap_text_smart(catchphrase_text, max_char_count=18)
    current_y_p3 = height - 40*mm
    for line in title_lines_p3:
        c.drawCentredString(width/2, current_y_p3, f"「{line}」")
        current_y_p3 -= 12*mm
        
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
        
        # 解説
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
    # 名言を中央配置
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
if 'specialty' not in st.session_state: st.session_state.specialty = ""
if 'free_answers' not in st.session_state: st.session_state.free_answers = {}

# STEP 1
if st.session_state.step == 1:
    try: st.image("cover.jpg", use_container_width=True)
    except: pass
    st.title("世界観診断 | Visionary Analysis")
    st.caption("あなたの感性と才能を言語化する、クリエイティブ診断ツール")
    
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
            診断の後半で、あなたの視覚表現から「美的DNA」を抽出・分析します。<br>
            以下の画像をお手元にご準備の上、スタートしてください。
        </p>
        <ul style="margin-bottom: 0;">
            <li><b>現在地（原点）</b>: あなたの代表作、仕事の成果物、または今好きな画像（1〜3枚）</li>
            <li><b>理想（未来）</b>: これから目指したい世界観の画像（1〜3枚）</li>
        </ul>
        <p style="font-size: 0.9rem; color: {COLORS['sub']}; margin-top: 10px;">
            ※ 写真作品に限らず、図面、コード、画面デザインなどの<b>スクリーンショット</b>でも解析可能です。
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"""<div class="domain-box"><div class="domain-title">00. あなたの表現領域 (Domain)</div>""", unsafe_allow_html=True)
    st.caption("あなたが世界を表現するために、主に扱っている「媒体」と「スタイル」を選択してください。")

    selected_main_domain = st.radio(
        "Main Category",
        options=list(DOMAIN_HIERARCHY.keys()),
        horizontal=False,
        label_visibility="collapsed"
    )
    
    current_domain_data = DOMAIN_HIERARCHY[selected_main_domain]
    st.info(f"💡 {current_domain_data['description']}")

    selected_sub_category = st.selectbox(
        "Sub Category (詳細ジャンル)",
        options=current_domain_data["sub_categories"]
    )

    specialty_detail = st.text_input(
        "具体的な活動名や肩書き（任意）", 
        placeholder="例：フリーランスのMV監督、週末だけのパティシエなど"
    )
    st.markdown("</div>", unsafe_allow_html=True)

    full_specialty_str = f"{selected_main_domain.split('(')[-1].strip(')')} > {selected_sub_category}"
    if specialty_detail:
        full_specialty_str += f" ({specialty_detail})"
    
    st.markdown("##### 01. 感性チェック")
    st.write("直感で回答してください。あなたの創作の源泉を探ります。")
    with st.form(key='quiz_form'):
        answers = []
        for i, item in enumerate(QUIZ_DATA):
            ans = st.radio(item["q"], item["opts"], key=f"q{i}", horizontal=False, index=None)
            answers.append((ans, item["type_a"]))
        
        st.markdown("<br><h5>02. あなたのエッセンス（自由回答）</h5>", unsafe_allow_html=True)
        st.caption("独自の分析精度を高めるための、重要な3つの質問です。")
        free_q1 = st.text_input("Q31. 好きな映画を１つだけ挙げるなら？")
        free_q2 = st.text_input("Q32. 好きな色は？")
        free_q3 = st.text_input("Q33. 最後の晩餐に何を食べる？")

        st.write("---")
        submit_button = st.form_submit_button(label="次へ進む")
        
    if submit_button:
        if any(a[0] is None for a in answers): 
            st.error("すべての質問に回答してください。")
        elif not free_q1 or not free_q2 or not free_q3:
            st.error("自由回答の3問もすべて入力してください。")
        else:
            st.session_state.specialty = full_specialty_str
            st.session_state.free_answers = {
                "movie": free_q1,
                "color": free_q2,
                "food": free_q3
            }
            
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
    st.header("02. ビジョンの統合")
    st.info(f"診断タイプ: **{st.session_state.quiz_result}** / 専門: **{st.session_state.specialty}**")
    
    st.warning("⚠️ iPhoneの方へ：『Live Photos』や『HEIC形式』はエラーになる場合があります。JPG/PNGを使用してください。")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### １、あなたが今、好きな作品（またはご自身の現代での最高制作作品）3枚")
        past_files = st.file_uploader("Origin (Max 3)", type=["jpg", "png"], accept_multiple_files=True, key="past")
    with col2:
        st.markdown("#### ２、あなたの理想の世界観を描いた作品　3枚")
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
    st.header("03. レポートの受け取り")
    with st.container():
        st.markdown(f"""<div style="background-color: {COLORS['card']}; padding: 30px; border-radius: 10px; border: 1px solid {COLORS['accent']}; text-align: center;"><h3 style="color: {COLORS['accent']};">Analysis Ready</h3><p>診断結果レポートを発行します。</p></div><br>""", unsafe_allow_html=True)
        with st.form("lead_capture"):
            col_f1, col_f2 = st.columns(2)
            with col_f1: 
                user_name = st.text_input("お名前")
                age_group = st.selectbox("年代", ["10代", "20代", "30代", "40代", "50代", "60代以上"])
            with col_f2: 
                user_email = st.text_input("メールアドレス")
                region = st.text_input("お住まいの地域（都道府県）")
                
            submit = st.form_submit_button("診断結果を見る", type="primary")
            
            if submit:
                if user_name and user_email and region:
                    st.session_state.user_name = user_name
                    st.session_state.user_email = user_email.strip().replace('\xa0', '').replace('\u3000', ' ')
                    st.session_state.user_age = age_group
                    st.session_state.user_region = region
                    
                    st.session_state.step = 4
                    st.rerun()
                else: st.warning("全ての項目を入力してください。")

# STEP 4 (AI Analysis)
elif st.session_state.step == 4:
    if "analysis_data" not in st.session_state:
        with st.spinner("あなたの視覚情報を解析し、『美的DNA』を抽出中... (約1分)"):
            
            success = False
            
            if "GEMINI_API_KEY" in st.secrets:
                # Prompt
                prompt_text = f"""
                # Role Definition
                あなたは「世界観 研究所」の所長、Thom Yoshidaです。
                MoMAのキュレーターのような美術史的知識、トップクリエイティブディレクターの審美眼、そして誰よりも「表現者の孤独」を知るメンターとして振る舞ってください。

                # Task
                ユーザーの入力情報（領域・タイプ・自由記述）と、アップロードされた作品画像（現在地・未来）を統合分析し、その表現者の「魂のアーキタイプ」を特定してください。
                甘いお世辞や表面的な「きれいごと」は不要です。クリス・ペプラー氏のような低音ボイスが聞こえてくるような、知的で落ち着いた、かつ「確信を突く（刺さる）」トーンで記述してください。

                # User Profile
                - 表現領域 (Domain & Specialty): {st.session_state.specialty}
                - 基礎診断傾向: {st.session_state.quiz_result}
                - **魂のエッセンス (Free Answers):**
                    - 好きな映画: {st.session_state.free_answers.get('movie')} (※これを視覚的ムードやストーリーテリングの参考にせよ)
                    - 好きな色: {st.session_state.free_answers.get('color')} (※これをキーカラーやトーン分析に反映せよ)
                    - 最後の晩餐: {st.session_state.free_answers.get('food')} (※ここから個人の「幸福の定義」や「執着の対象」を読み取り、アーキタイプ選定の決定打とせよ)

                # 1. Dynamic Analysis Strategy (Domain Switching)
                ユーザーが選択した以下の「表現領域」に合わせて、分析の着眼点を切り替えてください。
                選択された領域: {st.session_state.specialty}

                [分析ルール]
                - もし「Optics」系なら:
                  「光の入射角」「シャッターの瞬間の湿度」「構図の数学的整合性」を重視。
                - もし「Timeline」系なら:
                  「時間の流れ」「物語の予感」「カット割りのリズム」「音楽とのシンクロ」を重視。
                - もし「Matter」系なら:
                  「マテリアルの質感」「色彩の物理的な厚み」「空間の余白」を重視。
                  ※ 料理・香りの場合は、「味覚・嗅覚の視覚化（シズル感を超えた哲学）」を分析せよ。
                  ※ ネイル・テキスタイルの場合は、「ミクロな細部への執着」と「素材との融合」を分析せよ。
                  ※ Web・UIの場合は、「情報の建築美」と「ユーザー体験の導線」を分析せよ。
                - もし「Somatic」系なら:
                  「ポージングの重心」「表情筋の緊張」「オーラ（存在感）」「役への没入度」を重視。
                - もし「Context」系なら:
                  「行間」「メタファーの強度」「コンセプトの解像度」を重視。
                  ※ エンジニア・研究者の場合は、提出画像（コード、図、論文）から「論理の美しさ」「構造の堅牢性」「知性の品格」を読み取れ。
                  ※ 経営者の場合は、「ビジョンの視覚的強度」と「社会への眼差し」を分析せよ。

                # 2. Classification Logic (The 12 Aesthetic Archetypes)
                分析結果に基づき、以下の12の「美的アーキタイプ」から最も近いものを【1つだけ】選定してください。
                
                1. **The Purist (純粋なる観測者)**: [Innocent] 自然光、透明感、作為のない美、白、ミニマリズム、無垢。
                2. **The Analyst (光の解析者)**: [Sage] 幾何学構図、論理的な美、モノクロ、静寂、水平垂直、理知的。
                3. **The Seeker (真実の探求者)**: [Explorer] ストリートスナップ、ドキュメンタリー、旅、未知の風景、広角、生々しさ。
                4. **The Rebel (ノイズの反逆者)**: [Outlaw] ブレ、ボケ、粗粒子、アンダーグラウンド、既成概念の破壊、パンク。
                5. **The Alchemist (色彩の錬金術師)**: [Magician] 幻想的、高度なレタッチ、合成、非現実的な世界観、魔法。
                6. **The Protagonist (ドラマの主役)**: [Hero] 強いライティング、力強いポートレート、圧倒的な存在感、映画的。
                7. **The Romantic (愛の蒐集家)**: [Lover] 花、肌の質感、暖色、ソフトフォーカス、情緒的、エロス、耽美。
                8. **The Playful (色彩の遊戯者)**: [Jester] ポップ、ビビッドカラー、アイロニー、ユーモア、実験的、極彩色。
                9. **The Realist (日常の記録者)**: [Everyman] 生活感、ありのまま、フィルム調、ノスタルジー、人間味、哀愁。
                10. **The Healer (光の治癒者)**: [Caregiver] 柔らかさ、温かみ、安心感、優しさ、家族、笑顔、陽だまり。
                11. **The Director (世界の支配人)**: [Ruler] 構築された美、スタジオ撮影、重厚感、ラグジュアリー、完璧主義、威厳。
                12. **The Visionary (未踏の創造主)**: [Creator] 抽象表現、アートフォト、前衛的、誰にも似ていない、哲学。

                # 3. Output Rules (Natural & Organic Writing Style)
                - **禁止事項:** 「素晴らしい」「美しい」「感動的」「調和している」といった手垢のついたありきたりな賞賛言葉は一切禁止。「〜せよ」「〜だ」という断定的な命令口調も禁止。
                - **推奨事項:** 「網膜を刺すような」「静寂が聴こえる」「湿度を感じる」「鉄の味がする」など、五感に訴える具体的な描写を行うこと。
                - **トーン:** 厳しい批評家ではなく、**「孤独を知る理解者・伴走者」**として振る舞うこと。相手の迷いを否定せず、「その迷いすらも美しい」と肯定し、可能性を広げるような、優しくも深い**「共感重視」**の文体で語りかけること。「〜かもしれません」「〜という可能性を秘めています」といった表現を好む。
                - **リズム:** 体言止めや倒置法を使い、詩的なリズム（余白のある文体）を作ること。

                # 4. JSON Output Format
                以下のJSON形式で出力してください。Markdownのコードブロックは不要です。生JSONのみ返してください。
                {{
                    "catchphrase": "選定したアーキタイプ名（例：『ノイズの反逆者』として覚醒せよ）", 
                    "twelve_past_keywords": ["現在の作品から滲む『重さ』『停滞』『未熟さ』『躊躇』などを表す単語12個。※重要：必ず「一語（単語）」のみで出力すること。例：「混沌とした世界」は不可。「混沌」とする。"],
                    "twelve_future_keywords": ["未来の作品が放つべき『解放』『洗練』『理想』『覚醒』などを表す単語12個。※重要：必ず「一語（単語）」のみで出力すること。"],
                    "sense_metrics": [
                        {{"left": "論理(Logic)", "right": "直感(Sense)", "value": 0〜100}},
                        {{"left": "写実(Real)", "right": "抽象(Abstract)", "value": 0〜100}},
                        {{"left": "大衆性(Pop)", "right": "作家性(Cult)", "value": 0〜100}},
                        {{"left": "静的(Static)", "right": "動的(Dynamic)", "value": 0〜100}},
                        {{"left": "光(Light)", "right": "影(Shadow)", "value": 0〜100}},
                        {{"left": "記録(Record)", "right": "記憶(Memory)", "value": 0〜100}},
                        {{"left": "作為(Design)", "right": "偶発(Noise)", "value": 0〜100}},
                        {{"left": "肯定(Yes)", "right": "反骨(Rebel)", "value": 0〜100}}
                    ],
                    "formula": {{
                        "values": {{"word": "美意識の核(一言)", "detail": "あなたが死んでも守るべき譲れない美学とは(40文字)"}},
                        "strengths": {{"word": "隠れた武器(一言)", "detail": "自分ではコンプレックスだと思っているが、実は最大の武器になる要素(40文字)"}},
                        "interests": {{"word": "魂の飢餓(一言)", "detail": "なぜその被写体や表現に、執拗に惹かれてしまうのかの分析(40文字)"}}
                    }},
                    "roadmap_steps": [
                        {{"title": "Phase 1: 破壊 (Detox)", "detail": "今すぐやめるべき悪習慣や、捨てるべき『上手な写真』への執着(60文字)"}},
                        {{"title": "Phase 2: 構築 (Structure)", "detail": "世界観を実装するために取り入れるべき具体的な技術、機材、または習慣(60文字)"}},
                        {{"title": "Phase 3: 深化 (Deepen)", "detail": "作家として生き残るために触れるべき教養、哲学、または異分野の体験(60文字)"}}
                    ],
                    "artist_archetypes": [
                        {{"name": "メンターとなる巨匠・作家名(1〜3名)", "detail": "その作家の『視点』のどこを盗むべきか、なぜあなたと似ているのか"}}
                    ],
                    "final_proposals": [
                        {{"point": "具体的な処方箋 1（見出し不要）", "detail": "明日から実践できる具体的なアクション(40文字)"}},
                        {{"point": "具体的な処方箋 2（見出し不要）", "detail": "明日から実践できる具体的なアクション(40文字)"}},
                        {{"point": "具体的な処方箋 3（見出し不要）", "detail": "明日から実践できる具体的なアクション(40文字)"}},
                        {{"point": "具体的な処方箋 4（見出し不要）", "detail": "明日から実践できる具体的なアクション(40文字)"}},
                        {{"point": "具体的な処方箋 5（見出し不要）", "detail": "明日から実践できる具体的なアクション(40文字)"}}
                    ],
                    "alternative_expressions": [
                        "今の表現以外で触れるべき芸術分野（例：アンビエント音楽、純文学、ブルータリズム建築など）"
                    ],
                    "inspiring_quote": {{
                        "text": "その人の背中を押す、美と孤独に関する名言（日本語訳）",
                        "author": "哲学者や芸術家の名前"
                    }}
                }}
                """
                
                try:
                    target_model = None
                    available = []
                    try:
                        for m in genai.list_models():
                            if 'generateContent' in m.supported_generation_methods:
                                available.append(m.name)
                    except: pass

                    if available:
                        for m in available:
                            if '1.5' in m and 'flash' in m: target_model = m; break
                        if not target_model: target_model = available[0]
                    
                    if target_model:
                        model = genai.GenerativeModel(target_model)
                        contents_vision = [prompt_text] + st.session_state.uploaded_images
                        response = model.generate_content(contents_vision, generation_config={"response_mime_type": "application/json"})
                        data = json.loads(response.text)
                        success = True
                except Exception as e:
                    print(f"System Error: {e}")

            if not success:
                st.warning("⚠️ アクセス集中により、デモモードでレポートを作成しました。")
                data = {
                    "catchphrase": "デモモード：The Analyst", 
                    "twelve_past_keywords": ["静寂", "水平", "垂直", "迷い", "模倣", "硬質", "冷徹", "距離", "孤独", "観察", "理屈", "枠"],
                    "twelve_future_keywords": ["温度", "湿度", "ノイズ", "接触", "融解", "受容", "崩壊", "再生", "呼吸", "物語", "深淵", "光"],
                    "sense_metrics": [{"left": "論理", "right": "直感", "value": 80}] * 8,
                    "formula": {"values": {"word": "論理美", "detail": "カオスな世界を整理したい欲求"}, "strengths": {"word": "冷めた目", "detail": "感情に流されない客観性"}, "interests": {"word": "構造", "detail": "ビルの骨組みへの執着"}},
                    "roadmap_steps": [{"title": "Step 1", "detail": "三脚を捨てる"}, {"title": "Step 2", "detail": "雨の日に撮る"}, {"title": "Step 3", "detail": "詩を読む"}],
                    "artist_archetypes": [{"name": "杉本博司", "detail": "時間の概念化"}],
                    "final_proposals": [{"point": "APIキー確認", "detail": "設定を見直してください"}],
                    "alternative_expressions": ["現代音楽", "建築"],
                    "inspiring_quote": {"text": "世界は美しい。ただ、見る目がないだけだ。", "author": "Unknown"}
                }

            st.session_state.analysis_data = data
            
            pdf_buffer = create_pdf(data, st.session_state.get("user_name", "Guest"))
            
            drive_link = upload_to_drive(pdf_buffer, f"Visionary_Report_{st.session_state.user_name}.pdf")
            
            is_saved, save_error = save_to_google_sheets(
                st.session_state.user_name,
                st.session_state.user_age, 
                st.session_state.user_region, 
                st.session_state.user_email, 
                st.session_state.specialty, 
                st.session_state.quiz_result,
                st.session_state.free_answers,
                drive_link if drive_link else "Upload Failed"
            )
            
            is_sent, error_msg = send_email_with_pdf(st.session_state.user_email, pdf_buffer)
            
            st.session_state.email_sent_status = is_sent
            st.session_state.email_error_log = error_msg 
            st.rerun()
    else:
        # 結果表示
        data = st.session_state.analysis_data
        render_web_result(data)
        
        st.markdown("---")
        st.markdown("### 📩 詳細レポートを送信しました")
        
        if st.session_state.get("email_sent_status", False):
            st.success(f"""
            **{st.session_state.user_name} 様の診断レポート（PDF）を、以下のメールアドレス宛に送信いたしました。**
            
            📧 送信先: **{st.session_state.user_email}**
            
            ※ 数分以内に届かない場合は、**迷惑メールフォルダ**もご確認ください。
            """)
            st.info("このレポートは、あなたの今後の創作活動の指針となる「美の設計図」です。大切に保存してください。")
            
        else:
            st.error("⚠️ メール送信に失敗しました。")
            if "email_error_log" in st.session_state and st.session_state.email_error_log:
                st.error(f"【エラー原因】: {st.session_state.email_error_log}")
            
            st.warning("メールが送れませんでしたので、こちらから直接ダウンロードしてください。")
            
            pdf_buffer = create_pdf(data, st.session_state.get("user_name", "Guest"))
            st.download_button("📥 診断レポートをダウンロード", pdf_buffer, "Visionary_Report.pdf", "application/pdf")

        # === Floating CTA ===
        salon_url = "https://www.street-academy.com/subscription/services/3794?conversion_name=direct_message&tracking_code=d09de3445c9cd6725ecac969e0f06d76"
        
        st.markdown(f"""
        <a href="{salon_url}" target="_blank" class="floating-cta">
            <span>🚪 研究所のドアを叩く</span>
        </a>
        """, unsafe_allow_html=True)

        st.markdown("<br><br>", unsafe_allow_html=True)
        if st.button("トップに戻る"):
            st.session_state.clear()
            st.rerun()
