"""
Technical SEO Analyzer
Checks all technical on-page SEO factors and returns structured findings.
Each check returns: status (pass/warning/fail), message, severity, recommendation.
"""

import re
import logging
from urllib.parse import urlparse, urlunparse
from typing import Optional

logger = logging.getLogger(__name__)

# ── Severity levels ───────────────────────────────────────────────────────────
PASS = "pass"
WARNING = "warning"
FAIL = "fail"

SEV_LOW = "low"
SEV_MEDIUM = "medium"
SEV_HIGH = "high"
SEV_CRITICAL = "critical"


def _issue(check_id: str, status: str, severity: str, message: str,
           recommendation: str, value=None, impact: str = "") -> dict:
    return {
        "check_id": check_id,
        "status": status,
        "severity": severity,
        "message": message,
        "recommendation": recommendation,
        "value": value,
        "impact": impact,
    }


def _normalize_url(u: str) -> str:
    """
    Normalize URL for comparison:
    - Lowercase scheme and host
    - Strip www.
    - Strip trailing slash from path (except root)
    - Strip fragment
    - Strip query string for canonical comparison
    """
    try:
        p = urlparse(u.strip())
        host = p.netloc.lower().replace("www.", "")
        path = p.path.rstrip("/") or "/"
        return urlunparse((p.scheme.lower(), host, path, "", "", ""))
    except Exception:
        return u.strip().rstrip("/").lower()


# ═══════════════════════════════════════════════════════════════════════════════
# TITLE TAG CHECKS
# ═══════════════════════════════════════════════════════════════════════════════

def check_title(page_data: dict) -> list:
    results = []
    title = page_data.get("title")
    length = page_data.get("title_length", 0)

    if not title:
        results.append(_issue(
            "title_missing", FAIL, SEV_CRITICAL,
            "Page has no title tag",
            "Add a descriptive title tag. This is the most critical on-page SEO element.",
            impact="Title tags are the #1 on-page ranking factor. Missing title = severely hurts rankings."
        ))
        return results

    if length < 10:
        results.append(_issue(
            "title_too_short", FAIL, SEV_HIGH,
            f"Title is too short ({length} chars): '{title}'",
            "Write a descriptive title between 50-60 characters that includes your primary keyword.",
            value=length,
            impact="Titles under 10 chars provide no ranking signal and look unprofessional in SERPs."
        ))
    elif length < 30:
        results.append(_issue(
            "title_short", WARNING, SEV_MEDIUM,
            f"Title is short ({length} chars): '{title}'",
            "Expand title to 50-60 characters. Include primary keyword and value proposition.",
            value=length
        ))
    elif length > 60:
        results.append(_issue(
            "title_too_long", WARNING, SEV_MEDIUM,
            f"Title is too long ({length} chars) and will be truncated in SERPs: '{title[:60]}...'",
            "Trim title to 50-60 characters. Front-load your primary keyword.",
            value=length
        ))
    else:
        results.append(_issue(
            "title_length_ok", PASS, SEV_LOW,
            f"Title length is good ({length} chars)",
            "", value=length
        ))

    weak_patterns = ["home", "welcome", "index", "page 1", "untitled", "new page"]
    if any(title.lower().strip() == p for p in weak_patterns):
        results.append(_issue(
            "title_generic", FAIL, SEV_HIGH,
            f"Title is generic/placeholder: '{title}'",
            "Replace with a keyword-rich, descriptive title specific to this page's content.",
            impact="Generic titles waste your most important on-page SEO element."
        ))

    if title == title.upper() and len(title) > 5:
        results.append(_issue(
            "title_all_caps", WARNING, SEV_LOW,
            "Title is in ALL CAPS which looks spammy in SERPs",
            "Use title case formatting. ALL CAPS can deter clicks and looks unprofessional."
        ))

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# META DESCRIPTION CHECKS
# ═══════════════════════════════════════════════════════════════════════════════

