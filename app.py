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
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
    
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
# 1. 診断データ (30 Questions - Logic Layer)
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
    {"q": "Q21. 批評を受けた時の反応は？", "opts": ["感情を高める曲を大音量で", "冷静に改善点として受け止める"], "type_a": "感情を高める曲を大音量で"}, # 元データの重複修正の可能性あり
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
# 3. 外部連携関数 (Sheets & Email)
# ---------------------------------------------------------
def save_to_google_sheets(name, email, diagnosis_type):
    if "gcp_service_account" not in st.secrets: return False
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        sheet_name = st.secrets.get("SHEET_NAME", "customer_list")
        sheet = client.open(sheet_name).sheet1
        
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([now, name, email, diagnosis_type])
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
# 4. PDF生成ロジック
# ---------------------------------------------------------
def create_pdf(json_data):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)
    
    # 簡易デザイン（表紙のみ例示）
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
# 5. Web UI コンポーネント (The Experience Layer)
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

def render_admin_dashboard():
    st.title("🚁 Strategy Cockpit")
    st.markdown("### Manager Dashboard")
    with st.spinner("Loading Database..."):
        df = load_data_from_sheets()
        
    if df.empty:
        st.warning("No data available yet.")
        return

    col1, col2, col3 = st.columns(3)
    with col1: st.metric("Total Leads", len(df))
    with col2: st.metric("Recent", "---")
    with col3: st.metric("Status", "Active")

    st.markdown("---")
    col_chart, col_data = st.columns([1, 2])
    
    with col_chart:
        st.subheader("Type Distribution")
        # 4列目(index 3)が診断タイプと仮定
        if len(df.columns) >= 4:
            type_col = df.columns[3] 
            type_counts = df[type_col].value_counts()
            fig = go.Figure(data=[go.Pie(labels=type_counts.index, values=type_counts.values, hole=.3)])
            fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)

    with col_data:
        st.subheader("Customer List")
        st.dataframe(df, use_container_width=True)
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download CSV", csv, "list.csv", "text/csv")

# ---------------------------------------------------------
# 6. メイン実行フロー (The Pipeline)
# ---------------------------------------------------------

# --- Admin Access (Sidebar) ---
with st.sidebar:
    st.markdown("---")
    if st.checkbox("Manager Access", key="admin_mode"):
        admin_pass = st.text_input("Access Key", type="password")
        if admin_pass == st.secrets.get("ADMIN_PASSWORD", "admin123"):
            st.success("Access Granted")
            render_admin_dashboard()
            st.stop()
        elif admin_pass:
            st.error("Access Denied")

if 'step' not in st.session_state: st.session_state.step = 1
if 'quiz_result' not in st.session_state: st.session_state.quiz_result = None
if 'quiz_score' not in st.session_state: st.session_state.quiz_score = 0

# --- STEP 1: QUIZ (30 Questions) ---
if st.session_state.step == 1:
    try:
        st.image("cover.jpg", use_container_width=True)
    except: pass
    
    st.title("Visionary Analysis")
    st.caption("美意識の解像度を上げる、対話型診断ツール")
    
    st.markdown("##### 01. SENSE CHECK")
    st.write("直感で回答してください。あなたの創作の源泉を探ります。")

    with st.form(key='quiz_form'):
        answers = []
        # 30問のループ処理
        for i, item in enumerate(QUIZ_DATA):
            ans = st.radio(item["q"], item["opts"], key=f"q{i}", horizontal=True, index=None)
            answers.append((ans, item["type_a"]))
        
        st.write("---")
        submit_button = st.form_submit_button(label="PROCEED TO VISION")

    if submit_button:
        # 未回答チェック
        if any(a[0] is None for a in answers):
            st.error("すべての質問に回答してください。")
        else:
            # スコア計算
            score_a = 0
            for ans, type_a_val in answers:
                if ans == type_a_val:
                    score_a += 1
            
            percent = int((score_a / 30) * 100)
            st.session_state.quiz_score = percent
            
            # タイプ判定ロジック (Logic Layer)
            if score_a >= 20: st.session_state.quiz_result = f"直感・情熱型 (情熱度: {percent}%)"
            elif score_a >= 16: st.session_state.quiz_result = f"バランス型・直感寄り (情熱度: {percent}%)"
            elif score_a >= 11: st.session_state.quiz_result = f"バランス型・論理寄り (情熱度: {percent}%)"
            else: st.session_state.quiz_result = f"論理・構築型 (情熱度: {percent}%)"
            
            st.session_state.step = 2
            st.rerun()

# --- STEP 2: UPLOAD (投資行動) ---
elif st.session_state.step == 2:
    st.header("02. VISION INTEGRATION")
    st.info(f"Your Type: **{st.session_state.quiz_result}**")
    st.write("あなたの感性をAIに学習させます。画像をアップロードしてください。")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Past Works")
        past_files = st.file_uploader("Origin (Max 3)", type=["jpg", "png"], accept_multiple_files=True, key="past")
    with col2:
        st.markdown("#### Future Vision")
        future_files = st.file_uploader("Ideal (Max 3)", type=["jpg", "png"], accept_multiple_files=True, key="future")

    if st.button("NEXT STEP: UNLOCK REPORT"):
        if not past_files:
            st.error("分析のために、少なくとも1枚の作品画像をアップロードしてください。")
        else:
            st.session_state.step = 3
            st.rerun()

# --- STEP 3: LEAD CAPTURE (Gate) ---
elif st.session_state.step == 3:
    st.header("03. UNLOCK YOUR REPORT")
    
    with st.container():
        st.markdown(f"""
        <div style="background-color: {COLORS['card']}; padding: 30px; border-radius: 10px; border: 1px solid {COLORS['accent']}; text-align: center;">
            <h3 style="color: {COLORS['accent']};">Analysis Ready</h3>
            <p>診断結果とレポートを発行するために情報を入力してください。</p>
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

# --- STEP 4: GENERATE & DISPLAY (Result) ---
elif st.session_state.step == 4:
    if "analysis_data" not in st.session_state:
        with st.spinner("Connecting to Visionary Core..."):
            
            # --- ここでGemini APIを実行 (本番用) ---
            # prompt = f"..."
            # contents = [prompt] + [images...]
            # response = client.models.generate_content(...)
            # data = json.loads(response.text)
            
            # デモ用ダミーデータ（テスト時はAPI節約のためこちらを使用）
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
