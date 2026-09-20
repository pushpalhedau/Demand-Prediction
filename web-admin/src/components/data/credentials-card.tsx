"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import type { Flash } from "@/lib/flash";

/** A generated login, shown exactly once. The password is never stored anywhere it can be read again. */
export function CredentialsCard({ flash, onDismiss }: { flash: Flash; onDismiss: () => void }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(`Email: ${flash.email}\nPassword: ${flash.password}`);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard unavailable: the values are still visible to copy by hand */
    }
  }

  return (
    <Alert>
      <AlertTitle>{flash.title}</AlertTitle>
      <AlertDescription>
        <div className="mt-2 space-y-2">
          <pre className="bg-muted overflow-x-auto rounded-md p-3 font-mono text-xs">{`Email:    ${flash.email}\nPassword: ${flash.password}`}</pre>
          <p className="text-xs">Copy these now. The password is not stored anywhere you can read it again.</p>
          <div className="flex gap-2">
            <Button type="button" size="sm" variant="outline" onClick={copy}>
              {copied ? <Check /> : <Copy />} {copied ? "Copied" : "Copy"}
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={onDismiss}>
              Dismiss
            </Button>
          </div>
        </div>
      </AlertDescription>
    </Alert>
  );
}
