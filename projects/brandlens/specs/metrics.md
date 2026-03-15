# GEO Metrics

## References
- Related: specs/audit-pipeline.md — which agent computes which metric
- Related: specs/data-model.md — audit_metric_scores table structure
- Related: specs/billing.md — which metrics available per plan
- Source: GEO_Metrics_Golden_Standard_v2.md (user-provided — full metric definitions)

## Scoring Model

Global GEO Score = sum of (CategoryWeight x sum of (NormalizedMetricWeight x MetricScore))
NormalizedMetricWeight = MetricWeight / sum(MetricWeights in Category)

### Category Weights

| Category | Weight | Metrics |
|---|---|---|
| Entity and Semantic | 0.33 | GEO-01, GEO-03, GEO-04 |
| Citations and Trust | 0.27 | GEO-05, GEO-07 |
| Content and Technical | 0.12 | GEO-11, GEO-17 |
| Reputation and Sentiment | 0.28 | GEO-13, GEO-14, GEO-16 |

### Rating Thresholds

| Range | Rating |
|---|---|
| 90–100 | excellent |
| 75–89 | strong |
| 50–74 | moderate |
| 25–49 | weak |
| 0–24 | critical |

## Metric Definitions

### GEO-01-ENT-SAL: Entity Salience (15%, Entity and Semantic)
How prominently AI recognizes the brand as the primary entity.
```
Score = (0.4 x TopMentionRate + 0.35 x EntityRankPosition + 0.25 x DisambiguationClarity) x 100
TopMentionRate = queries_where_brand_is_first / total_queries
EntityRankPosition = 1 - (avg_rank - 1) / max_rank
DisambiguationClarity = 1 - (confusion_instances / total_mentions)
```
Data: Agent 2 (responses) + Agent 3 (mentions). **Free plan: available.**

### GEO-03-ENT-CON: Entity Consistency (8%, Entity and Semantic)
Whether brand is described consistently across AI platforms.
```
Score = (1 - InconsistencyRate) x 100
InconsistencyRate = conflicting_attributes / total_attributes_checked
```
Attributes checked: name, founding date, category, key products, leadership, location.
Data: Agent 2 cross-platform comparison. **Pro+ only.**

### GEO-04-TOP-AUTH: Topical Authority (10%, Entity and Semantic)
How deeply AI perceives the brand as a domain authority.
```
Score = (0.35 x AuthorityCiteRate + 0.35 x ExpertLanguageRate + 0.3 x ExclusiveInsightRate) x 100
AuthorityCiteRate = times_cited_as_authority / total_topic_mentions
ExpertLanguageRate = frequency of markers ("leading", "expert", "trusted")
ExclusiveInsightRate = unique_claims_attributed_only_to_brand / total_claims
```
Data: Agent 3 authority language detection. **Pro+ only.**

### GEO-05-CIT-FRQ: Citation Frequency (15%, Citations and Trust)
How often brand content is cited in AI responses.
```
Score = min(100, (TotalCitations / BenchmarkCitations) x 100)
TotalCitations = direct_urls + domain_mentions + author_attributions
BenchmarkCitations = avg citations of top 3 competitors
```
Normalized per 100 queries. Data: Agent 2 + Agent 3. **Pro+ only.**

### GEO-07-RAG-INC: RAG Inclusion Rate (12%, Citations and Trust)
How often brand content appears in RAG retrieval results.
```
Score = (BrandRAGHits / TotalRAGResults) x 100 x RelevancyMultiplier
RelevancyMultiplier = avg(relevancy_score) where 0 < score <= 1.2
```
Data: Agent 2 Perplexity source extraction. **Pro+ only.**

### GEO-11-FRS-REC: Freshness and Recency (6%, Content and Technical)
How current the brand's content is.
```
Score = (0.4 x PublicationRecency + 0.3 x UpdateFrequency + 0.3 x TemporalRelevance) x 100
PublicationRecency = avg(1 / days_since_publication) normalized
UpdateFrequency = updates_per_month / benchmark_frequency
TemporalRelevance = pct of content with current-year references
```
Data: Preprocessor (sitemap lastmod dates). **Pro+ only.**

### GEO-17-CRW-ACC: Crawl Accessibility (6%, Content and Technical)
How easily AI crawlers can access brand content.
```
Score = (0.4 x CrawlPermission + 0.3 x SitemapPresence + 0.3 x BasicAccessibility) x 100
CrawlPermission = pct of AI crawlers allowed (GPTBot, ClaudeBot, Bingbot, Googlebot)
SitemapPresence = 1 if valid, 0.5 if partial, 0 if missing
BasicAccessibility = pct of sampled pages returning 200 OK
```
Data: Preprocessor (robots.txt + sitemap). **Free plan: available.**

### GEO-13-SNT-POL: Sentiment Polarity (10%, Reputation and Sentiment)
Emotional tone AI adopts when describing the brand.
```
Score = ((AvgSentiment + 1) / 2) x 100
AvgSentiment = mean(sentiment_scores) across all responses, range [-1, 1]
```
Recent responses weighted 2x. Data: Agent 3 sentiment classification. **Free plan: available.**

### GEO-14-CMP-PST: Competitive Position (10%, Reputation and Sentiment)
Brand ranking relative to competitors in AI responses.
```
Score = (0.4 x MentionOrder + 0.3 x RecommendationRate + 0.3 x ComparativeAdvantage) x 100
MentionOrder = 1 - (avg_position - 1) / num_competitors
RecommendationRate = times_recommended_first / comparison_queries
ComparativeAdvantage = (positive - negative) / total_comparisons
```
Data: Agent 4 (competitor mapper). **Pro+ only.**

### GEO-16-HAL-RSK: Hallucination Risk (8%, Reputation and Sentiment)
How often AI generates incorrect facts about the brand.
```
Score = (1 - HallucinationRate) x 100
HallucinationRate = factually_incorrect_claims / total_claims
```
Severity weighted: critical x2, minor x0.5. Cross-referenced against companies.facts.
Data: Agent 5 fact-check. **Pro+ only.**

## Free Plan Metric Availability

Free plan computes and returns: GEO-01, GEO-13, GEO-17 + Global GEO Score.
Backend still computes all 10 internally (needed for accurate Global Score), but API response omits locked metric details. Frontend shows locked cards with blurred preview.

## Agent-to-Metric Mapping

| Agent | Metrics |
|---|---|
| Preprocessor | GEO-17, GEO-11 |
| Agent 2 (Response Collector) | GEO-01, GEO-03, GEO-05, GEO-07 |
| Agent 3 (Mention Analyzer) | GEO-01, GEO-04, GEO-05, GEO-13 |
| Agent 4 (Competitor Mapper) | GEO-14 |
| Agent 5 (Synthesizer) | GEO-16, Global Score (all 10) |
