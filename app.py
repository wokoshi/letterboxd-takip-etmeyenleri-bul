import streamlit as st
from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession
import asyncio
import random
import re

st.set_page_config(page_title="Letterboxd Takip Analizi", page_icon="🔍", layout="centered")

st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

.stApp { background-color: #0A110C; color: #9CAF9F; }

.custom-title {
    color: #E8F0E9;
    font-size: 1.8rem;
    font-weight: 800;
    text-align: center;
}
.custom-subtitle {
    text-align: center;
    color: #7A8C7D;
    margin-bottom: 1.8rem;
}

.footer-sig {
    text-align: center;
    color: #5A6E5E;
    font-size: 14px;
    margin-top: 3rem;
    padding-top: 1rem;
    border-top: 1px solid #1A2E20;
    width: 60%;
    opacity: 0.9;
    margin-left: auto;
    margin-right: auto;
}

.stButton>button {
    background-color: #1B5E32;
    color: white;
    border-radius: 12px;
    width: 100%;
}

img { border-radius: 10px; }

.card {
    background-color:#121E15;
    padding:10px;
    border-radius:14px;
    display:flex;
    align-items:center;
    gap:10px;
    margin-bottom:10px;
}
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='custom-title'>🔍 Letterboxd Takip Analizi</div>", unsafe_allow_html=True)
st.markdown("<div class='custom-subtitle'>Hesabınızın takipçi ve takip edilen durumunu tek tuşla öğrenin.</div>", unsafe_allow_html=True)

islem_modu = st.radio(
    "",
    ["Beni Takip Etmeyenler", "Benim Takip Etmediklerim"],
    horizontal=True
)

hedef_kullanici = st.text_input("Kullanıcı adınızı giriniz:")

YASAKLI = {"films", "reviews", "lists", "activity", "members", "following", "followers", "likes", "watchlist", "diary", "tags", "about", ""}

def parse_page_users(html):
    soup = BeautifulSoup(html, "html.parser")
    kisiler = {}
    
    # Sağ kenar çubuğunu (sidebar) tamamen dışarıda bırak:
    ana_alan = soup.find("table", class_="person-table") or soup.find("section", id="content") or soup.find("div", id="content")
    if not ana_alan:
        ana_alan = soup

    satirlar = ana_alan.find_all("div", class_="person-summary")
    for s in satirlar:
        if s.find_parent("aside") or s.find_parent("div", class_="sidebar"):
            continue
            
        a = s.find("a", class_="avatar") or s.find("a", class_="name")
        if a and a.get("href"):
            raw_href = a["href"].strip("/").split("/")
            if not raw_href:
                continue
            username = raw_href[-1].lower()
            if username in YASAKLI:
                continue
                
            img = s.find("img")
            img_url = img["src"] if (img and img.get("src")) else "https://s.ltrbxd.com/static/img/avatar220.png"
            kisiler[username] = img_url
            
    return kisiler

def has_next_page(html):
    soup = BeautifulSoup(html, "html.parser")
    # Sayfada 'Next' veya sonraki sayfa butonu var mı?
    next_btn = soup.select("a.next, .paginate-next a, a[rel='next']")
    return len(next_btn) > 0

async def scrape_target(session, kullanici_adi, tip, proxy_url):
    kisiler = {}
    page = 1
    proxies = {"http": proxy_url, "https": proxy_url}
    
    while True:
        url = f"https://letterboxd.com/{kullanici_adi}/{tip}/page/{page}/" if page > 1 else f"https://letterboxd.com/{kullanici_adi}/{tip}/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": f"https://letterboxd.com/{kullanici_adi}/",
        }
        
        success = False
        for _ in range(4):
            try:
                res = await session.get(url, proxies=proxies, impersonate="chrome120", headers=headers, timeout=12)
                if res.status_code == 404:
                    return None if page == 1 else kisiler
                if res.status_code == 200 and "Just a moment" not in res.text:
                    parsed = parse_page_users(res.text)
                    if not parsed and page > 1:
                        # Sayfa boş geldiyse bitmiştir
                        return kisiler
                    kisiler.update(parsed)
                    
                    # Sonraki sayfa yoksa döngüyü sonlandır
                    if not has_next_page(res.text):
                        return kisiler
                        
                    success = True
                    break
                await asyncio.sleep(random.uniform(0.5, 0.8))
            except Exception:
                await asyncio.sleep(0.5)
                
        if not success:
            return f"BLOK: 403"
            
        page += 1
        # İnsan hızında ufak bir ara vererek Cloudflare'in radarına girmeyi engelle
        await asyncio.sleep(random.uniform(0.3, 0.6))
        
    return kisiler

async def main_async(kullanici_adi, proxy_url):
    # Çerezleri ve oturumu koruyan TEK bir session ile ilerliyoruz
    async with AsyncSession() as session:
        res_following = await scrape_target(session, kullanici_adi, "following", proxy_url)
        if isinstance(res_following, str) and res_following.startswith("BLOK"):
            return res_following, None
            
        await asyncio.sleep(0.5)
        res_followers = await scrape_target(session, kullanici_adi, "followers", proxy_url)
        return res_following, res_followers

def analiz_calistir(kullanici_adi):
    try:
        proxy_url = st.secrets["DATAIMPULSE_PROXY"]
    except Exception:
        return "PROXY_ERROR", "PROXY_ERROR"
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    return loop.run_until_complete(main_async(kullanici_adi, proxy_url))

if st.button("Analizi Başlat 🎬"):
    if not hedef_kullanici:
        st.warning("Kullanıcı adınızı giriniz")
    else:
        with st.spinner("Tarama yapılıyor... Lütfen bekleyiniz."):
            cleaned_username = hedef_kullanici.strip().lower()
            following, followers = analiz_calistir(cleaned_username)

        if following == "PROXY_ERROR" or followers == "PROXY_ERROR":
            st.error("Sistem geçici olarak çalışmıyor lütfen daha sonra tekrar deneyiniz. (Hata: Proxy Secret Ayarı Yok)")
        elif isinstance(following, str) and following.startswith("BLOK"):
            st.error(f"Sistem geçici olarak çalışmıyor lütfen daha sonra tekrar deneyiniz. (Detay: Following {following})")
        elif isinstance(followers, str) and followers.startswith("BLOK"):
            st.error(f"Sistem geçici olarak çalışmıyor lütfen daha sonra tekrar deneyiniz. (Detay: Followers {followers})")
        elif following is None or followers is None:
            st.error("Bu kullanıcı adıyla ilgili hesap bulunmuyor. Kullanıcı adınızı kontrol ediniz.")
        else:
            if islem_modu == "Beni Takip Etmeyenler":
                sonuc = {u: following[u] for u in following if u not in followers}
            else:
                sonuc = {u: followers[u] for u in followers if u not in following}

            st.success(f"İşlem başarılı! {len(sonuc)} kişi bulundu.")

            users = list(sonuc.items())
            for i in range(0, len(users), 2):
                cols = st.columns(2)
                for j in range(2):
                    if i + j < len(users):
                        usr, img = users[i+j]
                        with cols[j]:
                            st.markdown(f"""
                            <div class="card">
                                <img src="{img}" width="50">
                                <div>
                                    <b>{usr}</b><br>
                                    <a href="https://letterboxd.com/{usr}/" target="_blank">Profile git</a>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

st.markdown("<div class='footer-sig'>Created by <a href='https://letterboxd.com/wokoshi/' target='_blank'>wokoshi</a></div>", unsafe_allow_html=True)
