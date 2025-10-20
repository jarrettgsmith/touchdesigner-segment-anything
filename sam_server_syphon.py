#!/usr/bin/env python3
"""
SAM 2 Server for TouchDesigner
Video I/O: Syphon (bidirectional)
Control/Data: OSC (TouchDesigner-friendly)
"""

import cv2
import numpy as np
import torch
import signal
import sys
import os
import time
from pathlib import Path
from pythonosc import udp_client, dispatcher, osc_server
import threading
import syphon
from syphon.utils.numpy import copy_image_to_mtl_texture, copy_mtl_texture_to_image
from syphon.utils.raw import create_mtl_texture

# SAM 2 imports
from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor

# Global flag for clean shutdown
running = True

def signal_handler(sig, frame):
    """Handle interrupt signals"""
    global running
    if running:
        print("\n[Shutdown] Interrupt signal received...")
        running = False
    else:
        # Force exit on second Ctrl+C
        print("\n[Shutdown] Force exit")
        os._exit(1)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

print("=" * 70)
print("SAM 2 Server → Syphon + OSC")
print("=" * 70)

# Configuration
WIDTH, HEIGHT = 1920, 1080
SYPHON_INPUT_NAME = "TD Video Out"  # Receive video from TouchDesigner
SYPHON_OUTPUT_NAME = "SAM 2 Masks"  # Send masks to TouchDesigner
OSC_RECEIVE_PORT = 7001  # Receive prompts from TD
OSC_SEND_IP = "127.0.0.1"
OSC_SEND_PORT = 7000  # Send mask data to TD

# SAM 2 Configuration
SAM2_CHECKPOINT = "facebook/sam2-hiera-tiny"  # Use tiny model for better performance
# Force CPU - MPS has issues with SAM 2
DEVICE = "cpu"  # "cuda" if torch.cuda.is_available() else "cpu"

print(f"\n[Config] Video Input: Syphon '{SYPHON_INPUT_NAME}'")
print(f"[Config] Mask Output: Syphon '{SYPHON_OUTPUT_NAME}'")
print(f"[Config] OSC Receive: Port {OSC_RECEIVE_PORT}")
print(f"[Config] OSC Send: {OSC_SEND_IP}:{OSC_SEND_PORT}")
print(f"[Config] Device: {DEVICE}")

# Global state for prompts
class PromptState:
    def __init__(self):
        self.mode = "auto"  # "auto", "point", "box"
        self.points = []
        self.labels = []  # 1 for positive, 0 for negative
        self.box = None
        self.lock = threading.RLock()  # Reentrant lock to avoid deadlock when methods call each other
        self.needs_update = False  # Flag to trigger immediate processing

    def clear(self):
        with self.lock:
            self.points = []
            self.labels = []
            self.box = None
            self.needs_update = True

    def add_point(self, x, y, label=1):
        with self.lock:
            self.points.append([x, y])
            self.labels.append(label)
            self.needs_update = True

    def set_box(self, x1, y1, x2, y2):
        with self.lock:
            self.box = [x1, y1, x2, y2]
            self.needs_update = True

    def set_mode(self, mode):
        with self.lock:
            self.mode = mode
            self.clear()
            self.needs_update = True

    def consume_update_flag(self):
        with self.lock:
            needs = self.needs_update
            self.needs_update = False
            return needs

prompt_state = PromptState()

# OSC Handlers
def handle_mode(unused_addr, mode):
    """Set segmentation mode: auto, point, box"""
    print(f"[OSC] ✓ Received mode change: '{mode}'")
    try:
        prompt_state.set_mode(mode)
        print(f"[OSC] ✓ Mode changed successfully to '{mode}'")
    except Exception as e:
        print(f"[OSC] ERROR in set_mode: {e}")
        import traceback
        traceback.print_exc()

def handle_point(unused_addr, x, y, label=1):
    """Add point prompt (normalized 0-1 coordinates)"""
    px, py = int(x * WIDTH), int(y * HEIGHT)
    print(f"[OSC] ✓ Received point: ({px}, {py}) label={label}")
    try:
        prompt_state.add_point(px, py, label)
        print(f"[OSC] ✓ Point added successfully")
    except Exception as e:
        print(f"[OSC] ERROR in add_point: {e}")
        import traceback
        traceback.print_exc()

