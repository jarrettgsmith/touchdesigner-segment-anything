# SAM 2 (Segment Anything) for TouchDesigner

Real-time video segmentation from TouchDesigner using Meta's SAM 2 model via Syphon (video) and OSC (prompts/data).

## Features

- **Syphon video I/O** - GPU texture sharing for input and output
- **OSC prompt control** - TouchDesigner-native protocol for interactive segmentation
- **Multiple modes** - Automatic, point-based, and box-based segmentation
- **Real-time feedback** - Mask statistics and visualization

## Quick Start

### 1. Setup (First Time)

```bash
./setup.sh
```

This will:
- Create a virtual environment
- Install PyTorch with CUDA/MPS support
- Install SAM 2 from the official repository
- Install Syphon and OSC dependencies

**Note:** First run will download the SAM 2 checkpoint (~900MB), so be patient!

### 2. Run Server

```bash
./run.sh
```

### 3. TouchDesigner Setup

#### Video Input (Syphon Out TOP)
1. Create **Syphon Out TOP**
2. Set **Server Name**: `TD Video Out`
3. Connect your video source

#### Mask Output (Syphon In TOP)
1. Create **Syphon In TOP**
2. Set **Server Name**: `SAM 2 Masks`
3. This will show the segmentation masks

#### Control (OSC Out DAT)
1. Create **OSC Out DAT**
2. Set **Network Port**: `7001`
3. Set **Network Address**: `127.0.0.1`

#### Data (OSC In CHOP)
1. Create **OSC In CHOP**
2. Set **Port**: `7000`
3. Set **Network Address**: `*`

## OSC Commands

All OSC commands are sent to **port 7001** on **127.0.0.1**.

### Segmentation Modes

```
/sam/mode "auto"     # Automatic segmentation (segment everything)
/sam/mode "point"    # Point-based prompts (click to segment)
/sam/mode "box"      # Box-based prompts (drag to segment)
```

**TouchDesigner Example:**
```python
# In TouchDesigner Script DAT or Execute DAT
op('oscout1').sendOSC('/sam/mode', ['point'])
```

### Point Prompts

```
/sam/point <x> <y> <label>

x, y:  Normalized coordinates (0.0 - 1.0)
       0,0 = top-left, 1,1 = bottom-right
label: 1 = include (positive), 0 = exclude (negative)
```

**TouchDesigner Examples:**
```python
# Segment object at center of frame
op('oscout1').sendOSC('/sam/point', [0.5, 0.5, 1])

# Add positive point on object
op('oscout1').sendOSC('/sam/point', [0.3, 0.4, 1])

# Add negative point to exclude background
op('oscout1').sendOSC('/sam/point', [0.1, 0.1, 0])

# Use mouse coordinates (convert from pixels to normalized)
x_norm = me.inputCellAttribs[0].vals[0] / 1920  # Assuming 1920x1080
y_norm = me.inputCellAttribs[0].vals[1] / 1080
op('oscout1').sendOSC('/sam/point', [x_norm, y_norm, 1])
```

### Box Prompts

```
/sam/box <x1> <y1> <x2> <y2>

All coordinates normalized (0.0 - 1.0)
x1, y1 = top-left corner
x2, y2 = bottom-right corner
```

**TouchDesigner Examples:**
```python
# Segment center region
op('oscout1').sendOSC('/sam/box', [0.25, 0.25, 0.75, 0.75])

# Segment left half
op('oscout1').sendOSC('/sam/box', [0.0, 0.0, 0.5, 1.0])

# Segment top-right quadrant
op('oscout1').sendOSC('/sam/box', [0.5, 0.0, 1.0, 0.5])
```

### Clear Prompts

```
/sam/clear
```

Removes all point/box prompts. Useful when starting a new segmentation.

**TouchDesigner Example:**
```python
op('oscout1').sendOSC('/sam/clear', [])
```

## OSC Feedback Channels

