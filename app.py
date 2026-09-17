import streamlit as st
from bs4 import BeautifulSoup
from curl_cffi import requests as cureq
import time
import random

# ayar
st.set_page_config(page_title="Letterboxd Takip Analizi", page_icon="🔍", layout="centered")

# css
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

.stApp { 
    background-color: #0c120e; 
    color: #9ab; 
    font-family: 'Inter', -apple-system, sans-serif;
}

.custom-title {
    color: #ffffff;
    font-size: 2.1rem;
    font-weight: 800;
    text-align: center;
    letter-spacing: -0.5px;
    margin-top: 0.5rem;
}

.custom-subtitle {
    text-align: center;
    color: #6a7c70;
    font-size: 0.95rem;
    margin-bottom: 2rem;
}

/* Radio Butonları */
div[role="radiogroup"] {
    justify-content: center;
    gap: 2rem;
    margin-bottom: 1.2rem;
}

div[role="radiogroup"] label {
    background: #131c16;
    padding: 8px 16px;
    border-radius: 20px;
    border: 1px solid #1e2c22;
    transition: all 0.2s ease;
}

div[role="radiogroup"] label:hover {
    border-color: #00e054;
}

/* Input Alanı */
div[data-baseweb="input"] {
    background-color: #121a14 !important;
    border: 1px solid #1f2e23 !important;
    border-radius: 12px !important;
    transition: all 0.2s ease;
}

div[data-baseweb="input"]:focus-within {
    border-color: #00e054 !important;
    box-shadow: 0 0 0 1px #00e054 !important;
}

/* Analiz Butonu */
.stButton>button {
    background: linear-gradient(135deg, #00e054 0%, #00b341 100%);
    color: #0a110c;
    font-weight: 700;
    font-size: 1rem;
    border-radius: 12px;
    border: none;
    padding: 0.65rem 1rem;
    width: 100%;
    margin-top: 0.5rem;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    box-shadow: 0 4px 14px rgba(0, 224, 84, 0.25);
}

.stButton>button:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(0, 224, 84, 0.4);
    color: #000000;
}

.stButton>button:active {
    transform: translateY(0px);
}

/* Kullanıcı Kartları */
.card {
    background: #131b15;
    border: 1px solid #1c2920;
    padding: 10px 14px;
    border-radius: 14px;
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;
    transition: all 0.2s ease;
}

.card:hover {
    border-color: #00e054;
    transform: translateY(-2px);
    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.35);
}

.card img {
    border-radius: 50%;
    width: 46px;
    height: 46px;
    object-fit: cover;
    border: 1.5px solid #233529;
}

.card b {
    color: #ffffff;
    font-size: 0.95rem;
    font-weight: 600;
}

.card a {
    color: #00e054;
    font-size: 0.8rem;
    text-decoration: none;
    font-weight: 500;
    transition: color 0.15s ease;
}

.card a:hover {
    text-decoration: underline;
    color: #40ff7d;
}

/* Footer */
.footer-sig {
    text-align: center;
    color: #5A6E5E;
    font-size: 14px;
    margin-top: 3.5rem;
    padding-top: 1.2rem;
    border-top: 1px solid #1A2E20;
    width: 60%;
    opacity: 0.9;
    margin-left: auto;
    margin-right: auto;
}

.footer-sig a {
    color: #00e054;
    text-decoration: none;
    font-weight: 600;
}

.footer-sig a:hover {
    text-decoration: underline;
}
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='custom-title'>🔍 Letterboxd Takip Analizi</div>", unsafe_allow_html=True)
st.markdown("<div class='custom-subtitle'>Hesabınızın takipçi ve takip edilen durumunu tek tuşla öğrenin.</div>", unsafe_allow_html=True)

# mod
islem_modu = st.radio(
    "",
    ["Beni Takip Etmeyenler", "Benim Takip Etmediklerim"],
    horizontal=True
)

hedef_kullanici = st.text_input("Kullanıcı adınızı giriniz:")

# veri
@st.cache_data(ttl=1800, show_spinner=False)
def veri_cek(kullanici_adi, tip):
    kisiler = {}
    
    try:
        PROXY_URL = st.secrets["DEXODATA_PROXY"]
    except:
        return "PROXY_ERROR"
        
    proxies = {"http": PROXY_URL, "https": PROXY_URL}
    session = cureq.Session()

    sayfa = 1

    while True:
        url = f"https://letterboxd.com/{kullanici_adi}/{tip}/" if sayfa == 1 else f"https://letterboxd.com/{kullanici_adi}/{tip}/page/{sayfa}/"
        sayfa_basarili = False

        for deneme in range(10):

            if deneme > 0:
                time.sleep(random.uniform(0.6, 1.4))

            try:
                res = session.get(url, proxies=proxies, impersonate="chrome120", timeout=20)

                if res.status_code == 404:
                    return None if sayfa == 1 else kisiler

                if res.status_code != 200 or "Cloudflare" in res.text or "Just a moment" in res.text:
                    session = cureq.Session()
                    continue

                soup = BeautifulSoup(res.text, 'html.parser')

                satirlar = soup.find_all('div', class_='person-summary')

                if not satirlar:
                    return kisiler

                for s in satirlar:
                    a = s.find('a', class_='name')
                    if a:
                        username = a['href'].strip('/')
                        img = s.find('img')
                        img_url = img['src'] if img else "https://s.ltrbxd.com/static/img/avatar220.png"
                        kisiler[username] = img_url

                sayfa += 1
                sayfa_basarili = True
                break

            except:
                session = cureq.Session()

        if not sayfa_basarili:
            return "BLOK"

# analiz
if st.button("Analizi Başlat 🎬"):

    if not hedef_kullanici:
        st.warning("Kullanıcı adınızı giriniz")
    else:
        with st.spinner("Tarama başlatılıyor... Takipçi ve takip edilen sayınızın yoğunluğuna bağlı olarak işlemin süresi değişiklik gösterebilir. Lütfen bekleyiniz."):

            following = veri_cek(hedef_kullanici, "following")
            followers = veri_cek(hedef_kullanici, "followers")

        if following in ["BLOK","PROXY_ERROR"] or followers in ["BLOK","PROXY_ERROR"]:
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

            # grid kismi
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

# --- FOOTER ---
st.markdown("<div class='footer-sig'>Created by <a href='https://letterboxd.com/wokoshi/' target='_blank'>wokoshi</a></div>", unsafe_allow_html=True)
