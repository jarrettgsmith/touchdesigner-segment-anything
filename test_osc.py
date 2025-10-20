#!/usr/bin/env python3
"""
Quick OSC test - send a test message to the SAM server
"""

from pythonosc import udp_client
import time

OSC_IP = "127.0.0.1"
OSC_PORT = 7001

print(f"Testing OSC connection to {OSC_IP}:{OSC_PORT}")
print("Make sure the SAM server is running!")
print()

client = udp_client.SimpleUDPClient(OSC_IP, OSC_PORT)

print("Sending test messages...")
print("1. Mode change to 'point'")
client.send_message("/sam/mode", "point")
time.sleep(0.5)

print("2. Test point at (0.5, 0.5)")
client.send_message("/sam/point", [0.5, 0.5, 1])
time.sleep(0.5)

print("3. Clear")
client.send_message("/sam/clear", [])

print()
print("Done! Check the SAM server console for output.")