### Mask Statistics
```
/sam/masks/count          # Number of masks generated
/sam/mask/0/score         # Confidence score (0.0 - 1.0)
/sam/mask/0/area          # Normalized area (0.0 - 1.0)
```

## Configuration

Edit `sam_server_syphon.py`:

```python
WIDTH, HEIGHT = 1920, 1080
SYPHON_INPUT_NAME = "TD Video Out"
SYPHON_OUTPUT_NAME = "SAM 2 Masks"
OSC_RECEIVE_PORT = 7001
OSC_SEND_PORT = 7000
SAM2_CHECKPOINT = "facebook/sam2-hiera-large"  # or other models
```

### SAM 2 Model Options

- `facebook/sam2-hiera-tiny` - Fastest, lower quality
- `facebook/sam2-hiera-small` - Balanced
- `facebook/sam2-hiera-base-plus` - Good quality
- `facebook/sam2-hiera-large` - Best quality (default)

## Requirements

- macOS (for Syphon)
- Python 3.10+
- CUDA-capable GPU (recommended) or Apple Silicon (MPS)
- TouchDesigner
- ~2GB free space for model checkpoints

## Workflow Examples

### Interactive Segmentation

1. Set mode to point:
   ```
   /sam/mode "point"
   ```

2. Click on objects in TD (send normalized coordinates):
   ```
   /sam/point 0.5 0.3 1  # Positive point
   /sam/point 0.6 0.4 1  # Another positive point
   /sam/point 0.2 0.8 0  # Negative point (exclude)
   ```

3. Masks appear in real-time via Syphon

### Box Selection

1. Set mode to box:
   ```
   /sam/mode "box"
   ```

2. Send bounding box:
   ```
   /sam/box 0.25 0.25 0.75 0.75
   ```

### Automatic Segmentation

1. Set mode to auto:
   ```
   /sam/mode "auto"
   ```

2. SAM 2 will automatically segment all objects (coming soon)

## Performance Notes

- GPU recommended for real-time performance
- Processing runs every 30 frames by default (configurable)
- First inference is slower due to model warmup
- Mask generation time varies by complexity

## Files

```
sam_server_syphon.py    # Main server
requirements.txt        # Python dependencies
setup.sh                # Setup script
run.sh                  # Run script
venv_sam/               # Virtual environment (created by setup)
external/               # Reference SAM 2 repo (optional)
```

## Troubleshooting

### No video input?

Make sure your TouchDesigner Syphon Out TOP has the exact server name `TD Video Out`

### Model download fails?

Check your internet connection. The checkpoint is ~900MB and may take time.

### CUDA out of memory?

Try a smaller model:
```python
SAM2_CHECKPOINT = "facebook/sam2-hiera-small"
```

### OSC not responding?

1. Check port conflicts (7000/7001)
2. Verify OSC Out DAT network settings
3. Check firewall settings

## Architecture

Following the [TouchDesigner External Tool Integration Pattern](../ARCHITECTURE_PATTERNS.md):

```
TouchDesigner                      SAM 2 Server
┌──────────────┐                  ┌──────────────┐
│ Syphon Out   │─────Video───────>│ Syphon In    │
│              │                  │              │
│ Syphon In    │<────Masks────────│ Syphon Out   │
│              │                  │              │
│ OSC Out      │────Prompts──────>│ OSC In       │
│              │                  │ (Port 7001)  │
│ OSC In       │<────Stats────────│ OSC Out      │
│ (Port 7000)  │                  │              │
└──────────────┘                  └──────────────┘
```

## Future Enhancements

- [ ] Automatic mask generation mode
- [ ] Video tracking (SAM 2 video mode)
- [ ] Multiple object tracking
- [ ] Mask refinement controls
- [ ] Export masks as separate layers
- [ ] TouchDesigner .toe example file

## License

MIT

## Credits

- SAM 2 by Meta AI Research: https://github.com/facebookresearch/sam2
- TouchDesigner integration pattern inspired by depthai-handtracking
