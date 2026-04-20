#!/usr/bin/env python3
# Meshtastic TUI - A terminal interface for Meshtastic devices
# Copyright (C) 2026 der-bender
# Licensed under the GNU General Public License v3.0

import sys
import time
from datetime import datetime
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Log, Input, Label
from textual.containers import Horizontal, Vertical
from textual import work
import meshtastic
import meshtastic.serial_interface
from meshtastic import channel_pb2
from pubsub import pub

TRANSLATIONS = {
    "de": {
        "col_user": "User", "col_id": "ID", "col_aka": "AKA", "col_hw": "HW", "col_hops": "Hops", "col_snr": "SNR", "col_last": "Zuletzt",
        "col_idx": "Idx", "col_chname": "Kanalname", "col_role": "Rolle",
        "log_start": "\n--- TUI GESTARTET: {} ---",
        "sys_conn": "[SYSTEM] Verbinde mit Node via USB...",
        "sys_conn_ok": "[SYSTEM] Erfolgreich verbunden!",
        "sys_conn_err": "[FEHLER] Verbindung fehlgeschlagen: {}",
        "sys_dm_ready": "[SYSTEM] Bereit für private Nachricht an {}. Text eingeben und Enter drücken...",
        "sys_ch_switch": "[SYSTEM] Gewechselt auf Kanal-Index {}. Neue Nachrichten landen jetzt hier.",
        "err_invalid_cmd": "[FEHLER] Ungültiger Befehl. Nutze: /ch <nummer>",
        "err_rename": "[FEHLER] Umbenennen fehlgeschlagen: {}",
        "sys_renamed": "[SYSTEM] Kanal {} wurde in '{}' umbenannt.",
        "err_dm_args": "[FEHLER] Zu wenig Argumente. Nutze: /dm <Node-ID> <Nachricht>",
        "err_dm_fail": "[FEHLER] DM fehlgeschlagen: {}",
        "err_not_conn": "[FEHLER] Nicht verbunden. Kann nicht senden.",
        "err_send_fail": "[FEHLER] Senden fehlgeschlagen: {}",
        "placeholder": "Nachricht... (/ch <idx>, /dm <ID>)",
        "time_days": "T", "time_hours": "h", "time_mins": "m", "time_secs": "s",
        "never": "Nie", "you": "DU", "primary": "Primary", "secondary": "Secondary"
    },
    "en": {
        "col_user": "User", "col_id": "ID", "col_aka": "AKA", "col_hw": "HW", "col_hops": "Hops", "col_snr": "SNR", "col_last": "Last Seen",
        "col_idx": "Idx", "col_chname": "Channel Name", "col_role": "Role",
        "log_start": "\n--- TUI STARTED: {} ---",
        "sys_conn": "[SYSTEM] Connecting to node via USB...",
        "sys_conn_ok": "[SYSTEM] Successfully connected!",
        "sys_conn_err": "[ERROR] Connection failed: {}",
        "sys_dm_ready": "[SYSTEM] Ready for direct message to {}. Enter text and press Enter...",
        "sys_ch_switch": "[SYSTEM] Switched to channel index {}. New messages will land here.",
        "err_invalid_cmd": "[ERROR] Invalid command. Use: /ch <number>",
        "err_rename": "[ERROR] Rename failed: {}",
        "sys_renamed": "[SYSTEM] Channel {} renamed to '{}'.",
        "err_dm_args": "[ERROR] Not enough arguments. Use: /dm <Node-ID> <Message>",
        "err_dm_fail": "[ERROR] DM failed: {}",
        "err_not_conn": "[ERROR] Not connected. Cannot send.",
        "err_send_fail": "[ERROR] Send failed: {}",
        "placeholder": "Message... (/ch <idx>, /dm <ID>)",
        "time_days": "d", "time_hours": "h", "time_mins": "m", "time_secs": "s",
        "never": "Never", "you": "YOU", "primary": "Primary", "secondary": "Secondary"
    }
}

