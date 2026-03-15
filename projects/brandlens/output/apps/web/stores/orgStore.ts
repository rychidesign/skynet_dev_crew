import { create } from 'zustand'

export interface OrgBase {
  id: string
  name: string
  slug: string
  plan: string
}

interface OrgState {
  organizations: OrgBase[]
  activeOrg: OrgBase | null
  setOrganizations: (orgs: OrgBase[]) => void
  setActiveOrg: (org: OrgBase) => void
}

export const useOrgStore = create<OrgState>((set) => ({
  organizations: [],
  activeOrg: null,
  setOrganizations: (orgs) => set({ organizations: orgs }),
  setActiveOrg: (org) => set({ activeOrg: org }),
}))
