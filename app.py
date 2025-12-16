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
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib.units import mm

# ---------------------------------------------------------
# ▼▼▼ セキュリティ対応版: APIキーの設定 ▼▼▼
# 1. Streamlitの「Secrets」からキーを取得を試みる
# 2. なければ、サイドバーで入力を求める（他人が自分のキーで試せるようにする）
# ---------------------------------------------------------
if "GEMINI_API_KEY" in st.secrets:
    os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
else:
    # Secretsがない場合（ローカルでファイル未作成、または公開時にキー未設定の場合）
    user_api_key = st.sidebar.text_input("Gemini APIキーを入力してください", type="password")
    if user_api_key:
        os.environ["GEMINI_API_KEY"] = user_api_key
    else:
        st.warning("⚠️ APIキーが設定されていません。サイドバーに入力するか、Secretsを設定してください。")
        st.stop() # キーがないとここで止まる
# ---------------------------------------------------------

# --- 設定: 日本語フォント ---
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
FONT_NAME = 'HeiseiKakuGo-W5'

# --- PDF生成関数 ---
def create_pdf(json_data, quiz_summary, quiz_score_percent):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # ヘッダー
    c.setFont(FONT_NAME, 20)
    c.drawCentredString(width / 2, height - 20*mm, "作家性・未来ビジョン統合診断レポート")
    c.setFont(FONT_NAME, 10)
    date_str = datetime.datetime.now().strftime("%Y年%m月%d日")
    c.drawRightString(width - 20*mm, height - 30*mm, f"診断日: {date_str}")
    
    y = height - 45*mm

    # ■ STEP1: 作家性格タイプ & キーワード
    c.setFillColorRGB(0.9, 0.9, 0.9)
    c.rect(15*mm, y - 25*mm, width - 30*mm, 30*mm, fill=1, stroke=0)
    c.setFillColorRGB(0, 0, 0)
    
    c.setFont(FONT_NAME, 14)
    c.drawString(20*mm, y, "■ あなたを表す5つのキーワード")
    y -= 10*mm
    
    keywords = json_data.get('five_keywords', [])
    kw_str = "  /  ".join(keywords)
    c.setFont(FONT_NAME, 12)
    c.drawCentredString(width / 2, y, f"【 {kw_str} 】")
    y -= 10*mm
    
    c.setFont(FONT_NAME, 10)
    c.drawString(20*mm, y, f"性格タイプ診断: {quiz_summary} (情熱度: {quiz_score_percent}%)")
    y -= 25*mm

    # ■ パラメータグラフ
    c.setFont(FONT_NAME, 14)
    c.drawString(20*mm, y, "■ 作家性パラメータ分析")
    y -= 8*mm
    
    scores = json_data.get('analysis_scores', {})
    c.setFont(FONT_NAME, 10)
    
    start_x = 25*mm
    bar_max_width = 100*mm
    
    for key, value in scores.items():
        c.drawString(start_x, y, f"{key}")
        c.drawRightString(start_x + 130*mm, y, f"{value}/100")
        bar_len = (value / 100) * bar_max_width
        c.setFillColorRGB(0.2, 0.4, 0.8)
        c.rect(start_x + 25*mm, y, bar_len, 3*mm, fill=1, stroke=0)
        c.setFillColorRGB(0, 0, 0)
        y -= 8*mm
        
    y -= 15*mm

    # ■ STEP2: 現在地の分析
    c.setFont(FONT_NAME, 14)
    c.drawString(20*mm, y, "■ 現在地の分析（過去作品より）")
    y -= 10*mm
    
    current = json_data.get('current_worldview', {})
    c.setFont(FONT_NAME, 12)
    c.drawString(25*mm, y, f"テーマ: {current.get('catchphrase', 'なし')}")
    y -= 8*mm
    c.setFont(FONT_NAME, 10)
    c.drawString(25*mm, y, f"特徴: {current.get('features', 'なし')}")
    y -= 20*mm

    # ■ STEP3: 理想の未来図
    c.setFont(FONT_NAME, 14)
    c.drawString(20*mm, y, "■ 理想の未来図（ヴィジョン）")
    y -= 10*mm
    
    ideal = json_data.get('ideal_worldview', {})
    c.setFont(FONT_NAME, 12)
    c.drawString(25*mm, y, f"テーマ: {ideal.get('catchphrase', 'なし')}")
    y -= 8*mm
    c.setFont(FONT_NAME, 10)
    c.drawString(25*mm, y, f"特徴: {ideal.get('features', 'なし')}")
    y -= 20*mm

    # ■ FINAL: 統合アドバイス
    c.setFillColorRGB(0.95, 0.95, 1.0)
    c.rect(15*mm, 20*mm, width - 30*mm, y - 25*mm, fill=1, stroke=0)
    c.setFillColorRGB(0, 0, 0)

    c.setFont(FONT_NAME, 14)
    c.drawString(20*mm, y, "■ 理想へのロードマップ")
    y -= 10*mm
    c.setFont(FONT_NAME, 10)
    
    advice = json_data.get('roadmap_advice', 'なし')
    
    text_object = c.beginText(20*mm, y)
    text_object.setFont(FONT_NAME, 10)
    text_object.setLeading(14)
    
    # 改行コード(\n)で分割してから折り返し処理を行うように改良
    # これにより箇条書きがきれいに表示されます
    lines = advice.split('\n')
    max_char = 40
    
    for line in lines:
        if line.strip() == "":
            text_object.textLine("") # 空行
            continue
            
        for i in range(0, len(line), max_char):
            chunk = line[i:i+max_char]
            text_object.textLine(chunk)
        
    c.drawText(text_object)
    
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

