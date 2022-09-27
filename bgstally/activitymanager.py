from copy import deepcopy
from os import listdir, mkdir, path, remove

from config import config

from bgstally.activity import Activity
from bgstally.debug import Debug
from bgstally.missionlog import MissionLog
from bgstally.tick import Tick

FILE_LEGACY_CURRENTDATA = "Today Data.txt"
FILE_LEGACY_PREVIOUSDATA = "Yesterday Data.txt"
FOLDER_ACTIVITYDATA = "activitydata"
FILE_SUFFIX = ".json"


class ActivityManager:
    """
    Handles a list of Activity objects, each representing the data for a tick, handles updating activity, and manages
    the data storage of Activity logs.
    """

    def __init__(self, plugindir: str, mission_log: MissionLog, current_tick: Tick):
        self.plugindir = plugindir
        self.mission_log = mission_log

        self.activitydata = []
        self.current_activity = None

        self._load(current_tick)


    def save(self):
        """
        Save all activity data
        """
        for activity in self.activitydata:
            activity.save(path.join(self.plugindir, FOLDER_ACTIVITYDATA, activity.tick_id + FILE_SUFFIX))


    def get_current_activity(self):
        """
        Get the latest Activity, i.e. current tick
        """
        return self.current_activity


    def get_previous_activity(self):
        """
        Get the previous Activity. This is hacky as we just return the second item in the sorted activity list.
        We'll probably do away with this specific function in future, and generalise this into being able to
        access any previous available activity, with a UI to choose from previous activities.
        """
        if len(self.activitydata) < 2: return None
        else: return self.activitydata[1]


    def new_tick(self, tick: Tick):
        """
        New tick detected, duplicate the current Activity object
        """
        new_activity = deepcopy(self.current_activity)
        new_activity.tick_id = tick.tick_id
        new_activity.tick_time = tick.tick_time
        new_activity.discord_messageid = None
        new_activity.clear_activity(self.mission_log)
        self.activitydata.append(new_activity)
        self.activitydata.sort(reverse=True)
        self.current_activity = new_activity


    def _load(self, current_tick: Tick):
        """
        Load all activity data
        """
        # Handle modern data from subfolder
        filepath = path.join(self.plugindir, FOLDER_ACTIVITYDATA)
        if not path.exists(filepath): mkdir(filepath)
        for activityfilename in listdir(filepath):
            if activityfilename.endswith(FILE_SUFFIX):
                activity = Activity(self.plugindir, Tick())
                activity.load(path.join(filepath, activityfilename))
                self.activitydata.append(activity)
                if activity.tick_id == current_tick.tick_id: self.current_activity = activity

        # Handle legacy data if it exists - parse and migrate to new format
        filepath = path.join(self.plugindir, FILE_LEGACY_CURRENTDATA)
        if path.exists(filepath): self._convert_legacy_data(filepath, current_tick, config.get_str('XDiscordCurrentMessageID'))
        filepath = path.join(self.plugindir, FILE_LEGACY_PREVIOUSDATA)
        if path.exists(filepath): self._convert_legacy_data(filepath, Tick(), config.get_str('XDiscordPreviousMessageID')) # Fake a tick for previous legacy - we don't have tick_id or tick_time

        self.activitydata.sort(reverse=True)


    def _convert_legacy_data(self, filepath: str, tick: Tick, discordmessageid: str):
        """
        Convert a legacy activity data file to new location and format.
        """
        for activity in self.activitydata:
            if activity.tick_id == tick.tick_id:
                # We already have modern data for this legacy tick ID, ignore it and delete the file
                Debug.logger.warning(f"Tick data already exists for tick {tick.tick_id} when loading legacy data. Ignoring legacy data.")
                # TODO: remove(filepath)
                return

        activity = Activity(self.plugindir, tick, discordmessageid)
        activity.load_legacy_data(filepath)
        self.activitydata.append(activity)
        if activity.tick_id == tick.tick_id: self.current_activity = activity
