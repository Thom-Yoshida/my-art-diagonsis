import streamlit as st
import os
from google import genai
from google.genai import types
from PIL import Image
import json
import io
import datetime
import pandas as pd

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

# ---------------------------------------------------------
# 🎨 デザイン・配色設定
# ---------------------------------------------------------

# フォント登録 (情緒の明朝、論理のゴシック)
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiMin-W3')) # 明朝体（情緒・権威）
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5')) # ゴシック体（論理・構造）

FONT_SERIF = 'HeiseiMin-W3'
FONT_SANS = 'HeiseiKakuGo-W5'

# 配色パレット
C_MAIN_SHADOW = HexColor('#2B2723')   # ウォームシャドウ（文字色）
C_BG_WHITE    = HexColor('#F5F5F5')   # オフホワイト（背景）
C_ACCENT_BLUE = HexColor('#7A96A0')   # ダスティーブルー（アクセント）
C_WARM_BEIGE  = HexColor('#D1C0AF')   # ウォームベージュ（テクスチャ・装飾）
C_MAUVE_GRAY  = HexColor('#A39E99')   # モーヴグレー（影）
C_FOREST_TEAL = HexColor('#528574')   # フォレストティール（構造）
C_MUTE_AMBER  = HexColor('#D6AE60')   # ミュートアンバー（ハイライト）

# ---------------------------------------------------------
# 📝 PDF生成ロジック（スライド形式）
# ---------------------------------------------------------

def draw_organic_shape(c, x, y, size, color):
    """手書き風のゆらぎのある円（簡易表現）"""
    c.setFillColor(color)
    c.setStrokeColor(color)
    # 完全に正円ではなく少し楕円にして有機的さを出す
    c.circle(x, y, size, fill=1, stroke=0)

def draw_header(c, title, page_num):
    """共通ヘッダー・フッター"""
    width, height = landscape(A4)
    
    # 背景色
    c.setFillColor(C_BG_WHITE)
    c.rect(0, 0, width, height, fill=1, stroke=0)
    
    # 装飾（有機的なシェイプ）
    draw_organic_shape(c, 10*mm, height - 10*mm, 15*mm, C_WARM_BEIGE)
    draw_organic_shape(c, width - 10*mm, 10*mm, 20*mm, C_ACCENT_BLUE)
    
    # ページ番号
    c.setFont(FONT_SANS, 9)
    c.setFillColor(C_MAUVE_GRAY)
    c.drawRightString(width - 15*mm, 10*mm, f"{page_num}")

