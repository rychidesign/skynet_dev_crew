from typing import List, Optional, Dict, Any
from .score_models import MentionData, ResponseData, TechnicalCheckData, CompetitorData, MetricScoreRecord, HallucinationFinding
from .score_constants import METRIC_DEFINITIONS

def compute_geo_01(mentions: List[MentionData], total_queries: int) -> MetricScoreRecord:
    """GEO-01: Entity Salience. Weight=0.15"""
    if not total_queries or not mentions:
        return MetricScoreRecord(metric_id="GEO-01-ENT-SAL", metric_category="entity_semantic", score=0.0)
    
    top_mentions = len([m for m in mentions if m.position_rank == 1])
    top_mention_rate = top_mentions / total_queries
    
    avg_rank = sum(m.position_rank for m in mentions) / len(mentions)
    # Plan says: 1 - (avg_rank - 1) / max_rank. max_rank = 10.
    entity_rank_pos = 1 - (avg_rank - 1) / 10.0
    
    confusion_instances = len([m for m in mentions if m.is_confused])
    disambiguation_clarity = 1 - (confusion_instances / len(mentions))
    
    score = (0.4 * top_mention_rate + 0.35 * entity_rank_pos + 0.25 * disambiguation_clarity) * 100
    return _create_record("GEO-01-ENT-SAL", "entity_semantic", score, {
        "top_mention_rate": top_mention_rate,
        "entity_rank_pos": entity_rank_pos,
        "disambiguation_clarity": disambiguation_clarity
    })

def compute_geo_03(mentions: List[MentionData], platforms: List[str]) -> MetricScoreRecord:
    """GEO-03: Entity Consistency. Weight=0.08"""
    if not platforms or len(platforms) < 2:
        return MetricScoreRecord(metric_id="GEO-03-ENT-CON", metric_category="entity_semantic", score=0.0)
    
    all_attrs = set()
    for m in mentions: all_attrs.update(m.extracted_attributes.keys())
    
    if not all_attrs:
        return MetricScoreRecord(metric_id="GEO-03-ENT-CON", metric_category="entity_semantic", score=100.0)
    
    inconsistency_count = 0
    for attr in all_attrs:
        vals = [str(m.extracted_attributes[attr]).lower().strip() for m in mentions if attr in m.extracted_attributes]
        if len(set(vals)) > 1: inconsistency_count += 1
            
    score = (1 - (inconsistency_count / len(all_attrs))) * 100
    return _create_record("GEO-03-ENT-CON", "entity_semantic", score, {"inconsistency_rate": inconsistency_count / len(all_attrs)})

def compute_geo_04(mentions: List[MentionData], total_topic_mentions: int) -> MetricScoreRecord:
    """GEO-04: Topical Authority. Weight=0.10"""
    if not mentions:
        return MetricScoreRecord(metric_id="GEO-04-TOP-AUTH", metric_category="entity_semantic", score=0.0)
    
    auth_cite_rate = len([m for m in mentions if m.is_authority_cite]) / max(total_topic_mentions, 1)
    expert_markers = ["leading", "expert", "trusted", "specialist", "authority"]
    expert_lang_count = sum(1 for m in mentions if any(mark.lower() in expert_markers for mark in m.authority_markers))
    expert_lang_rate = expert_lang_count / len(mentions)
    
    # ExclusiveInsightRate - simulated as 0.5 if not available
    exclusive_insight = 0.5 
    
    score = (0.35 * auth_cite_rate + 0.35 * expert_lang_rate + 0.3 * exclusive_insight) * 100
    return _create_record("GEO-04-TOP-AUTH", "entity_semantic", score, {
        "auth_cite_rate": auth_cite_rate, "expert_lang_rate": expert_lang_rate
    })

def compute_geo_05(responses: List[ResponseData]) -> MetricScoreRecord:
    """GEO-05: Citation Frequency. Weight=0.15"""
    total_citations = sum(len([c for c in r.citations if c.get("is_brand_citation")]) for r in responses)
    # Benchmark: avg citations of top 3 competitors. Mocked as 5.0 for now.
    benchmark = 5.0 
    score = min(100.0, (total_citations / benchmark) * 100.0)
    return _create_record("GEO-05-CIT-FRQ", "citations_trust", score, {"total_citations": total_citations})

def compute_geo_07(responses: List[ResponseData]) -> MetricScoreRecord:
    """GEO-07: RAG Inclusion Rate. Weight=0.12"""
    perplexity_responses = [r for r in responses if r.platform == "perplexity"]
    if not perplexity_responses:
        return MetricScoreRecord(metric_id="GEO-07-RAG-INC", metric_category="citations_trust", score=0.0)
        
    brand_hits = sum(len([s for s in r.rag_sources if s.get("is_brand_source")]) for r in perplexity_responses)
    total_sources = sum(len(r.rag_sources) for r in perplexity_responses)
    
    # RelevancyMultiplier simulated as 1.0
    relevancy_mult = 1.0
    score = (brand_hits / max(total_sources, 1)) * 100.0 * relevancy_mult
    return _create_record("GEO-07-RAG-INC", "citations_trust", score, {"brand_hits": brand_hits, "total_sources": total_sources})

