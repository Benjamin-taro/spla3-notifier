import requests
import json
from datetime import datetime

# 保存用の関数
def save_json_with_timestamp(data, prefix="spla3_schedule"):
    now = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"{prefix}_{now}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ JSON saved to: {filename}")

# API取得と保存の実行
def fetch_and_save_schedule():
    url = "https://spla3.yuu26.com/api/schedule"
    headers = {
        "User-Agent": "MyApp/1.0 (contact: your_email_or_twitter)"
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        save_json_with_timestamp(data)
    else:
        print(f"❌ Failed to fetch data: {response.status_code}")

if __name__ == "__main__":
    fetch_and_save_schedule()