# --- 30問のクイズデータ ---
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

st.set_page_config(page_title="AI作家性・未来統合診断", layout="centered")
st.title("🚀 AI 作家性・未来ビジョン統合診断")
st.write("「性質（クイズ）」「現在（過去作品）」「未来（理想）」を統合し、5つのキーワードと数値グラフで分析します。")

# セッション状態の初期化
if 'step' not in st.session_state:
    st.session_state.step = 1
if 'quiz_result' not in st.session_state:
    st.session_state.quiz_result = None
if 'quiz_score_percent' not in st.session_state:
    st.session_state.quiz_score_percent = 0

# ==========================================
# STEP 1: 心理クイズ (30問)
# ==========================================
if st.session_state.step == 1:
    st.header("STEP 1: 作家としての性質を知る")
    st.write("直感で答えてください。あなたの創作スタイルを詳細に分析します。")

    with st.form(key='quiz_form'):
        answers = []
        for i, item in enumerate(QUIZ_DATA):
            ans = st.radio(item["q"], item["opts"], key=f"q{i}", horizontal=True)
            answers.append((ans, item["type_a"]))
        
        st.write("---")
        submit_button = st.form_submit_button(label="診断結果を出して、次へ進む")

    if submit_button:
        score_a = 0
        for ans, type_a_val in answers:
            if ans == type_a_val:
                score_a += 1
        
        percent = int((score_a / 30) * 100)
        st.session_state.quiz_score_percent = percent
        
        if score_a >= 20:
            st.session_state.quiz_result = f"超・直感情熱型アーティスト (情熱度: {percent}%)"
        elif score_a >= 16:
            st.session_state.quiz_result = f"バランス型（直感寄り） (情熱度: {percent}%)"
        elif score_a >= 11:
            st.session_state.quiz_result = f"バランス型（論理寄り） (情熱度: {percent}%)"
        else:
            st.session_state.quiz_result = f"超・論理構築型クリエイター (情熱度: {percent}%)"
            
        st.session_state.step = 2
        st.rerun()

