import math

from dataclasses import dataclass, field
from mathutils import Quaternion, Matrix
from bpy.types import Object
from ....utility import PluginError, CData, indent
from ...oot_collision_classes import decomp_compat_map_CameraSType
from ...collision.properties import OOTCameraPositionProperty
from ..base import Base


@dataclass
class CrawlspaceCamera:
    """This class defines camera data for crawlspaces, if used"""

    points: list[tuple[int, int, int]]
    camIndex: int
    arrayIndex: int = 0

    def __post_init__(self):
        self.points = [self.points[0], self.points[0], self.points[0], self.points[1], self.points[1], self.points[1]]

    def getDataEntryC(self):
        """Returns an entry for the camera data array"""

        return "".join(indent + "{ " + f"{point[0]:6}, {point[1]:6}, {point[2]:6}" + " },\n" for point in self.points)

    def getInfoEntryC(self, posDataName: str):
        """Returns a crawlspace entry for the camera informations array"""

        return indent + "{ " + f"CAM_SET_CRAWLSPACE, 6, &{posDataName}[{self.arrayIndex}]" + " },\n"


@dataclass
class CameraData:
    """This class defines camera data, if used"""

    pos: tuple[int, int, int]
    rot: tuple[int, int, int]
    fov: int
    roomImageOverrideBgCamIndex: int

    def getEntryC(self):
        """Returns an entry for the camera data array"""

        return (
            (indent + "{ " + ", ".join(f"{p:6}" for p in self.pos) + " },\n")
            + (indent + "{ " + ", ".join(f"0x{r:04X}" for r in self.rot) + " },\n")
            + (indent + "{ " + f"{self.fov:6}, {self.roomImageOverrideBgCamIndex:6}, {-1:6}" + " },\n")
        )


@dataclass
class CameraInfo:
    """This class defines camera information data"""

    setting: str
    count: int
    data: CameraData
    camIndex: int
    arrayIndex: int = 0
    hasPosData: bool = False

    def __post_init__(self):
        self.hasPosData = self.data is not None

    def getInfoEntryC(self, posDataName: str):
        """Returns an entry for the camera information array"""

        ptr = f"&{posDataName}[{self.arrayIndex}]" if self.hasPosData else "NULL"
        return indent + "{ " + f"{self.setting}, {self.count}, {ptr}" + " },\n"


@dataclass
class BgCamInformations(Base):
    """This class defines the array of camera informations and the array of the associated data"""

    sceneObj: Object
    transform: Matrix
    name: str
    posDataName: str

    bgCamInfoList: list[CameraInfo] = field(default_factory=list)
    crawlspacePosList: list[CrawlspaceCamera] = field(default_factory=list)
    arrayIdx: int = 0
    crawlspaceCount: int = 6
    camFromIndex: dict[int, CameraInfo | CrawlspaceCamera] = field(default_factory=dict)

    def initCrawlspaceList(self):
        """Returns a list of crawlspace data from every splines objects with the type 'Crawlspace'"""

        crawlspaceObjList: list[Object] = [
            obj
            for obj in self.sceneObj.children_recursive
            if obj.type == "CURVE" and obj.ootSplineProperty.splineType == "Crawlspace"
        ]

        for obj in crawlspaceObjList:
            if self.validateCurveData(obj):
                self.crawlspacePosList.append(
                    CrawlspaceCamera(
                        [
                            [round(value) for value in self.transform @ obj.matrix_world @ point.co]
                            for point in obj.data.splines[0].points
                        ],
                        obj.ootSplineProperty.index,
                    )
                )

    def initBgCamInfoList(self):
        """Returns a list of camera informations from camera objects"""

        camObjList: list[Object] = [obj for obj in self.sceneObj.children_recursive if obj.type == "CAMERA"]
        camPosData: dict[int, CameraData] = {}
        camInfoData: dict[int, CameraInfo] = {}

        for camObj in camObjList:
            camProp: OOTCameraPositionProperty = camObj.ootCameraPositionProperty

            if camProp.camSType == "Custom":
                setting = camProp.camSTypeCustom
            else:
                setting = decomp_compat_map_CameraSType.get(camProp.camSType, camProp.camSType)

            if camProp.hasPositionData:
                if camProp.index in camPosData:
                    raise PluginError(f"ERROR: Repeated camera position index: {camProp.index} for {camObj.name}")

                # Camera faces opposite direction
                pos, rot, _, _ = self.getConvertedTransformWithOrientation(
                    self.transform, self.sceneObj, camObj, Quaternion((0, 1, 0), math.radians(180.0))
                )

                fov = math.degrees(camObj.data.angle)
                camPosData[camProp.index] = CameraData(
                    pos,
                    rot,
                    round(fov * 100 if fov > 3.6 else fov),  # see CAM_DATA_SCALED() macro
                    camObj.ootCameraPositionProperty.bgImageOverrideIndex,
                )

            if camProp.index in camInfoData:
                raise PluginError(f"ERROR: Repeated camera entry: {camProp.index} for {camObj.name}")

            camInfoData[camProp.index] = CameraInfo(
                setting,
                3 if camProp.hasPositionData else 0,  # cameras are using 3 entries in the data array
                camPosData[camProp.index] if camProp.hasPositionData else None,
                camProp.index,
            )
        self.bgCamInfoList = list(camInfoData.values())

    def initCamTable(self):
        for bgCam in self.bgCamInfoList:
            if bgCam.camIndex not in self.camFromIndex:
                self.camFromIndex[bgCam.camIndex] = bgCam
            else:
                raise PluginError(f"ERROR (CameraInfo): Camera index already used: {bgCam.camIndex}")

        for crawlCam in self.crawlspacePosList:
            if crawlCam.camIndex not in self.camFromIndex:
                self.camFromIndex[crawlCam.camIndex] = crawlCam
            else:
                raise PluginError(f"ERROR (Crawlspace): Camera index already used: {crawlCam.camIndex}")

        self.camFromIndex = dict(sorted(self.camFromIndex.items()))
        if list(self.camFromIndex.keys()) != list(range(len(self.camFromIndex))):
            raise PluginError("ERROR: The camera indices are not consecutive!")

        i = 0
        for val in self.camFromIndex.values():
            if isinstance(val, CrawlspaceCamera):
                val.arrayIndex = i
                i += 6  # crawlspaces are using 6 entries in the data array
            elif val.hasPosData:
                val.arrayIndex = i
                i += 3

    def __post_init__(self):
        self.initCrawlspaceList()
        self.initBgCamInfoList()
        self.initCamTable()

    def getDataArrayC(self):
        """Returns the camera data/crawlspace positions array"""

        posData = CData()
        listName = f"Vec3s {self.posDataName}[]"

        # .h
        posData.header = f"extern {listName};\n"

        # .c
        posData.source = listName + " = {\n"
        for val in self.camFromIndex.values():
            if isinstance(val, CrawlspaceCamera):
                posData.source += val.getDataEntryC() + "\n"
            elif val.hasPosData:
                posData.source += val.data.getEntryC() + "\n"
        posData.source = posData.source[:-1]  # remove extra newline
        posData.source += "};\n\n"

        return posData

    def getInfoArrayC(self):
        """Returns the array containing the informations of each cameras"""

        bgCamInfoData = CData()
        listName = f"BgCamInfo {self.name}[]"

        # .h
        bgCamInfoData.header = f"extern {listName};\n"

        # .c
        bgCamInfoData.source = (
            (listName + " = {\n")
            + "".join(val.getInfoEntryC(self.posDataName) for val in self.camFromIndex.values())
            + "};\n\n"
        )

        return bgCamInfoData
