# Scrapy settings for scraper project
#
# For simplicity, this file contains only settings considered important or
# commonly used. You can find more settings consulting the documentation:
#
#     https://docs.scrapy.org/en/latest/topics/settings.html
#     https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#     https://docs.scrapy.org/en/latest/topics/spider-middleware.html

BOT_NAME = "scraper"

SPIDER_MODULES = ["scraper.spiders"]
NEWSPIDER_MODULE = "scraper.spiders"

ADDONS = {}


# Ehrliche, sprechende Kennung statt "Scrapy/2.x": Betreiber koennen den
# Crawler zuordnen und im Zweifel Kontakt aufnehmen, statt ihn stumm zu
# sperren. Kontaktadresse gerne ergaenzen: "... (+mailto:...)".
USER_AGENT = (
    "BachelorarbeitBot/1.0 (akademische Datenerhebung, Autokorrelation "
    "von Spielergebnissen; scrapy)"
)

# Obey robots.txt rules
# robots.txt von fussball.de (Stand 08/2026): "Allow: /", gesperrt sind nur
# /*-service/ und /tipply/ – kein Crawl-delay vorgegeben.
ROBOTSTXT_OBEY = True

# --- Drosselung: zuegig, aber gleichmaessig und selbstbremsend ------------
# Gemessene Antwortzeit einer Spielseite: ~0,12 s bei ~25 KB (gzip).
# DOWNLOAD_DELAY ist der Mindestabstand zwischen zwei Requests derselben
# Domain und damit die eigentliche Ratenbremse: Rate ~= 1 / DOWNLOAD_DELAY.
# 0,3 s -> ~3 Anfragen/s (~75 KB/s) – fuer ein Portal dieser Groesse zahm,
# aber ~7x schneller als die urspruenglichen 2,0 s.
# Wer noch vorsichtiger sein will: DOWNLOAD_DELAY hochsetzen (0,5 -> 2/s).
CONCURRENT_REQUESTS = 8
CONCURRENT_REQUESTS_PER_DOMAIN = 4  # deckt Latenzspitzen ab, ohne die Rate zu erhoehen
DOWNLOAD_DELAY = 0.3            # Grundpause zwischen Requests (Sekunden)
RANDOMIZE_DOWNLOAD_DELAY = True  # streut die Pause -> weniger "botartig"

# AutoThrottle bleibt an: wird der Server langsamer (= Last), vergroessert
# sich der Abstand automatisch. Das ist die Sicherung gegen eine Sperre.
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1.0
AUTOTHROTTLE_MAX_DELAY = 60.0          # im Notfall weit runterregeln duerfen
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0
AUTOTHROTTLE_DEBUG = False

# --- Robustheit: Timeouts, Retries, saubere Wiederholungen ----------------
# Bei ~10.000 Seiten sind einzelne Aussetzer statistisch sicher; lieber
# mehrfach mit wachsendem Abstand wiederholen als Luecken im Datensatz.
DOWNLOAD_TIMEOUT = 30
RETRY_ENABLED = True
RETRY_TIMES = 5
RETRY_HTTP_CODES = [429, 500, 502, 503, 504, 522, 524, 408]

# --- HTTP-Cache: Reproduzierbarkeit + kein doppelter Traffic --------------
# Der wichtigste Schalter fuer wissenschaftliches Arbeiten: einmal geholte
# Seiten liegen lokal, spaetere Laeufe und Re-Extraktionen kosten kein Netz
# und liefern exakt dasselbe HTML.
HTTPCACHE_ENABLED = True
HTTPCACHE_DIR = "httpcache"
HTTPCACHE_EXPIRATION_SECS = 0          # nie verfallen
HTTPCACHE_STORAGE = "scrapy.extensions.httpcache.FilesystemCacheStorage"
HTTPCACHE_IGNORE_HTTP_CODES = [429, 500, 502, 503, 504]  # Fehler nicht cachen

# --- HTTP-Verhalten -------------------------------------------------------
COOKIES_ENABLED = True          # fussball.de setzt teils Session-Cookies
HTTPERROR_ALLOW_ALL = False     # 4xx/5xx nicht ins parse durchreichen
REDIRECT_ENABLED = True
AJAXCRAWL_ENABLED = True        # hilft teils bei "#!"-Fragment-Seiten

DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9",
}

# --- Logging & Abschlussbedingungen --------------------------------------
LOG_LEVEL = "INFO"
LOG_FILE = "scrapy.log"         # Lauf nachvollziehbar dokumentieren

# --- Ausgabe -------------------------------------------------------------
# Encoding fuer Umlaute in Vereinsnamen.
FEED_EXPORT_ENCODING = "utf-8"

# Zukunftssicheres Standardverhalten neuerer Scrapy-Versionen:
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
