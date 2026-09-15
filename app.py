import streamlit as st
from curl_cffi import requests as cureq
import time
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

img { border-radius: 10px; object-fit: cover; }

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

USER_ROW_RE = re.compile(r'<div class="person-summary">[\s\S]*?<a class="(?:avatar|name)" href="/([^"/]+)/"[\s\S]*?(?:<img[^>]+src="([^"]+)")?', re.IGNORECASE)
PAGE_NUM_RE = re.compile(r'/page/(\d+)/', re.IGNORECASE)

def parse_html_fast(html):
    kisiler = {}
    matches = USER_ROW_RE.findall(html)
    for u, img in matches:
        u_clean = u.lower().strip()
        if u_clean in ["films", "reviews", "lists", "activity", "members"]:
            continue
        img_url = img if img else "https://s.ltrbxd.com/static/img/avatar220.png"
        kisiler[u_clean] = img_url
    return kisiler

def find_pages(html):
    matches = PAGE_NUM_RE.findall(html)
    if matches:
        return max([int(m) for m in matches])
    return 1

def request_page(url, proxy_url, referer, max_retries=4):
    proxies = {"http": proxy_url, "https": proxy_url}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Referer": referer,
    }

    last_error = ""
    for deneme in range(max_retries):
        try:
            # Her istekte temiz bağlantı açarak Cloudflare IP takibini kırıyoruz
            res = cureq.get(
                url,
                proxies=proxies,
                impersonate="chrome120",
                headers=headers,
                timeout=18
            )
            if res.status_code == 404:
                return 404, ""
            if res.status_code == 200:
                if "Just a moment" in res.text or "Cloudflare" in res.text:
                    last_error = "Cloudflare Challenge"
                else:
                    return 200, res.text
            else:
                last_error = f"HTTP {res.status_code}"
            time.sleep(1.0)
        except Exception as e:
            last_error = str(e)
            time.sleep(1.0)
    return 0, last_error

def veri_cek(kullanici_adi, tip, proxy_url):
    kisiler = {}
    first_url = f"https://letterboxd.com/{kullanici_adi}/{tip}/"
    base_ref = f"https://letterboxd.com/{kullanici_adi}/"

    status, html_1 = request_page(first_url, proxy_url, referer=base_ref)
    if status == 404:
        return None
    if status != 200:
        return f"BLOK: 1. sayfa açılamadı ({html_1})"

    kisiler.update(parse_html_fast(html_1))
    max_page = find_pages(html_1)

    prev_url = first_url
    for p in range(2, max_page + 1):
        page_url = f"https://letterboxd.com/{kullanici_adi}/{tip}/page/{p}/"
        st_code, p_html = request_page(page_url, proxy_url, referer=prev_url)
        if st_code != 200:
            return f"BLOK: Sayfa {p} açılamadı ({p_html})"
        kisiler.update(parse_html_fast(p_html))
        prev_url = page_url
        time.sleep(random.uniform(0.4, 0.8))

    return kisiler

if st.button("Analizi Başlat 🎬"):

    if not hedef_kullanici:
        st.warning("Kullanıcı adınızı giriniz")
    else:
        with st.spinner("Tarama başlatılıyor... Takipçi ve takip edilen sayınızın yoğunluğuna bağlı olarak işlemin süresi değişiklik gösterebilir. Lütfen bekleyiniz."):
            try:
                proxy_url = st.secrets["DATAIMPULSE_PROXY"]
            except Exception:
                proxy_url = None

            if not proxy_url:
                st.error("Proxy ayarı (Secrets) bulunamadı.")
            else:
                user_clean = hedef_kullanici.strip().lower()
                following = veri_cek(user_clean, "following", proxy_url)
                followers = veri_cek(user_clean, "followers", proxy_url)

                if isinstance(following, str) and following.startswith("BLOK"):
                    st.error(f"Following hatası: {following}")
                elif isinstance(followers, str) and followers.startswith("BLOK"):
                    st.error(f"Followers hatası: {followers}")
                elif following is None or followers is None:
                    st.error("Bu kullanıcı adıyla ilgili hesap bulunmuyor. Kullanıcı adınızı kontrol ediniz.")
                else:
                    following_set = set(following.keys())
                    followers_set = set(followers.keys())

                    if islem_modu == "Beni Takip Etmeyenler":
                        hedef_set = following_set - followers_set
                        sonuc = {u: following[u] for u in hedef_set}
                    else:
                        hedef_set = followers_set - following_set
                        sonuc = {u: followers[u] for u in hedef_set}

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
                                        <img src="{img}" width="50" height="50">
                                        <div>
                                            <b>{usr}</b><br>
                                            <a href="https://letterboxd.com/{usr}/" target="_blank">Profile git</a>
                                        </div>
                                    </div>
                                    """, unsafe_allow_html=True)

st.markdown("<div class='footer-sig'>Created by <a href='https://letterboxd.com/wokoshi/' target='_blank'>wokoshi</a></div>", unsafe_allow_html=True)
