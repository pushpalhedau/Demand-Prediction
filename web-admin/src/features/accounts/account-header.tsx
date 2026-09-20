import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { MetricStrip, type Metric } from "@/components/data/metric-strip";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/format";
import type { AccountDetail } from "@/lib/types";

export function AccountHeader({ account }: { account: AccountDetail }) {
  const s = account.summary;
  const metrics: Metric[] = [
    { label: "Sales", value: s.sales.toLocaleString() },
    { label: "Dealers", value: s.dealers.toLocaleString() },
    { label: "Customers", value: s.customers.toLocaleString() },
    { label: "Inventory rows", value: s.inventory.toLocaleString() },
    { label: "Data from", value: formatDate(s.first_sale) },
    { label: "Models trained", value: s.models ? "Yes" : "No", delta: { text: s.models ? "ready" : "not yet", tone: s.models ? "positive" : "neutral" } },
  ];

  return (
    <div className="space-y-6">
      <Button asChild variant="ghost" size="sm" className="text-muted-foreground -ml-2 gap-1.5">
        <Link href="/">
          <ArrowLeft className="size-4" /> All accounts
        </Link>
      </Button>
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="font-heading text-[1.65rem] leading-tight font-semibold tracking-[-0.02em]">{account.name}</h1>
        <Badge variant={account.status === "active" ? "secondary" : "destructive"}>{account.status === "active" ? "Active" : "Suspended"}</Badge>
      </div>
      <p className="text-muted-foreground -mt-4 text-sm">
        id <code className="text-xs">{account.slug}</code> · created {formatDate(account.created_at)}
      </p>
      <MetricStrip metrics={metrics} />
      {s.sales === 0 && (
        <p className="text-muted-foreground bg-muted rounded-md px-3 py-2 text-sm">
          No data yet. Upload their files in the Import data tab. Until then they see &quot;Your account is being set up&quot;.
        </p>
      )}
    </div>
  );
}
