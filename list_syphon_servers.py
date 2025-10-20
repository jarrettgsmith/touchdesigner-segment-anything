#!/usr/bin/env python3
"""
List all available Syphon servers
Run this to see what's broadcasting
"""

import syphon

print("Available Syphon Servers:")
print("=" * 50)

try:
    # Create server directory
    directory = syphon.SyphonServerDirectory()

    # Get all servers
    servers = directory.servers

    if servers:
        for i, server in enumerate(servers):
            print(f"{i+1}. Name: '{server.name}' App: '{server.app_name}'")
    else:
        print("No Syphon servers found!")
        print("\nMake sure:")
        print("1. TouchDesigner is running")
        print("2. You have a Syphon Out TOP active")
        print("3. The Syphon Out TOP is connected to video")

    print(f"\nTotal servers: {len(servers)}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("=" * 50)
