import { FilesetResolver, PoseLandmarker } from '@mediapipe/tasks-vision';
let landmarker: PoseLandmarker | null = null;
// A classic worker lets MediaPipe import its matching local WASM loader.
const context = self as unknown as { onmessage: ((event: MessageEvent) => void) | null; postMessage: (data: unknown) => void; location: Location };
context.onmessage = async ({ data }) => {
  try {
    if (data.type === 'init') {
      const origin = context.location.origin;
      const vision = await FilesetResolver.forVisionTasks(origin + '/mediapipe/wasm');
      landmarker = await PoseLandmarker.createFromOptions(vision, {
        baseOptions: { modelAssetPath: origin + '/mediapipe/pose_landmarker_lite.task', delegate: 'CPU' },
        runningMode: 'VIDEO', numPoses: 1, minPoseDetectionConfidence: .5,
        minPosePresenceConfidence: .5, minTrackingConfidence: .5, outputSegmentationMasks: false,
      });
      context.postMessage({ id: data.id, ready: true });
    } else if (data.type === 'frame') {
      if (!landmarker) throw new Error('Joint tracker has not finished loading.');
      const start = performance.now();
      const result = landmarker.detectForVideo(data.frame, data.timestamp);
      context.postMessage({ id: data.id, image: result.landmarks[0] || [], world: result.worldLandmarks[0] || [], inferenceMs: performance.now() - start });
    }
  } catch (error) {
    context.postMessage({ id: data.id, error: error instanceof Error ? error.message : String(error) });
  } finally { data.frame?.close(); }
};
