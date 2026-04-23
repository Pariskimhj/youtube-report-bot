import requests
import os
from datetime import datetime, timedelta

# ================================
# 🔑 환경변수
# ================================
API_KEY = os.getenv("API_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")

X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")
X_USERNAME = os.getenv("X_USERNAME")

# ================================
# 📅 전월 계산
# ================================
today = datetime.now()
first_day_this_month = today.replace(day=1)
last_month_last_day = first_day_this_month - timedelta(days=1)
last_month_first_day = last_month_last_day.replace(day=1)

start_date = last_month_first_day.strftime("%Y-%m-%d")
end_date = last_month_last_day.strftime("%Y-%m-%d")
month_value = f"{last_month_last_day.month}월"

# ================================
# 📦 Notion 설정
# ================================
headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# ================================
# 🔍 기존 페이지 찾기 (월 + 채널)
# ================================
def find_existing_page(channel_name):
    query_url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"

    query_data = {
        "filter": {
            "and": [
                {
                    "property": "월",
                    "title": {
                        "equals": month_value
                    }
                },
                {
                    "property": "채널",
                    "select": {
                        "equals": channel_name
                    }
                }
            ]
        }
    }

    res = requests.post(query_url, headers=headers, json=query_data).json()

    if res.get("results"):
        return res["results"][0]["id"]
    return None

# ================================
# 💾 Notion 저장 함수
# ================================
def save_to_notion(channel_name, subs, views, likes, comments):
    existing_page = find_existing_page(channel_name)

    properties = {
        "월": {
            "title": [{"text": {"content": month_value}}]
        },
        "날짜": {
            "date": {"start": start_date, "end": end_date}
        },
        "채널": {
            "select": {"name": channel_name}
        },
        "구독자": {
            "number": subs
        },
        "누적 조회수": {
            "number": views
        },
        "좋아요": {
            "number": likes
        },
        "댓글": {
            "number": comments
        }
    }

    if existing_page:
        update_url = f"https://api.notion.com/v1/pages/{existing_page}"
        requests.patch(update_url, headers=headers, json={"properties": properties})
        print(f"{channel_name} → 업데이트 완료")
    else:
        create_data = {
            "parent": {"database_id": DATABASE_ID},
            "properties": properties
        }
        requests.post("https://api.notion.com/v1/pages", headers=headers, json=create_data)
        print(f"{channel_name} → 신규 생성 완료")

# ================================
# 🔵 1. 유튜브 데이터 수집
# ================================
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

# 영상 ID 수집
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

# 좋아요 / 댓글 합산
yt_likes = 0
yt_comments = 0

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
        yt_likes += int(stats.get('likeCount', 0))
        yt_comments += int(stats.get('commentCount', 0))

# ================================
# ⚫ 2. X 데이터 수집
# ================================
x_headers = {
    "Authorization": f"Bearer {X_BEARER_TOKEN}"
}

# USER ID
user_url = f"https://api.x.com/2/users/by/username/{X_USERNAME}"
user_res = requests.get(user_url, headers=x_headers).json()
USER_ID = user_res["data"]["id"]

# 팔로워
user_info_url = f"https://api.x.com/2/users/{USER_ID}?user.fields=public_metrics"
user_info = requests.get(user_info_url, headers=x_headers).json()

x_followers = user_info["data"]["public_metrics"]["followers_count"]

# 트윗 데이터
tweets_url = f"https://api.x.com/2/users/{USER_ID}/tweets?tweet.fields=public_metrics&max_results=100"
tweets_res = requests.get(tweets_url, headers=x_headers).json()

tweets = tweets_res.get("data", [])

x_likes = 0
x_comments = 0
x_retweets = 0

for t in tweets:
    m = t["public_metrics"]
    x_likes += m.get("like_count", 0)
    x_comments += m.get("reply_count", 0)
    x_retweets += m.get("retweet_count", 0)

# ================================
# 🚀 3. Notion 저장 실행
# ================================
save_to_notion("유튜브", subscriber_count, total_view_count, yt_likes, yt_comments)
save_to_notion("X", x_followers, 0, x_likes, x_comments)

# ================================
# 📊 결과 출력
# ================================
print("\n===== 완료 =====")
print("월:", month_value)

print("\n[유튜브]")
print("구독자:", subscriber_count)
print("조회수:", total_view_count)

print("\n[X]")
print("팔로워:", x_followers)
print("좋아요:", x_likes)
print("댓글:", x_comments)
print("리트윗:", x_retweets)