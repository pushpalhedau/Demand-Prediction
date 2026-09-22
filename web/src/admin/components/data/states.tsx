import { AlertCircle, Inbox } from "lucide-react";
import type { ReactNode } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

export function ErrorState({ message, reference }: { message: string; reference?: string }) {
  return (
    <Alert variant="destructive">
      <AlertCircle />
      <AlertTitle>{message}</AlertTitle>
      {reference && <AlertDescription>Reference: {reference}</AlertDescription>}
    </Alert>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="text-muted-foreground flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed px-6 py-12 text-center">
      <Inbox className="size-6" aria-hidden />
      <p className="text-foreground text-sm font-medium">{title}</p>
      {children && <div className="max-w-md text-sm">{children}</div>}
    </div>
  );
}
