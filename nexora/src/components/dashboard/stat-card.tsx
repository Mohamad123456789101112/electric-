"use client";

import type { LucideIcon } from "lucide-react";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { AnimatedCounter } from "./animated-counter";
import { cn, formatCurrency } from "@/lib/utils";

export function StatCard({
  label,
  value,
  icon: Icon,
  trend,
  format = "number",
  index = 0,
}: {
  label: string;
  value: number;
  icon: LucideIcon;
  trend?: { value: number; label: string } | null;
  format?: "number" | "currency" | "percent";
  index?: number;
}) {
  const trendPositive = trend ? trend.value > 0 : null;
  const trendNeutral = trend ? trend.value === 0 : true;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: index * 0.06, ease: [0.16, 1, 0.3, 1] }}
    >
      <Card className="group p-5 transition-all hover:shadow-[var(--shadow-elevation-2)] hover:-translate-y-0.5 sm:p-6">
        <div className="flex items-center justify-between">
          <span className="text-sm text-ink-muted">{label}</span>
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-accent-soft text-accent transition-transform group-hover:scale-105">
            <Icon className="h-4 w-4" aria-hidden="true" />
          </div>
        </div>
        <div className="mt-4 text-2xl font-bold tracking-tight text-ink sm:text-[28px]">
          {format === "currency" ? (
            <AnimatedCounter value={value} formatter={(n) => formatCurrency(n)} />
          ) : format === "percent" ? (
            <>
              <AnimatedCounter value={value} />
              <span className="text-lg">٪</span>
            </>
          ) : (
            <AnimatedCounter value={value} />
          )}
        </div>
        {trend && (
          <div
            className={cn(
              "mt-3 inline-flex items-center gap-1 text-xs font-medium",
              trendNeutral ? "text-ink-muted" : trendPositive ? "text-success" : "text-danger"
            )}
          >
            {trendNeutral ? (
              <Minus className="h-3 w-3" />
            ) : trendPositive ? (
              <ArrowUpRight className="h-3 w-3" />
            ) : (
              <ArrowDownRight className="h-3 w-3" />
            )}
            <span>{trend.label}</span>
          </div>
        )}
      </Card>
    </motion.div>
  );
}
