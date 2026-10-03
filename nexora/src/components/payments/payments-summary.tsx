import { Wallet, Clock, AlertTriangle } from "lucide-react";
import { Card } from "@/components/ui/card";
import { formatCurrency } from "@/lib/utils";

export function PaymentsSummary({ totalCollected, totalPending, totalOverdue }: { totalCollected: number; totalPending: number; totalOverdue: number }) {
  const items = [
    { label: "إجمالي المحصّل", value: totalCollected, icon: Wallet, tone: "text-success" },
    { label: "معلّق", value: totalPending, icon: Clock, tone: "text-warning" },
    { label: "متأخر", value: totalOverdue, icon: AlertTriangle, tone: "text-danger" },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      {items.map((item) => (
        <Card key={item.label} className="p-4">
          <div className="flex items-center justify-between">
            <p className="text-xs text-ink-muted">{item.label}</p>
            <item.icon className={`h-4 w-4 ${item.tone}`} />
          </div>
          <p className="mt-2 text-xl font-bold text-ink">{formatCurrency(item.value)}</p>
        </Card>
      ))}
    </div>
  );
}
