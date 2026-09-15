import streamlit as st
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

# Hızlı Regex derlemeleri (BeautifulSoup yerine mikro saniyede parse)
USER_BLOCK_RE = re.compile(r'<div class="person-summary">([\s\S]*?)</div>\s*</div>', re.IGNORECASE)
HREF_RE = re.compile(r'href="/([^"/]+)/"', re.IGNORECASE)
IMG_RE = re.compile(r'src="([^"]+)"', re.IGNORECASE)
PAGE_RE = re.compile(r'/page/(\d+)/')

def parse_fast(html):
    kisiler = {}
    blocks = USER_BLOCK_RE.findall(html)
    for b in blocks:
        u_match = HREF_RE.search(b)
        if u_match:
            u = u_match.group(1).lower()
            # Sistem linklerini ele
            if u in ["films", "reviews", "lists", "activity"]:
                continue
            img_match = IMG_RE.search(b)
            img_url = img_match.group(1) if img_match else "https://s.ltrbxd.com/static/img/avatar220.png"
            kisiler[u] = img_url
    return kisiler

async def fetch_page(url, proxy_url, kullanici_adi, sem=None):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": f"https://letterboxd.com/{kullanici_adi}/",
    }
    proxies = {"http": proxy_url, "https": proxy_url}

    async def _do():
        for _ in range(4):
            try:
                async with AsyncSession() as s:
                    res = await s.get(url, proxies=proxies, impersonate="chrome120", headers=headers, timeout=9)
                    if res.status_code == 404:
                        return 404, ""
                    if res.status_code == 200 and "Just a moment" not in res.text:
                        return 200, res.text
                    await asyncio.sleep(0.3)
            except Exception:
                await asyncio.sleep(0.2)
        return 0, ""

    if sem:
        async with sem:
            return await _do()
    return await _do()

async def scrape_target(kullanici_adi, tip, proxy_url):
    first_url = f"https://letterboxd.com/{kullanici_adi}/{tip}/"
    status, html = await fetch_page(first_url, proxy_url, kullanici_adi)
    
    if status == 404:
        return None
    if status != 200:
        return f"BLOK: {status}"
    
    kisiler = parse_fast(html)
    
    # Toplam sayfa sayısını bul
    pages = [int(p) for p in PAGE_RE.findall(html)]
    max_page = max(pages) if pages else 1

    if max_page > 1:
        sem = asyncio.Semaphore(8)  # Concurrency artırıldı
        tasks = [
            fetch_page(f"https://letterboxd.com/{kullanici_adi}/{tip}/page/{p}/", proxy_url, kullanici_adi, sem=sem)
            for p in range(2, max_page + 1)
        ]
        results = await asyncio.gather(*tasks)
        
        for st_code, page_html in results:
            if st_code == 200:
                kisiler.update(parse_fast(page_html))
            else:
                return f"BLOK: {st_code}"

    return kisiler

async def main_async(kullanici_adi, proxy_url):
    # İki liste aynı anda paralel çekilir
    return await asyncio.gather(
        scrape_target(kullanici_adi, "following", proxy_url),
        scrape_target(kullanici_adi, "followers", proxy_url)
    )

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
        with st.spinner("Tarama paralel olarak yapılıyor, lütfen bekleyiniz..."):
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
