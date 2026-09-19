"use client";

import { useDashboardQuery } from "@/lib/query";
import type { Glance, Recommendations } from "@/lib/types";

export const useGlance = () => useDashboardQuery<Glance>("overview-glance", "/api/overview/glance");

/** The plays' wording is generated server-side in the viewer's language, so language is part of the cache key. */
export const useRecommendations = () => useDashboardQuery<Recommendations>("overview-recs", "/api/overview/recommendations", { serverText: true });
