import { type SupabaseClient } from '@supabase/supabase-js'

export interface OnboardingPayload {
  orgName: string;
  companyName: string;
  companyDomain?: string;
  companyIndustry?: string;
}

export async function setupNewOrganization(
  supabase: SupabaseClient,
  payload: OnboardingPayload,
  userId: string
) {
  // 1. Organizace
  // Generate a simple slug from the org name (lowercase, replace non-alphanumeric with hyphens)
  const slug = payload.orgName
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '') + '-' + Math.random().toString(36).substring(2, 6);

  const { data: orgData, error: orgError } = await supabase
    .from('organizations')
    .insert({
      name: payload.orgName,
      slug: slug,
      plan: 'free',
    })
    .select('id')
    .single();

  if (orgError) {
    console.error('Failed to create organization:', orgError);
    throw new Error('Failed to create organization. Please try again.');
  }

  const orgId = orgData.id;

  // 2. Členství
  const { error: memberError } = await supabase
    .from('organization_members')
    .insert({
      organization_id: orgId,
      user_id: userId,
      role: 'owner',
      accepted_at: new Date().toISOString(),
    });

  if (memberError) {
    console.error('Failed to add organization member:', memberError);
    throw new Error('Failed to set up permissions. Please contact support.');
  }

  // 3. Společnost
  const { error: companyError } = await supabase
    .from('companies')
    .insert({
      organization_id: orgId,
      name: payload.companyName,
      domain: payload.companyDomain || null,
      industry: payload.companyIndustry || null,
    });

  if (companyError) {
    console.error('Failed to create company:', companyError);
    throw new Error('Failed to create company profile.');
  }

  // 4. Předplatné
  const { error: subError } = await supabase
    .from('subscriptions')
    .insert({
      organization_id: orgId,
      status: 'active',
      plan: 'free',
      current_period_start: new Date().toISOString(),
    });

  if (subError) {
    console.error('Failed to create subscription record:', subError);
    throw new Error('Failed to set up subscription plan.');
  }

  // 5. Usage tracking
  // Get 1st day of current month in YYYY-MM-DD format
  const now = new Date();
  const firstDayOfMonth = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1))
    .toISOString()
    .split('T')[0];

  const { error: usageError } = await supabase
    .from('usage_tracking')
    .insert({
      organization_id: orgId,
      period_start: firstDayOfMonth,
      audits_used: 0,
    });

  if (usageError) {
    console.error('Failed to initialize usage tracking:', usageError);
    throw new Error('Failed to initialize usage tracking.');
  }

  return { organizationId: orgId };
}
