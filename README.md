# Meshtastic TUI

A terminal-based user interface (TUI) for interacting with [Meshtastic](https://meshtastic.org/) devices via USB. This lightweight dashboard lets you monitor nodes, view channels, and chat directly from your terminal.

![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)

This is an independent community project and has no official connection to the Meshtastic core team.

![Screenshot](screenshot.png)

## Features

* **Live Node Monitoring:** View connected nodes, their hardware models, SNR, hops, and "last seen" status in real-time.
* **Channel Management:** See available channels and their roles (Primary/Secondary).
* **Interactive UI:**
  * Click on a node in the table to prepare a Direct Message (DM).
  * Click on a channel in the table (or use keyboard arrows + Enter) to switch your active sending channel.
* **Chat Log:** Keep track of incoming and outgoing messages. Messages are also saved to `meshtastic_chatlog.txt`.
* **Bilingual Support:** Available in German (default) and English.

**Important note**
As long as the node is connected to the app, messages will not appear in the history, i.e., they will **not be visible** in the smartphone app. This applies to both sent and received messages.

## Requirements

Ensure you have Python 3 installed. You will need the following libraries:

```
pip install textual meshtastic pypubsub
```

## Usage

Connect your Meshtastic device via USB and run the script. The application will automatically attempt to connect to the node.

### Start in German (Default):

```
python meshtui.py
```

### Start in English:

```
python meshtui.py --en
```

### Controls & Commands

```
* q - Quit the application.
* c - Focus the chat input field.
* Click Node - Pre-fills the chat input with /dm <Node-ID> to send a direct message.
* Click Channel - Switches your active sending channel to the selected one.
```

### Chat Commands:

```
* /ch <index> - Switch the active channel manually (e.g., /ch 1).
* /dm <Node-ID> <message> - Send a direct message to a specific node.
* /rename <index> <name> - Rename a channel on your local node.
```

## License

This project is licensed under the GNU General Public License v3.0.

Copyright (C) 2026 der-bender
