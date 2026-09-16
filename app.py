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

YASAKLI_LINKLER = {
    "films", "reviews", "lists", "activity", "members", "following", 
    "followers", "likes", "watchlist", "diary", "tags", "about", "stats", ""
}

def parse_page_users(html):
    soup = BeautifulSoup(html, "html.parser")
    kisiler = {}
    
    # 1. Ana tablo veya ana gövdeyi sınırla (sidebar'ı kesinlikle alma)
    ana_alan = soup.find("table", class_="person-table") or soup.find("section", id="content") or soup.find("div", id="content")
    if not ana_alan:
        ana_alan = soup

    satirlar = ana_alan.find_all("div", class_="person-summary")
    
    for s in satirlar:
        # Kenar çubuğu içindeki elemanları tamamen ele
        if s.find_parent("aside") or s.find_parent("div", class_="sidebar") or s.find_parent("section", class_="sidebar"):
            continue
            
        a = s.find("a", class_="avatar") or s.find("a", class_="name")
        if a and a.get("href"):
            raw_href = a["href"].strip("/")
            parts = [p for p in raw_href.split("/") if p]
            if not parts:
                continue
            username = parts[-1].lower()
            
            if username in YASAKLI_LINKLER:
                continue
                
            img = s.find("img")
            img_url = img["src"] if (img and img.get("src")) else "https://s.ltrbxd.com/static/img/avatar220.png"
            if username:
                kisiler[username] = img_url
    return kisiler

def extract_max_page(html):
    soup = BeautifulSoup(html, "html.parser")
    max_page = 1
    
    # Letterboxd'ın sayfalama konteynerleri: .paginate-pages, .pagination, .paginate-nextprev
    # 1. Yöntem: Sayfalama konteyneri içindeki tüm li ve a etiketlerindeki sayıları topla
    pagination_containers = soup.select(".paginate-pages, .pagination, div.paginate-pages, ul.paginate-pages")
    for container in pagination_containers:
        for tag in container.find_all(["li", "a"]):
            # URL içindeki /page/X/ kontrolü
            href = tag.get("href", "")
            match = re.search(r"/page/(\d+)/", href)
            if match:
                p = int(match.group(1))
                if p > max_page:
                    max_page = p
            
            # Etiket içindeki doğrudan metin sayısı kontrolü
            text = tag.get_text(strip=True)
            if text.isdigit():
                p = int(text)
                if p > max_page:
                    max_page = p
                    
    # 2. Yöntem: Genel HTML içinde kaçırılan herhangi bir /page/X/ linki varsa al
    if max_page == 1:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/page/" in href:
                match = re.search(r"/page/(\d+)/", href)
                if match:
                    p = int(match.group(1))
                    if p > max_page:
                        max_page = p

    # 3. Yöntem: Next butonu var ama sayfa sayısı tespit edilemediyse en az 2 sayfa vardır
    if max_page == 1 and soup.select("a.next, .paginate-next a, a[rel='next']"):
        max_page = 2
        
    return max_page

async def fetch_page(url, proxy_url, kullanici_adi, max_retries=5, sem=None):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": f"https://letterboxd.com/{kullanici_adi}/",
    }
    proxies = {"http": proxy_url, "https": proxy_url}
    
    async def _req():
        last_status = 0
        for _ in range(max_retries):
            try:
                async with AsyncSession() as s:
                    res = await s.get(url, proxies=proxies, impersonate="chrome120", headers=headers, timeout=15)
                    if res.status_code == 404:
                        return 404, ""
                    if res.status_code == 200 and "Cloudflare" not in res.text and "Just a moment" not in res.text:
                        if "person-summary" in res.text or "paginate-pages" in res.text or "pagination" in res.text or "No one yet" in res.text:
                            return 200, res.text
                    last_status = res.status_code
                    await asyncio.sleep(random.uniform(0.5, 1.0))
            except Exception as e:
                last_status = f"ERR: {str(e)}"
                await asyncio.sleep(0.5)
        return last_status, ""

    if sem:
        async with sem:
            return await _req()
    return await _req()

async def scrape_target(kullanici_adi, tip, proxy_url):
    first_url = f"https://letterboxd.com/{kullanici_adi}/{tip}/"
    status, html = await fetch_page(first_url, proxy_url, kullanici_adi)
    
    if status == 404:
        return None
    if status != 200:
        return f"BLOK: {status}"
    
    kisiler = parse_page_users(html)
    max_page = extract_max_page(html)

    # 2. ve sonraki sayfaları kesin olarak döngüye sokar
    if max_page > 1:
        sem = asyncio.Semaphore(3)
        tasks = [
            fetch_page(f"https://letterboxd.com/{kullanici_adi}/{tip}/page/{p}/", proxy_url, kullanici_adi, sem=sem)
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
    res_following, res_followers = await asyncio.gather(
        scrape_target(kullanici_adi, "following", proxy_url),
        scrape_target(kullanici_adi, "followers", proxy_url)
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
        with st.spinner("Tarama başlatılıyor... Takipçi ve takip edilen sayınızın yoğunluğuna bağlı olarak işlemin süresi değişiklik gösterebilir. Lütfen bekleyiniz."):
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
                baslik = "Takip etmeyenler"
            else:
                sonuc = {u: followers[u] for u in followers if u not in following}
                baslik = "Senin takip etmediklerin"

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
