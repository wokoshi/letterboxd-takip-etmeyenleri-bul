import streamlit as st
from bs4 import BeautifulSoup
from curl_cffi import requests as cureq
import time
import random

# Sayfa Ayarı
st.set_page_config(
    page_title="Letterboxd Takip Analizi", 
    page_icon="🎬", 
    layout="wide"
)

# Gelişmiş Yeşil / Letterboxd UI Tasarımı
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

.stApp { 
    background-color: #0b110e; 
    color: #9ab; 
    font-family: 'Inter', -apple-system, sans-serif;
}

/* Üst Başlık Bloğu */
.hero-wrapper {
    text-align: center;
    padding: 2.2rem 1rem 1.6rem 1rem;
    margin-bottom: 1.5rem;
    border-radius: 20px;
    background: radial-gradient(circle at top, rgba(0, 224, 84, 0.09) 0%, rgba(11, 17, 14, 0) 70%);
}

.custom-title {
    color: #ffffff;
    font-size: 2.3rem;
    font-weight: 800;
    letter-spacing: -0.5px;
    margin-bottom: 0.4rem;
}

.custom-title span {
    color: #00e054;
}

.custom-subtitle {
    color: #7b8e83;
    font-size: 1rem;
    font-weight: 400;
    max-width: 500px;
    margin: 0 auto;
}

/* Kontrol Kutusu */
.search-container {
    max-width: 720px;
    margin: 0 auto 2.5rem auto;
    background: #141c17;
    padding: 1.8rem;
    border-radius: 16px;
    border: 1px solid #1f2b24;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
}

/* Giriş Kutusu */
div[data-baseweb="input"] {
    background-color: #0e1511 !important;
    border: 1px solid #23332a !important;
    border-radius: 10px !important;
    color: #ffffff !important;
}

div[data-baseweb="input"]:focus-within {
    border-color: #00e054 !important;
    box-shadow: 0 0 0 1px #00e054 !important;
}

/* Buton */
.stButton>button {
    background: linear-gradient(135deg, #00e054 0%, #00b341 100%) !important;
    color: #0b110e !important;
    font-weight: 700 !important;
    font-size: 1.05rem !important;
    border-radius: 10px !important;
    border: none !important;
    padding: 0.65rem 1.4rem !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 4px 15px rgba(0, 224, 84, 0.25) !important;
}

.stButton>button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(0, 224, 84, 0.4) !important;
    color: #000000 !important;
}

/* Radio Seçim */
div[role="radiogroup"] {
    justify-content: center;
    gap: 1.8rem;
    margin-bottom: 1.2rem;
}

/* Kullanıcı Kartları */
.card-wrapper {
    background: #131a15;
    border: 1px solid #1c2720;
    border-radius: 14px;
    padding: 12px 14px;
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 14px;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.card-wrapper:hover {
    border-color: #00e054;
    background: #17221b;
    transform: translateY(-3px);
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.4);
}

.card-avatar {
    width: 52px;
    height: 52px;
    border-radius: 50%;
    object-fit: cover;
    border: 2px solid #23332a;
    flex-shrink: 0;
}

.card-info {
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.card-username {
    color: #ffffff;
    font-weight: 700;
    font-size: 0.96rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.card-link {
    color: #00e054;
    font-size: 0.82rem;
    font-weight: 500;
    text-decoration: none;
    margin-top: 2px;
    display: inline-flex;
    align-items: center;
    gap: 3px;
}

.card-link:hover {
    text-decoration: underline;
}

/* Sonuç Sayacı Rozeti */
.result-badge {
    background: rgba(0, 224, 84, 0.1);
    border: 1px solid rgba(0, 224, 84, 0.25);
    color: #00e054;
    padding: 8px 18px;
    border-radius: 30px;
    font-size: 0.95rem;
    font-weight: 600;
    display: inline-block;
    margin-bottom: 1.8rem;
}

/* Footer */
.footer-sig {
    text-align: center;
    color: #536558;
    font-size: 0.88rem;
    margin-top: 4rem;
    padding-top: 1.5rem;
    border-top: 1px solid #18221b;
}

.footer-sig a {
    color: #00e054;
    text-decoration: none;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

# Başlık
st.markdown("""
<div class='hero-wrapper'>
    <div class='custom-title'>Letterboxd <span>Takip Analizi</span></div>
    <div class='custom-subtitle'>Hesabınızın takipçi ve takip edilen dengesini hızlı, güvenli ve net şekilde görüntüleyin.</div>
</div>
""", unsafe_allow_html=True)

# Giriş ve Seçim Alanı
st.markdown("<div class='search-container'>", unsafe_allow_html=True)

islem_modu = st.radio(
    "",
    ["Beni Takip Etmeyenler", "Benim Takip Etmediklerim"],
    horizontal=True,
    label_visibility="collapsed"
)

col_in, col_bt = st.columns([3.5, 1.5])
with col_in:
    hedef_kullanici = st.text_input("Kullanıcı adınızı giriniz:", placeholder="Letterboxd kullanıcı adın (örn: wokoshi)", label_visibility="collapsed")
with col_bt:
    analiz_tetikle = st.button("Analizi Başlat 🎬", use_container_width=True)

st.markdown("</div>", unsafe_allow_html=True)

# Veri Kazıma Motoru
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

# İşlem Bloğu
if analiz_tetikle:
    if not hedef_kullanici.strip():
        st.warning("Lütfen analiz etmek istediğiniz kullanıcı adını giriniz.")
    else:
        with st.spinner("Letterboxd üzerinden takip verileri taranıyor, lütfen bekleyiniz..."):
            cleaned_target = hedef_kullanici.strip().lower()
            following = veri_cek(cleaned_target, "following")
            followers = veri_cek(cleaned_target, "followers")

        if following in ["BLOK", "PROXY_ERROR"] or followers in ["BLOK", "PROXY_ERROR"]:
            st.error("Proxy bağlantısında veya veri alımında anlık bir aksama yaşandı. Lütfen biraz bekleyip tekrar deneyin.")
        elif following is None or followers is None:
            st.error("Belirtilen kullanıcı adı Letterboxd üzerinde bulunamadı veya profil gizli.")
        else:
            if islem_modu == "Beni Takip Etmeyenler":
                sonuc = {u: following[u] for u in following if u not in followers}
            else:
                sonuc = {u: followers[u] for u in followers if u not in following}

            st.markdown(f"<div style='text-align: center;'><span class='result-badge'>✨ Toplam {len(sonuc)} kullanıcı listelendi</span></div>", unsafe_allow_html=True)

            users = list(sonuc.items())

            # 3'lü Grid Dizilimi
            cols_per_row = 3
            for i in range(0, len(users), cols_per_row):
                cols = st.columns(cols_per_row)
                for j in range(cols_per_row):
                    if i + j < len(users):
                        usr, img = users[i + j]
                        with cols[j]:
                            st.markdown(f"""
                            <div class="card-wrapper">
                                <img src="{img}" class="card-avatar">
                                <div class="card-info">
                                    <span class="card-username">@{usr}</span>
                                    <a href="https://letterboxd.com/{usr}/" target="_blank" class="card-link">Profile git ↗</a>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

# Footer
st.markdown("<div class='footer-sig'>Geliştirici: <a href='https://letterboxd.com/wokoshi/' target='_blank'>wokoshi</a> • Letterboxd Analiz Aracı</div>", unsafe_allow_html=True)
