# rss_crawler.py
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

def extract_article_data(url):
    print(f"🌐 기사 가져오기: {url}")
    res = requests.get(url, timeout=5)
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
    print(f"📝 Firestore 저장: {title}")
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
    print("🚀 RSS 크롤링 시작")
    feed = feedparser.parse("https://sports.khan.co.kr/rss")
    print(f"✔️ 기사 개수: {len(feed.entries)}")

    for entry in feed.entries[:5]:
        try:
            print(f"📄 기사 처리: {entry.title}")
            content, img_url = extract_article_data(entry.link)
            image_url = upload_image(img_url) if img_url else ""
            upload_to_firestore(entry.title, entry.link, content, image_url, entry.published)
            print(f"✅ 완료: {entry.title}")
        except Exception as e:
            print(f"❌ 오류 발생: {e}")

# 🔥 중요: 이 부분이 없으면 GitHub Actions에서 실행되지 않음
if __name__ == "__main__":
    print("🔥 rss_crawler.py 실행 시작")
    main()
