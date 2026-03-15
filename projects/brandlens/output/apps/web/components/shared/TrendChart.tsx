"use client";

import { useMemo } from "react";
import { MetricTimeSeries } from "@shared/types/database";

// Fake TrendChart aby sel kod zkompilovat
interface TrendChartProps {
  data: Pick<MetricTimeSeries, 'snapshotDate' | 'globalGeoScore' | 'categoryEntitySemantic' | 'categoryCitationsTrust' | 'categoryContentTechnical' | 'categoryReputationSentiment'>[];
}

export function TrendChart({ data }: TrendChartProps) {
  const sortedData = useMemo(() => {
    return [...data].sort(
      (a, b) => new Date(a.snapshotDate || "").getTime() - new Date(b.snapshotDate || "").getTime()
    );
  }, [data]);

  if (sortedData.length === 0) {
    return (
      <div className="h-full w-full flex items-center justify-center text-muted-foreground text-sm border border-dashed rounded-lg bg-muted/20">
        No trend data available
      </div>
    );
  }

  return (
    <div className="h-full w-full flex flex-col justify-end gap-1 relative border-b border-l pb-2 pl-2 border-muted">
      {/* Mock chart visualization */}
      <div className="flex h-full items-end gap-2 px-2 overflow-x-auto w-full">
        {sortedData.map((point, index) => {
          const heightPct = point.globalGeoScore ? `${Math.max(10, point.globalGeoScore)}%` : "10%";
          return (
            <div key={index} className="flex flex-col items-center justify-end h-full min-w-[30px] group relative">
              <div 
                className="w-full bg-primary/80 rounded-t-sm hover:bg-primary transition-colors cursor-pointer"
                style={{ height: heightPct }}
              >
                  <div className="opacity-0 group-hover:opacity-100 absolute -top-8 left-1/2 -translate-x-1/2 bg-popover text-popover-foreground text-xs px-2 py-1 rounded shadow-md pointer-events-none whitespace-nowrap z-10 transition-opacity">
                    {point.globalGeoScore ? point.globalGeoScore.toFixed(1) : "N/A"}
                    <br/>
                    <span className="text-[10px] text-muted-foreground">
                      {new Date(point.snapshotDate || "").toLocaleDateString()}
                    </span>
                  </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
