# Model provenance

## MotionBERT

- Source repository: https://github.com/Walter0807/MotionBERT
- Official model hosting: https://huggingface.co/walterzhu/MotionBERT
- Checkpoint: checkpoint/pose3d/FT_MB_lite_MB_ft_h36m_global_lite/best_epoch.bin
- Official download: https://huggingface.co/walterzhu/MotionBERT/resolve/main/checkpoint/pose3d/FT_MB_lite_MB_ft_h36m_global_lite/best_epoch.bin
- Configuration: https://github.com/Walter0807/MotionBERT/blob/main/configs/pose3d/MB_ft_h36m_global_lite.yaml
- In-the-wild input reference: https://github.com/Walter0807/MotionBERT/blob/main/lib/data/dataset_wild.py
- Local SHA-256: 9811155371db4ca5d20f31a36a232d41012e12e1333882888a564d741861148f
- Parameters: 16,001,549
- Role: fine-tuned monocular 2D-to-3D H36M pose lifting.

The adapter preserves confidence as channel 3 and normalizes image x/y with image dimensions. Pelvis, neck and spine are explicit midpoints; the missing head-top keypoint is approximated by extrapolating nose away from neck and reducing confidence. This approximation is documented, not described as a measured head-top joint. MediaPipe world coordinates are used for camera metrics, not as MotionBERT input channels.

Reference paper: Zhu, W., Ma, X., Liu, Z., Liu, L., Wu, W., and Wang, Y. MotionBERT: A Unified Perspective on Learning Human Motion Representations. ICCV 2023. https://openaccess.thecvf.com/content/ICCV2023/html/Zhu_MotionBERT_A_Unified_Perspective_on_Learning_Human_Motion_Representations_ICCV_2023_paper.html

MotionBERT code is distributed under Apache-2.0; its upstream license is included. Stochastic-depth helpers retain Ross Wightman's original attribution.

## Camera model

MediaPipe Tasks Vision 0.10.32 and the official pose_landmarker_lite float16 model are downloaded during setup; WASM assets are copied from the locked npm package. Model source: https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task

Guide: https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker/web_js

The application displays no trained exercise classifier output and does not use the rough archive's synthetic classifier checkpoints in its active pipeline.

The active MLP, Attention, Block and DSTformer class syntax trees were compared against the official upstream implementation and matched exactly. The bundled model is not an unrelated replacement architecture.
