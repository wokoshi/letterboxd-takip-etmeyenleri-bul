import streamlit as st
from bs4 import BeautifulSoup
from curl_cffi.requests import Session
import time
import random
import re
from urllib.parse import urljoin
from html import escape


# ============================================================
# STREAMLIT
# ============================================================

st.set_page_config(
    page_title="Letterboxd Takip Analizi",
    page_icon="🔍",
    layout="centered"
)


# ============================================================
# TASARIM
# ============================================================

st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    .stApp {
        background-color: #0A110C;
        color: #9CAF9F;
    }

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

    .stButton > button {
        background-color: #1B5E32;
        color: white;
        border-radius: 12px;
        width: 100%;
        border: none;
    }

    .stButton > button:hover {
        background-color: #247340;
    }

    img {
        border-radius: 10px;
    }

    .card {
        background-color: #121E15;
        padding: 10px;
        border-radius: 14px;
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 10px;
        min-height: 70px;
    }

    .card b {
        color: #E8F0E9;
    }

    .card a {
        color: #7FB38C;
        text-decoration: none;
    }

    .card a:hover {
        text-decoration: underline;
    }

    .info-box {
        background-color: #121E15;
        border: 1px solid #1A2E20;
        padding: 12px;
        border-radius: 12px;
        margin-top: 12px;
        margin-bottom: 15px;
        text-align: center;
        color: #9CAF9F;
    }

    .success-box {
        background-color: #102016;
        border: 1px solid #244A30;
        padding: 12px;
        border-radius: 12px;
        color: #9EC9A7;
        margin-top: 12px;
        margin-bottom: 15px;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# BAŞLIK
# ============================================================

st.markdown(
    "<div class='custom-title'>🔍 Letterboxd Takip Analizi</div>",
    unsafe_allow_html=True
)

st.markdown(
    "<div class='custom-subtitle'>"
    "Hesabınızın takipçi ve takip edilen durumunu tek tuşla öğrenin."
    "</div>",
    unsafe_allow_html=True
)


# ============================================================
# ARAYÜZ
# ============================================================

islem_modu = st.radio(
    "",
    [
        "Beni Takip Etmeyenler",
        "Benim Takip Etmediklerim"
    ],
    horizontal=True
)

hedef_kullanici = st.text_input(
    "Kullanıcı adınızı giriniz:",
    placeholder="örnek: wokoshi"
)


# ============================================================
# AYARLAR
# ============================================================

CACHE_VERSION = "v7"
CACHE_TTL = 600

# İstekler arasındaki bekleme.
MIN_DELAY = 1.0
MAX_DELAY = 1.8

# Aynı sayfa için maksimum tekrar.
MAX_RETRIES = 3

# Sonsuz pagination durumuna karşı güvenlik.
MAX_PAGES = 500


# ============================================================
# USERNAME AYIKLAMA
# ============================================================

RESERVED_PATHS = {
    "films",
    "lists",
    "diary",
    "reviews",
    "members",
    "activity",
    "people",
    "journal",
    "settings",
    "account",
    "watchlist",
    "following",
    "followers",
    "pro",
    "about",
    "features",
    "login",
    "signup",
    "search",
    "news",
    "apps",
    "contact",
    "help",
    "gifts",
    "api"
}


def extract_username(href):
    if not href:
        return None

    href = href.strip()

    if href.startswith("http://") or href.startswith("https://"):
        path = href.split("://", 1)[1]
        slash_index = path.find("/")

        if slash_index == -1:
            return None

        path = path[slash_index:]

    path = path.split("?", 1)[0]
    path = path.split("#", 1)[0]
    path = path.strip("/")

    if not path:
        return None

    # Sadece /username/ biçimindeki linkleri al.
    if "/" in path:
        return None

    username = path.lower()

    if username in RESERVED_PATHS:
        return None

    # Letterboxd kullanıcı adları için güvenli karakter filtresi.
    if not re.fullmatch(r"[a-z0-9_-]+", username):
        return None

    return username


# ============================================================
# AVATAR
# ============================================================

def get_avatar(card):
    default_avatar = (
        "https://s.ltrbxd.com/static/img/avatar220.png"
    )

    img = card.find("img") if card else None

    if not img:
        return default_avatar

    candidates = [
        img.get("src"),
        img.get("data-src"),
        img.get("data-original")
    ]

    for candidate in candidates:
        if not candidate:
            continue

        candidate = candidate.strip()

        if candidate.startswith("//"):
            candidate = "https:" + candidate

        if candidate.startswith("http"):
            return candidate

    srcset = img.get("srcset")

    if srcset:
        first = (
            srcset
            .split(",")[0]
            .strip()
            .split(" ")[0]
        )

        if first.startswith("//"):
            first = "https:" + first

        if first.startswith("http"):
            return first

    return default_avatar


# ============================================================
# KULLANICI PARSE
# ============================================================

def parse_users(html):
    soup = BeautifulSoup(html, "html.parser")

    users = {}

    # --------------------------------------------------------
    # 1. Eski / klasik Letterboxd yapısı
    # --------------------------------------------------------

    cards = soup.select(".person-summary")

    for card in cards:

        username = None

        links = card.select(
            "a.avatar, a.name"
        )

        if not links:
            links = card.find_all(
                "a",
                href=True
            )

        for link in links:

            username = extract_username(
                link.get("href")
            )

            if username:
                break

        if username:
            users[username] = get_avatar(card)

    # --------------------------------------------------------
    # 2. Güncel yapı için fallback
    # --------------------------------------------------------
    #
    # Letterboxd sayfasında kullanıcı profilleri doğrudan
    # /username/ linkleri olarak bulunuyor.
    #
    # Sadece bir segmentli profil linklerini alıyoruz.
    # --------------------------------------------------------

    if not users:

        for link in soup.find_all("a", href=True):

            username = extract_username(
                link.get("href")
            )

            if not username:
                continue

            # Kullanıcı linkinin yakınında avatar var mı?
            parent = link.parent
            grandparent = (
                parent.parent
                if parent
                else None
            )

            candidate_container = (
                grandparent
                or parent
            )

            img_exists = False

            if candidate_container:
                img_exists = (
                    candidate_container.find("img")
                    is not None
                )

            if img_exists:
                users[username] = get_avatar(
                    candidate_container
                )

    return users


# ============================================================
# NEXT LINK BUL
# ============================================================

def get_next_url(html, current_url):
    soup = BeautifulSoup(html, "html.parser")

    # Önce rel="next"
    next_link = soup.find(
        "a",
        rel=lambda value: (
            value
            and "next" in value
        ) if isinstance(value, list)
        else (
            value
            and "next" in value.lower()
        )
    )

    if next_link and next_link.get("href"):
        return urljoin(
            current_url,
            next_link["href"]
        )

    # Sonra link yazısına bak.
    for link in soup.find_all("a", href=True):

        text = link.get_text(
            " ",
            strip=True
        ).lower()

        if text in {
            "next",
            "next →",
            "next ›",
            "next »"
        }:

            return urljoin(
                current_url,
                link["href"]
            )

    # Son olarak href'te /page/ geçen linkleri kontrol et.
    candidates = []

    for link in soup.find_all(
        "a",
        href=True
    ):

        href = link["href"]

        if "/page/" in href:
            candidates.append(
                urljoin(
                    current_url,
                    href
                )
            )

    # Pagination linkleri varsa, mevcut sayfadan
    # daha büyük page numarasına sahip olanı bul.
    if candidates:

        current_match = re.search(
            r"/page/(\d+)",
            current_url
        )

        current_page = (
            int(current_match.group(1))
            if current_match
            else 1
        )

        next_candidates = []

        for candidate in candidates:

            match = re.search(
                r"/page/(\d+)",
                candidate
            )

            if not match:
                continue

            number = int(
                match.group(1)
            )

            if number > current_page:
                next_candidates.append(
                    (number, candidate)
                )

        if next_candidates:

            next_candidates.sort(
                key=lambda x: x[0]
            )

            return next_candidates[0][1]

    return None


# ============================================================
# CLOUDFLARE
# ============================================================

def looks_like_cloudflare(html):
    if not html:
        return False

    text = html.lower()

    strong_markers = [
        "just a moment...",
        "cf-chl-",
        "challenge-platform",
        "verify you are human",
        "checking your browser"
    ]

    for marker in strong_markers:
        if marker in text:
            return True

    return False


# ============================================================
# SAYFA ÇEK
# ============================================================

def fetch_page(
    session,
    url,
    proxy_url,
    username,
    section
):
    headers = {
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,image/avif,"
            "image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": (
            f"https://letterboxd.com/"
            f"{username}/{section}/"
        )
    }

    last_error = "Bilinmeyen hata"

    for attempt in range(MAX_RETRIES):

        try:

            response = session.get(
                url,
                proxy=proxy_url,
                impersonate="chrome",
                headers=headers,
                timeout=25,
                allow_redirects=True
            )

            status = response.status_code
            html = response.text or ""

            # ------------------------------------------------
            # Başarılı
            # ------------------------------------------------

            if status == 200:

                if looks_like_cloudflare(html):
                    last_error = (
                        "Cloudflare doğrulama sayfası"
                    )

                else:
                    return {
                        "ok": True,
                        "status": 200,
                        "html": html,
                        "error": None
                    }

            # ------------------------------------------------
            # 404
            # ------------------------------------------------

            elif status == 404:

                return {
                    "ok": False,
                    "status": 404,
                    "html": "",
                    "error": "404"
                }

            # ------------------------------------------------
            # 403
            # ------------------------------------------------

            elif status == 403:

                last_error = "HTTP 403"

            # ------------------------------------------------
            # 429
            # ------------------------------------------------

            elif status == 429:

                last_error = "HTTP 429"

            # ------------------------------------------------
            # Diğer
            # ------------------------------------------------

            else:

                last_error = (
                    f"HTTP {status}"
                )

            # ------------------------------------------------
            # Retry beklemesi
            # ------------------------------------------------

            if attempt < MAX_RETRIES - 1:

                wait = (
                    3
                    + (attempt * 3)
                    + random.uniform(
                        0.5,
                        1.5
                    )
                )

                time.sleep(wait)

        except Exception as exc:

            last_error = (
                f"{type(exc).__name__}: "
                f"{str(exc)[:150]}"
            )

            if attempt < MAX_RETRIES - 1:

                time.sleep(
                    3
                    + (attempt * 2)
                )

    return {
        "ok": False,
        "status": None,
        "html": "",
        "error": last_error
    }


# ============================================================
# LISTE TARAMA
# ============================================================

def scrape_list(
    session,
    username,
    section,
    proxy_url
):
    """
    Letterboxd'ın kendi Next linkini takip ederek
    bütün sayfaları sırayla çeker.
    """

    current_url = (
        f"https://letterboxd.com/"
        f"{username}/{section}/"
    )

    all_users = {}
    visited_urls = set()

    page_count = 0

    while page_count < MAX_PAGES:

        # Sonsuz döngü güvenliği.
        if current_url in visited_urls:

            return {
                "ok": False,
                "users": {},
                "pages": page_count,
                "error": (
                    "Pagination aynı URL'ye geri döndü."
                )
            }

        visited_urls.add(
            current_url
        )

        # İlk sayfa dışındaki isteklerde bekle.
        if page_count > 0:

            time.sleep(
                random.uniform(
                    MIN_DELAY,
                    MAX_DELAY
                )
            )

        result = fetch_page(
            session=session,
            url=current_url,
            proxy_url=proxy_url,
            username=username,
            section=section
        )

        # ----------------------------------------------------
        # İlk sayfa 404 = kullanıcı yok.
        # ----------------------------------------------------

        if (
            page_count == 0
            and result["status"] == 404
        ):

            return {
                "ok": False,
                "users": {},
                "pages": 0,
                "error": "USER_NOT_FOUND"
            }

        # ----------------------------------------------------
        # Herhangi bir sayfa alınamadı.
        # ----------------------------------------------------

        if not result["ok"]:

            return {
                "ok": False,
                "users": {},
                "pages": page_count,
                "error": (
                    result["error"]
                    or "Sayfa alınamadı."
                )
            }

        html = result["html"]

        page_users = parse_users(
            html
        )

        # ----------------------------------------------------
        # İlk sayfa boş olabilir.
        # ----------------------------------------------------

        if page_count == 0 and not page_users:

            return {
                "ok": True,
                "users": {},
                "pages": 1,
                "error": None
            }

        # ----------------------------------------------------
        # Sonraki sayfa boşsa güvenli şekilde hata ver.
        # ----------------------------------------------------

        if page_count > 0 and not page_users:

            return {
                "ok": False,
                "users": {},
                "pages": page_count,
                "error": (
                    f"{section} listesinin "
                    f"{page_count + 1}. sayfası boş döndü."
                )
            }

        # ----------------------------------------------------
        # Yeni kullanıcıları ekle.
        # ----------------------------------------------------

        before_count = len(
            all_users
        )

        all_users.update(
            page_users
        )

        after_count = len(
            all_users
        )

        # Aynı kullanıcılar tekrar geldiyse
        # pagination'ın ilerlemediğini kontrol et.
        if (
            page_count > 0
            and after_count == before_count
        ):

            return {
                "ok": False,
                "users": {},
                "pages": page_count,
                "error": (
                    f"{section} listesinde "
                    f"{page_count + 1}. sayfa yeni "
                    f"kullanıcı getirmedi."
                )
            }

        page_count += 1

        # ----------------------------------------------------
        # Letterboxd'ın kendi NEXT linki.
        # ----------------------------------------------------

        next_url = get_next_url(
            html,
            current_url
        )

        if not next_url:
            break

        # Next aynı URL ise dur.
        if next_url == current_url:
            break

        current_url = next_url

    # --------------------------------------------------------
    # MAX PAGE
    # --------------------------------------------------------

    if page_count >= MAX_PAGES:

        return {
            "ok": False,
            "users": {},
            "pages": page_count,
            "error": (
                f"{section} pagination "
                f"güvenlik sınırına ulaştı."
            )
        }

    return {
        "ok": True,
        "users": all_users,
        "pages": page_count,
        "error": None
    }


# ============================================================
# ANA ANALİZ
# ============================================================

def run_analysis(
    username,
    proxy_url
):
    """
    Tek session:
        Following tamamen çekilir
        ↓
        Followers tamamen çekilir
        ↓
        karşılaştırılır
    """

    session = Session()

    try:

        # ----------------------------------------------------
        # FOLLOWING
        # ----------------------------------------------------

        following = scrape_list(
            session=session,
            username=username,
            section="following",
            proxy_url=proxy_url
        )

        if not following["ok"]:

            return {
                "ok": False,
                "error": (
                    "Following taraması tamamlanamadı: "
                    + str(following["error"])
                )
            }

        # ----------------------------------------------------
        # FOLLOWERS
        # ----------------------------------------------------

        followers = scrape_list(
            session=session,
            username=username,
            section="followers",
            proxy_url=proxy_url
        )

        if not followers["ok"]:

            return {
                "ok": False,
                "error": (
                    "Followers taraması tamamlanamadı: "
                    + str(followers["error"])
                )
            }

        # ----------------------------------------------------
        # Sadece iki liste de bittikten sonra döndür.
        # ----------------------------------------------------

        return {
            "ok": True,
            "following": following,
            "followers": followers
        }

    finally:

        session.close()


# ============================================================
# CACHE
# ============================================================

@st.cache_data(
    ttl=CACHE_TTL,
    show_spinner=False
)
def analiz_calistir(
    username,
    cache_version
):
    try:

        proxy_url = st.secrets[
            "DATAIMPULSE_PROXY"
        ]

    except Exception:

        return {
            "ok": False,
            "error": "PROXY_ERROR"
        }

    try:

        return run_analysis(
            username,
            proxy_url
        )

    except Exception as exc:

        return {
            "ok": False,
            "error": (
                f"{type(exc).__name__}: "
                f"{str(exc)}"
            )
        }


# ============================================================
# BUTON
# ============================================================

if st.button(
    "Analizi Başlat 🎬",
    use_container_width=True
):

    if not hedef_kullanici.strip():

        st.warning(
            "Lütfen kullanıcı adınızı giriniz."
        )

    else:

        cleaned_username = (
            hedef_kullanici
            .strip()
            .lower()
            .lstrip("@")
            .strip("/")
        )

        with st.spinner(
            "Tarama başlatılıyor... "
            "Following ve followers listeleri "
            "tamamen alınıyor."
        ):

            data = analiz_calistir(
                cleaned_username,
                CACHE_VERSION
            )

        # ====================================================
        # HATALAR
        # ====================================================

        if data["error"] == "PROXY_ERROR":

            st.error(
                "DATAIMPULSE_PROXY bulunamadı."
            )

        elif not data["ok"]:

            st.error(
                "Analiz güvenli şekilde tamamlanamadı."
            )

            st.caption(
                str(data["error"])
            )

        else:

            following_data = data[
                "following"
            ]

            followers_data = data[
                "followers"
            ]

            following = following_data[
                "users"
            ]

            followers = followers_data[
                "users"
            ]

            # =================================================
            # KARŞILAŞTIRMA
            # =================================================

            if (
                islem_modu
                == "Beni Takip Etmeyenler"
            ):

                sonuc = {
                    user: following[user]
                    for user in following
                    if user not in followers
                }

                baslik = "Takip etmeyenler"

            else:

                sonuc = {
                    user: followers[user]
                    for user in followers
                    if user not in following
                }

                baslik = "Senin takip etmediklerin"

            # =================================================
            # BİLGİ
            # =================================================

            st.markdown(
                f"""
                <div class="info-box">
                    <b>Following:</b> {len(following)}
                    &nbsp;&nbsp;•&nbsp;&nbsp;
                    <b>Followers:</b> {len(followers)}
                    <br>
                    <small>
                        Following sayfa:
                        {following_data["pages"]}
                        &nbsp;&nbsp;•&nbsp;&nbsp;
                        Followers sayfa:
                        {followers_data["pages"]}
                    </small>
                </div>
                """,
                unsafe_allow_html=True
            )

            st.markdown(
                f"""
                <div class="success-box">
                    ✓ Analiz tamamlandı.
                    <b>{len(sonuc)}</b> kişi bulundu.
                </div>
                """,
                unsafe_allow_html=True
            )

            st.markdown(
                f"### {baslik}"
            )

            # =================================================
            # SONUÇ YOK
            # =================================================

            if not sonuc:

                st.info(
                    "Bu kriterlere uyan kişi bulunamadı."
                )

            else:

                users = sorted(
                    sonuc.items(),
                    key=lambda item: item[0]
                )

                # =================================================
                # 2 SÜTUN
                # =================================================

                for i in range(
                    0,
                    len(users),
                    2
                ):

                    columns = st.columns(2)

                    for j in range(2):

                        index = i + j

                        if index >= len(users):
                            continue

                        username, image_url = users[
                            index
                        ]

                        safe_username = escape(
                            username
                        )

                        safe_image = escape(
                            image_url,
                            quote=True
                        )

                        with columns[j]:

                            st.markdown(
                                f"""
                                <div class="card">
                                    <img
                                        src="{safe_image}"
                                        width="50"
                                        height="50"
                                    >
                                    <div>
                                        <b>
                                            {safe_username}
                                        </b>
                                        <br>
                                        <a
                                            href="https://letterboxd.com/{safe_username}/"
                                            target="_blank"
                                        >
                                            Profile git
                                        </a>
                                    </div>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )


# ============================================================
# FOOTER
# ============================================================

st.markdown(
    """
    <div class="footer-sig">
        Created by
        <a
            href="https://letterboxd.com/wokoshi/"
            target="_blank"
        >
            wokoshi
        </a>
    </div>
    """,
    unsafe_allow_html=True
)