# ==========================================
# STEP 2: 画像アップロード & 統合診断
# ==========================================
elif st.session_state.step == 2:
    st.header("STEP 2: 現在地と未来の可視化")
    st.success(f"あなたの診断結果: **「{st.session_state.quiz_result}」**")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("① 現在地（過去作品）")
        past_files = st.file_uploader("過去作品（最大3枚）", type=["jpg", "png", "jpeg"], accept_multiple_files=True, key="past")
    with col2:
        st.subheader("② 目的地（未来ヴィジョン）")
        future_files = st.file_uploader("理想画像（最大3枚）", type=["jpg", "png", "jpeg"], accept_multiple_files=True, key="future")

    if past_files and future_files:
        if len(past_files) > 3 or len(future_files) > 3:
             st.warning("画像はそれぞれ3枚以内でお願いします。")
        else:
            if st.button("🚀 すべての情報を統合して診断する"):
                
                past_images = [Image.open(f) for f in past_files]
                future_images = [Image.open(f) for f in future_files]

                # プロンプトの修正：具体的なツール名を避け、芸術的観点での箇条書きを指定
                prompt = f"""
                あなたはプロのアートディレクター兼キャリアストラテジストです。
                以下の情報に基づき、統合的な分析レポートを作成してください。

                【情報源】
                1. 性格タイプ: {st.session_state.quiz_result}
                2. 現在の作品（前半の画像）
                3. 未来の理想（後半の画像）

                【出力フォーマット】
                以下のJSONデータのみを出力してください。

                {{
                    "five_keywords": ["この作家を表すキーワード1", "キーワード2", "キーワード3", "キーワード4", "キーワード5"],
                    "analysis_scores": {{
                        "独創性": 0-100の数値,
                        "技術・構成力": 0-100の数値,
                        "情熱・表現力": 0-100の数値,
                        "市場・社会性": 0-100の数値,
                        "将来性": 0-100の数値
                    }},
                    "current_worldview": {{
                        "catchphrase": "現在のキャッチコピー",
                        "features": "現在の特徴（100文字以内）"
                    }},
                    "ideal_worldview": {{
                        "catchphrase": "未来のキャッチコピー",
                        "features": "理想の特徴（100文字以内）"
                    }},
                    "roadmap_advice": "性格タイプ（{st.session_state.quiz_result}）に基づき、現在から理想へ近づくための『方向性と表現』に関するヒント（全400文字程度）。具体的なツール名やソフトウェア名は言及せず、芸術的な観点（構図、色彩、哲学、マインドセットなど）からアドバイスしてください。\n出力形式は、以下の箇条書きスタイルにしてください（JSONの文字列の中で改行を含めてください）：\n・【ポイント1】: 詳細説明\n・【ポイント2】: 詳細説明\n・【ポイント3】: 詳細説明"
                }}
                """
                
                contents = [prompt] + past_images + future_images

                try:
                    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
                    
                    with st.spinner("キーワード抽出とパラメータ分析を実行中..."):
                        response = client.models.generate_content(
                            model='gemini-flash-latest',
                            contents=contents,
                            config=types.GenerateContentConfig(
                                response_mime_type="application/json"
                            )
                        )
                        
                        data = json.loads(response.text)
                        
                        st.success("統合分析が完了しました！")
                        
                        # --- 画面表示: キーワード ---
                        st.subheader("🔑 あなたを表す5つのキーワード")
                        cols = st.columns(5)
                        for i, kw in enumerate(data['five_keywords']):
                            cols[i].info(kw)

                        # --- 画面表示: グラフ ---
                        st.subheader("📊 成分パラメータ分析")
                        scores = data['analysis_scores']
                        
                        chart_data = pd.DataFrame(
                            list(scores.values()),
                            index=list(scores.keys()),
                            columns=["スコア"]
                        )
                        st.bar_chart(chart_data, horizontal=True)

                        # --- 画面表示: 現在と未来 ---
                        col_res1, col_res2 = st.columns(2)
                        with col_res1:
                            st.subheader("現在地")
                            st.write(f"**{data['current_worldview']['catchphrase']}**")
                            st.caption(data['current_worldview']['features'])
                        with col_res2:
                            st.subheader("理想の未来")
                            st.write(f"**{data['ideal_worldview']['catchphrase']}**")
                            st.caption(data['ideal_worldview']['features'])
                            
                        st.subheader("🗺️ 未来へのロードマップ（方向性と表現のヒント）")
                        # 改行をHTML的に反映して表示
                        st.info(data['roadmap_advice'].replace('\n', '  \n'))
                        
                        # PDF生成
                        pdf_file = create_pdf(data, st.session_state.quiz_result, st.session_state.quiz_score_percent)
                        
                        st.download_button(
                            label="📄 統合ロードマップ・レポートをPDFでダウンロード",
                            data=pdf_file,
                            file_name="future_roadmap_report.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )

                except Exception as e:
                    st.error(f"エラーが発生しました: {e}")

    elif st.button("診断を最初からやり直す"):
         st.session_state.step = 1
         st.session_state.quiz_result = None
         st.rerun()