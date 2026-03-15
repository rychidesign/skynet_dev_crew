-- =============================================================================
-- BrandLens Database Schema - Migration 001
-- Core tables, enums, indexes, triggers, and RLS policies
-- =============================================================================

-- =============================================================================
-- EXTENSIONS
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- ENUM TYPES
-- =============================================================================

CREATE TYPE audit_status AS ENUM (
    'pending',
    'preprocessing',
    'generating',
    'collecting',
    'analyzing',
    'synthesizing',
    'completed',
    'failed',
    'cancelled'
);

CREATE TYPE ai_platform AS ENUM (
    'chatgpt',
    'claude',
    'perplexity',
    'google_aio',
    'copilot'
);

CREATE TYPE metric_category AS ENUM (
    'entity_semantic',
    'citations_trust',
    'content_technical',
    'reputation_sentiment'
);

CREATE TYPE event_severity AS ENUM (
    'debug',
    'info',
    'warning',
    'error',
    'critical'
);

CREATE TYPE query_intent AS ENUM (
    'informational',
    'comparative',
    'navigational',
    'recommendation',
    'authority',
    'factual'
);

CREATE TYPE mention_type AS ENUM (
    'primary',
    'secondary',
    'citation',
    'comparison',
    'recommendation',
    'absent'
);

CREATE TYPE org_role AS ENUM (
    'owner',
    'admin',
    'analyst',
    'viewer'
);

-- =============================================================================
-- TABLES
-- =============================================================================

-- -----------------------------------------------------------------------------
-- organizations: Multi-tenant root entity
-- -----------------------------------------------------------------------------

CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    plan TEXT NOT NULL DEFAULT 'free' CHECK (plan IN ('free', 'pro', 'enterprise')),
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- organization_members: Join table users <-> organizations
-- -----------------------------------------------------------------------------

CREATE TABLE organization_members (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    role org_role DEFAULT 'viewer',
    invited_at TIMESTAMPTZ,
    accepted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (organization_id, user_id)
);

-- -----------------------------------------------------------------------------
-- companies: Brands being audited
-- -----------------------------------------------------------------------------

CREATE TABLE companies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    domain TEXT,
    industry TEXT,
    description TEXT,
    facts JSONB DEFAULT '{}',
    competitors TEXT[] DEFAULT '{}',
    core_topics TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- audits: Top-level audit run record
-- -----------------------------------------------------------------------------

CREATE TABLE audits (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    triggered_by UUID,
    status audit_status DEFAULT 'pending',
    config JSONB DEFAULT '{}',
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER,
    total_input_tokens INTEGER DEFAULT 0,
    total_output_tokens INTEGER DEFAULT 0,
    total_cost_usd NUMERIC(10,6) DEFAULT 0,
    global_geo_score NUMERIC(5,2),
    score_breakdown JSONB,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- audit_queries: Agent 1 output
-- -----------------------------------------------------------------------------

CREATE TABLE audit_queries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    audit_id UUID NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
    query_text TEXT NOT NULL,
    intent query_intent,
    target_metrics TEXT[] DEFAULT '{}',
    query_index SMALLINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (audit_id, query_index)
);

-- -----------------------------------------------------------------------------
-- audit_responses: Agent 2 output
-- -----------------------------------------------------------------------------

CREATE TABLE audit_responses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    audit_id UUID NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
    query_id UUID NOT NULL REFERENCES audit_queries(id) ON DELETE CASCADE,
    platform ai_platform,
    model_id TEXT,
    response_text TEXT NOT NULL,
    citations JSONB DEFAULT '[]',
    rag_sources JSONB DEFAULT '[]',
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd NUMERIC(10,6),
    latency_ms INTEGER,
    served_from_cache BOOLEAN DEFAULT FALSE,
    cache_key TEXT,
    idempotency_key TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- audit_mentions: Agent 3 output
-- -----------------------------------------------------------------------------

CREATE TABLE audit_mentions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    audit_id UUID NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
    response_id UUID NOT NULL REFERENCES audit_responses(id) ON DELETE CASCADE,
    entity_name TEXT NOT NULL,
    mention_type mention_type,
    position_rank SMALLINT,
    sentiment_score NUMERIC(4,3),
    sentiment_label TEXT,
    authority_markers TEXT[] DEFAULT '{}',
    is_authority_cite BOOLEAN DEFAULT FALSE,
    extracted_attributes JSONB DEFAULT '{}',
    is_confused BOOLEAN DEFAULT FALSE,
    confusion_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- audit_competitors: Agent 4 output
