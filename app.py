import streamlit as st
from bs4 import BeautifulSoup
from curl_cffi.requests import Session

import time
import random
import re

from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
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

    .progress-box {
        background-color: #121E15;
        border: 1px solid #1A2E20;
        padding: 10px;
        border-radius: 12px;
        text-align: center;
        color: #9CAF9F;
        margin-bottom: 12px;
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

# Cache 10 dakika
CACHE_TTL = 600

# Cache versiyonu.
# Kod değiştiğinde yükseltilebilir.
CACHE_VERSION = "v10"

# Kontrollü paralellik.
# Çok yüksek tutulmuyor çünkü fazla eşzamanlı
# istekler rate-limit / challenge ihtimalini artırabilir.
MAX_WORKERS = 3

# Sayfalar arası küçük bekleme.
MIN_DELAY = 0.8
MAX_DELAY = 1.5

# HTTP retry
MAX_RETRIES = 2

# Request timeout
REQUEST_TIMEOUT = 25

# Sonsuz pagination güvenliği
MAX_PAGES = 500


# ============================================================
# RESERVED PATHS
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


# ============================================================
# USERNAME ÇIKAR
# ============================================================

def extract_username(href):

    if not href:
        return None

    href = href.strip()

    # Tam URL ise path'i al
    if href.startswith(
        "http://"
    ) or href.startswith(
        "https://"
    ):

        parts = href.split(
            "://",
            1
        )

        if len(parts) != 2:
            return None

        path = parts[1]

        slash_index = path.find("/")

        if slash_index == -1:
            return None

        path = path[slash_index:]

    else:

        path = href

    path = path.split(
        "?",
        1
    )[0]

    path = path.split(
        "#",
        1
    )[0]

    path = path.strip("/")

    if not path:
        return None

    # /username/films gibi linkleri alma
    if "/" in path:
        return None

    username = path.lower()

    if username in RESERVED_PATHS:
        return None

    if not re.fullmatch(
        r"[a-z0-9_-]+",
        username
    ):
        return None

    return username


# ============================================================
# SADECE USERNAME PARSE
# ============================================================

def parse_usernames(html):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    users = set()

    # --------------------------------------------------------
    # Öncelik: person-summary
    # --------------------------------------------------------

    cards = soup.select(
        ".person-summary"
    )

    for card in cards:

        links = card.find_all(
            "a",
            href=True
        )

        for link in links:

            username = extract_username(
                link.get("href")
            )

            if username:

                users.add(
                    username
                )

                break

    # --------------------------------------------------------
    # Fallback
    # --------------------------------------------------------

    if not users:

        for link in soup.find_all(
            "a",
            href=True
        ):

            username = extract_username(
                link.get("href")
            )

            if username:

                users.add(
                    username
                )

    return users


# ============================================================
# CLOUDFLARE KONTROL
# ============================================================

def looks_like_cloudflare(html):

    if not html:
        return False

    text = html.lower()

    markers = [
        "just a moment...",
        "cf-chl-",
        "challenge-platform",
        "verify you are human",
        "checking your browser",
        "enable javascript and cookies",
        "attention required"
    ]

    for marker in markers:

        if marker in text:
            return True

    return False


# ============================================================
# PAGINATION SAYFALARINI BUL
# ============================================================

def get_pagination_pages(
    html,
    current_url
):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    page_numbers = {
        1
    }

    # --------------------------------------------------------
    # Sayfadaki /page/N linkleri
    # --------------------------------------------------------

    for link in soup.find_all(
        "a",
        href=True
    ):

        href = link.get(
            "href",
            ""
        )

        absolute_url = urljoin(
            current_url,
            href
        )

        match = re.search(
            r"/page/(\d+)/?",
            absolute_url
        )

        if match:

            number = int(
                match.group(1)
            )

            if 1 <= number <= MAX_PAGES:

                page_numbers.add(
                    number
                )

    # --------------------------------------------------------
    # rel next varsa onun page numarasını da ekle
    # --------------------------------------------------------

    next_link = soup.find(
        "a",
        rel=lambda value: (
            value
            and "next" in value
        )
        if isinstance(value, list)
        else (
            value
            and "next" in value.lower()
        )
    )

    if next_link:

        href = next_link.get(
            "href"
        )

        if href:

            next_url = urljoin(
                current_url,
                href
            )

            match = re.search(
                r"/page/(\d+)/?",
                next_url
            )

            if match:

                number = int(
                    match.group(1)
                )

                if number <= MAX_PAGES:

                    page_numbers.add(
                        number
                    )

    # --------------------------------------------------------
    # Sayfa linklerinden maksimum sayıyı bul
    # --------------------------------------------------------

    max_page = max(
        page_numbers
    )

    return max_page


# ============================================================
# PAGE URL OLUŞTUR
# ============================================================

def make_page_url(
    username,
    section,
    page
):

    if page <= 1:

        return (
            f"https://letterboxd.com/"
            f"{username}/{section}/"
        )

    return (
        f"https://letterboxd.com/"
        f"{username}/{section}/"
        f"page/{page}/"
    )


# ============================================================
# TEK SAYFA ÇEK
# ============================================================

def fetch_single_page(
    url,
    proxy_url,
    username,
    section,
    page_number
):

    headers = {

        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,"
            "image/avif,image/webp,"
            "*/*;q=0.8"
        ),

        "Accept-Language":
            "en-US,en;q=0.9",

        "Referer":
            f"https://letterboxd.com/"
            f"{username}/{section}/",

        "User-Agent":
            (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            )
    }

    session = Session()

    try:

        for attempt in range(
            MAX_RETRIES + 1
        ):

            try:

                response = session.get(

                    url,

                    proxy=proxy_url,

                    impersonate="chrome",

                    headers=headers,

                    timeout=REQUEST_TIMEOUT,

                    allow_redirects=True
                )

                status = response.status_code

                html = response.text or ""

                # ------------------------------------------------
                # Cloudflare
                # ------------------------------------------------

                if looks_like_cloudflare(
                    html
                ):

                    return {
                        "ok": False,
                        "page": page_number,
                        "users": set(),
                        "error": (
                            "Cloudflare doğrulama "
                            f"sayfası ({section}, "
                            f"sayfa {page_number})"
                        ),
                        "cloudflare": True
                    }

                # ------------------------------------------------
                # Başarılı
                # ------------------------------------------------

                if status == 200:

                    users = parse_usernames(
                        html
                    )

                    return {
                        "ok": True,
                        "page": page_number,
                        "users": users,
                        "error": None,
                        "cloudflare": False
                    }

                # ------------------------------------------------
                # 404
                # ------------------------------------------------

                if status == 404:

                    return {
                        "ok": False,
                        "page": page_number,
                        "users": set(),
                        "error": (
                            f"{section} sayfa "
                            f"{page_number}: HTTP 404"
                        ),
                        "cloudflare": False
                    }

                # ------------------------------------------------
                # 403 / 429
                # ------------------------------------------------

                if status in {
                    403,
                    429
                }:

                    if attempt < MAX_RETRIES:

                        time.sleep(
                            3
                            + attempt * 3
                            + random.uniform(
                                0.5,
                                1.5
                            )
                        )

                        continue

                    return {
                        "ok": False,
                        "page": page_number,
                        "users": set(),
                        "error": (
                            f"{section} sayfa "
                            f"{page_number}: "
                            f"HTTP {status}"
                        ),
                        "cloudflare": False
                    }

                # ------------------------------------------------
                # Diğer HTTP hataları
                # ------------------------------------------------

                if attempt < MAX_RETRIES:

                    time.sleep(
                        2
                        + attempt * 2
                    )

                    continue

                return {
                    "ok": False,
                    "page": page_number,
                    "users": set(),
                    "error": (
                        f"{section} sayfa "
                        f"{page_number}: "
                        f"HTTP {status}"
                    ),
                    "cloudflare": False
                }

            except Exception as exc:

                if attempt < MAX_RETRIES:

                    time.sleep(
                        2
                        + attempt * 2
                    )

                    continue

                return {
                    "ok": False,
                    "page": page_number,
                    "users": set(),
                    "error": (
                        f"{section} sayfa "
                        f"{page_number}: "
                        f"{type(exc).__name__}: "
                        f"{str(exc)[:180]}"
                    ),
                    "cloudflare": False
                }

    finally:

        session.close()