class MeshtasticTUI(App):
    """Ein TUI-Dashboard für Meshtastic-Nodes."""

    TITLE = "Meshtastic TUI"
    SUB_TITLE = "v0.1"
    
    ENABLE_COMMAND_PALETTE = False

    CSS = """
    Horizontal { height: 100%; }
    
    #sidebar { width: 55%; height: 100%; }
    #node_list { height: 70%; border: solid #336699; }
    #channel_list { height: 30%; border: solid #993366; }
    
    #chat_area { width: 45%; height: 100%; }
    #chat_log { height: 1fr; border: solid #339966; }
    
    #input_container { dock: bottom; height: 3; }
    #msg_input { width: 1fr; border: solid #996633; border-right: none; }
    #char_count { width: 9; height: 100%; border: solid #996633; content-align: center middle; }
    """

    BINDINGS = [
        ("q", "quit", "Quit / Beenden"),
        ("c", "focus_chat", "Focus Chat / Chat fokussieren"),
    ]

    def __init__(self):
        super().__init__()
        self.lang = "en" if "--en" in sys.argv else "de"
        self.interface = None
        self.channel_index = 0
        self.log_file = "meshtastic_chatlog.txt"

    def t(self, key: str) -> str:
        """Holt den übersetzten String."""
        return TRANSLATIONS[self.lang].get(key, key)

    def compose(self) -> ComposeResult:
        """Baut die Benutzeroberfläche auf."""
        yield Header()
        with Horizontal():
            # Sidebar für Nodes und Kanäle
            with Vertical(id="sidebar"):
                yield DataTable(id="node_list")
                yield DataTable(id="channel_list")
            
            # Chat-Bereich
            with Vertical(id="chat_area"):
                yield Log(id="chat_log", highlight=True)
                with Horizontal(id="input_container"):
                    yield Input(placeholder=self.t("placeholder"), id="msg_input", max_length=200)
                    yield Label("0/200", id="char_count")
        yield Footer()

    def on_mount(self) -> None:
        """Wird ausgeführt, sobald das TUI startet."""
        # Node-Tabelle einrichten
        node_table = self.query_one("#node_list", DataTable)
        node_table.add_columns(
            self.t("col_user"), self.t("col_id"), self.t("col_aka"), 
            self.t("col_hw"), self.t("col_hops"), self.t("col_snr"), self.t("col_last")
        )
        node_table.zebra_stripes = True
        node_table.cursor_type = "row"

        # Kanal-Tabelle einrichten
        chan_table = self.query_one("#channel_list", DataTable)
        chan_table.add_columns(self.t("col_idx"), self.t("col_chname"), self.t("col_role"))
        chan_table.zebra_stripes = True
        chan_table.cursor_type = "row" # Wichtig für die Auswahl per Tastatur/Maus

        time_str = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
        self.write_log(self.t("log_start").format(time_str))

        self.connect_to_meshtastic()
        self.set_interval(5.0, self.update_data)

    def write_log(self, text: str):
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(text + "\n")
        except Exception:
            pass 
        
        try:
            self.query_one("#chat_log", Log).write_line(text)
        except Exception:
            try:
                self.call_from_thread(self._ui_write_log, text)
            except Exception:
                pass

    def _ui_write_log(self, text: str):
        try:
            self.query_one("#chat_log", Log).write_line(text)
        except Exception:
            pass

    @work(thread=True)
    def connect_to_meshtastic(self):
        self.write_log(self.t("sys_conn"))
        try:
            self.interface = meshtastic.serial_interface.SerialInterface()
            self.write_log(self.t("sys_conn_ok"))
            
            pub.subscribe(self.on_receive_background, "meshtastic.receive")
            self.call_from_thread(self.update_data)
        except Exception as e:
            self.write_log(self.t("sys_conn_err").format(e))

    def on_receive_background(self, packet, interface):
        """Wird aufgerufen, wenn ein Paket ankommt."""
        if 'decoded' in packet and packet['decoded']['portnum'] == 'TEXT_MESSAGE_APP':
            msg = packet['decoded']['payload'].decode('utf-8')
            sender_id = packet.get('fromId', 'Unknown')
            to_id = packet.get('toId', '^all') # NEU: Ziel-ID auslesen
            
            sender_name = sender_id
            if sender_id in interface.nodes:
                sender_name = interface.nodes[sender_id].get('user', {}).get('shortName', sender_id)
            
            # NEU: Prüfen, ob es eine Direktnachricht (DM) ist
            if to_id != '^all':
                target_name = to_id
                if to_id in interface.nodes:
                    # Löst den Namen des Empfängers auf
                    target_name = interface.nodes[to_id].get('user', {}).get('shortName', to_id)
                
                ch_name = f"DM an {target_name}"
            else:
                # Normale Kanallogik
                ch_idx = packet.get('channel', 0)
                ch_name = f"Ch {ch_idx}"
                try:
                    ch = interface.localNode.channels[ch_idx]
                    if ch.settings.name:
                        ch_name = ch.settings.name
                    elif ch_idx == 0:
                        ch_name = self.t("primary")
                except Exception:
                    pass

            time_str = datetime.now().strftime('%H:%M:%S')
            self.write_log(f"[{time_str}] [{ch_name}] {sender_name}: {msg}")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Behandelt Klicks oder Enter-Tasten auf Tabellen-Reihen."""
        if event.data_table.id == "node_list":
            row_data = event.data_table.get_row(event.row_key)
            node_name = row_data[0]
            node_id = row_data[1]
            
            input_widget = self.query_one("#msg_input", Input)
            input_widget.focus()
            input_widget.value = f"/dm {node_id} "
            
            def fix_cursor():
                input_widget.cursor_position = len(input_widget.value)
                
            self.set_timer(0.05, fix_cursor)
            self.write_log(self.t("sys_dm_ready").format(node_name))
            
        elif event.data_table.id == "channel_list":
            row_data = event.data_table.get_row(event.row_key)
            # Extrahieren des Indexes (Säubern vom '*' Marker falls vorhanden)
            idx_str = str(row_data[0]).replace("*", "")
            try:
                self.channel_index = int(idx_str)
                self.write_log(self.t("sys_ch_switch").format(self.channel_index))
                self.update_data() # Erzwingt Update für das Sternchen (*)
                self.query_one("#msg_input", Input).focus() # Setzt Fokus zurück in den Chat
            except ValueError:
                pass

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "msg_input":
            count_label = self.query_one("#char_count", Label)
            current_len = len(event.value)
            count_label.update(f"{current_len}/200")
            
            if current_len >= 200:
                count_label.styles.color = "red"
            else:
                count_label.styles.color = None

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return

        if text.startswith("/ch "):
            try:
                parts = text.split(" ")
                ch_idx = int(parts[1])
                self.channel_index = ch_idx
                self.write_log(self.t("sys_ch_switch").format(ch_idx))
                self.update_data()
            except Exception:
                self.write_log(self.t("err_invalid_cmd"))

        elif text.startswith("/rename "):
            try:
                parts = text.split(" ", 2)
                ch_idx = int(parts[1])
                ch_name = parts[2]
                
                ch = self.interface.localNode.channels[ch_idx]
                ch.settings.name = ch_name
                
                if ch_idx > 0 and ch.role == channel_pb2.Channel.Role.DISABLED:
                    ch.role = channel_pb2.Channel.Role.SECONDARY
                    
                self.interface.localNode.writeChannel(ch_idx)
                self.write_log(self.t("sys_renamed").format(ch_idx, ch_name))
                self.update_data()
            except Exception as e:
                self.write_log(self.t("err_rename").format(e))
                
        elif text.startswith("/dm "):
            try:
                parts = text.split(" ", 2)
                if len(parts) < 3:
                    self.write_log(self.t("err_dm_args"))
                    return
                
                target_id = parts[1]
                dm_message = parts[2]
                
                if self.interface:
                    self.interface.sendText(dm_message, destinationId=target_id)
                    time_str = datetime.now().strftime('%H:%M:%S')
                    
                    # NEU: Namen des Ziels für den eigenen Log auflösen
                    target_name = target_id
                    if target_id in self.interface.nodes:
                        target_name = self.interface.nodes[target_id].get('user', {}).get('shortName', target_id)
                        
                    self.write_log(f"[{time_str}] [DM -> {target_name}]: {dm_message}")
                else:
                    self.write_log(self.t("err_not_conn"))
            except Exception as e:
                self.write_log(self.t("err_dm_fail").format(e))
        
        else:
            if self.interface:
                try:
                    self.interface.sendText(text, channelIndex=self.channel_index)
                    time_str = datetime.now().strftime('%H:%M:%S')
                    
                    ch_name = self.t("primary") if self.channel_index == 0 else f"Ch {self.channel_index}"
                    try:
                        ch = self.interface.localNode.channels[self.channel_index]
                        if ch.settings.name:
                            ch_name = ch.settings.name
                    except:
                        pass
                    
                    self.write_log(f"[{time_str}] {self.t('you')} [{ch_name}]: {text}")
                except Exception as e:
                    self.write_log(self.t("err_send_fail").format(e))
            else:
                self.write_log(self.t("err_not_conn"))

        event.input.value = ""

    def update_data(self):
        """Aktualisiert die Nodeliste und die Kanalliste."""
        if not self.interface:
            return

        # 1. NODES AKTUALISIEREN
        node_table = self.query_one("#node_list", DataTable)
        node_table.clear()
        now = datetime.now().timestamp()

        my_node_id = None
        try:
            my_user = self.interface.getMyUser()
            if my_user:
                my_node_id = my_user.get('id')
        except Exception:
            pass

        if hasattr(self.interface, 'nodes') and self.interface.nodes:
            node_list = list(self.interface.nodes.items())
        elif hasattr(self.interface, 'nodesByNum') and self.interface.nodesByNum:
            node_list = []
            for num, node in self.interface.nodesByNum.items():
                # Sicherheitscheck, falls node kein normales Daten-Wörterbuch ist
                if not isinstance(node, dict):
                    continue
                
                # Holt die User-Daten sicher (fängt den Fall ab, falls 'user' = None ist)
                user_data = node.get("user") or {}
                node_id = user_data.get("id")
                
                # Den Knoten nur der Liste hinzufügen, wenn eine gültige String-ID existiert
                if node_id:
                    node_list.append((node_id, node))
        else:
            node_list = []

        def sort_key(item):
            node_id, node = item
            is_mine = 1 if node_id == my_node_id else 0
            last_heard = node.get('lastHeard') or 0
            return (is_mine, last_heard)

        node_list.sort(key=sort_key, reverse=True)

        for node_id, node in node_list:
            user = node.get('user', {})
            long_name = user.get('longName', 'Unknown')[:20]
            short_name = user.get('shortName', 'Unk')[:5]
            hw_model = str(user.get('hwModel', 'Unknown')).replace('HardwareModel.', '')[:10]
            
            hops = str(node.get('hopsAway', '0'))
            snr = str(node.get('snr', '-'))
            
            last_heard = node.get('lastHeard')
            if last_heard:
                diff = int(now - last_heard)
                minutes, seconds = divmod(diff, 60)
                hours, minutes = divmod(minutes, 60)
                days, hours = divmod(hours, 24)
                
                if days > 0:
                    seen_str = f"{days}{self.t('time_days')} {hours}{self.t('time_hours')}"
                elif hours > 0:
                    seen_str = f"{hours}{self.t('time_hours')} {minutes}{self.t('time_mins')}"
                else:
                    seen_str = f"{minutes}{self.t('time_mins')} {seconds}{self.t('time_secs')}"
            else:
                seen_str = self.t("never")
                
            node_table.add_row(long_name, node_id, short_name, hw_model, hops, snr, seen_str)

        # 2. KANÄLE AKTUALISIEREN
        chan_table = self.query_one("#channel_list", DataTable)
        chan_table.clear()
        
        if hasattr(self.interface, 'localNode') and self.interface.localNode:
            for ch in self.interface.localNode.channels:
                if ch.role > 0: 
                    idx = ch.index
                    role_str = self.t("primary") if ch.role == 1 else self.t("secondary")
                    name = ch.settings.name if ch.settings.name else (self.t("primary") if idx == 0 else f"Channel {idx}")
                    
                    active_marker = "*" if idx == self.channel_index else ""
                    chan_table.add_row(f"{idx}{active_marker}", name, role_str)

    def action_focus_chat(self) -> None:
        self.query_one("#msg_input", Input).focus()

if __name__ == "__main__":
    app = MeshtasticTUI()
    app.run()
