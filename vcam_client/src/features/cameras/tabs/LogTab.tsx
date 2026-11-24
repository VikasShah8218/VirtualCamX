import { Download } from "lucide-react"
import { useCameraLog } from "@/api/queries"
import type { Camera } from "@/api/types"
import { Section } from "@/components/common"
import { Button } from "@/components/ui/button"

export function LogTab({ camera: c }: { camera: Camera }) {
  const log = useCameraLog(c.id)
  const lines = log.data?.lines ?? []
  const download = () => {
    const url = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/plain" }))
    const a = document.createElement("a")
    a.href = url
    a.download = `${c.name}-log.txt`
    a.click()
    URL.revokeObjectURL(url)
  }
  return (
    <Section
      title="Camera log"
      description="Same lines NVRs get with ONVIF GetSystemLog. Refreshes every 5 s."
      actions={<Button size="xs" variant="outline" onClick={download} disabled={!lines.length}><Download /> Download</Button>}
    >
      <pre className="max-h-[60vh] overflow-auto rounded-md bg-muted p-3 font-mono text-[11px] leading-relaxed">
        {lines.length ? [...lines].reverse().join("\n") : "No log lines yet."}
      </pre>
    </Section>
  )
}