def check_meta_description(page_data: dict) -> list:
    results = []
    meta_desc = page_data.get("meta_description")
    length = page_data.get("meta_description_length", 0)

    if not meta_desc:
        results.append(_issue(
            "meta_desc_missing", FAIL, SEV_HIGH,
            "No meta description found",
            "Add a compelling 140-160 character meta description. Include primary keyword and a clear call to action.",
            impact="Without meta description, Google auto-generates one — often poorly. Impacts CTR significantly."
        ))
        return results

    if length < 70:
        results.append(_issue(
            "meta_desc_too_short", WARNING, SEV_MEDIUM,
            f"Meta description too short ({length} chars)",
            "Expand to 140-160 characters. You're wasting valuable SERP real estate.",
            value=length
        ))
    elif length > 160:
        results.append(_issue(
            "meta_desc_too_long", WARNING, SEV_MEDIUM,
            f"Meta description too long ({length} chars) — will be truncated in SERPs",
            "Trim to 140-155 characters. Put the most important information first.",
            value=length
        ))
    else:
        results.append(_issue(
            "meta_desc_length_ok", PASS, SEV_LOW,
            f"Meta description length is good ({length} chars)",
            "", value=length
        ))

    generic_patterns = [
        r"^welcome to", r"^this is", r"^click here",
        r"lorem ipsum", r"^sample", r"^test",
    ]
    for pattern in generic_patterns:
        if re.match(pattern, meta_desc.lower()):
            results.append(_issue(
                "meta_desc_generic", FAIL, SEV_HIGH,
                f"Meta description appears to be generic/placeholder: '{meta_desc[:80]}...'",
                "Write a unique, compelling meta description that accurately summarizes the page content."
            ))
            break

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# HEADING CHECKS
# ═══════════════════════════════════════════════════════════════════════════════

def check_headings(page_data: dict) -> list:
    results = []
    headings = page_data.get("headings", {})
    h1_count = page_data.get("h1_count", 0)
    h1_tags = headings.get("h1", [])
    h2_tags = headings.get("h2", [])

    if h1_count == 0:
        results.append(_issue(
            "h1_missing", FAIL, SEV_HIGH,
            "No H1 tag found on page",
            "Add exactly one H1 tag containing your primary keyword. It signals the page's main topic.",
            impact="H1 is the second most important on-page SEO element after title tag."
        ))
    elif h1_count > 1:
        results.append(_issue(
            "h1_multiple", FAIL, SEV_HIGH,
            f"Multiple H1 tags found ({h1_count}): {h1_tags}",
            "Use exactly one H1 per page. Demote additional H1s to H2 or H3.",
            value=h1_count,
            impact="Multiple H1s confuse Google about page's primary topic."
        ))
    else:
        h1_text = h1_tags[0] if h1_tags else ""
        results.append(_issue(
            "h1_ok", PASS, SEV_LOW,
            f"Single H1 found: '{h1_text[:80]}'",
            "", value=h1_text
        ))
        if len(h1_text) < 5:
            results.append(_issue(
                "h1_too_short", WARNING, SEV_MEDIUM,
                f"H1 is very short: '{h1_text}'",
                "H1 should describe the page topic. Aim for 20-70 characters with primary keyword."
            ))

    if h2_tags:
        results.append(_issue(
            "h2_present", PASS, SEV_LOW,
            f"{len(h2_tags)} H2 heading(s) found",
            "", value=len(h2_tags)
        ))
    else:
        results.append(_issue(
            "h2_missing", WARNING, SEV_MEDIUM,
            "No H2 headings found — page may lack content structure",
            "Add H2 subheadings to organize content. Include secondary keywords naturally.",
        ))

    h3_tags = headings.get("h3", [])
    if h3_tags and not h2_tags:
        results.append(_issue(
            "heading_hierarchy_skip", WARNING, SEV_MEDIUM,
            "H3 tags present but no H2 — broken heading hierarchy",
            "Maintain proper heading hierarchy: H1 → H2 → H3. Don't skip levels.",
        ))

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# URL CHECKS
# ═══════════════════════════════════════════════════════════════════════════════

