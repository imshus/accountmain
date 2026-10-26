import type { IconName } from "../ui";
import type { Route } from "../router";

/** Home's two rows of pills (the owner's picture): "Add data" and "Report". Change the shortcuts here; keep the labels
 * short so a row stays readable on a phone (it scrolls sideways when it does not fit). "upload" opens the chat's file
 * picker; "chat" puts the cursor in the ask box. */
export type QuickAction = { label: string; icon: IconName; go: Route | "upload" | "chat"; primary?: boolean };

export const ADD_DATA: QuickAction[] = [
  { label: "Input by chat", icon: "chat", go: "chat" },
  { label: "Sales", icon: "trend", go: { name: "entry", kind: "sale" } },
  { label: "Purchase", icon: "cart", go: { name: "entry", kind: "purchase" } },
  { label: "Gold in/out", icon: "swap", go: { name: "metal", kind: "receipt" } },
  { label: "Upload", icon: "upload", go: "upload" },
];

export const REPORTS: QuickAction[] = [
  { label: "Chat with data", icon: "chat", go: "chat", primary: true },
  { label: "Sales", icon: "trend", go: { name: "register", kind: "sales" } },
  { label: "Purchase", icon: "cart", go: { name: "register", kind: "purchases" } },
  { label: "Stock", icon: "cube", go: { name: "stock" } },
];
