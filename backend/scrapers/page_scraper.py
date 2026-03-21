"""
Page Scraper - Foundation of the audit engine.
Uses requests+BeautifulSoup for standard crawling.
Uses Playwright for JavaScript-heavy pages and black hat detection (user-agent switching).
"""

import re
import time
import logging
from urllib.parse import urljoin, urlparse
from typing import Optional

import requests
from bs4 import BeautifulSoup
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

# User agents for cloaking detection
UA_GOOGLEBOT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
UA_DESKTOP = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
UA_MOBILE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"

REQUEST_TIMEOUT = 15
MAX_REDIRECTS = 10


def _make_request(url: str, user_agent: str, timeout: int = REQUEST_TIMEOUT) -> dict:
    """
    Make HTTP request and return structured response data.
    Captures redirect chain, final URL, status codes.
    """
    session = requests.Session()
    session.max_redirects = MAX_REDIRECTS

    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }

    redirect_chain = []
    start_time = time.time()

    try:
        response = session.get(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=True,
            verify=False,
        )

        for r in response.history:
            redirect_chain.append({
                "url": r.url,
                "status_code": r.status_code,
            })

        load_time_ms = int((time.time() - start_time) * 1000)

        return {
            "success": True,
            "url": url,
            "final_url": response.url,
            "status_code": response.status_code,
            "redirect_chain": redirect_chain,
            "redirect_count": len(redirect_chain),
            "html": response.text,
            "headers": dict(response.headers),
            "load_time_ms": load_time_ms,
            "content_length": len(response.content),
            "encoding": response.encoding,
        }

    except requests.exceptions.TooManyRedirects as e:
        return {"success": False, "url": url, "error": f"Too many redirects: {str(e)}", "error_type": "too_many_redirects"}
    except requests.exceptions.ConnectionError as e:
        return {"success": False, "url": url, "error": f"Connection error: {str(e)}", "error_type": "connection_error"}
    except requests.exceptions.Timeout:
        return {"success": False, "url": url, "error": f"Request timed out after {timeout}s", "error_type": "timeout"}
    except requests.exceptions.RequestException as e:
        return {"success": False, "url": url, "error": str(e), "error_type": "request_error"}


