import streamlit as st
from bs4 import BeautifulSoup
import requests
import time

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

def fetch_via_solver(target_url, solver_url):
    payload = {
        "cmd": "request.get",
        "url": target_url,
        "maxTimeout": 60000
    }
    headers = {"Content-Type": "application/json"}
    
    try:
        res = requests.post(solver_url, json=payload, headers=headers, timeout=70)
        data = res.json()
        if data.get("status") == "ok":
            solution = data.get("solution", {})
            return solution.get("status", 200), solution.get("response", "")
        return 500, f"FlareSolverr Hatası: {data.get('message', 'Bilinmeyen hata')}"
    except requests.exceptions.Timeout:
        return 500, "Render zaman aşımına uğradı (servis uyanıyor olabilir, lütfen 20-30 sn sonra tekrar deneyin)"
    except Exception as e:
        return 500, f"Bağlantı Hatası: {str(e)}"

@st.cache_data(ttl=1800, show_spinner=False)
def veri_cek(kullanici_adi, tip):
    kisiler = {}
    
    if "FLARESOLVERR_URL" not in st.secrets:
        return "SECRET_EKSIK"
        
    solver_url = st.secrets["FLARESOLVERR_URL"]
    sayfa = 1

    while True:
        url = f"https://letterboxd.com/{kullanici_adi}/{tip}/" if sayfa == 1 else f"https://letterboxd.com/{kullanici_adi}/{tip}/page/{sayfa}/"
        
        status_code, html_content = fetch_via_solver(url, solver_url)
        
        if status_code == 404:
            return None if sayfa == 1 else kisiler
            
        if status_code != 200 or not html_content:
            return f"BLOK [{html_content if isinstance(html_content, str) and html_content else status_code}]"

        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Kenar çubuğunu temizle
        for s in soup.select("aside, .sidebar, #sidebar, div.sidebar"):
            s.decompose()

        satirlar = soup.find_all('div', class_='person-summary')
        if not satirlar:
            return kisiler

        for s in satirlar:
            a = s.find('a', class_='name')
            if a and a.get('href'):
                uname = a['href'].strip('/').split('/')[-1].lower()
                img = s.find('img')
                img_url = img['src'] if img and img.get('src') else "https://s.ltrbxd.com/static/img/avatar220.png"
                kisiler[uname] = img_url

        # Sonraki sayfa kontrolü
        has_next = soup.select("a.next, .paginate-next a, a[rel='next']")
        if not has_next:
            break

        sayfa += 1
        time.sleep(0.5)

    return kisiler

# analiz
if st.button("Analizi Başlat 🎬"):
    if not hedef_kullanici:
        st.warning("Kullanıcı adınızı giriniz")
    else:
        with st.spinner("Tarama başlatılıyor... Cloudflare doğrulamaları aşılıyor, lütfen bekleyiniz."):
            cleaned = hedef_kullanici.strip().lower()
            following = veri_cek(cleaned, "following")
            followers = veri_cek(cleaned, "followers")

        if following == "SECRET_EKSIK" or followers == "SECRET_EKSIK":
            st.error("Secrets altında FLARESOLVERR_URL tanımlanmamış!")
        elif (isinstance(following, str) and following.startswith("BLOK")) or \
             (isinstance(followers, str) and followers.startswith("BLOK")):
            st.error(f"Hata Detayı: Following -> {following} | Followers -> {followers}")
        elif following is None or followers is None:
            st.error("Bu kullanıcı adıyla ilgili hesap bulunmuyor. Kullanıcı adınızı kontrol ediniz.")
        else:
            if islem_modu == "Beni Takip Etmeyenler":
                sonuc = {u: following[u] for u in following if u not in followers}
            else:
                sonuc = {u: followers[u] for u in followers if u not in following}

            st.success(f"İşlem başarılı! {len(sonuc)} kişi bulundu.")

            # grid kısmı
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
