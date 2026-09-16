import asyncio
import random
import re
from urllib.parse import urlparse
from html import escape

import streamlit as st
from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession


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
# KULLANICI ARAYÜZÜ
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

CACHE_VERSION = "v5"

# Free Streamlit için aynı hesabı tekrar tekrar taramasın.
CACHE_TTL = 600

# İstekler arasında küçük bekleme.
MIN_DELAY = 0.7
MAX_DELAY = 1.2

# Geçici boş/şüpheli sayfa için tekrar deneme.
PAGE_RETRIES = 3

# Güvenlik sınırı.
MAX_PAGES = 500


# ============================================================
# YARDIMCI FONKSİYONLAR
# ============================================================

def normalize_url(url):
    if not url:
        return None

    url = url.strip()

    if url.startswith("//"):
        return "https:" + url

    return url


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

    # Profil linki tek path segmentinden oluşmalı.
    if "/" in path:
        return None

    username = path.lower()

    # Letterboxd'ın sistem sayfaları.
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
    }

    if username in reserved:
        return None

    if not re.fullmatch(r"[a-z0-9_-]+", username):
        return None

    return username


def get_image(person):
    img = person.find("img")

    if not img:
        return "https://s.ltrbxd.com/static/img/avatar220.png"

    candidates = [
        img.get("src"),
        img.get("data-src"),
        img.get("data-original")
    ]

    for candidate in candidates:
        candidate = normalize_url(candidate)

        if candidate:
            return candidate

    srcset = img.get("srcset")

    if srcset:
        first = srcset.split(",")[0].strip().split(" ")[0]
        first = normalize_url(first)

        if first:
            return first

    return "https://s.ltrbxd.com/static/img/avatar220.png"


# ============================================================
# SAYFADAN KULLANICILARI ÇIKART
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

        # Önce avatar / name linklerini dene.
        links = card.select("a.avatar, a.name")

        # Bulamazsak kartın içindeki bütün linkleri dene.
        if not links:
            links = card.find_all("a", href=True)

        for link in links:
            username = extract_username(link.get("href"))

            if username:
                break

        if not username:
            continue

        users[username] = get_image(card)

    # --------------------------------------------------------
    # Fallback
    # --------------------------------------------------------
    #
    # HTML yapısı değişirse doğrudan profil linklerini deniyoruz.
    # --------------------------------------------------------

    if not users:
        for link in soup.find_all("a", href=True):

            username = extract_username(link.get("href"))

            if not username:
                continue

            parent = link.parent

            has_image = False

            if parent:
                has_image = parent.find("img") is not None

            if has_image:
                users[username] = get_image(parent)

    return users


# ============================================================
# CLOUDLFARE / SAYFA DOĞRULAMA
# ============================================================

def is_cloudflare(html):
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


def is_valid_letterboxd_html(html):
    if not html:
        return False

    if is_cloudflare(html):
        return False

    soup = BeautifulSoup(html, "html.parser")

    # Sayfa title.
    if soup.title:
        title = soup.title.get_text(" ", strip=True).lower()

        if "letterboxd" in title:
            return True

    # Kişi kartları.
    if soup.select("div.person-summary"):
        return True

    # Pagination elementleri.
    if soup.select(
        ".paginate-pages, .pagination, nav.pagination"
    ):
        return True

    return False


# ============================================================
# MAKSİMUM SAYFA NUMARASI
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

            match = re.search(pattern, href)

            if match:
                try:
                    number = int(match.group(1))

                    if number > max_page:
                        max_page = number

                except ValueError:
                    pass

    return max_page


