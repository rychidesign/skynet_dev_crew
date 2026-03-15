import { SupabaseClient } from '@supabase/supabase-js';
import { CompanyRow, CompanyUpdate } from '@shared/types/database';

export async function getCompanyById(
  supabase: SupabaseClient,
  id: string
): Promise<CompanyRow> {
  const { data, error } = await supabase
    .from('companies')
    .select('*')
    .eq('id', id)
    .single();

  if (error) {
    throw new Error(`Failed to fetch company: ${error.message}`);
  }

  return data as CompanyRow;
}

export async function updateCompany(
  supabase: SupabaseClient,
  id: string,
  updates: CompanyUpdate
): Promise<void> {
  const { error } = await supabase
    .from('companies')
    .update(updates)
    .eq('id', id);

  if (error) {
    throw new Error(`Failed to update company: ${error.message}`);
  }
}
