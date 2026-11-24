import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { CameraApp } from "./CameraApp"
import "./index.css"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <CameraApp />
  </StrictMode>,
)
