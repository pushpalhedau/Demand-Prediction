import { ExternalLink } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

/**
 * The import wizard (upload, column mapping, dry-run, background job) is not ported yet — it is the most complex
 * screen in the product and is being rebuilt carefully. It stays on the classic console meanwhile.
 */
export function ImportTab({ slug }: { slug: string }) {
  return (
    <Alert>
      <AlertTitle>Import data on the classic console</AlertTitle>
      <AlertDescription>
        <p className="mb-3">
          Uploading files, matching columns and running the import still happens on the classic admin console. Open it, sign in, then pick{" "}
          <strong>{slug}</strong> from the account list and use its <strong>Import data</strong> tab.
        </p>
        <Button asChild size="sm">
          <a href="http://localhost:8502" target="_blank" rel="noopener noreferrer">
            Open classic console <ExternalLink />
          </a>
        </Button>
      </AlertDescription>
    </Alert>
  );
}