# ============================================================
# İLK SAYFAYI ÇEK
# ============================================================

def fetch_first_page(
    username,
    section,
    proxy_url
):

    url = make_page_url(
        username,
        section,
        1
    )

    result = fetch_single_page(
        url=url,
        proxy_url=proxy_url,
        username=username,
        section=section,
        page_number=1
    )

    if not result["ok"]:

        return result

    # --------------------------------------------------------
    # İlk sayfadan toplam pagination bilgisini bul
    # --------------------------------------------------------

    try:

        with Session() as session:

            response = session.get(

                url,

                proxy=proxy_url,

                impersonate="chrome",

                timeout=REQUEST_TIMEOUT,

                allow_redirects=True
            )

            html = response.text or ""

    except Exception:

        html = ""

    if not html:

        return {
            "ok": False,
            "page": 1,
            "users": set(),
            "error": (
                f"{section} pagination bilgisi "
                "okunamadı."
            ),
            "cloudflare": False
        }

    if looks_like_cloudflare(
        html
    ):

        return {
            "ok": False,
            "page": 1,
            "users": set(),
            "error": (
                f"Cloudflare doğrulama sayfası "
                f"({section}, sayfa 1)"
            ),
            "cloudflare": True
        }

    max_page = get_pagination_pages(
        html,
        url
    )

    return {
        "ok": True,
        "page": 1,
        "users": result["users"],
        "total_pages": max_page,
        "error": None,
        "cloudflare": False
    }


# ============================================================
# LİSTE TARAMA - V2
# ============================================================

