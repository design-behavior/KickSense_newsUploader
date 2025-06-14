import feedparser
import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore, storage
from datetime import datetime
import hashlib
import os
import json

print("📦 Firebase 초기화 시작")

# ✅ 서비스 계정 키 로드
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

def upload_to_firestore(title, link, content, image_url, published, category):
    print(f"✅ Firestore 저장 시도: {title} [{category}]")
    # 중복 확인
    existing = db.collection('news').where('url', '==', link).get()
    if existing:
        print(f"⚠️ 이미 저장된 기사: {link}")
        return  # 이미 존재하면 건너뜀
        
    doc_ref = db.collection('news').document()
    doc_ref.set({
        'title': title,
        'url': link,
        'content': content,
        'thumbnail': image_url,
        'published': published,
        'category': category,         # ✅ 필수: 국내/해외 구분 필드!
        'createdAt': datetime.utcnow()
    })

def main():
    rss_sources = [
        ("https://sports.khan.co.kr/rss/soccer_korea-soccer", "domestic"),
        ("https://sports.khan.co.kr/rss/soccer_world-soccer", "international")
    ]

    for rss_url, category in rss_sources:
        entries = parse_feed(rss_url)
        print(f"📌 {rss_url} 에서 {len(entries)}개 기사 수집됨 [{category}]")

        for entry in entries[:18]:  # 필요시 전체 처리
            try:
                print(f"▶️ 기사 처리: {entry.title}")
                content, img_url = extract_article_data(entry.link)
                image_url = upload_image(img_url) if img_url else ""
                published = getattr(entry, 'published', '')

                upload_to_firestore(
                    entry.title,
                    entry.link,
                    content,
                    image_url,
                    published,
                    category    # ✅ 추가
                )

            except Exception as e:
                print(f"❌ 오류: {entry.link} → {e}")

if __name__ == "__main__":
    print("🔥 rss_crawler.py 실행 시작")
    main()
