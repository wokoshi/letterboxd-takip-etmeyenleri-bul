```python
import streamlit as st
from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession
import asyncio
import random
import re
from urllib.parse import urlparse
from html import escape


# =========================================================
# STREAMLIT AYARLARI
# =========================================================

st.set_page_config(
    page_title="Letterboxd Takip Analizi",
    page_icon="🔍",
    layout="centered"
)


# =========================================================
# TASARIM
# =========================================================

st.markdown("""
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

.warning-box {
    background-color: #241F12;
    border: 1px solid #4D4225;
    padding: 12px;
    border-radius: 12px;
    color: #D5C58A;
    margin-top: 12px;
}

.success-box {
    background-color: #102016;
    border: 1px solid #244A30;
    padding: 12px;
    border-radius: 12px;
    color: #9EC9A7;
    margin-top: 12px;
}
</style>
""", unsafe_allow_html=True)


# =========================================================
# BAŞLIK
# =========================================================

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


# =========================================================
# MOD
# =========================================================

islem_modu = st.radio(
    "",
    ["Beni Takip Etmeyenler", "Benim Takip Etmediklerim"],
    horizontal=True
)

hedef_kullanici = st.text_input(
    "Kullanıcı adınızı giriniz:",
    placeholder="örnek: wokoshi"
)


# =========================================================
# AYARLAR
# =========================================================

# Başka kod değişiklikleri olduğunda eski cache'i manuel
# olarak bozabilmek için versiyon.
CACHE_VERSION = "v4"

# Free Streamlit planı için makul cache.
# Aynı kullanıcıyı kısa sürede tekrar taramaz.
CACHE_TTL = 600  # 10 dakika

# Letterboxd tarafına gereksiz hızlı istek göndermemek için
# sayfalar arasında küçük bir bekleme.
PAGE_DELAY_MIN = 0.65
PAGE_DELAY_MAX = 1.20

# Bir sayfa boş/şüpheli gelirse hemen bitirmiyoruz.
EMPTY_PAGE_RETRIES = 2

# Bir sayfa aynı kullanıcı listesini döndürürse,
# pagination'ın ilerlemediğini düşünüyoruz.
DUPLICATE_PAGE_RETRIES = 2

# Tek analizde sonsuz döngü olmasını engeller.
MAX_PAGES = 500


# =========================================================
# LETTERBOXD HTML PARSER
# =========================================================

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
    "films-liked",
    "films-watched",
    "following",
    "followers",
    "pro",
}


def normalize_url(url):
    """
    Letterboxd'ın lazy-load image URL'lerini normalleştirir.
    """
    if not url:
        return None

    url = url.strip()

    if url.startswith("//"):
        return "https:" + url

    return url


def extract_image_url(person):
    """
    Avatar için mümkün olan farklı HTML attribute'larını kontrol eder.
    """

    img = person.find("img")

    if not img:
        return "https://s.ltrbxd.com/static/img/avatar220.png"

    candidates = [
        img.get("src"),
        img.get("data-src"),
        img.get("data-original"),
    ]

    for candidate in candidates:
        candidate = normalize_url(candidate)

        if candidate:
            return candidate

    # srcset varsa ilk resmi al
    srcset = img.get("srcset")

    if srcset:
        first = srcset.split(",")[0].strip().split(" ")[0]
        first = normalize_url(first)

        if first:
            return first

    return "https://s.ltrbxd.com/static/img/avatar220.png"


def extract_username_from_href(href):
    """
    /username/ formatındaki Letterboxd profil linkinden
    kullanıcı adını çıkarır.

    Nav linklerini yanlışlıkla kullanıcı sanmamak için
    ekstra filtreler uygulanır.
    """

    if not href:
        return None

    href = href.strip()

    # Absolute URL ise path'e çevir
    if href.startswith("http"):
        try:
            path = urlparse(href).path
        except Exception:
            return None
    else:
        path = href

    # Query/hash temizle
    path = path.split("?")[0].split("#")[0]

    # Baştaki/sondaki slashları kaldır
    path = path.strip("/")

    # Profil URL'si tam olarak tek path segmenti olmalı
    if not path or "/" in path:
        return None

    username = path.lower()

    # Letterboxd sistem sayfaları
    if username in RESERVED_PATHS:
        return None

    # Profil username karakterleri
    if not re.fullmatch(r"[a-z0-9_-]+", username):
        return None

    return username


def parse_page_users(html):
    """
    Bir Letterboxd followers/following sayfasındaki kullanıcıları çıkarır.

    Öncelik:
        .person-summary

    Fallback:
        /username/ biçimindeki profil linkleri
    """

    soup = BeautifulSoup(html, "html.parser")

    users = {}

    # -----------------------------------------------------
    # 1) Normal Letterboxd kişi kartları
    # -----------------------------------------------------

    people = soup.select(".person-summary")

    for person in people:

        # Avatar veya isim linkini tercih et
        anchors = person.select("a.avatar, a.name")

        if not anchors:
            anchors = person.find_all("a", href=True)

        username = None

        for anchor in anchors:
            username = extract_username_from_href(
                anchor.get("href")
            )

            if username:
                break

        if not username:
            continue

        img_url = extract_image_url(person)

        users[username] = img_url

    # -----------------------------------------------------
    # 2) Fallback parser
    # -----------------------------------------------------
    #
    # Letterboxd'ın HTML sınıfı değişirse tamamen boş
    # kalmamak için genel profil linklerini de kontrol ederiz.
    #
    # Ama bunu yalnızca normal parser hiçbir şey bulamazsa
    # çalıştırıyoruz.
    # -----------------------------------------------------

    if not users:

        for anchor in soup.find_all("a", href=True):

            username = extract_username_from_href(
                anchor.get("href")
            )

            if not username:
                continue

            # Nav'dan gelen linkleri mümkün olduğunca
            # filtrelemek için üst elementte kişi kartı
            # benzeri içerik arıyoruz.
            parent_text = anchor.parent.get_text(
                " ",
                strip=True
            ) if anchor.parent else ""

            # Profil linkinin gerçekten kullanıcı kartına
            # ait olduğunu anlamaya çalış.
            has_image = bool(
                anchor.find("img")
                or anchor.parent.find("img")
                if anchor.parent
                else False
            )

            if has_image or parent_text == anchor.get_text(
                " ",
                strip=True
            ):

                img_url = (
                    extract_image_url(anchor.parent)
                    if anchor.parent
                    else "https://s.ltrbxd.com/static/img/avatar220.png"
                )

                users[username] = img_url

    return users


# =========================================================
# PAGINATION TESPİTİ
# =========================================================

def detect_max_page(html):
    """
    İlk sayfanın HTML'inde görünen pagination linklerinden
    maksimum sayıyı bulur.

    Letterboxd farklı pagination biçimleri kullanabileceği
    için birden fazla pattern denenir.
    """

    soup = BeautifulSoup(html, "html.parser")

    max_page = 1

    # -----------------------------------------------------
    # Tüm a[href] linkleri içerisinde page/N ara
    # -----------------------------------------------------

    for anchor in soup.find_all("a", href=True):

        href = anchor.get("href", "")

        patterns = [
            r"/page/(\d+)/",
            r"/page/(\d+)$",
            r"[?&]page=(\d+)",
        ]

        for pattern in patterns:

            match = re.search(pattern, href)

            if match:

                try:
                    page_number = int(match.group(1))

                    if page_number > max_page:
                        max_page = page_number

                except ValueError:
                    pass

    return max_page


# =========================================================
# CLOUDFLARE / GEÇERLİ SAYFA KONTROLÜ
# =========================================================

def is_challenge_page(text):
    """
    200 status kodu gelip gerçek sayfa yerine
    Cloudflare/anti-bot sayfası dönerse yakalar.
    """

    lowered = text.lower()

    challenge_markers = [
        "just a moment",
        "cf-chl-",
        "challenge-platform",
        "cloudflare ray id",
        "verify you are human",
        "checking your browser",
        "enable javascript and cookies",
    ]

    return any(
        marker in lowered
        for marker in challenge_markers
    )


def looks_like_letterboxd_page(html):
    """
    HTML'in gerçek Letterboxd sayfasına benziyor mu?
    """

    if not html:
        return False

    if is_challenge_page(html):
        return False

    soup = BeautifulSoup(html, "html.parser")

    title = soup.title.get_text(
        " ",
        strip=True
    ).lower() if soup.title else ""

    # Letterboxd domain/title izi
    has_letterboxd_title = "letterboxd" in title

    # Normal kullanıcı kartı
    has_person_summary = bool(
        soup.select(".person-summary")
    )

    # Pagination
    has_pagination = bool(
        soup.select(
            ".paginate-pages, .pagination, nav.pagination"
        )
    )

    # Bunlardan biri yeterli
    return (
        has_letterboxd_title
        or has_person_summary
        or has_pagination
    )


# =========================================================
# TEK SAYFA İNDİRME
# =========================================================

async def fetch_page(
    session,
    url,
    proxy_url,
    kullanici_adi,
    tip,
    page_number,
    max_retries=4,
):
    """
    Tek bir sayfayı güvenli şekilde indirir.

    Önemli:
    200 dönmesi tek başına başarılı kabul edilmez.
    HTML'in gerçekten Letterboxd sayfası olması kontrol edilir.
    """

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
            f"{kullanici_adi}/{tip}/"
        ),
        "Cache-Control": "no-cache",
    }

    last_error = "UNKNOWN"

    for attempt in range(max_retries):

        try:

            res = await session.get(
                url,
                proxy=proxy_url,
                impersonate="chrome",
                headers=headers,
                timeout=20,
                allow_redirects=True,
                trust_env=False,
            )

            status = res.status_code
            text = res.text or ""

            # -------------------------------------------------
            # 404
            # -------------------------------------------------

            if status == 404:

                if page_number == 1:
                    return {
                        "ok": False,
                        "kind": "USER_NOT_FOUND",
                        "status": 404,
                        "html": "",
                    }

                return {
                    "ok": False,
                    "kind": "END",
                    "status": 404,
                    "html": "",
                }

            # -------------------------------------------------
            # Gerçek başarılı sayfa
            # -------------------------------------------------

            if status == 200 and looks_like_letterboxd_page(text):

                return {
                    "ok": True,
                    "kind": "PAGE",
                    "status": 200,
                    "html": text,
                }

            # -------------------------------------------------
            # Challenge / boş / şüpheli cevap
            # -------------------------------------------------

            if status == 200:

                last_error = (
                    f"Şüpheli HTML "
                    f"(sayfa {page_number}, deneme {attempt + 1})"
                )

                await asyncio.sleep(
                    1.5 + (attempt * 1.5)
                    + random.uniform(0.3, 0.8)
                )

                continue

            # -------------------------------------------------
            # 403 / 429 / 5xx
            # -------------------------------------------------

            if status in (403, 429, 500, 502, 503, 504):

                last_error = f"HTTP {status}"

                # Giderek artan bekleme
                wait_time = (
                    2.5 * (attempt + 1)
                    + random.uniform(0.5, 1.5)
                )

                await asyncio.sleep(wait_time)

                continue

            # -------------------------------------------------
            # Diğer status
            # -------------------------------------------------

            last_error = f"HTTP {status}"

            await asyncio.sleep(
                1.0 + random.uniform(0.5, 1.0)
            )

        except Exception as exc:

            last_error = (
                f"{type(exc).__name__}: {str(exc)[:150]}"
            )

            await asyncio.sleep(
                1.5 + (attempt * 1.5)
            )

    return {
        "ok": False,
        "kind": "BLOCK",
        "status": last_error,
        "html": "",
    }


# =========================================================
# BİR LİSTEYİ TAMAMEN TARAMA
# =========================================================

async def scrape_target(
    session,
    kullanici_adi,
    tip,
    proxy_url,
):
    """
    Following veya followers listesini tamamen toplar.

    Kritik prensip:
    Şüpheli pagination durumunda PARTİAL LİSTE döndürmez.
    Bunun yerine hata verir.

    Böylece:
        eksik following
        +
        tam followers
        =
        sahte unfollower
    problemi engellenir.
    """

    base_url = (
        f"https://letterboxd.com/"
        f"{kullanici_adi}/{tip}/"
    )

    # -----------------------------------------------------
    # 1. sayfa
    # -----------------------------------------------------

    first = await fetch_page(
        session=session,
        url=base_url,
        proxy_url=proxy_url,
        kullanici_adi=kullanici_adi,
        tip=tip,
        page_number=1,
    )

    if first["kind"] == "USER_NOT_FOUND":
        return None

    if not first["ok"]:
        return {
            "error": (
                f"{first['status']}"
            ),
            "users": {},
            "pages": 0,
        }

    first_html = first["html"]

    users = parse_page_users(first_html)

    # Hesap gerçekten boş olabilir
    if not users:
        return {
            "error": None,
            "users": {},
            "pages": 1,
            "expected_pages": 1,
        }

    expected_pages = detect_max_page(first_html)

    # -----------------------------------------------------
    # Pagination
    # -----------------------------------------------------
    #
    # Birinci sayfadan max page bulunursa onu kullanıyoruz.
    #
    # Bulunamazsa:
    #   2
    #   3
    #   4
    #   ...
    #
    # şeklinde kontrollü olarak devam ediyoruz.
    # -----------------------------------------------------

    page = 2

    while page <= MAX_PAGES:

        # İlk sayfada pagination bulunduysa,
        # gereksiz sayfa istemiyoruz.
        if expected_pages > 1 and page > expected_pages:
            break

        await asyncio.sleep(
            random.uniform(
                PAGE_DELAY_MIN,
                PAGE_DELAY_MAX
            )
        )

        url = (
            f"https://letterboxd.com/"
            f"{kullanici_adi}/{tip}/page/{page}/"
        )

        retry_count = 0
        duplicate_retry = 0
        page_finished = False

        while retry_count < EMPTY_PAGE_RETRIES:

            result = await fetch_page(
                session=session,
                url=url,
                proxy_url=proxy_url,
                kullanici_adi=kullanici_adi,
                tip=tip,
                page_number=page,
            )

            # -------------------------------------------------
            # Sayfa sonu
            # -------------------------------------------------

            if result["kind"] == "END":

                if expected_pages >= page:
                    return {
                        "error": (
                            f"Pagination hatası: "
                            f"{tip} listesinde beklenen "
                            f"{page}. sayfa 404 döndü."
                        ),
                        "users": {},
                        "pages": page - 1,
                    }

                page_finished = True
                break

            # -------------------------------------------------
            # Sayfa isteği bloklandı
            # -------------------------------------------------

            if not result["ok"]:

                return {
                    "error": (
                        f"{result['status']} "
                        f"(sayfa {page})"
                    ),
                    "users": {},
                    "pages": page - 1,
                }

            page_html = result["html"]

            page_users = parse_page_users(page_html)

            # -------------------------------------------------
            # Boş sayfa
            # -------------------------------------------------

            if not page_users:

                # max page biliniyorsa burada bitmesi beklenmiyor
                if expected_pages >= page:

                    retry_count += 1

                    if retry_count < EMPTY_PAGE_RETRIES:

                        await asyncio.sleep(
                            2.0
                            + random.uniform(0.5, 1.0)
                        )

                        continue

                    return {
                        "
```
