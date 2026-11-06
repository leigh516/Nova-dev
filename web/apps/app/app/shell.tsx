"use client";
import { Suspense } from "react";
import { AppShell } from "@nova/ui";
import { APP } from "../lib/app";

export default function Shell({ children }: { children: React.ReactNode }) {
  return <AppShell config={APP}><Suspense>{children}</Suspense></AppShell>;
}
