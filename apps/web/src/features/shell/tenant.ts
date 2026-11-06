"use client";

import { useState } from "react";

import type { Me, Membership } from "@/lib/api/client";

const TENANT_KEY = "meridian.tenant";

function storedTenant(): string | null {
  try {
    return window.localStorage.getItem(TENANT_KEY);
  } catch {
    return null; // gizli pencere ya da engellenmiş depolama
  }
}

/** Sohbet ve panel aynı çalışma alanını gösterir. */
export function useSelectedTenant(me: Me): { membership: Membership; select: (tenantId: string) => void } {
  const [selected, setSelected] = useState(storedTenant);
  const membership = me.memberships.find((item) => item.tenantId === selected) ?? me.memberships[0]!;

  function select(tenantId: string) {
    setSelected(tenantId);
    try {
      window.localStorage.setItem(TENANT_KEY, tenantId);
    } catch {
      // yalnızca kolaylık: kalıcı olmasa da seçim bu sayfada geçerli
    }
  }

  return { membership, select };
}
