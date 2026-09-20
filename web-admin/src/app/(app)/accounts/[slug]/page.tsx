"use client";

import { useParams } from "next/navigation";
import { AccountDetailPage } from "@/features/accounts/account-detail-page";

export default function Page() {
  const { slug } = useParams<{ slug: string }>();
  return <AccountDetailPage slug={slug} />;
}
