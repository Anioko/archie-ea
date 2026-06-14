import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"
import { format, formatDistanceToNow, parseISO } from "date-fns"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// ── Data Formatters ──

export function formatDate(value: string | Date | null | undefined): string {
  if (!value) return "—"
  try {
    // Handle "YYYY-MM-DD HH:MM:SS" (space separator) as well as ISO 8601
    const normalised = typeof value === "string" ? value.replace(" ", "T") : value
    const date = typeof normalised === "string" ? parseISO(normalised) : normalised
    return format(date, "MMM d, yyyy")
  } catch {
    return "—"
  }
}

export function formatDateTime(value: string | Date | null | undefined): string {
  if (!value) return "—"
  try {
    const normalised = typeof value === "string" ? value.replace(" ", "T") : value
    const date = typeof normalised === "string" ? parseISO(normalised) : normalised
    return format(date, "MMM d, yyyy 'at' h:mm a")
  } catch {
    return "—"
  }
}

export function formatRelative(value: string | Date | null | undefined): string {
  if (!value) return "—"
  try {
    const normalised = typeof value === "string" ? value.replace(" ", "T") : value
    const date = typeof normalised === "string" ? parseISO(normalised) : normalised
    return formatDistanceToNow(date, { addSuffix: true })
  } catch {
    return "—"
  }
}

export function formatCurrency(value: number | null | undefined, currency = "USD"): string {
  if (value == null) return "—"
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(value)
}

export function formatNumber(value: number | null | undefined): string {
  if (value == null) return "—"
  return new Intl.NumberFormat("en-US").format(value)
}

export function formatBoolean(value: boolean | null | undefined): string {
  if (value == null) return "—"
  return value ? "Yes" : "No"
}

export function truncate(str: string, length = 50): string {
  if (!str) return "—"
  return str.length > length ? str.slice(0, length) + "..." : str
}

// ── Status Badge Colors ──

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
  pending: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400",
  active: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400",
  in_progress: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
  completed: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400",
  done: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400",
  approved: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400",
  cancelled: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
  denied: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
  rejected: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
  failed: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
  assigned: "bg-violet-100 text-violet-800 dark:bg-violet-900/30 dark:text-violet-400",
  review: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-400",
  under_review: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-400",
  filed: "bg-sky-100 text-sky-800 dark:bg-sky-900/30 dark:text-sky-400",
  backlog: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
  todo: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
  confirmed: "bg-teal-100 text-teal-800 dark:bg-teal-900/30 dark:text-teal-400",
  checked_in: "bg-cyan-100 text-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-400",
  no_show: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400",
}

export function statusColor(status: string | null | undefined): string {
  if (!status) return STATUS_COLORS.draft
  return STATUS_COLORS[status.toLowerCase().replace(/ /g, "_")] ?? STATUS_COLORS.draft
}

export function statusLabel(status: string | null | undefined): string {
  if (!status) return "Unknown"
  return status.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
}
