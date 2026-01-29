# Model Catalogue (OpenPCDet, KITTI pretrained)

This catalogue focuses on models that are practical for indoor LiDAR pedestrian prelabels using OpenPCDet. All models below are KITTI-pretrained and run in `external/openpcdet`.

## Recommended (start here)

### PointRCNN (IoU)
- Config: `configs/pcdet/pointrcnn_iou_budde.yaml` (customized for lower point counts)
- Checkpoint: `external/openpcdet/ckpts/pointrcnn_iou_kitti.pth`
- Notes: Stronger pedestrian boxes than PointPillars. Slower but higher quality. Good baseline for indoor pedestrian prelabels.

### PV-RCNN
- Config: `external/openpcdet/tools/cfgs/kitti_models/pv_rcnn.yaml`
- Checkpoint: `external/openpcdet/ckpts/pv_rcnn_8369.pth` (KITTI pretrained)
- Notes: Often improves recall for pedestrians. Slower than PointRCNN but can be more stable.

### CenterPoint (KITTI)
- Config: `external/openpcdet/tools/cfgs/kitti_models/centerpoint.yaml` (or closest available)
- Checkpoint: `external/openpcdet/ckpts/centerpoint_kitti.pth` (if present)
- Notes: Fast and typically strong. Worth testing if the config exists in your OpenPCDet version.

## Secondary options (good to compare)

### SECOND
- Config: `external/openpcdet/tools/cfgs/kitti_models/second.yaml`
- Checkpoint: `external/openpcdet/ckpts/second_7862.pth`
- Notes: Older baseline; good for sanity checks and speed.

### Part-A2
- Config: `external/openpcdet/tools/cfgs/kitti_models/parta2.yaml`
- Checkpoint: `external/openpcdet/ckpts/parta2_7875.pth`
- Notes: Can be decent for pedestrians but heavier; test if PV-RCNN is too slow.

### Voxel R-CNN
- Config: `external/openpcdet/tools/cfgs/kitti_models/voxel_rcnn_car.yaml`
- Checkpoint: `external/openpcdet/ckpts/voxel_rcnn_car.pth`
- Notes: Usually strong for cars; may not help pedestrians unless a multi-class config is available.

## Not recommended for indoor pedestrians (but available)

### PointPillars
- Config: `external/openpcdet/tools/cfgs/kitti_models/pointpillar.yaml`
- Checkpoint: `external/openpcdet/ckpts/pointpillar_kitti.pth`
- Notes: Very fast but low precision in indoor scenes and tends to hallucinate cars.

## Practical guidance

1) Start with PointRCNN IoU for quality.
2) Add PV-RCNN for a second pass; compare recall vs PointRCNN.
3) If CenterPoint config exists, test it for speed/quality balance.
4) Merge detections across models (NMS/WBF) only after per-model tuning.

## Checkpoints

Not all checkpoints are bundled. Keep them under `external/openpcdet/ckpts/` and update paths in your commands.
