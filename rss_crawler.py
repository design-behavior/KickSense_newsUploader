import feedparser
import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore, storage
from datetime import datetime
import hashlib
import os
import json

# 환경 변수에서 Firebase 키 로드
with open("serviceAccountKey.json") as f:
    cred_dict = json.load(f)

cred = credentials.Certificate(cred_dict)
firebase_admin.initialize_app(cred, {
    'storageBucket': os.environ['FIREBASE_STORAGE_BUCKET']
})

db = firestore.client()
bucket = storage.bucket()

def extract_article_data(url):
    res = requests.get(url, timeout=5)
    soup = BeautifulSoup(res.content, 'html.parser')
    content_el = soup.select_one('.art_body')
    img_el = soup.select_one('.art_photo img')
    content = content_el.get_text(strip=True) if content_el else ''
    img_url = img_el['src'] if img_el else None
    return content, img_url

def upload_image(img_url):
    res = requests.get(img_url)
    filename = hashlib.md5(img_url.encode()).hexdigest() + '.jpg'
    blob = bucket.blob(f'news_thumbnails/{filename}')
    blob.upload_from_string(res.content, content_type='image/jpeg')
    blob.make_public()
    return blob.public_url

def upload_to_firestore(title, link, content, image_url, published):
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
    feed = feedparser.parse("https://sports.khan.co.kr/rss")
    for entry in feed.entries[:5]:  # 최근 5개만
        try:
            title = entry.title
            link = entry.link
            published = entry.published
            content, img_url = extract_article_data(link)
            image_url = upload_image(img_url) if img_url else ""
            upload_to_firestore(title, link, content, image_url, published)
        except Exception as e:
            print(f"Error processing {entry.link}: {e}")

if __name__ == "__main__":
    print("rss_crawler.py 실행 시작")
    main()