def create_pdf(json_data, quiz_summary):
    buffer = io.BytesIO()
    # A4横向き (スライド形式)
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)
    
    # -----------------------------------------------
    # P1. 表紙 (Key Visual)
    # -----------------------------------------------
    draw_header(c, "", 1)
    
    # キャッチコピー (儚さ・静謐な美しさ)
    c.setFont(FONT_SERIF, 40)
    c.setFillColor(C_MAIN_SHADOW)
    catchphrase = json_data.get('catchphrase', '無題')
    c.drawCentredString(width/2, height/2 + 10*mm, catchphrase)
    
    # サブタイトル
    c.setFont(FONT_SANS, 14)
    c.setFillColor(C_ACCENT_BLUE)
    c.drawCentredString(width/2, height/2 - 15*mm, "Worldview Analysis Report")
    
    # 日付と名前
    date_str = datetime.datetime.now().strftime("%Y.%m.%d")
    c.setFont(FONT_SERIF, 10)
    c.setFillColor(C_MAIN_SHADOW)
    c.drawCentredString(width/2, height/2 - 30*mm, f"Designed by AI Art Director | {date_str}")
    
    c.showPage()

    # -----------------------------------------------
    # P2. 数式スライド (A x B = C)
    # -----------------------------------------------
    draw_header(c, "", 2)
    
    # タイトル
    c.setFont(FONT_SANS, 12)
    c.setFillColor(C_ACCENT_BLUE)
    c.drawString(20*mm, height - 25*mm, "01. THE FORMULA")
    
    # 数式デザイン
    # 性格 (A)
    c.setFont(FONT_SERIF, 24)
    c.setFillColor(C_MAIN_SHADOW)
    type_short = quiz_summary.split('（')[0] if '（' in quiz_summary else quiz_summary
    c.drawCentredString(width*0.25, height/2 + 10*mm, "『 性格 』")
    c.setFont(FONT_SANS, 14)
    c.setFillColor(C_FOREST_TEAL)
    c.drawCentredString(width*0.25, height/2 - 10*mm, type_short)
    
    # ×
    c.setFont(FONT_SERIF, 40)
    c.setFillColor(C_MUTE_AMBER)
    c.drawCentredString(width*0.4, height/2, "×")
    
    # 表現 (B)
    c.setFont(FONT_SERIF, 24)
    c.setFillColor(C_MAIN_SHADOW)
    c.drawCentredString(width*0.55, height/2 + 10*mm, "『 表現 』")
    c.setFont(FONT_SANS, 14)
    c.setFillColor(C_FOREST_TEAL)
    # キーワードの1つ目を使用
    kw1 = json_data.get('five_keywords', ['表現'])[0]
    c.drawCentredString(width*0.55, height/2 - 10*mm, kw1)
    
    # = 
    c.setFont(FONT_SERIF, 40)
    c.setFillColor(C_MUTE_AMBER)
    c.drawCentredString(width*0.7, height/2, "=")
    
    # 世界観 (C)
    c.setFont(FONT_SERIF, 32)
    c.setFillColor(C_MAIN_SHADOW)
    # キャッチコピーの一部を使用
    c.drawCentredString(width*0.85, height/2, "世界観")
    
    c.showPage()

    # -----------------------------------------------
    # P3. チャート (精密データ)
    # -----------------------------------------------
    draw_header(c, "", 3)
    
    c.setFont(FONT_SANS, 12)
    c.setFillColor(C_ACCENT_BLUE)
    c.drawString(20*mm, height - 25*mm, "02. ANALYSIS CHART")
    
    # グラフ描画
    scores = json_data.get('analysis_scores', {})
    start_x = 40*mm
    start_y = height - 60*mm
    gap_y = 15*mm
    
    c.setLineWidth(0.5)
    
    for i, (key, value) in enumerate(scores.items()):
        y_pos = start_y - (i * gap_y)
        
        # ラベル
        c.setFont(FONT_SERIF, 12)
        c.setFillColor(C_MAIN_SHADOW)
        c.drawString(start_x, y_pos, key)
        
        # ライン (科学計測器風：細い線)
        line_start = start_x + 40*mm
        line_max = 120*mm
        c.setStrokeColor(C_MAUVE_GRAY)
        c.line(line_start, y_pos + 1*mm, line_start + line_max, y_pos + 1*mm)
        
        # 値のドット
        current_len = (value / 100) * line_max
        c.setFillColor(C_FOREST_TEAL)
        c.circle(line_start + current_len, y_pos + 1*mm, 1.5*mm, fill=1, stroke=0)
        
        # 数値
        c.setFont(FONT_SANS, 10)
        c.setFillColor(C_MAIN_SHADOW)
        c.drawString(line_start + line_max + 5*mm, y_pos, f"{value}")
        
    # 分析コメント（吹き出し風ではないシンプルなブロック）
    c.setFont(FONT_SANS, 10)
    c.setFillColor(C_MAIN_SHADOW)
    current_features = json_data.get('current_worldview', {}).get('features', '')
    
    text_y = 40*mm
    text_obj = c.beginText(40*mm, text_y)
    text_obj.setFont(FONT_SERIF, 11)
    text_obj.setLeading(16)
    
    # 文字列の折り返し処理
    comment = "分析結果：\n" + current_features
    for line in comment.split('\n'):
        if len(line) > 40:
             text_obj.textLine(line[:40])
             text_obj.textLine(line[40:])
        else:
             text_obj.textLine(line)
    c.drawText(text_obj)
    
    c.showPage()

    # -----------------------------------------------
    # P4. ロードマップ (年表リスト & 矢印)
    # -----------------------------------------------
    draw_header(c, "", 4)
    
    c.setFont(FONT_SANS, 12)
    c.setFillColor(C_ACCENT_BLUE)
    c.drawString(20*mm, height - 25*mm, "03. FUTURE ROADMAP")
    
    roadmap_points = json_data.get('roadmap_steps', [])
    
    y_pos = height - 50*mm
    
    for i, point in enumerate(roadmap_points):
        # 左列：巨大な数字 (年号的表現)
        c.setFont(FONT_SANS, 36)
        c.setFillColor(C_WARM_BEIGE)
        step_num = f"0{i+1}"
        c.drawString(30*mm, y_pos - 5*mm, step_num)
        
        # 右列：説明
        # タイトル
        title = point.get('title', '')
        c.setFont(FONT_SERIF, 14)
        c.setFillColor(C_MAIN_SHADOW)
        c.drawString(60*mm, y_pos, title)
        
        # 詳細（体言止め）
        desc = point.get('detail', '')
        c.setFont(FONT_SANS, 10)
        c.setFillColor(C_MAUVE_GRAY)
        c.drawString(60*mm, y_pos - 6*mm, desc)
        
        # 装飾ライン
        c.setStrokeColor(C_ACCENT_BLUE)
        c.setLineWidth(1)
        c.line(60*mm, y_pos - 12*mm, width - 30*mm, y_pos - 12*mm)
        
        y_pos -= 35*mm
        
    c.showPage()
    
    # -----------------------------------------------
    # P5. メッセージ (対話形式・締め)
    # -----------------------------------------------
    draw_header(c, "", 5)
    
    # シンプルなテキストブロック
    c.setFont(FONT_SERIF, 16)
    c.setFillColor(C_MAIN_SHADOW)
    c.drawString(30*mm, height/2 + 20*mm, "私からの提案。")
    
    c.setFont(FONT_SERIF, 12)
    final_msg = json_data.get('final_message', 'あなたの創造性が、世界を彩ることを願う。')
    
    text_obj = c.beginText(30*mm, height/2)
    text_obj.setLeading(20)
    
    # 折り返し
    for i in range(0, len(final_msg), 35):
        text_obj.textLine(final_msg[i:i+35])
        
    c.drawText(text_obj)
    
    # 最後のロゴ風装飾
    c.setFillColor(C_FOREST_TEAL)
    c.circle(width - 30*mm, 30*mm, 3*mm, fill=1, stroke=0)
    c.setFont(FONT_SANS, 8)
    c.drawCentredString(width - 30*mm, 22*mm, "Visionary")

    c.showPage()

    c.save()
    buffer.seek(0)
    return buffer

