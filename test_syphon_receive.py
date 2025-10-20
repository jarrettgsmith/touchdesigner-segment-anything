#!/usr/bin/env python3
"""
Simple test: Receive Syphon from TouchDesigner and display in OpenCV window
"""

import syphon
from syphon.utils.numpy import copy_mtl_texture_to_image
import cv2
import numpy as np
import time

# Configuration
SYPHON_INPUT_NAME = "TD Video Out"
WIDTH, HEIGHT = 1920, 1080

print("=" * 70)
print("Syphon Receive Test")
print("=" * 70)

# Create server directory
print(f"\n[1/3] Looking for Syphon servers...")
directory = syphon.SyphonServerDirectory()
servers = directory.servers

print(f"Found {len(servers)} Syphon server(s):")
for i, server in enumerate(servers):
    print(f"  {i+1}. Name: '{server.name}' App: '{server.app_name}'")

# Look for our specific server
print(f"\n[2/3] Looking for server named '{SYPHON_INPUT_NAME}'...")
matching = directory.servers_matching_name(name=SYPHON_INPUT_NAME)

if not matching:
    print(f"\nERROR: No server named '{SYPHON_INPUT_NAME}' found!")
    print("\nTo fix:")
    print("1. Open TouchDesigner")
    print("2. Create a Syphon Out TOP")
    print("3. Set Server Name to: 'TD Video Out'")
    print("4. Connect a video source (webcam, movie, etc.)")
    exit(1)

# Create client
server_desc = matching[0]
print(f"Found: '{server_desc.name}' from '{server_desc.app_name}'")
print(f"\n[3/3] Creating Syphon client...")

try:
    client = syphon.SyphonMetalClient(server_desc)
    print("✓ Client created!")
except Exception as e:
    print(f"ERROR: Could not create client: {e}")
    exit(1)

print("\n" + "=" * 70)
print("Receiving video... (Press 'q' to quit)")
print("=" * 70)

frame_count = 0

try:
    while True:
        # Check for new frame (it's a property, not a method)
        if client.has_new_frame:
            # Get frame from Syphon (also a property)
            syphon_frame = client.new_frame_image
        else:
            syphon_frame = None

        if syphon_frame is not None:
            # Convert Metal texture to numpy array
            frame_bgra = copy_mtl_texture_to_image(syphon_frame)

            # Convert BGRA to BGR for OpenCV
            frame_bgr = cv2.cvtColor(frame_bgra, cv2.COLOR_BGRA2BGR)

            # Flip vertically (Syphon coordinate system)
            frame_bgr = cv2.flip(frame_bgr, 0)

            # Display
            cv2.imshow("Syphon Input from TouchDesigner", frame_bgr)

            frame_count += 1
            if frame_count % 100 == 0:
                print(f"Frames received: {frame_count}")
        else:
            # No frame yet
            if frame_count == 0:
                print("Waiting for frames...")

        # Check for quit
        key = cv2.waitKey(1)
        if key == ord('q'):
            break

        time.sleep(0.001)

except KeyboardInterrupt:
    print("\nCtrl+C received")

finally:
    cv2.destroyAllWindows()
    print(f"\nTotal frames: {frame_count}")
    print("Done!")
