import asyncio
import random
import re
from urllib.parse import urlparse
from html import escape

import streamlit as st
from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession


# ============================================================
# STREAMLIT AYARLARI
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
# KULLANICI AYARLARI
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
# GENEL AYARLAR
# ============================================================

# Kod değiştiğinde eski cache kullanılmasın.
CACHE_VERSION = "v6"

# Free Streamlit için 10 dakika.
CACHE_TTL = 600

# İstekler arasında küçük insan-benzeri bekleme.
MIN_DELAY = 0.8
MAX_DELAY = 1.4

# Şüpheli cevaplarda kaç kez tekrar denenecek.
MAX_RETRIES = 3

# Güvenlik sınırı.
MAX_PAGES = 500


# ============================================================
# URL'DEN USERNAME ÇIKARMA
# ============================================================

def extract_username(href):
    if not href:
        return None

    href = href.strip()

    try:
        if href.startswith("http://") or href.startswith("https://"):
            path = urlparse(href).path
        else:
            path = href
    except Exception:
        return None

    path = path.split("?")[0]
    path = path.split("#")[0]
    path = path.strip("/")

    if not path:
        return None

    # /username/ gibi tek segmentli profil linkleri.
    if "/" in path:
        return None

    username = path.strip()

    if not username:
        return None

    # Letterboxd navigasyon yolları.
    reserved = {
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
        "films-liked",
        "films-watched"
    }

    if username.lower() in reserved:
        return None

    return username.lower()


# ============================================================
# AVATAR
# ============================================================

def extract_avatar(card):
    img = card.find("img")

    default_avatar = (
        "https://s.ltrbxd.com/static/img/avatar220.png"
    )

    if not img:
        return default_avatar

    candidates = [
        img.get("src"),
        img.get("data-src"),
        img.get("data-original")
    ]

    for url in candidates:
        if url:
            url = url.strip()

            if url.startswith("//"):
                url = "https:" + url

            if url.startswith("http"):
                return url

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
# SAYFADAKİ KULLANICILARI PARSE ET
# ============================================================

def parse_page_users(html):
    soup = BeautifulSoup(html, "html.parser")

    users = {}

    # --------------------------------------------------------
    # Normal Letterboxd person-summary kartları
    # --------------------------------------------------------

    cards = soup.select("div.person-summary")

    for card in cards:

        username = None

        # Öncelikle avatar ve isim linklerini dene.
        links = card.select(
            "a.avatar, a.name"
        )

        # Olmazsa kartın içindeki linklere bak.
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

        if not username:
            continue

        users[username] = extract_avatar(card)

    return users


# ============================================================
# CLOUDFLARE KONTROLÜ
# ============================================================

def is_cloudflare_page(html):
    if not html:
        return False

    text = html.lower()

    markers = [
        "just a moment",
        "cf-chl-",
        "challenge-platform",
        "cloudflare ray id",
        "verify you are human",
        "checking your browser",
        "enable javascript and cookies"
    ]

    for marker in markers:
        if marker in text:
            return True

    return False


# ============================================================
# MAX PAGE BUL
# ============================================================

def detect_max_page(html):
    soup = BeautifulSoup(html, "html.parser")

    max_page = 1

    for link in soup.find_all("a", href=True):

        href = link.get("href", "")

        patterns = [
            r"/page/(\d+)/",
            r"/page/(\d+)$",
            r"[?&]page=(\d+)"
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                href
            )

            if match:
                try:
                    number = int(
                        match.group(1)
                    )

                    max_page = max(
                        max_page,
                        number
                    )

                except ValueError:
                    pass

    return max_page


# ============================================================
# TEK SAYFAYI ÇEK
# ============================================================

