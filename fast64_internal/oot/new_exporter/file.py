import os
import re

from dataclasses import dataclass
from typing import TYPE_CHECKING
from ..oot_utility import ExportInfo, getSceneDirFromLevelName
from .spec import Spec
from .scene_table import SceneTable

if TYPE_CHECKING:
    from .exporter import OOTSceneExport


@dataclass
class Files:
    exporter: "OOTSceneExport"

    def modifySceneFiles(self):
        if self.exporter.exportInfo.customSubPath is not None:
            sceneDir = self.exporter.exportInfo.customSubPath + self.exporter.exportInfo.name
        else:
            sceneDir = getSceneDirFromLevelName(self.exporter.sceneName)

        scenePath = os.path.join(self.exporter.exportInfo.exportPath, sceneDir)
        for filename in os.listdir(scenePath):
            filepath = os.path.join(scenePath, filename)
            if os.path.isfile(filepath):
                match = re.match(self.exporter.scene.name + "\_room\_(\d+)\.[ch]", filename)
                if match is not None and int(match.group(1)) >= len(self.exporter.scene.roomList):
                    os.remove(filepath)

    def editFiles(self):
        self.modifySceneFiles()
        Spec().editSpec(self.exporter)
        SceneTable().editSceneTable(self.exporter)