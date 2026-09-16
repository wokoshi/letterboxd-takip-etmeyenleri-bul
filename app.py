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

# Letterboxd sistem URL'leri (kullanıcı değildir, temizlenmesi gerekir)
SISTEM_URL_ENGEL = {
    "films", "reviews", "lists", "activity", "members", "following", 
    "followers", "likes", "watchlist", "diary", "tags", "stats", ""
}

def parse_page_users(html):
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")
        
    kisiler = {}
    satirlar = soup.select(".person-summary, td.table-person")
    
    for s in satirlar:
        link = s.select_one("a.name, h3.title a, a.avatar")
        if not link or not link.get("href"):
            continue
            
        href_parts = [p for p in link["href"].strip("/").split("/") if p]
        if not href_parts:
            continue
            
        username = href_parts[-1].lower()
        
        if username in SISTEM_URL_ENGEL:
            continue
            
        img = s.select_one("img")
        img_url = "https://s.ltrbxd.com/static/img/avatar220.png"
        if img:
            img_url = img.get("src") or img.get("data-src") or img_url
            
        kisiler[username] = img_url
        
    return kisiler

def extract_max_page(html):
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")
        
    max_page = 1
    pagination_links = soup.select(".paginate-pages a, .pagination a, div.pagination li a, .paginate-nextprev a")
    
    for a in pagination_links:
        href = a.get("href", "")
        match = re.search(r"/page/(\d+)/", href)
        if match:
            p = int(match.group(1))
            if p > max_page:
                max_page = p
                
        text = a.get_text(strip=True)
        if text.isdigit():
            p = int(text)
            if p > max_page:
                max_page = p
                
    return max_page

async def fetch_page(session, url, kullanici_adi, max_retries=4, sem=None):
    # curl_cffi kendi TLS parmak izini ürettiği için sahte User-Agent vermiyoruz
    extra_headers = {
        "Referer": f"https://letterboxd.com/{kullanici_adi}/",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
    }
    
    async def _req():
        last_status = 0
        for attempt in range(max_retries):
            try:
                await asyncio.sleep(random.uniform(0.1, 0.3))
                res = await session.get(
                    url, 
                    impersonate="chrome124", 
                    headers=extra_headers, 
                    timeout=15
                )
                
                if res.status_code == 404:
                    return 404, ""
                    
                if res.status_code == 200 and "Just a moment" not in res.text:
                    if "person-summary" in res.text or "paginate-pages" in res.text or "table-person" in res.text or "No one yet" in res.text:
                        return 200, res.text
                        
                last_status = res.status_code
                await asyncio.sleep(0.5 + (attempt * 0.5))
            except Exception as e:
                last_status = f"ERR: {str(e)}"
                await asyncio.sleep(0.5)
        return last_status, ""

    if sem:
        async with sem:
            return await _req()
    return await _req()

async def scrape_target(session, kullanici_adi, tip, sem):
    first_url = f"https://letterboxd.com/{kullanici_adi}/{tip}/"
    status, html = await fetch_page(session, first_url, kullanici_adi)
    
    if status == 404:
        return None
    if status != 200:
        return f"BLOK: {status}"
    
    kisiler = parse_page_users(html)
    max_page = extract_max_page(html)

    if max_page > 1:
        tasks = [
            fetch_page(session, f"https://letterboxd.com/{kullanici_adi}/{tip}/page/{p}/", kullanici_adi, sem=sem)
            for p in range(2, max_page + 1)
        ]
        results = await asyncio.gather(*tasks)
        
        for st_code, page_html in results:
            if st_code == 200:
                kisiler.update(parse_page_users(page_html))
            else:
                return f"BLOK: {st_code}"

    return kisiler

async def main_async(kullanici_adi, proxy_url):
    proxies = {"http": proxy_url, "https": proxy_url}
    # Cloudflare rate-limit yememek için eşzamanlı sayfa çekimini 4'te sabitliyoruz
    sem = asyncio.Semaphore(4)
    
    async with AsyncSession(proxies=proxies) as session:
        res_following, res_followers = await asyncio.gather(
            scrape_target(session, kullanici_adi, "following", sem),
            scrape_target(session, kullanici_adi, "followers", sem)
        )
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
        with st.spinner("Tarama başlatılıyor... Lütfen bekleyiniz."):
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
