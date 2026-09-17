import streamlit as st
import time
import random
from bs4 import BeautifulSoup
from curl_cffi import requests as cureq

st.set_page_config(
    page_title="Letterboxd Unfollow Checker",
    page_icon="👥",
    layout="wide"
)

# ----------------- PROXY AYARI (DATAIMPULSE) -----------------
DEFAULT_PROXY = "" 
PROXY_URL = st.secrets.get("DATAIMPULSE_PROXY", DEFAULT_PROXY)

def create_session():
    if PROXY_URL:
        return cureq.Session(proxies={"http": PROXY_URL, "https": PROXY_URL})
    return cureq.Session()
# -------------------------------------------------------------

st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

.stApp {
    background-color: #14181c;
    color: #9ab;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}

.title-text {
    font-size: 2.1rem;
    font-weight: 800;
    color: #fff;
    text-align: center;
    margin-bottom: 0.2rem;
}

.sub-text {
    text-align: center;
    color: #678;
    font-size: 0.95rem;
    margin-bottom: 1.8rem;
}

.user-card {
    background: #1e242b;
    border: 1px solid #2c3440;
    border-radius: 12px;
    padding: 10px 14px;
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 10px;
    transition: transform 0.15s ease, border-color 0.15s ease;
}

.user-card:hover {
    border-color: #ff453a;
    transform: translateY(-2px);
}

.user-card-fan:hover {
    border-color: #00e054;
}

.user-avatar {
    width: 46px;
    height: 46px;
    border-radius: 50%;
    object-fit: cover;
    border: 2px solid #2c3440;
}

.user-info {
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.user-name {
    color: #fff;
    font-weight: 600;
    font-size: 0.95rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.user-link {
    color: #00e054;
    font-size: 0.8rem;
    text-decoration: none;
}

.user-link:hover {
    text-decoration: underline;
}

.section-badge {
    background: #202830;
    padding: 10px 16px;
    border-radius: 8px;
    font-weight: 700;
    color: #fff;
    margin-top: 1.6rem;
    margin-bottom: 1rem;
    border-left: 4px solid #ff453a;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.section-badge-fan {
    border-left-color: #00e054;
}

.footer-credits {
    text-align: center;
    margin-top: 3rem;
    padding: 1.5rem;
    color: #567;
    font-size: 0.85rem;
    border-top: 1px solid #222933;
}
.footer-credits a {
    color: #00e054;
    text-decoration: none;
}
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='title-text'>👥 Letterboxd Takipçi Analizcisi (Unfollow Checker)</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-text'>Cloudflare bypass & dinamik oturum sıfırlama ile eksiksiz liste çıkarır.</div>", unsafe_allow_html=True)

col_input, col_btn = st.columns([4, 1])
with col_input:
    kullanici_adi = st.text_input("Letterboxd Kullanıcı Adı:", value="wokoshi", label_visibility="collapsed")
with col_btn:
    baslat = st.button("Taramayı Başlat 🚀", use_container_width=True)

def get_headers(referer="https://letterboxd.com/"):
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": referer,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,tr;q=0.8",
        "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1"
    }

def clean_username(href):
    if not href:
        return None
    parts = [p for p in href.strip("/").split("/") if p]
    if parts:
        return parts[-1].lower()
    return None

def safe_get(session_holder, url, referer="https://letterboxd.com/", status_box=None):
    for deneme in range(1, 6):
        try:
            headers = get_headers(referer)
            # chrome124 parmak izi ile sorgula
            res = session_holder["session"].get(url, impersonate="chrome124", headers=headers, timeout=25)
            
            if res.status_code == 200:
                if "Just a moment..." in res.text or "cf-browser-verification" in res.text:
                    if status_box:
                        status_box.warning(f"Cloudflare beklemesi... ({deneme}/5)")
                    # Cloudflare challenge'ında yeni oturum aç
                    session_holder["session"] = create_session()
                    time.sleep(random.uniform(4.0, 6.0))
                    continue
                return res.text
            elif res.status_code in [403, 429]:
                bekleme = 3.5 + (deneme * 2.0)
                if status_box:
                    status_box.warning(f"403/429 algılandı. Yeni oturum açılıyor ve {bekleme:.1f} sn bekleniyor...")
                # 403 yiyen oturumu tamamen çöpe atıp sıfırdan oluştur
                session_holder["session"] = create_session()
                time.sleep(bekleme)
            elif res.status_code == 404:
                return None
        except Exception:
            # Hata anında da oturumu tazele
            session_holder["session"] = create_session()
            time.sleep(random.uniform(3.0, 4.5))
            
    return None

def fetch_user_list(session_holder, username, list_type, status_box):
    """list_type: 'following' veya 'followers'"""
    users = {}
    page = 1
    type_tr = "Takip Edilenler (Following)" if list_type == "following" else "Takipçiler (Followers)"
    last_url = f"https://letterboxd.com/{username}/"
    
    while True:
        url = f"https://letterboxd.com/{username}/{list_type}/" if page == 1 else f"https://letterboxd.com/{username}/{list_type}/page/{page}/"
        status_box.info(f"⏳ **{type_tr}** taranıyor: **Sayfa {page}** (Toplanan: {len(users)} kişi)")
        
        html = safe_get(session_holder, url, referer=last_url, status_box=status_box)
        if not html:
            break
            
        soup = BeautifulSoup(html, "html.parser")
        
        # Yan panelleri ve menüleri temizle
        for s in soup.select("aside, .sidebar, #sidebar, div.profile-header, header, nav, div.site-header"):
            s.decompose()
            
        cards = soup.select("div.person-summary, table.person-table tr, td.table-person")
        if not cards:
            break
            
        found_in_page = 0
        for c in cards:
            a = c.select_one("a.name, h3.title a, a.avatar")
            if not a and c.name == "a":
                a = c
                
            if a and a.get("href"):
                uname = clean_username(a["href"])
                if uname and uname not in ["followers", "following", "members", username.lower()]:
                    if uname not in users:
                        img = c.find("img")
                        avatar_url = img["src"] if img and img.get("src") else "https://s.ltrbxd.com/static/img/avatar220.png"
                        users[uname] = avatar_url
                        found_in_page += 1
                        
        if found_in_page == 0:
            break
            
        next_link = soup.select_one("a.next, .paginate-next a, li.paginate-next a, a[rel='next']")
        if not next_link and found_in_page < 20:
            break
            
        last_url = url
        page += 1
        
        # İnsansı dinlenme süresi (1.8 - 3.2 sn)
        time.sleep(random.uniform(1.8, 3.2))
        
    return users

def render_grid(users_subset, all_users_dict, is_fan=False):
    if not users_subset:
        st.success("Tebrikler! Bu kategoride listelenecek kullanıcı yok.")
        return
        
    cols = st.columns(4)
    users_sorted = sorted(list(users_subset))
    card_class = "user-card user-card-fan" if is_fan else "user-card"
    
    for idx, u in enumerate(users_sorted):
        avatar = all_users_dict.get(u, "https://s.ltrbxd.com/static/img/avatar220.png")
        col = cols[idx % 4]
        with col:
            st.markdown(f"""
            <div class="{card_class}">
                <img src="{avatar}" class="user-avatar" />
                <div class="user-info">
                    <span class="user-name">@{u}</span>
                    <a href="https://letterboxd.com/{u}/" target="_blank" class="user-link">Profile Git ↗</a>
                </div>
            </div>
            """, unsafe_allow_html=True)

if baslat:
    cleaned_user = kullanici_adi.strip().lower()
    
    # Oturumu bir sözlük içinde tutuyoruz ki 403 yediğinde anında yenisiyle değiştirebilelim
    session_holder = {"session": create_session()}
    
    status_box = st.empty()
    progress_bar = st.progress(0)
    
    # 1. Takip Edilenleri Çek (Following)
    following = fetch_user_list(session_holder, cleaned_user, "following", status_box)
    progress_bar.progress(50)
    
    time.sleep(random.uniform(1.5, 2.5))
    
    # 2. Takipçileri Çek (Followers)
    followers = fetch_user_list(session_holder, cleaned_user, "followers", status_box)
    progress_bar.progress(100)
    
    if not following and not followers:
        status_box.error("Kullanıcı verileri çekilemedi. Profilin açık olduğunu veya proxy ayarını kontrol et.")
        st.stop()
        
    status_box.success(f"Analiz tamamlandı! Toplam Takip Edilen: {len(following)} | Toplam Takipçi: {len(followers)}")
    time.sleep(0.5)
    
    following_set = set(following.keys())
    followers_set = set(followers.keys())
    all_users = {**following, **followers}
    
    # Seni geri takip etmeyenler
    not_following_back = following_set - followers_set
    
    # Senin geri takip etmediğin takipçilerin
    fans = followers_set - following_set

    st.write("---")

    # 1. Seni Geri Takip Etmeyenler
    st.markdown(f"""
    <div class="section-badge">
        <span>🚫 Seni Geri Takip Etmeyenler (Unfollowers)</span>
        <span>{len(not_following_back)} Kişi</span>
    </div>
    """, unsafe_allow_html=True)
    render_grid(not_following_back, all_users, is_fan=False)

    # 2. Hayranlar
    st.markdown(f"""
    <div class="section-badge section-badge-fan">
        <span>⭐ Senin Takip Etmediğin Takipçilerin (Hayranlar)</span>
        <span>{len(fans)} Kişi</span>
    </div>
    """, unsafe_allow_html=True)
    render_grid(fans, all_users, is_fan=True)

st.markdown("""
<div class="footer-credits">
    Geliştirici: <a href="https://letterboxd.com/wokoshi/" target="_blank">wokoshi</a> • Güvenli Letterboxd Analiz Aracı
</div>
""", unsafe_allow_html=True)