def _parse_html(html: str, base_url: str) -> dict:
    """
    Parse HTML with BeautifulSoup and extract all SEO-relevant elements.
    """
    soup = BeautifulSoup(html, "lxml")

    # ── Meta tags ─────────────────────────────────────────────
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else None

    meta_desc_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    meta_description = meta_desc_tag.get("content", "").strip() if meta_desc_tag else None

    meta_robots_tag = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
    meta_robots = meta_robots_tag.get("content", "").strip() if meta_robots_tag else None

    meta_viewport_tag = soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)})
    meta_viewport = meta_viewport_tag.get("content", "").strip() if meta_viewport_tag else None

    # ── Canonical ─────────────────────────────────────────────
    canonical_tag = soup.find("link", attrs={"rel": "canonical"})
    canonical_url = canonical_tag.get("href", "").strip() if canonical_tag else None

    # ── Open Graph ────────────────────────────────────────────
    og_tags = {}
    for tag in soup.find_all("meta", attrs={"property": re.compile(r"^og:", re.I)}):
        prop = tag.get("property", "").lower()
        og_tags[prop] = tag.get("content", "")

    # ── Twitter Card ──────────────────────────────────────────
    twitter_tags = {}
    for tag in soup.find_all("meta", attrs={"name": re.compile(r"^twitter:", re.I)}):
        name = tag.get("name", "").lower()
        twitter_tags[name] = tag.get("content", "")

    # ── Headings ──────────────────────────────────────────────
    headings = {"h1": [], "h2": [], "h3": [], "h4": [], "h5": [], "h6": []}
    for level in headings:
        tags = soup.find_all(level)
        headings[level] = [t.get_text(strip=True) for t in tags if t.get_text(strip=True)]

    # ── Body content ──────────────────────────────────────────
    body_soup = BeautifulSoup(str(soup), "lxml")
    for tag in body_soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()

    body_text = body_soup.get_text(separator=" ", strip=True)
    body_text = re.sub(r'\s+', ' ', body_text).strip()
    word_count = len(body_text.split()) if body_text else 0

    # ── Images ────────────────────────────────────────────────
    images = []
    for img in soup.find_all("img"):
        src = img.get("src", "")
        alt = img.get("alt", None)
        images.append({
            "src": urljoin(base_url, src) if src else "",
            "alt": alt,
            "has_alt": alt is not None,
            "alt_empty": alt == "" if alt is not None else False,
        })

    # ── Links ─────────────────────────────────────────────────
    internal_links = []
    external_links = []
    base_domain = urlparse(base_url).netloc.replace("www.", "")

    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        anchor_text = a.get_text(strip=True)
        rel = a.get("rel", [])
        is_nofollow = "nofollow" in rel

        if not href or href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
            continue

        absolute_href = urljoin(base_url, href)
        link_domain = urlparse(absolute_href).netloc.replace("www.", "")

        link_data = {
            "href": absolute_href,
            "anchor_text": anchor_text,
            "is_nofollow": is_nofollow,
            "rel": rel,
        }

        if link_domain == base_domain or not link_domain:
            internal_links.append(link_data)
        else:
            external_links.append({**link_data, "domain": link_domain})

    # ── Schema / Structured Data ──────────────────────────────
    schema_scripts = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            import json
            data = json.loads(script.string or "{}")
            schema_scripts.append(data)
        except Exception:
            pass

    # ── JavaScript & CSS ──────────────────────────────────────
    js_files = [s.get("src", "") for s in soup.find_all("script", src=True)]
    css_files = [l.get("href", "") for l in soup.find_all("link", rel="stylesheet")]

    # ── Inline styles (for hidden text detection) ─────────────
    inline_styles = []
    for tag in soup.find_all(style=True):
        inline_styles.append({
            "tag": tag.name,
            "style": tag.get("style", ""),
            "text": tag.get_text(strip=True)[:200],
            "html": str(tag)[:500],
        })

    # ── Hreflang ──────────────────────────────────────────────
    hreflang_tags = []
    for link in soup.find_all("link", attrs={"hreflang": True}):
        hreflang_tags.append({
            "hreflang": link.get("hreflang"),
            "href": link.get("href"),
        })

    # ── Iframe detection ──────────────────────────────────────
    iframes = [{"src": f.get("src", ""), "id": f.get("id", "")} for f in soup.find_all("iframe")]

    # ── Popup / Interstitial detection ────────────────────────
    popup_indicators = []
    popup_patterns = [
        r'popup', r'modal', r'overlay', r'interstitial',
        r'newsletter.*signup', r'subscribe.*popup', r'exit.?intent'
    ]
    for script in soup.find_all("script"):
        script_text = script.string or ""
        for pattern in popup_patterns:
            if re.search(pattern, script_text, re.I):
                popup_indicators.append(pattern)
                break

    modal_divs = soup.find_all(
        lambda tag: tag.name == "div" and
        any(c in tag.get("class", []) for c in ["modal", "popup", "overlay", "interstitial"])
    )

    return {
        "title": title,
        "title_length": len(title) if title else 0,
        "meta_description": meta_description,
        "meta_description_length": len(meta_description) if meta_description else 0,
        "meta_robots": meta_robots,
        "meta_viewport": meta_viewport,
        "canonical_url": canonical_url,
        "og_tags": og_tags,
        "twitter_tags": twitter_tags,
        "headings": headings,
        "h1_count": len(headings["h1"]),
        "body_text": body_text,
        "word_count": word_count,
        "images": images,
        "images_without_alt": [img for img in images if not img["has_alt"]],
        "images_empty_alt": [img for img in images if img["alt_empty"]],
        "internal_links": internal_links,
        "external_links": external_links,
        "internal_link_count": len(internal_links),
        "external_link_count": len(external_links),
        "schema_scripts": schema_scripts,
        "js_files": js_files,
        "css_files": css_files,
        "inline_styles": inline_styles,
        "hreflang_tags": hreflang_tags,
        "iframes": iframes,
        "popup_indicators": popup_indicators,
        "modal_divs_count": len(modal_divs),
        "raw_html": html,
        "soup": soup,
    }


