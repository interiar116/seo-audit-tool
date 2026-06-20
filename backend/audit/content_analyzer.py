"""
Content Analyzer
Checks content quality, keyword density, readability, and E-E-A-T signals.
This is what separates surface-level SEO tools from a real audit platform.
"""

import re
import math
import logging
from collections import Counter
from typing import Optional

logger = logging.getLogger(__name__)

# ── Severity constants (mirrors technical_analyzer) ──────────────────────────
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


# ═══════════════════════════════════════════════════════════════════════════════
# WORD COUNT / CONTENT LENGTH
# ═══════════════════════════════════════════════════════════════════════════════

def check_word_count(page_data: dict) -> list:
    results = []
    word_count = page_data.get("word_count", 0)

    if word_count < 100:
        results.append(_issue(
            "content_very_thin", FAIL, SEV_CRITICAL,
            f"Extremely thin content: only {word_count} words",
            "This page likely qualifies as thin content — a direct Google penalty risk. Expand to 600+ words minimum, or consolidate with a related page.",
            value=word_count,
            impact="Thin content is one of Google's top algorithmic penalties (Panda/Helpful Content). Pages under 300 words risk deindexing."
        ))
    elif word_count < 300:
        results.append(_issue(
            "content_thin", FAIL, SEV_HIGH,
            f"Thin content: {word_count} words (minimum threshold is 300)",
            "Expand content to at least 600 words. Cover the topic comprehensively. Google's Helpful Content algorithm penalizes thin pages.",
            value=word_count,
            impact="Pages under 300 words are flagged as thin content and underperform in rankings."
        ))
    elif word_count < 600:
        results.append(_issue(
            "content_short", WARNING, SEV_MEDIUM,
            f"Content is below recommended length: {word_count} words",
            "Consider expanding to 800+ words if this is a competitive keyword. Cover related subtopics and FAQs.",
            value=word_count
        ))
    elif word_count < 1000:
        results.append(_issue(
            "content_adequate", PASS, SEV_LOW,
            f"Content length is adequate: {word_count} words",
            "For competitive keywords, 1,500+ words typically performs better. Use your judgment based on competitor content length.",
            value=word_count
        ))
    else:
        results.append(_issue(
            "content_length_good", PASS, SEV_LOW,
            f"Good content length: {word_count} words",
            "", value=word_count
        ))

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# KEYWORD DENSITY ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

def _calculate_keyword_density(text: str, keyword: str) -> float:
    """Calculate keyword density as a percentage."""
    if not text or not keyword:
        return 0.0
    words = text.lower().split()
    keyword_words = keyword.lower().split()
    keyword_count = 0

    # Count phrase occurrences
    for i in range(len(words) - len(keyword_words) + 1):
        if words[i:i + len(keyword_words)] == keyword_words:
            keyword_count += 1

    if not words:
        return 0.0

    return round((keyword_count / len(words)) * 100, 2)


def _extract_top_keywords(text: str, top_n: int = 10) -> list:
    """Extract most frequent words (excluding stop words) as potential keywords."""
    stop_words = {
        "the", "be", "to", "of", "and", "a", "in", "that", "have", "it",
        "for", "not", "on", "with", "he", "as", "you", "do", "at", "this",
        "but", "his", "by", "from", "they", "we", "say", "her", "she", "or",
        "an", "will", "my", "one", "all", "would", "there", "their", "what",
        "so", "up", "out", "if", "about", "who", "get", "which", "go", "me",
        "when", "make", "can", "like", "time", "no", "just", "him", "know",
        "take", "people", "into", "year", "your", "good", "some", "could",
        "them", "see", "other", "than", "then", "now", "look", "only", "come",
        "its", "over", "think", "also", "back", "after", "use", "two", "how",
        "our", "work", "first", "well", "way", "even", "new", "want", "because",
        "any", "these", "give", "day", "most", "us", "is", "are", "was", "were",
        "been", "has", "had", "did", "does", "said", "each", "more", "may",
    }
    words = re.findall(r'\b[a-z]{3,}\b', text.lower())
    filtered = [w for w in words if w not in stop_words]
    count = Counter(filtered)
    return [(word, freq) for word, freq in count.most_common(top_n)]


