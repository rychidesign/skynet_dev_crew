import { AiPlatform } from '../types/database';

export interface PlanLimits {
  maxAuditsPerMonth: number;
  maxQueriesPerAudit: number;
  allowedPlatforms: AiPlatform[];
  metricsAvailable: string[];
  competitorAnalysis: boolean;
  maxCompetitors: number;
  trendHistoryMonths: number;
  maxTeamMembers: number;
  recommendationsLevel: 'score_only' | 'full' | 'full_export';
}

const allMetrics = [
  'GEO-01-ENT-SAL',
  'GEO-03-ENT-CON',
  'GEO-04-TOP-AUTH',
  'GEO-05-CIT-FRQ',
  'GEO-07-RAG-INC',
  'GEO-11-FRS-REC',
  'GEO-17-CRW-ACC',
  'GEO-13-SNT-POL',
  'GEO-14-CMP-PST',
  'GEO-16-HAL-RSK',
];

export const PLAN_LIMITS: Record<'free' | 'pro' | 'enterprise', PlanLimits> = {
  free: {
    maxAuditsPerMonth: 1,
    maxQueriesPerAudit: 10,
    allowedPlatforms: ['chatgpt', 'perplexity'],
    metricsAvailable: ['GEO-01-ENT-SAL', 'GEO-13-SNT-POL', 'GEO-17-CRW-ACC'],
    competitorAnalysis: false,
    maxCompetitors: 0,
    trendHistoryMonths: 0,
    maxTeamMembers: 1,
    recommendationsLevel: 'score_only',
  },
  pro: {
    maxAuditsPerMonth: 20,
    maxQueriesPerAudit: 50,
    allowedPlatforms: ['chatgpt', 'claude', 'perplexity', 'google_aio', 'copilot'],
    metricsAvailable: allMetrics,
    competitorAnalysis: true,
    maxCompetitors: 5,
    trendHistoryMonths: 12,
    maxTeamMembers: 5,
    recommendationsLevel: 'full',
  },
  enterprise: {
    maxAuditsPerMonth: 100,
    maxQueriesPerAudit: 200,
    allowedPlatforms: ['chatgpt', 'claude', 'perplexity', 'google_aio', 'copilot'],
    metricsAvailable: allMetrics,
    competitorAnalysis: true,
    maxCompetitors: 999,
    trendHistoryMonths: 999,
    maxTeamMembers: 999,
    recommendationsLevel: 'full_export',
  },
} as const;
