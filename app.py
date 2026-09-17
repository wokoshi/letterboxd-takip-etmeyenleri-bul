import streamlit as st
from bs4 import BeautifulSoup
import asyncio
import math
import os

st.set_page_config(page_title="Letterboxd Takip Analizi", page_icon="🔍", layout="centered")

@st.cache_resource
def setup_browser_engine():
    os.system("playwright install chromium")

setup_browser_engine()

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

def extract_users(html):
    soup = BeautifulSoup(html, 'html.parser')
    users = {}
    
    # Sadece ana gövdedeki tabloyu ve person kartlarını hedefle
    main_section = soup.select_one("div#content, section#content, div.site-body")
    target_soup = main_section if main_section else soup
    
    # Kenar çubuğunu temizle
    for s in target_soup.select("aside, .sidebar, #sidebar, div.sidebar"):
        s.decompose()

    cards = target_soup.select("table.person-table tr, div.person-summary")
    for card in cards:
        a = card.find('a', class_='name')
        if a and a.get('href'):
            parts = a['href'].strip('/').split('/')
            if parts:
                uname = parts[-1].lower()
                img = card.find('img')
                img_url = img['src'] if img and img.get('src') else "https://s.ltrbxd.com/static/img/avatar220.png"
                users[uname] = img_url

    return users

async def wait_for_letterboxd_page(page, url):
    # Cloudflare challenge kontrolü ve bekleme mekanizması
    for attempt in range(3):
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(1500)
        
        title = await page.title()
        content = await page.content()
        
        # Eğer Cloudflare ekranı gelirse çözülmesi için bekle
        if "Just a moment" in title or "Cloudflare" in content:
            await page.wait_for_timeout(3500)
            title = await page.title()
            
        if "Just a moment" not in title:
            return content
            
        await page.wait_for_timeout(2000)
    
    return await page.content()

async def fetch_relation_list(browser, username, relation_type):
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        viewport={"width": 1366, "height": 768},
        locale="en-US"
    )
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        window.navigator.chrome = { runtime: {} };
    """)
    page = await context.new_page()

    all_users = {}
    page_num = 1

    while True:
        url = f"https://letterboxd.com/{username}/{relation_type}/page/{page_num}/" if page_num > 1 else f"https://letterboxd.com/{username}/{relation_type}/"
        
        try:
            content = await wait_for_letterboxd_page(page, url)
            
            # Sayfa 404 mü veya hesap yok mu?
            if "Page not found" in content and page_num == 1:
                await context.close()
                return None

            page_users = extract_users(content)
            
            # Eğer hiç kullanıcı gelmediyse ve hala Cloudflare'deyse dur
            if not page_users:
                break

            all_users.update(page_users)

            # Sayfalamada 'Next' butonu var mı kontrolü
            soup = BeautifulSoup(content, 'html.parser')
            has_next = soup.select("a.next, .paginate-next a, a[rel='next']")
            
            if not has_next:
                break

            page_num += 1
            await page.wait_for_timeout(1200) # Cloudflare ratelimit yememek için bekleme

        except Exception as e:
            break

    await context.close()
    return all_users

async def execute_scraping(username):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled"
            ]
        )
        following = await fetch_relation_list(browser, username, "following")
        await asyncio.sleep(1)
        followers = await fetch_relation_list(browser, username, "followers")
        await browser.close()
        return following, followers

if st.button("Analizi Başlat 🎬"):
    if not hedef_kullanici:
        st.warning("Kullanıcı adınızı giriniz")
    else:
        with st.spinner("Tarama başlatılıyor... Cloudflare doğrulamaları aşılıyor, lütfen bekleyiniz."):
            cleaned = hedef_kullanici.strip().lower()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            following, followers = loop.run_until_complete(execute_scraping(cleaned))

        if following is None or followers is None:
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
