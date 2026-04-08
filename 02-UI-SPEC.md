# UI-SPEC - Phase 2: Core UI & Wizard

**Status:** draft
**Phase:** 02 - Core UI & Wizard
**Design System:** PyQt6 Standard (with custom CSS)

## 1. Visual Theme (PyQt6-based)

The application uses a clean, modern desktop aesthetic leveraging standard PyQt6 widgets with custom stylesheet enhancements.

### Color Palette
- **Dominant (Surface):** `#ffffff` (White) or System Default Window Color (60%)
- **Secondary (Columns/Sidebars):** `#f3f4f6` (Light Gray) (30%)
- **Accent (Primary Action):** `#2b579a` (Windows/Qt Blue) (10%)
  - *Used for: "Apply Configuration", "Launch Wizard", "Next/Finish" buttons.*
- **Identify (Highlight):** `#e0f7fa` (Light Cyan)
  - *Used for: Brief flash on device identification.*
- **Destructive/Critical:** `#d32f2f` (Material Red)
  - *Used for: "Install Now", "Clear Seat", "Cancel" in critical contexts.*

### Typography
- **Title (Wizard/Main):** 20pt Bold, System Default
- **Heading (Columns):** 14pt Bold, System Default
- **Body (Labels/Lists):** 10pt Regular, System Default, 1.4 line-height
- **Monospace (Review):** 10pt "Monospace" or "Courier New"
  - *Used for: `review_dialog.py` text edit.*

### Iconography
- **Graphics:** `🖥️`
- **Input Devices:** `⌨️` (Keyboard), `🖱️` (Mouse), `🕹️` (Generic Input)
- **USB Hubs:** `🔌`
- **Audio/Video:** `🎙️` (Mic), `🔊` (Speaker), `📺` (Monitor)
- **Status:** `✅` (Success), `⚠️` (Warning)

---

## 2. Layout & Spacing

### Spacing Scale
- **Unit:** 8px
- **Layout Spacing:** `setSpacing(8)`
- **Layout Margins:** `setContentsMargins(16, 16, 16, 16)`
- **Column Stretch:**
  - `seat0` (Master): Stretch 1
  - Secondary Seats: Stretch 2 (total for scrollable area)

### Navigation Structure
- **Primary:** `AdvancedSetupWindow` (Main Entry)
  - **Focal Point:** "Apply Configuration" button (Bottom Right).
- **Secondary:** `ExpressSetupWizard` (Triggered from Main)
- **Overlays:** `DisplayOverlay` (Frameless, translucent white on blue)

---

## 3. Component Contracts

### 3.1 Setup Wizard (`wizard.py`)
- **Flow:**
  1. `IntroPage`: Explains multiseat; allows setting `seat_count` (1-10).
  2. `SeatSetupPage` (Dynamic): Generated for each `seatX`.
     - **GPU Picker:** `QComboBox` populated from `HardwareScanner.scan_graphics()`.
     - **Input Identification:** Button triggers `InputListenerThread`.
     - **Display Identification:** Button triggers `OverlayManager.show_gpu_overlays()`.
  3. `FinalPage`:
     - **Summary:** Shows all items remaining on `seat0`.
     - **Action:** Confirmation before exiting.

### 3.2 Advanced Manual Setup (`advanced_ui.py`)
- **Draggable Trees (`DraggableTree`):**
  - **Drag Source:** `seat0` tree or any secondary seat tree.
  - **Drop Target:** Any seat tree.
  - **Grouping:** Items must be automatically sorted into "Graphics", "Inputs", "USB", or "AV" group nodes upon drop.
  - **Nesting Rules:**
    - Monitors MUST move with GPUs.
    - Audio/Video nested under Monitors MUST move with them.
    - Only top-level nodes (GPU, Input Device, USB Hub, Independent AV) are draggable.

---

## 4. Interaction Contracts

### Drag-and-Drop Reliability
- **Action:** `Qt.DropAction.MoveAction` only.
- **Validation:** `dropEvent` must check `hw_type` and force assignment to correct group node.
- **Feedback:** Standard Qt drop indicator.

### Device Identification
- **Input:** When `InputListenerThread` emits `device_identified(persistent_id)`, the UI MUST:
  - Scroll to the item in the `DraggableTree`.
  - Select the item.
  - Flash the item background with `Identify (Highlight)` color for 1.5 seconds.
- **Graphics:** When "Identify Displays" clicked, `OverlayManager` MUST show overlays for 4 seconds on all screens associated with the selected GPU.

---

## 5. Copywriting

| Context | String | Purpose |
|---------|--------|---------|
| Wizard Intro | "This wizard will help you configure additional seats." | Orientation |
| Wizard Final | "Everything not assigned to a secondary seat will remain on seat0 (Master)." | Confirmation |
| Main Window CTA | "Apply Configuration" | Primary Action (Focal Point) |
| Input Listener | "Listening... (Press a key/button on the physical device)" | Instruction |
| Success State | "Configuration applied successfully! Please reboot or restart your session." | Feedback |
| Empty State | "Pending Hardware Selection..." | Placeholder |
| Review Dialog | "Install Now (sudo)" | Destructive/Critical Action |
| Error State | "Configuration failed. Please check hardware permissions and try again." | Error Feedback |
| Destructive | "Discard Changes" | Replaces generic "Cancel" |
| Wizard | "Stop Setup" | Replaces generic "Cancel" |

---

## 6. Pre-Populated Decisions

| Source | Decisions Used |
|--------|----------------|
| PLAN.md | Phase 2 layout (Master left, others right), Wizard flow, Drag-and-Drop. |
| STACK.md | PyQt6, Python, evdev, loginctl. |
| README.md | Screenshots showing "Windows Blue" and "Material Red" colors. |
| scanner.py | Hardware categories (Graphics, Inputs, USB, AV). |
| current codebase | Hex colors `#2b579a`, `#d32f2f`, `#e0f7fa` already in use. |
