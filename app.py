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

def parse_page_users(html):
    soup = BeautifulSoup(html, "html.parser")
    satirlar = soup.find_all("div", class_="person-summary")
    kisiler = {}
    for s in satirlar:
        # Doğrudan profile giden linki ve avatarı yakala
        a = s.find("a", class_="avatar") or s.find("a", class_="name")
        if a and a.get("href"):
            raw_href = a["href"].strip("/")
            username = raw_href.split("/")[-1].lower()

            img = s.find("img")
            img_url = img["src"] if (img and img.get("src")) else "https://s.ltrbxd.com/static/img/avatar220.png"
            if username:
                kisiler[username] = img_url
    return kisiler

async def fetch_page(session, url, proxy_url, kullanici_adi, max_retries=5, sem=None):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": f"https://letterboxd.com/{kullanici_adi}/",
    }
    proxies = {"http": proxy_url, "https": proxy_url}

    async def _req():
        last_status = 0
        for attempt in range(max_retries):
            try:
                # İstekleri paralel ateşlerken hepsi aynı anda gitmesin diye
                # ufak, rastgele bir başlangıç gecikmesi
                await asyncio.sleep(random.uniform(0.15, 0.6))

                # Aynı hedef için paylaşılan session kullanıyoruz ki
                # Cloudflare'ın verdiği cookie/clearance sayfalar arasında taşınsın
                res = await session.get(url, proxies=proxies, impersonate="chrome120", headers=headers, timeout=15)

                if res.status_code == 404:
                    return 404, ""
                if res.status_code == 200 and "Cloudflare" not in res.text and "Just a moment" not in res.text:
                    return 200, res.text

                last_status = res.status_code
                if res.status_code == 403:
                    # 403 = Cloudflare/anti-bot bloğu. Hemen tekrar denemek
                    # genelde aynı sonucu verir, daha uzun bekleyip tekrar deneriz.
                    await asyncio.sleep(random.uniform(3.0, 6.0) * (attempt + 1))
                else:
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
    # Bir hedef (following/followers) için TÜM sayfalarda aynı session'ı
    # kullanıyoruz ki Cloudflare'ın 1. sayfada verdiği cookie/clearance
    # sonraki sayfalara da taşınsın (403'lerin başlıca sebebi buydu).
    async with AsyncSession() as session:
        first_url = f"https://letterboxd.com/{kullanici_adi}/{tip}/"
        status, html = await fetch_page(session, first_url, proxy_url, kullanici_adi)

        if status == 404:
            return None
        if status != 200:
            return f"BLOK: {status}"

        kisiler = parse_page_users(html)

        # İlk sayfa boşsa (hiç takipçi/takip edilen yoksa) direkt dön
        if not kisiler:
            return kisiler

        # --- PAGINATION MANTIĞI ---
        # Letterboxd artık numaralı sayfa linkleri (1 2 3 4 ...) sunmuyor,
        # bu yüzden toplam sayfa sayısını önceden kestirmiyoruz.
        # Küçük gruplar halinde istek atıp, bir grup içinde boş/404
        # bir sayfaya rastlayana kadar devam ediyoruz. Eşzamanlılık
        # bilinçli olarak düşük tutuluyor (403 riskini azaltmak için).
        sem = asyncio.Semaphore(2)
        page = 2
        batch_size = 2

        while True:
            page_numbers = list(range(page, page + batch_size))
            tasks = [
                fetch_page(
                    session,
                    f"https://letterboxd.com/{kullanici_adi}/{tip}/page/{p}/",
                    proxy_url, kullanici_adi, sem=sem
                )
                for p in page_numbers
            ]
            results = await asyncio.gather(*tasks)

            reached_end = False
            for p, (st_code, page_html) in zip(page_numbers, results):
                if st_code == 404:
                    reached_end = True
                    continue
                if st_code != 200:
                    return f"BLOK: {st_code} (sayfa {p})"

                page_users = parse_page_users(page_html)
                if not page_users:
                    # Bu sayfa boş -> listenin sonuna gelmişiz demektir
                    reached_end = True
                    continue

                kisiler.update(page_users)

            if reached_end:
                break

            page += batch_size

    return kisiler

async def main_async(kullanici_adi, proxy_url):
    res_following, res_followers = await asyncio.gather(
        scrape_target(kullanici_adi, "following", proxy_url),
        scrape_target(kullanici_adi, "followers", proxy_url)
    )
    return res_following, res_followers

# Cache süresini kapattık ki eski hatalı aramaları hafızadan basmasın
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
            st.error("Sistem geçiçi olarak çalışmıyor lütfen daha sonra tekrar deneyiniz. (Hata: Proxy Secret Ayarı Yok)")
        elif isinstance(following, str) and following.startswith("BLOK"):
            st.error(f"Sistem geçiçi olarak çalışmıyor lütfen daha sonra tekrar deneyiniz. (Detay: Following {following})")
        elif isinstance(followers, str) and followers.startswith("BLOK"):
            st.error(f"Sistem geçiçi olarak çalışmıyor lütfen daha sonra tekrar deneyiniz. (Detay: Followers {followers})")
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