def check_url(url: str) -> list:
    results = []
    parsed = urlparse(url)
    path = parsed.path

    if parsed.scheme != "https":
        results.append(_issue(
            "url_not_https", FAIL, SEV_CRITICAL,
            f"Page is not served over HTTPS: {url}",
            "Install SSL certificate and redirect all HTTP to HTTPS. Google uses HTTPS as a ranking signal.",
            impact="HTTPS is a confirmed ranking factor. Non-HTTPS sites lose trust and rankings."
        ))
    else:
        results.append(_issue("url_https", PASS, SEV_LOW, "Page served over HTTPS", ""))

    if len(url) > 100:
        results.append(_issue(
            "url_too_long", WARNING, SEV_MEDIUM,
            f"URL is too long ({len(url)} chars)",
            "Keep URLs under 75 characters. Use short, descriptive slugs.",
            value=len(url)
        ))

    if re.search(r'[^a-zA-Z0-9/_\-\.~:%?=&#@!]', path):
        results.append(_issue(
            "url_special_chars", WARNING, SEV_MEDIUM,
            "URL contains special characters that may cause issues",
            "Use only letters, numbers, hyphens, and underscores in URLs."
        ))

    if "_" in path:
        results.append(_issue(
            "url_underscores", WARNING, SEV_LOW,
            f"URL uses underscores instead of hyphens: {path}",
            "Use hyphens (-) not underscores (_) as word separators. Google treats underscores as word joiners.",
        ))

    if re.search(r'[A-Z]', path):
        results.append(_issue(
            "url_uppercase", WARNING, SEV_LOW,
            "URL contains uppercase letters which can cause duplicate content issues",
            "Use lowercase URLs only. Implement 301 redirects from uppercase to lowercase versions."
        ))

    if parsed.query:
        results.append(_issue(
            "url_has_params", WARNING, SEV_LOW,
            f"URL contains query parameters: ?{parsed.query}",
            "Consider using clean URL structure without parameters for better SEO. Use canonical tags if parameters can't be removed.",
        ))

    depth = len([p for p in path.split("/") if p])
    if depth > 4:
        results.append(_issue(
            "url_too_deep", WARNING, SEV_MEDIUM,
            f"URL is {depth} levels deep — reduces crawl priority",
            "Keep important pages within 3 clicks (folder levels) of the homepage.",
            value=depth
        ))

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# CANONICAL CHECKS
# ═══════════════════════════════════════════════════════════════════════════════

def check_canonical(page_data: dict, current_url: str) -> list:
    results = []
    canonical = page_data.get("canonical_url")

    if not canonical:
        results.append(_issue(
            "canonical_missing", WARNING, SEV_MEDIUM,
            "No canonical tag found",
            "Add a self-referencing canonical tag to prevent duplicate content issues: "
            "<link rel='canonical' href='[current-url]' />",
        ))
        return results

    # Normalize both URLs before comparing — trailing slash, www, scheme
    canonical_norm = _normalize_url(canonical)
    current_norm = _normalize_url(current_url)

    if canonical_norm != current_norm:
        results.append(_issue(
            "canonical_different", WARNING, SEV_HIGH,
            f"Canonical points to different URL: {canonical}",
            "Verify this is intentional. If this is a duplicate page, the canonical should point to "
            "the preferred version. If this is the preferred version, update canonical to self-reference.",
            value=canonical,
            impact="Wrong canonical = Google ignores this page and passes signals to canonical URL."
        ))
    else:
        results.append(_issue(
            "canonical_ok", PASS, SEV_LOW,
            "Canonical tag is correctly self-referencing",
            "", value=canonical
        ))

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# ROBOTS / INDEXABILITY CHECKS
# ═══════════════════════════════════════════════════════════════════════════════

