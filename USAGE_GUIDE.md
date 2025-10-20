# SAM 2 TouchDesigner Usage Guide

Complete guide for using SAM 2 segmentation in TouchDesigner.

## Basic Setup

### 1. Network Structure

```
┌─────────────────────────────────────────────────────────┐
│ TouchDesigner Network                                    │
│                                                          │
│  [Video Source] → [Syphon Out] → (SAM 2 Server)        │
│                                                          │
│  (SAM 2 Server) → [Syphon In] → [Display/Processing]   │
│                                                          │
│  [Control Logic] → [OSC Out] → (SAM 2 Server)          │
│                                                          │
│  (SAM 2 Server) → [OSC In CHOP] → [Data Processing]    │
└─────────────────────────────────────────────────────────┘
```

### 2. Minimum Components

1. **Syphon Out TOP** - Send video to SAM 2
2. **Syphon In TOP** - Receive masks from SAM 2
3. **OSC Out DAT** - Send prompts to SAM 2
4. **OSC In CHOP** - Receive mask data from SAM 2

## Mode Examples

### Point Mode - Interactive Clicking

```python
# In a Script DAT or Python script

# Set to point mode
op('oscout1').sendOSC('/sam/mode', ['point'])

# On mouse click (normalized coordinates)
def onMouseClick(x, y):
    # Convert pixel to normalized (0-1)
    norm_x = x / 1920
    norm_y = y / 1080

    # Send positive point
    op('oscout1').sendOSC('/sam/point', [norm_x, norm_y, 1])

# Add negative point (exclude area)
def onRightClick(x, y):
    norm_x = x / 1920
    norm_y = y / 1080
    op('oscout1').sendOSC('/sam/point', [norm_x, norm_y, 0])

# Clear all points
def onClear():
    op('oscout1').sendOSC('/sam/clear', [])
```

### Box Mode - Region Selection

```python
# In a Script DAT

# Set to box mode
op('oscout1').sendOSC('/sam/mode', ['box'])

# On drag selection
def onDragComplete(x1, y1, x2, y2):
    # Convert to normalized coordinates
    norm_x1 = x1 / 1920
    norm_y1 = y1 / 1080
    norm_x2 = x2 / 1920
    norm_y2 = y2 / 1080

    # Send box
    op('oscout1').sendOSC('/sam/box', [norm_x1, norm_y1, norm_x2, norm_y2])
```

### Auto Mode - Segment Everything

```python
# Set to auto mode
op('oscout1').sendOSC('/sam/mode', ['auto'])

# SAM 2 will automatically detect and segment all objects
# (Coming soon in implementation)
```

## Reading Mask Data

### Using OSC In CHOP

The OSC In CHOP will receive channels:

```
/sam/masks/count      # Number of masks
/sam/mask/0/score     # Confidence
/sam/mask/0/area      # Size
```

### Processing in Python

```python
# In a Script CHOP or DAT

def getMaskCount():
    oscin = op('oscin1')
    count_chan = oscin['sam/masks/count']
    if count_chan:
        return count_chan[0].val
    return 0

def getMaskScore():
    oscin = op('oscin1')
    score_chan = oscin['sam/mask/0/score']
    if score_chan:
        return score_chan[0].val
    return 0.0

def getMaskArea():
    oscin = op('oscin1')
    area_chan = oscin['sam/mask/0/area']
    if area_chan:
        return area_chan[0].val
    return 0.0
```

## Interactive UI Example

### Simple Click-to-Segment

1. Create a Container COMP with:
   - **Syphon In TOP** - Display SAM output
   - **Panel** - For mouse interaction
   - **Script DAT** - Handle clicks
   - **OSC Out DAT** - Send prompts

2. Panel callbacks (`callbacks DAT`):

```python
def onLeftClickDown(event):
    # Get normalized coordinates
    u = event.u
    v = event.v

    # Send point prompt
    parent().op('oscout1').sendOSC('/sam/point', [u, v, 1])

def onRightClickDown(event):
    # Negative point
    u = event.u
    v = event.v
    parent().op('oscout1').sendOSC('/sam/point', [u, v, 0])

def onMiddleClickDown(event):
    # Clear
    parent().op('oscout1').sendOSC('/sam/clear', [])
```

### Box Selection UI

```python
# In panel callbacks

# Store drag start
drag_start = None

def onLeftClickDown(event):
    global drag_start
    drag_start = (event.u, event.v)

def onLeftClickUp(event):
    global drag_start
    if drag_start:
        x1, y1 = drag_start
        x2, y2 = event.u, event.v

        # Send box
        parent().op('oscout1').sendOSC('/sam/box', [x1, y1, x2, y2])
        drag_start = None
```

