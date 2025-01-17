import tkinter as tk
from datetime import datetime, timedelta
from functools import partial
from os import path
from threading import Thread
from time import sleep
from tkinter import PhotoImage, ttk
from tkinter.messagebox import askyesno
from typing import Dict, List, Optional

import myNotebook as nb
from config import config
from ScrollableNotebook import ScrollableNotebook
from theme import theme
from ttkHyperlinkLabel import HyperlinkLabel

from bgstally.activity import CONFLICT_STATES, ELECTION_STATES, Activity
from bgstally.debug import Debug
from bgstally.constants import CheckStates, CZs, UpdateUIPolicy

DATETIME_FORMAT_WINDOWTITLE = "%Y-%m-%d %H:%M:%S"
DATETIME_FORMAT_OVERLAY = "%Y-%m-%d %H:%M"
FOLDER_ASSETS = "assets"
TIME_WORKER_PERIOD_S = 2
TIME_TICK_ALERT_M = 60
URL_LATEST_RELEASE = "https://github.com/aussig/BGS-Tally/releases/latest"
URL_WIKI = "https://github.com/aussig/BGS-Tally/wiki"


class UI:
    """
    Display the user's activity
    """

    def __init__(self, bgstally):
        self.bgstally = bgstally

        self.image_button_dropdown_menu = PhotoImage(file = path.join(self.bgstally.plugin_dir, FOLDER_ASSETS, "button_dropdown_menu.png"))
        self.image_tab_active_enabled = PhotoImage(file = path.join(self.bgstally.plugin_dir, FOLDER_ASSETS, "tab_active_enabled.png"))
        self.image_tab_active_part_enabled = PhotoImage(file = path.join(self.bgstally.plugin_dir, FOLDER_ASSETS, "tab_active_part_enabled.png"))
        self.image_tab_active_disabled = PhotoImage(file = path.join(self.bgstally.plugin_dir, FOLDER_ASSETS, "tab_active_disabled.png"))
        self.image_tab_inactive_enabled = PhotoImage(file = path.join(self.bgstally.plugin_dir, FOLDER_ASSETS, "tab_inactive_enabled.png"))
        self.image_tab_inactive_part_enabled = PhotoImage(file = path.join(self.bgstally.plugin_dir, FOLDER_ASSETS, "tab_inactive_part_enabled.png"))
        self.image_tab_inactive_disabled = PhotoImage(file = path.join(self.bgstally.plugin_dir, FOLDER_ASSETS, "tab_inactive_disabled.png"))

        self.heading_font = ("Helvetica", 11, "bold")

        self.thread: Optional[Thread] = Thread(target=self._worker, name="BGSTally UI worker")
        self.thread.daemon = True
        self.thread.start()


    def shut_down(self):
        """
        Shut down all worker threads.
        """


    def get_plugin_frame(self, parent_frame: tk.Frame, git_version_number: str):
        """
        Return a TK Frame for adding to the EDMC main window
        """
        self.frame = tk.Frame(parent_frame)

        TitleLabel = tk.Label(self.frame, text="BGS Tally (Aussi)")
        TitleLabel.grid(row=0, column=0, sticky=tk.W)
        TitleVersion = tk.Label(self.frame, text="v" + self.bgstally.version)
        TitleVersion.grid(row=0, column=1, sticky=tk.W)
        if self._version_tuple(git_version_number) > self._version_tuple(self.bgstally.version):
            HyperlinkLabel(self.frame, text="New version available", background=nb.Label().cget('background'), url=URL_LATEST_RELEASE, underline=True).grid(row=0, column=1, sticky=tk.W)
        tk.Button(self.frame, text="Latest BGS Tally", command=partial(self._show_activity_window, self.bgstally.activity_manager.get_current_activity())).grid(row=1, column=0, padx=3)
        self.PreviousButton = tk.Button(self.frame, text = "Previous BGS Tallies ", image=self.image_button_dropdown_menu, compound=tk.RIGHT, command=self._previous_ticks_popup)
        self.PreviousButton.grid(row=1, column=1, padx=3)
        tk.Label(self.frame, text="BGS Tally Plugin Status:").grid(row=2, column=0, sticky=tk.W)
        tk.Label(self.frame, text="Last BGS Tick:").grid(row=3, column=0, sticky=tk.W)
        tk.Label(self.frame, textvariable=self.bgstally.state.Status).grid(row=2, column=1, sticky=tk.W)
        tk.Label(self.frame, text=self.bgstally.tick.get_formatted()).grid(row=3, column=1, sticky=tk.W)

        return self.frame


    def update_plugin_frame(self):
        """
        Update the tick time label and current activity button in the plugin frame
        """
        tk.Label(self.frame, text=self.bgstally.tick.get_formatted()).grid(row=3, column=1, sticky=tk.W)
        tk.Button(self.frame, text="Latest BGS Tally", command=partial(self._show_activity_window, self.bgstally.activity_manager.get_current_activity())).grid(row=1, column=0, padx=3)

        theme.update(self.frame)


    def get_prefs_frame(self, parent_frame: tk.Frame):
        """
        Return a TK Frame for adding to the EDMC settings dialog
        """

        frame = nb.Frame(parent_frame)
        # Make the second column fill available space
        frame.columnconfigure(1, weight=1)

        current_row = 1
        nb.Label(frame, text=f"BGS Tally (modified by Aussi) v{self.bgstally.version}", font=self.heading_font).grid(column=0, padx=10, sticky=tk.W); current_row += 1
        HyperlinkLabel(frame, text="Instructions for Use", background=nb.Label().cget('background'), url=URL_WIKI, underline=True).grid(column=1, padx=10, sticky=tk.W); current_row += 1

        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(columnspan=2, padx=10, pady=2, sticky=tk.EW); current_row += 1
        nb.Label(frame, text="General", font=self.heading_font).grid(column=0, padx=10, sticky=tk.W); current_row += 1
        nb.Checkbutton(frame, text="BGS Tally Active", variable=self.bgstally.state.Status, onvalue="Active", offvalue="Paused").grid(column=1, padx=10, sticky=tk.W); current_row += 1
        nb.Checkbutton(frame, text="Show Systems with Zero Activity", variable=self.bgstally.state.ShowZeroActivitySystems, onvalue=CheckStates.STATE_ON, offvalue=CheckStates.STATE_OFF).grid(column=1, padx=10, sticky=tk.W); current_row += 1

        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(columnspan=2, padx=10, pady=2, sticky=tk.EW); current_row += 1
        nb.Label(frame, text="Discord", font=self.heading_font).grid(column=0, padx=10, sticky=tk.W); current_row += 1
        nb.Checkbutton(frame, text="Abbreviate Faction Names", variable=self.bgstally.state.AbbreviateFactionNames, onvalue=CheckStates.STATE_ON, offvalue=CheckStates.STATE_OFF).grid(column=1, padx=10, sticky=tk.W); current_row += 1
        nb.Checkbutton(frame, text="Include Secondary INF", variable=self.bgstally.state.IncludeSecondaryInf, onvalue=CheckStates.STATE_ON, offvalue=CheckStates.STATE_OFF).grid(column=1, padx=10, sticky=tk.W); current_row += 1
        nb.Label(frame, text="Discord Webhook URL").grid(column=0, padx=10, sticky=tk.W, row=current_row)
        EntryPlus(frame, textvariable=self.bgstally.state.DiscordWebhook).grid(column=1, padx=10, pady=2, sticky=tk.EW, row=current_row); current_row += 1
        nb.Label(frame, text="Discord Post as User").grid(column=0, padx=10, sticky=tk.W, row=current_row)
        EntryPlus(frame, textvariable=self.bgstally.state.DiscordUsername).grid(column=1, padx=10, pady=2, sticky=tk.W, row=current_row); current_row += 1

        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(columnspan=2, padx=10, pady=2, sticky=tk.EW); current_row += 1
        nb.Label(frame, text="In-game Overlay", font=self.heading_font).grid(column=0, padx=10, sticky=tk.W); current_row += 1
        nb.Checkbutton(frame, text="Show In-game Overlay", variable=self.bgstally.state.EnableOverlay, state="disabled" if self.bgstally.overlay.edmcoverlay == None else "enabled", onvalue=CheckStates.STATE_ON, offvalue=CheckStates.STATE_OFF, command=self.bgstally.state.refresh).grid(column=1, padx=10, sticky=tk.W); current_row += 1
        if self.bgstally.overlay.edmcoverlay == None:
            nb.Label(frame, text="In-game overlay support requires the separate EDMCOverlay plugin to be installed - see the instructions for more information.").grid(columnspan=2, padx=10, sticky=tk.W); current_row += 1

        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(columnspan=2, padx=10, pady=2, sticky=tk.EW); current_row += 1
        nb.Label(frame, text="Advanced", font=self.heading_font).grid(column=0, padx=10, sticky=tk.W); current_row += 1
        tk.Button(frame, text="FORCE Tick", command=self._confirm_force_tick, bg="red", fg="white").grid(column=1, padx=10, sticky=tk.W, row=current_row); current_row += 1

        return frame


    def _worker(self) -> None:
        """
        Handle thread work
        """
        Debug.logger.debug("Starting UI Worker...")

        while True:
            if config.shutting_down:
                Debug.logger.debug("Shutting down UI Worker...")
                return

            self.bgstally.overlay.display_message("tick", f"Curr Tick: {self.bgstally.tick.get_formatted(DATETIME_FORMAT_OVERLAY)}", True)
            if (datetime.utcnow() > self.bgstally.tick.next_predicted() - timedelta(minutes = TIME_TICK_ALERT_M)):
                self.bgstally.overlay.display_message("tickwarn", f"Within {TIME_TICK_ALERT_M}m of next tick (est)", True)

            sleep(TIME_WORKER_PERIOD_S)


    def _previous_ticks_popup(self):
        menu = tk.Menu(self.frame, tearoff = 0)

        activities: List = self.bgstally.activity_manager.get_previous_activities()

        for activity in activities:
            menu.add_command(label=activity.tick_time, command=partial(self._show_activity_window, activity))

        try:
            menu.tk_popup(self.PreviousButton.winfo_rootx(), self.PreviousButton.winfo_rooty())
        finally:
            menu.grab_release()


    def _show_activity_window(self, activity: Activity):
        """
        Display the data window, using data from the passed in activity object
        """
        Form = tk.Toplevel(self.frame)
        Form.title("BGS Tally - After Tick at: " + activity.tick_time.strftime(DATETIME_FORMAT_WINDOWTITLE))
        Form.geometry("1200x800")

        ContainerFrame = ttk.Frame(Form)
        ContainerFrame.pack(fill=tk.BOTH, expand=1)
        TabParent=ScrollableNotebook(ContainerFrame, wheelscroll=False, tabmenu=True)
        TabParent.pack(fill=tk.BOTH, expand=1, side=tk.TOP, padx=5, pady=5)

        DiscordFrame = ttk.Frame(ContainerFrame)
        DiscordFrame.pack(fill=tk.BOTH, padx=5, pady=5)
        ttk.Label(DiscordFrame, text="Discord Report", font=self.heading_font).grid(row=0, column=0, sticky=tk.W)
        ttk.Label(DiscordFrame, text="Discord Options", font=self.heading_font).grid(row=0, column=1, sticky=tk.W)
        ttk.Label(DiscordFrame, text="Double-check on-ground CZ tallies, sizes are not always correct", foreground='#f00').grid(row=1, column=0, columnspan=2, sticky=tk.W)

        DiscordTextFrame = ttk.Frame(DiscordFrame)
        DiscordTextFrame.grid(row=2, column=0, pady=5, sticky=tk.NSEW)
        DiscordText = TextPlus(DiscordTextFrame, wrap=tk.WORD, height=14, font=("Helvetica", 9))
        DiscordScroll = tk.Scrollbar(DiscordTextFrame, orient=tk.VERTICAL, command=DiscordText.yview)
        DiscordText['yscrollcommand'] = DiscordScroll.set
        DiscordScroll.pack(fill=tk.Y, side=tk.RIGHT)
        DiscordText.pack(fill=tk.BOTH, side=tk.LEFT, expand=True)

        DiscordOptionsFrame = ttk.Frame(DiscordFrame)
        DiscordOptionsFrame.grid(row=2, column=1, padx=5, pady=5, sticky=tk.NW)
        ttk.Checkbutton(DiscordOptionsFrame, text="Abbreviate Faction Names", variable=self.bgstally.state.AbbreviateFactionNames, onvalue=CheckStates.STATE_ON, offvalue=CheckStates.STATE_OFF, command=partial(self._option_change, DiscordText, activity)).grid(sticky=tk.W)
        ttk.Checkbutton(DiscordOptionsFrame, text="Include Secondary INF", variable=self.bgstally.state.IncludeSecondaryInf, onvalue=CheckStates.STATE_ON, offvalue=CheckStates.STATE_OFF, command=partial(self._option_change, DiscordText, activity)).grid(sticky=tk.W)

        system_list = activity.get_ordered_systems()

        tab_index = 0

        for system_id in system_list:
            system = activity.systems[system_id]

            if self.bgstally.state.ShowZeroActivitySystems.get() == CheckStates.STATE_OFF \
                and system['zero_system_activity'] \
                and str(system_id) != self.bgstally.state.current_system_id: continue

            tab = ttk.Frame(TabParent)
            tab.columnconfigure(1, weight=1) # Make the second column (faction name) fill available space
            TabParent.add(tab, text=system['System'], compound='right', image=self.image_tab_active_enabled)

            FactionEnableCheckbuttons = []

            ttk.Label(tab, text="Include", font=self.heading_font).grid(row=0, column=0, padx=2, pady=2)
            EnableAllCheckbutton = ttk.Checkbutton(tab)
            EnableAllCheckbutton.grid(row=1, column=0, padx=2, pady=2)
            EnableAllCheckbutton.configure(command=partial(self._enable_all_factions_change, TabParent, tab_index, EnableAllCheckbutton, FactionEnableCheckbuttons, DiscordText, activity, system))
            EnableAllCheckbutton.state(['!alternate'])
            ttk.Label(tab, text="Faction", font=self.heading_font).grid(row=0, column=1, padx=2, pady=2)
            ttk.Label(tab, text="State", font=self.heading_font).grid(row=0, column=2, padx=2, pady=2)
            ttk.Label(tab, text="INF", font=self.heading_font, anchor=tk.CENTER).grid(row=0, column=3, columnspan=2, padx=2)
            ttk.Label(tab, text="Pri", font=self.heading_font).grid(row=1, column=3, padx=2, pady=2)
            ttk.Label(tab, text="Sec", font=self.heading_font).grid(row=1, column=4, padx=2, pady=2)
            ttk.Label(tab, text="Trade", font=self.heading_font, anchor=tk.CENTER).grid(row=0, column=5, columnspan=3, padx=2)
            ttk.Label(tab, text="Purch", font=self.heading_font).grid(row=1, column=5, padx=2, pady=2)
            ttk.Label(tab, text="Prof", font=self.heading_font).grid(row=1, column=6, padx=2, pady=2)
            ttk.Label(tab, text="BM Prof", font=self.heading_font).grid(row=1, column=7, padx=2, pady=2)
            ttk.Label(tab, text="BVs", font=self.heading_font).grid(row=0, column=8, padx=2, pady=2)
            ttk.Label(tab, text="Expl", font=self.heading_font).grid(row=0, column=9, padx=2, pady=2)
            ttk.Label(tab, text="Exo", font=self.heading_font).grid(row=0, column=10, padx=2, pady=2)
            ttk.Label(tab, text="CBs", font=self.heading_font).grid(row=0, column=11, padx=2, pady=2)
            ttk.Label(tab, text="Fails", font=self.heading_font).grid(row=0, column=12, padx=2, pady=2)
            ttk.Label(tab, text="Murders", font=self.heading_font).grid(row=0, column=13, padx=2, pady=2)
            ttk.Label(tab, text="Scens", font=self.heading_font).grid(row=0, column=14, padx=2, pady=2)
            ttk.Label(tab, text="Space CZs", font=self.heading_font, anchor=tk.CENTER).grid(row=0, column=15, columnspan=3, padx=2)
            ttk.Label(tab, text="L", font=self.heading_font).grid(row=1, column=15, padx=2, pady=2)
            ttk.Label(tab, text="M", font=self.heading_font).grid(row=1, column=16, padx=2, pady=2)
            ttk.Label(tab, text="H", font=self.heading_font).grid(row=1, column=17, padx=2, pady=2)
            ttk.Label(tab, text="On-foot CZs", font=self.heading_font, anchor=tk.CENTER).grid(row=0, column=18, columnspan=3, padx=2)
            ttk.Label(tab, text="L", font=self.heading_font).grid(row=1, column=18, padx=2, pady=2)
            ttk.Label(tab, text="M", font=self.heading_font).grid(row=1, column=19, padx=2, pady=2)
            ttk.Label(tab, text="H", font=self.heading_font).grid(row=1, column=20, padx=2, pady=2)
            ttk.Separator(tab, orient=tk.HORIZONTAL).grid(columnspan=21, padx=2, pady=5, sticky=tk.EW)

            header_rows = 3
            x = 0

            for faction in system['Factions'].values():
                EnableCheckbutton = ttk.Checkbutton(tab)
                EnableCheckbutton.grid(row=x + header_rows, column=0, sticky=tk.N, padx=2, pady=2)
                EnableCheckbutton.configure(command=partial(self._enable_faction_change, TabParent, tab_index, EnableAllCheckbutton, FactionEnableCheckbuttons, DiscordText, activity, system, faction, x))
                EnableCheckbutton.state(['selected', '!alternate'] if faction['Enabled'] == CheckStates.STATE_ON else ['!selected', '!alternate'])
                FactionEnableCheckbuttons.append(EnableCheckbutton)

                FactionNameFrame = ttk.Frame(tab)
                FactionNameFrame.grid(row=x + header_rows, column=1, sticky=tk.NW)
                FactionName = ttk.Label(FactionNameFrame, text=faction['Faction'])
                FactionName.grid(row=0, column=0, columnspan=2, sticky=tk.W, padx=2, pady=2)
                FactionName.bind("<Button-1>", partial(self._faction_name_clicked, TabParent, tab_index, EnableCheckbutton, EnableAllCheckbutton, FactionEnableCheckbuttons, DiscordText, activity, system, faction, x))
                settlement_row_index = 1
                for settlement_name in faction.get('GroundCZSettlements', {}):
                    SettlementCheckbutton = ttk.Checkbutton(FactionNameFrame)
                    SettlementCheckbutton.grid(row=settlement_row_index, column=0, padx=2, pady=2)
                    SettlementCheckbutton.configure(command=partial(self._enable_settlement_change, SettlementCheckbutton, settlement_name, DiscordText, activity, faction, x))
                    SettlementCheckbutton.state(['selected', '!alternate'] if faction['GroundCZSettlements'][settlement_name]['enabled'] == CheckStates.STATE_ON else ['!selected', '!alternate'])
                    SettlementName = ttk.Label(FactionNameFrame, text=f"{settlement_name} ({faction['GroundCZSettlements'][settlement_name]['type'].upper()})")
                    SettlementName.grid(row=settlement_row_index, column=1, sticky=tk.W, padx=2, pady=2)
                    SettlementName.bind("<Button-1>", partial(self._settlement_name_clicked, SettlementCheckbutton, settlement_name, DiscordText, activity, faction, x))
                    settlement_row_index += 1

                ttk.Label(tab, text=faction['FactionState']).grid(row=x + header_rows, column=2, sticky=tk.N)
                MissionPointsVar = tk.IntVar(value=faction['MissionPoints'])
                ttk.Spinbox(tab, from_=-999, to=999, width=3, textvariable=MissionPointsVar).grid(row=x + header_rows, column=3, sticky=tk.N, padx=2, pady=2)
                MissionPointsVar.trace('w', partial(self._mission_points_change, TabParent, tab_index, MissionPointsVar, True, EnableAllCheckbutton, DiscordText, activity, system, faction, x))
                if (faction['FactionState'] not in CONFLICT_STATES and faction['FactionState'] not in ELECTION_STATES):
                    MissionPointsSecVar = tk.IntVar(value=faction['MissionPointsSecondary'])
                    ttk.Spinbox(tab, from_=-999, to=999, width=3, textvariable=MissionPointsSecVar).grid(row=x + header_rows, column=4, sticky=tk.N, padx=2, pady=2)
                    MissionPointsSecVar.trace('w', partial(self._mission_points_change, TabParent, tab_index, MissionPointsSecVar, False, EnableAllCheckbutton, DiscordText, activity, system, faction, x))
                ttk.Label(tab, text=self._human_format(faction['TradePurchase'])).grid(row=x + header_rows, column=5, sticky=tk.N)
                ttk.Label(tab, text=self._human_format(faction['TradeProfit'])).grid(row=x + header_rows, column=6, sticky=tk.N)
                ttk.Label(tab, text=self._human_format(faction['BlackMarketProfit'])).grid(row=x + header_rows, column=7, sticky=tk.N)
                ttk.Label(tab, text=self._human_format(faction['Bounties'])).grid(row=x + header_rows, column=8, sticky=tk.N)
                ttk.Label(tab, text=self._human_format(faction['CartData'])).grid(row=x + header_rows, column=9, sticky=tk.N)
                ttk.Label(tab, text=self._human_format(faction['ExoData'])).grid(row=x + header_rows, column=10, sticky=tk.N)
                ttk.Label(tab, text=self._human_format(faction['CombatBonds'])).grid(row=x + header_rows, column=11, sticky=tk.N)
                ttk.Label(tab, text=faction['MissionFailed']).grid(row=x + header_rows, column=12, sticky=tk.N)
                ttk.Label(tab, text=faction['Murdered']).grid(row=x + header_rows, column=13, sticky=tk.N)
                ScenariosVar = tk.IntVar(value=faction['Scenarios'])
                ttk.Spinbox(tab, from_=0, to=999, width=3, textvariable=ScenariosVar).grid(row=x + header_rows, column=14, sticky=tk.N, padx=2, pady=2)
                ScenariosVar.trace('w', partial(self._scenarios_change, TabParent, tab_index, ScenariosVar, EnableAllCheckbutton, DiscordText, activity, system, faction, x))

                if (faction['FactionState'] in CONFLICT_STATES):
                    CZSpaceLVar = tk.StringVar(value=faction['SpaceCZ'].get('l', '0'))
                    ttk.Spinbox(tab, from_=0, to=999, width=3, textvariable=CZSpaceLVar).grid(row=x + header_rows, column=15, sticky=tk.N, padx=2, pady=2)
                    CZSpaceMVar = tk.StringVar(value=faction['SpaceCZ'].get('m', '0'))
                    ttk.Spinbox(tab, from_=0, to=999, width=3, textvariable=CZSpaceMVar).grid(row=x + header_rows, column=16, sticky=tk.N, padx=2, pady=2)
                    CZSpaceHVar = tk.StringVar(value=faction['SpaceCZ'].get('h', '0'))
                    ttk.Spinbox(tab, from_=0, to=999, width=3, textvariable=CZSpaceHVar).grid(row=x + header_rows, column=17, sticky=tk.N, padx=2, pady=2)
                    CZGroundLVar = tk.StringVar(value=faction['GroundCZ'].get('l', '0'))
                    ttk.Spinbox(tab, from_=0, to=999, width=3, textvariable=CZGroundLVar).grid(row=x + header_rows, column=18, sticky=tk.N, padx=2, pady=2)
                    CZGroundMVar = tk.StringVar(value=faction['GroundCZ'].get('m', '0'))
                    ttk.Spinbox(tab, from_=0, to=999, width=3, textvariable=CZGroundMVar).grid(row=x + header_rows, column=19, sticky=tk.N, padx=2, pady=2)
                    CZGroundHVar = tk.StringVar(value=faction['GroundCZ'].get('h', '0'))
                    ttk.Spinbox(tab, from_=0, to=999, width=3, textvariable=CZGroundHVar).grid(row=x + header_rows, column=20, sticky=tk.N, padx=2, pady=2)
                    # Watch for changes on all SpinBox Variables. This approach catches any change, including manual editing, while using 'command' callbacks only catches clicks
                    CZSpaceLVar.trace('w', partial(self._cz_change, TabParent, tab_index, CZSpaceLVar, EnableAllCheckbutton, DiscordText, CZs.SPACE_LOW, activity, system, faction, x))
                    CZSpaceMVar.trace('w', partial(self._cz_change, TabParent, tab_index, CZSpaceMVar, EnableAllCheckbutton, DiscordText, CZs.SPACE_MED, activity, system, faction, x))
                    CZSpaceHVar.trace('w', partial(self._cz_change, TabParent, tab_index, CZSpaceHVar, EnableAllCheckbutton, DiscordText, CZs.SPACE_HIGH, activity, system, faction, x))
                    CZGroundLVar.trace('w', partial(self._cz_change, TabParent, tab_index, CZGroundLVar, EnableAllCheckbutton, DiscordText, CZs.GROUND_LOW, activity, system, faction, x))
                    CZGroundMVar.trace('w', partial(self._cz_change, TabParent, tab_index, CZGroundMVar, EnableAllCheckbutton, DiscordText, CZs.GROUND_MED, activity, system, faction, x))
                    CZGroundHVar.trace('w', partial(self._cz_change, TabParent, tab_index, CZGroundHVar, EnableAllCheckbutton, DiscordText, CZs.GROUND_HIGH, activity, system, faction, x))

                x += 1

            self._update_enable_all_factions_checkbutton(TabParent, tab_index, EnableAllCheckbutton, FactionEnableCheckbuttons, system)

            tab.pack_forget()
            tab_index += 1

        DiscordText.insert(tk.INSERT, self._generate_discord_text(activity))
        # Select all text and focus the field
        DiscordText.tag_add('sel', '1.0', 'end')
        DiscordText.focus()

        ttk.Button(ContainerFrame, text="Copy to Clipboard", command=partial(self._copy_to_clipboard, ContainerFrame, DiscordText)).pack(side=tk.LEFT, padx=5, pady=5)
        if self.bgstally.discord.is_webhook_valid(): ttk.Button(ContainerFrame, text="Post to Discord", command=partial(self.bgstally.discord.post_to_discord, DiscordText, activity)).pack(side=tk.RIGHT, padx=5, pady=5)

        theme.update(ContainerFrame)

        # Ignore all scroll wheel events on spinboxes, to avoid accidental inputs
        Form.bind_class('TSpinbox', '<MouseWheel>', lambda event : "break")


    def _confirm_force_tick(self):
        """
        Force a tick when user clicks button
        """
        answer = askyesno(title="Confirm FORCE a New Tick", message="This will move your current activity into the previous tick, and clear activity for the current tick.\n\nWARNING: It is not usually necessary to force a tick. Only do this if you know FOR CERTAIN there has been a tick but BGS-Tally is not showing it.\n\nAre you sure that you want to do this?", default="no")
        if answer: self.bgstally.new_tick(True, UpdateUIPolicy.IMMEDIATE)


    def _version_tuple(self, version: str):
        """
        Parse the plugin version number into a tuple
        """
        try:
            ret = tuple(map(int, version.split(".")))
        except:
            ret = (0,)
        return ret


    def _option_change(self, DiscordText, activity: Activity):
        """
        Callback when one of the Discord options is changed
        """
        DiscordText.delete('1.0', 'end-1c')
        DiscordText.insert(tk.INSERT, self._generate_discord_text(activity))


    def _enable_faction_change(self, notebook: ScrollableNotebook, tab_index: int, EnableAllCheckbutton, FactionEnableCheckbuttons, DiscordText, activity: Activity, system, faction, faction_index, *args):
        """
        Callback for when a Faction Enable Checkbutton is changed
        """
        faction['Enabled'] = CheckStates.STATE_ON if FactionEnableCheckbuttons[faction_index].instate(['selected']) else CheckStates.STATE_OFF
        self._update_enable_all_factions_checkbutton(notebook, tab_index, EnableAllCheckbutton, FactionEnableCheckbuttons, system)

        DiscordText.delete('1.0', 'end-1c')
        DiscordText.insert(tk.INSERT, self._generate_discord_text(activity))


    def _enable_all_factions_change(self, notebook: ScrollableNotebook, tab_index: int, EnableAllCheckbutton, FactionEnableCheckbuttons, DiscordText, activity: Activity, system, *args):
        """
        Callback for when the Enable All Factions Checkbutton is changed
        """
        x = 0
        for faction in system['Factions'].values():
            if EnableAllCheckbutton.instate(['selected']):
                FactionEnableCheckbuttons[x].state(['selected'])
                faction['Enabled'] = CheckStates.STATE_ON
            else:
                FactionEnableCheckbuttons[x].state(['!selected'])
                faction['Enabled'] = CheckStates.STATE_OFF
            x += 1

        self._update_tab_image(notebook, tab_index, EnableAllCheckbutton, system)

        DiscordText.delete('1.0', 'end-1c')
        DiscordText.insert(tk.INSERT, self._generate_discord_text(activity))


    def _enable_settlement_change(self, SettlementCheckbutton, settlement_name, DiscordText, activity: Activity, faction, faction_index, *args):
        """
        Callback for when a Settlement Enable Checkbutton is changed
        """
        faction['GroundCZSettlements'][settlement_name]['enabled'] = CheckStates.STATE_ON if SettlementCheckbutton.instate(['selected']) else CheckStates.STATE_OFF

        DiscordText.delete('1.0', 'end-1c')
        DiscordText.insert(tk.INSERT, self._generate_discord_text(activity))


    def _update_enable_all_factions_checkbutton(self, notebook: ScrollableNotebook, tab_index: int, EnableAllCheckbutton, FactionEnableCheckbuttons, system):
        """
        Update the 'Enable all factions' checkbox to the correct state based on which individual factions are enabled
        """
        any_on = False
        any_off = False
        z = len(FactionEnableCheckbuttons)
        for x in range(0, z):
            if FactionEnableCheckbuttons[x].instate(['selected']): any_on = True
            if FactionEnableCheckbuttons[x].instate(['!selected']): any_off = True

        if any_on == True:
            if any_off == True:
                EnableAllCheckbutton.state(['alternate', '!selected'])
            else:
                EnableAllCheckbutton.state(['!alternate', 'selected'])
        else:
            EnableAllCheckbutton.state(['!alternate', '!selected'])

        self._update_tab_image(notebook, tab_index, EnableAllCheckbutton, system)


    def _faction_name_clicked(self, notebook: ScrollableNotebook, tab_index: int, EnableCheckbutton, EnableAllCheckbutton, FactionEnableCheckbuttons, DiscordText, activity: Activity, system, faction, faction_index, *args):
        """
        Callback when a faction name is clicked. Toggle enabled state.
        """
        if EnableCheckbutton.instate(['selected']): EnableCheckbutton.state(['!selected'])
        else: EnableCheckbutton.state(['selected'])
        self._enable_faction_change(notebook, tab_index, EnableAllCheckbutton, FactionEnableCheckbuttons, DiscordText, activity, system, faction, faction_index, *args)


    def _settlement_name_clicked(self, SettlementCheckbutton, settlement_name, DiscordText, activity: Activity, faction, faction_index, *args):
        """
        Callback when a settlement name is clicked. Toggle enabled state.
        """
        if SettlementCheckbutton.instate(['selected']): SettlementCheckbutton.state(['!selected'])
        else: SettlementCheckbutton.state(['selected'])
        self._enable_settlement_change(SettlementCheckbutton, settlement_name, DiscordText, activity, faction, faction_index, *args)


    def _cz_change(self, notebook: ScrollableNotebook, tab_index: int, CZVar, EnableAllCheckbutton, DiscordText, cz_type, activity: Activity, system, faction, faction_index, *args):
        """
        Callback (set as a variable trace) for when a CZ Variable is changed
        """
        if cz_type == CZs.SPACE_LOW:
            faction['SpaceCZ']['l'] = CZVar.get()
        elif cz_type == CZs.SPACE_MED:
            faction['SpaceCZ']['m'] = CZVar.get()
        elif cz_type == CZs.SPACE_HIGH:
            faction['SpaceCZ']['h'] = CZVar.get()
        elif cz_type == CZs.GROUND_LOW:
            faction['GroundCZ']['l'] = CZVar.get()
        elif cz_type == CZs.GROUND_MED:
            faction['GroundCZ']['m'] = CZVar.get()
        elif cz_type == CZs.GROUND_HIGH:
            faction['GroundCZ']['h'] = CZVar.get()

        activity.recalculate_zero_activity()
        self._update_tab_image(notebook, tab_index, EnableAllCheckbutton, system)

        DiscordText.delete('1.0', 'end-1c')
        DiscordText.insert(tk.INSERT, self._generate_discord_text(activity))


    def _mission_points_change(self, notebook: ScrollableNotebook, tab_index: int, MissionPointsVar, primary, EnableAllCheckbutton, DiscordText, activity: Activity, system, faction, faction_index, *args):
        """
        Callback (set as a variable trace) for when a mission points Variable is changed
        """
        if primary:
            faction['MissionPoints'] = MissionPointsVar.get()
        else:
            faction['MissionPointsSecondary'] = MissionPointsVar.get()

        activity.recalculate_zero_activity()
        Debug.logger.info(system)
        self._update_tab_image(notebook, tab_index, EnableAllCheckbutton, system)

        DiscordText.delete('1.0', 'end-1c')
        DiscordText.insert(tk.INSERT, self._generate_discord_text(activity))


    def _scenarios_change(self, notebook: ScrollableNotebook, tab_index: int, ScenariosVar, EnableAllCheckbutton, DiscordText, activity: Activity, system, faction, faction_index, *args):
        """
        Callback (set as a variable trace) for when the scenarios Variable is changed
        """
        faction['Scenarios'] = ScenariosVar.get()

        activity.recalculate_zero_activity()
        self._update_tab_image(notebook, tab_index, EnableAllCheckbutton, system)

        DiscordText.delete('1.0', 'end-1c')
        DiscordText.insert(tk.INSERT, self._generate_discord_text(activity))


    def _update_tab_image(self, notebook: ScrollableNotebook, tab_index: int, EnableAllCheckbutton, system: Dict):
        """
        Update the image alongside the tab title
        """
        if EnableAllCheckbutton.instate(['selected']):
            if system['zero_system_activity']: notebook.notebookTab.tab(tab_index, image=self.image_tab_inactive_enabled)
            else: notebook.notebookTab.tab(tab_index, image=self.image_tab_active_enabled)
        else:
            if EnableAllCheckbutton.instate(['alternate']):
                if system['zero_system_activity']: notebook.notebookTab.tab(tab_index, image=self.image_tab_inactive_part_enabled)
                else: notebook.notebookTab.tab(tab_index, image=self.image_tab_active_part_enabled)
            else:
                if system['zero_system_activity']: notebook.notebookTab.tab(tab_index, image=self.image_tab_inactive_disabled)
                else: notebook.notebookTab.tab(tab_index, image=self.image_tab_active_disabled)


    def _process_faction_name(self, faction_name):
        """
        Shorten the faction name if the user has chosen to
        """
        if self.bgstally.state.AbbreviateFactionNames.get() == CheckStates.STATE_ON:
            return ''.join((i if i.isnumeric() else i[0]) for i in faction_name.split())
        else:
            return faction_name


    def _generate_discord_text(self, activity: Activity):
        """
        Generate the Discord-formatted version of the tally data
        """
        discord_text = ""

        for system in activity.systems.values():
            system_discord_text = ""

            for faction in system['Factions'].values():
                if faction['Enabled'] != CheckStates.STATE_ON: continue

                faction_discord_text = ""

                if faction['FactionState'] in ELECTION_STATES:
                    faction_discord_text += f".ElectionINF {faction['MissionPoints']}; " if faction['MissionPoints'] > 0 else ""
                elif faction['FactionState'] in CONFLICT_STATES:
                    faction_discord_text += f".WarINF {faction['MissionPoints']}; " if faction['MissionPoints'] > 0 else ""
                else:
                    inf = faction['MissionPoints']
                    if self.bgstally.state.IncludeSecondaryInf.get() == CheckStates.STATE_ON: inf += faction['MissionPointsSecondary']
                    faction_discord_text += f".INF +{inf}; " if inf > 0 else f".INF {inf}; " if inf < 0 else ""

                faction_discord_text += f".BVs {self._human_format(faction['Bounties'])}; " if faction['Bounties'] != 0 else ""
                faction_discord_text += f".CBs {self._human_format(faction['CombatBonds'])}; " if faction['CombatBonds'] != 0 else ""
                faction_discord_text += f".TrdPurchase {self._human_format(faction['TradePurchase'])}; " if faction['TradePurchase'] != 0 else ""
                faction_discord_text += f".TrdProfit {self._human_format(faction['TradeProfit'])}; " if faction['TradeProfit'] != 0 else ""
                faction_discord_text += f".TrdBMProfit {self._human_format(faction['BlackMarketProfit'])}; " if faction['BlackMarketProfit'] != 0 else ""
                faction_discord_text += f".Expl {self._human_format(faction['CartData'])}; " if faction['CartData'] != 0 else ""
                faction_discord_text += f".Exo {self._human_format(faction['ExoData'])}; " if faction['ExoData'] != 0 else ""
                faction_discord_text += f".Murders {faction['Murdered']}; " if faction['Murdered'] != 0 else ""
                faction_discord_text += f".Scenarios {faction['Scenarios']}; " if faction['Scenarios'] != 0 else ""
                faction_discord_text += f".Fails {faction['MissionFailed']}; " if faction['MissionFailed'] != 0 else ""
                space_cz = self._build_cz_text(faction.get('SpaceCZ', {}), "SpaceCZs")
                faction_discord_text += f"{space_cz}; " if space_cz != "" else ""
                ground_cz = self._build_cz_text(faction.get('GroundCZ', {}), "GroundCZs")
                faction_discord_text += f"{ground_cz}; " if ground_cz != "" else ""
                faction_name = self._process_faction_name(faction['Faction'])
                system_discord_text += f"[{faction_name}] - {faction_discord_text}\n" if faction_discord_text != "" else ""

                for settlement_name in faction.get('GroundCZSettlements', {}):
                    if faction['GroundCZSettlements'][settlement_name]['enabled'] == CheckStates.STATE_ON:
                        system_discord_text += f"  - {settlement_name} x {faction['GroundCZSettlements'][settlement_name]['count']}\n"

            discord_text += f"```css\n{system['System']}\n{system_discord_text}```" if system_discord_text != "" else ""

        return discord_text.replace("'", "")


    def _build_cz_text(self, cz_data, prefix):
        """
        Create a summary of Conflict Zone activity
        """
        if cz_data == {}: return ""
        text = ""

        if 'l' in cz_data and cz_data['l'] != '0' and cz_data['l'] != '': text += f"{cz_data['l']}xL "
        if 'm' in cz_data and cz_data['m'] != '0' and cz_data['m'] != '': text += f"{cz_data['m']}xM "
        if 'h' in cz_data and cz_data['h'] != '0' and cz_data['h'] != '': text += f"{cz_data['h']}xH "

        if text != '': text = f".{prefix} {text}"
        return text


    def _human_format(self, num):
        """
        Format a BGS value into shortened human-readable text
        """
        num = float('{:.3g}'.format(num))
        magnitude = 0
        while abs(num) >= 1000:
            magnitude += 1
            num /= 1000.0
        return '{}{}'.format('{:f}'.format(num).rstrip('0').rstrip('.'), ['', 'K', 'M', 'B', 'T'][magnitude])


    def _copy_to_clipboard(self, Form, DiscordText):
        """
        Get all text from the Discord field and put it in the Copy buffer
        """
        Form.clipboard_clear()
        Form.event_generate("<<TextModified>>")
        Form.clipboard_append(DiscordText.get('1.0', 'end-1c'))
        Form.update()