def check_robots(page_data: dict, robots_txt_data: dict) -> list:
    results = []
    meta_robots = page_data.get("meta_robots", "")

    if meta_robots:
        directives = [d.strip().lower() for d in meta_robots.split(",")]

        if "noindex" in directives:
            results.append(_issue(
                "meta_robots_noindex", FAIL, SEV_CRITICAL,
                f"Page has noindex directive: meta robots='{meta_robots}'",
                "Remove noindex if you want this page indexed. This is the most common cause of pages disappearing from Google.",
                impact="CRITICAL: Page will be removed from Google index within days of next crawl."
            ))

        if "nofollow" in directives:
            results.append(_issue(
                "meta_robots_nofollow", WARNING, SEV_MEDIUM,
                "Page has nofollow directive — link equity not passed to linked pages",
                "Only use nofollow on pages you don't want Google to follow links on. Unnecessary nofollow wastes link equity."
            ))

        if "none" in directives:
            results.append(_issue(
                "meta_robots_none", FAIL, SEV_CRITICAL,
                "Meta robots='none' — page is both noindex and nofollow",
                "Remove unless this page should absolutely not appear in search results.",
                impact="Page will be deindexed and no link equity will flow through it."
            ))
    else:
        results.append(_issue(
            "meta_robots_missing", PASS, SEV_LOW,
            "No meta robots restrictions found (defaults to index, follow)",
            ""
        ))

    if robots_txt_data.get("found"):
        if robots_txt_data.get("disallow_all"):
            results.append(_issue(
                "robots_txt_disallow_all", FAIL, SEV_CRITICAL,
                "robots.txt has 'Disallow: /' — entire site is blocked from crawling",
                "URGENT: Fix robots.txt immediately. Google cannot crawl any page on this site.",
                impact="CRITICAL: No new pages will be indexed. Existing indexed pages may be dropped."
            ))
        else:
            results.append(_issue(
                "robots_txt_ok", PASS, SEV_LOW,
                "robots.txt found and does not block entire site",
                ""
            ))
        if robots_txt_data.get("sitemap_urls"):
            results.append(_issue(
                "robots_txt_has_sitemap", PASS, SEV_LOW,
                f"Sitemap referenced in robots.txt: {robots_txt_data['sitemap_urls'][0]}",
                ""
            ))
    else:
        results.append(_issue(
            "robots_txt_missing", WARNING, SEV_MEDIUM,
            "robots.txt file not found",
            "Create a robots.txt file. While not required, it helps guide search engine crawlers.",
        ))

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# IMAGE CHECKS
# ═══════════════════════════════════════════════════════════════════════════════

def check_images(page_data: dict) -> list:
    results = []
    images = page_data.get("images", [])
    missing_alt = page_data.get("images_without_alt", [])
    empty_alt = page_data.get("images_empty_alt", [])

    if not images:
        results.append(_issue(
            "no_images", WARNING, SEV_LOW,
            "No images found on page",
            "Add relevant images with descriptive alt text to improve engagement and image search visibility."
        ))
        return results

    total = len(images)
    missing_count = len(missing_alt)
    empty_count = len(empty_alt)

    if missing_count == 0 and empty_count == 0:
        results.append(_issue(
            "images_alt_ok", PASS, SEV_LOW,
            f"All {total} images have alt text",
            "", value=total
        ))
    else:
        if missing_count > 0:
            pct = round((missing_count / total) * 100)
            severity = SEV_HIGH if pct > 50 else SEV_MEDIUM
            results.append(_issue(
                "images_missing_alt", FAIL if pct > 50 else WARNING, severity,
                f"{missing_count} of {total} images ({pct}%) are missing alt attributes",
                "Add descriptive alt text to all images. Include relevant keywords naturally. "
                "Alt text is also critical for accessibility.",
                value=missing_count,
                impact="Missing alt text = missed image search rankings + accessibility violations."
            ))

        if empty_count > 0:
            results.append(_issue(
                "images_empty_alt", WARNING, SEV_LOW,
                f"{empty_count} images have empty alt attributes (alt='')",
                "Empty alt is correct for purely decorative images. If images are informational, add descriptive alt text.",
                value=empty_count
            ))

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# STRUCTURED DATA / SCHEMA CHECKS
# ═══════════════════════════════════════════════════════════════════════════════

def check_schema(page_data: dict) -> list:
    results = []
    schema_scripts = page_data.get("schema_scripts", [])

    if not schema_scripts:
        results.append(_issue(
            "schema_missing", WARNING, SEV_MEDIUM,
            "No structured data (Schema.org / JSON-LD) found",
            "Implement relevant schema markup (Article, Product, LocalBusiness, FAQ, BreadcrumbList). "
            "Schema can earn rich results in SERPs.",
            impact="No schema = no rich snippets. Competitors with schema get more SERP real estate."
        ))
        return results

    schema_types = []
    for schema in schema_scripts:
        if isinstance(schema, dict):
            schema_type = schema.get("@type", schema.get("type", "Unknown"))
            schema_types.append(schema_type)
        elif isinstance(schema, list):
            for item in schema:
                if isinstance(item, dict):
                    schema_types.append(item.get("@type", "Unknown"))

    results.append(_issue(
        "schema_found", PASS, SEV_LOW,
        f"Structured data found: {', '.join(str(t) for t in schema_types)}",
        "", value=schema_types
    ))

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# MOBILE CHECKS
# ═══════════════════════════════════════════════════════════════════════════════