def scrape_list_v2(
    username,
    section,
    proxy_url
):

    # --------------------------------------------------------
    # İlk sayfa
    # --------------------------------------------------------

    first = fetch_first_page(
        username=username,
        section=section,
        proxy_url=proxy_url
    )

    if not first["ok"]:

        return {
            "ok": False,
            "users": set(),
            "pages": 0,
            "error": first["error"]
        }

    all_users = set(
        first["users"]
    )

    total_pages = first.get(
        "total_pages",
        1
    )

    # --------------------------------------------------------
    # Güvenlik
    # --------------------------------------------------------

    if total_pages < 1:
        total_pages = 1

    if total_pages > MAX_PAGES:

        return {
            "ok": False,
            "users": set(),
            "pages": 0,
            "error": (
                f"{section} için bulunan "
                f"sayfa sayısı ({total_pages}) "
                f"güvenlik sınırını aşıyor."
            )
        }

    # --------------------------------------------------------
    # Tek sayfa ise bitti
    # --------------------------------------------------------

    if total_pages == 1:

        return {
            "ok": True,
            "users": all_users,
            "pages": 1,
            "error": None
        }

    # --------------------------------------------------------
    # Sayfa URL'lerini oluştur
    # --------------------------------------------------------

    page_jobs = []

    for page_number in range(
        2,
        total_pages + 1
    ):

        page_url = make_page_url(
            username,
            section,
            page_number
        )

        page_jobs.append(
            (
                page_number,
                page_url
            )
        )

    # --------------------------------------------------------
    # Kontrollü paralel tarama
    # --------------------------------------------------------

    errors = []

    completed_pages = 1

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        future_map = {}

        for page_number, page_url in page_jobs:

            future = executor.submit(
                fetch_single_page,
                page_url,
                proxy_url,
                username,
                section,
                page_number
            )

            future_map[
                future
            ] = page_number

        for future in as_completed(
            future_map
        ):

            page_number = future_map[
                future
            ]

            try:

                result = future.result()

            except Exception as exc:

                errors.append(
                    (
                        page_number,
                        f"{type(exc).__name__}: "
                        f"{str(exc)[:180]}"
                    )
                )

                continue

            if not result["ok"]:

                errors.append(
                    (
                        page_number,
                        result["error"]
                    )
                )

                # Cloudflare'a girdiyse
                # kalan sonucu eksik göstermiyoruz.
                continue

            all_users.update(
                result["users"]
            )

            completed_pages += 1

    # --------------------------------------------------------
    # Her sayfa başarıyla alınmadıysa
    # eksik sonuç döndürme.
    # --------------------------------------------------------

    if errors:

        first_error = errors[0]

        return {
            "ok": False,
            "users": set(),
            "pages": completed_pages,
            "error": (
                f"{section} taraması tamamlanamadı. "
                f"{first_error[1]}"
            )
        }

    # --------------------------------------------------------
    # Başarılı
    # --------------------------------------------------------

    return {
        "ok": True,
        "users": all_users,
        "pages": total_pages,
        "error": None
    }


# ============================================================
# ANA ANALİZ
# ============================================================

def run_analysis(
    username,
    proxy_url
):

    # --------------------------------------------------------
    # FOLLOWING
    # --------------------------------------------------------

    following = scrape_list_v2(
        username=username,
        section="following",
        proxy_url=proxy_url
    )

    if not following["ok"]:

        return {
            "ok": False,
            "error": (
                "Following taraması "
                "tamamlanamadı: "
                + str(
                    following["error"]
                )
            )
        }

    # --------------------------------------------------------
    # FOLLOWERS
    # --------------------------------------------------------

    followers = scrape_list_v2(
        username=username,
        section="followers",
        proxy_url=proxy_url
    )

    if not followers["ok"]:

        return {
            "ok": False,
            "error": (
                "Followers taraması "
                "tamamlanamadı: "
                + str(
                    followers["error"]
                )
            )
        }

    # --------------------------------------------------------
    # Başarılı
    # --------------------------------------------------------

    return {
        "ok": True,
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
            "ok": False,
            "error": "PROXY_ERROR"
        }

    try:

        return run_analysis(
            username=username,
            proxy_url=proxy_url
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
            "Takip listeleri taranıyor..."
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
                "Analiz tamamlanamadı."
            )

            error_text = str(
                data["error"]
            )

            if "Cloudflare" in error_text:

                st.warning(
                    "Letterboxd isteği Cloudflare "
                    "doğrulama sayfasına yönlendirdi. "
                    "Eksik listeyle yanlış sonuç "
                    "gösterilmedi."
                )

            st.caption(
                error_text
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

                sonuc = (
                    following
                    - followers
                )

                baslik = (
                    "Takip etmeyenler"
                )

            else:

                sonuc = (
                    followers
                    - following
                )

                baslik = (
                    "Senin takip etmediklerin"
                )

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
                    sonuc
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

                        username = users[
                            index
                        ]

                        safe_username = escape(
                            username
                        )

                        with columns[j]:

                            st.markdown(
                                f"""
                                <div class="card">
                                    <img
                                        src="https://s.ltrbxd.com/static/img/avatar220.png"
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
