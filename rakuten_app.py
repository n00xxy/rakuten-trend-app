from flask import Flask, render_template, request, jsonify
import pandas as pd
from datetime import datetime, timedelta
import os
from pytrends.request import TrendReq
import numpy as np

app = Flask(__name__)

GENRE_LIST = {
    "スイーツ・お菓子": "100283",
    "水・ソフトドリンク": "551167",
    "パソコン・周辺機器": "216131",
    "レディースファッション": "100371",
}

# Renderの永続ディスクのパスを指定
DATA_DIR = "/data"
REVIEW_INCREASE_THRESHOLD = 2
RANK_CHANGE_THRESHOLD = 5

def get_hot_items(genre_name):
    now = datetime.now()
    current_suffix = "AM" if now.hour < 12 else "PM"
    current_date_str = now.strftime('%Y-%m-%d')
    if now.hour < 12:
        previous_date = now - timedelta(days=1)
        previous_date_str = previous_date.strftime('%Y-%m-%d')
        previous_suffix = "PM"
    else:
        previous_date_str = current_date_str
        previous_suffix = "AM"

    current_file = os.path.join(DATA_DIR, f"{genre_name}_{current_date_str}_{current_suffix}.csv")
    previous_file = os.path.join(DATA_DIR, f"{genre_name}_{previous_date_str}_{previous_suffix}.csv")

    if not os.path.exists(current_file) or not os.path.exists(previous_file):
        return None, f"「{genre_name}」の比較データが見つかりません。"
    try:
        current_df = pd.read_csv(current_file)
        previous_df = pd.read_csv(previous_file)
        merged_df = pd.merge(current_df, previous_df, on='商品コード', how='left', suffixes=('_today', '_yesterday'))
        merged_df['順位_yesterday'] = merged_df['順位_yesterday'].fillna(301)
        merged_df['順位変動'] = pd.to_numeric(merged_df['順位_yesterday'], errors='coerce') - pd.to_numeric(merged_df['順位_today'], errors='coerce')
        merged_df['レビュー数_yesterday'] = merged_df['レビュー数_yesterday'].fillna(0)
        merged_df['レビュー増加数'] = pd.to_numeric(merged_df['レビュー数_today'], errors='coerce') - pd.to_numeric(merged_df['レビュー数_yesterday'], errors='coerce')
        
        hot_items_df = merged_df[
            (merged_df['順位変動'] >= RANK_CHANGE_THRESHOLD) | (merged_df['レビュー増加数'] >= REVIEW_INCREASE_THRESHOLD)
        ].copy()

        if hot_items_df.empty:
            return None, "注目すべき変動があった商品はありませんでした。"

        conditions = [
            (hot_items_df['順位変動'] >= RANK_CHANGE_THRESHOLD) & (hot_items_df['レビュー増加数'] >= REVIEW_INCREASE_THRESHOLD),
            (hot_items_df['順位変動'] >= RANK_CHANGE_THRESHOLD),
            (hot_items_df['レビュー増加数'] >= REVIEW_INCREASE_THRESHOLD)
        ]
        choices = ['👑 順位 & レビューW増', '📈 順位急上昇', '⭐ レビュー急増']
        hot_items_df['理由'] = np.select(conditions, choices, default='')
        
        score_map = {'👑 順位 & レビューW増': 3, '📈 順位急上昇': 2, '⭐ レビュー急増': 1}
        hot_items_df['score'] = hot_items_df['理由'].map(score_map)
        hot_items_df.sort_values(by=['score', '順位変動'], ascending=[False, False], inplace=True)

        hot_items_df.loc[:, '順位_yesterday'] = hot_items_df['順位_yesterday'].replace(301, '圏外')
        return hot_items_df.to_dict(orient='records'), f"分析対象: {previous_date_str} {previous_suffix} と {current_date_str} {current_suffix} の比較"
    except Exception as e:
        return None, f"分析中にエラーが発生しました: {e}"

@app.route('/')
def index():
    selected_genre = request.args.get('genre', list(GENRE_LIST.keys())[0])
    hot_items, message = get_hot_items(selected_genre)
    return render_template('index.html', 
                           items=hot_items, message=message, genres=GENRE_LIST,
                           selected_genre=selected_genre, today=datetime.now().strftime('%Y年%m月%d日 %H:%M'))

@app.route('/get_trends')
def get_trends_data():
    keyword = request.args.get('keyword')
    if not keyword:
        return jsonify({"error": "キーワードが指定されていません"}), 400
    try:
        pytrends = TrendReq(hl='ja-JP', tz=360) 
        pytrends.build_payload(kw_list=[keyword], timeframe='today 3-m', geo='JP')
        trends_df = pytrends.interest_over_time()
        if trends_df.empty:
            return jsonify({"error": f"「{keyword}」のトレンドデータが見つませんでした。"}), 404
        trends_df.reset_index(inplace=True)
        chart_data = {
            "labels": [d.strftime('%Y-%m-%d') for d in trends_df['date']],
            "datasets": [{
                "label": f"「{keyword}」の検索トレンド", "data": list(trends_df[keyword]),
                "borderColor": "#d62828", "backgroundColor": "rgba(214, 40, 40, 0.1)",
                "fill": True, "tension": 0.1
            }]
        }
        return jsonify(chart_data)
    except Exception as e:
        return jsonify({"error": f"トレンド取得中にエラーが発生しました: {e}"}), 500

if __name__ == '__main__':
    # gunicornで動かすため、ポートとホストの指定を追加
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)