def scrape_page(url: str, use_playwright: bool = False) -> dict:
    """
    Main entry point. Scrapes a URL and returns full structured data.
    """
    logger.info(f"Scraping: {url} | Playwright: {use_playwright}")

    if use_playwright:
        return _scrape_with_playwright(url)

    result = _make_request(url, UA_DESKTOP)
    if not result["success"]:
        return result

    parsed = _parse_html(result["html"], result["final_url"])

    return {
        **result,
        **parsed,
        "scrape_method": "requests",
    }


def scrape_for_cloaking_detection(url: str) -> dict:
    """
    Scrapes page THREE times with different user agents to detect cloaking.
    """
    logger.info(f"Cloaking detection scrape: {url}")

    desktop_result = _make_request(url, UA_DESKTOP)
    googlebot_result = _make_request(url, UA_GOOGLEBOT)
    mobile_result = _make_request(url, UA_MOBILE)

    results = {}
    for key, result in [("desktop", desktop_result), ("googlebot", googlebot_result), ("mobile", mobile_result)]:
        if result["success"]:
            parsed = _parse_html(result["html"], result.get("final_url", url))
            results[key] = {**result, **parsed}
        else:
            results[key] = result

    return results


def scrape_robots_txt(url: str) -> dict:
    """
    Fetches and parses robots.txt for the domain.
    """
    parsed_url = urlparse(url)
    robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"

    result = _make_request(robots_url, UA_DESKTOP)
    if not result["success"] or result["status_code"] != 200:
        return {
            "found": False,
            "url": robots_url,
            "content": None,
            "disallow_all": False,
            "sitemap_urls": [],
        }

    content = result["html"]
    lines = content.split("\n")

    sitemap_urls = []
    disallow_rules = []
    allow_rules = []
    is_disallow_all = False

    current_agent = None
    for line in lines:
        line = line.strip()
        if line.lower().startswith("user-agent:"):
            current_agent = line.split(":", 1)[1].strip()
        elif line.lower().startswith("disallow:"):
            rule = line.split(":", 1)[1].strip()
            disallow_rules.append({"agent": current_agent, "rule": rule})
            if rule == "/":
                is_disallow_all = True
        elif line.lower().startswith("allow:"):
            rule = line.split(":", 1)[1].strip()
            allow_rules.append({"agent": current_agent, "rule": rule})
        elif line.lower().startswith("sitemap:"):
            sitemap_url = line.split(":", 1)[1].strip()
            sitemap_urls.append(sitemap_url)

    return {
        "found": True,
        "url": robots_url,
        "content": content,
        "disallow_all": is_disallow_all,
        "disallow_rules": disallow_rules,
        "allow_rules": allow_rules,
        "sitemap_urls": sitemap_urls,
    }