def check_keyword_usage(page_data: dict, target_keyword: Optional[str] = None) -> dict:
    """
    Analyze keyword usage in content and key SEO locations.
    Returns keyword analysis data (not just issues — full metrics for frontend display).
    """
    body_text = page_data.get("body_text", "")
    title = page_data.get("title", "") or ""
    meta_description = page_data.get("meta_description", "") or ""
    headings = page_data.get("headings", {})
    h1_tags = headings.get("h1", [])
    h2_tags = headings.get("h2", [])
    word_count = page_data.get("word_count", 0)

    top_keywords = _extract_top_keywords(body_text, top_n=10)

    # If user didn't specify a target keyword, use the most frequent content word
    if not target_keyword and top_keywords:
        target_keyword = top_keywords[0][0]
        keyword_auto_detected = True
    else:
        keyword_auto_detected = False

    result = {
        "target_keyword": target_keyword,
        "keyword_auto_detected": keyword_auto_detected,
        "top_keywords": top_keywords,
        "keyword_analysis": {},
        "issues": [],
    }

    if not target_keyword:
        return result

    keyword = target_keyword.lower().strip()

    # Keyword density
    density = _calculate_keyword_density(body_text, keyword)

    # Keyword presence in key locations
    in_title = keyword in title.lower()
    in_meta = keyword in meta_description.lower()
    in_h1 = any(keyword in h.lower() for h in h1_tags)
    in_h2 = any(keyword in h.lower() for h in h2_tags)

    # First 100 words check
    first_100 = " ".join(body_text.split()[:100]).lower()
    in_first_100 = keyword in first_100

    # Count occurrences in body
    occurrences_in_body = body_text.lower().count(keyword)

    # Consecutive repetition check (keyword stuffing signal)
    words = body_text.lower().split()
    max_consecutive = 0
    current_consecutive = 0
    for word in words:
        if keyword in word:
            current_consecutive += 1
            max_consecutive = max(max_consecutive, current_consecutive)
        else:
            current_consecutive = 0

    result["keyword_analysis"] = {
        "density": density,
        "occurrences": occurrences_in_body,
        "in_title": in_title,
        "in_meta_description": in_meta,
        "in_h1": in_h1,
        "in_h2": in_h2,
        "in_first_100_words": in_first_100,
        "max_consecutive_repetitions": max_consecutive,
    }

    # ── Generate issues based on findings ───────────────────────────────
    issues = []

    # Density checks
    if density > 4.0:
        issues.append(_issue(
            "keyword_stuffing_critical", FAIL, SEV_CRITICAL,
            f"Severe keyword stuffing: '{keyword}' appears at {density}% density ({occurrences_in_body} times)",
            "Reduce keyword usage to 0.5-2%. Replace repetitions with semantic variations. This triggers Google's keyword stuffing filter.",
            value=density,
            impact="Keyword stuffing is a manual penalty trigger. Google can deindex or demote the entire site."
        ))
    elif density > 3.0:
        issues.append(_issue(
            "keyword_density_high", FAIL, SEV_HIGH,
            f"High keyword density: '{keyword}' at {density}% ({occurrences_in_body} occurrences)",
            "Reduce to 1-2% density. Diversify with LSI keywords and natural language variations.",
            value=density,
            impact="Density above 3% puts page at risk of algorithmic penalty."
        ))
    elif density > 2.0:
        issues.append(_issue(
            "keyword_density_moderate", WARNING, SEV_MEDIUM,
            f"Keyword density slightly elevated: {density}% for '{keyword}'",
            "Consider reducing slightly. Aim for 1-2% with natural language.",
            value=density
        ))
    elif density < 0.3 and word_count > 300:
        issues.append(_issue(
            "keyword_density_low", WARNING, SEV_MEDIUM,
            f"Very low keyword density: '{keyword}' appears only {occurrences_in_body} time(s) in {word_count} words",
            "Ensure your primary keyword appears naturally throughout the content. Aim for 0.5-1.5%.",
            value=density
        ))
    else:
        issues.append(_issue(
            "keyword_density_ok", PASS, SEV_LOW,
            f"Keyword density is healthy: {density}% for '{keyword}'",
            "", value=density
        ))

    # Keyword in key locations
    missing_locations = []
    if not in_title:
        missing_locations.append("title tag")
    if not in_h1:
        missing_locations.append("H1 heading")
    if not in_meta:
        missing_locations.append("meta description")
    if not in_first_100:
        missing_locations.append("first 100 words")

    if len(missing_locations) >= 3:
        issues.append(_issue(
            "keyword_placement_poor", FAIL, SEV_HIGH,
            f"Target keyword '{keyword}' missing from key locations: {', '.join(missing_locations)}",
            "Place your primary keyword in the title, H1, first paragraph, and meta description.",
            value=missing_locations,
            impact="Keyword placement in these locations is how Google identifies page relevance."
        ))
    elif missing_locations:
        issues.append(_issue(
            "keyword_placement_partial", WARNING, SEV_MEDIUM,
            f"Keyword missing from: {', '.join(missing_locations)}",
            f"Add '{keyword}' to {' and '.join(missing_locations)} for stronger relevance signals.",
            value=missing_locations
        ))
    else:
        issues.append(_issue(
            "keyword_placement_ok", PASS, SEV_LOW,
            f"Keyword present in title, H1, meta description, and early content",
            ""
        ))

    # Consecutive repetition (stuffing pattern)
    if max_consecutive >= 3:
        issues.append(_issue(
            "keyword_consecutive_repetition", FAIL, SEV_HIGH,
            f"Keyword appears {max_consecutive} times consecutively — clear stuffing pattern",
            "Remove consecutive keyword repetitions immediately. This is a textbook stuffing signal.",
            value=max_consecutive
        ))

    result["issues"] = issues
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# CONTENT FRESHNESS
# ═══════════════════════════════════════════════════════════════════════════════

