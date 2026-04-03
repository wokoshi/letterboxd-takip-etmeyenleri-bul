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
        PROXY_URL = st.secrets["DATAIMPULSE_PROXY"]
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