# ============================================================
# TEK SAYFA FETCH
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
            "Chrome/146.0.0.0 Safari/537.36"
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
        )
    }

    last_error = "Bilinmeyen hata"

    for attempt in range(PAGE_RETRIES):

        try:

            response = await session.get(
                url,
                proxy=proxy_url,
                impersonate="chrome",
                headers=headers,
                timeout=20
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
            # Başarılı ve gerçek Letterboxd sayfası
            # ------------------------------------------------

            if status == 200 and is_valid_letterboxd_html(html):

                return {
                    "status": "OK",
                    "html": html
                }

            # ------------------------------------------------
            # Cloudflare / şüpheli cevap
            # ------------------------------------------------

            if status == 403:
                last_error = "HTTP 403"

            elif status == 429:
                last_error = "HTTP 429"

            elif status >= 500:
                last_error = f"HTTP {status}"

            elif status == 200:
                last_error = "Geçersiz veya eksik HTML"

            else:
                last_error = f"HTTP {status}"

            # Giderek biraz daha uzun bekle.
            await asyncio.sleep(
                2.0 * (attempt + 1)
                + random.uniform(0.5, 1.2)
            )

        except Exception as exc:

            last_error = (
                f"{type(exc).__name__}: "
                f"{str(exc)[:120]}"
            )

            await asyncio.sleep(
                2.0 * (attempt + 1)
            )

    return {
        "status": "ERROR",
        "html": last_error
    }


# ============================================================
# FOLLOWING / FOLLOWERS TAMAMEN ÇEK
# ============================================================

async def scrape_target(
    session,
    username,
    section,
    proxy_url
):
    first_url = (
        f"https://letterboxd.com/"
        f"{username}/{section}/"
    )

    # --------------------------------------------------------
    # 1. sayfa
    # --------------------------------------------------------

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

    # Gerçekten hiç kimse yoksa.
    if not first_users:
        return {
            "error": None,
            "users": {},
            "pages": 1
        }

    # İlk sayfadan bilinen maksimum sayıyı bul.
    detected_max = detect_max_page(
        first["html"]
    )

    page = 2

    while page <= MAX_PAGES:

        # Eğer pagination açık şekilde toplam sayıyı
        # söylüyorsa gereksiz sayfalara gitme.
        if detected_max > 1 and page > detected_max:
            break

        url = (
            f"https://letterboxd.com/"
            f"{username}/{section}/"
            f"page/{page}/"
        )

        result = None
        page_users = {}

        # ----------------------------------------------------
        # Aynı sayfayı gerektiğinde yeniden dene.
        # ----------------------------------------------------

        for retry in range(PAGE_RETRIES):

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

            # Son sayfa.
            if result["status"] == "END":
                break

            # Başarılı sayfa.
            if result["status"] == "OK":

                page_users = parse_page_users(
                    result["html"]
                )

                # Kullanıcı bulundu.
                if page_users:
                    break

                # HTML geldi ama kişi bulunamadı.
                await asyncio.sleep(
                    2.0 + random.uniform(0.5, 1.0)
                )

                continue

            # Sayfa hatası.
            if result["status"] in (
                "ERROR",
            ):

                if retry < PAGE_RETRIES - 1:
                    await asyncio.sleep(
                        2.5 + retry * 2
                    )
                    continue

                return {
                    "error": (
                        f"{result['html']} "
                        f"(sayfa {page})"
                    ),
                    "users": {},
                    "pages": page - 1
                }

        # ----------------------------------------------------
        # Gerçek 404 / listenin sonu
        # ----------------------------------------------------

        if result and result["status"] == "END":

            if detected_max >= page:
                return {
                    "error": (
                        f"{section} listesinde "
                        f"{page}. sayfa beklenirken 404 döndü."
                    ),
                    "users": {},
                    "pages": page - 1
                }

            break

        # ----------------------------------------------------
        # Sayfa kullanıcı içermedi
        # ----------------------------------------------------

        if not page_users:

            # Eğer ilk sayfadaki pagination toplam sayfa
            # sayısını söylüyorsa burada durmak güvenli değil.
            if detected_max >= page:

                return {
                    "error": (
                        f"{section} listesinde "
                        f"{page}. sayfa alınamadı. "
                        f"Eksik veriyle analiz yapılmadı."
                    ),
                    "users": {},
                    "pages": page - 1
                }

            # Pagination bilinmiyorsa bu son sayfa olabilir.
            break

        # ----------------------------------------------------
        # Pagination gerçekten ilerliyor mu?
        # ----------------------------------------------------

        new_users = {}

        for user, avatar in page_users.items():
            if user not in users:
                new_users[user] = avatar

        # Sayfa tamamen eski kullanıcıları döndürüyorsa
        # pagination ilerlemiyor demektir.
        if not new_users:

            if detected_max >= page:

                return {
                    "error": (
                        f"{section} listesinde "
                        f"{page}. sayfa önceki sayfayla "
                        f"aynı kullanıcıları döndürdü. "
                        f"Pagination güvenilir değil."
                    ),
                    "users": {},
                    "pages": page - 1
                }

            break

        # Yeni kullanıcıları ekle.
        users.update(new_users)

        # Eğer bilinen son sayfaya ulaştıysak bitir.
        if detected_max > 1 and page >= detected_max:
            break

        page += 1

    return {
        "error": None,
        "users": users,
        "pages": page - 1
    }


# ============================================================
# ANA ASYNC
# ============================================================

async def run_analysis(username, proxy_url):

    async with AsyncSession() as session:

        # ====================================================
        # ÖNCE FOLLOWING
        # ====================================================

        following = await scrape_target(
            session=session,
            username=username,
            section="following",
            proxy_url=proxy_url
        )

        # Kullanıcı bulunamadı.
        if following["error"] == "USER_NOT_FOUND":
            return {
                "error": "USER_NOT_FOUND"
            }

        # Following tamamlanamadıysa dur.
        if following["error"]:
            return {
                "error": (
                    "Following taraması tamamlanamadı: "
                    + str(following["error"])
                )
            }

        # ====================================================
        # SONRA FOLLOWERS
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
        # SADECE İKİSİ DE TAMAMLANINCA SONUÇ
        # ====================================================

        return {
            "error": None,
            "following": following,
            "followers": followers
        }


# ============================================================
# CACHE'Lİ ANALİZ
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
        return asyncio.run(
            run_analysis(
                username,
                proxy_url
            )
        )

    except Exception as exc:
        return {
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
            "Önce following, ardından followers "
            "eksiksiz şekilde taranıyor."
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
                "Proxy ayarı bulunamadı. "
                "Streamlit Secrets bölümünde "
                "DATAIMPULSE_PROXY kontrol edilmeli."
            )

        elif data["error"] == "USER_NOT_FOUND":

            st.error(
                "Bu kullanıcı bulunamadı. "
                "Kullanıcı adınızı kontrol ediniz."
            )

        elif data["error"]:

            st.error(
                "Analiz güvenli şekilde tamamlanamadı."
            )

            st.caption(
                str(data["error"])
            )

        else:

            following_data = data["following"]
            followers_data = data["followers"]

            following = following_data["users"]
            followers = followers_data["users"]

            # =================================================
            # ÖNEMLİ:
            # İKİ LİSTE TAMAMEN ÇEKİLDİKTEN SONRA FARK
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

                        username, image_url = users[index]

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