def check_content_freshness(page_data: dict) -> list:
    """
    Detects date signals in content to estimate freshness.
    Note: Last-Modified header is more reliable but not always present.
    """
    results = []
    body_text = page_data.get("body_text", "")
    headers = page_data.get("headers", {})

    # Check Last-Modified header
    last_modified = headers.get("Last-Modified") or headers.get("last-modified")
    if last_modified:
        results.append(_issue(
            "last_modified_present", PASS, SEV_LOW,
            f"Last-Modified header: {last_modified}",
            "Ensure this date reflects actual content updates, not server configuration changes.",
            value=last_modified
        ))

    # Look for year patterns in content (rough freshness signal)
    current_year = 2026
    years_found = re.findall(r'\b(20\d{2})\b', body_text)
    if years_found:
        years = [int(y) for y in years_found]
        most_recent_year = max(years)
        age = current_year - most_recent_year

        if age >= 3:
            results.append(_issue(
                "content_potentially_stale", WARNING, SEV_MEDIUM,
                f"Most recent year reference found in content: {most_recent_year} ({age} years ago)",
                "Review and update content. Stale content underperforms against fresh competitors, especially for 'best', 'top', 'current' queries.",
                value=most_recent_year
            ))
        elif age == 0 or age == 1:
            results.append(_issue(
                "content_fresh", PASS, SEV_LOW,
                f"Content appears relatively fresh (references {most_recent_year})",
                "", value=most_recent_year
            ))

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# READABILITY
# ═══════════════════════════════════════════════════════════════════════════════

def _count_syllables(word: str) -> int:
    """Approximate syllable count for Flesch reading ease."""
    word = word.lower().strip(".,!?;:")
    if len(word) <= 3:
        return 1
    vowels = "aeiouy"
    count = 0
    prev_was_vowel = False
    for char in word:
        is_vowel = char in vowels
        if is_vowel and not prev_was_vowel:
            count += 1
        prev_was_vowel = is_vowel
    if word.endswith("e"):
        count -= 1
    return max(1, count)


