// Capture has its own cancellable lifecycle; late permission results never leave a camera running.
export function errorText(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  if (error && typeof error === 'object' && 'message' in error) return String(error.message);
  return 'The camera or tracker returned an unexpected error.';
}
export function cameraError(error: unknown): string {
  const name = error && typeof error === 'object' && 'name' in error ? String(error.name) : '';
  if (name === 'NotAllowedError' || name === 'SecurityError') return 'Camera access is blocked. Allow camera access for this page in your browser, then try again. You can also open http://localhost:3000 in Chrome or Edge.';
  if (name === 'NotFoundError') return 'No camera is available. Connect a webcam and select it from the camera list.';
  if (name === 'NotReadableError' || name === 'AbortError') return 'The camera could not be opened. Close any other app using it, then try again.';
  return errorText(error);
}
export function stopStream(stream: MediaStream | null) { stream?.getTracks().forEach(track => track.stop()); }
export async function openCamera(deviceId: string, signal: AbortSignal): Promise<MediaStream> {
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) throw new Error('Camera capture needs localhost or HTTPS. Open http://localhost:3000 in Chrome or Edge.');
  let timeout: ReturnType<typeof setTimeout>;
  let cancel: () => void = () => {};
  const aborted = new Promise<never>((_, reject) => {
    cancel = () => reject(new Error('Camera startup cancelled.'));
    signal.addEventListener('abort', cancel, { once: true });
    timeout = setTimeout(() => reject(new Error('Camera permission is still pending. Allow access in the browser, then try again.')), 30000);
  });
  let accepted = false, expired = false;
  const request = navigator.mediaDevices.getUserMedia({ audio: false, video: {
    ...(deviceId ? { deviceId: { exact: deviceId } } : { facingMode: 'user' }),
    width: { ideal: 960 }, height: { ideal: 720 }, frameRate: { ideal: 30, max: 30 },
  }}).catch(error => {
    if (error?.name !== 'OverconstrainedError' || signal.aborted) throw error;
    return navigator.mediaDevices.getUserMedia({ audio: false, video: deviceId ? { deviceId: { exact: deviceId } } : true });
  }).then(stream => {
    if (signal.aborted || expired) { stopStream(stream); throw new Error('Camera startup cancelled.'); }
    return stream;
  });
  try {
    if (signal.aborted) throw new Error('Camera startup cancelled.');
    const stream = await Promise.race([request, aborted]); accepted = true; return stream;
  } finally {
    expired = !accepted; clearTimeout(timeout!); signal.removeEventListener('abort', cancel);
    // A browser permission prompt cannot be programmatically dismissed. Clean up late approval.
    if (!accepted) void request.then(stopStream, () => {});
  }
}
export async function playCamera(video: HTMLVideoElement, stream: MediaStream, signal: AbortSignal) {
  video.srcObject = stream;
  video.muted = true;
  video.playsInline = true;
  await new Promise<void>((resolve, reject) => {
    let done = false;
    const finish = (error?: Error) => {
      if (done) return; done = true;
      clearInterval(poll); clearTimeout(timeout); signal.removeEventListener('abort', abort);
      error ? reject(error) : resolve();
    };
    const abort = () => finish(new Error('Camera startup cancelled.'));
    const poll = setInterval(() => { if (video.readyState >= 2 && video.videoWidth > 0 && video.videoHeight > 0) finish(); }, 40);
    const timeout = setTimeout(() => finish(new Error('The camera opened but sent no video. Select another camera or close other camera apps.')), 10000);
    signal.addEventListener('abort', abort, { once: true });
    void video.play().catch(error => finish(new Error('Video playback could not begin: ' + errorText(error))));
    if (signal.aborted) abort();
  });
}
