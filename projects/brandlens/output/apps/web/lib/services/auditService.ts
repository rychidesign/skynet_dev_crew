import { SupabaseClient } from '@supabase/supabase-js';
import { AuditRow, MetricTimeSeriesRow } from '@shared/types/database';

export async function getAuditsByCompany(
  supabase: SupabaseClient,
  companyId: string
): Promise<AuditRow[]> {
  const { data, error } = await supabase
    .from('audits')
    .select('*')
    .eq('company_id', companyId)
    .order('created_at', { ascending: false });

  if (error) {
    throw new Error(`Failed to fetch audits: ${error.message}`);
  }

  return data as AuditRow[];
}

export async function getCompanyTimeSeries(
  supabase: SupabaseClient,
  companyId: string
): Promise<MetricTimeSeriesRow[]> {
  const { data, error } = await supabase
    .from('metric_time_series')
    .select('*')
    .eq('company_id', companyId)
    .order('snapshot_date', { ascending: true });

  if (error) {
    throw new Error(`Failed to fetch time series: ${error.message}`);
  }

  return data as MetricTimeSeriesRow[];
}