async def fetch_page(
    session,
    url,
    proxy_url,
    username,
    section,
    page_number
):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/140.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,image/avif,image/webp,"
            "*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": (
            f"https://letterboxd.com/"
            f"{username}/{section}/"
        ),
        "Connection": "keep-alive"
    }

    # curl_cffi dokümantasyonuna uygun.
    proxies = {
        "http": proxy_url,
        "https": proxy_url
    }

    last_error = "Bilinmeyen hata"

    for attempt in range(MAX_RETRIES):

        try:

            response = await session.get(
                url,
                proxies=proxies,
                impersonate="chrome",
                headers=headers,
                timeout=20,
                allow_redirects=True
            )

            status = response.status_code
            html = response.text or ""

            # ------------------------------------------------
            # 404
            # ------------------------------------------------

            if status == 404:

                if page_number == 1:
                    return {
                        "status": "USER_NOT_FOUND",
                        "html": ""
                    }

                return {
                    "status": "END",
                    "html": ""
                }

            # ------------------------------------------------
            # 200
            # ------------------------------------------------
            #
            # Burada artık HTML'i fazla katı kontrol etmiyoruz.
            # Cloudflare sayfası değilse kabul ediyoruz.
            # ------------------------------------------------

            if status == 200:

                if is_cloudflare_page(html):

                    last_error = (
                        "Cloudflare doğrulama sayfası"
                    )

                else:

                    return {
                        "status": "OK",
                        "html": html
                    }

            # ------------------------------------------------
            # 403 / 429
            # ------------------------------------------------

            elif status == 403:

                last_error = "HTTP 403"

            elif status == 429:

                last_error = "HTTP 429"

            # ------------------------------------------------
            # Sunucu hataları
            # ------------------------------------------------

            elif status >= 500:

                last_error = f"HTTP {status}"

            else:

                last_error = f"HTTP {status}"

            # Retry beklemesi
            await asyncio.sleep(
                2.0
                + (attempt * 2.0)
                + random.uniform(0.4, 1.2)
            )

        except Exception as exc:

            last_error = (
                f"{type(exc).__name__}: "
                f"{str(exc)[:150]}"
            )

            await asyncio.sleep(
                2.0
                + (attempt * 2.0)
            )

    return {
        "status": "ERROR",
        "html": last_error
    }


# ============================================================
# FOLLOWING / FOLLOWERS TARAMA
# ============================================================

async def scrape_target(
    session,
    username,
    section,
    proxy_url
):
    """
    Listeyi sayfa sayfa toplar.

    Önemli:
    - Sayfalar sırayla çekilir.
    - Paralel pagination yoktur.
    - Bir sayfa eksikse sonuç güvenilir kabul edilmez.
    - Tüm liste tamamlanmadan karşılaştırma yapılmaz.
    """

    first_url = (
        f"https://letterboxd.com/"
        f"{username}/{section}/"
    )

    # ========================================================
    # 1. SAYFA
    # ========================================================

    first = await fetch_page(
        session=session,
        url=first_url,
        proxy_url=proxy_url,
        username=username,
        section=section,
        page_number=1
    )

    if first["status"] == "USER_NOT_FOUND":

        return {
            "error": "USER_NOT_FOUND",
            "users": {},
            "pages": 0
        }

    if first["status"] != "OK":

        return {
            "error": first["html"],
            "users": {},
            "pages": 0
        }

    first_users = parse_page_users(
        first["html"]
    )

    users = dict(first_users)

    detected_max = detect_max_page(
        first["html"]
    )

    # ========================================================
    # BOŞ LİSTE
    # ========================================================

    if not first_users:

        return {
            "error": None,
            "users": {},
            "pages": 1
        }

    # ========================================================
    # SONRAKİ SAYFALAR
    # ========================================================

    page = 2

    while page <= MAX_PAGES:

        # İlk sayfada toplam sayfa belli olduysa
        # gereksiz istek atma.
        if detected_max > 1:

            if page > detected_max:
                break

        url = (
            f"https://letterboxd.com/"
            f"{username}/{section}/"
            f"page/{page}/"
        )

        page_users = None
        page_status = None

        # ----------------------------------------------------
        # SAYFAYI AL
        # ----------------------------------------------------

        for attempt in range(MAX_RETRIES):

            await asyncio.sleep(
                random.uniform(
                    MIN_DELAY,
                    MAX_DELAY
                )
            )

            result = await fetch_page(
                session=session,
                url=url,
                proxy_url=proxy_url,
                username=username,
                section=section,
                page_number=page
            )

            page_status = result["status"]

            # ------------------------------------------------
            # Gerçek son sayfa
            # ------------------------------------------------

            if page_status == "END":
                page_users = {}
                break

            # ------------------------------------------------
            # Başarılı sayfa
            # ------------------------------------------------

            if page_status == "OK":

                page_users = parse_page_users(
                    result["html"]
                )

                # Kullanıcı bulundu.
                if page_users:
                    break

                # 200 geldi ama kullanıcı kartı çıkmadı.
                # Hemen bitirmiyoruz.
                if attempt < MAX_RETRIES - 1:

                    await asyncio.sleep(
                        2.0
                        + random.uniform(
                            0.5,
                            1.0
                        )
                    )

                    continue

                # Retry bitti.
                page_users = {}

                break

            # ------------------------------------------------
            # Hata
            # ------------------------------------------------

            if attempt < MAX_RETRIES - 1:

                await asyncio.sleep(
                    2.0
                    + (attempt * 2.0)
                )

                continue

        # ====================================================
        # 404 -> SON
        # ====================================================

        if page_status == "END":

            # Eğer Letterboxd ilk sayfada bu sayfanın
            # var olduğunu söylüyorsa tutarsızlık var.
            if detected_max >= page:

                return {
                    "error": (
                        f"{section} listesinde "
                        f"{page}. sayfa bekleniyordu "
                        f"ama 404 döndü."
                    ),
                    "users": {},
                    "pages": page - 1
                }

            break

        # ====================================================
        # SAYFA HİÇ KULLANICI VERMEDİ
        # ====================================================

        if not page_users:

            # İlk sayfada toplam sayfa bilgisi varsa,
            # boş sayfa normal değildir.
            if detected_max >= page:

                return {
                    "error": (
                        f"{section} listesinin "
                        f"{page}. sayfası alınamadı. "
                        f"Eksik veriyle analiz yapılmadı."
                    ),
                    "users": {},
                    "pages": page - 1
                }

            # Toplam sayfa bilgisi yoksa,
            # boş sayfayı son kabul et.
            break

        # ====================================================
        # AYNI KULLANICILAR MI GELDİ?
        # ====================================================

        new_users = {}

        for user, avatar in page_users.items():

            if user not in users:
                new_users[user] = avatar

        # Sayfa önceki sayfanın aynısıysa
        # pagination ilerlemiyor.
        if not new_users:

            if detected_max >= page:

                return {
                    "error": (
                        f"{section} listesinde "
                        f"{page}. sayfa yeni kullanıcı "
                        f"getirmedi. Pagination güvenilir değil."
                    ),
                    "users": {},
                    "pages": page - 1
                }

            break

        # ====================================================
        # YENİ KULLANICILARI EKLE
        # ====================================================

        users.update(new_users)

        # ====================================================
        # SON SAYFAYA ULAŞILDI
        # ====================================================

        if detected_max > 1:

            if page >= detected_max:
                break

        page += 1

    # ========================================================
    # SONUÇ
    # ========================================================

    return {
        "error": None,
        "users": users,
        "pages": page - 1
    }