def handle_box(unused_addr, x1, y1, x2, y2):
    """Add box prompt (normalized 0-1 coordinates)"""
    bx1, by1 = int(x1 * WIDTH), int(y1 * HEIGHT)
    bx2, by2 = int(x2 * WIDTH), int(y2 * HEIGHT)
    print(f"[OSC] ✓ Received box: ({bx1}, {by1}) to ({bx2}, {by2})")
    try:
        prompt_state.set_box(bx1, by1, bx2, by2)
        print(f"[OSC] ✓ Box set successfully")
    except Exception as e:
        print(f"[OSC] ERROR in set_box: {e}")
        import traceback
        traceback.print_exc()

def handle_clear(unused_addr):
    """Clear all prompts"""
    print("[OSC] ✓ Received clear command")
    try:
        prompt_state.clear()
        print("[OSC] ✓ Cleared successfully")
    except Exception as e:
        print(f"[OSC] ERROR in clear: {e}")
        import traceback
        traceback.print_exc()

def handle_any(addr, *args):
    """Catch-all handler for debugging"""
    print(f"[OSC] ✓ Received message: {addr} with args: {args}")

def create_osc_server():
    """Create OSC server for receiving prompts"""
    disp = dispatcher.Dispatcher()
    disp.map("/sam/mode", handle_mode)
    disp.map("/sam/point", handle_point)
    disp.map("/sam/box", handle_box)
    disp.map("/sam/clear", handle_clear)
    disp.set_default_handler(handle_any)  # Catch all other messages for debugging

    server = osc_server.ThreadingOSCUDPServer(
        ("0.0.0.0", OSC_RECEIVE_PORT), disp
    )
    return server

def process_frame_with_sam(predictor, frame, osc_client):
    """
    Process frame with SAM 2 based on current prompt state
    Returns mask visualization
    """
    with prompt_state.lock:
        mode = prompt_state.mode
        points = np.array(prompt_state.points) if prompt_state.points else None
        labels = np.array(prompt_state.labels) if prompt_state.labels else None
        box = np.array(prompt_state.box) if prompt_state.box else None

    # Set image for prediction
    predictor.set_image(frame)

    if mode == "auto":
        # Automatic segmentation - segment everything
        # For now, just return the original frame
        # TODO: Implement automatic mask generation
        mask_viz = frame.copy()
        osc_client.send_message("/sam/masks/count", 0)

    elif mode == "point" and points is not None and len(points) > 0:
        # Point-based segmentation
        masks, scores, _ = predictor.predict(
            point_coords=points,
            point_labels=labels,
            multimask_output=True
        )

        # Use best mask
        best_mask = masks[np.argmax(scores)].astype(bool)  # Convert to boolean for indexing
        best_score = scores[np.argmax(scores)]

        print(f"[SAM] Point segmentation: {len(points)} point(s), score: {best_score:.3f}")

        # Create colored mask overlay
        mask_viz = frame.copy()
        mask_viz[best_mask] = mask_viz[best_mask] * 0.5 + np.array([0, 255, 0]) * 0.5

        # Draw points
        for (x, y), label in zip(points, labels):
            color = (0, 255, 0) if label == 1 else (255, 0, 0)
            cv2.circle(mask_viz, (int(x), int(y)), 8, color, -1)

        # Send mask statistics
        osc_client.send_message("/sam/masks/count", 1)
        osc_client.send_message("/sam/mask/0/score", float(best_score))
        osc_client.send_message("/sam/mask/0/area", float(np.sum(best_mask)) / (WIDTH * HEIGHT))

    elif mode == "box" and box is not None:
        # Box-based segmentation
        masks, scores, _ = predictor.predict(
            box=box,
            multimask_output=False
        )

        mask = masks[0].astype(bool)  # Convert to boolean for indexing

        # Create colored mask overlay
        mask_viz = frame.copy()
        mask_viz[mask] = mask_viz[mask] * 0.5 + np.array([0, 255, 255]) * 0.5

        # Draw box
        cv2.rectangle(mask_viz,
                     (int(box[0]), int(box[1])),
                     (int(box[2]), int(box[3])),
                     (0, 255, 255), 2)

        # Send mask statistics
        osc_client.send_message("/sam/masks/count", 1)
        osc_client.send_message("/sam/mask/0/score", float(scores[0]))
        osc_client.send_message("/sam/mask/0/area", float(np.sum(mask)) / (WIDTH * HEIGHT))

    else:
        # No valid prompts, return original
        mask_viz = frame.copy()
        osc_client.send_message("/sam/masks/count", 0)

    return mask_viz

