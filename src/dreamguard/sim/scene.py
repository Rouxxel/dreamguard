"""Bimanual i2rt YAM scene: two Menagerie YAM arms on a table with three cameras."""

from __future__ import annotations

from pathlib import Path

import mujoco

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
YAM_XML = ASSETS_DIR / "i2rt_yam" / "yam.xml"

TABLE_TOP_Z = 0.75
ARM_BASE_Y = 0.30
ARM_PREFIX = {"right": "right_", "left": "left_"}
# Dream-1 camera roles -> MuJoCo camera names
CAMERAS = {"overhead": "overhead", "wrist_l": "left_wrist", "wrist_r": "right_wrist"}
CAMERA_WIDTH, CAMERA_HEIGHT = 320, 176
HOME_JOINTS = (0.0, 1.047, 1.047, 0.0, 0.0, 0.0)  # the Menagerie "home" keyframe
FINGER_OPEN_M = 0.041  # finger actuator ctrlrange upper bound


def _add_arm(spec: mujoco.MjSpec, arm: str, y: float) -> None:
    arm_spec = mujoco.MjSpec.from_file(str(YAM_XML))
    # Mounted on top of the gripper (+y of link_6), looking along the fingers (+z) toward the
    # grasp point. MuJoCo cameras look along their -z axis.
    arm_spec.body("link_6").add_camera(
        name="wrist", pos=[0.0, 0.10, 0.09],
        xyaxes=[-1.0, 0.0, 0.0, 0.0, 0.848, 0.53], fovy=80,
    )
    frame = spec.worldbody.add_frame(pos=[0.0, y, TABLE_TOP_Z])
    spec.attach(arm_spec, prefix=ARM_PREFIX[arm], frame=frame)


def _add_object(spec: mujoco.MjSpec, name: str, pos, geom_type, size, rgba) -> None:
    body = spec.worldbody.add_body(name=name, pos=pos)
    body.add_freejoint(name=f"{name}_free")
    body.add_geom(type=geom_type, size=size, rgba=rgba, mass=0.05, friction=[1.0, 0.01, 0.001])


def build_spec() -> mujoco.MjSpec:
    spec = mujoco.MjSpec()
    spec.modelname = "dreamguard_bimanual_yam"
    spec.option.integrator = mujoco.mjtIntegrator.mjINT_IMPLICITFAST
    spec.option.timestep = 0.002
    spec.visual.global_.offwidth = 640
    spec.visual.global_.offheight = 480

    world = spec.worldbody
    world.add_light(pos=[0.4, 0.0, 2.5], dir=[0.0, 0.0, -1.0], diffuse=[0.8, 0.8, 0.8])
    world.add_light(pos=[1.5, 1.0, 2.0], dir=[-0.6, -0.4, -0.7], diffuse=[0.4, 0.4, 0.4])
    world.add_geom(
        name="floor", type=mujoco.mjtGeom.mjGEOM_PLANE, size=[3.0, 3.0, 0.1],
        rgba=[0.55, 0.57, 0.6, 1.0],
    )
    world.add_geom(
        name="table", type=mujoco.mjtGeom.mjGEOM_BOX,
        pos=[0.35, 0.0, TABLE_TOP_Z / 2], size=[0.5, 0.8, TABLE_TOP_Z / 2],
        rgba=[0.76, 0.6, 0.42, 1.0],
    )
    _add_object(spec, "red_cube", [0.45, -0.12, TABLE_TOP_Z + 0.025],
                mujoco.mjtGeom.mjGEOM_BOX, [0.025, 0.025, 0.025], [0.85, 0.15, 0.15, 1.0])
    _add_object(spec, "blue_ball", [0.42, 0.14, TABLE_TOP_Z + 0.03],
                mujoco.mjtGeom.mjGEOM_SPHERE, [0.03, 0.0, 0.0], [0.15, 0.3, 0.85, 1.0])
    _add_object(spec, "green_block", [0.58, 0.02, TABLE_TOP_Z + 0.02],
                mujoco.mjtGeom.mjGEOM_BOX, [0.04, 0.02, 0.02], [0.2, 0.7, 0.3, 1.0])

    # Behind and above the arms, looking at the table (right arm on the right of the image).
    world.add_camera(
        name="overhead", pos=[-0.30, 0.0, 1.45],
        xyaxes=[0.0, -1.0, 0.0, 0.6823, 0.0, 0.7311], fovy=70,
    )
    _add_arm(spec, "right", -ARM_BASE_Y)
    _add_arm(spec, "left", ARM_BASE_Y)
    return spec


def build_model() -> mujoco.MjModel:
    return build_spec().compile()