class TextPlus(tk.Text):
    """
    Subclass of tk.Text to install a context-sensitive menu on right-click
    """
    def __init__(self, *args, **kwargs):
        tk.Text.__init__(self, *args, **kwargs)
        _rc_menu_install(self)
        # overwrite default class binding so we don't need to return "break"
        self.bind_class("Text", "<Control-a>", self.event_select_all)
        self.bind("<Button-3><ButtonRelease-3>", self.show_menu)

    def event_select_all(self, *args):
        self.focus_force()
        self.tag_add("sel","1.0","end")

    def show_menu(self, e):
        self.menu.tk_popup(e.x_root, e.y_root)


class EntryPlus(ttk.Entry):
    """
    Subclass of ttk.Entry to install a context-sensitive menu on right-click
    """
    def __init__(self, *args, **kwargs):
        ttk.Entry.__init__(self, *args, **kwargs)
        _rc_menu_install(self)
        # overwrite default class binding so we don't need to return "break"
        self.bind_class("Entry", "<Control-a>", self.event_select_all)
        self.bind("<Button-3><ButtonRelease-3>", self.show_menu)

    def event_select_all(self, *args):
        self.focus_force()
        self.selection_range(0, tk.END)

    def show_menu(self, e):
        self.menu.tk_popup(e.x_root, e.y_root)


def _rc_menu_install(w):
    """
    Create a context sensitive menu for a text widget
    """
    w.menu = tk.Menu(w, tearoff=0)
    w.menu.add_command(label="Cut")
    w.menu.add_command(label="Copy")
    w.menu.add_command(label="Paste")
    w.menu.add_separator()
    w.menu.add_command(label="Select all")

    w.menu.entryconfigure("Cut", command=lambda: w.focus_force() or w.event_generate("<<Cut>>"))
    w.menu.entryconfigure("Copy", command=lambda: w.focus_force() or w.event_generate("<<Copy>>"))
    w.menu.entryconfigure("Paste", command=lambda: w.focus_force() or w.event_generate("<<Paste>>"))
    w.menu.entryconfigure("Select all", command=w.event_select_all)
