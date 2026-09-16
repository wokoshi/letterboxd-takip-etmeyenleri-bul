import streamlit as st
from bs4 import BeautifulSoup
import asyncio
import re
import os

st.set_page_config(page_title="Letterboxd Takip Analizi", page_icon="🔍", layout="centered")

@st.cache_resource
def setup_playwright():
    os.system("playwright install chromium")

setup_playwright()

from playwright.async_api import async_playwright

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

YASAKLI = {"films", "reviews", "lists", "activity", "members", "following", "followers", "likes", "watchlist", "diary", "tags", "about", "stats", ""}

def parse_page_users(html):
    soup = BeautifulSoup(html, "html.parser")
    kisiler = {}
    
    # 1. Kenar çubuğunu (sidebar) HTML'den kökten kazı (o 9 sahte kişiyi yok et)
    for sidebar in soup.select("aside, .sidebar, #sidebar, div.sidebar, section.sidebar"):
        sidebar.decompose()
        
    # 2. Artık sayfada sadece ana akış kaldı; tüm person-summary kartlarını al
    satirlar = soup.find_all("div", class_="person-summary")
    for s in satirlar:
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

def extract_total_pages(html):
    soup = BeautifulSoup(html, "html.parser")
    max_page = 1
    
    # Letterboxd sayfalandırma linklerini yakala
    for a in soup.select(".paginate-pages a, .pagination a, a.paginate-page"):
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

async def scrape_letterboxd(kullanici_adi, tip):
    kisiler = {}
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        web_page = await context.new_page()

        # 1. İlk sayfayı yükle
        first_url = f"https://letterboxd.com/{kullanici_adi}/{tip}/"
        try:
            res = await web_page.goto(first_url, wait_until="domcontentloaded", timeout=30000)
            if res and res.status == 404:
                await browser.close()
                return None
                
            await web_page.wait_for_timeout(1500)
            content = await web_page.content()
            
            if "Just a moment..." in content or "Checking your browser" in content:
                await web_page.wait_for_timeout(3000)
                content = await web_page.content()

            kisiler.update(parse_page_users(content))
            total_pages = extract_total_pages(content)
            
            # 2. Eğer birden fazla sayfa varsa sırayla gez
            if total_pages > 1:
                for page_num in range(2, total_pages + 1):
                    next_url = f"https://letterboxd.com/{kullanici_adi}/{tip}/page/{page_num}/"
                    await web_page.goto(next_url, wait_until="domcontentloaded", timeout=30000)
                    await web_page.wait_for_timeout(1000)
                    page_content = await web_page.content()
                    kisiler.update(parse_page_users(page_content))
                    
        except Exception as e:
            await browser.close()
            return f"HATA: {str(e)}"

        await browser.close()
    return kisiler

async def main_async(kullanici_adi):
    res_following = await scrape_letterboxd(kullanici_adi, "following")
    if isinstance(res_following, str) and res_following.startswith("HATA"):
        return res_following, None
        
    await asyncio.sleep(0.5)
    res_followers = await scrape_letterboxd(kullanici_adi, "followers")
    return res_following, res_followers

def analiz_calistir(kullanici_adi):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(main_async(kullanici_adi))

if st.button("Analizi Başlat 🎬"):
    if not hedef_kullanici:
        st.warning("Kullanıcı adınızı giriniz")
    else:
        with st.spinner("Tarama yapılıyor... Lütfen bekleyiniz."):
            cleaned_username = hedef_kullanici.strip().lower()
            following, followers = analiz_calistir(cleaned_username)

        if isinstance(following, str) and following.startswith("HATA"):
            st.error(f"Sistem geçici olarak çalışmıyor lütfen daha sonra tekrar deneyiniz. (Detay: Following {following})")
        elif isinstance(followers, str) and followers.startswith("HATA"):
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
