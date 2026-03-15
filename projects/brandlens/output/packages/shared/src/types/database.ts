export type AuditStatus = 'pending' | 'preprocessing' | 'generating' | 'collecting' | 'analyzing' | 'synthesizing' | 'completed' | 'failed' | 'cancelled';
export type AiPlatform = 'chatgpt' | 'claude' | 'perplexity' | 'google_aio' | 'copilot';
export type MetricCategory = 'entity_semantic' | 'citations_trust' | 'content_technical' | 'reputation_sentiment';
export type EventSeverity = 'debug' | 'info' | 'warning' | 'error' | 'critical';
export type QueryIntent = 'informational' | 'comparative' | 'navigational' | 'recommendation' | 'authority' | 'factual';
export type MentionType = 'primary' | 'secondary' | 'citation' | 'comparison' | 'recommendation' | 'absent';
export type OrgRole = 'owner' | 'admin' | 'analyst' | 'viewer';

export interface Organization {
  id: string;
  name: string;
  slug: string;
  plan: 'free' | 'pro' | 'enterprise';
  settings: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
}

export interface OrganizationMember {
  id: string;
  organizationId: string;
  userId: string;
  role: OrgRole;
  invitedAt: string;
  acceptedAt: string | null;
}

export interface Company {
  id: string;
  organizationId: string;
  name: string;
  domain: string | null;
  industry: string | null;
  description: string | null;
  facts: Record<string, unknown>;
  competitors: string[];
  coreTopics: string[];
  createdAt: string;
  updatedAt: string;
}

export interface Subscription {
  id: string;
  organizationId: string;
  paddleSubscriptionId: string | null;
  paddleCustomerId: string | null;
  status: 'active' | 'past_due' | 'cancelled' | 'trialing' | 'paused';
  plan: 'free' | 'pro' | 'enterprise';
  currentPeriodStart: string | null;
  currentPeriodEnd: string | null;
  cancelAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface UsageTracking {
  id: string;
  organizationId: string;
  periodStart: string;
  auditsUsed: number;
}

export interface Audit {
  id: string;
  organizationId: string;
  companyId: string;
  triggeredBy: string | null;
  status: AuditStatus;
  config: Record<string, unknown>;
  startedAt: string | null;
  completedAt: string | null;
  durationMs: number | null;
  totalInputTokens: number;
  totalOutputTokens: number;
  totalCostUsd: number;
  globalGeoScore: number | null;
  scoreBreakdown: Record<string, unknown> | null;
  errorMessage: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface AuditQuery {
  id: string;
  auditId: string;
  queryText: string;
  intent: QueryIntent | null;
  targetMetrics: string[];
  queryIndex: number;
  createdAt: string;
}

export interface AuditResponse {
  id: string;
  auditId: string;
  queryId: string;
  platform: AiPlatform;
  modelId: string | null;
  responseText: string;
  citations: Record<string, unknown>[];
  ragSources: Record<string, unknown>[];
  inputTokens: number | null;
  outputTokens: number | null;
  costUsd: number | null;
  latencyMs: number | null;
  servedFromCache: boolean;
  cacheKey: string | null;
  idempotencyKey: string;
  createdAt: string;
}

export interface AuditMention {
  id: string;
  auditId: string;
  responseId: string;
  entityName: string;
  mentionType: MentionType | null;
  positionRank: number | null;
  sentimentScore: number | null;
  sentimentLabel: 'positive' | 'negative' | 'neutral' | null;
  authorityMarkers: string[];
  isAuthorityCite: boolean;
  extractedAttributes: Record<string, unknown>;
  isConfused: boolean;
  confusionNote: string | null;
  createdAt: string;
}

export interface AuditCompetitor {
  id: string;
  auditId: string;
  competitorName: string;
  competitorDomain: string | null;
  avgMentionPosition: number | null;
  recommendationCount: number;
  totalAppearances: number;
  positiveComparisons: number;
  negativeComparisons: number;
  neutralComparisons: number;
  platformBreakdown: Record<string, unknown>;
  createdAt: string;
}

export interface AuditMetricScore {
  id: string;
  auditId: string;
  metricId: string;
  metricCategory: MetricCategory | null;
  score: number | null;
  components: Record<string, unknown>;
  weight: number | null;
  weightedContribution: number | null;
  platformScores: Record<string, unknown>;
  evidenceSummary: string | null;
  createdAt: string;
}

export interface AuditRecommendation {
  id: string;
  auditId: string;
  priority: 'P0' | 'P1' | 'P2' | 'P3' | null;
  targetMetric: string | null;
  title: string;
  description: string;
  actionItems: Record<string, unknown>[];
  estimatedImpact: string | null;
  effortLevel: 'low' | 'medium' | 'high' | null;
  createdAt: string;
}

export interface AuditHallucination {
  id: string;
  auditId: string;
  responseId: string;
  claimText: string;
  factField: string;
  expectedValue: string | null;
  actualValue: string | null;
  severity: 'critical' | 'major' | 'minor' | null;
  platform: AiPlatform | null;
  createdAt: string;
}

export interface AuditTechnicalCheck {
  id: string;
  auditId: string;
  robotsTxtRaw: string | null;
  crawlerPermissions: Record<string, unknown>;
  sitemapPresent: boolean | null;
  sitemapValid: boolean | null;
  sitemapUrlCount: number | null;
  sampledPages: Record<string, unknown>[];
  avgLastmodDays: number | null;
  updateFrequencyMonthly: number | null;
  currentYearContentPct: number | null;
  sitemapSample: Record<string, unknown>[];
  createdAt: string;
}

export interface AuditEvent {
  id: string;
  auditId: string;
  agent: string;
  eventType: string;
  severity: EventSeverity;
  message: string;
  metadata: Record<string, unknown>;
  progress: number | null;
  createdAt: string;
}

export interface MetricTimeSeries {
  id: string;
  companyId: string;
  auditId: string;
  snapshotDate: string | null;
  globalGeoScore: number | null;
  entSalScore: number | null;
  entConScore: number | null;
  topAuthScore: number | null;
  citFrqScore: number | null;
  ragIncScore: number | null;
  frsRecScore: number | null;
  crwAccScore: number | null;
  sntPolScore: number | null;
  cmpPstScore: number | null;
  halRskScore: number | null;
  categoryEntitySemantic: number | null;
  categoryCitationsTrust: number | null;
  categoryContentTechnical: number | null;
  categoryReputationSentiment: number | null;
  platformScores: Record<string, unknown>;
  createdAt: string;
}
