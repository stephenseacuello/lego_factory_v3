# Installing the LegoMCP Fusion 360 Add-in

## Automatic Installation

### Windows
1. Copy the `LegoMCP` folder to:
   ```
   %APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\
   ```

### macOS
1. Copy the `LegoMCP` folder to:
   ```
   ~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/
   ```

### Linux
1. Copy the `LegoMCP` folder to:
   ```
   ~/.local/share/Autodesk/Autodesk Fusion 360/API/AddIns/
   ```

## Manual Installation

1. Open Fusion 360
2. Click **Tools** in the top toolbar
3. Select **Add-Ins** → **Scripts and Add-Ins** (or press `Shift+S`)
4. In the dialog, click the **Add-Ins** tab
5. Click the green **+** button next to "My Add-Ins"
6. Navigate to and select the `LegoMCP` folder
7. Click **Select Folder** (Windows) or **Open** (Mac)

## Running the Add-in

1. In the Scripts and Add-Ins dialog, find **LegoMCP** in the list
2. Check the **Run on Startup** checkbox (recommended)
3. Click **Run**

You should see a confirmation message:
> LegoMCP Add-in Started!
> HTTP API running on http://localhost:8765
> Ready to receive commands from MCP server.

## Verifying Installation

Open a terminal and run:
```bash
curl http://localhost:8765/health
```

Expected response:
```json
{"status": "ok", "service": "LegoMCP Fusion360", "version": "1.0.0"}
```

## Troubleshooting

### Add-in doesn't appear in list
- Ensure the folder structure is correct: `LegoMCP/LegoMCP.py` and `LegoMCP/LegoMCP.manifest`
- Restart Fusion 360

### Add-in fails to start
- Open Fusion 360's **Text Commands** window (View → Text Commands)
- Run the add-in and check for error messages
- Common issues:
  - Port 8765 already in use
  - Missing Python dependencies (shouldn't happen with Fusion's bundled Python)

### HTTP API not responding
- Check Windows Firewall / macOS firewall settings
- Ensure no other service is using port 8765
- Try restarting the add-in

## Stopping the Add-in

1. Go to **Tools** → **Add-Ins** → **Scripts and Add-Ins**
2. Select **LegoMCP**
3. Click **Stop**

The HTTP server will stop and you'll see a confirmation message.

## Updating the Add-in

1. Stop the running add-in
2. Replace the files in the LegoMCP folder
3. Restart Fusion 360 or manually run the add-in again
