import streamlit as st
from bs4 import BeautifulSoup
from curl_cffi import requests
import math
import random
import time

st.set_page_config(page_title="Letterboxd Takip Analizi", page_icon="🔍", layout="centered")

st.title("🔍 Letterboxd Takip Analizi")

islem_modu = st.radio("", ["Beni Takip Etmeyenler", "Benim Takip Etmediklerim"], horizontal=True)
hedef_kullanici = st.text_input("Letterboxd Kullanıcı Adı:")

def get_session(proxy_url):
    s = requests.Session()
    s.proxies = {"http": proxy_url, "https": proxy_url}
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://letterboxd.com/",
    })
    return s

def parse_users(html):
    soup = BeautifulSoup(html, "html.parser")
    # Kenar çubuğunu yok et
    for sb in soup.select("aside, .sidebar, #sidebar, div.sidebar"):
        sb.decompose()

    users = {}
    # Sadece ana gövdedeki person-summary kartları
    cards = soup.select("div.person-summary")
    for card in cards:
        name_tag = card.find("a", class_="name")
        if name_tag and name_tag.get("href"):
            uname = name_tag.get("href").strip("/").split("/")[-1].lower()
            img = card.find("img")
            img_url = img["src"] if (img and img.get("src")) else "https://s.ltrbxd.com/static/img/avatar220.png"
            users[uname] = img_url
    return users

def get_all_users_for_rel(session, username, rel_type):
    users = {}
    page = 1
    
    while True:
        url = f"https://letterboxd.com/{username}/{rel_type}/page/{page}/" if page > 1 else f"https://letterboxd.com/{username}/{rel_type}/"
        
        res = None
        for _ in range(3):
            try:
                res = session.get(url, impersonate="chrome124", timeout=15)
                if res.status_code in [200, 404]:
                    break
                time.sleep(1)
            except Exception:
                time.sleep(1)

        if not res or res.status_code == 404:
            if page == 1:
                return None  # Kullanıcı yok
            break
            
        if res.status_code != 200:
            return f"BLOK: {res.status_code}"

        parsed = parse_users(res.text)
        if not parsed:
            break
            
        users.update(parsed)
        
        # Sayfada 'Next' butonu var mı kontrolü
        soup = BeautifulSoup(res.text, "html.parser")
        has_next = soup.select("a.next, .paginate-next a, a[rel='next']")
        if not has_next:
            break
            
        page += 1
        time.sleep(random.uniform(0.4, 0.7))
        
    return users

if st.button("Analizi Başlat 🎬"):
    if not hedef_kullanici:
        st.warning("Kullanıcı adınızı giriniz.")
    else:
        proxy_url = st.secrets.get("DATAIMPULSE_PROXY")
        if not proxy_url:
            st.error("Secrets altında DATAIMPULSE_PROXY tanımlı değil.")
        else:
            with st.spinner("Analiz ediliyor..."):
                cleaned = hedef_kullanici.strip().lower()
                session = get_session(proxy_url)
                
                following = get_all_users_for_rel(session, cleaned, "following")
                time.sleep(0.5)
                followers = get_all_users_for_rel(session, cleaned, "followers")

            if isinstance(following, str) and following.startswith("BLOK"):
                st.error(f"Following listesi çekilemedi: {following}")
            elif isinstance(followers, str) and followers.startswith("BLOK"):
                st.error(f"Followers listesi çekilemedi: {followers}")
            elif following is None or followers is None:
                st.error("Kullanıcı bulunamadı.")
            else:
                # İki listenin de başarıyla dolduğunu doğrula
                if islem_modu == "Beni Takip Etmeyenler":
                    sonuc = {u: following[u] for u in following if u not in followers}
                else:
                    sonuc = {u: followers[u] for u in followers if u not in following}

                st.success(f"İşlem tamamlandı! Toplam {len(sonuc)} kişi bulundu.")
                for u, img in sonuc.items():
                    st.markdown(f"- [{u}](https://letterboxd.com/{u}/)")
