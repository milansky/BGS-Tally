import json
import os.path
import re
from datetime import datetime, timedelta
from typing import Dict

import requests

from bgstally.constants import DATETIME_FORMAT_JOURNAL
from bgstally.debug import Debug

FILENAME = "targetlog.json"
TIME_TARGET_LOG_EXPIRY_D = 30
URL_INARA_API = "https://inara.cz/inapi/v1/"
DATETIME_FORMAT_INARA = "%Y-%m-%dT%H:%M:%SZ"


class TargetLog:
    """
    Handle a log of all targeted players
    """
    cmdr_name_pattern:re.Pattern = re.compile(r"\$cmdr_decorate\:#name=([^]]*);")

    def __init__(self, bgstally):
        self.bgstally = bgstally
        self.targetlog = []
        self.cmdr_cache = {}
        self.load()


    def load(self):
        """
        Load state from file
        """
        file = os.path.join(self.bgstally.plugin_dir, FILENAME)
        if os.path.exists(file):
            with open(file) as json_file:
                self.targetlog = json.load(json_file)


    def save(self):
        """
        Save state to file
        """
        file = os.path.join(self.bgstally.plugin_dir, FILENAME)
        with open(file, 'w') as outfile:
            json.dump(self.targetlog, outfile)


    def get_targetlog(self):
        """
        Get the current target log
        """
        return self.targetlog


    def get_target_info(self, cmdr_name:str):
        """
        Look up and return information on a CMDR
        """
        return next((item for item in self.targetlog if item['TargetName'] == cmdr_name), None)


    def ship_targeted(self, journal_entry: Dict, system: str):
        """
        A ship targeted event has been received, if it's a player, add it to the target log
        """
        # { "timestamp":"2022-10-09T06:49:06Z", "event":"ShipTargeted", "TargetLocked":true, "Ship":"cutter", "Ship_Localised":"Imperial Cutter", "ScanStage":3, "PilotName":"$cmdr_decorate:#name=[Name];", "PilotName_Localised":"[CMDR Name]", "PilotRank":"Elite", "SquadronID":"TSPA", "ShieldHealth":100.000000, "HullHealth":100.000000, "LegalStatus":"Clean" }
        if not 'ScanStage' in journal_entry or journal_entry['ScanStage'] < 3: return
        if not 'PilotName' in journal_entry: return

        cmdr_match = self.cmdr_name_pattern.match(journal_entry['PilotName'])
        if not cmdr_match: return

        cmdr_name = cmdr_match.group(1)

        cmdr_data = {'TargetName': cmdr_name,
                    'System': system,
                    'SquadronID': journal_entry['SquadronID'] if 'SquadronID' in journal_entry else "----",
                    'Ship': journal_entry['Ship'],
                    'LegalStatus': journal_entry['LegalStatus'],
                    'Timestamp': journal_entry['timestamp']}

        cmdr_data = self._fetch_cmdr_info(cmdr_name, cmdr_data)
        self.targetlog.append(cmdr_data)


    def _fetch_cmdr_info(self, cmdr_name:str, cmdr_data:Dict):
        """
        Fetch additional CMDR data from Inara and enhance the cmdr_data Dict with it
        """
        if cmdr_name in self.cmdr_cache: return self.cmdr_cache[cmdr_name]

        payload = {
            'header': {
                'appName': self.bgstally.plugin_name,
                'appVersion': self.bgstally.version,
                'isBeingDeveloped': "true",
                'APIkey': self.bgstally.config.apikey_inara()
            },
            'events': [
                {
                    'eventName': "getCommanderProfile",
                    'eventTimestamp': datetime.utcnow().strftime(DATETIME_FORMAT_INARA),
                    'eventData': {
                        'searchName': cmdr_name
                    }
                }
            ]
        }

        try:
            response = requests.post(URL_INARA_API, json=payload, timeout=10)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            Debug.logger.error(f"Unable to fetch CMDR Profile from Inara", exc_info=e)
            return cmdr_data

        data = response.json()
        if not 'events' in data or len(data['events']) == 0 or not 'eventData' in data['events'][0]: return cmdr_data

        event_data = data['events'][0]['eventData']

        if 'commanderRanksPilot' in event_data:
            cmdr_data['ranks'] = event_data['commanderRanksPilot']
        if 'commanderSquadron' in event_data:
            cmdr_data['squadron'] = event_data['commanderSquadron']
        if 'inaraURL' in event_data:
            cmdr_data['inaraURL'] = event_data['inaraURL']

        self.cmdr_cache[cmdr_name] = cmdr_data
        return cmdr_data


    def _expire_old_targets(self):
        """
        Clear out all targets older than 7 days from the target log
        """
        for target in reversed(self.targetlog):
            timedifference = datetime.utcnow() - datetime.strptime(target['Timestamp'], DATETIME_FORMAT_JOURNAL)
            if timedifference > timedelta(days = TIME_TARGET_LOG_EXPIRY_D):
                self.targetlog.remove(target)