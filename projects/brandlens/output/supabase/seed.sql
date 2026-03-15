-- Seed Data for Local Development

-- We use a known UUID for the test organization to link it reliably
DO $$
DECLARE
    org_id UUID := '11111111-1111-1111-1111-111111111111';
    company_id UUID := '22222222-2222-2222-2222-222222222222';
    audit_id UUID := '33333333-3333-3333-3333-333333333333';
    user_id UUID := '00000000-0000-0000-0000-000000000000';
BEGIN
    -- 1. Create Organization
    INSERT INTO organizations (id, name, slug, plan, settings)
    VALUES (org_id, 'BrandLens Test Org', 'brandlens-test-org', 'pro', '{}'::jsonb)
    ON CONFLICT (id) DO NOTHING;

    -- 1a. Create Organization Member
    INSERT INTO organization_members (id, organization_id, user_id, role, invited_at, accepted_at)
    VALUES (
        uuid_generate_v4(),
        org_id,
        user_id,
        'owner',
        now(),
        now()
    )
    ON CONFLICT (organization_id, user_id) DO NOTHING;

    -- 2. Create Company
    INSERT INTO companies (id, organization_id, name, domain, industry, description, facts, competitors, core_topics)
    VALUES (
        company_id,
        org_id,
        'Acme Corp',
        'acme.com',
        'Technology',
        'AI automation company',
        '{"founded": "2020", "product": "AI Widgets", "headquarters": "San Francisco"}'::jsonb,
        '{"Globex": "globex.com", "Initech": "initech.com", "Soylent": "soylent.com"}'::jsonb,
        '{"topics": ["AI automation", "Enterprise widgets"]}'::jsonb
    )
    ON CONFLICT (id) DO NOTHING;

    -- 3. Create Subscription (Mock Pro Plan)
    INSERT INTO subscriptions (organization_id, paddle_subscription_id, paddle_customer_id, status, plan, current_period_start, current_period_end, cancel_at)
    VALUES (
        org_id,
        'sub_test_123',
        'cus_test_123',
        'active',
        'pro',
        now(),
        now() + interval '30 days',
        NULL
    )
    ON CONFLICT (organization_id) DO NOTHING;

    -- 4. Create Usage Tracking
    INSERT INTO usage_tracking (organization_id, period_start, audits_used)
    VALUES (
        org_id,
        date_trunc('month', now())::date,
        1
    )
    ON CONFLICT (organization_id, period_start) DO NOTHING;

    -- 5. Create Mock Audit
    INSERT INTO audits (id, organization_id, company_id, triggered_by, status, config, global_geo_score, score_breakdown)
    VALUES (
        audit_id,
        org_id,
        company_id,
        user_id,
        'completed',
        '{"query_count": 10, "platforms": ["chatgpt", "perplexity"], "cache_ttl_hours": 24}'::jsonb,
        85.50,
        '{
            "global": 85.50,
            "category_breakdown": {
                "entity_semantic": 87.00,
                "citations_trust": 83.00,
                "content_technical": 86.00,
                "reputation_sentiment": 85.50
            },
            "platform_scores": {
                "chatgpt": 86.00,
                "perplexity": 85.00
            }
        }'::jsonb
    )
    ON CONFLICT (id) DO NOTHING;

    -- 6. Insert Sample Audit Queries
    INSERT INTO audit_queries (id, audit_id, query_text, intent, target_metrics, query_index)
    VALUES 
        (uuid_generate_v4(), audit_id, 'What is Acme Corp?', 'informational', '{"GEO-01-ENT-SAL"}', 1),
        (uuid_generate_v4(), audit_id, 'Best AI widget providers', 'comparative', '{"GEO-03-ENT-CON"}', 2),
        (uuid_generate_v4(), audit_id, 'Acme Corp vs Globex', 'comparative', '{"GEO-03-ENT-CON"}', 3)
    ON CONFLICT DO NOTHING;

    -- 7. Insert Sample Metric Scores
    INSERT INTO audit_metric_scores (audit_id, metric_id, metric_category, score, components, weight, weighted_contribution, platform_scores, evidence_summary)
    VALUES 
        (audit_id, 'GEO-01-ENT-SAL', 'entity_semantic', 90.00, '{"component_a": 0.8, "component_b": 0.2}'::jsonb, 0.200, 18.00, '{"chatgpt": 92, "perplexity": 88}'::jsonb, 'Strong entity presence across platforms'),
        (audit_id, 'GEO-03-ENT-CON', 'entity_semantic', 88.00, '{}'::jsonb, 0.100, 8.80, '{"chatgpt": 90, "perplexity": 86}'::jsonb, 'Consistent entity concepts'),
        (audit_id, 'GEO-04-TOP-AUTH', 'entity_semantic', 85.00, '{}'::jsonb, 0.150, 12.75, '{"chatgpt": 87, "perplexity": 83}'::jsonb, 'Good topical authority'),
        (audit_id, 'GEO-05-CIT-FRQ', 'citations_trust', 83.00, '{}'::jsonb, 0.100, 8.30, '{"chatgpt": 85, "perplexity": 81}'::jsonb, 'Frequent citations in knowledge base'),
        (audit_id, 'GEO-07-RAG-INC', 'citations_trust', 81.00, '{}'::jsonb, 0.150, 12.15, '{"chatgpt": 83, "perplexity": 79}'::jsonb, 'Good RAG inclusion'),
        (audit_id, 'GEO-11-FRS-REC', 'content_technical', 95.00, '{}'::jsonb, 0.150, 14.25, '{"chatgpt": 95, "perplexity": 95}'::jsonb, 'First-party recall strong'),
        (audit_id, 'GEO-17-CRW-ACC', 'content_technical', 95.00, '{}'::jsonb, 0.150, 14.25, '{"chatgpt": 95, "perplexity": 95}'::jsonb, 'All crawlers allowed'),
        (audit_id, 'GEO-13-SNT-POL', 'reputation_sentiment', 82.00, '{}'::jsonb, 0.100, 8.20, '{"chatgpt": 85, "perplexity": 79}'::jsonb, 'Generally positive sentiment'),
        (audit_id, 'GEO-14-CMP-PST', 'reputation_sentiment', 84.00, '{}'::jsonb, 0.150, 12.60, '{"chatgpt": 86, "perplexity": 82}'::jsonb, 'Positive comparison mentions'),
        (audit_id, 'GEO-16-HAL-RSK', 'reputation_sentiment', 78.00, '{}'::jsonb, 0.100, 7.80, '{"chatgpt": 80, "perplexity": 76}'::jsonb, 'Low hallucination risk')
    ON CONFLICT (audit_id, metric_id) DO NOTHING;

    -- 8. Insert Sample Metric Time Series
    INSERT INTO metric_time_series (
        company_id, audit_id, snapshot_date, global_geo_score,
        ent_sal_score, ent_con_score, top_auth_score,
        cit_frq_score, rag_inc_score,
        frs_rec_score, crw_acc_score,
        snt_pol_score, cmp_pst_score, hal_rsk_score,
        category_entity_semantic, category_citations_trust,
        category_content_technical, category_reputation_sentiment, platform_scores
    ) VALUES (
        company_id, audit_id, CURRENT_DATE, 85.50,
        90.00, 88.00, 85.00,
        83.00, 81.00,
        95.00, 95.00,
        82.00, 84.00, 78.00,
        87.67, 82.00, 95.00, 81.33,
        '{"chatgpt": 86.00, "perplexity": 85.00}'::jsonb
    )
    ON CONFLICT (audit_id) DO UPDATE SET
        snapshot_date = EXCLUDED.snapshot_date,
        global_geo_score = EXCLUDED.global_geo_score,
        ent_sal_score = EXCLUDED.ent_sal_score,
        ent_con_score = EXCLUDED.ent_con_score,
        top_auth_score = EXCLUDED.top_auth_score,
        cit_frq_score = EXCLUDED.cit_frq_score,
        rag_inc_score = EXCLUDED.rag_inc_score,
        frs_rec_score = EXCLUDED.frs_rec_score,
        crw_acc_score = EXCLUDED.crw_acc_score,
        snt_pol_score = EXCLUDED.snt_pol_score,
        cmp_pst_score = EXCLUDED.cmp_pst_score,
        hal_rsk_score = EXCLUDED.hal_rsk_score,
        category_entity_semantic = EXCLUDED.category_entity_semantic,
        category_citations_trust = EXCLUDED.category_citations_trust,
        category_content_technical = EXCLUDED.category_content_technical,
        category_reputation_sentiment = EXCLUDED.category_reputation_sentiment,
        platform_scores = EXCLUDED.platform_scores;

END $$;