# --- 30問のクイズデータ（前回と同じ） ---
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

st.set_page_config(page_title="Visionary Analysis", layout="wide") # デザインに合わせてwideに
st.title("Visionary Analysis: AI作家性・統合診断")
st.write("「センス」を科学し、あなたの「世界観」を体系化する。")

if 'step' not in st.session_state:
    st.session_state.step = 1
if 'quiz_result' not in st.session_state:
    st.session_state.quiz_result = None
if 'quiz_score_percent' not in st.session_state:
    st.session_state.quiz_score_percent = 0

# ==========================================
# STEP 1: 心理クイズ
# ==========================================
if st.session_state.step == 1:
    st.header("01. SENSE CHECK")
    st.write("直感で回答。あなたの創作の源泉を探る。")

    with st.form(key='quiz_form'):
        answers = []
        for i, item in enumerate(QUIZ_DATA):
            ans = st.radio(item["q"], item["opts"], key=f"q{i}", horizontal=True)
            answers.append((ans, item["type_a"]))
        
        st.write("---")
        submit_button = st.form_submit_button(label="Analyze Type")

    if submit_button:
        score_a = 0
        for ans, type_a_val in answers:
            if ans == type_a_val:
                score_a += 1
        
        percent = int((score_a / 30) * 100)
        st.session_state.quiz_score_percent = percent
        
        if score_a >= 20:
            st.session_state.quiz_result = f"直感・情熱型 (情熱度: {percent}%)"
        elif score_a >= 16:
            st.session_state.quiz_result = f"バランス型・直感寄り (情熱度: {percent}%)"
        elif score_a >= 11:
            st.session_state.quiz_result = f"バランス型・論理寄り (情熱度: {percent}%)"
        else:
            st.session_state.quiz_result = f"論理・構築型 (情熱度: {percent}%)"
            
        st.session_state.step = 2
        st.rerun()