# ============================================================
# ANA SCRAPER
# ============================================================

async def run_analysis(
    username,
    proxy_url
):
    """
    Following tamamen biter.
    Ardından followers tamamen biter.
    Ardından karşılaştırma yapılır.
    """

    async with AsyncSession() as session:

        # ====================================================
        # FOLLOWING
        # ====================================================

        following = await scrape_target(
            session=session,
            username=username,
            section="following",
            proxy_url=proxy_url
        )

        if following["error"] == "USER_NOT_FOUND":

            return {
                "error": "USER_NOT_FOUND"
            }

        if following["error"]:

            return {
                "error": (
                    "Following taraması tamamlanamadı: "
                    + str(following["error"])
                )
            }

        # ====================================================
        # FOLLOWERS
        # ====================================================

        followers = await scrape_target(
            session=session,
            username=username,
            section="followers",
            proxy_url=proxy_url
        )

        if followers["error"]:

            return {
                "error": (
                    "Followers taraması tamamlanamadı: "
                    + str(followers["error"])
                )
            }

        # ====================================================
        # İKİSİ DE TAMAM
        # ====================================================

        return {
            "error": None,
            "following": following,
            "followers": followers
        }


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
            "error": "PROXY_ERROR"
        }

    try:

        result = asyncio.run(
            run_analysis(
                username,
                proxy_url
            )
        )

        return result

    except Exception as exc:

        return {
            "error": (
                f"{type(exc).__name__}: "
                f"{str(exc)}"
            )
        }


# ============================================================
# ANALİZ BUTONU
# ============================================================

if st.button(
    "Analizi Başlat 🎬",
    use_container_width=True
):

    # --------------------------------------------------------
    # Kullanıcı adı kontrolü
    # --------------------------------------------------------

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
            "eksiksiz şekilde alınıyor."
        ):

            data = analiz_calistir(
                cleaned_username,
                CACHE_VERSION
            )

        # ====================================================
        # PROXY HATASI
        # ====================================================

        if data["error"] == "PROXY_ERROR":

            st.error(
                "DATAIMPULSE_PROXY bulunamadı. "
                "Streamlit Secrets ayarınızı kontrol edin."
            )

        # ====================================================
        # KULLANICI BULUNAMADI
        # ====================================================

        elif data["error"] == "USER_NOT_FOUND":

            st.error(
                "Bu kullanıcı bulunamadı. "
                "Kullanıcı adınızı kontrol ediniz."
            )

        # ====================================================
        # TARAMA HATASI
        # ====================================================

        elif data["error"]:

            st.error(
                "Analiz güvenli şekilde tamamlanamadı."
            )

            st.caption(
                str(data["error"])
            )

        # ====================================================
        # BAŞARILI
        # ====================================================

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
            #
            # DİKKAT:
            # Bu noktaya ancak iki liste de tamamen bittikten
            # sonra geliyoruz.
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
            # İSTATİSTİK
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

            # =================================================
            # BAŞARILI
            # =================================================

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

            # =================================================
            # SONUÇLAR
            # =================================================

            else:

                users = sorted(
                    sonuc.items(),
                    key=lambda item: item[0]
                )

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
