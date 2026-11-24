import { ArrowDown, ArrowDownLeft, ArrowDownRight, ArrowLeft, ArrowRight, ArrowUp, ArrowUpLeft, ArrowUpRight, Home, ZoomIn, ZoomOut } from "lucide-react"
import { useEffect, useRef, useState, type ReactNode } from "react"
import { Button } from "@/components/ui/button"
import { Slider } from "@/components/ui/slider"
import { cn } from "@/lib/utils"

export interface PtzActions {
  move: (pan: number, tilt: number, zoom: number) => Promise<unknown>
  stop: () => Promise<unknown>
  home?: () => Promise<unknown>
  gotoPreset?: (token: string) => Promise<unknown>
}

/**
 * Press-and-hold PTZ pad (same feel as an NVR joystick). While held, the move command is
 * re-sent every 1.5 s (the backend move times out after 2 s, so a lost "stop" cannot leave
 * the camera spinning). Shared by the Manager camera detail and the Camera Web Page.
 */
export function PtzPad({ actions, presets, position, className }: {
  actions: PtzActions
  presets?: { token: string; name: string }[]
  position?: { pan: number; tilt: number; zoom: number; moving: boolean }
  className?: string
}) {
  const [speed, setSpeed] = useState(0.5)
  const held = useRef<ReturnType<typeof setInterval> | null>(null)

  const release = () => {
    if (held.current) {
      clearInterval(held.current)
      held.current = null
      void actions.stop()
    }
  }
  useEffect(() => release, []) // eslint-disable-line react-hooks/exhaustive-deps

  const press = (pan: number, tilt: number, zoom: number) => {
    release()
    const send = () => void actions.move(pan * speed, tilt * speed, zoom * speed)
    send()
    held.current = setInterval(send, 1500)
  }

  const Btn = ({ icon, d, label }: { icon: ReactNode; d: [number, number, number]; label: string }) => (
    <Button
      variant="secondary"
      size="icon-lg"
      aria-label={label}
      className="touch-none"
      onPointerDown={(e) => {
        e.currentTarget.setPointerCapture(e.pointerId)
        press(...d)
      }}
      onPointerUp={release}
      onPointerCancel={release}
    >
      {icon}
    </Button>
  )

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      <div className="grid w-fit grid-cols-3 gap-1.5 self-center">
        <Btn icon={<ArrowUpLeft />} d={[-1, 1, 0]} label="Up left" />
        <Btn icon={<ArrowUp />} d={[0, 1, 0]} label="Up" />
        <Btn icon={<ArrowUpRight />} d={[1, 1, 0]} label="Up right" />
        <Btn icon={<ArrowLeft />} d={[-1, 0, 0]} label="Left" />
        <Button variant="outline" size="icon-lg" aria-label="Home" onClick={() => actions.home?.()} disabled={!actions.home}>
          <Home />
        </Button>
        <Btn icon={<ArrowRight />} d={[1, 0, 0]} label="Right" />
        <Btn icon={<ArrowDownLeft />} d={[-1, -1, 0]} label="Down left" />
        <Btn icon={<ArrowDown />} d={[0, -1, 0]} label="Down" />
        <Btn icon={<ArrowDownRight />} d={[1, -1, 0]} label="Down right" />
      </div>
      <div className="flex items-center justify-center gap-2">
        <Btn icon={<ZoomOut />} d={[0, 0, -1]} label="Zoom out" />
        <Btn icon={<ZoomIn />} d={[0, 0, 1]} label="Zoom in" />
      </div>
      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        Speed
        <Slider value={[speed * 100]} min={10} max={100} step={10} onValueChange={([v]) => setSpeed(v / 100)} />
        <span className="w-8 tabular-nums">{Math.round(speed * 100)}%</span>
      </div>
      {position && (
        <div className="rounded-md bg-muted px-2 py-1 text-center font-mono text-[11px] tabular-nums text-muted-foreground">
          pan {position.pan.toFixed(2)} · tilt {position.tilt.toFixed(2)} · zoom {position.zoom.toFixed(2)} {position.moving && "· moving"}
        </div>
      )}
      {presets && presets.length > 0 && actions.gotoPreset && (
        <div className="flex flex-wrap gap-1.5">
          {presets.map((p) => (
            <Button key={p.token} variant="outline" size="xs" onClick={() => actions.gotoPreset!(p.token)}>
              {p.token}. {p.name}
            </Button>
          ))}
        </div>
      )}
    </div>
  )
}