## Advanced Techniques

### Multiple Points Refinement

```python
def refineSegmentation():
    """Add multiple points to refine a mask"""

    # Initial point
    op('oscout1').sendOSC('/sam/point', [0.5, 0.5, 1])

    # Wait for user to see result, then add refinement points
    # (In practice, use timers or callbacks)

    # Add positive points in the object
    op('oscout1').sendOSC('/sam/point', [0.52, 0.48, 1])
    op('oscout1').sendOSC('/sam/point', [0.48, 0.52, 1])

    # Add negative points outside
    op('oscout1').sendOSC('/sam/point', [0.3, 0.3, 0])
```

### Mode Switching Workflow

```python
class SegmentationController:
    def __init__(self, osc_out):
        self.osc = osc_out
        self.current_mode = None

    def setMode(self, mode):
        """Switch modes and clear prompts"""
        if mode != self.current_mode:
            self.osc.sendOSC('/sam/mode', [mode])
            self.osc.sendOSC('/sam/clear', [])
            self.current_mode = mode

    def quickPoint(self, u, v):
        """Quick point segmentation"""
        self.setMode('point')
        self.osc.sendOSC('/sam/point', [u, v, 1])

    def quickBox(self, u1, v1, u2, v2):
        """Quick box segmentation"""
        self.setMode('box')
        self.osc.sendOSC('/sam/box', [u1, v1, u2, v2])
```

## Visualization Tips

### Overlay Masks on Original

```
Network:
[Original Video] → [Over TOP]
                      ↑
[SAM Syphon In] ──────┘
```

Set Over TOP blend mode to visualize masks over original video.

### Extract Mask Channel

Use a **Select TOP** to extract the mask channel (usually green channel where mask overlay is applied).

### Create Multiple Mask Layers

```python
# Send multiple prompts for different objects
op('oscout1').sendOSC('/sam/mode', ['point'])

# Object 1
op('oscout1').sendOSC('/sam/point', [0.3, 0.3, 1])
# Wait, capture mask

# Clear and get Object 2
op('oscout1').sendOSC('/sam/clear', [])
op('oscout1').sendOSC('/sam/point', [0.7, 0.7, 1])
# Wait, capture mask
```

## Performance Optimization

### Reduce Processing Frequency

The server processes every 30 frames by default. Adjust in `sam_server_syphon.py`:

```python
if frame_count % 30 == 0:  # Change to 60 for less frequent updates
    mask_viz = process_frame_with_sam(predictor, frame, osc_send)
```

### Lower Resolution

Reduce WIDTH/HEIGHT in the server configuration for faster processing:

```python
WIDTH, HEIGHT = 1280, 720  # Instead of 1920x1080
```

### Use Smaller Model

```python
SAM2_CHECKPOINT = "facebook/sam2-hiera-small"
```

## Common Patterns

### Click-and-Hold Tracking

```python
# Track an object across frames
# (Will be enhanced with SAM 2 video mode)

def onObjectClick(u, v):
    # Initial segmentation
    op('oscout1').sendOSC('/sam/mode', ['point'])
    op('oscout1').sendOSC('/sam/point', [u, v, 1])

    # TODO: Add video tracking mode
```

### Batch Processing

```python
# Segment multiple regions
regions = [
    (0.25, 0.25, 0.45, 0.45),  # Top-left
    (0.55, 0.25, 0.75, 0.45),  # Top-right
    (0.25, 0.55, 0.45, 0.75),  # Bottom-left
    (0.55, 0.55, 0.75, 0.75),  # Bottom-right
]

op('oscout1').sendOSC('/sam/mode', ['box'])

for x1, y1, x2, y2 in regions:
    op('oscout1').sendOSC('/sam/box', [x1, y1, x2, y2])
    # Wait for processing, capture result
    # Clear and continue
    op('oscout1').sendOSC('/sam/clear', [])
```

## Troubleshooting

### Coordinates Not Working?

- Ensure coordinates are normalized (0.0 to 1.0)
- Check video resolution matches server config
- Verify Syphon coordinate system (origin may be flipped)

### Slow Response?

- Check OSC port conflicts
- Verify server is running and connected
- Monitor console output for errors
- Try smaller model or lower resolution

### No Mask Output?

- Ensure valid prompts are sent
- Check mode is set correctly
- Verify point/box coordinates are within bounds
- Look for error messages in server console

## Next Steps

- Experiment with different prompt combinations
- Build custom UI for your workflow
- Integrate with other TD operators for creative effects
- Explore video tracking mode (coming soon)