def main():
    global running

    # Initialize SAM 2
    print(f"\n[SAM 2] Loading model from {SAM2_CHECKPOINT}...")
    print("[SAM 2] This may take a while on first run (downloading checkpoint)...")

    try:
        predictor = SAM2ImagePredictor.from_pretrained(SAM2_CHECKPOINT, device=DEVICE)
        print("[SAM 2] ✓ Model loaded")
    except Exception as e:
        print(f"[SAM 2] Error loading model: {e}")
        print("[SAM 2] Trying alternative checkpoint...")
        # Fallback to local checkpoint if available
        checkpoint = "checkpoints/sam2_hiera_large.pt"
        config = "sam2_hiera_l.yaml"
        if Path(checkpoint).exists():
            predictor = SAM2ImagePredictor(build_sam2(config, checkpoint, device=DEVICE))
            print("[SAM 2] ✓ Model loaded from local checkpoint")
        else:
            print("[SAM 2] Failed to load model. Please check installation.")
            return

    # Create Syphon client for input
    print(f"\n[Syphon] Looking for input server '{SYPHON_INPUT_NAME}'...")
    syphon_in = None
    syphon_directory = None

    try:
        # Create server directory
        syphon_directory = syphon.SyphonServerDirectory()

        # Look for the server by name
        servers = syphon_directory.servers_matching_name(name=SYPHON_INPUT_NAME)

        if servers:
            server_desc = servers[0]
            print(f"[Syphon] Found server: '{server_desc.name}' from '{server_desc.app_name}'")
            syphon_in = syphon.SyphonMetalClient(server_desc)
            print("[Syphon] ✓ Input client created")
        else:
            print(f"[Syphon] No server named '{SYPHON_INPUT_NAME}' found")
            print("[Syphon] Will use test frames. Create a Syphon Out TOP in TD with this name.")

    except Exception as e:
        print(f"[Syphon] Warning: Could not create input client: {e}")
        print("[Syphon] Will use test frames instead")
        syphon_in = None

    # Create Syphon server for output
    print(f"[Syphon] Creating output server '{SYPHON_OUTPUT_NAME}'...")
    syphon_out = syphon.SyphonMetalServer(SYPHON_OUTPUT_NAME)
    texture = create_mtl_texture(syphon_out.device, WIDTH, HEIGHT)
    print("[Syphon] ✓ Output server created")

    # Create OSC client for sending data
    print(f"\n[OSC] Creating send client {OSC_SEND_IP}:{OSC_SEND_PORT}...")
    osc_send = udp_client.SimpleUDPClient(OSC_SEND_IP, OSC_SEND_PORT)
    print("[OSC] ✓ Send client created")

    # Create OSC server for receiving prompts
    print(f"[OSC] Creating receive server on port {OSC_RECEIVE_PORT}...")
    osc_recv_server = create_osc_server()
    print("[OSC] ✓ Receive server created")

    # Start OSC server in background thread
    osc_thread = threading.Thread(target=osc_recv_server.serve_forever, daemon=True)
    osc_thread.start()
    print("[OSC] ✓ Receive server started")

    print(f"\n[Ready] Waiting for Syphon input '{SYPHON_INPUT_NAME}'...")
    print("=" * 70)
    print(f"TouchDesigner Setup:")
    print(f"  1. Syphon Out TOP - Server: '{SYPHON_INPUT_NAME}'")
    print(f"  2. Syphon In TOP - Server: '{SYPHON_OUTPUT_NAME}'")
    print(f"  3. OSC Out DAT - Port: {OSC_RECEIVE_PORT}")
    print(f"     Commands: /sam/mode <auto|point|box>")
    print(f"               /sam/point <x> <y> <label>")
    print(f"               /sam/box <x1> <y1> <x2> <y2>")
    print(f"  4. OSC In CHOP - Port: {OSC_SEND_PORT}")
    print("=" * 70)
    print("Press Ctrl+C to quit\n")

    frame_count = 0
    dummy_frame = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)
    last_frame = None  # Keep last valid frame to avoid noise
    last_mask_viz = None  # Keep last processed visualization for smooth display

    try:
        while running:
            # Try to get frame from Syphon input
            frame = None

            if syphon_in is not None:
                try:
                    # Try to get frame from Syphon (both are properties, not methods)
                    if syphon_in.has_new_frame:
                        syphon_frame = syphon_in.new_frame_image
                    else:
                        syphon_frame = None

                    if syphon_frame is not None:
                        # Convert Metal texture to numpy array
                        frame_bgra = copy_mtl_texture_to_image(syphon_frame)
                        # Convert from BGRA to RGB
                        frame = cv2.cvtColor(frame_bgra, cv2.COLOR_BGRA2RGB)
                        # Flip back from Syphon coordinate system
                        frame = cv2.flip(frame, 0)
                        last_frame = frame.copy()  # Save for reuse

                        if frame_count == 0:
                            print("[Syphon] ✓ Receiving video frames from TouchDesigner")
                        elif frame_count % 300 == 0:
                            print(f"[Syphon] Still receiving frames... (frame {frame_count})")
                except Exception as e:
                    if frame_count % 100 == 0:
                        print(f"[Syphon] Warning: Could not read frame: {e}")

            # Reuse last frame if no new input
            if frame is None:
                if last_frame is not None:
                    frame = last_frame  # Reuse last valid frame
                else:
                    # Only use test pattern on very first frame if no input
                    if frame_count == 0:
                        print("[Syphon] No input detected, waiting for video...")
                    test_frame = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)  # Black frame instead of noise
                    frame = test_frame

            # Process frame with SAM 2
            # Process every 30 frames OR when prompts change
            needs_update = prompt_state.consume_update_flag()

            if needs_update or (frame_count % 30 == 0):
                if needs_update:
                    print(f"[SAM] Prompt changed, processing immediately...")

                try:
                    mask_viz = process_frame_with_sam(predictor, frame, osc_send)
                    last_mask_viz = mask_viz.copy()  # Save for reuse
                except Exception as e:
                    print(f"[ERROR] SAM processing failed: {e}")
                    import traceback
                    traceback.print_exc()
                    mask_viz = frame
            else:
                # Reuse last processed visualization for smooth playback
                if last_mask_viz is not None:
                    mask_viz = last_mask_viz
                else:
                    mask_viz = frame

            # Send output to Syphon (flip vertical for Syphon coordinate system)
            try:
                flipped = cv2.flip(mask_viz, 0)
                bgra_frame = cv2.cvtColor(flipped, cv2.COLOR_BGR2BGRA)  # OpenCV uses BGR, not RGB
                copy_image_to_mtl_texture(bgra_frame, texture)
                syphon_out.publish_frame_texture(texture)
            except Exception as e:
                print(f"[ERROR] Syphon send failed: {e}")
                import traceback
                traceback.print_exc()

            frame_count += 1
            if frame_count % 300 == 0:
                print(f"[Status] Frames: {frame_count}, Mode: {prompt_state.mode}")

            # Small delay to prevent CPU spinning (don't use cv2.waitKey as it can hang)
            time.sleep(0.001)

    except KeyboardInterrupt:
        print("\n[Shutdown] Ctrl+C received")
        running = False
    finally:
        print("\n[Shutdown] Cleaning up...")
        try:
            if 'osc_recv_server' in locals():
                osc_recv_server.shutdown()
            if 'osc_thread' in locals():
                osc_thread.join(timeout=1.0)
        except Exception as e:
            pass
        print(f"[Stats] Total frames: {frame_count}")
        print("[Shutdown] Done")
        sys.exit(0)

if __name__ == "__main__":
    main()