def check_readability(page_data: dict) -> list:
    """
    Basic readability analysis using Flesch Reading Ease approximation.
    Also checks for paragraph/sentence structure.
    """
    results = []
    body_text = page_data.get("body_text", "")

    if not body_text or len(body_text) < 200:
        return results

    # Split into sentences
    sentences = re.split(r'[.!?]+', body_text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

    if not sentences:
        return results

    words = body_text.split()
    word_count = len(words)
    sentence_count = len(sentences)

    if sentence_count == 0:
        return results

    avg_words_per_sentence = word_count / sentence_count

    # Flesch approximation
    total_syllables = sum(_count_syllables(w) for w in words)
    flesch = 206.835 - (1.015 * avg_words_per_sentence) - (84.6 * (total_syllables / max(word_count, 1)))
    flesch = round(max(0, min(100, flesch)), 1)

    # Sentence length checks
    if avg_words_per_sentence > 25:
        results.append(_issue(
            "sentences_too_long", WARNING, SEV_LOW,
            f"Average sentence length is long: {avg_words_per_sentence:.1f} words",
            "Break up long sentences. Aim for 15-20 words average. Shorter sentences = better readability and dwell time.",
            value=avg_words_per_sentence
        ))
    elif avg_words_per_sentence < 8:
        results.append(_issue(
            "sentences_very_short", WARNING, SEV_LOW,
            f"Very short average sentence length: {avg_words_per_sentence:.1f} words",
            "Vary sentence length for better reading flow. Very choppy sentences feel unnatural.",
            value=avg_words_per_sentence
        ))
    else:
        results.append(_issue(
            "sentence_length_ok", PASS, SEV_LOW,
            f"Good average sentence length: {avg_words_per_sentence:.1f} words",
            "", value=avg_words_per_sentence
        ))

    # Flesch score interpretation
    if flesch < 30:
        results.append(_issue(
            "readability_very_difficult", WARNING, SEV_MEDIUM,
            f"Content is very difficult to read (Flesch score: {flesch})",
            "Simplify vocabulary and shorten sentences. Most web content should target Flesch 60-70 (plain English).",
            value=flesch
        ))
    elif flesch < 50:
        results.append(_issue(
            "readability_difficult", WARNING, SEV_LOW,
            f"Content is moderately difficult to read (Flesch score: {flesch})",
            "Consider simplifying for broader audience. Aim for 60+ Flesch score for most commercial content.",
            value=flesch
        ))
    elif flesch >= 60:
        results.append(_issue(
            "readability_good", PASS, SEV_LOW,
            f"Good readability score: {flesch} (Flesch Reading Ease)",
            "", value=flesch
        ))

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# E-E-A-T SIGNALS
# ═══════════════════════════════════════════════════════════════════════════════

def check_eeat_signals(page_data: dict) -> list:
    """
    Checks for E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness) signals.
    Critical for YMYL pages. Based on Google's Quality Rater Guidelines.
    """
    results = []
    body_text = page_data.get("body_text", "")
    soup = page_data.get("soup")
    schema_scripts = page_data.get("schema_scripts", [])

    # Author byline detection
    author_patterns = [
        r'by\s+[A-Z][a-z]+\s+[A-Z][a-z]+',  # "By John Smith"
        r'author[:\s]+[A-Z][a-z]+',            # "Author: John"
        r'written\s+by\s+[A-Z]',               # "Written by J..."
        r'<[^>]*class="[^"]*author[^"]*"',      # Author CSS class
    ]
    has_author = any(re.search(p, body_text, re.I) for p in author_patterns)

    # Check schema for author
    has_author_schema = any(
        isinstance(s, dict) and ("author" in s or s.get("@type") in ["Person", "Author"])
        for s in schema_scripts
    )

    if not has_author and not has_author_schema:
        results.append(_issue(
            "eeat_no_author", WARNING, SEV_MEDIUM,
            "No author byline or author schema detected",
            "Add a visible author byline with credentials. Link to an author bio page. Implement Person schema. Critical for YMYL content.",
            impact="Google's QRG specifically looks for author expertise signals. No author = lower E-E-A-T score."
        ))
    else:
        results.append(_issue(
            "eeat_author_detected", PASS, SEV_LOW,
            "Author signal detected (byline or schema)",
            ""
        ))

    # External citations/links to authoritative sources
    external_links = page_data.get("external_links", [])
    authoritative_domains = [
        ".gov", ".edu", "wikipedia.org", "pubmed", "ncbi.nlm",
        "nature.com", "sciencedirect", "reuters.com", "apnews.com"
    ]
    has_authoritative_citations = any(
        any(auth in link.get("domain", "") for auth in authoritative_domains)
        for link in external_links
    )

    if not has_authoritative_citations and len(external_links) == 0:
        results.append(_issue(
            "eeat_no_citations", WARNING, SEV_LOW,
            "No external citations or references found",
            "Link to authoritative sources to support your claims. This builds trust and E-E-A-T."
        ))

    # Statistics and data signals (rough check)
    stats_pattern = r'\b\d+(\.\d+)?(%|percent|billion|million|thousand|study|research|survey|report)\b'
    has_stats = bool(re.search(stats_pattern, body_text, re.I))

    if not has_stats:
        results.append(_issue(
            "eeat_no_data", WARNING, SEV_LOW,
            "No statistics or data references detected in content",
            "Include relevant statistics, research findings, or data points. Data-backed content scores higher for E-E-A-T."
        ))

    # Personal experience signals (for Experience component of E-E-A-T)
    experience_patterns = [
        r'\bI (have|had|tested|tried|used|found|discovered|noticed)\b',
        r'\bin my experience\b',
        r'\bI\'ve been\b',
        r'\bmy (review|testing|experience|recommendation)\b',
    ]
    has_experience = any(re.search(p, body_text, re.I) for p in experience_patterns)

    if has_experience:
        results.append(_issue(
            "eeat_experience_signals", PASS, SEV_LOW,
            "First-person experience signals detected (positive E-E-A-T indicator)",
            ""
        ))

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# CONTENT STRUCTURE CHECKS
# ═══════════════════════════════════════════════════════════════════════════════

def check_content_structure(page_data: dict) -> list:
    results = []
    soup = page_data.get("soup")
    word_count = page_data.get("word_count", 0)

    if not soup:
        return results

    # Check for bullet points / lists (important for formatting signals)
    lists = soup.find_all(["ul", "ol"])
    list_count = len(lists)

    if word_count > 500 and list_count == 0:
        results.append(_issue(
            "no_lists", WARNING, SEV_LOW,
            "No bullet points or numbered lists found",
            "Add lists to break up content. Lists improve readability and are more likely to be featured in Google's list snippets.",
        ))

    # Check for tables
    tables = soup.find_all("table")
    if tables:
        results.append(_issue(
            "has_tables", PASS, SEV_LOW,
            f"{len(tables)} table(s) found — good for data comparison content",
            ""
        ))

    # Check for FAQ schema + FAQ content
    has_faq_schema = any(
        isinstance(s, dict) and s.get("@type") == "FAQPage"
        for s in page_data.get("schema_scripts", [])
    )

    faq_pattern = r'\b(FAQ|frequently asked|Q:|A:|Question:|Answer:)\b'
    has_faq_content = bool(re.search(faq_pattern, page_data.get("body_text", ""), re.I))

    if has_faq_content and not has_faq_schema:
        results.append(_issue(
            "faq_no_schema", WARNING, SEV_MEDIUM,
            "FAQ-style content detected but no FAQPage schema markup",
            "Add FAQPage schema to unlock FAQ rich results in Google SERPs — can double your SERP real estate.",
            impact="FAQPage schema can appear directly in SERPs above regular results."
        ))
    elif has_faq_schema:
        results.append(_issue(
            "faq_schema_present", PASS, SEV_LOW,
            "FAQPage schema markup detected — eligible for FAQ rich results",
            ""
        ))

    # Internal link context check
    internal_links = page_data.get("internal_links", [])
    if internal_links:
        # Check anchor text quality
        generic_anchors = ["click here", "read more", "here", "link", "this", "more", "learn more"]
        generic_count = sum(
            1 for link in internal_links
            if link.get("anchor_text", "").lower().strip() in generic_anchors
        )
        if generic_count > 2:
            results.append(_issue(
                "generic_anchor_text", WARNING, SEV_MEDIUM,
                f"{generic_count} internal links use generic anchor text (click here, read more, etc.)",
                "Use descriptive keyword-rich anchor text for internal links. It signals content relevance to Google.",
                value=generic_count
            ))

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# DUPLICATE CONTENT SIGNALS
# ═══════════════════════════════════════════════════════════════════════════════

def check_duplicate_signals(page_data: dict) -> list:
    """
    Checks for on-page duplicate content signals.
    Note: Cross-site duplicate detection requires a paid API (Copyscape etc.)
    This checks for obvious self-duplication and thin/templated content signals.
    """
    results = []
    body_text = page_data.get("body_text", "")
    title = page_data.get("title", "") or ""
    meta_description = page_data.get("meta_description", "") or ""

    if not body_text:
        return results

    # Check if title and meta description are identical (templated content signal)
    if title and meta_description:
        if title.lower().strip() == meta_description.lower().strip():
            results.append(_issue(
                "title_equals_meta", FAIL, SEV_HIGH,
                "Title tag and meta description are identical",
                "Write unique meta descriptions for each page. Identical title/meta = templated content signal.",
                impact="Templated content is a Google Panda penalty trigger."
            ))

    # Check for repeated paragraph patterns (content spinning signal)
    paragraphs = [p.strip() for p in re.split(r'\n\n+', body_text) if len(p.strip()) > 50]
    if len(paragraphs) > 3:
        # Check if any two paragraphs are very similar (>70% word overlap)
        def word_overlap(a, b):
            a_words = set(a.lower().split())
            b_words = set(b.lower().split())
            if not a_words or not b_words:
                return 0
            return len(a_words & b_words) / min(len(a_words), len(b_words))

        duplicate_paragraphs = 0
        for i in range(len(paragraphs)):
            for j in range(i + 1, len(paragraphs)):
                if word_overlap(paragraphs[i], paragraphs[j]) > 0.7:
                    duplicate_paragraphs += 1

        if duplicate_paragraphs > 0:
            results.append(_issue(
                "duplicate_paragraphs", WARNING, SEV_HIGH,
                f"{duplicate_paragraphs} paragraph(s) appear to have very similar content (possible content spinning/duplication)",
                "Review and rewrite duplicate paragraphs. Each section should add unique value.",
                value=duplicate_paragraphs
            ))

    # AI content pattern detection (basic signals)
    ai_patterns = [
        (r'\bIn conclusion,\b.*\bIn summary,\b', "Uses both 'In conclusion' and 'In summary' (AI writing pattern)"),
        (r'\bIn this (article|post|guide|piece),\b', "Generic AI opener pattern detected"),
        (r'\b(Moreover|Furthermore|Additionally|In addition),\b.*\b(Moreover|Furthermore|Additionally|In addition),\b', "Excessive transition word stacking (AI pattern)"),
        (r'\bIt is (important|worth|crucial|essential|vital) to note that\b', "Formulaic hedge phrase (AI writing signal)"),
    ]

    ai_signals_found = []
    for pattern, description in ai_patterns:
        if re.search(pattern, body_text, re.I | re.S):
            ai_signals_found.append(description)

    if len(ai_signals_found) >= 2:
        results.append(_issue(
            "ai_content_patterns", WARNING, SEV_MEDIUM,
            f"Multiple AI-generated content patterns detected: {'; '.join(ai_signals_found[:2])}",
            "Review content for AI-generated patterns. Add personal experience, specific examples, and unique insights. Google's Helpful Content system targets generic AI content.",
            value=ai_signals_found,
            impact="Google's Helpful Content algorithm aggressively demotes AI content without genuine expertise or experience."
        ))

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN CONTENT ANALYZER ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_content(page_data: dict, target_keyword: Optional[str] = None) -> dict:
    """
    Run all content analysis checks.

    Returns:
        {
            "checks": [...all individual issues...],
            "keyword_data": {...keyword analysis metrics...},
            "score": int (0-100),
            "word_count": int,
            "readability_score": float,
            ...
        }
    """
    all_checks = []

    all_checks.extend(check_word_count(page_data))
    all_checks.extend(check_readability(page_data))
    all_checks.extend(check_eeat_signals(page_data))
    all_checks.extend(check_content_structure(page_data))
    all_checks.extend(check_duplicate_signals(page_data))
    all_checks.extend(check_content_freshness(page_data))

    # Keyword analysis (returns issues + metrics)
    keyword_result = check_keyword_usage(page_data, target_keyword)
    all_checks.extend(keyword_result.get("issues", []))

    # Score calculation
    critical = sum(1 for c in all_checks if c["status"] in [FAIL, WARNING] and c["severity"] == SEV_CRITICAL)
    high = sum(1 for c in all_checks if c["status"] in [FAIL, WARNING] and c["severity"] == SEV_HIGH)
    medium = sum(1 for c in all_checks if c["status"] in [FAIL, WARNING] and c["severity"] == SEV_MEDIUM)
    low = sum(1 for c in all_checks if c["status"] in [FAIL, WARNING] and c["severity"] == SEV_LOW)
    passes = sum(1 for c in all_checks if c["status"] == PASS)

    deductions = (critical * 20) + (high * 10) + (medium * 5) + (low * 2)
    score = max(0, min(100, 100 - deductions))

    return {
        "checks": all_checks,
        "keyword_data": keyword_result,
        "score": score,
        "word_count": page_data.get("word_count", 0),
        "issues_critical": critical,
        "issues_high": high,
        "issues_medium": medium,
        "issues_low": low,
        "passes": passes,
        "total_checks": len(all_checks),
    }
