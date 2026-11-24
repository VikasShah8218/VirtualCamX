import type { Camera } from "@/api/types"
import { InspectorView } from "@/features/inspector/InspectorView"

export function OnvifTab({ camera: c }: { camera: Camera }) {
  return <InspectorView cameraId={c.id} />
}
