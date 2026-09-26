"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { apiPost } from "@/lib/api-client";

export function LogoutButton() {
  const router = useRouter();
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  async function logout() {
    setIsLoggingOut(true);
    try {
      await apiPost("/api/auth/logout");
    } finally {
      router.replace("/login");
      router.refresh();
    }
  }

  return <Button variant="outline" onClick={logout} disabled={isLoggingOut}>{isLoggingOut ? "Signing out…" : "Sign out"}</Button>;
}
