"""
Black Hat SEO Detector
Implements all 10 detection checks from the Black Hat Detection Matrix.
Returns a risk score (0-100) and detailed findings per check.

Risk Score Scale:
  0-15:  LOW RISK - Clean practices
 16-35:  MODERATE RISK - Some issues to fix
 36-60:  HIGH RISK - Multiple violations
 61-100: CRITICAL - Severe penalty likely
"""

import re
import logging
from typing import Optional
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# ── Status constants ───────────────────────────────────────────────────────────
CLEAN = "clean"
WARNING = "warning"
DETECTED = "detected"

SEV_LOW = "low"
SEV_MEDIUM = "medium"
SEV_HIGH = "high"
SEV_CRITICAL = "critical"

# ── Risk score weights (from Detection Matrix) ─────────────────────────────────
RISK_WEIGHTS = {
    "cloaking": 40,
    "mobile_cloaking": 20,
    "hidden_text": 35,
    "keyword_stuffing": 25,
    "over_optimization": 20,
    "sneaky_redirects": 30,
    "doorway_pages": 30,
    "unnatural_links": 20,
    "unmarked_paid_links": 10,
    "intrusive_interstitials": 15,
}


def _finding(check_id: str, status: str, severity: str, title: str,
             message: str, evidence: list = None, fix: str = "",
             risk_points: int = 0) -> dict:
    return {
        "check_id": check_id,
        "status": status,
        "severity": severity,
        "title": title,
        "message": message,
        "evidence": evidence or [],
        "fix": fix,
        "risk_points": risk_points if status != CLEAN else 0,
    }


def _text_similarity(text_a: str, text_b: str) -> float:
    """Calculate text similarity ratio between two strings."""
    if not text_a or not text_b:
        return 0.0
    a = text_a[:2000].lower()
    b = text_b[:2000].lower()
    return SequenceMatcher(None, a, b).ratio()


# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 1: KEYWORD STUFFING
# ═══════════════════════════════════════════════════════════════════════════════

