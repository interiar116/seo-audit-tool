"""
Audit Engine — Main Orchestrator
Coordinates the scraper, technical analyzer, content analyzer, and black hat detector.
Handles async execution, stores results in DB, and builds the final audit report.
"""

import threading
import logging
import traceback
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


def run_audit(audit_id: int, url: str, target_keyword: Optional[str] = None,
              run_cloaking_check: bool = True, app=None) -> None:
    """
    Main audit execution function. Designed to run in a background thread.
    """
    def _run():
        with app.app_context():
            from models import db, Audit
            from scrapers.page_scraper import (
                scrape_page,
                scrape_for_cloaking_detection,
                scrape_robots_txt,
                scrape_sitemap,
            )
            from audit.technical_analyzer import analyze_technical
            from audit.content_analyzer import analyze_content
            from audit.blackhat_detector import run_blackhat_detection

            audit = Audit.query.get(audit_id)
            if not audit:
                logger.error(f"Audit ID {audit_id} not found in database")
                return

            try:
                # ── STEP 1: Update status to running ─────────────────────
                audit.status = "running"
                audit.started_at = datetime.now(timezone.utc)
                db.session.commit()
                logger.info(f"[Audit {audit_id}] Starting audit for: {url}")

                # ── STEP 2: Scrape robots.txt and sitemap ─────────────────
                logger.info(f"[Audit {audit_id}] Fetching robots.txt...")
                robots_data = scrape_robots_txt(url)

                logger.info(f"[Audit {audit_id}] Fetching sitemap...")
                sitemap_data = scrape_sitemap(url)

                # ── STEP 3: Main page scrape ──────────────────────────────
                logger.info(f"[Audit {audit_id}] Scraping page (Playwright)...")
                page_data = scrape_page(url, use_playwright=True)

                if not page_data.get("success"):
                    error_msg = page_data.get("error", "Unknown scrape error")
                    logger.error(f"[Audit {audit_id}] Scrape failed: {error_msg}")
                    audit.status = "failed"
                    audit.error_message = error_msg
                    audit.completed_at = datetime.now(timezone.utc)
                    db.session.commit()
                    return

                # ── STEP 4: Cloaking detection (optional) ─────────────────
                cloaking_data = None
                if run_cloaking_check:
                    logger.info(f"[Audit {audit_id}] Running cloaking detection (3x scrape)...")
                    try:
                        cloaking_data = scrape_for_cloaking_detection(url)
                    except Exception as e:
                        logger.warning(f"[Audit {audit_id}] Cloaking check failed: {e} — continuing without it")

                # ── STEP 5: Run all analyzers ─────────────────────────────
                logger.info(f"[Audit {audit_id}] Running technical analysis...")
                technical_results = analyze_technical(
                    page_data,
                    url=page_data.get("final_url", url),
                    robots_txt_data=robots_data,
                    sitemap_data=sitemap_data,
                )

                logger.info(f"[Audit {audit_id}] Running content analysis...")
                content_results = analyze_content(page_data, target_keyword=target_keyword)

                logger.info(f"[Audit {audit_id}] Running black hat detection...")
                blackhat_results = run_blackhat_detection(
                    page_data,
                    cloaking_data=cloaking_data,
                    target_keyword=target_keyword,  # ← pass user keyword to prevent false positives
                )

                # ── STEP 6: Build final report ────────────────────────────
                final_url = page_data.get("final_url", url)
                was_redirected = final_url.rstrip("/").lower() != url.rstrip("/").lower()

                report = {
                    "meta": {
                        "url": url,
                        "final_url": final_url,
                        "was_redirected": was_redirected,
                        "status_code": page_data.get("status_code"),
                        "load_time_ms": page_data.get("load_time_ms"),
                        "word_count": page_data.get("word_count", 0),
                        "scrape_method": page_data.get("scrape_method"),
                        "audited_at": datetime.now(timezone.utc).isoformat(),
                    },
                    "scores": {
                        "technical": technical_results["score"],
                        "content": content_results["score"],
                        "blackhat_risk": blackhat_results["risk_score"],
                        "overall": _calculate_overall_score(technical_results, content_results, blackhat_results),
                    },
                    "summary": {
                        "technical_critical": technical_results["issues_critical"],
                        "technical_high": technical_results["issues_high"],
                        "technical_medium": technical_results["issues_medium"],
                        "technical_passes": technical_results["passes"],
                        "content_word_count": content_results["word_count"],
                        "blackhat_risk_level": blackhat_results["risk_level"],
                        "blackhat_detected_count": blackhat_results["detected_count"],
                    },
                    "technical": {
                        "score": technical_results["score"],
                        "checks": technical_results["checks"],
                    },
                    "content": {
                        "score": content_results["score"],
                        "checks": content_results["checks"],
                        "keyword_data": content_results["keyword_data"],
                    },
                    "blackhat": {
                        "risk_score": blackhat_results["risk_score"],
                        "risk_level": blackhat_results["risk_level"],
                        "risk_label": blackhat_results["risk_label"],
                        "findings": blackhat_results["findings"],
                        "detected_count": blackhat_results["detected_count"],
                    },
                    "page_info": {
                        "title": page_data.get("title"),
                        "meta_description": page_data.get("meta_description"),
                        "canonical_url": page_data.get("canonical_url"),
                        "h1": page_data.get("headings", {}).get("h1", []),
                        "schema_types": [
                            s.get("@type") for s in page_data.get("schema_scripts", [])
                            if isinstance(s, dict)
                        ],
                        "internal_link_count": page_data.get("internal_link_count", 0),
                        "external_link_count": page_data.get("external_link_count", 0),
                        "image_count": len(page_data.get("images", [])),
                        "robots_txt": {
                            "found": robots_data.get("found"),
                            "disallow_all": robots_data.get("disallow_all"),
                            "sitemap_urls": robots_data.get("sitemap_urls", []),
                        },
                        "sitemap": {
                            "found": sitemap_data.get("found"),
                            "url_count": sitemap_data.get("url_count", 0),
                        },
                    },
                    "recovery_priority": _build_recovery_priority(
                        technical_results, content_results, blackhat_results
                    ),
                }

                # ── STEP 7: Save to database ──────────────────────────────
                audit.status = "completed"
                audit.results = report
                audit.overall_score = report["scores"]["overall"]
                audit.completed_at = datetime.now(timezone.utc)
                audit.technical_score = technical_results["score"]
                audit.content_score = content_results["score"]
                audit.blackhat_risk_score = blackhat_results["risk_score"]

                db.session.commit()
                logger.info(f"[Audit {audit_id}] Complete. Overall score: {report['scores']['overall']}")

            except Exception as e:
                logger.error(f"[Audit {audit_id}] Unexpected error: {traceback.format_exc()}")
                try:
                    audit.status = "failed"
                    audit.error_message = str(e)
                    audit.completed_at = datetime.now(timezone.utc)
                    db.session.commit()
                except Exception:
                    pass

    if app:
        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
    else:
        logger.error("run_audit called without Flask app context")


