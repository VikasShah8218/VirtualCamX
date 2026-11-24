import type { SourceSpec } from "@/api/types"

/** A complete SourceSpec (the generated type marks fields that have server defaults as required). */
export function makeSource(partial: Partial<SourceSpec> & { type: SourceSpec["type"] }): SourceSpec {
  return { pattern: "testsrc2", start_offset: 0, loop: true, path: null, url: null, ...partial }
}

/** Last part of a Windows or POSIX path. */
export const baseName = (path: string | null | undefined) => (path ?? "").split(/[\\/]/).pop() ?? ""

export function sourceLabel(s: SourceSpec): string {
  if (s.type === "file" || s.type === "image") return baseName(s.path) || s.type
  if (s.type === "rtsp") return s.url ?? "RTSP relay"
  return `Test pattern (${s.pattern})`
}
