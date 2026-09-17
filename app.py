import streamlit as st
import time
import random
from bs4 import BeautifulSoup
from curl_cffi import requests as cureq

st.set_page_config(
    page_title="Letterboxd Etkileşim & Tarih Analizi",
    page_icon="🎬",
    layout="wide"
)

# ----------------- PROXY AYARI (DATAIMPULSE) -----------------
# Streamlit Cloud'a yüklediğinde Secrets kısmına DATAIMPULSE_PROXY ekleyebilirsin.
# Yerelde test etmek için aşağıdaki tırnak içine doğrudan proxy linkini yazabilirsin.
# Format: "http://kullanici:sifre@gw.dataimpulse.com:823"
DEFAULT_PROXY = "" 

PROXY_URL = st.secrets.get("DATAIMPULSE_PROXY", DEFAULT_PROXY)

def get_session():
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
    padding: 10px 12px;
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 10px;
    transition: transform 0.15s ease, border-color 0.15s ease;
}

.user-card:hover {
    border-color: #00e054;
    transform: translateY(-2px);
}

.user-avatar {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    object-fit: cover;
    border: 2px solid #2c3440;
}

.user-info {
    display: flex;
    flex-direction: column;
    overflow: hidden;
    width: 100%;
}

.user-name {
    color: #fff;
    font-weight: 600;
    font-size: 0.92rem;
    text-decoration: none;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.user-link {
    color: #00e054;
    font-size: 0.78rem;
    text-decoration: none;
}

.user-link:hover {
    text-decoration: underline;
}

.badge-date {
    display: inline-block;
    background: rgba(0, 224, 84, 0.12);
    color: #00e054;
    border: 1px solid rgba(0, 224, 84, 0.35);
    font-size: 0.73rem;
    padding: 2px 7px;
    border-radius: 4px;
    margin-top: 4px;
    width: fit-content;
    font-weight: 500;
}

.badge-nodate {
    display: inline-block;
    background: rgba(255, 159, 10, 0.15);
    color: #ff9f0a;
    border: 1px solid rgba(255, 159, 10, 0.35);
    font-size: 0.73rem;
    padding: 2px 7px;
    border-radius: 4px;
    margin-top: 4px;
    width: fit-content;
}

.section-badge {
    background: #202830;
    padding: 10px 16px;
    border-radius: 8px;
    font-weight: 700;
    color: #fff;
    margin-top: 1.6rem;
    margin-bottom: 1rem;
    border-left: 4px solid #00e054;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.section-badge-danger {
    border-left-color: #ff453a;
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

st.markdown("<div class='title-text'>🎬 Letterboxd Tarih & Etkileşim Analizi</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-text'>Son inceleme tarihlerinize göre yanıt vermeyen veya inaktif hesapları filtreler.</div>", unsafe_allow_html=True)

col_input, col_btn = st.columns([4, 1])
with col_input:
    kullanici_adi = st.text_input("Letterboxd Kullanıcı Adı:", value="wokoshi", label_visibility="collapsed")
with col_btn:
    baslat = st.button("Analizi Başlat 🚀", use_container_width=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://letterboxd.com/",
    "X-Requested-With": "XMLHttpRequest"
}

def clean_username(href):
    if not href:
        return None
    return href.strip('/').split('/')[-1].lower()

def safe_get(session, url):
    for _ in range(4):
        try:
            res = session.get(url, impersonate="chrome120", headers=HEADERS, timeout=20)
            if res.status_code == 200:
                return res.text
            elif res.status_code == 404:
                return None
        except Exception:
            pass
        time.sleep(random.uniform(0.6, 1.2))
    return None

def get_following_dict(session, username):
    following = {}
    page = 1
    
    while True:
        url = f"https://letterboxd.com/{username}/following/" if page == 1 else f"https://letterboxd.com/{username}/following/page/{page}/"
        html = safe_get(session, url)
        if not html:
            break
            
        soup = BeautifulSoup(html, "html.parser")
        for s in soup.select("aside, .sidebar, #sidebar, div.sidebar"):
            s.decompose()
            
        cards = soup.select("div.person-summary")
        if not cards:
            break
            
        for c in cards:
            a = c.find("a", class_="name")
            if a and a.get("href"):
                uname = clean_username(a["href"])
                if uname:
                    img = c.find("img")
                    img_url = img["src"] if img and img.get("src") else "https://s.ltrbxd.com/static/img/avatar220.png"
                    following[uname] = img_url
                    
        has_next = soup.select("a.next, .paginate-next a, a[rel='next']")
        if not has_next:
            break
            
        page += 1
        time.sleep(random.uniform(0.3, 0.5))
        
    return following

def get_latest_reviews_with_dates(session, username, count=10):
    reviews = []
    review_dates = {}
    page = 1
    
    while len(reviews) < count:
        url = f"https://letterboxd.com/{username}/films/reviews/" if page == 1 else f"https://letterboxd.com/{username}/films/reviews/page/{page}/"
        html = safe_get(session, url)
        if not html:
            break
            
        soup = BeautifulSoup(html, "html.parser")
        for s in soup.select("aside, .sidebar, #sidebar"):
            s.decompose()

        found_on_page = 0
        for a in soup.find_all("a", href=True):
            raw_href = a["href"].split("#")[0].split("?")[0].strip("/")
            if raw_href.startswith(f"{username}/film/") and len(raw_href.split("/")) >= 3:
                parts = raw_href.split("/")
                clean_path = "/".join(parts[:4]) if (len(parts) >= 4 and parts[3].isdigit()) else "/".join(parts[:3])
                
                if clean_path not in reviews:
                    reviews.append(clean_path)
                    
                    parent = a.find_parent(["li", "tr", "div", "article"])
                    date_found = ""
                    if parent:
                        t = parent.select_one("time, span.date, span._nobr, p.attribution span")
                        if t:
                            date_found = t.text.strip()
                            
                    review_dates[clean_path] = date_found
                    found_on_page += 1
                    if len(reviews) == count:
                        break

        if found_on_page == 0:
            break
            
        has_next = soup.select("a.next, .paginate-next a, a[rel='next']")
        if not has_next:
            break
            
        page += 1
        time.sleep(random.uniform(0.3, 0.5))
        
    return reviews, review_dates

def get_review_likers(session, review_path):
    likers = set()
    page = 1
    
    while True:
        url = f"https://letterboxd.com/{review_path}/likes/" if page == 1 else f"https://letterboxd.com/{review_path}/likes/page/{page}/"
        html = safe_get(session, url)
        if not html:
            break
            
        soup = BeautifulSoup(html, "html.parser")
        for s in soup.select("aside, .sidebar, #sidebar"):
            s.decompose()

        cards = soup.select("div.person-summary, a.avatar, table.person-table tr")
        if not cards:
            break
            
        found_any = False
        for c in cards:
            a = c if c.name == "a" else c.find("a", class_="name")
            if not a:
                a = c.find("a")
            if a and a.get("href"):
                uname = clean_username(a["href"])
                if uname and uname not in ["likes", "members"]:
                    likers.add(uname)
                    found_any = True
                    
        has_next = soup.select("a.next, .paginate-next a, a[rel='next']")
        if not has_next or not found_any:
            break
            
        page += 1
        time.sleep(random.uniform(0.3, 0.5))
        
    return likers

def get_user_last_review_date(session, target_user):
    url = f"https://letterboxd.com/{target_user}/films/reviews/"
    html = safe_get(session, url)
    if not html:
        url_profile = f"https://letterboxd.com/{target_user}/"
        html_prof = safe_get(session, url_profile)
        if not html_prof:
            return "Bilinmiyor"
        soup_p = BeautifulSoup(html_prof, "html.parser")
        time_tag = soup_p.select_one("section#recent-activity time, time")
        if time_tag:
            return time_tag.text.strip()
        return "İnceleme Yok"
        
    soup = BeautifulSoup(html, "html.parser")
    for s in soup.select("aside, .sidebar, #sidebar"):
        s.decompose()

    time_tag = soup.select_one("time, span.date, span._nobr")
    if time_tag:
        return time_tag.text.strip()
        
    return "İnceleme Yok"

def display_user_cards(users_subset, following_dict, user_dates_dict):
    if not users_subset:
        st.caption("Bu kategoride hiç kullanıcı bulunamadı.")
        return
        
    cols = st.columns(4)
    users_list = sorted(list(users_subset))
    
    for idx, u in enumerate(users_list):
        avatar = following_dict.get(u, "https://s.ltrbxd.com/static/img/avatar220.png")
        last_date = user_dates_dict.get(u, "Bilinmiyor")
        
        if last_date in ["İnceleme Yok", "Bilinmiyor"]:
            badge_html = f"<span class='badge-nodate'>⚠️ {last_date}</span>"
        else:
            badge_html = f"<span class='badge-date'>📅 Son İnc: {last_date}</span>"
            
        col = cols[idx % 4]
        with col:
            st.markdown(f"""
            <div class="user-card">
                <img src="{avatar}" class="user-avatar" />
                <div class="user-info">
                    <span class="user-name">{u}</span>
                    <a href="https://letterboxd.com/{u}/" target="_blank" class="user-link">Profile Git ↗</a>
                    {badge_html}
                </div>
            </div>
            """, unsafe_allow_html=True)

if baslat:
    cleaned_user = kullanici_adi.strip().lower()
    session = get_session()
    
    progress_bar = st.progress(0)
    status_box = st.empty()
    
    status_box.info("Takip edilen kullanıcılar alınıyor...")
    following_dict = get_following_dict(session, cleaned_user)
    if not following_dict:
        status_box.error("Takip edilen kullanıcılar bulunamadı.")
        st.stop()
        
    following_set = set(following_dict.keys())
    progress_bar.progress(20)
    
    status_box.info("Son 10 inceleme ve tarihleri taranıyor...")
    reviews, review_dates = get_latest_reviews_with_dates(session, cleaned_user, count=10)
    if not reviews:
        status_box.error("İncelemeler bulunamadı.")
        st.stop()
        
    progress_bar.progress(35)
    
    review_likes = {}
    total_revs = len(reviews)
    for idx, r_path in enumerate(reviews, 1):
        film_slug = r_path.split("/")[2] if len(r_path.split("/")) > 2 else r_path
        status_box.info(f"Beğeniler taranıyor ({idx}/{total_revs}): **{film_slug}**")
        likers = get_review_likers(session, r_path)
        review_likes[idx] = likers.intersection(following_set)
        progress_bar.progress(35 + int((idx / total_revs) * 35))

    adaylar = set()
    for target_idx in range(6, 11):
        if target_idx in review_likes:
            daha_yeniler = set()
            for p in range(1, target_idx):
                daha_yeniler.update(review_likes.get(p, set()))
            adaylar.update(review_likes[target_idx] - daha_yeniler)
            
    tum_10 = set()
    for i in range(1, len(reviews) + 1):
        tum_10.update(review_likes.get(i, set()))
    sifir_cekenler = following_set - tum_10
    adaylar.update(sifir_cekenler)

    status_box.info(f"Filtreye takılan {len(adaylar)} kişinin son inceleme tarihleri alınıyor...")
    user_dates_dict = {}
    adaylar_list = list(adaylar)
    
    for i, target_u in enumerate(adaylar_list, 1):
        status_box.info(f"Tarih kontrolü ({i}/{len(adaylar_list)}): **{target_u}**")
        d = get_user_last_review_date(session, target_u)
        user_dates_dict[target_u] = d
        progress_bar.progress(70 + int((i / len(adaylar_list)) * 30))
        time.sleep(random.uniform(0.15, 0.35))

    progress_bar.progress(100)
    status_box.success("Tüm analiz ve tarih eşleştirmeleri tamamlandı!")
    time.sleep(0.3)

    st.write("---")
    
    for target_idx in range(6, 11):
        if target_idx not in review_likes:
            continue
            
        daha_yenileri_begenenler = set()
        for prev in range(1, target_idx):
            daha_yenileri_begenenler.update(review_likes.get(prev, set()))
            
        kategori_kisileri = review_likes[target_idx] - daha_yenileri_begenenler
        
        rev_key = reviews[target_idx - 1]
        film_title = rev_key.split("/")[2].replace("-", " ").title()
        rev_date = review_dates.get(rev_key, "")
        date_display = f" — Tarih: {rev_date}" if rev_date else ""

        st.markdown(f"""
        <div class="section-badge">
            <span>📌 En Son {target_idx}. İncelemeni Beğenenler: {film_title}{date_display}</span>
            <span>{len(kategori_kisileri)} Kişi</span>
        </div>
        """, unsafe_allow_html=True)
        display_user_cards(kategori_kisileri, following_dict, user_dates_dict)

    st.markdown(f"""
    <div class="section-badge section-badge-danger">
        <span>🚨 Son 10 İncelemende SIFIR Beğenisi Olanlar</span>
        <span>{len(sifir_cekenler)} Kişi</span>
    </div>
    """, unsafe_allow_html=True)
    display_user_cards(sifir_cekenler, following_dict, user_dates_dict)

st.markdown("""
<div class="footer-credits">
    Geliştirici: <a href="https://letterboxd.com/wokoshi/" target="_blank">wokoshi</a> • Letterboxd Tarih & Etkileşim Analizi
</div>
""", unsafe_allow_html=True)
