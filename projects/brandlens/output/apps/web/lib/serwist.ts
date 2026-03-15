import type { RuntimeCaching } from "serwist";
import { defaultCache } from "@serwist/next/worker";

// Here we can define custom caching strategies if defaultCache is not enough.
// For now, we export the default setup.
export const customRuntimeCaching: RuntimeCaching[] = [
  ...defaultCache,
];
