-- Subscriptions Table (Synced via Paddle Webhooks) - UPDATED
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL UNIQUE REFERENCES organizations(id) ON DELETE CASCADE,
    paddle_subscription_id TEXT UNIQUE NOT NULL,
    paddle_customer_id TEXT NOT NULL,
    status TEXT NOT NULL,
    plan TEXT NOT NULL,
    current_period_start TIMESTAMPTZ,
    current_period_end TIMESTAMPTZ,
    cancel_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Usage Tracking Table (Monthly Limits) - UPDATED
CREATE TABLE usage_tracking (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    period_start DATE NOT NULL,
    audits_used INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(organization_id, period_start)
);

-- Trigger for updated_at
CREATE TRIGGER update_subscriptions_modtime BEFORE UPDATE ON subscriptions FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
CREATE TRIGGER update_usage_tracking_modtime BEFORE UPDATE ON usage_tracking FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

-- Enable RLS
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_tracking ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "Users can view their org subscription" ON subscriptions
  FOR SELECT USING (user_in_org(organization_id));

CREATE POLICY "Users can view their org usage tracking" ON usage_tracking
  FOR SELECT USING (user_in_org(organization_id));

-- Backend uses Service Role Key to insert/update these tables via webhooks
