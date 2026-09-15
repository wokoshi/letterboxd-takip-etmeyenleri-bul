import streamlit as st
from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession
import asyncio
import random
import re
import string

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

def get_fresh_proxy(base_proxy):
    rand_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    if "__session-" in base_proxy:
        return re.sub(r"__session-[^:@]+", f"__session-{rand_id}", base_proxy)
    elif "@" in base_proxy:
        p = base_proxy.split("@")
        return f"{p[0]}__session-{rand_id}@{p[1]}"
    return base_proxy

def parse_page_users(html):
    soup = BeautifulSoup(html, "html.parser")
    satirlar = soup.find_all("div", class_="person-summary")
    kisiler = {}
    for s in satirlar:
        a = s.find("a", class_="name")
        if a:
            username = a["href"].strip("/")
            img = s.find("img")
            img_url = img["src"] if img else "https://s.ltrbxd.com/static/img/avatar220.png"
            kisiler[username] = img_url
    return kisiler

async def fetch_page(url, raw_proxy, kullanici_adi, max_retries=5, sem=None):
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": f"https://letterboxd.com/{kullanici_adi}/",
    }
    
    async def _req():
        for _ in range(max_retries):
            px = get_fresh_proxy(raw_proxy)
            proxies = {"http": px, "https": px}
            try:
                async with AsyncSession() as s:
                    res = await s.get(url, proxies=proxies, impersonate="chrome124", headers=headers, timeout=10)
                    if res.status_code == 404:
                        return 404, ""
                    if res.status_code != 200 or "Cloudflare" in res.text or "Just a moment" in res.text:
                        await asyncio.sleep(random.uniform(0.4, 0.8))
                        continue
                    return 200, res.text
            except Exception:
                await asyncio.sleep(0.3)
        return 0, ""

    if sem:
        async with sem:
            return await _req()
    return await _req()

async def scrape_target(kullanici_adi, tip, raw_proxy):
    first_url = f"https://letterboxd.com/{kullanici_adi}/{tip}/"
    status, html = await fetch_page(first_url, raw_proxy, kullanici_adi)
    
    if status == 404:
        return None
    if status != 200:
        return "BLOK"
    
    kisiler = parse_page_users(html)
    if not kisiler:
        return {}
    
    soup = BeautifulSoup(html, "html.parser")
    pagination_links = soup.select("div.paginate-pages li a")
    max_page = 1
    for a in pagination_links:
        href = a.get("href", "")
        match = re.search(r"/page/(\d+)/", href)
        if match:
            page_num = int(match.group(1))
            if page_num > max_page:
                max_page = page_num

    if max_page > 1:
        sem = asyncio.Semaphore(6)
        tasks = [
            fetch_page(f"https://letterboxd.com/{kullanici_adi}/{tip}/page/{p}/", raw_proxy, kullanici_adi, sem=sem)
            for p in range(2, max_page + 1)
        ]
        results = await asyncio.gather(*tasks)
        
        for st_code, page_html in results:
            if st_code == 200:
                kisiler.update(parse_page_users(page_html))
            else:
                return "BLOK"

    return kisiler

async def main_async(kullanici_adi, raw_proxy):
    res_following, res_followers = await asyncio.gather(
        scrape_target(kullanici_adi, "following", raw_proxy),
        scrape_target(kullanici_adi, "followers", raw_proxy)
    )
    return res_following, res_followers

@st.cache_data(ttl=1800, show_spinner=False)
def analiz_calistir(kullanici_adi):
    try:
        raw_proxy = st.secrets["DATAIMPULSE_PROXY"]
    except Exception:
        return "PROXY_ERROR", "PROXY_ERROR"
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    return loop.run_until_complete(main_async(kullanici_adi, raw_proxy))

if st.button("Analizi Başlat 🎬"):

    if not hedef_kullanici:
        st.warning("Kullanıcı adınızı giriniz")
    else:
        with st.spinner("Tarama başlatılıyor... Takipçi ve takip edilen sayınızın yoğunluğuna bağlı olarak işlemin süresi değişiklik gösterebilir. Lütfen bekleyiniz."):
            following, followers = analiz_calistir(hedef_kullanici.strip().lower())

        if following == "PROXY_ERROR" or followers == "PROXY_ERROR":
            st.error("Proxy bağlantısı kurulamadı.")
        elif following == "BLOK" or followers == "BLOK":
            st.error("Sistem geçiçi olarak çalışmıyor lütfen daha sonra tekrar deneyiniz.")
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