def check_mobile(page_data: dict) -> list:
    results = []
    viewport = page_data.get("meta_viewport")

    if not viewport:
        results.append(_issue(
            "viewport_missing", FAIL, SEV_CRITICAL,
            "No viewport meta tag found — page is not mobile-optimized",
            "Add: <meta name='viewport' content='width=device-width, initial-scale=1.0'>",
            impact="CRITICAL: Google uses mobile-first indexing. Non-mobile-friendly pages rank significantly lower."
        ))
    elif "width=device-width" in viewport:
        results.append(_issue(
            "viewport_ok", PASS, SEV_LOW,
            f"Viewport meta tag present: {viewport}",
            "", value=viewport
        ))
    else:
        results.append(_issue(
            "viewport_invalid", WARNING, SEV_HIGH,
            f"Viewport tag may not be correctly configured: {viewport}",
            "Use: content='width=device-width, initial-scale=1.0'",
            value=viewport
        ))

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# LINK CHECKS
# ═══════════════════════════════════════════════════════════════════════════════

def check_links(page_data: dict) -> list:
    results = []
    internal = page_data.get("internal_links", [])
    external = page_data.get("external_links", [])
    word_count = page_data.get("word_count", 0)

    internal_count = len(internal)
    external_count = len(external)

    if internal_count == 0:
        results.append(_issue(
            "no_internal_links", FAIL, SEV_HIGH,
            "No internal links found — page is isolated",
            "Add 3-5 internal links to related pages. Internal linking distributes PageRank and helps users navigate.",
            impact="Isolated pages receive no internal link equity and may be poorly crawled."
        ))
    elif internal_count > 100:
        results.append(_issue(
            "too_many_internal_links", WARNING, SEV_MEDIUM,
            f"Very high number of internal links: {internal_count}",
            "Excessive internal links dilute link equity. Aim for 3-15 contextual internal links per page.",
            value=internal_count
        ))
    else:
        results.append(_issue(
            "internal_links_ok", PASS, SEV_LOW,
            f"{internal_count} internal link(s) found",
            "", value=internal_count
        ))

    if external_count > 20:
        results.append(_issue(
            "too_many_external_links", WARNING, SEV_MEDIUM,
            f"High number of external links: {external_count}",
            "Excessive external linking can leak PageRank. Review and nofollow links to untrusted/commercial sites.",
            value=external_count
        ))

    if word_count > 0 and internal_count > 0:
        link_density = (internal_count / (word_count / 100))
        if link_density > 15:
            results.append(_issue(
                "link_density_high", WARNING, SEV_MEDIUM,
                f"High internal link density: {internal_count} links in {word_count} words",
                "Reduce internal links or expand content. Too many links per word looks spammy.",
                value=round(link_density, 1)
            ))

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# OPEN GRAPH / SOCIAL CHECKS
# ═══════════════════════════════════════════════════════════════════════════════

def check_social_tags(page_data: dict) -> list:
    results = []
    og_tags = page_data.get("og_tags", {})

    required_og = ["og:title", "og:description", "og:image", "og:url"]
    missing_og = [t for t in required_og if t not in og_tags]

    if missing_og:
        results.append(_issue(
            "og_tags_missing", WARNING, SEV_LOW,
            f"Missing Open Graph tags: {', '.join(missing_og)}",
            "Add Open Graph tags for better social media sharing. Missing og:image means no image preview when shared.",
            value=missing_og
        ))
    else:
        results.append(_issue(
            "og_tags_ok", PASS, SEV_LOW,
            "Required Open Graph tags present",
            ""
        ))

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# REDIRECT CHECKS
# ═══════════════════════════════════════════════════════════════════════════════

