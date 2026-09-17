import streamlit as st
from bs4 import BeautifulSoup
import asyncio
import os

st.set_page_config(page_title="Letterboxd Takip Analizi", page_icon="🔍", layout="centered")

# Playwright Chromium motorunu kur
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

def parse_cards(html):
    soup = BeautifulSoup(html, 'html.parser')
    kisiler = {}
    satirlar = soup.find_all('div', class_='person-summary')
    for s in satirlar:
        a = s.find('a', class_='name')
        if a and a.get('href'):
            username = a['href'].strip('/')
            img = s.find('img')
            img_url = img['src'] if img and img.get('src') else "https://s.ltrbxd.com/static/img/avatar220.png"
            kisiler[username] = img_url
    return kisiler

async def fetch_relation_list(browser, username, relation_type):
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 800},
        locale="en-US"
    )
    
    # Tarayıcıyı bot gibi gösteren navigator.webdriver bayrağını gizle
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
    """)

    page = await context.new_page()
    page_num = 1
    users_dict = {}

    while True:
        url = f"https://letterboxd.com/{username}/{relation_type}/page/{page_num}/" if page_num > 1 else f"https://letterboxd.com/{username}/{relation_type}/"
        try:
            res = await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            if res and res.status == 404:
                if page_num == 1:
                    await context.close()
                    return None
                break

            await page.wait_for_timeout(1000)
            content = await page.content()
            
            parsed = parse_cards(content)
            if not parsed:
                break

            users_dict.update(parsed)

            soup = BeautifulSoup(content, 'html.parser')
            has_next = soup.select("a.next, .paginate-next a, a[rel='next']")
            if not has_next:
                break

            page_num += 1
        except Exception:
            break

    await context.close()
    return users_dict

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
        await asyncio.sleep(0.5)
        followers = await fetch_relation_list(browser, username, "followers")
        await browser.close()
        return following, followers

if st.button("Analizi Başlat 🎬"):
    if not hedef_kullanici:
        st.warning("Kullanıcı adınızı giriniz")
    else:
        with st.spinner("Tarama başlatılıyor... Lütfen bekleyiniz."):
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
