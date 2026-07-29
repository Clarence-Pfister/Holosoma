# Kimodo で生成した SMPL-X モーションを Holosoma で G1 23-DoF 向けにリターゲティングする手順

*This document in [English](kimodo-g1-23dof.md).*

このガイドでは、Kimodo で生成した SMPL-X/AMASS モーションを Holosoma 用の形式に変換し、Unitree G1 23-DoF ロボット向けにリターゲティングする手順を説明します。

全体の流れは以下のとおりです。

1. Kimodo で人間の SMPL-X モーションを生成します。
2. Kimodo の AMASS 形式ファイルを、Holosoma の前処理が想定する形式に変換します。
3. SMPL-X の前処理を実行し、グローバル関節位置を抽出します。
4. 前処理した SMPL-X モーションを G1 23-DoF 向けにリターゲティングします。
5. 元のモーションと、リターゲティング後のロボットモーションを可視化します。

## 前提条件

- セットアップ済みの [Kimodo](https://github.com/nv-tlabs/kimodo) 環境。
- Holosoma リターゲティング用 Docker コンテナにマウントする [Holosoma](https://github.com/amazon-far/holosoma) リポジトリ。
- ローカルで `holosoma-retargeting:latest` としてタグ付けした Holosoma リターゲティング用 Docker イメージ。
- Holosoma リポジトリ内に配置した [SMPL-X モデルファイル](https://smpl-x.is.tue.mpg.de/)。

```text
holosoma/smplx/SMPLX_NEUTRAL.npz
holosoma/smplx/SMPLX_MALE.npz
holosoma/smplx/SMPLX_FEMALE.npz
```

最低限、AMASS/SMPL-X シーケンスで使用する `gender` に対応したファイルが必要です。3 つすべてを配置しておくと、最も扱いやすい構成になります。

## パスとモーション名の設定

自分の環境とモーションに合わせて、以下の値を調整してください。

```bash
export HOST_HOLOSOMA_DIR=/path/to/holosoma
export HOST_KIMODO_DIR=/path/to/kimodo
export MOTION_NAME=my_motion
export PROMPT="Describe the motion here."
export DATASET_NAME=kimodo
export TASK_NAME=holosoma_amass_${DATASET_NAME}_${MOTION_NAME}_stageii
```

Docker 内では、Holosoma リポジトリが以下の場所にマウントされます。

```text
/workspace/holosoma
```

## 1. Kimodo で SMPL-X モーションを生成する

この手順は、Holosoma Docker コンテナの外、ホスト側で実行します。

```bash
cd "$HOST_KIMODO_DIR"
conda activate kimodo

kimodo_gen "$PROMPT" \
  --model Kimodo-SMPLX-RP-v1 \
  --duration 3.0 \
  --output "$HOST_KIMODO_DIR/outputs/$MOTION_NAME"
```

Kimodo で生成した AMASS 形式の `.npz` ファイルを Holosoma リポジトリにコピーまたは移動します。

```bash
mkdir -p "$HOST_HOLOSOMA_DIR/motions/kimodo_amass"
cp "$HOST_KIMODO_DIR/outputs/$MOTION_NAME"/*.npz \
  "$HOST_HOLOSOMA_DIR/motions/kimodo_amass/${MOTION_NAME}_amass.npz"
```

## 2. Holosoma Docker コンテナに入る

この手順はホスト側で実行します。

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

Docker 内で、Holosoma のリターゲティング環境を初期化します。

```bash
source /workspace/holosoma/scripts/source_retargeting_setup.sh
cd /workspace/holosoma/src/holosoma_retargeting/holosoma_retargeting

export MOTION_NAME=my_motion
export DATASET_NAME=kimodo
export TASK_NAME=holosoma_amass_${DATASET_NAME}_${MOTION_NAME}_stageii
```

## 3. SMPL-X 前処理用の依存関係をインストールする

Docker 内で一度だけ実行します。

```bash
cd /workspace/holosoma
mkdir -p thirdparty
cd thirdparty

git clone https://github.com/nghorbani/human_body_prior.git
cd human_body_prior
pip install -e . --no-deps
pip install transforms3d
```

Holosoma パッケージのディレクトリに戻ります。

```bash
cd /workspace/holosoma/src/holosoma_retargeting/holosoma_retargeting
```

## 4. Kimodo の AMASS ファイルを Holosoma 用の AMASS 形式に変換する

この手順では、Kimodo の AMASS 形式ファイルに、Holosoma が必要とする結合済みの `poses` 配列を追加します。

```bash
mkdir -p /workspace/holosoma/motions/holosoma_amass/${DATASET_NAME}

python data_utils/kimodo_amass_to_holosoma_amass.py \
  /workspace/holosoma/motions/kimodo_amass/${MOTION_NAME}_amass.npz \
  /workspace/holosoma/motions/holosoma_amass/${DATASET_NAME}/${MOTION_NAME}_stageii.npz
```

## 5. AMASS/SMPL-X をリターゲティング用に前処理する

AMASS/SMPL-X のパラメータファイルを、グローバルな SMPL-X 関節位置に変換します。

```bash
python data_utils/prep_amass_smplx_for_rt.py \
  --amass-root-folder /workspace/holosoma/motions/holosoma_amass \
  --output-folder /workspace/holosoma/motions/holosoma_smplx \
  --model-root-folder /workspace/holosoma
```

前処理後のファイルは、以下の場所に出力されます。

```text
/workspace/holosoma/motions/holosoma_smplx/${TASK_NAME}.npz
```

## 6. 元の SMPL-X モーションを可視化する

リターゲティング前に、人間側の元のモーションを確認するために使用します。

```bash
python data_utils/visualize_smplx_joints.py \
  /workspace/holosoma/motions/holosoma_smplx/${TASK_NAME}.npz
```

ターミナルに表示される Viser の URL を開きます。ビューアには、フレームスライダー、再生/一時停止コントロール、FPS コントロールがあります。

## 7. G1 23-DoF 向けにリターゲティングする

基本コマンドは以下のとおりです。

```bash
python examples/robot_retarget.py \
  --data-path /workspace/holosoma/motions/holosoma_smplx \
  --task-type robot_only \
  --task-name "$TASK_NAME" \
  --data-format smplx \
  --robot g1_23dof \
  --save-dir /workspace/holosoma/motions/retargeted_g1_23dof
```

`--task-name` には、前処理後の SMPL-X ファイル名から `.npz` を除いた名前を指定します。

ロボットモーションは、以下の場所に出力されます。

```text
/workspace/holosoma/motions/retargeted_g1_23dof/${TASK_NAME}.npz
```

## 8. 任意のリターゲティング調整パラメータ

以下のパラメータは、最適化で用いるソフトコストです。厳密な制約ではなく、オプティマイザが特定の解を選びやすくするための重みです。

### 直接的なキーポイント追従

マッピング済みのすべてのキーポイントを追跡対象にします。

```bash
--retargeter.keypoint-tracking-weight 5.0
```

肩、肘、手首、手のキーポイントだけを追跡対象にします。

```bash
--retargeter.arm-keypoint-tracking-weight 50.0
```

腰、膝、足首、足、つま先のキーポイントだけを追跡対象にします。

```bash
--retargeter.leg-keypoint-tracking-weight 20.0
```

interaction-mesh による結果の全体的な形は合っているものの、個々の手足が元のモーションに十分追従していない場合に使用します。

### ルート姿勢の追従

元のモーションの yaw 方向に追従させたり、最適化で得られたルートの roll/pitch を最初のフレームの値に近づけたりするために使用します。

```bash
--retargeter.root-yaw-tracking-weight 20.0
--retargeter.root-roll-tracking-weight 20.0
--retargeter.root-pitch-tracking-weight 20.0
```

ロボットのベースが回転する、横に傾く、または意図した動きから外れて pitch 方向に傾く場合に使用します。

## 9. リターゲティング後のロボットモーションを可視化する

robot-only のモーションでは、`--no-assume-object-in-qpos` を指定します。

```bash
python viser_player.py \
  --qpos-npz /workspace/holosoma/motions/retargeted_g1_23dof/${TASK_NAME}.npz \
  --robot-urdf models/g1_23dof/g1_23dof_23dof.urdf \
  --no-assume-object-in-qpos \
  --loop
```

ターミナルに表示される Viser の URL を開きます。