def check_redirects(page_data: dict, original_url: str) -> list:
    results = []
    redirect_chain = page_data.get("redirect_chain", [])
    final_url = page_data.get("final_url", original_url)

    if not redirect_chain:
        results.append(_issue(
            "redirects_none", PASS, SEV_LOW,
            "No redirects detected",
            ""
        ))
        return results

    redirect_count = len(redirect_chain)

    if redirect_count == 1:
        r = redirect_chain[0]
        if r["status_code"] in [301, 308]:
            results.append(_issue(
                "redirect_301", PASS, SEV_LOW,
                f"Single 301 redirect to: {final_url}",
                "301 redirects are fine. Ensure target URL is the canonical version.",
                value=final_url
            ))
        elif r["status_code"] in [302, 307]:
            results.append(_issue(
                "redirect_302", WARNING, SEV_MEDIUM,
                f"Temporary 302 redirect detected to: {final_url}",
                "Use 301 (permanent) redirects unless the redirect is genuinely temporary. "
                "302 doesn't pass full link equity.",
                value=r["status_code"],
                impact="302 redirects pass ~85% of link equity vs 99% for 301."
            ))

    elif redirect_count >= 3:
        results.append(_issue(
            "redirect_chain", FAIL, SEV_HIGH,
            f"Redirect chain detected: {redirect_count} redirects",
            "Fix redirect chains. Each hop loses link equity and slows page load. Point directly to final URL.",
            value=redirect_count,
            impact="Each redirect adds ~100-500ms latency. Chains kill page speed and leak link equity."
        ))

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# SITEMAP CHECK
# ═══════════════════════════════════════════════════════════════════════════════

def check_sitemap(sitemap_data: dict) -> list:
    results = []

    if sitemap_data.get("found"):
        results.append(_issue(
            "sitemap_found", PASS, SEV_LOW,
            f"XML sitemap found at: {sitemap_data['url']} ({sitemap_data['url_count']} URLs)",
            "", value=sitemap_data.get("url_count")
        ))
    else:
        results.append(_issue(
            "sitemap_missing", WARNING, SEV_MEDIUM,
            "No XML sitemap found",
            "Create and submit an XML sitemap to Google Search Console. "
            "Helps Google discover and index all pages.",
        ))

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# HREFLANG CHECK
# ═══════════════════════════════════════════════════════════════════════════════

def check_hreflang(page_data: dict) -> list:
    results = []
    hreflang = page_data.get("hreflang_tags", [])

    if hreflang:
        has_self_ref = any(tag.get("hreflang") == "x-default" for tag in hreflang)
        results.append(_issue(
            "hreflang_found", PASS, SEV_LOW,
            f"{len(hreflang)} hreflang tag(s) found",
            "" if has_self_ref else "Ensure hreflang includes x-default tag for default language.",
            value=len(hreflang)
        ))

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ANALYZER ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_technical(page_data: dict, url: str,
                       robots_txt_data: dict = None,
                       sitemap_data: dict = None) -> dict:
    """
    Run all technical SEO checks and return structured results.
    """
    robots_txt_data = robots_txt_data or {"found": False}
    sitemap_data = sitemap_data or {"found": False}

    all_checks = []

    all_checks.extend(check_title(page_data))
    all_checks.extend(check_meta_description(page_data))
    all_checks.extend(check_headings(page_data))
    all_checks.extend(check_url(url))
    all_checks.extend(check_canonical(page_data, url))
    all_checks.extend(check_robots(page_data, robots_txt_data))
    all_checks.extend(check_images(page_data))
    all_checks.extend(check_schema(page_data))
    all_checks.extend(check_mobile(page_data))
    all_checks.extend(check_links(page_data))
    all_checks.extend(check_social_tags(page_data))
    all_checks.extend(check_redirects(page_data, url))
    all_checks.extend(check_sitemap(sitemap_data))
    all_checks.extend(check_hreflang(page_data))

    critical = sum(1 for c in all_checks if c["status"] in [FAIL, WARNING] and c["severity"] == SEV_CRITICAL)
    high = sum(1 for c in all_checks if c["status"] in [FAIL, WARNING] and c["severity"] == SEV_HIGH)
    medium = sum(1 for c in all_checks if c["status"] in [FAIL, WARNING] and c["severity"] == SEV_MEDIUM)
    low = sum(1 for c in all_checks if c["status"] in [FAIL, WARNING] and c["severity"] == SEV_LOW)
    passes = sum(1 for c in all_checks if c["status"] == PASS)
    total = len(all_checks)

    deductions = (critical * 20) + (high * 10) + (medium * 5) + (low * 2)
    score = max(0, min(100, 100 - deductions))

    return {
        "checks": all_checks,
        "score": score,
        "issues_critical": critical,
        "issues_high": high,
        "issues_medium": medium,
        "issues_low": low,
        "passes": passes,
        "total_checks": total,
    }