def _calculate_overall_score(technical: dict, content: dict, blackhat: dict) -> int:
    """
    Weighted overall score:
    - Technical: 40%
    - Content: 35%
    - Blackhat: penalty up to 50 points
    """
    tech_score = technical["score"]
    content_score = content["score"]
    blackhat_penalty = blackhat["risk_score"] * 0.5

    raw_score = (tech_score * 0.40) + (content_score * 0.35) + (60 * 0.25)
    final_score = max(0, min(100, raw_score - blackhat_penalty))

    return round(final_score)


def _build_recovery_priority(technical: dict, content: dict, blackhat: dict) -> list:
    """
    Prioritized recovery action list sorted by severity.
    Returns top 20 issues across all audit sections.
    """
    priority_items = []

    for check in technical.get("checks", []):
        if check["status"] in ["fail", "warning"] and check["severity"] in ["critical", "high"]:
            priority_items.append({
                "category": "technical",
                "severity": check["severity"],
                "title": check["message"],
                "recommendation": check["recommendation"],
                "impact": check.get("impact", ""),
                "check_id": check["check_id"],
            })

    for check in content.get("checks", []):
        if check["status"] in ["fail", "warning"] and check["severity"] in ["critical", "high"]:
            priority_items.append({
                "category": "content",
                "severity": check["severity"],
                "title": check["message"],
                "recommendation": check["recommendation"],
                "impact": check.get("impact", ""),
                "check_id": check["check_id"],
            })

    for finding in blackhat.get("critical_findings", []):
        priority_items.append({
            "category": "blackhat",
            "severity": finding["severity"],
            "title": finding["title"],
            "recommendation": finding["fix"],
            "impact": "Black hat practices can result in manual penalties or algorithmic deindexing",
            "check_id": finding["check_id"],
            "evidence": finding.get("evidence", []),
        })

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    priority_items.sort(key=lambda x: severity_order.get(x["severity"], 4))

    return priority_items[:20]