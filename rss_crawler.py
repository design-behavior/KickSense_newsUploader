import feedparser
import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore, storage
from datetime import datetime
import hashlib
import os
import json

print("📦 시작: Firebase 및 라이브러리 설정")

# Firebase 초기화
with open("serviceAccountKey.json") as f:
    cred_dict = json.load(f)

cred = credentials.Certificate(cred_dict)
firebase_admin.initialize_app(cred, {
    'storageBucket': os.environ.get('FIREBASE_STORAGE_BUCKET')
})

db = firestore.client()
bucket = storage.bucket()

headers = {
    'User-Agent': 'Mozilla/5.0 (compatible; MyNewsBot/1.0; +http://example.com/bot)'
}

def parse_feed(url):
    print(f"🌐 RSS 요청 중: {url}")
    res = requests.get(url, headers=headers, timeout=5)
    feed = feedparser.parse(res.content)
    return feed.entries

def extract_article_data(url):
    print(f"📰 기사 본문 크롤링: {url}")
    res = requests.get(url, headers=headers, timeout=5)
    soup = BeautifulSoup(res.content, 'html.parser')
    content_el = soup.select_one('.art_body')
    img_el = soup.select_one('.art_photo img')
    content = content_el.get_text(strip=True) if content_el else ''
    img_url = img_el['src'] if img_el else None
    return content, img_url

def upload_image(img_url):
    print(f"🖼 이미지 업로드: {img_url}")
    res = requests.get(img_url)
    filename = hashlib.md5(img_url.encode()).hexdigest() + '.jpg'
    blob = bucket.blob(f'news_thumbnails/{filename}')
    blob.upload_from_string(res.content, content_type='image/jpeg')
    blob.make_public()
    return blob.public_url

def upload_to_firestore(title, link, content, image_url, published):
    print(f"✅ Firestore 저장: {title}")
    doc_ref = db.collection('news').document()
    doc_ref.set({
        'title': title,
        'url': link,
        'content': content,
        'thumbnail': image_url,
        'published': published,
        'createdAt': datetime.utcnow()
    })

def main():
    rss_urls = [
        "https://sports.khan.co.kr/rss/soccer_korea-soccer",
        "https://sports.khan.co.kr/rss/soccer_world-soccer"
    ]

    all_entries = []
    for url in rss_urls:
        entries = parse_feed(url)
        print(f"📌 {url} 에서 {len(entries)}개 기사 수집됨")
        all_entries.extend(entries)

    print(f"📊 총 기사 수: {len(all_entries)}")

    for entry in all_entries[:10]:  # 테스트용으로 10개 제한
        try:
            print(f"▶️ 기사 처리: {entry.title}")
            content, img_url = extract_article_data(entry.link)
            image_url = upload_image(img_url) if img_url else ""

            published = getattr(entry, 'published', '')  # ← 핵심 수정 포인트

            upload_to_firestore(
                entry.title,
                entry.link,
                content,
                image_url,
                published
            )
            print(f"✅ 저장 완료: {entry.title}")

        except Exception as e:
            print(f"❌ 오류: {entry.link} → {e}")

# 실행 진입점
if __name__ == "__main__":
    print("🔥 rss_crawler.py 실행 시작")
    main()