# ==========================================
# STEP 2: 画像アップロード & 統合診断
# ==========================================
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
            if st.button("Generate Report (PDF)"):
                
                past_images = [Image.open(f) for f in past_files]
                future_images = [Image.open(f) for f in future_files]

                # --- 厳密なデザイン・文章指示を含むプロンプト ---
                prompt = f"""
                あなたは洗練された美意識を持つアートディレクターです。
                ユーザーの「性格タイプ」「過去作品」「未来の理想」を分析し、
                PDFスライド生成用のデータをJSON形式で作成してください。

                【基本ルール】
                ・製作者（あなた）の主語は「私」または主語なし。
                ・文体は「〜だ。」「〜である。」「〜体言止め。」を使用。
                ・説得力のある、短くても重みのある言葉を選ぶこと。
                ・「センスを科学する」視点で、抽象的な言葉と論理的な分析を融合させること。

                【入力情報】
                性格タイプ: {st.session_state.quiz_result}
                (前半画像: 現在 / 後半画像: 理想)

                【出力JSONフォーマット】
                {{
                    "catchphrase": "世界観を一言で表す、短く詩的なキャッチコピー（15文字以内）",
                    "five_keywords": ["キーワード1", "キーワード2", "キーワード3", "キーワード4", "キーワード5"],
                    "analysis_scores": {{
                        "独創性": 0-100,
                        "技術力": 0-100,
                        "表現力": 0-100,
                        "社会性": 0-100,
                        "将来性": 0-100
                    }},
                    "current_worldview": {{
                        "features": "現在の作品に見られる特徴の分析。（100文字程度、体言止め多用）"
                    }},
                    "roadmap_steps": [
                        {{
                            "title": "STEP 1: 認識",
                            "detail": "まず現状の武器を把握すること。〇〇の技術は既に高い水準にある。（体言止め・具体的助言）"
                        }},
                        {{
                            "title": "STEP 2: 拡張",
                            "detail": "次に、〇〇の要素を取り入れること。理想とのギャップはここに存在する。（体言止め・具体的助言）"
                        }},
                        {{
                            "title": "STEP 3: 到達",
                            "detail": "最終的に、〇〇な表現へと昇華させること。それが独自のスタイルとなる。（体言止め・具体的助言）"
                        }}
                    ],
                    "final_message": "未来への総括メッセージ。100文字程度。詩的かつ応援を含めること。"
                }}
                """
                
                contents = [prompt] + past_images + future_images

                try:
                    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
                    
                    with st.spinner("Analyzing Sense & Logic..."):
                        response = client.models.generate_content(
                            model='gemini-flash-latest',
                            contents=contents,
                            config=types.GenerateContentConfig(
                                response_mime_type="application/json"
                            )
                        )
                        
                        data = json.loads(response.text)
                        
                        st.success("Analysis Completed.")
                        
                        # PDF生成 (スライド形式)
                        pdf_file = create_pdf(data, st.session_state.quiz_result)
                        
                        # ダウンロードボタン
                        st.download_button(
                            label="📥 Download Analysis Report (PDF)",
                            data=pdf_file,
                            file_name="Visionary_Analysis_Report.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )
                        
                        # 簡易プレビュー
                        st.subheader("Analysis Preview")
                        st.write(f"**{data['catchphrase']}**")
                        st.bar_chart(data['analysis_scores'])

                except Exception as e:
                    st.error(f"Error: {e}")

    elif st.button("Reset"):
         st.session_state.step = 1
         st.session_state.quiz_result = None
         st.rerun()
