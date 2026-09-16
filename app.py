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
    })
    return s

def get_total_count_and_pages(session, username, rel_type):
    # Ana profil sekmesinden veya ilk sayfadan toplam sayıyı matematiksel çek
    url = f"https://letterboxd.com/{username}/{rel_type}/"
    res = session.get(url, impersonate="chrome124", timeout=15)
    
    if res.status_code == 404:
        return 0, 0, ""
    if res.status_code != 200:
        return -1, -1, f"BLOK: {res.status_code}"

    soup = BeautifulSoup(res.text, "html.parser")
    
    # Sayfadaki toplam sayıyı yakala (örn: 'following' başlığındaki sayı)
    count = 0
    nav_link = soup.select_one(f"a[href*='/{username}/{rel_type}/']")
    if nav_link:
        text = nav_link.get_text()
        digits = "".join(filter(str.isdigit, text))
        if digits:
            count = int(digits)

    total_pages = math.ceil(count / 25) if count > 0 else 1
    return count, total_pages, res.text

def parse_users(html):
    soup = BeautifulSoup(html, "html.parser")
    # Kenar çubuğunu doğrudan hafızadan yok et (o 9 sahte kişiyi siler)
    for sb in soup.select("aside, .sidebar, #sidebar, div.sidebar"):
        sb.decompose()

    users = {}
    cards = soup.select("div.person-summary")
    for card in cards:
        name_tag = card.find("a", class_="name")
        if name_tag and name_tag.get("href"):
            uname = name_tag.get("href").strip("/").split("/")[-1].lower()
            img = card.find("img")
            img_url = img["src"] if (img and img.get("src")) else "https://s.ltrbxd.com/static/img/avatar220.png"
            users[uname] = img_url
    return users

def scrape_list(session, username, rel_type):
    count, total_pages, first_html = get_total_count_and_pages(session, username, rel_type)
    if total_pages == -1:
        return first_html # BLOK stringi döner
    if count == 0 and total_pages == 0:
        return None

    users = parse_users(first_html)

    # Matematiksel olarak hesaplanan sayfa adedince sırayla çek
    for page in range(2, total_pages + 1):
        time.sleep(random.uniform(0.4, 0.8)) # Cloudflare oran limitine takılmamak için nefes al
        url = f"https://letterboxd.com/{username}/{rel_type}/page/{page}/"
        res = session.get(url, impersonate="chrome124", timeout=15)
        if res.status_code == 200:
            users.update(parse_users(res.text))
        else:
            break

    return users

if st.button("Analizi Başlat 🎬"):
    if not hedef_kullanici:
        st.warning("Kullanıcı adınızı giriniz.")
    else:
        proxy_url = st.secrets.get("DATAIMPULSE_PROXY")
        if not proxy_url:
            st.error("Secrets altında proxy tanımlı değil.")
        else:
            with st.spinner("Analiz ediliyor..."):
                cleaned = hedef_kullanici.strip().lower()
                session = get_session(proxy_url)
                
                following = scrape_list(session, cleaned, "following")
                time.sleep(0.5)
                followers = scrape_list(session, cleaned, "followers")

            if isinstance(following, str) and following.startswith("BLOK"):
                st.error(f"Proxy engeli: {following}")
            elif following is None or followers is None:
                st.error("Kullanıcı bulunamadı.")
            else:
                if islem_modu == "Beni Takip Etmeyenler":
                    sonuc = {u: following[u] for u in following if u not in followers}
                else:
                    sonuc = {u: followers[u] for u in followers if u not in following}

                st.success(f"İşlem tamamlandı! Toplam {len(sonuc)} kişi bulundu.")
                for u, img in sonuc.items():
                    st.markdown(f"- [{u}](https://letterboxd.com/{u}/)")
