import requests
import os
from datetime import datetime, timedelta

API_KEY = os.getenv("API_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")

# -------------------------------
# 1. 전월 자동 계산
# -------------------------------
today = datetime.now()

first_day_this_month = today.replace(day=1)
last_month_last_day = first_day_this_month - timedelta(days=1)
last_month_first_day = last_month_last_day.replace(day=1)

start_date = last_month_first_day.strftime("%Y-%m-%d")
end_date = last_month_last_day.strftime("%Y-%m-%d")
month_value = f"{last_month_last_day.month}월"

# -------------------------------
# 2. 유튜브 채널 정보
# -------------------------------
channel_url = "https://www.googleapis.com/youtube/v3/channels"
params = {
    "part": "statistics,contentDetails",
    "id": CHANNEL_ID,
    "key": API_KEY
}

res = requests.get(channel_url, params=params).json()
channel_data = res['items'][0]

subscriber_count = int(channel_data['statistics']['subscriberCount'])
total_view_count = int(channel_data['statistics']['viewCount'])
uploads_playlist_id = channel_data['contentDetails']['relatedPlaylists']['uploads']

# -------------------------------
# 3. 영상 ID 수집
# -------------------------------
video_ids = []
next_page_token = None

while True:
    playlist_url = "https://www.googleapis.com/youtube/v3/playlistItems"
    params = {
        "part": "contentDetails",
        "playlistId": uploads_playlist_id,
        "maxResults": 50,
        "key": API_KEY
    }

    if next_page_token:
        params["pageToken"] = next_page_token

    res = requests.get(playlist_url, params=params).json()

    for item in res['items']:
        video_ids.append(item['contentDetails']['videoId'])

    next_page_token = res.get('nextPageToken')
    if not next_page_token:
        break

# -------------------------------
# 4. 좋아요 + 댓글 합산
# -------------------------------
total_likes = 0
total_comments = 0

for i in range(0, len(video_ids), 50):
    video_url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "part": "statistics",
        "id": ",".join(video_ids[i:i+50]),
        "key": API_KEY
    }

    res = requests.get(video_url, params=params).json()

    for item in res['items']:
        stats = item['statistics']
        total_likes += int(stats.get('likeCount', 0))
        total_comments += int(stats.get('commentCount', 0))

# -------------------------------
# 5. Notion 설정
# -------------------------------
headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# -------------------------------
# 6. 중복 체크 (월 기준)
# -------------------------------
query_url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"

query_data = {
    "filter": {
        "property": "월",
        "title": {
            "equals": month_value
        }
    }
}

query_res = requests.post(query_url, headers=headers, json=query_data).json()

existing_page = None
if query_res.get("results"):
    existing_page = query_res["results"][0]["id"]

# -------------------------------
# 7. 데이터 구성
# -------------------------------
properties_data = {
    "월": {
        "title": [
            {
                "text": {
                    "content": month_value
                }
            }
        ]
    },
    "날짜": {
        "date": {
            "start": start_date,
            "end": end_date
        }
    },
    "채널": {
        "select": {"name": "유튜브"}
    },
    "구독자": {
        "number": subscriber_count
    },
    "누적 조회수": {
        "number": total_view_count
    },
    "좋아요": {
        "number": total_likes
    },
    "댓글": {
        "number": total_comments
    }
}

# -------------------------------
# 8. 생성 or 업데이트
# -------------------------------
if existing_page:
    update_url = f"https://api.notion.com/v1/pages/{existing_page}"
    response = requests.patch(update_url, headers=headers, json={"properties": properties_data})
    print("기존 데이터 업데이트 완료")
else:
    create_data = {
        "parent": {"database_id": DATABASE_ID},
        "properties": properties_data
    }
    response = requests.post("https://api.notion.com/v1/pages", headers=headers, json=create_data)
    print("신규 데이터 생성 완료")

# -------------------------------
# 결과 출력
# -------------------------------
print("\n===== 완료 =====")
print("월:", month_value)
print("기간:", start_date, "~", end_date)
print("Notion 상태:", response.status_code)