# Kimodo to Holosoma G1 23-DoF Retargeting

*Read this in [日本語](kimodo-g1-23dof.ja.md).*

This guide converts a Kimodo-generated SMPL-X/AMASS motion into a Holosoma motion and retargets it to the Unitree G1 23-DoF robot.

The workflow is:

1. Generate a human SMPL-X motion with Kimodo.
2. Convert the Kimodo AMASS-style file to the format expected by Holosoma preprocessing.
3. Run SMPL-X preprocessing to extract global joint positions.
4. Retarget the processed SMPL-X motion to G1 23-DoF.
5. Visualize the source and retargeted robot motions.

## Prerequisites

- A working [Kimodo](https://github.com/nv-tlabs/kimodo) environment.
- A [Holosoma](https://github.com/amazon-far/holosoma) repo mounted into the Holosoma retargeting Docker image.
- The Holosoma retargeting Docker image, tagged locally as `holosoma-retargeting:latest`.
- [SMPL-X model files](https://smpl-x.is.tue.mpg.de/) placed in the Holosoma repo:

```text
holosoma/smplx/SMPLX_NEUTRAL.npz
holosoma/smplx/SMPLX_MALE.npz
holosoma/smplx/SMPLX_FEMALE.npz
```

At minimum, the gender file used by your AMASS/SMPL-X sequence must exist. Keeping all three is the simplest setup.

## Paths And Motion Variables

Adjust these values for your machine and motion:

```bash
export HOST_HOLOSOMA_DIR=/path/to/holosoma
export HOST_KIMODO_DIR=/path/to/kimodo
export MOTION_NAME=my_motion
export PROMPT="Describe the motion here."
export DATASET_NAME=kimodo
export TASK_NAME=holosoma_amass_${DATASET_NAME}_${MOTION_NAME}_stageii
```

Inside Docker, the Holosoma repo is mounted at:

```text
/workspace/holosoma
```

## 1. Generate A SMPL-X Motion With Kimodo

Run this on the host, outside the Holosoma Docker container:

```bash
cd "$HOST_KIMODO_DIR"
conda activate kimodo

kimodo_gen "$PROMPT" \
  --model Kimodo-SMPLX-RP-v1 \
  --duration 3.0 \
  --output "$HOST_KIMODO_DIR/outputs/$MOTION_NAME"
```

Copy or move the generated AMASS-style `.npz` into the Holosoma repo:

```bash
mkdir -p "$HOST_HOLOSOMA_DIR/motions/kimodo_amass"
cp "$HOST_KIMODO_DIR/outputs/$MOTION_NAME"/*.npz \
  "$HOST_HOLOSOMA_DIR/motions/kimodo_amass/${MOTION_NAME}_amass.npz"
```

## 2. Enter The Holosoma Docker Container

Run this on the host:

```bash
docker run --rm -it \
  --name holosoma-retarget \
  --network host \
  --ipc host \
  --privileged \
  -v "$HOST_HOLOSOMA_DIR":/workspace/holosoma \
  -w /workspace/holosoma \
  holosoma-retargeting:latest \
  /bin/bash
```

Inside Docker, initialize the Holosoma retargeting environment:

```bash
source /workspace/holosoma/scripts/source_retargeting_setup.sh
cd /workspace/holosoma/src/holosoma_retargeting/holosoma_retargeting

export MOTION_NAME=my_motion
export DATASET_NAME=kimodo
export TASK_NAME=holosoma_amass_${DATASET_NAME}_${MOTION_NAME}_stageii
```

## 3. Install SMPL-X Preprocessing Dependency

Run this once inside Docker:

```bash
cd /workspace/holosoma
mkdir -p thirdparty
cd thirdparty

git clone https://github.com/nghorbani/human_body_prior.git
cd human_body_prior
pip install -e . --no-deps
pip install transforms3d
```

Return to the Holosoma package directory:

```bash
cd /workspace/holosoma/src/holosoma_retargeting/holosoma_retargeting
```

## 4. Convert Kimodo AMASS To Holosoma AMASS

This adds Holosoma's expected combined `poses` array to the Kimodo AMASS-style file.

```bash
mkdir -p /workspace/holosoma/motions/holosoma_amass/${DATASET_NAME}

python data_utils/kimodo_amass_to_holosoma_amass.py \
  /workspace/holosoma/motions/kimodo_amass/${MOTION_NAME}_amass.npz \
  /workspace/holosoma/motions/holosoma_amass/${DATASET_NAME}/${MOTION_NAME}_stageii.npz
```

## 5. Preprocess AMASS/SMPL-X For Retargeting

This converts the AMASS/SMPL-X parameter file into global SMPL-X joint positions.

```bash
python data_utils/prep_amass_smplx_for_rt.py \
  --amass-root-folder /workspace/holosoma/motions/holosoma_amass \
  --output-folder /workspace/holosoma/motions/holosoma_smplx \
  --model-root-folder /workspace/holosoma
```

Expected processed file:

```text
/workspace/holosoma/motions/holosoma_smplx/${TASK_NAME}.npz
```

## 6. Visualize The Source SMPL-X Motion

Use this to check the human/source motion before retargeting:

```bash
python data_utils/visualize_smplx_joints.py \
  /workspace/holosoma/motions/holosoma_smplx/${TASK_NAME}.npz
```

Open the Viser URL printed in the terminal. The viewer includes a frame slider, play/pause control, and FPS control.

## 7. Retarget To G1 23-DoF

Basic command:

```bash
python examples/robot_retarget.py \
  --data-path /workspace/holosoma/motions/holosoma_smplx \
  --task-type robot_only \
  --task-name "$TASK_NAME" \
  --data-format smplx \
  --robot g1_23dof \
  --save-dir /workspace/holosoma/motions/retargeted_g1_23dof
```

The `--task-name` must match the processed SMPL-X file name without `.npz`.

Expected robot output:

```text
/workspace/holosoma/motions/retargeted_g1_23dof/${TASK_NAME}.npz
```

## 8. Optional Retargeting Knobs

These are soft optimization costs. They do not force hard constraints; they only make the optimizer prefer certain solutions.

### Direct Keypoint Tracking

Track all mapped keypoints:

```bash
--retargeter.keypoint-tracking-weight 5.0
```

Track only shoulder/elbow/wrist/hand keypoints:

```bash
--retargeter.arm-keypoint-tracking-weight 50.0
```

Track only hip/knee/ankle/foot/toe keypoints:

```bash
--retargeter.leg-keypoint-tracking-weight 20.0
```

Use these when the interaction-mesh result has the right global shape but individual limbs do not follow the source well enough.

### Root Orientation Tracking

Track source-facing yaw, or keep the solved root roll/pitch close to the first solved frame:

```bash
--retargeter.root-yaw-tracking-weight 20.0
--retargeter.root-roll-tracking-weight 20.0
--retargeter.root-pitch-tracking-weight 20.0
```

Use these if the robot base rotates, leans sideways, or pitches forward/backward away from the intended motion.

## 9. Visualize The Retargeted Robot Motion

For robot-only motions, use `--no-assume-object-in-qpos`.

```bash
python viser_player.py \
  --qpos-npz /workspace/holosoma/motions/retargeted_g1_23dof/${TASK_NAME}.npz \
  --robot-urdf models/g1_23dof/g1_23dof_23dof.urdf \
  --no-assume-object-in-qpos \
  --loop
```

Open the Viser URL printed in the terminal.