def detect_keyword_stuffing(page_data: dict, target_keyword: str = None) -> dict:
    """
    Detects keyword stuffing patterns.
    Uses target_keyword if provided (user-supplied), otherwise falls back to
    auto-detected top word.
    """
    body_text = page_data.get("body_text", "")
    headings = page_data.get("headings", {})
    h1s = headings.get("h1", [])
    h2s = headings.get("h2", [])
    word_count = page_data.get("word_count", 0)

    if not body_text or word_count < 50:
        return _finding("keyword_stuffing", CLEAN, SEV_LOW, "Keyword Stuffing",
                        "Not enough content to analyze.", risk_points=0)

    words = re.findall(r'\b[a-z]{4,}\b', body_text.lower())
    stop_words = {"that", "this", "with", "from", "have", "they", "been", "were", "will",
                  "your", "what", "when", "which", "their", "there", "about", "would",
                  "more", "also", "into", "over", "each", "then", "than"}
    words = [w for w in words if w not in stop_words]

    from collections import Counter
    word_freq = Counter(words)

    if not word_freq:
        return _finding("keyword_stuffing", CLEAN, SEV_LOW, "Keyword Stuffing",
                        "No significant word patterns detected.", risk_points=0)

    # ── Use user-supplied keyword if provided ──────────────────────────────────
    if target_keyword:
        top_word = target_keyword.lower().strip()
        kw_words = top_word.split()
        if len(kw_words) > 1:
            # Multi-word phrase: count phrase occurrences
            body_lower = body_text.lower()
            top_count = len(re.findall(re.escape(top_word), body_lower))
        else:
            top_count = word_freq.get(top_word, 0)

        if top_count == 0:
            return _finding(
                "keyword_stuffing", CLEAN, SEV_LOW,
                "Keyword Stuffing",
                f"Target keyword '{target_keyword}' not found in body text — no stuffing possible.",
                risk_points=0
            )
    else:
        top_word, top_count = word_freq.most_common(1)[0]

    density = round((top_count / word_count) * 100, 2)

    evidence = []
    risk_addition = 0

    # Density check
    if density > 4.0:
        evidence.append(
            f"Keyword '{top_word}' density: {density}% ({top_count} occurrences in {word_count} words) "
            f"— SAFE RANGE: 0.5-2%"
        )
        risk_addition = RISK_WEIGHTS["keyword_stuffing"]
    elif density > 3.0:
        evidence.append(f"Elevated keyword density: '{top_word}' at {density}%")
        risk_addition = 15

    # Heading keyword concentration
    h2_with_keyword = [h for h in h2s if top_word in h.lower()]
    if len(h2s) >= 3 and len(h2_with_keyword) == len(h2s):
        evidence.append(
            f"Keyword '{top_word}' appears in ALL {len(h2s)} H2 headings — unnatural pattern"
        )
        risk_addition = max(risk_addition, 15)

    # Consecutive repetition detection
    words_list = body_text.lower().split()
    max_streak = 0
    streak = 0
    for word in words_list:
        if top_word in word:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0

    if max_streak >= 3:
        evidence.append(
            f"'{top_word}' appears {max_streak} times consecutively — textbook stuffing pattern"
        )
        risk_addition = max(risk_addition, RISK_WEIGHTS["keyword_stuffing"])

    if not evidence:
        return _finding(
            "keyword_stuffing", CLEAN, SEV_LOW,
            "Keyword Stuffing",
            f"No keyword stuffing detected. '{top_word}' is at healthy {density}% density.",
            risk_points=0
        )

    severity = SEV_CRITICAL if risk_addition >= 25 else SEV_HIGH
    return _finding(
        "keyword_stuffing", DETECTED, severity,
        "Keyword Stuffing Detected",
        f"Unnatural keyword repetition detected for '{top_word}'",
        evidence=evidence,
        fix="1. Reduce keyword usage to 0.5-2% density\n2. Use semantic variations and LSI keywords\n"
            "3. Rewrite heading text to be topically varied\n4. Remove consecutive keyword repetitions",
        risk_points=risk_addition
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 2: HIDDEN TEXT & LINKS
# ═══════════════════════════════════════════════════════════════════════════════

def detect_hidden_text(page_data: dict) -> dict:
    """
    Detects text/links hidden via CSS techniques.
    """
    inline_styles = page_data.get("inline_styles", [])
    raw_html = page_data.get("raw_html", "")
    soup = page_data.get("soup")

    evidence = []
    risk_addition = 0

    hidden_css_patterns = [
        (r'font-size\s*:\s*0(px)?', "font-size: 0"),
        (r'font-size\s*:\s*1px', "font-size: 1px"),
        (r'text-indent\s*:\s*-\d{3,}px', "text-indent: -999px (off-screen)"),
        (r'position\s*:\s*absolute[^;]*left\s*:\s*-\d{3,}px', "position absolute off-screen"),
        (r'opacity\s*:\s*0[^\.1-9]', "opacity: 0"),
        (r'visibility\s*:\s*hidden', "visibility: hidden"),
        (r'overflow\s*:\s*hidden[^;]*width\s*:\s*0', "zero-width overflow hidden"),
        (r'width\s*:\s*0[^;]*height\s*:\s*0', "zero dimensions"),
    ]

    for element in inline_styles:
        style = element.get("style", "")
        text = element.get("text", "")
        if not style or not text:
            continue

        for pattern, description in hidden_css_patterns:
            if re.search(pattern, style, re.I):
                evidence.append(
                    f"Hidden content via '{description}': '{text[:80]}'" if len(text) <= 80
                    else f"Hidden content via '{description}': '{text[:80]}...'"
                )
                risk_addition = RISK_WEIGHTS["hidden_text"]
                break

    # White text on white background
    white_on_white_pattern = (
        r'color\s*:\s*(#fff(fff)?|white|rgb\(255,\s*255,\s*255\))'
        r'[^}]*background(-color)?\s*:\s*(#fff(fff)?|white|rgb\(255,\s*255,\s*255\))'
    )
    if re.search(white_on_white_pattern, raw_html, re.I):
        evidence.append("Possible white-on-white text detected (same color as background)")
        risk_addition = RISK_WEIGHTS["hidden_text"]

    # Links in noscript tags
    if soup:
        noscript_links = []
        for noscript in soup.find_all("noscript"):
            links = noscript.find_all("a", href=True)
            if links:
                noscript_links.extend([a.get("href", "") for a in links])

        if noscript_links:
            evidence.append(f"Links hidden in <noscript> tags: {noscript_links[:3]}")
            risk_addition = RISK_WEIGHTS["hidden_text"]

    # display:none with link content
    if soup:
        for tag in soup.find_all(style=re.compile(r'display\s*:\s*none', re.I)):
            links = tag.find_all("a", href=True)
            if links:
                link_texts = [a.get_text(strip=True) for a in links[:3]]
                evidence.append(f"Links inside display:none element: {link_texts}")
                risk_addition = RISK_WEIGHTS["hidden_text"]
                break

    if not evidence:
        return _finding(
            "hidden_text", CLEAN, SEV_LOW,
            "Hidden Text & Links",
            "No hidden text or link patterns detected.",
            risk_points=0
        )

    return _finding(
        "hidden_text", DETECTED, SEV_CRITICAL,
        "Hidden Text/Links Detected",
        "Content is hidden from users but visible to search engine crawlers",
        evidence=evidence,
        fix="1. Remove ALL hidden text and links immediately\n2. Ensure all content is visible to users\n"
            "3. If content isn't worth showing users, delete it\n"
            "4. Request Google recrawl after cleanup\n"
            "5. Submit reconsideration request if manual action exists",
        risk_points=risk_addition
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 3: CLOAKING (User-Agent based)
# ═══════════════════════════════════════════════════════════════════════════════

def detect_cloaking(cloaking_data: dict) -> dict:
    desktop = cloaking_data.get("desktop", {})
    googlebot = cloaking_data.get("googlebot", {})

    if not desktop.get("success") or not googlebot.get("success"):
        return _finding(
            "cloaking", WARNING, SEV_LOW,
            "Cloaking Detection",
            "Could not complete cloaking check — one or more requests failed.",
            risk_points=0
        )

    desktop_text = desktop.get("body_text", "")
    googlebot_text = googlebot.get("body_text", "")
    similarity = _text_similarity(desktop_text, googlebot_text)
    evidence = []

    desktop_final = desktop.get("final_url", "")
    googlebot_final = googlebot.get("final_url", "")

    if desktop_final != googlebot_final:
        evidence.append(
            f"Different final URLs: Desktop→{desktop_final} | Googlebot→{googlebot_final}"
        )

    if similarity < 0.80:
        diff_pct = round((1 - similarity) * 100, 1)
        evidence.append(
            f"Content divergence: {diff_pct}% difference between desktop and Googlebot responses"
        )
        desktop_wc = desktop.get("word_count", 0)
        googlebot_wc = googlebot.get("word_count", 0)
        if abs(desktop_wc - googlebot_wc) > 100:
            evidence.append(
                f"Word count mismatch: Desktop={desktop_wc} words | Googlebot={googlebot_wc} words"
            )

    if not evidence:
        return _finding(
            "cloaking", CLEAN, SEV_LOW,
            "Cloaking (User-Agent)",
            f"No cloaking detected. Desktop and Googlebot similarity: {round(similarity * 100, 1)}%",
            risk_points=0
        )

    severity = SEV_CRITICAL if similarity < 0.60 else SEV_HIGH
    return _finding(
        "cloaking", DETECTED, severity,
        "Cloaking Detected",
        f"Different content served to Googlebot vs regular users (similarity: {round(similarity * 100, 1)}%)",
        evidence=evidence,
        fix="1. Ensure identical content for all user agents\n2. Remove user-agent based content switching\n"
            "3. Do not serve bot-specific content\n4. If using CDN, verify no agent-based rules\n"
            "5. Submit reconsideration request after cleanup",
        risk_points=RISK_WEIGHTS["cloaking"]
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 4: MOBILE CLOAKING
# ═══════════════════════════════════════════════════════════════════════════════

def detect_mobile_cloaking(cloaking_data: dict) -> dict:
    desktop = cloaking_data.get("desktop", {})
    mobile = cloaking_data.get("mobile", {})

    if not desktop.get("success") or not mobile.get("success"):
        return _finding(
            "mobile_cloaking", WARNING, SEV_LOW,
            "Mobile Cloaking",
            "Could not complete mobile cloaking check — mobile request failed.",
            risk_points=0
        )

    desktop_text = desktop.get("body_text", "")
    mobile_text = mobile.get("body_text", "")
    similarity = _text_similarity(desktop_text, mobile_text)
    evidence = []

    desktop_final = desktop.get("final_url", "")
    mobile_final = mobile.get("final_url", "")

    from urllib.parse import urlparse
    desktop_domain = urlparse(desktop_final).netloc
    mobile_domain = urlparse(mobile_final).netloc

    if desktop_domain != mobile_domain:
        evidence.append(
            f"Mobile redirected to different domain: {mobile_domain} (desktop: {desktop_domain})"
        )

    if similarity < 0.80:
        diff_pct = round((1 - similarity) * 100, 1)
        evidence.append(f"Mobile content {diff_pct}% different from desktop")
        desktop_wc = desktop.get("word_count", 0)
        mobile_wc = mobile.get("word_count", 0)
        if desktop_wc > 0 and mobile_wc < desktop_wc * 0.7:
            evidence.append(
                f"Mobile content significantly thinner: {mobile_wc} words vs {desktop_wc} desktop words"
            )

    mobile_modals = mobile.get("modal_divs_count", 0)
    mobile_popups = mobile.get("popup_indicators", [])
    if mobile_modals > 0 or mobile_popups:
        evidence.append(
            f"Mobile interstitials detected: {mobile_modals} modal(s), popup patterns: {mobile_popups}"
        )

    if not evidence:
        return _finding(
            "mobile_cloaking", CLEAN, SEV_LOW,
            "Mobile Cloaking",
            f"No mobile cloaking detected. Mobile/desktop similarity: {round(similarity * 100, 1)}%",
            risk_points=0
        )

    severity = SEV_CRITICAL if desktop_domain != mobile_domain else SEV_HIGH
    risk = RISK_WEIGHTS["mobile_cloaking"] if desktop_domain != mobile_domain else 10

    return _finding(
        "mobile_cloaking", DETECTED, severity,
        "Mobile Cloaking Detected",
        "Different content/experience served to mobile users vs desktop",
        evidence=evidence,
        fix="1. Use responsive design — same HTML for all devices\n"
            "2. If using m.subdomain, implement proper mobile config with rel=alternate\n"
            "3. Ensure mobile content is not thinner than desktop\n"
            "4. Remove intrusive mobile popups\n"
            "5. Verify mobile URLs serve same core content",
        risk_points=risk
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 5: SNEAKY REDIRECTS
# ═══════════════════════════════════════════════════════════════════════════════

def detect_sneaky_redirects(page_data: dict) -> dict:
    raw_html = page_data.get("raw_html", "")
    soup = page_data.get("soup")
    js_redirect_detected = page_data.get("js_redirect_detected", False)
    redirect_chain = page_data.get("redirect_chain", [])

    evidence = []
    risk_addition = 0

    sneaky_js_patterns = [
        (r'setTimeout\s*\([^)]*window\.location', "setTimeout + window.location redirect"),
        (r'setTimeout\s*\([^)]*document\.location', "setTimeout + document.location redirect"),
        (r'setTimeout\s*\([^)]*location\.href', "setTimeout + location.href redirect"),
        (r'setTimeout\s*\([^)]*location\.replace', "setTimeout + location.replace redirect"),
    ]

    for pattern, description in sneaky_js_patterns:
        if re.search(pattern, raw_html, re.I | re.S):
            evidence.append(f"Automatic JavaScript redirect detected: {description}")
            risk_addition = RISK_WEIGHTS["sneaky_redirects"]

    if js_redirect_detected and not any(e.startswith("Automatic JavaScript") for e in evidence):
        evidence.append("Playwright detected automatic JavaScript-based redirect on page load")
        risk_addition = RISK_WEIGHTS["sneaky_redirects"]

    if soup:
        meta_refresh = soup.find("meta", attrs={"http-equiv": re.compile(r"refresh", re.I)})
        if meta_refresh:
            content = meta_refresh.get("content", "")
            delay_match = re.search(r'(\d+)\s*;?\s*url=', content, re.I)
            if delay_match:
                delay = int(delay_match.group(1))
                if delay < 5:
                    evidence.append(f"Meta refresh redirect with {delay}s delay — too fast for user to read")
                    risk_addition = RISK_WEIGHTS["sneaky_redirects"]
                elif delay < 10:
                    evidence.append(f"Meta refresh redirect with {delay}s delay — borderline sneaky")
                    risk_addition = 10

    if len(redirect_chain) >= 3:
        evidence.append(f"Redirect chain of {len(redirect_chain)} hops detected")
        risk_addition = max(risk_addition, 15)

    if not evidence:
        return _finding(
            "sneaky_redirects", CLEAN, SEV_LOW,
            "Sneaky Redirects",
            "No automatic or sneaky redirects detected.",
            risk_points=0
        )

    return _finding(
        "sneaky_redirects", DETECTED, SEV_CRITICAL,
        "Sneaky Redirect Detected",
        "Page automatically redirects users without interaction",
        evidence=evidence,
        fix="1. Remove all automatic JavaScript redirects (setTimeout + window.location)\n"
            "2. Remove auto-refresh meta tags\n"
            "3. If redirect is needed, use server-side 301 (permanent) or 302 (temporary)\n"
            "4. Never redirect to a different page than what was originally clicked",
        risk_points=risk_addition
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 6: DOORWAY PAGES
# ═══════════════════════════════════════════════════════════════════════════════

def detect_doorway_pages(page_data: dict) -> dict:
    word_count = page_data.get("word_count", 0)
    title = (page_data.get("title") or "").lower()
    headings = page_data.get("headings", {})
    h1s = headings.get("h1", [])
    redirect_chain = page_data.get("redirect_chain", [])
    internal_links = page_data.get("internal_links", [])
    external_links = page_data.get("external_links", [])

    evidence = []
    risk_addition = 0

    if word_count < 300:
        evidence.append(f"Very thin content: {word_count} words (doorway threshold: <300)")
        risk_addition = 15

    if word_count < 300 and redirect_chain:
        evidence.append(f"Thin page ({word_count} words) with redirect — classic doorway pattern")
        risk_addition = RISK_WEIGHTS["doorway_pages"]

    location_pattern = r'(in|near|for)\s+[A-Z][a-z]+,?\s*[A-Z]{2}\b'
    h1_text = " ".join(h1s).lower()

    if re.search(location_pattern, title) and re.search(location_pattern, h1_text):
        if word_count < 500:
            evidence.append("Location-keyword doorway pattern: location in both title and H1 with thin content")
            risk_addition = max(risk_addition, RISK_WEIGHTS["doorway_pages"])

    total_links = len(internal_links) + len(external_links)
    if word_count < 300 and total_links <= 2 and total_links > 0:
        evidence.append(
            f"Minimal content ({word_count} words) with only {total_links} link(s) — possible funnel page"
        )
        risk_addition = max(risk_addition, 15)

    if not evidence:
        return _finding(
            "doorway_pages", CLEAN, SEV_LOW,
            "Doorway Pages",
            "No doorway page patterns detected.",
            risk_points=0
        )

    severity = SEV_CRITICAL if risk_addition >= 30 else SEV_HIGH
    return _finding(
        "doorway_pages", DETECTED if risk_addition >= 20 else WARNING, severity,
        "Doorway Page Pattern Detected",
        "Page shows characteristics of a doorway page",
        evidence=evidence,
        fix="1. Add substantial unique content (800+ words) to this page\n"
            "2. Remove redirect if it exists\n"
            "3. Ensure page provides genuine value beyond just ranking for keyword\n"
            "4. If page is truly thin, consolidate with a related page\n"
            "5. Target location pages need unique, locally relevant content",
        risk_points=risk_addition
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 7: OVER-OPTIMIZATION
# ═══════════════════════════════════════════════════════════════════════════════

def detect_over_optimization(page_data: dict, target_keyword: str = None) -> dict:
    from collections import Counter

    body_text = page_data.get("body_text", "")
    title = (page_data.get("title") or "").lower()
    meta = (page_data.get("meta_description") or "").lower()
    headings = page_data.get("headings", {})
    h1s = headings.get("h1", [])
    h2s = headings.get("h2", [])
    internal_links = page_data.get("internal_links", [])

    words = re.findall(r'\b[a-z]{4,}\b', body_text.lower())
    stop_words = {"that", "this", "with", "from", "have", "they", "been", "were", "will",
                  "your", "what", "when", "which", "their", "there", "about", "would"}
    filtered = [w for w in words if w not in stop_words]

    if not filtered:
        return _finding("over_optimization", CLEAN, SEV_LOW,
                        "Over-Optimization", "Not enough content to analyze.", risk_points=0)

    # Use target keyword if provided, otherwise auto-detect
    if target_keyword:
        keyword = target_keyword.lower().strip()
    else:
        keyword = Counter(filtered).most_common(1)[0][0]

    locations_checked = [
        ("title", keyword in title),
        ("meta description", keyword in meta),
        ("H1", any(keyword in h.lower() for h in h1s)),
        ("URL", False),
        ("first 100 words", keyword in " ".join(body_text.split()[:100]).lower()),
        ("H2s", any(keyword in h.lower() for h in h2s)),
        ("image alt", any(keyword in (img.get("alt") or "").lower() for img in page_data.get("images", []))),
        ("internal link anchor", any(keyword in link.get("anchor_text", "").lower() for link in internal_links)),
    ]

    hits = [name for name, found in locations_checked if found]
    locations_with_keyword = len(hits)

    evidence = []
    risk_addition = 0

    if locations_with_keyword >= 7:
        evidence.append(
            f"Keyword '{keyword}' found in {locations_with_keyword}/8 key SEO locations: {', '.join(hits)}"
        )
        evidence.append("Unnatural keyword placement pattern — looks manipulative to Google's algorithms")
        risk_addition = RISK_WEIGHTS["over_optimization"]
    elif locations_with_keyword >= 6:
        evidence.append(
            f"Keyword '{keyword}' found in {locations_with_keyword}/8 key locations — borderline over-optimization"
        )
        risk_addition = 10

    if len(h2s) >= 3:
        h2s_with_kw = [h for h in h2s if keyword in h.lower()]
        if len(h2s_with_kw) == len(h2s):
            evidence.append(f"Keyword '{keyword}' present in all {len(h2s)} H2 headings — unnatural pattern")
            risk_addition = max(risk_addition, 15)

    if len(internal_links) >= 3:
        anchor_texts = [link.get("anchor_text", "").lower().strip() for link in internal_links]
        if len(set(anchor_texts)) == 1:
            evidence.append(
                f"All {len(internal_links)} internal links use identical anchor text: '{anchor_texts[0]}'"
            )
            risk_addition = max(risk_addition, 15)

    if not evidence:
        return _finding(
            "over_optimization", CLEAN, SEV_LOW,
            "Over-Optimization",
            f"No over-optimization detected. Keyword '{keyword}' appears in {locations_with_keyword}/8 locations.",
            risk_points=0
        )

    severity = SEV_HIGH if risk_addition >= 20 else SEV_MEDIUM
    return _finding(
        "over_optimization", DETECTED, severity,
        "Over-Optimization Detected",
        "Keyword placement appears formulaic and unnatural",
        evidence=evidence,
        fix="1. Remove keyword from some heading tags — use topical variations\n"
            "2. Diversify image alt text with descriptive phrases, not just the keyword\n"
            "3. Vary internal link anchor text across the page\n"
            "4. Aim for keyword in 4-6 locations, not all 10",
        risk_points=risk_addition
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 8: UNNATURAL LINK PATTERNS
# ═══════════════════════════════════════════════════════════════════════════════

def detect_unnatural_links(page_data: dict) -> dict:
    internal_links = page_data.get("internal_links", [])
    external_links = page_data.get("external_links", [])
    word_count = page_data.get("word_count", 1)
    soup = page_data.get("soup")

    evidence = []
    risk_addition = 0

    anchor_texts = [link.get("anchor_text", "").lower().strip() for link in internal_links]

    if anchor_texts:
        from collections import Counter
        anchor_freq = Counter(anchor_texts)
        most_common_anchor, most_common_count = anchor_freq.most_common(1)[0]

        if most_common_count >= 10 and most_common_anchor and len(most_common_anchor) > 3:
            evidence.append(
                f"Exact-match anchor text '{most_common_anchor}' used {most_common_count} times in internal links"
            )
            risk_addition = RISK_WEIGHTS["unnatural_links"]
        elif most_common_count >= 5 and len(most_common_anchor) > 3:
            evidence.append(
                f"Repeated anchor text '{most_common_anchor}' on {most_common_count} internal links"
            )
            risk_addition = 10

    total_links = len(internal_links) + len(external_links)
    link_density = (total_links / (word_count / 100)) if word_count > 0 else 0

    if link_density > 15:
        evidence.append(
            f"High link density: {total_links} links in {word_count} words ({link_density:.1f} links per 100 words)"
        )
        risk_addition = max(risk_addition, 10)

    if soup:
        footer = soup.find("footer")
        if footer:
            footer_links = footer.find_all("a", href=True)
            if len(footer_links) > 50:
                evidence.append(f"Footer contains {len(footer_links)} links — possible link farm pattern")
                risk_addition = max(risk_addition, 15)
            elif len(footer_links) > 20:
                evidence.append(f"Footer has {len(footer_links)} links — review if all are necessary")

    if len(external_links) >= 5:
        ext_anchors = [link.get("anchor_text", "").lower().strip() for link in external_links]
        if len(set(ext_anchors)) <= 2 and all(len(a) > 5 for a in ext_anchors):
            evidence.append(
                f"All {len(external_links)} external links use very similar anchor text — possible paid link scheme"
            )
            risk_addition = max(risk_addition, 15)

    if not evidence:
        return _finding(
            "unnatural_links", CLEAN, SEV_LOW,
            "Unnatural Link Patterns",
            "No unnatural internal link patterns detected.",
            risk_points=0
        )

    severity = SEV_HIGH if risk_addition >= 20 else SEV_MEDIUM
    return _finding(
        "unnatural_links", DETECTED, severity,
        "Unnatural Link Patterns Detected",
        "Internal linking shows patterns that may trigger algorithmic scrutiny",
        evidence=evidence,
        fix="1. Diversify anchor text — use brand name, URL, and descriptive phrases\n"
            "2. Limit footer links to <20 genuinely useful links\n"
            "3. Reduce total link count if link density is high\n"
            "4. Nofollow or remove commercial links that appear paid\n"
            "5. Make linking decisions based on user value, not keyword optimization",
        risk_points=risk_addition
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 9: UNMARKED PAID LINKS
# ═══════════════════════════════════════════════════════════════════════════════

def detect_unmarked_paid_links(page_data: dict) -> dict:
    external_links = page_data.get("external_links", [])
    body_text = page_data.get("body_text", "")

    affiliate_patterns = [
        r'\?ref=', r'\?aff=', r'\?affiliate=', r'\?partner=',
        r'/go/', r'/out/', r'/refer/', r'/referral/',
        r'clickbank\.com', r'shareasale\.com', r'commission', r'affiliate',
        r'\?tag=', r'\?source=aff', r'\?utm_source=affiliate',
    ]

    evidence = []
    risk_addition = 0
    suspicious_links = []

    for link in external_links:
        href = link.get("href", "")
        is_nofollow = link.get("is_nofollow", False)
        rel = link.get("rel", [])
        has_sponsored = "sponsored" in rel

        for pattern in affiliate_patterns:
            if re.search(pattern, href, re.I):
                if not is_nofollow and not has_sponsored:
                    suspicious_links.append(
                        f"Possible unmarked affiliate link: {href[:80]} (missing nofollow/sponsored)"
                    )
                    risk_addition = RISK_WEIGHTS["unmarked_paid_links"]
                break

    disclosure_patterns = [
        r'\bsponsored\b', r'\baffiliate\s+link\b',
        r'\bpaid\s+(post|partnership|link)\b', r'#ad\b'
    ]
    has_disclosure = any(re.search(p, body_text, re.I) for p in disclosure_patterns)

    if suspicious_links:
        evidence.extend(suspicious_links[:5])
        if not has_disclosure:
            evidence.append("No affiliate/sponsored disclosure found on page")

    if not evidence:
        return _finding(
            "unmarked_paid_links", CLEAN, SEV_LOW,
            "Unmarked Paid Links",
            "No unmarked affiliate or paid link patterns detected.",
            risk_points=0
        )

    return _finding(
        "unmarked_paid_links", DETECTED, SEV_MEDIUM,
        "Possible Unmarked Paid/Affiliate Links",
        "Links that appear to be affiliate or paid links are missing proper rel attributes",
        evidence=evidence,
        fix="1. Add rel='nofollow sponsored' to all affiliate links\n"
            "2. Add visible disclosure (FTC requires this)\n"
            "3. Never include commercial links without proper attribution\n"
            "4. Use rel='ugc' for user-submitted links",
        risk_points=risk_addition
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 10: INTRUSIVE INTERSTITIALS
# ═══════════════════════════════════════════════════════════════════════════════

def detect_intrusive_interstitials(page_data: dict) -> dict:
    popup_indicators = page_data.get("popup_indicators", [])
    modal_divs_count = page_data.get("modal_divs_count", 0)
    raw_html = page_data.get("raw_html", "")

    evidence = []
    risk_addition = 0

    intrusive_patterns = [
        (r'exit.?intent', "Exit-intent popup detected"),
        (r'(show|display|open).*(modal|popup|overlay).*onload', "Modal/popup triggers on page load"),
        (r'document\.ready.*modal', "Modal shown on document ready"),
        (r'window\.onload.*popup', "Popup shown on window load"),
        (r'setTimeout.*modal.*show', "Delayed popup detected"),
        (r'newsletter.*(popup|modal|overlay)', "Newsletter popup detected"),
    ]

    for pattern, description in intrusive_patterns:
        if re.search(pattern, raw_html, re.I | re.S):
            evidence.append(description)
            risk_addition = RISK_WEIGHTS["intrusive_interstitials"]

    if modal_divs_count > 0:
        evidence.append(f"{modal_divs_count} modal/overlay element(s) found in HTML")
        risk_addition = max(risk_addition, 10)

    if popup_indicators:
        evidence.append(f"Popup-related JavaScript patterns found: {popup_indicators[:3]}")

    fullscreen_pattern = r'position\s*:\s*fixed[^}]*width\s*:\s*100(vw|%)[^}]*height\s*:\s*100(vh|%)'
    if re.search(fullscreen_pattern, raw_html, re.I | re.S):
        evidence.append("Full-screen fixed overlay CSS detected — likely blocks content visibility")
        risk_addition = max(risk_addition, RISK_WEIGHTS["intrusive_interstitials"])

    if not evidence:
        return _finding(
            "intrusive_interstitials", CLEAN, SEV_LOW,
            "Intrusive Interstitials",
            "No intrusive popup or interstitial patterns detected.",
            risk_points=0
        )

    severity = SEV_HIGH if risk_addition >= 15 else SEV_MEDIUM
    return _finding(
        "intrusive_interstitials", DETECTED, severity,
        "Intrusive Interstitials Detected",
        "Popups or overlays that may block main content — direct Google penalty risk on mobile",
        evidence=evidence,
        fix="1. Remove full-screen popups that trigger immediately on page load\n"
            "2. Exit-intent popups are acceptable but should not cover entire viewport\n"
            "3. Use banners instead of full-screen overlays for offers\n"
            "4. Age/login gates are acceptable exceptions\n"
            "5. Keep any modals dismissible with a clear, visible close button",
        risk_points=risk_addition
    )


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN DETECTOR ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def run_blackhat_detection(page_data: dict, cloaking_data: dict = None,
                           target_keyword: str = None) -> dict:
    """
    Run all 10 black hat checks and return complete risk assessment.
    target_keyword: user-supplied keyword (prevents auto-detection false positives)
    """
    cloaking_data = cloaking_data or {}
    findings = []

    findings.append(detect_keyword_stuffing(page_data, target_keyword=target_keyword))
    findings.append(detect_hidden_text(page_data))
    findings.append(detect_sneaky_redirects(page_data))
    findings.append(detect_doorway_pages(page_data))
    findings.append(detect_over_optimization(page_data, target_keyword=target_keyword))
    findings.append(detect_unnatural_links(page_data))
    findings.append(detect_unmarked_paid_links(page_data))
    findings.append(detect_intrusive_interstitials(page_data))

    if cloaking_data:
        findings.append(detect_cloaking(cloaking_data))
        findings.append(detect_mobile_cloaking(cloaking_data))
    else:
        findings.append(_finding(
            "cloaking", WARNING, SEV_LOW,
            "Cloaking (User-Agent)",
            "Cloaking check skipped — requires additional scrape pass. Run full audit for cloaking detection.",
            risk_points=0
        ))
        findings.append(_finding(
            "mobile_cloaking", WARNING, SEV_LOW,
            "Mobile Cloaking",
            "Mobile cloaking check skipped — requires additional scrape pass.",
            risk_points=0
        ))

    total_risk = sum(f.get("risk_points", 0) for f in findings)
    total_risk = min(100, total_risk)

    if total_risk <= 15:
        risk_level = "low"
        risk_label = "🟢 LOW RISK — Clean practices"
    elif total_risk <= 35:
        risk_level = "moderate"
        risk_label = "🟡 MODERATE RISK — Some issues to fix"
    elif total_risk <= 60:
        risk_level = "high"
        risk_label = "🟠 HIGH RISK — Multiple violations"
    else:
        risk_level = "critical"
        risk_label = "🔴 CRITICAL — Severe penalty likely"

    detected = [f for f in findings if f["status"] == DETECTED]
    warnings = [f for f in findings if f["status"] == WARNING]

    return {
        "risk_score": total_risk,
        "risk_level": risk_level,
        "risk_label": risk_label,
        "findings": findings,
        "detected_count": len(detected),
        "warning_count": len(warnings),
        "clean_count": sum(1 for f in findings if f["status"] == CLEAN),
        "total_checks": len(findings),
        "critical_findings": [f for f in detected if f["severity"] in [SEV_CRITICAL, SEV_HIGH]],
    }