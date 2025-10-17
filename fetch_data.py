import requests
import pandas as pd
from datetime import datetime
import os
import time

# 環境変数からAPIキーを安全に読み込む
RAKUTEN_APP_ID = os.environ.get('RAKUTEN_APP_ID')

# 分析したいジャンル
GENRE_LIST = {
    "スイーツ・お菓子": "100283",
    "水・ソフトドリンク": "551167",
    "パソコン・周辺機器": "216131",
    "レディースファッション": "100371",
}

# Renderの永続ディスクのパスを指定
DATA_DIR = "/data"
ITEM_SEARCH_URL = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"
PAGES_TO_FETCH = 10 

def get_time_suffix(now):
    return "AM" if now.hour < 12 else "PM"

def fetch_and_save_data():
    """全ジャンルの「レビュー数が多い順」商品を300件取得し、レビュー数と共に保存する"""
    now = datetime.now()
    print(f"{now.strftime('%Y-%m-%d %H:%M:%S')}: データ取得処理を開始します...")

    if not RAKUTEN_APP_ID:
        print("エラー: 環境変数 RAKUTEN_APP_ID が設定されていません。")
        return

    for genre_name, genre_id in GENRE_LIST.items():
        print(f"【{genre_name}】のデータを最大300件取得中... (時間がかかります)")
        
        all_items_list = []
        
        # 1. 10ページ分の商品リストを取得
        for page in range(1, PAGES_TO_FETCH + 1):
            print(f" - {page}/{PAGES_TO_FETCH} ページ目を取得中...")
            search_params = {
                "applicationId": RAKUTEN_APP_ID,
                "format": "json",
                "genreId": genre_id,
                "sort": "+reviewCount",
                "page": page,
                "hits": 30
            }
            try:
                response = requests.get(ITEM_SEARCH_URL, params=search_params)
                response.raise_for_status()
                search_data = response.json()

                if "Items" in search_data and search_data["Items"]:
                    for item_info in search_data["Items"]:
                        all_items_list.append(item_info["Item"])
                else:
                    print(f" - {page}ページ目にはデータがありませんでした。取得を終了します。")
                    break 
                
                time.sleep(1) 

            except requests.exceptions.RequestException as e:
                print(f"APIリクエストエラー: {e}")
                break

        if not all_items_list:
            print(f"「{genre_name}」のデータが取得できませんでした。")
            continue

        # 2. 取得した全商品のレビュー数を取得
        print(f" -> 合計{len(all_items_list)}件の商品についてレビュー数を取得します...")
        final_data_list = []
        for i, item in enumerate(all_items_list):
            print(f"   - データ整形中: {i+1}/{len(all_items_list)}", end="\r")
            review_count = item.get("reviewCount", 0)
            final_data_list.append({
                "順位": i + 1, "商品名": item.get("itemName"), "価格": item.get("itemPrice"),
                "店舗名": item.get("shopName"), "商品コード": item.get("itemCode"),
                "itemUrl": item.get("itemUrl"), "レビュー数": review_count,
            })
        
        print("\n -> データ整形完了！")
        df = pd.DataFrame(final_data_list)

        # 3. ファイルに保存
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        
        date_str = now.strftime('%Y-%m-%d')
        suffix = get_time_suffix(now)
        file_path = os.path.join(DATA_DIR, f"{genre_name}_{date_str}_{suffix}.csv")
        df.to_csv(file_path, index=False, encoding='utf-8-sig')
        print(f" -> 保存成功！: {file_path}")

if __name__ == '__main__':
    fetch_and_save_data()