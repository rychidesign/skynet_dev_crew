export const METRIC_CATEGORIES = {
  entity_semantic: {
    id: 'entity_semantic',
    name: 'Entity and Semantic',
    weight: 0.33,
  },
  citations_trust: {
    id: 'citations_trust',
    name: 'Citations and Trust',
    weight: 0.27,
  },
  content_technical: {
    id: 'content_technical',
    name: 'Content and Technical',
    weight: 0.12,
  },
  reputation_sentiment: {
    id: 'reputation_sentiment',
    name: 'Reputation and Sentiment',
    weight: 0.28,
  },
} as const;

export const METRICS = [
  {
    id: 'GEO-01-ENT-SAL',
    name: 'Entity Salience',
    category: 'entity_semantic',
    weight: 0.15,
    isFree: true,
  },
  {
    id: 'GEO-03-ENT-CON',
    name: 'Entity Consistency',
    category: 'entity_semantic',
    weight: 0.08,
    isFree: false,
  },
  {
    id: 'GEO-04-TOP-AUTH',
    name: 'Topical Authority',
    category: 'entity_semantic',
    weight: 0.10,
    isFree: false,
  },
  {
    id: 'GEO-05-CIT-FRQ',
    name: 'Citation Frequency',
    category: 'citations_trust',
    weight: 0.15,
    isFree: false,
  },
  {
    id: 'GEO-07-RAG-INC',
    name: 'RAG Inclusion Rate',
    category: 'citations_trust',
    weight: 0.12,
    isFree: false,
  },
  {
    id: 'GEO-11-FRS-REC',
    name: 'Freshness and Recency',
    category: 'content_technical',
    weight: 0.06,
    isFree: false,
  },
  {
    id: 'GEO-17-CRW-ACC',
    name: 'Crawl Accessibility',
    category: 'content_technical',
    weight: 0.06,
    isFree: true,
  },
  {
    id: 'GEO-13-SNT-POL',
    name: 'Sentiment Polarity',
    category: 'reputation_sentiment',
    weight: 0.10,
    isFree: true,
  },
  {
    id: 'GEO-14-CMP-PST',
    name: 'Competitive Position',
    category: 'reputation_sentiment',
    weight: 0.10,
    isFree: false,
  },
  {
    id: 'GEO-16-HAL-RSK',
    name: 'Hallucination Risk',
    category: 'reputation_sentiment',
    weight: 0.08,
    isFree: false,
  },
] as const;

export const RATING_THRESHOLDS = [
  { max: 24, label: 'critical' },
  { max: 49, label: 'weak' },
  { max: 74, label: 'moderate' },
  { max: 89, label: 'strong' },
  { max: 100, label: 'excellent' },
] as const;