def compute_geo_11(tech: Optional[TechnicalCheckData]) -> MetricScoreRecord:
    """GEO-11: Freshness and Recency. Weight=0.06"""
    if not tech:
        return MetricScoreRecord(metric_id="GEO-11-FRS-REC", metric_category="content_technical", score=0.0)
    
    recency = 1 / max(tech.avg_lastmod_days, 1)
    frequency = min(1.0, tech.update_frequency_monthly / 4.0)
    relevance = tech.current_year_content_pct / 100.0
    
    score = (0.4 * recency + 0.3 * frequency + 0.3 * relevance) * 100
    return _create_record("GEO-11-FRS-REC", "content_technical", score, {"recency": recency, "frequency": frequency})

def compute_geo_13(mentions: List[MentionData]) -> MetricScoreRecord:
    """GEO-13: Sentiment Polarity. Weight=0.10"""
    if not mentions: 
        return MetricScoreRecord(metric_id="GEO-13-SNT-POL", metric_category="reputation_sentiment", score=50.0)
    avg_sentiment = sum(m.sentiment_score for m in mentions) / len(mentions)
    score = ((avg_sentiment + 1) / 2) * 100
    return _create_record("GEO-13-SNT-POL", "reputation_sentiment", score, {"avg_sentiment": avg_sentiment})

def compute_geo_14(competitors: List[CompetitorData], brand_name: str) -> MetricScoreRecord:
    """GEO-14: Competitive Position. Weight=0.10"""
    brand_comp = next((c for c in competitors if c.competitor_name == brand_name), None)
    if not brand_comp: 
        return MetricScoreRecord(metric_id="GEO-14-CMP-PST", metric_category="reputation_sentiment", score=0.0)
    
    num_comps = len(competitors)
    mention_order = 1 - (brand_comp.avg_mention_position - 1) / max(num_comps, 1)
    recommend_rate = brand_comp.recommendation_count / max(brand_comp.total_appearances, 1)
    
    adv = (brand_comp.positive_comparisons - brand_comp.negative_comparisons)
    total_comp = (brand_comp.positive_comparisons + brand_comp.negative_comparisons)
    comp_adv = (adv / max(total_comp, 1) + 1) / 2
    
    score = (0.4 * mention_order + 0.3 * recommend_rate + 0.3 * comp_adv) * 100
    return _create_record("GEO-14-CMP-PST", "reputation_sentiment", score, {"recommend_rate": recommend_rate})

def compute_geo_16(findings: List[HallucinationFinding], total_claims: int) -> MetricScoreRecord:
    """GEO-16: Hallucination Risk. Weight=0.08"""
    severity_weights = {"critical": 2.0, "major": 1.0, "minor": 0.5}
    weighted_incorrect = sum(severity_weights.get(f.severity, 1.0) for f in findings)
    
    hallucination_rate = weighted_incorrect / max(total_claims, 1)
    score = (1 - hallucination_rate) * 100 if total_claims > 0 else 100.0
    return _create_record("GEO-16-HAL-RSK", "reputation_sentiment", score, {"weighted_incorrect": weighted_incorrect})

def compute_geo_17(tech: Optional[TechnicalCheckData]) -> MetricScoreRecord:
    """GEO-17: Crawl Accessibility. Weight=0.06"""
    if not tech:
        return MetricScoreRecord(metric_id="GEO-17-CRW-ACC", metric_category="content_technical", score=0.0)
    crawlers = ["GPTBot", "ClaudeBot", "Bingbot", "Googlebot"]
    crawl_perm = len([c for c in crawlers if tech.crawler_permissions.get(c) == "allowed"]) / 4.0
    sitemap = 1.0 if tech.sitemap_valid else (0.5 if tech.sitemap_present else 0.0)
    accessibility = len([p for p in tech.sampled_pages if p.get("status") == 200]) / max(len(tech.sampled_pages), 1)
    
    score = (0.4 * crawl_perm + 0.3 * sitemap + 0.3 * accessibility) * 100
    return _create_record("GEO-17-CRW-ACC", "content_technical", score, {"accessibility": accessibility})

def _create_record(mid: str, cat: str, score: float, components: Dict[str, Any]) -> MetricScoreRecord:
    score = max(0.0, min(100.0, score))
    weight = METRIC_DEFINITIONS[mid]["weight"]
    return MetricScoreRecord(metric_id=mid, metric_category=cat, score=score, components=components, weight=weight)