-- -----------------------------------------------------------------------------

CREATE TABLE audit_competitors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    audit_id UUID NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
    competitor_name TEXT NOT NULL,
    competitor_domain TEXT,
    avg_mention_position NUMERIC(4,2),
    recommendation_count INTEGER DEFAULT 0,
    total_appearances INTEGER DEFAULT 0,
    positive_comparisons INTEGER DEFAULT 0,
    negative_comparisons INTEGER DEFAULT 0,
    neutral_comparisons INTEGER DEFAULT 0,
    platform_breakdown JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- audit_metric_scores: Agent 5 output
-- -----------------------------------------------------------------------------

CREATE TABLE audit_metric_scores (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    audit_id UUID NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
    metric_id TEXT NOT NULL,
    metric_category metric_category,
    score NUMERIC(5,2),
    components JSONB DEFAULT '{}',
    weight NUMERIC(4,3),
    weighted_contribution NUMERIC(5,2),
    platform_scores JSONB DEFAULT '{}',
    evidence_summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (audit_id, metric_id)
);

-- -----------------------------------------------------------------------------
-- audit_recommendations: Agent 5 output
-- -----------------------------------------------------------------------------

CREATE TABLE audit_recommendations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    audit_id UUID NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
    priority TEXT CHECK (priority IN ('P0', 'P1', 'P2', 'P3')),
    target_metric TEXT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    action_items JSONB DEFAULT '[]',
    estimated_impact TEXT,
    effort_level TEXT CHECK (effort_level IN ('low', 'medium', 'high')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- audit_hallucinations: Agent 5 output
-- -----------------------------------------------------------------------------

CREATE TABLE audit_hallucinations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    audit_id UUID NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
    response_id UUID NOT NULL REFERENCES audit_responses(id) ON DELETE CASCADE,
    claim_text TEXT NOT NULL,
    fact_field TEXT NOT NULL,
    expected_value TEXT,
    actual_value TEXT,
    severity TEXT CHECK (severity IN ('critical', 'major', 'minor')),
    platform ai_platform,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- audit_technical_checks: Preprocessor output
-- -----------------------------------------------------------------------------

CREATE TABLE audit_technical_checks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    audit_id UUID UNIQUE NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
    robots_txt_raw TEXT,
    crawler_permissions JSONB DEFAULT '{}',
    sitemap_present BOOLEAN,
    sitemap_valid BOOLEAN,
    sitemap_url_count INTEGER,
    sampled_pages JSONB DEFAULT '[]',
    avg_lastmod_days NUMERIC(8,2),
    update_frequency_monthly NUMERIC(6,2),
    current_year_content_pct NUMERIC(5,2),
    sitemap_sample JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- audit_events: Observability log
-- -----------------------------------------------------------------------------

CREATE TABLE audit_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    audit_id UUID NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
    agent TEXT NOT NULL,
    event_type TEXT NOT NULL,
    severity event_severity DEFAULT 'info',
    message TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    progress NUMERIC(4,3),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- metric_time_series: Denormalized trend snapshots
-- -----------------------------------------------------------------------------

CREATE TABLE metric_time_series (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    audit_id UUID UNIQUE REFERENCES audits(id) ON DELETE CASCADE,
    snapshot_date DATE NOT NULL,
    global_geo_score NUMERIC(5,2),
    -- Entity and Semantic metrics
    ent_sal_score NUMERIC(5,2),
    ent_con_score NUMERIC(5,2),
    top_auth_score NUMERIC(5,2),
    -- Citations and Trust metrics
    cit_frq_score NUMERIC(5,2),
    rag_inc_score NUMERIC(5,2),
    -- Content and Technical metrics
    frs_rec_score NUMERIC(5,2),
    crw_acc_score NUMERIC(5,2),
    -- Reputation and Sentiment metrics
    snt_pol_score NUMERIC(5,2),
    cmp_pst_score NUMERIC(5,2),
    hal_rsk_score NUMERIC(5,2),
    -- Category averages
    category_entity_semantic NUMERIC(5,2),
    category_citations_trust NUMERIC(5,2),
    category_content_technical NUMERIC(5,2),
    category_reputation_sentiment NUMERIC(5,2),
    -- Platform breakdown
    platform_scores JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- INDEXES
-- =============================================================================

-- Dashboard: latest audits per company
CREATE INDEX idx_audits_company_created ON audits(company_id, created_at DESC);

-- Trend charts
CREATE INDEX idx_timeseries_company_date ON metric_time_series(company_id, snapshot_date DESC);

-- Metric evolution over time
CREATE INDEX idx_metric_scores_trend ON audit_metric_scores(audit_id, metric_id);

-- Event log queries
CREATE INDEX idx_audit_events_audit_time ON audit_events(audit_id, created_at DESC);

-- Partial index for error/critical events only
CREATE INDEX idx_audit_events_severity ON audit_events(audit_id, severity) 
    WHERE severity IN ('error', 'critical');

-- Cache lookups (for responses not served from cache)
CREATE INDEX idx_audit_responses_cache ON audit_responses(cache_key) 
    WHERE served_from_cache = FALSE;

-- Organization lookup by slug
CREATE INDEX idx_organizations_slug ON organizations(slug);

-- Company lookup by organization
CREATE INDEX idx_companies_organization ON companies(organization_id);

-- Audit queries by audit
CREATE INDEX idx_audit_queries_audit ON audit_queries(audit_id);

-- Audit responses by audit and query
CREATE INDEX idx_audit_responses_audit ON audit_responses(audit_id);
CREATE INDEX idx_audit_responses_query ON audit_responses(query_id);

-- Audit mentions by response
CREATE INDEX idx_audit_mentions_response ON audit_mentions(response_id);
CREATE INDEX idx_audit_mentions_audit ON audit_mentions(audit_id);

-- Audit competitors by audit
CREATE INDEX idx_audit_competitors_audit ON audit_competitors(audit_id);

-- Audit metric scores by audit
CREATE INDEX idx_audit_metric_scores_audit ON audit_metric_scores(audit_id);

-- Audit recommendations by audit
CREATE INDEX idx_audit_recommendations_audit ON audit_recommendations(audit_id);

-- Audit hallucinations by response
CREATE INDEX idx_audit_hallucinations_response ON audit_hallucinations(response_id);
CREATE INDEX idx_audit_hallucinations_audit ON audit_hallucinations(audit_id);

-- Organization members by user
CREATE INDEX idx_organization_members_user ON organization_members(user_id);

-- =============================================================================
-- FUNCTIONS AND TRIGGERS
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Auto-update updated_at column
-- -----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to organizations
CREATE TRIGGER update_organizations_updated_at
    BEFORE UPDATE ON organizations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Apply to companies
CREATE TRIGGER update_companies_updated_at
    BEFORE UPDATE ON companies
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Apply to audits
CREATE TRIGGER update_audits_updated_at
    BEFORE UPDATE ON audits
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- -----------------------------------------------------------------------------
-- Populate time series when audit completes
-- -----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION populate_time_series()
RETURNS TRIGGER AS $$
DECLARE
    v_company_id UUID;
    v_ent_sal NUMERIC(5,2);
    v_ent_con NUMERIC(5,2);
    v_top_auth NUMERIC(5,2);
    v_cit_frq NUMERIC(5,2);
    v_rag_inc NUMERIC(5,2);
    v_frs_rec NUMERIC(5,2);
    v_crw_acc NUMERIC(5,2);
    v_snt_pol NUMERIC(5,2);
    v_cmp_pst NUMERIC(5,2);
    v_hal_rsk NUMERIC(5,2);
    v_cat_ent_sem NUMERIC(5,2);
    v_cat_cit_trust NUMERIC(5,2);
    v_cat_con_tech NUMERIC(5,2);
    v_cat_rep_snt NUMERIC(5,2);
BEGIN
    -- Only trigger when status changes to 'completed'
    IF NEW.status = 'completed' AND OLD.status != 'completed' THEN
        -- Get company_id from audit
        v_company_id := NEW.company_id;
        
        -- Get individual metric scores
        SELECT score INTO v_ent_sal FROM audit_metric_scores 
            WHERE audit_id = NEW.id AND metric_id = 'GEO-01-ENT-SAL';
        SELECT score INTO v_ent_con FROM audit_metric_scores 
            WHERE audit_id = NEW.id AND metric_id = 'GEO-03-ENT-CON';
        SELECT score INTO v_top_auth FROM audit_metric_scores 
            WHERE audit_id = NEW.id AND metric_id = 'GEO-04-TOP-AUTH';
        SELECT score INTO v_cit_frq FROM audit_metric_scores 
            WHERE audit_id = NEW.id AND metric_id = 'GEO-05-CIT-FRQ';
        SELECT score INTO v_rag_inc FROM audit_metric_scores 
            WHERE audit_id = NEW.id AND metric_id = 'GEO-07-RAG-INC';
        SELECT score INTO v_frs_rec FROM audit_metric_scores 
            WHERE audit_id = NEW.id AND metric_id = 'GEO-11-FRS-REC';
        SELECT score INTO v_crw_acc FROM audit_metric_scores 
            WHERE audit_id = NEW.id AND metric_id = 'GEO-17-CRW-ACC';
        SELECT score INTO v_snt_pol FROM audit_metric_scores 
            WHERE audit_id = NEW.id AND metric_id = 'GEO-13-SNT-POL';
        SELECT score INTO v_cmp_pst FROM audit_metric_scores 
            WHERE audit_id = NEW.id AND metric_id = 'GEO-14-CMP-PST';
        SELECT score INTO v_hal_rsk FROM audit_metric_scores 
            WHERE audit_id = NEW.id AND metric_id = 'GEO-16-HAL-RSK';
        
        -- Calculate category averages
        SELECT AVG(score) INTO v_cat_ent_sem FROM audit_metric_scores 
            WHERE audit_id = NEW.id AND metric_category = 'entity_semantic';
        SELECT AVG(score) INTO v_cat_cit_trust FROM audit_metric_scores 
            WHERE audit_id = NEW.id AND metric_category = 'citations_trust';
        SELECT AVG(score) INTO v_cat_con_tech FROM audit_metric_scores 
            WHERE audit_id = NEW.id AND metric_category = 'content_technical';
        SELECT AVG(score) INTO v_cat_rep_snt FROM audit_metric_scores 
            WHERE audit_id = NEW.id AND metric_category = 'reputation_sentiment';
        
        -- Insert into time series
        INSERT INTO metric_time_series (
            company_id,
            audit_id,
            snapshot_date,
            global_geo_score,
            ent_sal_score,
            ent_con_score,
            top_auth_score,
            cit_frq_score,
            rag_inc_score,
            frs_rec_score,
            crw_acc_score,
            snt_pol_score,
            cmp_pst_score,
            hal_rsk_score,
            category_entity_semantic,
            category_citations_trust,
            category_content_technical,
            category_reputation_sentiment
        ) VALUES (
            v_company_id,
            NEW.id,
            CURRENT_DATE,
            NEW.global_geo_score,
            v_ent_sal,
            v_ent_con,
            v_top_auth,
            v_cit_frq,
            v_rag_inc,
            v_frs_rec,
            v_crw_acc,
            v_snt_pol,
            v_cmp_pst,
            v_hal_rsk,
            v_cat_ent_sem,
            v_cat_cit_trust,
            v_cat_con_tech,
            v_cat_rep_snt
        );
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to audits table
CREATE TRIGGER trigger_populate_time_series
    AFTER UPDATE ON audits
    FOR EACH ROW
    EXECUTE FUNCTION populate_time_series();

-- =============================================================================
-- ROW LEVEL SECURITY (RLS)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- RLS Helper Functions
-- -----------------------------------------------------------------------------

-- Check if current user is a member of the given organization
CREATE OR REPLACE FUNCTION user_in_org(org_id UUID)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM organization_members
        WHERE organization_id = org_id
        AND user_id = auth.uid()
        AND accepted_at IS NOT NULL
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER STABLE;

-- Check if current user has access to an audit (via organization membership)
CREATE OR REPLACE FUNCTION audit_org_check(audit_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    v_org_id UUID;
BEGIN
    SELECT organization_id INTO v_org_id FROM audits WHERE id = audit_id;
    IF v_org_id IS NULL THEN
        RETURN FALSE;
    END IF;
    RETURN user_in_org(v_org_id);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER STABLE;

-- -----------------------------------------------------------------------------
-- Enable RLS on all tables
-- -----------------------------------------------------------------------------

ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE audits ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_queries ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_responses ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_mentions ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_competitors ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_metric_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_recommendations ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_hallucinations ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_technical_checks ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE metric_time_series ENABLE ROW LEVEL SECURITY;

-- -----------------------------------------------------------------------------
-- RLS Policies for organizations
-- -----------------------------------------------------------------------------

CREATE POLICY org_select ON organizations
    FOR SELECT USING (user_in_org(id));

CREATE POLICY org_insert ON organizations
    FOR INSERT WITH CHECK (true);  -- Allow creation, membership added separately

CREATE POLICY org_update ON organizations
    FOR UPDATE USING (user_in_org(id));

CREATE POLICY org_delete ON organizations
    FOR DELETE USING (user_in_org(id));

-- -----------------------------------------------------------------------------
-- RLS Policies for organization_members
-- -----------------------------------------------------------------------------

CREATE POLICY org_members_select ON organization_members
    FOR SELECT USING (user_in_org(organization_id));

CREATE POLICY org_members_insert ON organization_members
    FOR INSERT WITH CHECK (user_in_org(organization_id));

CREATE POLICY org_members_update ON organization_members
    FOR UPDATE USING (user_in_org(organization_id));

CREATE POLICY org_members_delete ON organization_members
    FOR DELETE USING (user_in_org(organization_id));

-- -----------------------------------------------------------------------------
-- RLS Policies for companies
-- -----------------------------------------------------------------------------

CREATE POLICY companies_select ON companies
    FOR SELECT USING (user_in_org(organization_id));

CREATE POLICY companies_insert ON companies
    FOR INSERT WITH CHECK (user_in_org(organization_id));

CREATE POLICY companies_update ON companies
    FOR UPDATE USING (user_in_org(organization_id));

CREATE POLICY companies_delete ON companies
    FOR DELETE USING (user_in_org(organization_id));

-- -----------------------------------------------------------------------------
-- RLS Policies for audits
-- -----------------------------------------------------------------------------

CREATE POLICY audits_select ON audits
    FOR SELECT USING (user_in_org(organization_id));

CREATE POLICY audits_insert ON audits
    FOR INSERT WITH CHECK (user_in_org(organization_id));

CREATE POLICY audits_update ON audits
    FOR UPDATE USING (user_in_org(organization_id));

CREATE POLICY audits_delete ON audits
    FOR DELETE USING (user_in_org(organization_id));

-- -----------------------------------------------------------------------------
-- RLS Policies for audit_queries
-- -----------------------------------------------------------------------------

CREATE POLICY audit_queries_select ON audit_queries
    FOR SELECT USING (audit_org_check(audit_id));

CREATE POLICY audit_queries_insert ON audit_queries
    FOR INSERT WITH CHECK (audit_org_check(audit_id));

CREATE POLICY audit_queries_update ON audit_queries
    FOR UPDATE USING (audit_org_check(audit_id));

CREATE POLICY audit_queries_delete ON audit_queries
    FOR DELETE USING (audit_org_check(audit_id));

-- -----------------------------------------------------------------------------
-- RLS Policies for audit_responses
-- -----------------------------------------------------------------------------

CREATE POLICY audit_responses_select ON audit_responses
    FOR SELECT USING (audit_org_check(audit_id));

CREATE POLICY audit_responses_insert ON audit_responses
    FOR INSERT WITH CHECK (audit_org_check(audit_id));

CREATE POLICY audit_responses_update ON audit_responses
    FOR UPDATE USING (audit_org_check(audit_id));

CREATE POLICY audit_responses_delete ON audit_responses
    FOR DELETE USING (audit_org_check(audit_id));

-- -----------------------------------------------------------------------------
-- RLS Policies for audit_mentions
-- -----------------------------------------------------------------------------

CREATE POLICY audit_mentions_select ON audit_mentions
    FOR SELECT USING (audit_org_check(audit_id));

CREATE POLICY audit_mentions_insert ON audit_mentions
    FOR INSERT WITH CHECK (audit_org_check(audit_id));

CREATE POLICY audit_mentions_update ON audit_mentions
    FOR UPDATE USING (audit_org_check(audit_id));

CREATE POLICY audit_mentions_delete ON audit_mentions
    FOR DELETE USING (audit_org_check(audit_id));

-- -----------------------------------------------------------------------------
-- RLS Policies for audit_competitors
-- -----------------------------------------------------------------------------

CREATE POLICY audit_competitors_select ON audit_competitors
    FOR SELECT USING (audit_org_check(audit_id));

CREATE POLICY audit_competitors_insert ON audit_competitors
    FOR INSERT WITH CHECK (audit_org_check(audit_id));

CREATE POLICY audit_competitors_update ON audit_competitors
    FOR UPDATE USING (audit_org_check(audit_id));

CREATE POLICY audit_competitors_delete ON audit_competitors
    FOR DELETE USING (audit_org_check(audit_id));

-- -----------------------------------------------------------------------------
-- RLS Policies for audit_metric_scores
-- -----------------------------------------------------------------------------

CREATE POLICY audit_metric_scores_select ON audit_metric_scores
    FOR SELECT USING (audit_org_check(audit_id));

CREATE POLICY audit_metric_scores_insert ON audit_metric_scores
    FOR INSERT WITH CHECK (audit_org_check(audit_id));

CREATE POLICY audit_metric_scores_update ON audit_metric_scores
    FOR UPDATE USING (audit_org_check(audit_id));

CREATE POLICY audit_metric_scores_delete ON audit_metric_scores
    FOR DELETE USING (audit_org_check(audit_id));

-- -----------------------------------------------------------------------------
-- RLS Policies for audit_recommendations
-- -----------------------------------------------------------------------------

CREATE POLICY audit_recommendations_select ON audit_recommendations
    FOR SELECT USING (audit_org_check(audit_id));

CREATE POLICY audit_recommendations_insert ON audit_recommendations
    FOR INSERT WITH CHECK (audit_org_check(audit_id));

CREATE POLICY audit_recommendations_update ON audit_recommendations
    FOR UPDATE USING (audit_org_check(audit_id));

CREATE POLICY audit_recommendations_delete ON audit_recommendations
    FOR DELETE USING (audit_org_check(audit_id));

-- -----------------------------------------------------------------------------
-- RLS Policies for audit_hallucinations
-- -----------------------------------------------------------------------------

CREATE POLICY audit_hallucinations_select ON audit_hallucinations
    FOR SELECT USING (audit_org_check(audit_id));

CREATE POLICY audit_hallucinations_insert ON audit_hallucinations
    FOR INSERT WITH CHECK (audit_org_check(audit_id));

CREATE POLICY audit_hallucinations_update ON audit_hallucinations
    FOR UPDATE USING (audit_org_check(audit_id));

CREATE POLICY audit_hallucinations_delete ON audit_hallucinations
    FOR DELETE USING (audit_org_check(audit_id));

-- -----------------------------------------------------------------------------
-- RLS Policies for audit_technical_checks
-- -----------------------------------------------------------------------------

CREATE POLICY audit_technical_checks_select ON audit_technical_checks
    FOR SELECT USING (audit_org_check(audit_id));

CREATE POLICY audit_technical_checks_insert ON audit_technical_checks
    FOR INSERT WITH CHECK (audit_org_check(audit_id));

CREATE POLICY audit_technical_checks_update ON audit_technical_checks
    FOR UPDATE USING (audit_org_check(audit_id));

CREATE POLICY audit_technical_checks_delete ON audit_technical_checks
    FOR DELETE USING (audit_org_check(audit_id));

-- -----------------------------------------------------------------------------
-- RLS Policies for audit_events
-- -----------------------------------------------------------------------------

CREATE POLICY audit_events_select ON audit_events
    FOR SELECT USING (audit_org_check(audit_id));

CREATE POLICY audit_events_insert ON audit_events
    FOR INSERT WITH CHECK (audit_org_check(audit_id));

CREATE POLICY audit_events_update ON audit_events
    FOR UPDATE USING (audit_org_check(audit_id));

CREATE POLICY audit_events_delete ON audit_events
    FOR DELETE USING (audit_org_check(audit_id));

-- -----------------------------------------------------------------------------
-- RLS Policies for metric_time_series
-- -----------------------------------------------------------------------------

CREATE POLICY metric_time_series_select ON metric_time_series
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM companies
            WHERE companies.id = metric_time_series.company_id
            AND user_in_org(companies.organization_id)
        )
    );

CREATE POLICY metric_time_series_insert ON metric_time_series
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM companies
            WHERE companies.id = metric_time_series.company_id
            AND user_in_org(companies.organization_id)
        )
    );

CREATE POLICY metric_time_series_update ON metric_time_series
    FOR UPDATE USING (
        EXISTS (
            SELECT 1 FROM companies
            WHERE companies.id = metric_time_series.company_id
            AND user_in_org(companies.organization_id)
        )
    );

CREATE POLICY metric_time_series_delete ON metric_time_series
    FOR DELETE USING (
        EXISTS (
            SELECT 1 FROM companies
            WHERE companies.id = metric_time_series.company_id
            AND user_in_org(companies.organization_id)
        )
    );