def scrape_sitemap(url: str) -> dict:
    """
    Attempts to find and parse XML sitemap.
    """
    parsed_url = urlparse(url)
    base = f"{parsed_url.scheme}://{parsed_url.netloc}"

    candidate_urls = [
        f"{base}/sitemap.xml",
        f"{base}/sitemap_index.xml",
        f"{base}/sitemap/sitemap.xml",
    ]

    for sitemap_url in candidate_urls:
        result = _make_request(sitemap_url, UA_DESKTOP)
        if result["success"] and result["status_code"] == 200:
            try:
                from bs4 import BeautifulSoup as BS
                sitemap_soup = BS(result["html"], "xml")
                urls = [loc.get_text(strip=True) for loc in sitemap_soup.find_all("loc")]
                return {
                    "found": True,
                    "url": sitemap_url,
                    "url_count": len(urls),
                    "urls_sample": urls[:20],
                    "is_index": bool(sitemap_soup.find("sitemapindex")),
                }
            except Exception as e:
                logger.warning(f"Failed to parse sitemap: {e}")

    return {"found": False, "url": None, "url_count": 0, "urls_sample": []}


def _scrape_with_playwright(url: str) -> dict:
    """
    Playwright-based scraping for JS-heavy pages.
    Tracks only HTML page URLs as final_url — ignores JS/CSS asset redirects.
    Falls back to requests if Playwright not available.
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=UA_DESKTOP,
                viewport={"width": 1280, "height": 720},
            )
            page = context.new_page()

            redirect_chain = []
            final_url = url
            html_final_url = url  # Tracks last HTML page URL (not JS/CSS assets)

            def handle_response(response):
                nonlocal final_url, html_final_url
                if response.status in [301, 302, 303, 307, 308]:
                    redirect_chain.append({
                        "url": response.url,
                        "status_code": response.status,
                    })
                final_url = response.url
                # Only update html_final_url for actual HTML pages
                resp_url = response.url.lower().split("?")[0]
                non_html_extensions = ('.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg',
                                     '.woff', '.woff2', '.ttf', '.ico', '.json', '.xml', '.pdf')
                content_type = response.headers.get("content-type", "")
                is_html = "text/html" in content_type
                is_asset = any(resp_url.endswith(ext) for ext in non_html_extensions)
                is_api = "/api/" in response.url or "/v1/" in response.url or "/v2/" in response.url

                if is_html and not is_asset and not is_api:
                    html_final_url = response.url

            page.on("response", handle_response)

            start_time = time.time()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(2000)
            except PlaywrightTimeout:
                browser.close()
                logger.warning(f"Playwright timeout for {url}, falling back to requests")
                return scrape_page(url, use_playwright=False)

            html = page.content()
            load_time_ms = int((time.time() - start_time) * 1000)
            status_code = 200

            js_redirect_detected = page.evaluate("""
                () => {
                    const scripts = Array.from(document.querySelectorAll('script'));
                    const redirectPatterns = [
                        /setTimeout.*window\\.location/s,
                        /window\\.location\\s*=/,
                        /window\\.location\\.replace/,
                        /window\\.location\\.href\\s*=/,
                        /document\\.location\\s*=/,
                    ];
                    for (const script of scripts) {
                        const text = script.textContent || '';
                        for (const pattern of redirectPatterns) {
                            if (pattern.test(text)) return true;
                        }
                    }
                    return false;
                }
            """)

            browser.close()

        # Use html_final_url — the last HTML page URL, not a JS/CSS asset URL
        actual_final_url = html_final_url if html_final_url != url else final_url
        parsed = _parse_html(html, actual_final_url)

        return {
            "success": True,
            "url": url,
            "final_url": actual_final_url,
            "status_code": status_code,
            "redirect_chain": redirect_chain,
            "redirect_count": len(redirect_chain),
            "html": html,
            "load_time_ms": load_time_ms,
            "content_length": len(html),
            "js_redirect_detected": js_redirect_detected,
            "scrape_method": "playwright",
            **parsed,
        }

    except ImportError:
        logger.warning("Playwright not installed, falling back to requests")
        result = scrape_page(url, use_playwright=False)
        result["scrape_method"] = "requests_fallback"
        return result
    except Exception as e:
        logger.error(f"Playwright error for {url}: {e}")
        result = scrape_page(url, use_playwright=False)
        result["scrape_method"] = "requests_fallback"
        result["playwright_error"] = str(e)
        return result